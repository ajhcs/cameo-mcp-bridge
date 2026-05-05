package com.claude.cameo.bridge.handlers;

import com.claude.cameo.bridge.HttpBridgeServer;
import com.claude.cameo.bridge.util.EdtDispatcher;
import com.claude.cameo.bridge.util.ElementSerializer;
import com.claude.cameo.bridge.util.JsonHelper;
import com.google.gson.JsonArray;
import com.google.gson.JsonObject;
import com.nomagic.generictable.GenericTableManager;
import com.nomagic.magicdraw.properties.Property;
import com.nomagic.magicdraw.uml.ClassTypes;
import com.nomagic.magicdraw.uml.symbols.DiagramPresentationElement;
import com.nomagic.uml2.ext.jmi.helpers.StereotypesHelper;
import com.nomagic.uml2.ext.magicdraw.classes.mdkernel.Diagram;
import com.nomagic.uml2.ext.magicdraw.classes.mdkernel.Element;
import com.nomagic.uml2.ext.magicdraw.classes.mdkernel.Namespace;
import com.nomagic.uml2.ext.magicdraw.mdprofiles.Stereotype;
import com.sun.net.httpserver.HttpExchange;
import com.sun.net.httpserver.HttpHandler;

import java.io.IOException;
import java.util.ArrayList;
import java.util.Collection;
import java.util.List;
import java.util.Map;
import java.util.concurrent.TimeoutException;

public class GenericTableHandler implements HttpHandler {

    private static final String PREFIX = "/api/v1/generic-tables/";
    private static final String GENERIC_TABLE_TYPE = "Generic Table";

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

            if ("GET".equals(method) && path.equals("/api/v1/generic-tables/columns")) {
                handlePossibleColumns(exchange);
                return;
            }

            String tableId = JsonHelper.extractPathParam(exchange, PREFIX);
            if ("GET".equals(method) && tableId != null) {
                handleGetTable(exchange, tableId);
                return;
            }
            if ("GET".equals(method)) {
                handleListTables(exchange);
                return;
            }
            if ("POST".equals(method)) {
                handleCreateTable(exchange);
                return;
            }

            HttpBridgeServer.sendError(exchange, 405, "METHOD_NOT_ALLOWED",
                    "Only GET, POST, and OPTIONS are supported");
        } catch (Exception e) {
            HttpBridgeServer.sendError(exchange, 500, "GENERIC_TABLE_ERROR", e.getMessage());
        }
    }

    private void handleListTables(HttpExchange exchange) throws Exception {
        JsonObject result = EdtDispatcher.read(project -> {
            JsonArray tables = new JsonArray();
            Collection<DiagramPresentationElement> diagrams = project.getDiagrams();
            if (diagrams != null) {
                for (DiagramPresentationElement dpe : diagrams) {
                    if (GENERIC_TABLE_TYPE.equals(diagramType(dpe))) {
                        tables.add(toSummaryJson(dpe));
                    }
                }
            }
            JsonObject response = new JsonObject();
            response.addProperty("count", tables.size());
            response.add("tables", tables);
            return response;
        });
        HttpBridgeServer.sendJson(exchange, 200, result);
    }

    private void handleGetTable(HttpExchange exchange, String tableId) throws Exception {
        JsonObject result = EdtDispatcher.read(project -> serializeTable(project, tableId));
        HttpBridgeServer.sendJson(exchange, 200, result);
    }

    private void handlePossibleColumns(HttpExchange exchange) throws Exception {
        Map<String, String> params = JsonHelper.parseQuery(exchange);
        String elementId = params.get("elementId");
        String elementType = params.get("elementType");
        if ((elementId == null || elementId.isEmpty()) && (elementType == null || elementType.isEmpty())) {
            throw new IllegalArgumentException("elementId or elementType is required");
        }

        JsonObject result = EdtDispatcher.read(project -> {
            Element basis = elementId != null && !elementId.isEmpty()
                    ? resolveElement(project, elementId, "Column basis element")
                    : resolveTypeElement(project, elementType);
            JsonArray columns = new JsonArray();
            for (String id : GenericTableManager.getPossibleColumnIDs(basis)) {
                JsonObject column = new JsonObject();
                column.addProperty("id", id);
                column.addProperty("name", id);
                columns.add(column);
            }
            JsonObject response = new JsonObject();
            response.add("basis", ElementSerializer.toJsonCompact(basis));
            response.addProperty("count", columns.size());
            response.add("columns", columns);
            return response;
        });
        HttpBridgeServer.sendJson(exchange, 200, result);
    }

    private void handleCreateTable(HttpExchange exchange) throws Exception {
        JsonObject body = JsonHelper.parseBody(exchange);
        String parentId = JsonHelper.requireString(body, "parentId");
        String name = JsonHelper.optionalString(body, "name");
        List<String> elementTypes = JsonHelper.optionalStringList(body, "elementTypes");
        List<String> scopeIds = JsonHelper.optionalStringList(body, "scopeIds");
        List<String> rowElementIds = JsonHelper.optionalStringList(body, "rowElementIds");
        List<String> columnIds = JsonHelper.optionalStringList(body, "columnIds");
        if (name == null || name.isEmpty()) {
            name = "Generic Table";
        }

        String finalName = name;
        JsonObject result = EdtDispatcher.write("MCP Bridge: Create Generic Table", project -> {
            Element parent = resolveElement(project, parentId, "Parent element");
            if (!(parent instanceof Namespace)) {
                throw new IllegalArgumentException("Parent element is not a Namespace: " + parentId);
            }

            Diagram diagram = com.nomagic.magicdraw.openapi.uml.ModelElementsManager.getInstance()
                    .createDiagram(GENERIC_TABLE_TYPE, (Namespace) parent);
            if (diagram == null) {
                throw new IllegalStateException("Failed to create Generic Table");
            }
            diagram.setName(finalName);

            if (elementTypes != null && !elementTypes.isEmpty()) {
                GenericTableManager.setTableElementTypes(diagram, resolveTypes(project, elementTypes));
            }
            if (scopeIds != null && !scopeIds.isEmpty()) {
                GenericTableManager.setScope(diagram, resolveElements(project, scopeIds, "Scope element"));
            }
            if (rowElementIds != null && !rowElementIds.isEmpty()) {
                for (Element row : resolveElements(project, rowElementIds, "Row element")) {
                    GenericTableManager.addRowElement(diagram, row);
                }
            }
            if (columnIds != null && !columnIds.isEmpty()) {
                GenericTableManager.addColumnsById(diagram, columnIds);
            }
            refresh(diagram);

            JsonObject response = new JsonObject();
            response.addProperty("created", true);
            response.add("table", serializeTable(project, diagram.getID()));
            return response;
        });
        HttpBridgeServer.sendJson(exchange, 201, result);
    }

    private JsonObject serializeTable(com.nomagic.magicdraw.core.Project project, String tableId) {
        Diagram diagram = resolveDiagram(project, tableId);
        refresh(diagram);

        JsonObject response = toSummaryJson(project.getDiagram(diagram));
        JsonArray scopes = new JsonArray();
        for (Element scope : GenericTableManager.getScope(diagram)) {
            scopes.add(ElementSerializer.toJsonCompact(scope));
        }
        response.add("scope", scopes);

        JsonArray rows = new JsonArray();
        for (Element row : GenericTableManager.getRowElements(diagram)) {
            rows.add(ElementSerializer.toJsonCompact(row));
        }
        response.add("rows", rows);
        response.addProperty("rowCount", rows.size());

        List<String> columnIds = GenericTableManager.getColumnIds(diagram);
        List<String> columnNames = GenericTableManager.getColumnNames(diagram);
        JsonArray columns = new JsonArray();
        for (int i = 0; i < columnIds.size(); i++) {
            JsonObject column = new JsonObject();
            column.addProperty("id", columnIds.get(i));
            column.addProperty("name", i < columnNames.size() ? columnNames.get(i) : columnIds.get(i));
            columns.add(column);
        }
        response.add("columns", columns);
        response.addProperty("columnCount", columns.size());

        JsonArray cells = new JsonArray();
        Map<Element, Map<String, Property>> values = GenericTableManager.getCellValues(diagram);
        for (Map.Entry<Element, Map<String, Property>> rowEntry : values.entrySet()) {
            for (Map.Entry<String, Property> cellEntry : rowEntry.getValue().entrySet()) {
                JsonObject cell = new JsonObject();
                cell.add("row", ElementSerializer.toJsonCompact(rowEntry.getKey()));
                cell.addProperty("columnId", cellEntry.getKey());
                Property value = cellEntry.getValue();
                cell.addProperty("value", value != null ? value.getValueStringRepresentation() : "");
                cells.add(cell);
            }
        }
        response.add("cells", cells);
        response.addProperty("cellCount", cells.size());
        return response;
    }

    private void refresh(Diagram diagram) {
        GenericTableManager.refreshTable(diagram);
        try {
            GenericTableManager.waitForCellValuesLoad(diagram);
        } catch (TimeoutException | InterruptedException e) {
            if (e instanceof InterruptedException) {
                Thread.currentThread().interrupt();
            }
        }
    }

    private JsonObject toSummaryJson(DiagramPresentationElement dpe) {
        JsonObject json = new JsonObject();
        Diagram diagram = dpe != null ? dpe.getDiagram() : null;
        json.addProperty("id", diagram != null ? diagram.getID() : "");
        json.addProperty("name", dpe != null && dpe.getName() != null ? dpe.getName() : "");
        json.addProperty("type", dpe != null ? diagramType(dpe) : GENERIC_TABLE_TYPE);
        if (diagram != null && diagram.getOwner() instanceof Element) {
            Element owner = (Element) diagram.getOwner();
            json.addProperty("ownerId", owner.getID());
            if (owner instanceof com.nomagic.uml2.ext.magicdraw.classes.mdkernel.NamedElement namedOwner) {
                json.addProperty("ownerName", namedOwner.getName());
            }
        }
        return json;
    }

    private String diagramType(DiagramPresentationElement dpe) {
        return dpe != null && dpe.getDiagramType() != null ? dpe.getDiagramType().getType() : "";
    }

    private Diagram resolveDiagram(com.nomagic.magicdraw.core.Project project, String tableId) {
        Object element = project.getElementByID(tableId);
        if (element instanceof Diagram diagram) {
            return diagram;
        }
        throw new IllegalArgumentException("Generic Table not found: " + tableId);
    }

    private Element resolveElement(com.nomagic.magicdraw.core.Project project, String elementId, String label) {
        Object element = project.getElementByID(elementId);
        if (element instanceof Element resolved) {
            return resolved;
        }
        throw new IllegalArgumentException(label + " not found: " + elementId);
    }

    private List<Element> resolveElements(
            com.nomagic.magicdraw.core.Project project,
            List<String> ids,
            String label) {
        List<Element> elements = new ArrayList<>(ids.size());
        for (String id : ids) {
            elements.add(resolveElement(project, id, label));
        }
        return elements;
    }

    private List<Object> resolveTypes(com.nomagic.magicdraw.core.Project project, List<String> typeNames) {
        List<Object> resolved = new ArrayList<>(typeNames.size());
        for (String typeName : typeNames) {
            resolved.add(resolveTypeReference(project, typeName));
        }
        return resolved;
    }

    private Element resolveTypeElement(com.nomagic.magicdraw.core.Project project, String typeName) {
        Object type = resolveTypeReference(project, typeName);
        if (type instanceof Element element) {
            return element;
        }
        throw new IllegalArgumentException("Could not resolve type element: " + typeName);
    }

    private Object resolveTypeReference(com.nomagic.magicdraw.core.Project project, String typeName) {
        Stereotype stereotype = resolveStereotype(project, typeName);
        if (stereotype != null) {
            return stereotype;
        }

        com.nomagic.uml2.ext.magicdraw.classes.mdkernel.Class metaClass = resolveMetaClass(project, typeName);
        if (metaClass != null) {
            return metaClass;
        }

        throw new IllegalArgumentException("Unknown Generic Table element type: " + typeName);
    }

    private Stereotype resolveStereotype(com.nomagic.magicdraw.core.Project project, String stereotypeName) {
        String normalized = normalizeTypeToken(stereotypeName);
        Collection<Stereotype> stereotypes = StereotypesHelper.getAllStereotypes(project);
        if (stereotypes == null) {
            return null;
        }
        for (Stereotype stereotype : stereotypes) {
            if (normalized.equals(normalizeTypeToken(stereotype.getName()))) {
                return stereotype;
            }
        }
        return null;
    }

    private com.nomagic.uml2.ext.magicdraw.classes.mdkernel.Class resolveMetaClass(
            com.nomagic.magicdraw.core.Project project,
            String rawTypeName) {
        java.lang.Class<?> metaclass = ClassTypes.getClassType(rawTypeName);
        if (metaclass == null) {
            return null;
        }
        String shortName = ClassTypes.getShortName(metaclass);
        return shortName != null && !shortName.isEmpty()
                ? StereotypesHelper.getMetaClassByName(project, shortName)
                : null;
    }

    private String normalizeTypeToken(String input) {
        return input == null ? "" : input.replaceAll("[^A-Za-z0-9]+", "").toLowerCase();
    }
}
