package com.claude.cameo.bridge.handlers;

import com.claude.cameo.bridge.HttpBridgeServer;
import com.claude.cameo.bridge.util.EdtDispatcher;
import com.claude.cameo.bridge.util.ElementSerializer;
import com.claude.cameo.bridge.util.JsonHelper;
import com.google.gson.JsonArray;
import com.google.gson.JsonObject;
import com.nomagic.magicdraw.dependencymatrix.DependencyMatrix;
import com.nomagic.magicdraw.dependencymatrix.MatrixManager;
import com.nomagic.magicdraw.dependencymatrix.configuration.MatrixDataHelper;
import com.nomagic.magicdraw.dependencymatrix.datamodel.MatrixData;
import com.nomagic.magicdraw.dependencymatrix.datamodel.cell.AbstractMatrixCell;
import com.nomagic.magicdraw.dependencymatrix.datamodel.cell.DependencyEntry;
import com.nomagic.magicdraw.dependencymatrix.persistence.FilterSettings;
import com.nomagic.magicdraw.dependencymatrix.persistence.MatrixSettings;
import com.nomagic.magicdraw.dependencymatrix.persistence.PersistenceManager;
import com.nomagic.magicdraw.uml.symbols.DiagramPresentationElement;
import com.nomagic.uml2.ext.jmi.helpers.StereotypesHelper;
import com.nomagic.uml2.ext.magicdraw.classes.mdkernel.Diagram;
import com.nomagic.uml2.ext.magicdraw.classes.mdkernel.Element;
import com.nomagic.uml2.ext.magicdraw.classes.mdkernel.NamedElement;
import com.nomagic.uml2.ext.magicdraw.classes.mdkernel.Namespace;
import com.nomagic.uml2.ext.magicdraw.mdprofiles.Profile;
import com.nomagic.uml2.ext.magicdraw.mdprofiles.Stereotype;
import com.sun.net.httpserver.HttpExchange;
import com.sun.net.httpserver.HttpHandler;

import java.io.IOException;
import java.util.ArrayList;
import java.util.Collection;
import java.util.List;
import java.util.Map;
import java.util.logging.Level;
import java.util.logging.Logger;

public class MatrixHandler implements HttpHandler {

    private static final Logger LOG = Logger.getLogger(MatrixHandler.class.getName());
    private static final String PREFIX = "/api/v1/matrices/";
    private static final String SYSML_PROFILE = "SysML";

    @Override
    public void handle(HttpExchange exchange) throws IOException {
        try {
            String method = exchange.getRequestMethod();
            String path = exchange.getRequestURI().getPath();

            if ("OPTIONS".equals(method)) {
                exchange.getResponseHeaders().set("Access-Control-Allow-Methods",
                        "GET, POST, OPTIONS");
                exchange.getResponseHeaders().set("Access-Control-Allow-Headers", "Content-Type");
                exchange.sendResponseHeaders(204, -1);
                return;
            }

            String matrixId = JsonHelper.extractPathParam(exchange, PREFIX);
            String subPath = JsonHelper.extractSubPath(exchange, PREFIX);

            if ("GET".equals(method)) {
                if ("/api/v1/matrices".equals(path)) {
                    handleListMatrices(exchange);
                } else if (matrixId != null && subPath == null) {
                    handleGetMatrix(exchange, matrixId);
                } else {
                    HttpBridgeServer.sendError(exchange, 404, "NOT_FOUND",
                            "Unknown endpoint: " + path);
                }
                return;
            }

            if ("POST".equals(method)) {
                if ("/api/v1/matrices".equals(path)) {
                    handleCreateMatrix(exchange);
                } else {
                    HttpBridgeServer.sendError(exchange, 404, "NOT_FOUND",
                            "Unknown endpoint: " + path);
                }
                return;
            }

            HttpBridgeServer.sendError(exchange, 405, "METHOD_NOT_ALLOWED",
                    "Method not supported: " + method);
        } catch (IllegalArgumentException e) {
            HttpBridgeServer.sendError(exchange, 400, "BAD_REQUEST", e.getMessage());
        } catch (IllegalStateException e) {
            HttpBridgeServer.sendError(exchange, 409, "CONFLICT", e.getMessage());
        } catch (Exception e) {
            LOG.log(Level.SEVERE, "Error in MatrixHandler", e);
            HttpBridgeServer.sendError(exchange, 500, "INTERNAL_ERROR", e.getMessage());
        }
    }

    private void handleListMatrices(HttpExchange exchange) throws Exception {
        Map<String, String> query = JsonHelper.parseQuery(exchange);
        MatrixKind filterKind = parseOptionalKind(query.get("kind"));
        String ownerId = query.get("ownerId");

        JsonObject result = EdtDispatcher.read(project -> {
            JsonArray matrices = new JsonArray();
            Collection<DiagramPresentationElement> diagrams = project.getDiagrams();

            if (diagrams != null) {
                for (DiagramPresentationElement dpe : diagrams) {
                    Diagram diagram = dpe.getDiagram();
                    if (diagram == null) {
                        continue;
                    }

                    MatrixKind kind = MatrixKind.fromDiagramType(diagramType(dpe));
                    if (kind == null) {
                        continue;
                    }
                    if (filterKind != null && kind != filterKind) {
                        continue;
                    }
                    if (ownerId != null && !ownerId.isEmpty()) {
                        Element owner = diagram.getOwner();
                        if (owner == null || !ownerId.equals(owner.getID())) {
                            continue;
                        }
                    }

                    matrices.add(toSummaryJson(kind, dpe));
                }
            }

            JsonObject response = new JsonObject();
            response.addProperty("count", matrices.size());
            if (filterKind != null) {
                response.addProperty("kind", filterKind.apiName);
            }
            if (ownerId != null && !ownerId.isEmpty()) {
                response.addProperty("ownerId", ownerId);
            }
            response.add("matrices", matrices);
            return response;
        });

        HttpBridgeServer.sendJson(exchange, 200, result);
    }

    private void handleGetMatrix(HttpExchange exchange, String matrixId) throws Exception {
        JsonObject result = EdtDispatcher.read(project -> serializeMatrix(project, matrixId));
        HttpBridgeServer.sendJson(exchange, 200, result);
    }

    private void handleCreateMatrix(HttpExchange exchange) throws Exception {
        JsonObject body = JsonHelper.parseBody(exchange);
        MatrixKind kind = MatrixKind.require(JsonHelper.requireString(body, "kind"));
        String parentId = JsonHelper.requireString(body, "parentId");
        String scopeId = JsonHelper.optionalString(body, "scopeId");
        String rowScopeId = JsonHelper.optionalString(body, "rowScopeId");
        String columnScopeId = JsonHelper.optionalString(body, "columnScopeId");
        String name = JsonHelper.optionalString(body, "name");

        JsonObject result = EdtDispatcher.write("MCP Bridge: Create " + kind.diagramType, project -> {
            Element parentElement = resolveElement(project, parentId, "Parent element");
            if (!(parentElement instanceof Namespace)) {
                throw new IllegalArgumentException(
                        "Parent element is not a Namespace: " + parentId);
            }

            String resolvedRowScopeId = firstNonEmpty(rowScopeId, scopeId, parentId);
            String resolvedColumnScopeId = firstNonEmpty(columnScopeId, scopeId, parentId);
            Element rowScope = resolveElement(project, resolvedRowScopeId, "Row scope element");
            Element columnScope = resolveElement(project, resolvedColumnScopeId, "Column scope element");

            Diagram diagram = com.nomagic.magicdraw.openapi.uml.ModelElementsManager.getInstance()
                    .createDiagram(kind.diagramType, (Namespace) parentElement);
            if (diagram == null) {
                throw new IllegalStateException("Failed to create matrix diagram: " + kind.diagramType);
            }
            if (name != null && !name.isEmpty()) {
                diagram.setName(name);
            }

            configureMatrix(project, diagram, kind, rowScope, columnScope);

            JsonObject response = new JsonObject();
            response.addProperty("created", true);
            response.add("matrix", serializeMatrix(project, diagram.getID()));

            JsonObject receipt = new JsonObject();
            receipt.addProperty("operation", "createMatrix");
            receipt.addProperty("kind", kind.apiName);
            receipt.addProperty("matrixId", diagram.getID());
            receipt.addProperty("status", "created");
            response.add("receipt", receipt);
            return response;
        });

        HttpBridgeServer.sendJson(exchange, 201, result);
    }

    private void configureMatrix(
            com.nomagic.magicdraw.core.Project project,
            Diagram diagram,
            MatrixKind kind,
            Element rowScope,
            Element columnScope) {
        PersistenceManager persistenceManager = new PersistenceManager(diagram);
        MatrixSettings settings = persistenceManager.getMatrixSettings();
        settings.setDirection(MatrixSettings.Direction.ROW_TO_COLUMN);
        settings.setShowElementsOption(MatrixSettings.RelationOption.ALL);

        FilterSettings rowSettings = persistenceManager.getRowSettings();
        FilterSettings columnSettings = persistenceManager.getColumnSettings();

        rowSettings.setScope(List.of(rowScope));
        rowSettings.setScopeDefined(true);
        rowSettings.setTypesIncludeSubtypes(true);
        rowSettings.setTypesIncludeCustomTypes(true);
        rowSettings.setConvertedElementTypes(kind.resolveRowTypes(project));

        columnSettings.setScope(List.of(columnScope));
        columnSettings.setScopeDefined(true);
        columnSettings.setTypesIncludeSubtypes(true);
        columnSettings.setTypesIncludeCustomTypes(true);
        columnSettings.setConvertedElementTypes(kind.resolveColumnTypes(project));
    }

    private JsonObject serializeMatrix(com.nomagic.magicdraw.core.Project project, String matrixId) {
        MatrixContext context = resolveMatrix(project, matrixId);
        DependencyMatrix matrix = MatrixManager.getExistingOrCreate(context.diagram, context.dpe);
        matrix.viewCreated();
        matrix.setActive(true);
        try {
            MatrixData data = MatrixDataHelper.buildMatrix(context.diagram);
            PersistenceManager persistenceManager = new PersistenceManager(context.diagram);

            JsonObject response = toSummaryJson(context.kind, context.dpe);
            response.add("rowScopes", serializeElements(persistenceManager.getRowSettings().getScope()));
            response.add("columnScopes", serializeElements(persistenceManager.getColumnSettings().getScope()));
            response.add("rowTypes", serializeElements(persistenceManager.getRowSettings().getElementTypes()));
            response.add("columnTypes", serializeElements(persistenceManager.getColumnSettings().getElementTypes()));

            JsonArray rows = serializeElements(data.getRowElements());
            JsonArray columns = serializeElements(data.getColumnElements());
            JsonArray populatedCells = new JsonArray();

            Collection<Element> rowElements = data.getRowElements();
            Collection<Element> columnElements = data.getColumnElements();
            for (Element row : rowElements) {
                for (Element column : columnElements) {
                    AbstractMatrixCell cell = data.getValue(row, column);
                    if (cell == null || cell.getDependencies().isEmpty()) {
                        continue;
                    }

                    JsonObject cellJson = new JsonObject();
                    cellJson.add("row", ElementSerializer.toJsonCompact(row));
                    cellJson.add("column", ElementSerializer.toJsonCompact(column));
                    JsonArray dependencies = new JsonArray();
                    for (DependencyEntry entry : cell.getDependencies()) {
                        JsonObject depJson = new JsonObject();
                        depJson.addProperty("type", entry.getType());
                        depJson.addProperty("name", entry.getName());
                        depJson.add("cause", serializeElements(entry.getCause()));
                        dependencies.add(depJson);
                    }
                    cellJson.addProperty("dependencyCount", dependencies.size());
                    cellJson.add("dependencies", dependencies);
                    populatedCells.add(cellJson);
                }
            }

            response.addProperty("rowCount", rows.size());
            response.addProperty("columnCount", columns.size());
            response.addProperty("totalCellCount", rows.size() * columns.size());
            response.addProperty("populatedCellCount", populatedCells.size());
            response.addProperty("empty", data.isEmpty());
            response.add("rows", rows);
            response.add("columns", columns);
            response.add("populatedCells", populatedCells);
            return response;
        } finally {
            matrix.setActive(false);
            matrix.viewDisposed();
        }
    }

    private JsonObject toSummaryJson(MatrixKind kind, DiagramPresentationElement dpe) {
        JsonObject summary = new JsonObject();
        Diagram diagram = dpe.getDiagram();
        summary.addProperty("id", diagram.getID());
        summary.addProperty("name", dpe.getName() != null ? dpe.getName() : "");
        summary.addProperty("kind", kind.apiName);
        summary.addProperty("matrixType", kind.diagramType);

        Element owner = diagram.getOwner();
        if (owner != null) {
            summary.addProperty("ownerId", owner.getID());
            if (owner instanceof NamedElement) {
                summary.addProperty("ownerName", ((NamedElement) owner).getName());
            }
        }
        return summary;
    }

    private JsonArray serializeElements(Collection<? extends Element> elements) {
        JsonArray array = new JsonArray();
        if (elements == null) {
            return array;
        }
        for (Element element : elements) {
            array.add(ElementSerializer.toJsonCompact(element));
        }
        return array;
    }

    private MatrixContext resolveMatrix(com.nomagic.magicdraw.core.Project project, String matrixId) {
        DiagramPresentationElement dpe = findDiagramById(project, matrixId);
        MatrixKind kind = MatrixKind.fromDiagramType(diagramType(dpe));
        if (kind == null) {
            throw new IllegalArgumentException(
                    "Matrix is not a supported refine/derive matrix: " + matrixId);
        }
        dpe.ensureLoaded();
        return new MatrixContext(kind, dpe.getDiagram(), dpe);
    }

    private DiagramPresentationElement findDiagramById(com.nomagic.magicdraw.core.Project project, String matrixId) {
        Object baseElement = project.getElementByID(matrixId);
        if (baseElement instanceof Diagram) {
            DiagramPresentationElement dpe = project.getDiagram((Diagram) baseElement);
            if (dpe != null) {
                return dpe;
            }
        }

        Collection<DiagramPresentationElement> diagrams = project.getDiagrams();
        if (diagrams != null) {
            for (DiagramPresentationElement dpe : diagrams) {
                Diagram diagram = dpe.getDiagram();
                if (diagram != null && matrixId.equals(diagram.getID())) {
                    return dpe;
                }
            }
        }

        throw new IllegalArgumentException("Matrix not found: " + matrixId);
    }

    private Element resolveElement(
            com.nomagic.magicdraw.core.Project project,
            String elementId,
            String label) {
        Element element = (Element) project.getElementByID(elementId);
        if (element == null) {
            throw new IllegalArgumentException(label + " not found: " + elementId);
        }
        return element;
    }

    private MatrixKind parseOptionalKind(String rawKind) {
        if (rawKind == null || rawKind.isEmpty()) {
            return null;
        }
        return MatrixKind.require(rawKind);
    }

    private String firstNonEmpty(String... candidates) {
        for (String candidate : candidates) {
            if (candidate != null && !candidate.isEmpty()) {
                return candidate;
            }
        }
        return null;
    }

    private String diagramType(DiagramPresentationElement dpe) {
        return dpe.getDiagramType() != null ? dpe.getDiagramType().getType() : "";
    }

    private static final class MatrixContext {
        private final MatrixKind kind;
        private final Diagram diagram;
        private final DiagramPresentationElement dpe;

        private MatrixContext(MatrixKind kind, Diagram diagram, DiagramPresentationElement dpe) {
            this.kind = kind;
            this.diagram = diagram;
            this.dpe = dpe;
        }
    }

    private enum MatrixKind {
        REFINE("refine", "Refine Requirement Matrix", "Block", "Requirement"),
        DERIVE("derive", "Derive Requirement Matrix", "Requirement", "Requirement");

        private final String apiName;
        private final String diagramType;
        private final String rowStereotype;
        private final String columnStereotype;

        MatrixKind(String apiName, String diagramType, String rowStereotype, String columnStereotype) {
            this.apiName = apiName;
            this.diagramType = diagramType;
            this.rowStereotype = rowStereotype;
            this.columnStereotype = columnStereotype;
        }

        private static MatrixKind require(String rawValue) {
            MatrixKind kind = fromInput(rawValue);
            if (kind == null) {
                throw new IllegalArgumentException(
                        "Unsupported matrix kind: " + rawValue
                                + ". Supported: refine, derive");
            }
            return kind;
        }

        private static MatrixKind fromInput(String rawValue) {
            if (rawValue == null) {
                return null;
            }
            String normalized = rawValue.toLowerCase().replaceAll("[^a-z0-9]+", "");
            switch (normalized) {
                case "refine":
                case "refinerequirementmatrix":
                    return REFINE;
                case "derive":
                case "deriverequirementmatrix":
                    return DERIVE;
                default:
                    return null;
            }
        }

        private static MatrixKind fromDiagramType(String diagramType) {
            for (MatrixKind kind : values()) {
                if (kind.diagramType.equals(diagramType)) {
                    return kind;
                }
            }
            return null;
        }

        private List<Object> resolveRowTypes(com.nomagic.magicdraw.core.Project project) {
            return List.of(resolveRequiredStereotype(project, rowStereotype));
        }

        private List<Object> resolveColumnTypes(com.nomagic.magicdraw.core.Project project) {
            return List.of(resolveRequiredStereotype(project, columnStereotype));
        }

        private Stereotype resolveRequiredStereotype(
                com.nomagic.magicdraw.core.Project project,
                String stereotypeName) {
            Profile profile = StereotypesHelper.getProfile(project, SYSML_PROFILE);
            if (profile == null) {
                throw new IllegalStateException("SysML profile is not available in the open project");
            }
            Stereotype stereotype = StereotypesHelper.getStereotype(project, stereotypeName, profile);
            if (stereotype == null) {
                throw new IllegalStateException(
                        "Required SysML stereotype is not available: " + stereotypeName);
            }
            return stereotype;
        }
    }
}
