package com.claude.cameo.bridge.handlers;

import com.claude.cameo.bridge.HttpBridgeServer;
import com.claude.cameo.bridge.util.CompartmentAliasResolver;
import com.claude.cameo.bridge.util.EdtDispatcher;
import com.claude.cameo.bridge.util.ElementSerializer;
import com.claude.cameo.bridge.util.JsonHelper;
import com.nomagic.magicdraw.core.Project;
import com.nomagic.magicdraw.export.image.ImageExporter;
import com.nomagic.magicdraw.openapi.uml.ModelElementsManager;
import com.nomagic.magicdraw.openapi.uml.PresentationElementsManager;
import com.nomagic.magicdraw.uml.ClassTypes;
import com.nomagic.magicdraw.uml.symbols.DiagramPresentationElement;
import com.nomagic.magicdraw.uml.symbols.PresentationElement;
import com.nomagic.magicdraw.uml.symbols.shapes.ShapeElement;
import com.nomagic.magicdraw.uml.symbols.paths.PathElement;
import com.nomagic.magicdraw.visualization.relationshipmap.RelationshipMapUtilities;
import com.nomagic.magicdraw.visualization.relationshipmap.model.settings.BasicGraphSettings;
import com.nomagic.magicdraw.properties.PropertyManager;
import com.nomagic.magicdraw.properties.Property;
import com.nomagic.uml2.ext.jmi.helpers.StereotypesHelper;
import com.nomagic.uml2.ext.magicdraw.classes.mdkernel.Comment;
import com.nomagic.uml2.ext.magicdraw.classes.mdkernel.Diagram;
import com.nomagic.uml2.ext.magicdraw.classes.mdkernel.Element;
import com.nomagic.uml2.ext.magicdraw.classes.mdkernel.NamedElement;
import com.nomagic.uml2.ext.magicdraw.classes.mdkernel.Namespace;
import com.nomagic.uml2.ext.magicdraw.activities.mdintermediateactivities.ActivityPartition;
import com.nomagic.uml2.ext.magicdraw.mdprofiles.Stereotype;
import com.sun.net.httpserver.HttpExchange;
import com.sun.net.httpserver.HttpHandler;
import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;

import javax.imageio.ImageIO;
import java.awt.Point;
import java.awt.Rectangle;
import java.awt.image.BufferedImage;
import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.lang.reflect.Method;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.Base64;
import java.util.Collection;
import java.util.Collections;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.function.Predicate;
import java.util.logging.Level;
import java.util.logging.Logger;

/**
 * Handles diagram REST endpoints.
 */
public class DiagramHandler implements HttpHandler {

    private static final Logger LOG = Logger.getLogger(DiagramHandler.class.getName());
    private static final String PREFIX = "/api/v1/diagrams/";

    @Override
    public void handle(HttpExchange exchange) throws IOException {
        try {
            String method = exchange.getRequestMethod();
            String path = exchange.getRequestURI().getPath();

            if ("OPTIONS".equals(method)) {
                exchange.getResponseHeaders().set("Access-Control-Allow-Methods",
                        "GET, POST, PUT, DELETE, OPTIONS");
                exchange.getResponseHeaders().set("Access-Control-Allow-Headers", "Content-Type");
                exchange.sendResponseHeaders(204, -1);
                return;
            }

            String diagramId = JsonHelper.extractPathParam(exchange, PREFIX);
            String subPath = JsonHelper.extractSubPath(exchange, PREFIX);

            if ("GET".equals(method)) {
                if (path.equals("/api/v1/diagrams")) {
                    handleListDiagrams(exchange);
                } else if (diagramId != null && "image".equals(subPath)) {
                    handleExportImage(exchange, diagramId);
                } else if (diagramId != null && subPath != null
                        && subPath.startsWith("shapes/") && subPath.endsWith("/properties")) {
                    String peId = subPath.substring("shapes/".length(),
                            subPath.length() - "/properties".length());
                    handleGetShapeProperties(exchange, diagramId, peId);
                } else if (diagramId != null && "shapes".equals(subPath)) {
                    handleListShapes(exchange, diagramId);
                } else if (diagramId != null && subPath == null) {
                    handleGetDiagram(exchange, diagramId);
                } else {
                    HttpBridgeServer.sendError(exchange, 404, "NOT_FOUND",
                            "Unknown endpoint: " + path);
                }
            } else if ("POST".equals(method)) {
                if (path.equals("/api/v1/diagrams")) {
                    handleCreateDiagram(exchange);
                } else if (diagramId != null && "elements".equals(subPath)) {
                    handleAddElement(exchange, diagramId);
                } else if (diagramId != null && "layout".equals(subPath)) {
                    handleLayout(exchange, diagramId);
                } else if (diagramId != null && "paths".equals(subPath)) {
                    handleAddPaths(exchange, diagramId);
                } else {
                    HttpBridgeServer.sendError(exchange, 404, "NOT_FOUND",
                            "Unknown endpoint: " + path);
                }
            } else if ("PUT".equals(method)) {
                if (diagramId != null && "shapes".equals(subPath)) {
                    handleMoveResizeShapes(exchange, diagramId);
                } else if (diagramId != null && "shapes/reparent".equals(subPath)) {
                    handleReparentShapes(exchange, diagramId);
                } else if (diagramId != null && "paths/route".equals(subPath)) {
                    handleRoutePaths(exchange, diagramId);
                } else if (diagramId != null && subPath != null
                        && subPath.startsWith("shapes/") && subPath.endsWith("/properties")) {
                    // Extract peId from subPath: shapes/{peId}/properties
                    String peId = subPath.substring("shapes/".length(),
                            subPath.length() - "/properties".length());
                    handleSetShapeProperties(exchange, diagramId, peId);
                } else if (diagramId != null && subPath != null
                        && subPath.startsWith("shapes/") && subPath.endsWith("/compartments")) {
                    String peId = subPath.substring("shapes/".length(),
                            subPath.length() - "/compartments".length());
                    handleSetShapeCompartments(exchange, diagramId, peId);
                } else if (diagramId != null && "presentation/transition-labels".equals(subPath)) {
                    handleConfigureTransitionLabelPresentation(exchange, diagramId);
                } else if (diagramId != null && "presentation/item-flow-labels".equals(subPath)) {
                    handleConfigureItemFlowLabelPresentation(exchange, diagramId);
                } else if (diagramId != null && "repair/path-decorations".equals(subPath)) {
                    handlePrunePathDecorations(exchange, diagramId);
                } else if (diagramId != null && "presentation/allocation-compartments".equals(subPath)) {
                    handleConfigureAllocationCompartmentPresentation(exchange, diagramId);
                } else if (diagramId != null && "repair/hidden-labels".equals(subPath)) {
                    handleRepairHiddenLabels(exchange, diagramId);
                } else if (diagramId != null && "repair/label-positions".equals(subPath)) {
                    handleRepairLabelPositions(exchange, diagramId);
                } else if (diagramId != null && "repair/conveyed-item-labels".equals(subPath)) {
                    handleForceConveyedItemLabels(exchange, diagramId);
                } else if (diagramId != null && "repair/compartment-presets".equals(subPath)) {
                    handleNormalizeCompartmentPresets(exchange, diagramId);
                } else if (diagramId != null && "repair/prune-presentations".equals(subPath)) {
                    handlePrunePresentations(exchange, diagramId);
                } else {
                    HttpBridgeServer.sendError(exchange, 404, "NOT_FOUND",
                            "Unknown endpoint: " + path);
                }
            } else if ("DELETE".equals(method)) {
                if (diagramId != null && "shapes".equals(subPath)) {
                    handleDeleteShapes(exchange, diagramId);
                } else {
                    HttpBridgeServer.sendError(exchange, 404, "NOT_FOUND",
                            "Unknown endpoint: " + path);
                }
            } else {
                HttpBridgeServer.sendError(exchange, 405, "METHOD_NOT_ALLOWED",
                        "Method not supported: " + method);
            }
        } catch (IllegalArgumentException e) {
            HttpBridgeServer.sendError(exchange, 404, "NOT_FOUND", e.getMessage());
        } catch (Exception e) {
            LOG.log(Level.SEVERE, "Error in DiagramHandler", e);
            HttpBridgeServer.sendError(exchange, 500, "INTERNAL_ERROR", e.getMessage());
        }
    }

    private void handleListDiagrams(HttpExchange exchange) throws Exception {
        JsonObject result = EdtDispatcher.read(project -> {
            Collection<DiagramPresentationElement> diagrams = project.getDiagrams();
            JsonArray array = new JsonArray();

            if (diagrams != null) {
                for (DiagramPresentationElement dpe : diagrams) {
                    JsonObject diagramJson = new JsonObject();
                    Diagram diagram = dpe.getDiagram();
                    diagramJson.addProperty("id", diagram.getID());
                    diagramJson.addProperty("name", dpe.getName() != null ? dpe.getName() : "");
                    diagramJson.addProperty("type", dpe.getDiagramType() != null
                            ? dpe.getDiagramType().getType() : "");

                    Element owner = diagram.getOwner();
                    if (owner != null) {
                        diagramJson.addProperty("ownerId", owner.getID());
                        if (owner instanceof NamedElement) {
                            diagramJson.addProperty("ownerName",
                                    ((NamedElement) owner).getName());
                        }
                    }
                    array.add(diagramJson);
                }
            }

            JsonObject response = new JsonObject();
            response.addProperty("count", array.size());
            response.add("diagrams", array);
            return response;
        });

        HttpBridgeServer.sendJson(exchange, 200, result);
    }

    private void handleGetDiagram(HttpExchange exchange, String diagramId) throws Exception {
        JsonObject result = EdtDispatcher.read(project -> {
            DiagramPresentationElement dpe = findDiagramById(project, diagramId);

            JsonObject response = new JsonObject();
            Diagram diagram = dpe.getDiagram();
            response.addProperty("id", diagram.getID());
            response.addProperty("name", dpe.getName() != null ? dpe.getName() : "");
            response.addProperty("type", dpe.getDiagramType() != null
                    ? dpe.getDiagramType().getType() : "");

            Element owner = diagram.getOwner();
            if (owner != null) {
                response.addProperty("ownerId", owner.getID());
                if (owner instanceof NamedElement) {
                    response.addProperty("ownerName", ((NamedElement) owner).getName());
                }
            }

            dpe.ensureLoaded();
            Collection<Element> usedElements = dpe.getUsedModelElements(false);
            JsonArray elementsArray = new JsonArray();
            if (usedElements != null) {
                for (Element el : usedElements) {
                    elementsArray.add(ElementSerializer.toJsonCompact(el));
                }
            }
            response.addProperty("elementCount", elementsArray.size());
            response.add("elements", elementsArray);

            List<PresentationElement> presentationElements = dpe.getPresentationElements();
            JsonArray shapesArray = new JsonArray();
            collectShapes(presentationElements, shapesArray, null);
            response.addProperty("shapeCount", shapesArray.size());
            response.add("shapes", shapesArray);

            return response;
        });

        HttpBridgeServer.sendJson(exchange, 200, result);
    }

    private void handleExportImage(HttpExchange exchange, String diagramId) throws Exception {
        Map<String, String> params = JsonHelper.parseQuery(exchange);
        int scalePercentage = parseScalePercentage(params);

        JsonObject result = EdtDispatcher.read(project -> {
            DiagramPresentationElement dpe = findDiagramById(project, diagramId);
            dpe.ensureLoaded();

            BufferedImage image = ImageExporter.export(dpe, false, scalePercentage);
            if (image == null) {
                throw new IllegalStateException(
                        "ImageExporter returned null for diagram: " + diagramId);
            }

            ByteArrayOutputStream baos = new ByteArrayOutputStream();
            ImageIO.write(image, "PNG", baos);
            String base64 = Base64.getEncoder().encodeToString(baos.toByteArray());

            JsonObject response = new JsonObject();
            response.addProperty("id", diagramId);
            response.addProperty("name", dpe.getName() != null ? dpe.getName() : "");
            response.addProperty("format", "png");
            response.addProperty("width", image.getWidth());
            response.addProperty("height", image.getHeight());
            response.addProperty("scalePercentage", scalePercentage);
            response.addProperty("image", base64);
            return response;
        });

        HttpBridgeServer.sendJson(exchange, 200, result);
    }

    private int parseScalePercentage(Map<String, String> params) {
        String value = params.get("scalePercentage");
        if (value == null || value.isBlank()) {
            value = params.get("scale");
        }
        if (value == null || value.isBlank()) {
            return 100;
        }
        try {
            int parsed = Integer.parseInt(value);
            if (parsed < 25 || parsed > 1000) {
                throw new IllegalArgumentException(
                        "scalePercentage must be between 25 and 1000");
            }
            return parsed;
        } catch (NumberFormatException ex) {
            throw new IllegalArgumentException(
                    "scalePercentage must be an integer between 25 and 1000");
        }
    }

    private void handleCreateDiagram(HttpExchange exchange) throws Exception {
        JsonObject body = JsonHelper.parseBody(exchange);

        if (!body.has("type") || body.get("type").getAsString().isEmpty()) {
            HttpBridgeServer.sendError(exchange, 400, "MISSING_PARAM",
                    "Request body must include a type (diagram type string)");
            return;
        }

        String diagramType = body.get("type").getAsString();
        String name = body.has("name") ? body.get("name").getAsString() : null;
        String parentId = body.has("parentId") ? body.get("parentId").getAsString() : null;
        RelationMapOptions relationMapOptions = RelationMapOptions.fromJson(body);

        JsonObject result = EdtDispatcher.write("MCP Bridge: Create Diagram", project -> {
            Namespace parent;
            if (parentId != null && !parentId.isEmpty()) {
                Element parentElement = (Element) project.getElementByID(parentId);
                if (parentElement == null) {
                    throw new IllegalArgumentException("Parent element not found: " + parentId);
                }
                if (!(parentElement instanceof Namespace)) {
                    throw new IllegalArgumentException(
                            "Parent element is not a Namespace: " + parentId
                                    + " (type: " + parentElement.getHumanType() + ")");
                }
                parent = (Namespace) parentElement;
            } else {
                parent = project.getPrimaryModel();
                if (parent == null) {
                    throw new IllegalStateException("No primary model found in project");
                }
            }

            String resolvedType = resolveDiagramType(diagramType);

            ModelElementsManager mem = ModelElementsManager.getInstance();
            Diagram diagram = mem.createDiagram(resolvedType, parent);

            if (diagram == null) {
                throw new IllegalStateException(
                        "Failed to create diagram of type: " + resolvedType);
            }

            if (name != null && !name.isEmpty()) {
                diagram.setName(name);
            }

            JsonObject response = new JsonObject();
            response.addProperty("id", diagram.getID());
            response.addProperty("name", diagram.getName() != null ? diagram.getName() : "");
            response.addProperty("type", resolvedType);
            response.addProperty("parentId", parent.getID());
            if (isRelationMapType(resolvedType) && relationMapOptions.hasConfiguration()) {
                JsonObject relationMap = configureRelationMap(project, diagram, relationMapOptions);
                response.add("relationMap", relationMap);
            }
            return response;
        });

        HttpBridgeServer.sendJson(exchange, 201, result);
    }

    private boolean isRelationMapType(String diagramType) {
        return "Relation Map Diagram".equals(diagramType);
    }

    private JsonObject configureRelationMap(
            Project project,
            Diagram diagram,
            RelationMapOptions options) {
        BasicGraphSettings settings = new BasicGraphSettings(diagram);

        JsonObject response = new JsonObject();
        response.addProperty("configured", true);

        if (options.contextId != null) {
            Element context = resolveElement(project, options.contextId, "Relation map context element");
            settings.setContextElement(context);
            settings.setMakeElementAsContext(true);
            response.add("context", ElementSerializer.toJsonCompact(context));
        }

        if (options.scopeIds != null) {
            List<Element> scopes = resolveElements(project, options.scopeIds, "Relation map scope element");
            settings.setScopeRoots(scopes);
            JsonArray scopeJson = new JsonArray();
            for (Element scope : scopes) {
                scopeJson.add(ElementSerializer.toJsonCompact(scope));
            }
            response.add("scope", scopeJson);
            response.addProperty("scopeCount", scopes.size());
        }

        if (options.elementTypes != null) {
            List<Element> elementTypes = resolveTypeElements(project, options.elementTypes);
            settings.setElementTypes(elementTypes);
            settings.setTypesIncludeSubtypes(true);
            settings.setIncludeCustomTypes(true);
            JsonArray typesJson = new JsonArray();
            for (Element elementType : elementTypes) {
                typesJson.add(ElementSerializer.toJsonCompact(elementType));
            }
            response.add("elementTypes", typesJson);
            response.addProperty("elementTypeCount", elementTypes.size());
        }

        if (options.dependencyCriteria != null) {
            settings.setDependencyCriterion(options.dependencyCriteria);
            response.addProperty("dependencyCriteriaCount", options.dependencyCriteria.size());
        }

        if (options.depth != null) {
            settings.setDepth(options.depth);
            response.addProperty("depth", options.depth);
        }

        settings.setInitialized(true);
        RelationshipMapUtilities.refreshMap(diagram);
        response.addProperty("refreshed", true);
        return response;
    }

    private Element resolveElement(Project project, String elementId, String label) {
        Object element = project.getElementByID(elementId);
        if (element instanceof Element resolved) {
            return resolved;
        }
        throw new IllegalArgumentException(label + " not found: " + elementId);
    }

    private List<Element> resolveElements(Project project, List<String> ids, String label) {
        List<Element> elements = new ArrayList<>(ids.size());
        for (String id : ids) {
            elements.add(resolveElement(project, id, label));
        }
        return elements;
    }

    private List<Element> resolveTypeElements(Project project, List<String> typeNames) {
        List<Element> resolved = new ArrayList<>(typeNames.size());
        for (String typeName : typeNames) {
            resolved.add(resolveTypeElement(project, typeName));
        }
        return resolved;
    }

    private Element resolveTypeElement(Project project, String typeName) {
        Stereotype stereotype = resolveStereotype(project, typeName);
        if (stereotype != null) {
            return stereotype;
        }

        com.nomagic.uml2.ext.magicdraw.classes.mdkernel.Class metaClass = resolveMetaClass(project, typeName);
        if (metaClass != null) {
            return metaClass;
        }

        throw new IllegalArgumentException("Unknown relation map element type: " + typeName);
    }

    private Stereotype resolveStereotype(Project project, String stereotypeName) {
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
            Project project,
            String rawTypeName) {
        java.lang.Class<?> metaclass = ClassTypes.getClassType(rawTypeName);
        if (metaclass == null) {
            metaclass = ClassTypes.getClassType(normalizeTypeToken(rawTypeName));
        }
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

    private void handleAddElement(HttpExchange exchange, String diagramId) throws Exception {
        JsonObject body = JsonHelper.parseBody(exchange);

        if (!body.has("elementId") || body.get("elementId").getAsString().isEmpty()) {
            HttpBridgeServer.sendError(exchange, 400, "MISSING_PARAM",
                    "Request body must include elementId");
            return;
        }

        String elementId = body.get("elementId").getAsString();
        Integer requestedX = body.has("x") ? body.get("x").getAsInt() : null;
        Integer requestedY = body.has("y") ? body.get("y").getAsInt() : null;
        int x = requestedX != null ? requestedX : 100;
        int y = requestedY != null ? requestedY : 100;
        String containerPeId = JsonHelper.optionalString(body, "containerPresentationId");
        boolean hasWidth = body.has("width");
        boolean hasHeight = body.has("height");

        if (hasWidth != hasHeight) {
            HttpBridgeServer.sendError(exchange, 400, "MISSING_PARAM",
                    "Request body must include both width and height, or neither");
            return;
        }
        Integer requestedWidth = hasWidth ? body.get("width").getAsInt() : null;
        Integer requestedHeight = hasHeight ? body.get("height").getAsInt() : null;

        JsonObject result = EdtDispatcher.write("MCP Bridge: Add Element to Diagram", project -> {
            DiagramPresentationElement dpe = findDiagramById(project, diagramId);
            dpe.ensureLoaded();

            Element element = (Element) project.getElementByID(elementId);
            if (element == null) {
                throw new IllegalArgumentException("Element not found: " + elementId);
            }

            PresentationElementsManager pem = PresentationElementsManager.getInstance();
            PresentationElement shapeParent;
            if (containerPeId != null) {
                shapeParent = findPresentationElement(dpe.getPresentationElements(), containerPeId);
                if (shapeParent == null) {
                    throw new IllegalArgumentException("Container shape not found: " + containerPeId);
                }
            } else {
                shapeParent = dpe;
            }
            DiagramAddResult addResult = addElementPresentation(
                    dpe,
                    element,
                    shapeParent,
                    pem,
                    requestedX,
                    requestedY,
                    requestedWidth,
                    requestedHeight);
            ShapeElement shape = addResult.shape;

            JsonObject response = new JsonObject();
            response.addProperty("diagramId", diagramId);
            response.addProperty("elementId", elementId);
            Rectangle bounds = null;
            try {
                bounds = shape.getBounds();
                if (bounds != null) {
                    response.addProperty("x", bounds.x);
                    response.addProperty("y", bounds.y);
                    response.addProperty("width", bounds.width);
                    response.addProperty("height", bounds.height);
                }
            } catch (Exception e) {
                // Bounds may not be available for all shape types
            }
            if (bounds == null) {
                response.addProperty("x", x);
                response.addProperty("y", y);
            }
            response.addProperty("added", true);
            response.addProperty("presentationId", shape.getID());

            JsonObject receipt = new JsonObject();
            receipt.addProperty("operation", "addShape");
            receipt.addProperty("diagramId", diagramId);
            receipt.addProperty("elementId", elementId);
            receipt.addProperty("presentationId", shape.getID());
            if (containerPeId != null) {
                receipt.addProperty("containerPresentationId", containerPeId);
            }
            if (bounds != null) {
                receipt.addProperty("x", bounds.x);
                receipt.addProperty("y", bounds.y);
                receipt.addProperty("width", bounds.width);
                receipt.addProperty("height", bounds.height);
            } else {
                receipt.addProperty("x", x);
                receipt.addProperty("y", y);
                if (requestedWidth != null && requestedHeight != null) {
                    receipt.addProperty("width", requestedWidth);
                    receipt.addProperty("height", requestedHeight);
                }
            }
            receipt.addProperty("status", addResult.status);
            if (addResult.activityPartitionNative) {
                receipt.addProperty("activityPartitionNative", true);
            }
            response.add("receipt", receipt);
            return response;
        });

        HttpBridgeServer.sendJson(exchange, 200, result);
    }

    private DiagramAddResult addElementPresentation(
            DiagramPresentationElement dpe,
            Element element,
            PresentationElement shapeParent,
            PresentationElementsManager pem,
            Integer requestedX,
            Integer requestedY,
            Integer requestedWidth,
            Integer requestedHeight) throws Exception {
        int x = requestedX != null ? requestedX : 100;
        int y = requestedY != null ? requestedY : 100;

        if (element instanceof ActivityPartition) {
            if (shapeParent != dpe) {
                throw new IllegalStateException(
                        "ActivityPartition insertion through containerPresentationId is not supported; "
                                + "omit containerPresentationId and let the bridge create or resolve "
                                + "the swimlane container natively.");
            }
            return addActivityPartitionPresentation(
                    dpe,
                    (ActivityPartition) element,
                    pem,
                    requestedX,
                    requestedY,
                    requestedWidth,
                    requestedHeight);
        }

        ShapeElement shape = pem.createShapeElement(element, shapeParent, true, new Point(x, y));
        if (shape == null) {
            throw new IllegalStateException(
                    "Failed to create shape for element: " + element.getID());
        }
        if (requestedWidth != null && requestedHeight != null) {
            pem.reshapeShapeElement(shape, new Rectangle(x, y, requestedWidth, requestedHeight));
        }
        return new DiagramAddResult(shape, "created", false);
    }

    private DiagramAddResult addActivityPartitionPresentation(
            DiagramPresentationElement dpe,
            ActivityPartition partition,
            PresentationElementsManager pem,
            Integer requestedX,
            Integer requestedY,
            Integer requestedWidth,
            Integer requestedHeight) throws Exception {
        PresentationElement existingPartition = findActivityPartitionPresentation(
                dpe.getPresentationElements(),
                partition.getID());
        if (existingPartition != null) {
            return new DiagramAddResult(
                    requireShapeElement(
                            existingPartition,
                            "Existing activity partition presentation is not a shape"),
                    "existing",
                    true);
        }

        ShapeElement existingSwimlane = findFirstSwimlane(dpe.getPresentationElements());
        if (existingSwimlane != null) {
            throw new IllegalStateException(
                    "Activity partition add-to-diagram found an existing swimlane but could not "
                            + "locate a presentation for partition " + partition.getID()
                            + ". Refusing to rebuild the entire swimlane container automatically.");
        }

        List<ActivityPartition> siblingPartitions = collectSiblingPartitions(partition);
        int laneCount = Math.max(siblingPartitions.size(), 1);
        int laneWidth = requestedWidth != null ? requestedWidth : 220;
        int totalWidth = requestedWidth != null ? laneWidth * laneCount : laneWidth * laneCount;
        int totalHeight = requestedHeight != null ? requestedHeight : 280;
        int targetX = requestedX != null ? requestedX : 100;
        int targetY = requestedY != null ? requestedY : 100;

        @SuppressWarnings({"rawtypes", "unchecked"})
        ShapeElement swimlane = pem.createSwimlane(
                Collections.emptyList(),
                new ArrayList(siblingPartitions),
                dpe);
        if (swimlane == null) {
            throw new IllegalStateException(
                    "Failed to create swimlane for activity partition: " + partition.getID());
        }
        pem.reshapeShapeElement(swimlane, new Rectangle(targetX, targetY, totalWidth, totalHeight));

        PresentationElement createdPartition = findActivityPartitionPresentation(
                dpe.getPresentationElements(),
                partition.getID());
        if (createdPartition == null) {
            throw new IllegalStateException(
                    "Failed to locate the created swimlane presentation for activity partition: "
                            + partition.getID());
        }

        return new DiagramAddResult(
                requireShapeElement(
                        createdPartition,
                        "Created activity partition presentation is not a shape"),
                "created",
                true);
    }

    private List<ActivityPartition> collectSiblingPartitions(ActivityPartition partition) {
        Element owner = partition.getOwner();
        if (owner == null) {
            return Collections.singletonList(partition);
        }

        List<ActivityPartition> partitions = new ArrayList<>();
        for (Element owned : owner.getOwnedElement()) {
            if (owned instanceof ActivityPartition) {
                partitions.add((ActivityPartition) owned);
            }
        }
        if (partitions.isEmpty()) {
            partitions.add(partition);
        } else if (!partitions.contains(partition)) {
            partitions.add(partition);
        }
        return partitions;
    }

    private PresentationElement findActivityPartitionPresentation(
            List<PresentationElement> elements,
            String targetElementId) {
        if (elements == null || targetElementId == null) {
            return null;
        }

        PresentationElement fallback = null;
        for (PresentationElement pe : elements) {
            Element peElement = null;
            try {
                peElement = pe.getElement();
            } catch (Exception ignored) {
                // Some presentation elements do not expose a backing element.
            }

            if (peElement != null && targetElementId.equals(peElement.getID())) {
                String className = pe.getClass().getSimpleName();
                if ("SwimlaneHeaderView".equals(className)) {
                    return pe;
                }
                if (fallback == null
                        && (className.contains("Swimlane") || className.contains("Partition"))) {
                    fallback = pe;
                }
            }

            PresentationElement nested = findActivityPartitionPresentation(
                    pe.getPresentationElements(),
                    targetElementId);
            if (nested != null) {
                return nested;
            }
        }
        return fallback;
    }

    private ShapeElement findFirstSwimlane(List<PresentationElement> elements) {
        if (elements == null) {
            return null;
        }
        for (PresentationElement pe : elements) {
            if ("SwimlaneView".equals(pe.getClass().getSimpleName())) {
                return requireShapeElement(pe, "Swimlane presentation is not a shape");
            }
            ShapeElement nested = findFirstSwimlane(pe.getPresentationElements());
            if (nested != null) {
                return nested;
            }
        }
        return null;
    }

    private ShapeElement requireShapeElement(PresentationElement pe, String message) {
        if (pe instanceof ShapeElement) {
            return (ShapeElement) pe;
        }
        throw new IllegalStateException(message);
    }

    private void handleLayout(HttpExchange exchange, String diagramId) throws Exception {
        JsonObject result = EdtDispatcher.write("MCP Bridge: Auto-Layout Diagram", project -> {
            DiagramPresentationElement dpe = findDiagramById(project, diagramId);
            dpe.ensureLoaded();

            boolean success = dpe.layout(true);

            JsonObject response = new JsonObject();
            response.addProperty("diagramId", diagramId);
            response.addProperty("name", dpe.getName() != null ? dpe.getName() : "");
            response.addProperty("layoutApplied", success);
            return response;
        });

        HttpBridgeServer.sendJson(exchange, 200, result);
    }

    // ── Shape Management Endpoints ──────────────────────────────────────────

    private void handleListShapes(HttpExchange exchange, String diagramId) throws Exception {
        JsonObject result = EdtDispatcher.read(project -> {
            DiagramPresentationElement dpe = findDiagramById(project, diagramId);
            dpe.ensureLoaded();

            JsonArray shapesArray = new JsonArray();
            List<PresentationElement> presentationElements = dpe.getPresentationElements();
            collectShapes(presentationElements, shapesArray, null);

            JsonObject response = new JsonObject();
            response.addProperty("diagramId", diagramId);
            response.addProperty("count", shapesArray.size());
            response.addProperty("shapeCount", shapesArray.size());
            response.add("shapes", shapesArray);
            return response;
        });

        HttpBridgeServer.sendJson(exchange, 200, result);
    }

    private void handleGetShapeProperties(HttpExchange exchange, String diagramId, String peId)
            throws Exception {
        JsonObject result = EdtDispatcher.read(project -> {
            DiagramPresentationElement dpe = findDiagramById(project, diagramId);
            dpe.ensureLoaded();

            PresentationElement target = findPresentationElement(dpe.getPresentationElements(), peId);
            if (target == null) {
                throw new IllegalArgumentException("Presentation element not found: " + peId);
            }

            PropertyManager pm = target.getPropertyManager();
            JsonArray propertiesArray = new JsonArray();
            JsonObject propertiesObject = new JsonObject();
            JsonObject compartments = new JsonObject();

            @SuppressWarnings("unchecked")
            List<Property> properties = pm.getProperties();
            for (Property property : properties) {
                JsonObject entry = new JsonObject();
                entry.addProperty("name", property.getName());
                if (property.getID() != null) {
                    entry.addProperty("id", property.getID());
                }
                if (property.getClassType() != null) {
                    entry.addProperty("classType", property.getClassType());
                }
                addJsonValue(entry, "value", property.getValue());
                propertiesArray.add(entry);
                addJsonValue(propertiesObject, property.getName(), property.getValue());

                String compartmentKey = canonicalCompartmentKey(property.getName());
                if (compartmentKey != null) {
                    addJsonValue(compartments, compartmentKey, property.getValue());
                }
            }

            JsonObject response = new JsonObject();
            response.addProperty("diagramId", diagramId);
            response.addProperty("presentationId", peId);
            response.add("properties", propertiesObject);
            response.add("propertyList", propertiesArray);
            response.add("compartments", compartments);
            response.addProperty("resultCount", propertiesArray.size());
            return response;
        });

        HttpBridgeServer.sendJson(exchange, 200, result);
    }

    /**
     * Recursively collect presentation elements into a flat array,
     * tagging each with its parentPresentationId for hierarchy context.
     */
    private void collectShapes(List<PresentationElement> elements, JsonArray shapesArray,
            String parentPeId) {
        if (elements == null) return;
        for (PresentationElement pe : elements) {
            try {
                JsonObject shapeJson = new JsonObject();
                shapeJson.addProperty("presentationId", pe.getID());
                shapeJson.addProperty("shapeType", pe.getClass().getSimpleName());

                if (parentPeId != null) {
                    shapeJson.addProperty("parentPresentationId", parentPeId);
                }

                Element modelElement = pe.getElement();
                if (modelElement != null) {
                    shapeJson.addProperty("elementId", modelElement.getID());
                    if (modelElement instanceof NamedElement) {
                        shapeJson.addProperty("elementName",
                                ((NamedElement) modelElement).getName());
                    }
                    shapeJson.addProperty("elementType",
                            modelElement.getHumanType());
                }

                try {
                    Rectangle bounds = pe.getBounds();
                    if (bounds != null) {
                        JsonObject boundsJson = new JsonObject();
                        boundsJson.addProperty("x", bounds.x);
                        boundsJson.addProperty("y", bounds.y);
                        boundsJson.addProperty("width", bounds.width);
                        boundsJson.addProperty("height", bounds.height);
                        shapeJson.add("bounds", boundsJson);
                    }
                } catch (Exception e) {
                    // Some presentation elements do not have rectangular bounds
                }

                // Count children for context
                List<PresentationElement> children = pe.getPresentationElements();
                int childCount = (children != null) ? children.size() : 0;
                if (childCount > 0) {
                    shapeJson.addProperty("childCount", childCount);
                }

                shapesArray.add(shapeJson);

                // Recurse into children
                if (childCount > 0) {
                    collectShapes(children, shapesArray, pe.getID());
                }
            } catch (Exception e) {
                LOG.log(Level.FINE, "Error reading presentation element", e);
            }
        }
    }

    private void handleMoveResizeShapes(HttpExchange exchange, String diagramId) throws Exception {
        JsonObject body = JsonHelper.parseBody(exchange);

        if (!body.has("shapes") || !body.get("shapes").isJsonArray()) {
            HttpBridgeServer.sendError(exchange, 400, "MISSING_PARAM",
                    "Request body must include a 'shapes' array");
            return;
        }

        JsonArray shapesInput = body.getAsJsonArray("shapes");

        JsonObject result = EdtDispatcher.write("MCP Bridge: Move/Resize Shapes", project -> {
            DiagramPresentationElement dpe = findDiagramById(project, diagramId);
            dpe.ensureLoaded();

            List<PresentationElement> allPEs = dpe.getPresentationElements();
            PresentationElementsManager pem = PresentationElementsManager.getInstance();
            JsonArray results = new JsonArray();

            for (JsonElement item : shapesInput) {
                JsonObject shapeReq = item.getAsJsonObject();
                if (!shapeReq.has("presentationId")
                        || !shapeReq.has("x")
                        || !shapeReq.has("y")
                        || !shapeReq.has("width")
                        || !shapeReq.has("height")) {
                    JsonObject err = new JsonObject();
                    err.addProperty("presentationId",
                            JsonHelper.optionalString(shapeReq, "presentationId"));
                    err.addProperty("error",
                            "Request item must include presentationId, x, y, width, and height");
                    results.add(err);
                    continue;
                }

                String presentationId = shapeReq.get("presentationId").getAsString();
                int x = shapeReq.get("x").getAsInt();
                int y = shapeReq.get("y").getAsInt();
                int width = shapeReq.get("width").getAsInt();
                int height = shapeReq.get("height").getAsInt();

                PresentationElement target = findPresentationElement(allPEs, presentationId);
                if (target == null) {
                    JsonObject err = new JsonObject();
                    err.addProperty("presentationId", presentationId);
                    err.addProperty("error", "Presentation element not found");
                    results.add(err);
                    continue;
                }

                if (!(target instanceof ShapeElement)) {
                    JsonObject err = new JsonObject();
                    err.addProperty("presentationId", presentationId);
                    err.addProperty("error", "Element is not a shape (cannot reshape paths)");
                    results.add(err);
                    continue;
                }

                pem.reshapeShapeElement((ShapeElement) target,
                        new Rectangle(x, y, width, height));

                JsonObject ok = new JsonObject();
                ok.addProperty("presentationId", presentationId);
                ok.addProperty("reshaped", true);
                JsonObject receipt = new JsonObject();
                receipt.addProperty("operation", "reshapeShape");
                receipt.addProperty("diagramId", diagramId);
                receipt.addProperty("presentationId", presentationId);
                receipt.addProperty("x", x);
                receipt.addProperty("y", y);
                receipt.addProperty("width", width);
                receipt.addProperty("height", height);
                receipt.addProperty("status", "applied");
                ok.add("receipt", receipt);
                results.add(ok);
            }

            JsonObject response = new JsonObject();
            response.addProperty("diagramId", diagramId);
            response.addProperty("resultCount", results.size());
            response.add("results", results);
            return response;
        });

        HttpBridgeServer.sendJson(exchange, 200, result);
    }

    private void handleDeleteShapes(HttpExchange exchange, String diagramId) throws Exception {
        JsonObject body = JsonHelper.parseBody(exchange);

        if (!body.has("presentationIds") || !body.get("presentationIds").isJsonArray()) {
            HttpBridgeServer.sendError(exchange, 400, "MISSING_PARAM",
                    "Request body must include a 'presentationIds' array");
            return;
        }

        JsonArray idsInput = body.getAsJsonArray("presentationIds");

        JsonObject result = EdtDispatcher.write("MCP Bridge: Delete Presentation Elements", project -> {
            DiagramPresentationElement dpe = findDiagramById(project, diagramId);
            dpe.ensureLoaded();

            List<PresentationElement> allPEs = dpe.getPresentationElements();
            PresentationElementsManager pem = PresentationElementsManager.getInstance();
            JsonArray results = new JsonArray();

            for (JsonElement item : idsInput) {
                String peId = item.getAsString();
                PresentationElement target = findPresentationElement(allPEs, peId);

                JsonObject entry = new JsonObject();
                entry.addProperty("presentationId", peId);

                if (target == null) {
                    entry.addProperty("error", "Presentation element not found");
                } else {
                    pem.deletePresentationElement(target);
                    entry.addProperty("deleted", true);
                }
                results.add(entry);
            }

            JsonObject response = new JsonObject();
            response.addProperty("diagramId", diagramId);
            response.addProperty("resultCount", results.size());
            response.add("results", results);
            return response;
        });

        HttpBridgeServer.sendJson(exchange, 200, result);
    }

    private void handleReparentShapes(HttpExchange exchange, String diagramId) throws Exception {
        JsonObject body = JsonHelper.parseBody(exchange);
        if (!body.has("reparentings") || !body.get("reparentings").isJsonArray()) {
            HttpBridgeServer.sendError(exchange, 400, "MISSING_PARAM",
                    "Request body must include a 'reparentings' array");
            return;
        }

        JsonArray reparentings = body.getAsJsonArray("reparentings");
        JsonObject result = EdtDispatcher.write("MCP Bridge: Reparent Shapes", project -> {
            DiagramPresentationElement dpe = findDiagramById(project, diagramId);
            dpe.ensureLoaded();

            List<PresentationElement> allPEs = dpe.getPresentationElements();
            JsonArray results = new JsonArray();
            Method setParentMethod = PresentationElement.class.getMethod(
                    "setParent", PresentationElement.class);

            for (JsonElement item : reparentings) {
                JsonObject req = item.getAsJsonObject();
                String presentationId = JsonHelper.optionalString(req, "presentationId");
                String parentPresentationId = JsonHelper.optionalString(req, "parentPresentationId");

                JsonObject entry = new JsonObject();
                entry.addProperty("presentationId", presentationId);
                entry.addProperty("parentPresentationId", parentPresentationId);

                if (presentationId == null || parentPresentationId == null) {
                    entry.addProperty("error",
                            "Each reparenting must include presentationId and parentPresentationId");
                    results.add(entry);
                    continue;
                }

                PresentationElement child = findPresentationElement(allPEs, presentationId);
                PresentationElement parent = findPresentationElement(allPEs, parentPresentationId);
                if (child == null) {
                    entry.addProperty("error", "Presentation element not found: " + presentationId);
                    results.add(entry);
                    continue;
                }
                if (parent == null) {
                    entry.addProperty("error",
                            "Parent presentation element not found: " + parentPresentationId);
                    results.add(entry);
                    continue;
                }

                setParentMethod.invoke(child, parent);
                entry.addProperty("reparented", true);
                JsonObject receipt = new JsonObject();
                receipt.addProperty("operation", "reparentShape");
                receipt.addProperty("diagramId", diagramId);
                receipt.addProperty("presentationId", presentationId);
                receipt.addProperty("parentPresentationId", parentPresentationId);
                receipt.addProperty("status", "applied");
                entry.add("receipt", receipt);
                results.add(entry);
            }

            JsonObject response = new JsonObject();
            response.addProperty("diagramId", diagramId);
            response.addProperty("resultCount", results.size());
            response.add("results", results);
            return response;
        });

        HttpBridgeServer.sendJson(exchange, 200, result);
    }

    private void handleAddPaths(HttpExchange exchange, String diagramId) throws Exception {
        JsonObject body = JsonHelper.parseBody(exchange);

        if (!body.has("paths") || !body.get("paths").isJsonArray()) {
            HttpBridgeServer.sendError(exchange, 400, "MISSING_PARAM",
                    "Request body must include a 'paths' array");
            return;
        }

        JsonArray pathsInput = body.getAsJsonArray("paths");

        JsonObject result = EdtDispatcher.write("MCP Bridge: Add Relationship Paths", project -> {
            DiagramPresentationElement dpe = findDiagramById(project, diagramId);
            dpe.ensureLoaded();

            List<PresentationElement> allPEs = dpe.getPresentationElements();
            PresentationElementsManager pem = PresentationElementsManager.getInstance();
            JsonArray results = new JsonArray();

            for (JsonElement item : pathsInput) {
                JsonObject pathReq = item.getAsJsonObject();
                if (!pathReq.has("relationshipId")
                        || !pathReq.has("sourceShapeId")
                        || !pathReq.has("targetShapeId")) {
                    JsonObject err = new JsonObject();
                    err.addProperty("error",
                            "Request item must include relationshipId, sourceShapeId, and targetShapeId");
                    results.add(err);
                    continue;
                }

                String relationshipId = pathReq.get("relationshipId").getAsString();
                String sourceShapeId = pathReq.get("sourceShapeId").getAsString();
                String targetShapeId = pathReq.get("targetShapeId").getAsString();

                JsonObject entry = new JsonObject();
                entry.addProperty("relationshipId", relationshipId);

                Element relationship = (Element) project.getElementByID(relationshipId);
                if (relationship == null) {
                    entry.addProperty("error",
                            "Relationship model element not found: " + relationshipId);
                    results.add(entry);
                    continue;
                }

                PresentationElement sourcePE = findPresentationElement(allPEs, sourceShapeId);
                if (sourcePE == null) {
                    entry.addProperty("error",
                            "Source presentation element not found: " + sourceShapeId);
                    results.add(entry);
                    continue;
                }

                PresentationElement targetPE = findPresentationElement(allPEs, targetShapeId);
                if (targetPE == null) {
                    entry.addProperty("error",
                            "Target presentation element not found: " + targetShapeId);
                    results.add(entry);
                    continue;
                }

                PathElement pathElement = pem.createPathElement(relationship, sourcePE, targetPE);
                if (pathElement != null) {
                    entry.addProperty("presentationId", pathElement.getID());
                    entry.addProperty("created", true);
                } else {
                    entry.addProperty("error", "Failed to create path element");
                }
                results.add(entry);
            }

            JsonObject response = new JsonObject();
            response.addProperty("diagramId", diagramId);
            response.addProperty("resultCount", results.size());
            response.add("results", results);
            return response;
        });

        HttpBridgeServer.sendJson(exchange, 200, result);
    }

    private void handleSetShapeProperties(HttpExchange exchange, String diagramId, String peId)
            throws Exception {
        JsonObject body = JsonHelper.parseBody(exchange);

        if (!body.has("properties") || !body.get("properties").isJsonObject()) {
            HttpBridgeServer.sendError(exchange, 400, "MISSING_PARAM",
                    "Request body must include a 'properties' object");
            return;
        }

        JsonObject propsInput = body.getAsJsonObject("properties");

        JsonObject result = EdtDispatcher.write("MCP Bridge: Set Shape Properties", project -> {
            DiagramPresentationElement dpe = findDiagramById(project, diagramId);
            dpe.ensureLoaded();

            List<PresentationElement> allPEs = dpe.getPresentationElements();
            PresentationElement target = findPresentationElement(allPEs, peId);
            if (target == null) {
                throw new IllegalArgumentException(
                        "Presentation element not found: " + peId);
            }

            // MUST clone the PropertyManager -- Cameo rejects reuse of the old one
            PropertyManager pm = target.getPropertyManager().clone();
            @SuppressWarnings("unchecked")
            List<Property> properties = pm.getProperties();
            JsonArray updated = new JsonArray();

            for (var propEntry : propsInput.entrySet()) {
                String propName = propEntry.getKey();
                boolean found = false;
                for (Property p : properties) {
                    if (propName.equals(p.getName())) {
                        JsonElement val = propEntry.getValue();
                        if (val.isJsonPrimitive()) {
                            if (val.getAsJsonPrimitive().isBoolean()) {
                                p.setValue(val.getAsBoolean());
                            } else if (val.getAsJsonPrimitive().isNumber()) {
                                p.setValue(val.getAsInt());
                            } else {
                                p.setValue(val.getAsString());
                            }
                        } else if (val.isJsonNull()) {
                            p.setValue("");
                        } else {
                            // JSON objects/arrays: convert to string representation
                            p.setValue(val.toString());
                        }
                        JsonObject u = new JsonObject();
                        u.addProperty("name", propName);
                        u.addProperty("set", true);
                        updated.add(u);
                        found = true;
                        break;
                    }
                }
                if (!found) {
                    JsonObject u = new JsonObject();
                    u.addProperty("name", propName);
                    u.addProperty("error", "Property not found on this shape");
                    updated.add(u);
                }
            }

            PresentationElementsManager pem = PresentationElementsManager.getInstance();
            applyPresentationPropertiesOrThrow(
                    pem,
                    target,
                    pm,
                    "Failed to apply shape properties to presentation " + peId);

            JsonObject response = new JsonObject();
            response.addProperty("diagramId", diagramId);
            response.addProperty("presentationId", peId);
            response.add("properties", updated);
            response.addProperty("resultCount", updated.size());
            JsonObject receipt = new JsonObject();
            receipt.addProperty("operation", "setShapeProperties");
            receipt.addProperty("diagramId", diagramId);
            receipt.addProperty("presentationId", peId);
            receipt.addProperty("status", "applied");
            response.add("receipt", receipt);
            return response;
        });

        HttpBridgeServer.sendJson(exchange, 200, result);
    }

    private void handleSetShapeCompartments(HttpExchange exchange, String diagramId, String peId)
            throws Exception {
        JsonObject body = JsonHelper.parseBody(exchange);
        if (!body.has("compartments") || !body.get("compartments").isJsonObject()) {
            HttpBridgeServer.sendError(exchange, 400, "MISSING_PARAM",
                    "Request body must include a 'compartments' object");
            return;
        }

        JsonObject compartmentsInput = body.getAsJsonObject("compartments");
        JsonObject result = EdtDispatcher.write("MCP Bridge: Set Shape Compartments", project -> {
            DiagramPresentationElement dpe = findDiagramById(project, diagramId);
            dpe.ensureLoaded();

            PresentationElement target = findPresentationElement(dpe.getPresentationElements(), peId);
            if (target == null) {
                throw new IllegalArgumentException("Presentation element not found: " + peId);
            }

            PropertyManager pm = target.getPropertyManager().clone();
            @SuppressWarnings("unchecked")
            List<Property> properties = pm.getProperties();
            Map<String, Property> propertyByName = new LinkedHashMap<>();
            for (Property property : properties) {
                propertyByName.put(property.getName(), property);
            }

            JsonArray updated = new JsonArray();
            for (var compartmentEntry : compartmentsInput.entrySet()) {
                String requestedKey = compartmentEntry.getKey();
                JsonElement requestedValue = compartmentEntry.getValue();
                Property property = resolveCompartmentProperty(propertyByName, requestedKey);

                JsonObject entry = new JsonObject();
                entry.addProperty("compartment", requestedKey);
                if (property == null) {
                    entry.addProperty("error", "No matching compartment property found on this shape");
                    updated.add(entry);
                    continue;
                }

                applyCompartmentValue(property, requestedValue, requestedKey);
                entry.addProperty("property", property.getName());
                addJsonValue(entry, "value", property.getValue());
                entry.addProperty("set", true);
                updated.add(entry);
            }

            applyPresentationPropertiesOrThrow(
                    PresentationElementsManager.getInstance(),
                    target,
                    pm,
                    "Failed to apply shape compartments to presentation " + peId);

            JsonObject response = new JsonObject();
            response.addProperty("diagramId", diagramId);
            response.addProperty("presentationId", peId);
            response.add("results", updated);
            response.addProperty("resultCount", updated.size());
            JsonObject receipt = new JsonObject();
            receipt.addProperty("operation", "setShapeCompartments");
            receipt.addProperty("diagramId", diagramId);
            receipt.addProperty("presentationId", peId);
            receipt.addProperty("status", "applied");
            response.add("receipt", receipt);
            return response;
        });

        HttpBridgeServer.sendJson(exchange, 200, result);
    }

    private void handleConfigureTransitionLabelPresentation(
            HttpExchange exchange,
            String diagramId) throws Exception {
        JsonObject body = JsonHelper.parseBody(exchange);
        List<String> presentationIds = JsonHelper.optionalStringList(body, "presentationIds");
        boolean showName = readBoolean(body, "showName", true);
        boolean showTriggers = readBoolean(body, "showTriggers", true);
        boolean showGuard = readBoolean(body, "showGuard", false);
        boolean showEffect = readBoolean(body, "showEffect", false);
        boolean resetLabels = readBoolean(body, "resetLabels", true);

        JsonObject result = EdtDispatcher.write("MCP Bridge: Configure Transition Label Presentation", project -> {
            DiagramPresentationElement dpe = findDiagramById(project, diagramId);
            dpe.ensureLoaded();

            PresentationSelection selection = selectPresentationElementsWithErrors(
                    dpe.getPresentationElements(),
                    presentationIds,
                    this::isTransitionPathPresentation,
                    "Presentation element is not a transition path");

            PresentationElementsManager pem = PresentationElementsManager.getInstance();
            JsonArray results = new JsonArray();
            appendResults(results, selection.errors);
            Map<String, PropertySelection> selections = new LinkedHashMap<>();
            selections.put("showName", new PropertySelection(showName, List.of("Show Name"), List.of("showname")));
            selections.put("showTriggers", new PropertySelection(showTriggers, List.of(), List.of("showtrigger", "showtriggers")));
            selections.put("showGuard", new PropertySelection(showGuard, List.of(), List.of("showguard")));
            selections.put("showEffect", new PropertySelection(showEffect, List.of(), List.of("showeffect")));
            for (PresentationElement target : selection.targets) {
                results.add(configurePresentationProperties(target, pem, selections, resetLabels));
            }

            JsonObject response = new JsonObject();
            response.addProperty("diagramId", diagramId);
            response.addProperty("resultCount", results.size());
            response.add("results", results);
            JsonObject receipt = new JsonObject();
            receipt.addProperty("operation", "configureTransitionLabelPresentation");
            receipt.addProperty("diagramId", diagramId);
            receipt.addProperty("status", "applied");
            response.add("receipt", receipt);
            return response;
        });

        HttpBridgeServer.sendJson(exchange, 200, result);
    }

    private void handleConfigureItemFlowLabelPresentation(
            HttpExchange exchange,
            String diagramId) throws Exception {
        JsonObject body = JsonHelper.parseBody(exchange);
        List<String> presentationIds = JsonHelper.optionalStringList(body, "presentationIds");
        boolean showName = readBoolean(body, "showName", false);
        boolean showConveyed = readBoolean(body, "showConveyed", true);
        boolean showItemProperty = readBoolean(body, "showItemProperty", true);
        boolean showDirection = readBoolean(body, "showDirection", true);
        boolean showStereotype = readBoolean(body, "showStereotype", false);
        boolean resetLabels = readBoolean(body, "resetLabels", true);

        JsonObject result = EdtDispatcher.write("MCP Bridge: Configure Item Flow Label Presentation", project -> {
            DiagramPresentationElement dpe = findDiagramById(project, diagramId);
            dpe.ensureLoaded();

            PresentationSelection selection = selectPresentationElementsWithErrors(
                    dpe.getPresentationElements(),
                    presentationIds,
                    this::isItemFlowPathPresentation,
                    "Presentation element is not an information-flow path");

            PresentationElementsManager pem = PresentationElementsManager.getInstance();
            JsonArray results = new JsonArray();
            appendResults(results, selection.errors);
            Map<String, PropertySelection> selections = new LinkedHashMap<>();
            selections.put("showName", new PropertySelection(showName, List.of("Show Name"), List.of("showname")));
            selections.put("showConveyed", new PropertySelection(showConveyed, List.of(), List.of("conveyed", "informationflow")));
            selections.put("showItemProperty", new PropertySelection(showItemProperty, List.of(), List.of("itemproperty")));
            selections.put("showDirection", new PropertySelection(showDirection, List.of(), List.of("showdirection", "direction")));
            selections.put("showStereotype", new PropertySelection(showStereotype, List.of("Show Stereotype"), List.of("showstereotype")));
            for (PresentationElement target : selection.targets) {
                results.add(configurePresentationProperties(target, pem, selections, resetLabels));
            }

            JsonObject response = new JsonObject();
            response.addProperty("diagramId", diagramId);
            response.addProperty("resultCount", results.size());
            response.add("results", results);
            JsonObject receipt = new JsonObject();
            receipt.addProperty("operation", "configureItemFlowLabelPresentation");
            receipt.addProperty("diagramId", diagramId);
            receipt.addProperty("status", "applied");
            response.add("receipt", receipt);
            return response;
        });

        HttpBridgeServer.sendJson(exchange, 200, result);
    }

    private void handleConfigureAllocationCompartmentPresentation(
            HttpExchange exchange,
            String diagramId) throws Exception {
        JsonObject body = JsonHelper.parseBody(exchange);
        List<String> presentationIds = JsonHelper.optionalStringList(body, "presentationIds");
        boolean showAllocatedElements = readBoolean(body, "showAllocatedElements", true);
        boolean showElementProperties = readBoolean(body, "showElementProperties", true);
        boolean showPorts = readBoolean(body, "showPorts", true);
        boolean showFullPorts = readBoolean(body, "showFullPorts", true);
        boolean applyAllocationNaming = readBoolean(body, "applyAllocationNaming", true);

        JsonObject result = EdtDispatcher.write("MCP Bridge: Configure Allocation Compartments", project -> {
            DiagramPresentationElement dpe = findDiagramById(project, diagramId);
            dpe.ensureLoaded();

            PresentationSelection selection = selectPresentationElementsWithErrors(
                    dpe.getPresentationElements(),
                    presentationIds,
                    this::isAllocationCompartmentCandidate,
                    "Presentation element does not support allocation compartments");

            PresentationElementsManager pem = PresentationElementsManager.getInstance();
            JsonArray results = new JsonArray();
            appendResults(results, selection.errors);
            Map<String, PropertySelection> selections = new LinkedHashMap<>();
            selections.put("showAllocatedElements", new PropertySelection(
                    showAllocatedElements,
                    List.of(),
                    List.of("allocatedelements", "allocatedfrom")));
            selections.put("showElementProperties", new PropertySelection(
                    showElementProperties,
                    List.of("Show Element Properties"),
                    List.of("showelementproperties")));
            selections.put("showPorts", new PropertySelection(
                    showPorts,
                    List.of("Show Ports"),
                    List.of("showports")));
            selections.put("showFullPorts", new PropertySelection(
                    showFullPorts,
                    List.of("Show Full Ports", "Suppress Full Ports"),
                    List.of("showfullports", "suppressfullports")));
            selections.put("applyAllocationNaming", new PropertySelection(
                    applyAllocationNaming,
                    List.of("Apply SysML 1.7 Allocation Compartment Naming"),
                    List.of("allocationcompartmentnaming")));
            for (PresentationElement target : selection.targets) {
                results.add(configurePresentationProperties(target, pem, selections, false));
            }

            JsonObject response = new JsonObject();
            response.addProperty("diagramId", diagramId);
            response.addProperty("resultCount", results.size());
            response.add("results", results);
            JsonObject receipt = new JsonObject();
            receipt.addProperty("operation", "configureAllocationCompartmentPresentation");
            receipt.addProperty("diagramId", diagramId);
            receipt.addProperty("status", "applied");
            response.add("receipt", receipt);
            return response;
        });

        HttpBridgeServer.sendJson(exchange, 200, result);
    }

    private void handlePrunePathDecorations(
            HttpExchange exchange,
            String diagramId) throws Exception {
        JsonObject body = JsonHelper.parseBody(exchange);
        List<String> presentationIds = JsonHelper.optionalStringList(body, "presentationIds");
        List<String> dropChildShapeTypes = JsonHelper.optionalStringList(body, "dropChildShapeTypes");
        boolean dryRun = readBoolean(body, "dryRun", false);

        List<String> effectiveDropShapeTypes = (dropChildShapeTypes == null || dropChildShapeTypes.isEmpty())
                ? List.of("RoleView")
                : new ArrayList<>(dropChildShapeTypes);

        JsonObject result = EdtDispatcher.write("MCP Bridge: Prune Path Decorations", project -> {
            DiagramPresentationElement dpe = findDiagramById(project, diagramId);
            dpe.ensureLoaded();

            String diagramType = diagramTypeName(dpe);
            PresentationSelection selection = selectPresentationElementsWithErrors(
                    dpe.getPresentationElements(),
                    presentationIds,
                    pe -> pe instanceof PathElement,
                    "Presentation element is not a path");

            PresentationElementsManager pem = PresentationElementsManager.getInstance();
            JsonArray results = new JsonArray();
            appendResults(results, selection.errors);
            int deletedDecorationCount = 0;

            for (PresentationElement target : selection.targets) {
                JsonObject entry = describePresentationElement(target, null);
                entry.addProperty("repairMode", "path-decorations");
                JsonArray requestedTypes = new JsonArray();
                for (String shapeType : effectiveDropShapeTypes) {
                    requestedTypes.add(shapeType);
                }
                entry.add("dropChildShapeTypes", requestedTypes);

                List<PresentationElement> descendants = new ArrayList<>();
                Map<String, String> parentById = new LinkedHashMap<>();
                collectPresentationElements(target.getPresentationElements(), descendants, parentById, target.getID());

                LinkedHashSet<String> matchedIds = new LinkedHashSet<>();
                for (PresentationElement descendant : descendants) {
                    if (matchesAnyShapeTypeToken(descendant, effectiveDropShapeTypes)) {
                        matchedIds.add(descendant.getID());
                    }
                }

                JsonArray decorations = new JsonArray();
                int deletedForTarget = 0;
                int errorsForTarget = 0;
                for (PresentationElement descendant : descendants) {
                    String presentationId = descendant.getID();
                    if (!matchedIds.contains(presentationId)) {
                        continue;
                    }

                    String parentId = parentById.get(presentationId);
                    if (parentId != null && matchedIds.contains(parentId)) {
                        continue;
                    }

                    List<PresentationElement> deletionOrder = new ArrayList<>();
                    List<PresentationElement> subtree = new ArrayList<>();
                    Map<String, String> subtreeParents = new LinkedHashMap<>();
                    collectPresentationElements(
                            descendant.getPresentationElements(),
                            subtree,
                            subtreeParents,
                            descendant.getID());
                    Collections.reverse(subtree);
                    deletionOrder.addAll(subtree);
                    deletionOrder.add(descendant);

                    LinkedHashSet<String> seenDeletionIds = new LinkedHashSet<>();
                    for (PresentationElement candidate : deletionOrder) {
                        if (!seenDeletionIds.add(candidate.getID())) {
                            continue;
                        }
                        String candidateParentId = candidate == descendant
                                ? parentId
                                : subtreeParents.get(candidate.getID());
                        JsonObject decoration = describePresentationElement(candidate, candidateParentId);
                        try {
                            if (dryRun) {
                                decoration.addProperty("status", "preview");
                                decoration.addProperty("applied", false);
                                decoration.addProperty("deleted", false);
                            } else {
                                pem.deletePresentationElement(candidate);
                                decoration.addProperty("status", "deleted");
                                decoration.addProperty("applied", true);
                                decoration.addProperty("deleted", true);
                                deletedForTarget++;
                                deletedDecorationCount++;
                            }
                        } catch (Exception e) {
                            decoration.addProperty("status", "error");
                            decoration.addProperty("applied", false);
                            decoration.addProperty("deleted", false);
                            decoration.addProperty("error", safeMessage(e));
                            errorsForTarget++;
                        }
                        decorations.add(decoration);
                    }
                }

                boolean updated = dryRun ? decorations.size() > 0 : deletedForTarget > 0;
                String status;
                if (decorations.size() == 0) {
                    status = "noop";
                } else if (dryRun) {
                    status = "preview";
                } else if (errorsForTarget > 0 && deletedForTarget > 0) {
                    status = "partial";
                } else if (errorsForTarget > 0) {
                    status = "error";
                } else {
                    status = "applied";
                }

                entry.addProperty("matchedDecorationCount", matchedIds.size());
                entry.addProperty("targetDecorationCount", decorations.size());
                entry.addProperty("deletedCount", deletedForTarget);
                entry.addProperty("updated", updated);
                entry.addProperty("applied", !dryRun && updated);
                entry.addProperty("status", status);
                if (errorsForTarget > 0) {
                    entry.addProperty("error", errorsForTarget + " path decoration(s) failed to prune");
                }
                entry.add("decorations", decorations);
                entry.add("receipt", buildRepairReceipt(
                        "prunePathDecorations",
                        diagramId,
                        diagramType,
                        target.getID(),
                        !dryRun && updated,
                        false,
                        entry));
                results.add(entry);
            }

            JsonObject response = new JsonObject();
            response.addProperty("diagramId", diagramId);
            response.addProperty("diagramType", diagramType);
            response.addProperty("dryRun", dryRun);
            JsonArray dropTypes = new JsonArray();
            for (String shapeType : effectiveDropShapeTypes) {
                dropTypes.add(shapeType);
            }
            response.add("dropChildShapeTypes", dropTypes);
            response.addProperty("resultCount", results.size());
            response.addProperty("updatedCount", countUpdatedTargets(results));
            response.addProperty("deletedDecorationCount", deletedDecorationCount);
            response.add("results", results);
            response.add("receipt", buildBatchRepairReceipt(
                    "prunePathDecorations",
                    diagramId,
                    diagramType,
                    dryRun,
                    selection.totalRequestedCount(),
                    countUpdatedTargets(results),
                    results.size(),
                    countErrorTargets(results)));
            return response;
        });

        HttpBridgeServer.sendJson(exchange, 200, result);
    }

    private void handleRepairHiddenLabels(HttpExchange exchange, String diagramId) throws Exception {
        JsonObject body = JsonHelper.parseBody(exchange);
        List<String> presentationIds = JsonHelper.optionalStringList(body, "presentationIds");
        boolean dryRun = readBoolean(body, "dryRun", false);

        JsonObject result = EdtDispatcher.write("MCP Bridge: Repair Hidden Labels", project -> {
            DiagramPresentationElement dpe = findDiagramById(project, diagramId);
            dpe.ensureLoaded();

            String diagramType = diagramTypeName(dpe);
            RepairDefaults defaults = repairDefaultsForDiagramType(diagramType);
            Map<String, PropertySelection> selections = buildSelectionMap(
                    true,
                    defaults.hiddenLabelKeys);

            PresentationSelection selection = selectPresentationElementsWithErrors(
                    dpe.getPresentationElements(),
                    presentationIds,
                    target -> targetSupportsAnySelection(target, selections),
                    "Presentation element does not support hidden-label repair");

            PresentationElementsManager pem = PresentationElementsManager.getInstance();
            JsonArray results = new JsonArray();
            appendResults(results, selection.errors);
            for (PresentationElement target : selection.targets) {
                JsonObject entry = configurePresentationProperties(
                        target, pem, selections, false, !dryRun);
                entry.addProperty("repairMode", "hidden-labels");
                entry.add("receipt", buildRepairReceipt(
                        "repairHiddenLabels",
                        diagramId,
                        diagramType,
                        target.getID(),
                        !dryRun,
                        false,
                        entry));
                results.add(entry);
            }

            JsonObject response = new JsonObject();
            response.addProperty("diagramId", diagramId);
            response.addProperty("diagramType", diagramType);
            response.addProperty("repairMode", "hidden-labels");
            response.addProperty("dryRun", dryRun);
            response.addProperty("resultCount", results.size());
            response.addProperty("updatedCount", countUpdatedTargets(results));
            response.add("results", results);
            response.add("receipt", buildBatchRepairReceipt(
                    "repairHiddenLabels",
                    diagramId,
                    diagramType,
                    dryRun,
                    selection.totalRequestedCount(),
                    countUpdatedTargets(results),
                    results.size(),
                    countErrorTargets(results)));
            return response;
        });

        HttpBridgeServer.sendJson(exchange, 200, result);
    }

    private void handleRepairLabelPositions(HttpExchange exchange, String diagramId) throws Exception {
        JsonObject body = JsonHelper.parseBody(exchange);
        List<String> presentationIds = JsonHelper.optionalStringList(body, "presentationIds");
        boolean dryRun = readBoolean(body, "dryRun", false);
        boolean onlyOverlapping = readBoolean(body, "onlyOverlapping", true);
        int overlapPadding = body.has("overlapPadding")
                ? Math.max(0, body.get("overlapPadding").getAsInt())
                : 40;

        JsonObject result = EdtDispatcher.write("MCP Bridge: Repair Label Positions", project -> {
            DiagramPresentationElement dpe = findDiagramById(project, diagramId);
            dpe.ensureLoaded();

            String diagramType = diagramTypeName(dpe);
            PresentationSelection selection = selectPresentationElementsWithErrors(
                    dpe.getPresentationElements(),
                    presentationIds,
                    pe -> pe instanceof PathElement,
                    "Presentation element is not a path");
            List<PresentationElement> targets = selection.targets;
            if (onlyOverlapping) {
                targets = selectOverlappingPathTargets(targets, overlapPadding);
            }

            PresentationElementsManager pem = PresentationElementsManager.getInstance();
            JsonArray results = new JsonArray();
            appendResults(results, selection.errors);
            for (PresentationElement target : targets) {
                JsonObject entry = new JsonObject();
                entry.addProperty("presentationId", target.getID());
                entry.addProperty("elementType", target.getElement() != null
                        ? target.getElement().getHumanType() : "");
                entry.addProperty("overlapCandidate", true);
                entry.addProperty("requestedResetLabels", true);
                entry.addProperty("repairMode", "label-positions");
                if (dryRun) {
                    entry.addProperty("applied", false);
                    entry.addProperty("updated", true);
                    entry.addProperty("status", "preview");
                    entry.addProperty("resetLabels", false);
                    entry.addProperty("labelsReset", false);
                } else {
                    try {
                        pem.resetLabelPositions((PathElement) target);
                        entry.addProperty("applied", true);
                        entry.addProperty("updated", true);
                        entry.addProperty("status", "applied");
                        entry.addProperty("resetLabels", true);
                        entry.addProperty("labelsReset", true);
                    } catch (Exception e) {
                        entry.addProperty("applied", false);
                        entry.addProperty("updated", false);
                        entry.addProperty("status", "error");
                        entry.addProperty("resetLabels", false);
                        entry.addProperty("labelsReset", false);
                        entry.addProperty("error",
                                "Failed to reset label positions: " + safeMessage(e));
                    }
                }
                JsonObject receipt = new JsonObject();
                receipt.addProperty("operation", "repairLabelPositions");
                receipt.addProperty("diagramId", diagramId);
                receipt.addProperty("diagramType", diagramType);
                receipt.addProperty("presentationId", target.getID());
                receipt.addProperty("onlyOverlapping", onlyOverlapping);
                receipt.addProperty("overlapPadding", overlapPadding);
                receipt.addProperty("status", entry.get("status").getAsString());
                receipt.addProperty("updated", entry.get("updated").getAsBoolean());
                entry.add("receipt", receipt);
                results.add(entry);
            }

            JsonObject response = new JsonObject();
            response.addProperty("diagramId", diagramId);
            response.addProperty("diagramType", diagramType);
            response.addProperty("repairMode", "label-positions");
            response.addProperty("dryRun", dryRun);
            response.addProperty("onlyOverlapping", onlyOverlapping);
            response.addProperty("overlapPadding", overlapPadding);
            response.addProperty("resultCount", results.size());
            response.addProperty("updatedCount", countUpdatedTargets(results));
            response.add("results", results);
            response.add("receipt", buildBatchRepairReceipt(
                    "repairLabelPositions",
                    diagramId,
                    diagramType,
                    dryRun,
                    targets.size() + selection.errors.size(),
                    countUpdatedTargets(results),
                    results.size(),
                    countErrorTargets(results)));
            return response;
        });

        HttpBridgeServer.sendJson(exchange, 200, result);
    }

    private void handleForceConveyedItemLabels(
            HttpExchange exchange,
            String diagramId) throws Exception {
        JsonObject body = JsonHelper.parseBody(exchange);
        List<String> presentationIds = JsonHelper.optionalStringList(body, "presentationIds");
        boolean dryRun = readBoolean(body, "dryRun", false);
        boolean resetLabels = readBoolean(body, "resetLabels", true);

        JsonObject result = EdtDispatcher.write("MCP Bridge: Force Conveyed Item Labels", project -> {
            DiagramPresentationElement dpe = findDiagramById(project, diagramId);
            dpe.ensureLoaded();

            String diagramType = diagramTypeName(dpe);
            RepairDefaults defaults = repairDefaultsForDiagramType(diagramType);
            Map<String, PropertySelection> selections = buildSelectionMap(
                    false,
                    defaults.conveyedItemKeys);

            PresentationSelection selection = selectPresentationElementsWithErrors(
                    dpe.getPresentationElements(),
                    presentationIds,
                    target -> target instanceof PathElement && targetSupportsAnySelection(target, selections),
                    "Presentation element does not support conveyed-item labels");

            PresentationElementsManager pem = PresentationElementsManager.getInstance();
            JsonArray results = new JsonArray();
            appendResults(results, selection.errors);
            for (PresentationElement target : selection.targets) {
                JsonObject entry = configurePresentationProperties(
                        target, pem, selections, resetLabels, !dryRun);
                entry.addProperty("repairMode", "conveyed-item-labels");
                entry.add("receipt", buildRepairReceipt(
                        "repairConveyedItemLabels",
                        diagramId,
                        diagramType,
                        target.getID(),
                        !dryRun,
                        resetLabels,
                        entry));
                results.add(entry);
            }

            JsonObject response = new JsonObject();
            response.addProperty("diagramId", diagramId);
            response.addProperty("diagramType", diagramType);
            response.addProperty("repairMode", "conveyed-item-labels");
            response.addProperty("dryRun", dryRun);
            response.addProperty("resetLabels", resetLabels);
            response.addProperty("resultCount", results.size());
            response.addProperty("updatedCount", countUpdatedTargets(results));
            response.add("results", results);
            response.add("receipt", buildBatchRepairReceipt(
                    "repairConveyedItemLabels",
                    diagramId,
                    diagramType,
                    dryRun,
                    selection.totalRequestedCount(),
                    countUpdatedTargets(results),
                    results.size(),
                    countErrorTargets(results)));
            return response;
        });

        HttpBridgeServer.sendJson(exchange, 200, result);
    }

    private void handleNormalizeCompartmentPresets(
            HttpExchange exchange,
            String diagramId) throws Exception {
        JsonObject body = JsonHelper.parseBody(exchange);
        List<String> presentationIds = JsonHelper.optionalStringList(body, "presentationIds");
        boolean dryRun = readBoolean(body, "dryRun", false);

        JsonObject result = EdtDispatcher.write("MCP Bridge: Normalize Compartment Presets", project -> {
            DiagramPresentationElement dpe = findDiagramById(project, diagramId);
            dpe.ensureLoaded();

            String diagramType = diagramTypeName(dpe);
            RepairDefaults defaults = repairDefaultsForDiagramType(diagramType);
            Map<String, PropertySelection> selections = buildSelectionMap(
                    true,
                    defaults.compartmentKeys);

            PresentationSelection selection = selectPresentationElementsWithErrors(
                    dpe.getPresentationElements(),
                    presentationIds,
                    target -> target instanceof ShapeElement
                            && !isCommentLikePresentation(target)
                            && targetSupportsAnySelection(target, selections),
                    "Presentation element does not support compartment normalization");

            PresentationElementsManager pem = PresentationElementsManager.getInstance();
            JsonArray results = new JsonArray();
            appendResults(results, selection.errors);
            for (PresentationElement target : selection.targets) {
                JsonObject entry = configurePresentationProperties(
                        target, pem, selections, false, !dryRun);
                entry.addProperty("repairMode", "compartment-presets");
                entry.add("receipt", buildRepairReceipt(
                        "normalizeCompartmentPresets",
                        diagramId,
                        diagramType,
                        target.getID(),
                        !dryRun,
                        false,
                        entry));
                results.add(entry);
            }

            JsonObject response = new JsonObject();
            response.addProperty("diagramId", diagramId);
            response.addProperty("diagramType", diagramType);
            response.addProperty("repairMode", "compartment-presets");
            response.addProperty("dryRun", dryRun);
            response.addProperty("resultCount", results.size());
            response.addProperty("updatedCount", countUpdatedTargets(results));
            response.add("results", results);
            response.add("receipt", buildBatchRepairReceipt(
                    "normalizeCompartmentPresets",
                    diagramId,
                    diagramType,
                    dryRun,
                    selection.totalRequestedCount(),
                    countUpdatedTargets(results),
                    results.size(),
                    countErrorTargets(results)));
            return response;
        });

        HttpBridgeServer.sendJson(exchange, 200, result);
    }

    private void handlePrunePresentations(HttpExchange exchange, String diagramId) throws Exception {
        JsonObject body = JsonHelper.parseBody(exchange);
        List<String> keepElementIds = JsonHelper.optionalStringList(body, "keepElementIds");
        List<String> dropElementTypes = JsonHelper.optionalStringList(body, "dropElementTypes");
        List<String> dropShapeTypes = JsonHelper.optionalStringList(body, "dropShapeTypes");
        List<String> excludeElementIds = JsonHelper.optionalStringList(body, "excludeElementIds");
        List<String> excludePresentationIds = JsonHelper.optionalStringList(body, "excludePresentationIds");
        boolean dryRun = readBoolean(body, "dryRun", false);

        boolean hasRules = (keepElementIds != null && !keepElementIds.isEmpty())
                || (dropElementTypes != null && !dropElementTypes.isEmpty())
                || (dropShapeTypes != null && !dropShapeTypes.isEmpty())
                || (excludeElementIds != null && !excludeElementIds.isEmpty())
                || (excludePresentationIds != null && !excludePresentationIds.isEmpty());
        if (!hasRules) {
            HttpBridgeServer.sendError(exchange, 400, "MISSING_PARAM",
                    "Request body must include at least one prune rule");
            return;
        }

        JsonObject result = EdtDispatcher.write("MCP Bridge: Prune Diagram Presentations", project -> {
            DiagramPresentationElement dpe = findDiagramById(project, diagramId);
            dpe.ensureLoaded();

            List<PresentationElement> flattened = new ArrayList<>();
            Map<String, String> parentById = new LinkedHashMap<>();
            collectPresentationElements(dpe.getPresentationElements(), flattened, parentById, null);

            PresentationPruneRules rules = new PresentationPruneRules(
                    keepElementIds != null ? new LinkedHashSet<>(keepElementIds) : Collections.emptySet(),
                    dropElementTypes != null ? new ArrayList<>(dropElementTypes) : Collections.emptyList(),
                    dropShapeTypes != null ? new ArrayList<>(dropShapeTypes) : Collections.emptyList(),
                    excludeElementIds != null ? new LinkedHashSet<>(excludeElementIds) : Collections.emptySet(),
                    excludePresentationIds != null ? new LinkedHashSet<>(excludePresentationIds) : Collections.emptySet());

            LinkedHashSet<String> matchedIds = new LinkedHashSet<>();
            for (PresentationElement target : flattened) {
                if (shouldPrunePresentation(target, rules)) {
                    matchedIds.add(target.getID());
                }
            }

            PresentationElementsManager pem = PresentationElementsManager.getInstance();
            JsonArray results = new JsonArray();
            int deletedCount = 0;
            for (PresentationElement target : flattened) {
                String presentationId = target.getID();
                if (!matchedIds.contains(presentationId)) {
                    continue;
                }

                String parentId = parentById.get(presentationId);
                if (parentId != null && matchedIds.contains(parentId)) {
                    continue;
                }

                JsonObject entry = describePresentationElement(target, parentId);
                try {
                    if (dryRun) {
                        entry.addProperty("status", "preview");
                        entry.addProperty("applied", false);
                        entry.addProperty("deleted", false);
                    } else {
                        pem.deletePresentationElement(target);
                        entry.addProperty("status", "deleted");
                        entry.addProperty("applied", true);
                        entry.addProperty("deleted", true);
                        deletedCount++;
                    }
                } catch (Exception e) {
                    entry.addProperty("status", "error");
                    entry.addProperty("applied", false);
                    entry.addProperty("deleted", false);
                    entry.addProperty("error", safeMessage(e));
                }
                results.add(entry);
            }

            String diagramType = diagramTypeName(dpe);
            JsonObject response = new JsonObject();
            response.addProperty("diagramId", diagramId);
            response.addProperty("diagramType", diagramType);
            response.addProperty("dryRun", dryRun);
            response.addProperty("matchedCount", matchedIds.size());
            response.addProperty("targetCount", results.size());
            response.addProperty("deletedCount", deletedCount);
            response.add("results", results);
            response.add("receipt", buildBatchRepairReceipt(
                    "prunePresentations",
                    diagramId,
                    diagramType,
                    dryRun,
                    matchedIds.size(),
                    deletedCount,
                    results.size(),
                    countErrorTargets(results)));
            return response;
        });

        HttpBridgeServer.sendJson(exchange, 200, result);
    }

    private void handleRoutePaths(HttpExchange exchange, String diagramId) throws Exception {
        JsonObject body = JsonHelper.parseBody(exchange);
        if (!body.has("routes") || !body.get("routes").isJsonArray()) {
            HttpBridgeServer.sendError(exchange, 400, "MISSING_PARAM",
                    "Request body must include a 'routes' array");
            return;
        }

        JsonArray routesInput = body.getAsJsonArray("routes");
        JsonObject result = EdtDispatcher.write("MCP Bridge: Route Paths", project -> {
            DiagramPresentationElement dpe = findDiagramById(project, diagramId);
            dpe.ensureLoaded();

            PresentationElementsManager pem = PresentationElementsManager.getInstance();
            List<PresentationElement> allPEs = dpe.getPresentationElements();
            JsonArray results = new JsonArray();

            for (JsonElement item : routesInput) {
                JsonObject routeReq = item.getAsJsonObject();
                String presentationId = JsonHelper.optionalString(routeReq, "presentationId");
                JsonObject entry = new JsonObject();
                entry.addProperty("presentationId", presentationId);

                if (presentationId == null) {
                    entry.addProperty("error", "Each route must include presentationId");
                    results.add(entry);
                    continue;
                }

                PresentationElement target = findPresentationElement(allPEs, presentationId);
                if (!(target instanceof PathElement)) {
                    entry.addProperty("error", "Presentation element is not a path");
                    results.add(entry);
                    continue;
                }

                PathElement path = (PathElement) target;
                List<Point> breakPoints = parsePointList(routeReq.get("breakPoints"));
                Point sourcePoint = parsePoint(routeReq.get("sourcePoint"));
                Point targetPoint = parsePoint(routeReq.get("targetPoint"));
                boolean resetLabels = !routeReq.has("resetLabels")
                        || routeReq.get("resetLabels").getAsBoolean();

                try {
                    if (sourcePoint != null || targetPoint != null) {
                        pem.changePathPoints(path, sourcePoint, targetPoint, breakPoints);
                    } else {
                        pem.changePathBreakPoints(path, breakPoints);
                    }
                    if (resetLabels) {
                        resetLabelPositionsOrThrow(
                                pem,
                                path,
                                "Failed to reset label positions for presentation " + presentationId);
                    }
                } catch (Exception e) {
                    entry.addProperty("status", "error");
                    entry.addProperty("updated", false);
                    entry.addProperty("error", safeMessage(e));
                    results.add(entry);
                    continue;
                }

                entry.addProperty("routed", true);
                entry.addProperty("breakPointCount", breakPoints.size());
                JsonObject receipt = new JsonObject();
                receipt.addProperty("operation", "routePath");
                receipt.addProperty("diagramId", diagramId);
                receipt.addProperty("presentationId", presentationId);
                receipt.addProperty("resetLabels", resetLabels);
                receipt.addProperty("status", "applied");
                entry.add("receipt", receipt);
                results.add(entry);
            }

            JsonObject response = new JsonObject();
            response.addProperty("diagramId", diagramId);
            response.addProperty("resultCount", results.size());
            response.add("results", results);
            return response;
        });

        HttpBridgeServer.sendJson(exchange, 200, result);
    }

    private JsonObject configurePresentationProperties(
            PresentationElement target,
            PresentationElementsManager pem,
            Map<String, PropertySelection> selections,
            boolean resetLabels) {
        return configurePresentationProperties(target, pem, selections, resetLabels, true);
    }

    private JsonObject configurePresentationProperties(
            PresentationElement target,
            PresentationElementsManager pem,
            Map<String, PropertySelection> selections,
            boolean resetLabels,
            boolean applyChanges) {
        PropertyManager pm = target.getPropertyManager().clone();
        @SuppressWarnings("unchecked")
        List<Property> properties = pm.getProperties();
        JsonArray updated = new JsonArray();
        JsonArray supportedRequests = new JsonArray();
        JsonArray unsupportedRequests = new JsonArray();
        JsonArray errors = new JsonArray();

        for (Map.Entry<String, PropertySelection> selection : selections.entrySet()) {
            applyPropertySelection(properties, updated, selection.getKey(), selection.getValue());
        }

        for (JsonElement element : updated) {
            if (!element.isJsonObject()) {
                continue;
            }
            JsonObject entry = element.getAsJsonObject();
            if (!entry.has("request")) {
                continue;
            }
            String request = entry.get("request").getAsString();
            if (entry.has("set") && entry.get("set").getAsBoolean()) {
                supportedRequests.add(request);
            } else if (entry.has("error")) {
                unsupportedRequests.add(request);
            }
        }

        boolean requestedResetLabels = resetLabels && target instanceof PathElement;
        boolean propertyChangesApplied = false;
        boolean labelsReset = false;

        if (applyChanges) {
            if (supportedRequests.size() > 0) {
                try {
                    pem.setPresentationElementProperties(target, pm);
                    propertyChangesApplied = true;
                } catch (Exception e) {
                    errors.add("Failed to apply presentation properties: " + safeMessage(e));
                }
            }
        }
        if (applyChanges && requestedResetLabels) {
            try {
                pem.resetLabelPositions((PathElement) target);
                labelsReset = true;
            } catch (Exception e) {
                errors.add("Failed to reset label positions: " + safeMessage(e));
            }
        }

        boolean unsupportedRequestsPresent = unsupportedRequests.size() > 0;
        boolean updatedFlag = !applyChanges
                ? (supportedRequests.size() > 0 || requestedResetLabels)
                : (propertyChangesApplied || labelsReset);
        String status;
        if (!applyChanges) {
            status = "preview";
        } else if (errors.size() == 0 && unsupportedRequestsPresent) {
            status = updatedFlag ? "partial" : "error";
        } else if (errors.size() == 0) {
            status = "applied";
        } else if (updatedFlag) {
            status = "partial";
        } else {
            status = "error";
        }

        JsonObject response = new JsonObject();
        response.addProperty("presentationId", target.getID());
        if (target.getElement() != null) {
            response.addProperty("elementId", target.getElement().getID());
            response.addProperty("elementType", target.getElement().getHumanType());
        }
        response.addProperty("applied", applyChanges && updatedFlag);
        response.addProperty("fullyApplied", applyChanges && errors.size() == 0 && !unsupportedRequestsPresent);
        response.addProperty("status", status);
        response.addProperty("updated", updatedFlag);
        response.addProperty("requestedResetLabels", requestedResetLabels);
        response.addProperty("resetLabels", labelsReset);
        response.addProperty("labelsReset", labelsReset);
        response.add("supportedRequests", supportedRequests);
        response.add("unsupportedRequests", unsupportedRequests);
        response.add("updates", updated);
        if (errors.size() > 0) {
            response.add("errors", errors);
        }
        response.addProperty("resultCount", updated.size());
        return response;
    }

    private void applyPresentationPropertiesOrThrow(
            PresentationElementsManager pem,
            PresentationElement target,
            PropertyManager pm,
            String message) {
        try {
            pem.setPresentationElementProperties(target, pm);
        } catch (Exception e) {
            throw new IllegalStateException(message + ": " + safeMessage(e), e);
        }
    }

    private void resetLabelPositionsOrThrow(
            PresentationElementsManager pem,
            PathElement path,
            String message) {
        try {
            pem.resetLabelPositions(path);
        } catch (Exception e) {
            throw new IllegalStateException(message + ": " + safeMessage(e), e);
        }
    }

    private void applyPropertySelection(
            List<Property> properties,
            JsonArray updated,
            String requestKey,
            PropertySelection selection) {
        Set<String> seen = new LinkedHashSet<>();
        for (Property property : properties) {
            if (!matchesPropertySelection(property.getName(), selection)) {
                continue;
            }
            String normalized = normalizePropertyKey(property.getName());
            if (!seen.add(normalized)) {
                continue;
            }
            setBooleanLikeProperty(property, selection.value);

            JsonObject entry = new JsonObject();
            entry.addProperty("request", requestKey);
            entry.addProperty("property", property.getName());
            addJsonValue(entry, "value", property.getValue());
            entry.addProperty("set", true);
            updated.add(entry);
        }

        if (seen.isEmpty()) {
            JsonObject missing = new JsonObject();
            missing.addProperty("request", requestKey);
            missing.addProperty("error", "No matching presentation property found");
            updated.add(missing);
        }
    }

    private boolean matchesPropertySelection(String propertyName, PropertySelection selection) {
        String normalized = normalizePropertyKey(propertyName);
        for (String exactName : selection.exactNames) {
            if (normalizePropertyKey(exactName).equals(normalized)) {
                return true;
            }
        }
        for (String containsToken : selection.containsNormalizedTokens) {
            if (normalized.contains(containsToken)) {
                return true;
            }
        }
        return false;
    }

    private void setBooleanLikeProperty(Property property, boolean value) {
        String normalized = normalizePropertyKey(property.getName());
        if (normalized.startsWith("suppress")) {
            property.setValue(!value);
            return;
        }
        property.setValue(value);
    }

    private List<PresentationElement> selectPresentationElements(
            List<PresentationElement> roots,
            List<String> requestedIds,
            Predicate<PresentationElement> predicate) {
        List<PresentationElement> flattened = new ArrayList<>();
        collectPresentationElements(roots, flattened);

        if (requestedIds != null && !requestedIds.isEmpty()) {
            Map<String, PresentationElement> byId = new LinkedHashMap<>();
            for (PresentationElement pe : flattened) {
                byId.put(pe.getID(), pe);
            }
            List<PresentationElement> selected = new ArrayList<>();
            for (String presentationId : requestedIds) {
                PresentationElement target = byId.get(presentationId);
                if (target != null && predicate.test(target)) {
                    selected.add(target);
                }
            }
            return selected;
        }

        List<PresentationElement> selected = new ArrayList<>();
        for (PresentationElement pe : flattened) {
            if (predicate.test(pe)) {
                selected.add(pe);
            }
        }
        return selected;
    }

    private void collectPresentationElements(
            List<PresentationElement> elements,
            List<PresentationElement> sink) {
        collectPresentationElements(elements, sink, null, null);
    }

    private void collectPresentationElements(
            List<PresentationElement> elements,
            List<PresentationElement> sink,
            Map<String, String> parentById,
            String parentPresentationId) {
        if (elements == null) {
            return;
        }
        for (PresentationElement pe : elements) {
            sink.add(pe);
            if (parentById != null && parentPresentationId != null) {
                parentById.put(pe.getID(), parentPresentationId);
            }
            collectPresentationElements(pe.getPresentationElements(), sink, parentById, pe.getID());
        }
    }

    private PresentationSelection selectPresentationElementsWithErrors(
            List<PresentationElement> roots,
            List<String> requestedIds,
            Predicate<PresentationElement> predicate,
            String unsupportedMessage) {
        List<PresentationElement> flattened = new ArrayList<>();
        collectPresentationElements(roots, flattened);

        if (requestedIds == null || requestedIds.isEmpty()) {
            return new PresentationSelection(selectPresentationElements(roots, null, predicate), new JsonArray());
        }

        Map<String, PresentationElement> byId = new LinkedHashMap<>();
        for (PresentationElement pe : flattened) {
            byId.put(pe.getID(), pe);
        }

        List<PresentationElement> selected = new ArrayList<>();
        JsonArray errors = new JsonArray();
        for (String presentationId : requestedIds) {
            PresentationElement target = byId.get(presentationId);
            if (target == null) {
                errors.add(buildSelectionError(presentationId, "Presentation element not found"));
                continue;
            }
            if (!predicate.test(target)) {
                errors.add(buildSelectionError(presentationId, unsupportedMessage));
                continue;
            }
            selected.add(target);
        }
        return new PresentationSelection(selected, errors);
    }

    private boolean isTransitionPathPresentation(PresentationElement pe) {
        return pe instanceof PathElement && presentationElementMatches(pe, "transition");
    }

    private boolean isItemFlowPathPresentation(PresentationElement pe) {
        return pe instanceof PathElement
                && (presentationElementMatches(pe, "informationflow")
                || presentationElementMatches(pe, "itemflow"));
    }

    private boolean isAllocationCompartmentCandidate(PresentationElement pe) {
        return pe instanceof ShapeElement
                && !isCommentLikePresentation(pe)
                && targetHasAllocationProperties(pe);
    }

    private boolean isCommentLikePresentation(PresentationElement pe) {
        if (pe == null) {
            return false;
        }
        if (presentationElementMatches(pe, "comment") || presentationElementMatches(pe, "note")) {
            return true;
        }
        Element element = pe.getElement();
        return element instanceof Comment;
    }

    private boolean targetHasAllocationProperties(PresentationElement pe) {
        try {
            PropertyManager pm = pe.getPropertyManager();
            @SuppressWarnings("unchecked")
            List<Property> properties = pm.getProperties();
            for (Property property : properties) {
                String normalized = normalizePropertyKey(property.getName());
                if (normalized.contains("allocatedelements")
                        || normalized.contains("allocatedfrom")
                        || normalized.contains("allocationcompartmentnaming")
                        || normalized.contains("showelementproperties")
                        || normalized.contains("showfullports")
                        || normalized.contains("suppressfullports")) {
                    return true;
                }
            }
        } catch (Exception e) {
            LOG.log(Level.FINE, "Could not inspect allocation-related shape properties", e);
        }
        return false;
    }

    private boolean targetSupportsAnySelection(
            PresentationElement target,
            Map<String, PropertySelection> selections) {
        try {
            PropertyManager pm = target.getPropertyManager();
            @SuppressWarnings("unchecked")
            List<Property> properties = pm.getProperties();
            for (Property property : properties) {
                for (PropertySelection selection : selections.values()) {
                    if (matchesPropertySelection(property.getName(), selection)) {
                        return true;
                    }
                }
            }
        } catch (Exception e) {
            LOG.log(Level.FINE, "Could not inspect presentation properties", e);
        }
        return false;
    }

    private Map<String, PropertySelection> buildSelectionMap(
            boolean value,
            List<String> canonicalKeys) {
        Map<String, PropertySelection> selections = new LinkedHashMap<>();
        for (String key : canonicalKeys) {
            selections.put(key, selectionForCanonicalKey(key, value));
        }
        return selections;
    }

    private PropertySelection selectionForCanonicalKey(String canonicalKey, boolean value) {
        String normalized = normalizePropertyKey(canonicalKey);
        switch (normalized) {
            case "showname":
                return new PropertySelection(value, List.of("Show Name"), List.of("showname"));
            case "showstereotype":
                return new PropertySelection(value, List.of("Show Stereotype"), List.of("showstereotype"));
            case "showtype":
                return new PropertySelection(value, List.of("Show Type"), List.of("showtype"));
            case "showtriggers":
                return new PropertySelection(value,
                        List.of("Show Triggers", "Show Trigger", "Show Events", "Show Event"),
                        List.of("showtrigger", "showtriggers", "showevent", "showevents"));
            case "showguard":
                return new PropertySelection(value,
                        List.of("Show Guard", "Show Guards", "Show Condition", "Show Conditions"),
                        List.of("showguard", "showguards", "showcondition", "showconditions"));
            case "showeffect":
                return new PropertySelection(value,
                        List.of("Show Effect", "Show Effects", "Show Action", "Show Actions"),
                        List.of("showeffect", "showeffects", "showaction", "showactions"));
            case "showconveyed":
                return new PropertySelection(value, List.of(), List.of("conveyed", "informationflow"));
            case "showitemproperty":
                return new PropertySelection(value, List.of(), List.of("itemproperty"));
            case "showdirection":
                return new PropertySelection(value, List.of(), List.of("showdirection", "direction"));
            case "showproperties":
                return new PropertySelection(value, List.of("Show Properties", "Suppress Properties"),
                        List.of("showproperties", "suppressproperties"));
            case "showoperations":
                return new PropertySelection(value, List.of("Show Operations", "Suppress Operations"),
                        List.of("showoperations", "suppressoperations"));
            case "showconstraints":
                return new PropertySelection(value, List.of("Show Constraints", "Suppress Constraints"),
                        List.of("showconstraints", "suppressconstraints"));
            case "showtaggedvalues":
                return new PropertySelection(value, List.of("Show Tagged Values"),
                        List.of("showtaggedvalues"));
            case "showports":
                return new PropertySelection(value, List.of("Show Ports", "Suppress Ports"),
                        List.of("showports", "suppressports"));
            case "showattributes":
                return new PropertySelection(value, List.of("Suppress Attributes"), List.of("suppressattributes"));
            case "showelementproperties":
                return new PropertySelection(value, List.of("Show Element Properties"),
                        List.of("showelementproperties"));
            case "showfullports":
                return new PropertySelection(value, List.of("Show Full Ports", "Suppress Full Ports"),
                        List.of("showfullports", "suppressfullports"));
            case "showparts":
                return new PropertySelection(value, List.of("Show Parts", "Suppress Parts"),
                        List.of("showparts", "suppressparts"));
            case "showcontent":
                return new PropertySelection(value, List.of("Show Content", "Suppress Content"),
                        List.of("showcontent", "suppresscontent"));
            case "showreferences":
                return new PropertySelection(value, List.of("Show References", "Suppress References"),
                        List.of("showreferences", "suppressreferences"));
            case "showvalues":
                return new PropertySelection(value, List.of("Show Values", "Suppress Values"),
                        List.of("showvalues", "suppressvalues"));
            case "showflowproperties":
                return new PropertySelection(value, List.of("Show Flow Properties", "Suppress Flow Properties"),
                        List.of("showflowproperties", "suppressflowproperties"));
            case "showproxyports":
                return new PropertySelection(value, List.of("Show Proxy Ports", "Suppress Proxy Ports"),
                        List.of("showproxyports", "suppressproxyports"));
            case "showbehaviors":
                return new PropertySelection(value, List.of("Show Behaviors", "Suppress Behaviors"),
                        List.of("showbehaviors", "suppressbehaviors"));
            case "showreceptions":
                return new PropertySelection(value, List.of("Show Receptions", "Suppress Receptions"),
                        List.of("showreceptions", "suppressreceptions"));
            case "showstructure":
                return new PropertySelection(value, List.of("Show Structure", "Suppress Structure"),
                        List.of("showstructure", "suppressstructure"));
            case "showallocatedelements":
                return new PropertySelection(value, List.of(), List.of("allocatedelements", "allocatedfrom"));
            case "applyallocationnaming":
                return new PropertySelection(value, List.of("Apply SysML 1.7 Allocation Compartment Naming"),
                        List.of("allocationcompartmentnaming"));
            default:
                return new PropertySelection(value, List.of(canonicalKey), List.of(normalized));
        }
    }

    private JsonObject buildBatchRepairReceipt(
            String operation,
            String diagramId,
            String diagramType,
            boolean dryRun,
            int targetCount,
            int updatedCount,
            int resultCount,
            int errorCount) {
        JsonObject receipt = new JsonObject();
        receipt.addProperty("operation", operation);
        receipt.addProperty("diagramId", diagramId);
        receipt.addProperty("diagramType", diagramType);
        receipt.addProperty("status", dryRun ? "preview" : "applied");
        receipt.addProperty("dryRun", dryRun);
        receipt.addProperty("targetCount", targetCount);
        receipt.addProperty("updatedCount", updatedCount);
        receipt.addProperty("resultCount", resultCount);
        receipt.addProperty("errorCount", errorCount);
        return receipt;
    }

    private JsonObject buildRepairReceipt(
            String operation,
            String diagramId,
            String diagramType,
            String presentationId,
            boolean applied,
            boolean resetLabels,
            JsonObject resultEntry) {
        JsonObject receipt = new JsonObject();
        receipt.addProperty("operation", operation);
        receipt.addProperty("diagramId", diagramId);
        receipt.addProperty("diagramType", diagramType);
        receipt.addProperty("presentationId", presentationId);
        String status = resultEntry != null && resultEntry.has("status")
                ? resultEntry.get("status").getAsString()
                : (applied ? "applied" : "preview");
        receipt.addProperty("status", status);
        receipt.addProperty("applied", resultEntry != null && resultEntry.has("applied")
                ? resultEntry.get("applied").getAsBoolean()
                : applied);
        receipt.addProperty("resetLabels", resultEntry != null && resultEntry.has("resetLabels")
                ? resultEntry.get("resetLabels").getAsBoolean()
                : resetLabels);
        receipt.addProperty("updated", resultEntry != null && resultEntry.has("updated")
                && resultEntry.get("updated").getAsBoolean());
        receipt.addProperty("updateCount", resultEntry != null && resultEntry.has("updates")
                ? resultEntry.getAsJsonArray("updates").size()
                : 0);
        return receipt;
    }

    private int countUpdatedTargets(JsonArray results) {
        int count = 0;
        for (JsonElement element : results) {
            if (!element.isJsonObject()) {
                continue;
            }
            JsonObject entry = element.getAsJsonObject();
            if (entry.has("error")) {
                continue;
            }
            if (entry.has("updated") && entry.get("updated").isJsonPrimitive()
                    && entry.get("updated").getAsBoolean()) {
                count++;
                continue;
            }
            if (entry.has("updates") && entry.get("updates").isJsonArray()
                    && entry.getAsJsonArray("updates").size() > 0) {
                count++;
            }
        }
        return count;
    }

    private int countErrorTargets(JsonArray results) {
        int count = 0;
        for (JsonElement element : results) {
            if (!element.isJsonObject()) {
                continue;
            }
            JsonObject entry = element.getAsJsonObject();
            if (entry.has("error")) {
                count++;
            }
        }
        return count;
    }

    private void appendResults(JsonArray target, JsonArray source) {
        for (JsonElement element : source) {
            target.add(element);
        }
    }

    private JsonObject buildSelectionError(String presentationId, String message) {
        JsonObject entry = new JsonObject();
        entry.addProperty("presentationId", presentationId);
        entry.addProperty("status", "error");
        entry.addProperty("applied", false);
        entry.addProperty("updated", false);
        entry.addProperty("error", message);
        return entry;
    }

    private String safeMessage(Exception e) {
        return e.getMessage() != null ? e.getMessage() : e.getClass().getSimpleName();
    }

    private List<PresentationElement> selectOverlappingPathTargets(
            List<PresentationElement> targets,
            int overlapPadding) {
        if (targets == null || targets.size() < 2) {
            return targets == null ? List.of() : targets;
        }

        Map<String, Rectangle> boundsById = new LinkedHashMap<>();
        for (PresentationElement target : targets) {
            try {
                Rectangle bounds = target.getBounds();
                if (bounds != null) {
                    boundsById.put(target.getID(), new Rectangle(bounds));
                }
            } catch (Exception e) {
                LOG.log(Level.FINE, "Could not inspect path bounds for overlap", e);
            }
        }

        if (boundsById.size() < 2) {
            return List.of();
        }

        Set<String> selectedIds = new LinkedHashSet<>();
        List<Map.Entry<String, Rectangle>> entries = new ArrayList<>(boundsById.entrySet());
        for (int i = 0; i < entries.size(); i++) {
            Map.Entry<String, Rectangle> leftEntry = entries.get(i);
            Rectangle leftBounds = new Rectangle(leftEntry.getValue());
            leftBounds.grow(overlapPadding, overlapPadding);
            for (int j = i + 1; j < entries.size(); j++) {
                Map.Entry<String, Rectangle> rightEntry = entries.get(j);
                if (leftBounds.intersects(rightEntry.getValue())
                        || rightEntry.getValue().intersects(leftEntry.getValue())) {
                    selectedIds.add(leftEntry.getKey());
                    selectedIds.add(rightEntry.getKey());
                }
            }
        }

        List<PresentationElement> selected = new ArrayList<>();
        for (PresentationElement target : targets) {
            if (selectedIds.contains(target.getID())) {
                selected.add(target);
            }
        }
        return selected;
    }

    private String diagramTypeName(DiagramPresentationElement dpe) {
        if (dpe == null || dpe.getDiagramType() == null || dpe.getDiagramType().getType() == null) {
            return "";
        }
        return dpe.getDiagramType().getType();
    }

    static JsonObject describeRepairDefaults(String diagramType) {
        RepairDefaults defaults = repairDefaultsForDiagramType(diagramType);
        JsonObject json = new JsonObject();
        json.addProperty("diagramType", defaults.diagramType);
        json.addProperty("normalizedDiagramType", defaults.normalizedDiagramType);
        json.addProperty("resetPathLabelsByDefault", defaults.resetPathLabelsByDefault);
        json.add("hiddenLabelKeys", toJsonArray(defaults.hiddenLabelKeys));
        json.add("shapeLabelKeys", toJsonArray(defaults.shapeLabelKeys));
        json.add("pathLabelKeys", toJsonArray(defaults.pathLabelKeys));
        json.add("conveyedItemKeys", toJsonArray(defaults.conveyedItemKeys));
        json.add("compartmentKeys", toJsonArray(defaults.compartmentKeys));
        return json;
    }

    private static JsonArray toJsonArray(List<String> values) {
        JsonArray array = new JsonArray();
        for (String value : values) {
            array.add(value);
        }
        return array;
    }

    private static RepairDefaults repairDefaultsForDiagramType(String diagramType) {
        String normalized = normalizeDiagramType(diagramType);
        List<String> shapeLabelKeys = List.of("showName", "showStereotype");
        List<String> pathLabelKeys = List.of("showName");
        List<String> conveyedItemKeys = List.of("showConveyed", "showItemProperty", "showDirection");
        List<String> compartmentKeys = List.of();
        boolean resetPathLabelsByDefault = true;

        if (normalized.contains("statemachine")) {
            shapeLabelKeys = List.of("showName");
            pathLabelKeys = List.of("showName", "showTriggers", "showGuard", "showEffect");
            conveyedItemKeys = List.of("showName", "showConveyed", "showItemProperty", "showDirection");
        } else if (normalized.contains("internalblock") || normalized.equals("ibd")) {
            shapeLabelKeys = List.of("showName", "showStereotype");
            pathLabelKeys = List.of("showName");
            conveyedItemKeys = List.of("showConveyed", "showItemProperty", "showDirection", "showStereotype");
            compartmentKeys = List.of("showPorts", "showFullPorts", "showElementProperties",
                    "showAllocatedElements", "applyAllocationNaming");
        } else if (normalized.contains("blockdefinition") || normalized.equals("bdd")
                || normalized.contains("classdiagram")) {
            shapeLabelKeys = List.of("showName", "showStereotype", "showType");
            pathLabelKeys = List.of("showName");
            compartmentKeys = List.of("showProperties", "showOperations", "showConstraints",
                    "showTaggedValues", "showPorts", "showAttributes");
        } else if (normalized.contains("requirement")) {
            shapeLabelKeys = List.of("showName", "showStereotype", "showType");
            pathLabelKeys = List.of("showName");
            compartmentKeys = List.of("showConstraints", "showTaggedValues");
        } else if (normalized.contains("usecase")) {
            shapeLabelKeys = List.of("showName", "showStereotype");
            pathLabelKeys = List.of();
            compartmentKeys = List.of();
        } else if (normalized.contains("activity")) {
            shapeLabelKeys = List.of("showName", "showStereotype");
            pathLabelKeys = List.of("showName");
            compartmentKeys = List.of();
        } else if (normalized.contains("sequence")) {
            shapeLabelKeys = List.of("showName");
            pathLabelKeys = List.of("showName");
            compartmentKeys = List.of();
        } else if (normalized.contains("component") || normalized.contains("deployment")
                || normalized.contains("package") || normalized.contains("compositestructure")) {
            shapeLabelKeys = List.of("showName", "showStereotype", "showType");
            pathLabelKeys = List.of("showName");
            compartmentKeys = List.of("showProperties", "showOperations", "showConstraints",
                    "showTaggedValues", "showPorts", "showAttributes");
        }

        List<String> hiddenLabelKeys = mergeCanonicalKeys(shapeLabelKeys, pathLabelKeys);
        return new RepairDefaults(
                diagramType == null ? "" : diagramType,
                normalized,
                hiddenLabelKeys,
                shapeLabelKeys,
                pathLabelKeys,
                conveyedItemKeys,
                compartmentKeys,
                resetPathLabelsByDefault);
    }

    @SafeVarargs
    private static List<String> mergeCanonicalKeys(List<String>... groups) {
        LinkedHashSet<String> merged = new LinkedHashSet<>();
        for (List<String> group : groups) {
            if (group == null) {
                continue;
            }
            merged.addAll(group);
        }
        return List.copyOf(merged);
    }

    private static String normalizeDiagramType(String value) {
        return value == null ? "" : value.replaceAll("[^A-Za-z0-9]", "").toLowerCase();
    }

    private boolean shouldPrunePresentation(
            PresentationElement pe,
            PresentationPruneRules rules) {
        if (pe == null || rules == null) {
            return false;
        }

        String presentationId = pe.getID();
        if (presentationId == null || rules.excludePresentationIds.contains(presentationId)) {
            return false;
        }

        Element element = null;
        try {
            element = pe.getElement();
        } catch (Exception e) {
            LOG.log(Level.FINE, "Could not inspect presentation element for pruning", e);
        }

        if (element instanceof Diagram) {
            return false;
        }

        String elementId = element != null ? element.getID() : null;
        if (elementId != null && rules.excludeElementIds.contains(elementId)) {
            return false;
        }

        boolean matched = false;
        if (!rules.keepElementIds.isEmpty() && elementId != null && !rules.keepElementIds.contains(elementId)) {
            matched = true;
        }
        if (!rules.dropElementTypes.isEmpty() && matchesAnyPresentationToken(pe, rules.dropElementTypes)) {
            matched = true;
        }
        if (!rules.dropShapeTypes.isEmpty() && matchesAnyShapeTypeToken(pe, rules.dropShapeTypes)) {
            matched = true;
        }
        return matched;
    }

    private boolean presentationElementMatches(PresentationElement pe, String token) {
        if (pe == null) {
            return false;
        }
        String normalizedToken = normalizePropertyKey(token);
        String className = normalizePropertyKey(pe.getClass().getSimpleName());
        if (className.contains(normalizedToken)) {
            return true;
        }
        Element element = pe.getElement();
        if (element == null) {
            return false;
        }
        String humanType = normalizePropertyKey(element.getHumanType());
        if (humanType.contains(normalizedToken)) {
            return true;
        }
        Object classType = element.getClassType();
        String runtimeType = normalizePropertyKey(
                classType != null ? classType.toString() : "");
        return runtimeType.contains(normalizedToken);
    }

    private boolean matchesAnyPresentationToken(PresentationElement pe, List<String> tokens) {
        if (tokens == null) {
            return false;
        }
        for (String token : tokens) {
            if (presentationElementMatches(pe, token)) {
                return true;
            }
        }
        return false;
    }

    private boolean matchesAnyShapeTypeToken(PresentationElement pe, List<String> tokens) {
        if (pe == null || tokens == null) {
            return false;
        }
        String shapeType = normalizePropertyKey(pe.getClass().getSimpleName());
        for (String token : tokens) {
            if (shapeType.contains(normalizePropertyKey(token))) {
                return true;
            }
        }
        return false;
    }

    private boolean readBoolean(JsonObject body, String key, boolean defaultValue) {
        if (body == null || !body.has(key) || body.get(key).isJsonNull()) {
            return defaultValue;
        }
        return body.get(key).getAsBoolean();
    }

    /**
     * Find a PresentationElement by its ID, searching recursively into children.
     */
    private PresentationElement findPresentationElement(
            List<PresentationElement> elements, String peId) {
        if (elements == null || peId == null) return null;
        for (PresentationElement pe : elements) {
            if (peId.equals(pe.getID())) {
                return pe;
            }
            // Recurse into children (regions, nested states, messages, etc.)
            List<PresentationElement> children = pe.getPresentationElements();
            if (children != null && !children.isEmpty()) {
                PresentationElement found = findPresentationElement(children, peId);
                if (found != null) return found;
            }
        }
        return null;
    }

    private static final class DiagramAddResult {
        private final ShapeElement shape;
        private final String status;
        private final boolean activityPartitionNative;

        private DiagramAddResult(ShapeElement shape, String status, boolean activityPartitionNative) {
            this.shape = shape;
            this.status = status;
            this.activityPartitionNative = activityPartitionNative;
        }
    }

    private static final class RelationMapOptions {
        private final String contextId;
        private final List<String> scopeIds;
        private final List<String> elementTypes;
        private final List<String> dependencyCriteria;
        private final Integer depth;

        private RelationMapOptions(
                String contextId,
                List<String> scopeIds,
                List<String> elementTypes,
                List<String> dependencyCriteria,
                Integer depth) {
            this.contextId = contextId;
            this.scopeIds = scopeIds;
            this.elementTypes = elementTypes;
            this.dependencyCriteria = dependencyCriteria;
            this.depth = depth;
        }

        private static RelationMapOptions fromJson(JsonObject body) {
            Integer depth = null;
            if (body.has("relationMapDepth") && !body.get("relationMapDepth").isJsonNull()) {
                depth = body.get("relationMapDepth").getAsInt();
                if (depth < BasicGraphSettings.INDEFINITE_DEPTH || depth > 100) {
                    throw new IllegalArgumentException(
                            "relationMapDepth must be -1 for indefinite depth, or between 0 and 100");
                }
            }
            return new RelationMapOptions(
                    JsonHelper.optionalString(body, "relationMapContextId"),
                    JsonHelper.optionalStringList(body, "relationMapScopeIds"),
                    JsonHelper.optionalStringList(body, "relationMapElementTypes"),
                    JsonHelper.optionalStringList(body, "relationMapDependencyCriteria"),
                    depth);
        }

        private boolean hasConfiguration() {
            return contextId != null
                    || scopeIds != null
                    || elementTypes != null
                    || dependencyCriteria != null
                    || depth != null;
        }
    }

    private static final class PresentationPruneRules {
        private final Set<String> keepElementIds;
        private final List<String> dropElementTypes;
        private final List<String> dropShapeTypes;
        private final Set<String> excludeElementIds;
        private final Set<String> excludePresentationIds;

        private PresentationPruneRules(
                Set<String> keepElementIds,
                List<String> dropElementTypes,
                List<String> dropShapeTypes,
                Set<String> excludeElementIds,
                Set<String> excludePresentationIds) {
            this.keepElementIds = keepElementIds;
            this.dropElementTypes = dropElementTypes;
            this.dropShapeTypes = dropShapeTypes;
            this.excludeElementIds = excludeElementIds;
            this.excludePresentationIds = excludePresentationIds;
        }
    }

    private void addJsonValue(JsonObject target, String key, Object value) {
        if (value == null) {
            return;
        }
        if (value instanceof Boolean) {
            target.addProperty(key, (Boolean) value);
        } else if (value instanceof Number) {
            target.addProperty(key, (Number) value);
        } else {
            target.addProperty(key, String.valueOf(value));
        }
    }

    private String canonicalCompartmentKey(String propertyName) {
        if (propertyName == null) {
            return null;
        }
        String normalized = normalizePropertyKey(propertyName);
        switch (normalized) {
            case "showproperties":
                return "properties";
            case "showoperations":
            case "suppressoperations":
                return "operations";
            case "showconstraints":
                return "constraints";
            case "showtaggedvalues":
                return "tagged_values";
            case "showports":
                return "ports";
            case "suppressattributes":
                return "attributes";
            case "showstereotype":
                return "stereotype";
            case "showname":
                return "name";
            case "showtype":
                return "type";
            default:
                return null;
        }
    }

    private static String normalizePropertyKey(String value) {
        return value == null ? "" : value.replaceAll("[^A-Za-z0-9]", "").toLowerCase();
    }

    private Property resolveCompartmentProperty(Map<String, Property> propertyByName, String requestedKey) {
        String normalized = normalizePropertyKey(requestedKey);
        for (Map.Entry<String, Property> entry : propertyByName.entrySet()) {
            if (normalizePropertyKey(entry.getKey()).equals(normalized)) {
                return entry.getValue();
            }
        }

        for (String candidate : CompartmentAliasResolver.candidatePropertyNames(requestedKey)) {
            Property property = propertyByName.get(candidate);
            if (property != null) {
                return property;
            }
        }
        return null;
    }

    private void applyCompartmentValue(Property property, JsonElement value, String requestedKey) {
        if (value.isJsonPrimitive() && value.getAsJsonPrimitive().isBoolean()) {
            setBooleanLikeProperty(property, value.getAsBoolean());
        } else if (value.isJsonPrimitive() && value.getAsJsonPrimitive().isNumber()) {
            property.setValue(value.getAsInt());
        } else {
            property.setValue(value.getAsString());
        }
    }

    private Point parsePoint(JsonElement pointElement) {
        if (pointElement == null || pointElement.isJsonNull() || !pointElement.isJsonObject()) {
            return null;
        }
        JsonObject pointJson = pointElement.getAsJsonObject();
        if (!pointJson.has("x") || !pointJson.has("y")) {
            return null;
        }
        return new Point(pointJson.get("x").getAsInt(), pointJson.get("y").getAsInt());
    }

    private List<Point> parsePointList(JsonElement pointsElement) {
        List<Point> points = new ArrayList<>();
        if (pointsElement == null || pointsElement.isJsonNull() || !pointsElement.isJsonArray()) {
            return points;
        }
        for (JsonElement pointElement : pointsElement.getAsJsonArray()) {
            Point point = parsePoint(pointElement);
            if (point != null) {
                points.add(point);
            }
        }
        return points;
    }

    private JsonObject describePresentationElement(PresentationElement pe, String parentPeId) {
        JsonObject shapeJson = new JsonObject();
        shapeJson.addProperty("presentationId", pe.getID());
        shapeJson.addProperty("shapeType", pe.getClass().getSimpleName());

        if (parentPeId != null) {
            shapeJson.addProperty("parentPresentationId", parentPeId);
        }

        try {
            Element modelElement = pe.getElement();
            if (modelElement != null) {
                shapeJson.addProperty("elementId", modelElement.getID());
                if (modelElement instanceof NamedElement) {
                    shapeJson.addProperty("elementName",
                            ((NamedElement) modelElement).getName());
                }
                shapeJson.addProperty("elementType", modelElement.getHumanType());
            }
        } catch (Exception e) {
            LOG.log(Level.FINE, "Could not inspect backing element for presentation", e);
        }

        try {
            Rectangle bounds = pe.getBounds();
            if (bounds != null) {
                JsonObject boundsJson = new JsonObject();
                boundsJson.addProperty("x", bounds.x);
                boundsJson.addProperty("y", bounds.y);
                boundsJson.addProperty("width", bounds.width);
                boundsJson.addProperty("height", bounds.height);
                shapeJson.add("bounds", boundsJson);
            }
        } catch (Exception e) {
            LOG.log(Level.FINE, "Could not inspect presentation bounds", e);
        }

        List<PresentationElement> children = pe.getPresentationElements();
        int childCount = (children != null) ? children.size() : 0;
        if (childCount > 0) {
            shapeJson.addProperty("childCount", childCount);
        }
        return shapeJson;
    }

    // ── Utility Methods ─────────────────────────────────────────────────────

    private DiagramPresentationElement findDiagramById(Project project, String diagramId) {
        Object baseElement = project.getElementByID(diagramId);
        if (baseElement instanceof Diagram) {
            DiagramPresentationElement dpe = project.getDiagram((Diagram) baseElement);
            if (dpe != null) {
                return dpe;
            }
        }

        Collection<DiagramPresentationElement> diagrams = project.getDiagrams();
        if (diagrams != null) {
            for (DiagramPresentationElement dpe : diagrams) {
                Diagram d = dpe.getDiagram();
                if (d != null && diagramId.equals(d.getID())) {
                    return dpe;
                }
            }
        }

        throw new IllegalArgumentException("Diagram not found: " + diagramId);
    }

    private String resolveDiagramType(String input) {
        if (input == null) return input;

        String normalized = input.trim().toLowerCase().replace("-", " ").replace("_", " ");

        switch (normalized) {
            case "class":
            case "class diagram":
                return "Class Diagram";
            case "package":
            case "package diagram":
                return "Package Diagram";
            case "use case":
            case "usecase":
            case "use case diagram":
                return "Use Case Diagram";
            case "activity":
            case "activity diagram":
                return "Activity Diagram";
            case "sequence":
            case "sequence diagram":
                return "Sequence Diagram";
            case "state machine":
            case "statemachine":
            case "state machine diagram":
                return "State Machine Diagram";
            case "component":
            case "component diagram":
                return "Component Diagram";
            case "deployment":
            case "deployment diagram":
                return "Deployment Diagram";
            case "composite structure":
            case "composite structure diagram":
                return "Composite Structure Diagram";
            case "object":
            case "object diagram":
                return "Object Diagram";
            case "communication":
            case "communication diagram":
                return "Communication Diagram";
            case "interaction overview":
            case "interaction overview diagram":
                return "Interaction Overview Diagram";
            case "timing":
            case "timing diagram":
                return "Timing Diagram";
            case "profile":
            case "profile diagram":
                return "Profile Diagram";
            case "bdd":
            case "block definition":
            case "block definition diagram":
                return "SysML Block Definition Diagram";
            case "ibd":
            case "internal block":
            case "internal block diagram":
                return "SysML Internal Block Diagram";
            case "requirement":
            case "requirement diagram":
            case "requirements":
            case "sysml requirement diagram":
                return "Requirement Diagram";
            case "parametric":
            case "parametric diagram":
            case "sysml parametric diagram":
                return "SysML Parametric Diagram";
            case "relation map":
            case "relationmap":
            case "relation map diagram":
            case "relationship map":
            case "relationshipmap":
            case "relationship map diagram":
                return "Relation Map Diagram";
            case "content":
            case "contentdiagram":
            case "content diagram":
                return "Content Diagram";
            default:
                return input.trim();
        }
    }

    private static final class PropertySelection {
        private final boolean value;
        private final List<String> exactNames;
        private final List<String> containsNormalizedTokens;

        private PropertySelection(
                boolean value,
                List<String> exactNames,
                List<String> containsNormalizedTokens) {
            this.value = value;
            this.exactNames = exactNames;
            this.containsNormalizedTokens = containsNormalizedTokens;
        }
    }

    private static final class RepairDefaults {
        private final String diagramType;
        private final String normalizedDiagramType;
        private final List<String> hiddenLabelKeys;
        private final List<String> shapeLabelKeys;
        private final List<String> pathLabelKeys;
        private final List<String> conveyedItemKeys;
        private final List<String> compartmentKeys;
        private final boolean resetPathLabelsByDefault;

        private RepairDefaults(
                String diagramType,
                String normalizedDiagramType,
                List<String> hiddenLabelKeys,
                List<String> shapeLabelKeys,
                List<String> pathLabelKeys,
                List<String> conveyedItemKeys,
                List<String> compartmentKeys,
                boolean resetPathLabelsByDefault) {
            this.diagramType = diagramType;
            this.normalizedDiagramType = normalizedDiagramType;
            this.hiddenLabelKeys = hiddenLabelKeys;
            this.shapeLabelKeys = shapeLabelKeys;
            this.pathLabelKeys = pathLabelKeys;
            this.conveyedItemKeys = conveyedItemKeys;
            this.compartmentKeys = compartmentKeys;
            this.resetPathLabelsByDefault = resetPathLabelsByDefault;
        }
    }

    private static final class PresentationSelection {
        private final List<PresentationElement> targets;
        private final JsonArray errors;

        private PresentationSelection(List<PresentationElement> targets, JsonArray errors) {
            this.targets = targets;
            this.errors = errors;
        }

        private int totalRequestedCount() {
            return targets.size() + errors.size();
        }
    }
}
