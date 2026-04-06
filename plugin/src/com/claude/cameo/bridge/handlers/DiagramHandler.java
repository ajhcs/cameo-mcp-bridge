package com.claude.cameo.bridge.handlers;

import com.claude.cameo.bridge.HttpBridgeServer;
import com.claude.cameo.bridge.util.EdtDispatcher;
import com.claude.cameo.bridge.util.ElementSerializer;
import com.claude.cameo.bridge.util.JsonHelper;
import com.nomagic.magicdraw.core.Project;
import com.nomagic.magicdraw.export.image.ImageExporter;
import com.nomagic.magicdraw.openapi.uml.ModelElementsManager;
import com.nomagic.magicdraw.openapi.uml.PresentationElementsManager;
import com.nomagic.magicdraw.uml.symbols.DiagramPresentationElement;
import com.nomagic.magicdraw.uml.symbols.PresentationElement;
import com.nomagic.magicdraw.uml.symbols.shapes.ShapeElement;
import com.nomagic.magicdraw.uml.symbols.paths.PathElement;
import com.nomagic.magicdraw.properties.PropertyManager;
import com.nomagic.magicdraw.properties.Property;
import com.nomagic.uml2.ext.magicdraw.classes.mdkernel.Diagram;
import com.nomagic.uml2.ext.magicdraw.classes.mdkernel.Element;
import com.nomagic.uml2.ext.magicdraw.classes.mdkernel.NamedElement;
import com.nomagic.uml2.ext.magicdraw.classes.mdkernel.Namespace;
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
import java.util.Base64;
import java.util.Collection;
import java.util.List;
import java.util.Map;
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
        JsonObject result = EdtDispatcher.read(project -> {
            DiagramPresentationElement dpe = findDiagramById(project, diagramId);
            dpe.ensureLoaded();

            BufferedImage image = ImageExporter.export(dpe, false);
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
            response.addProperty("image", base64);
            return response;
        });

        HttpBridgeServer.sendJson(exchange, 200, result);
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
            return response;
        });

        HttpBridgeServer.sendJson(exchange, 201, result);
    }

    private void handleAddElement(HttpExchange exchange, String diagramId) throws Exception {
        JsonObject body = JsonHelper.parseBody(exchange);

        if (!body.has("elementId") || body.get("elementId").getAsString().isEmpty()) {
            HttpBridgeServer.sendError(exchange, 400, "MISSING_PARAM",
                    "Request body must include elementId");
            return;
        }

        String elementId = body.get("elementId").getAsString();
        int x = body.has("x") ? body.get("x").getAsInt() : 100;
        int y = body.has("y") ? body.get("y").getAsInt() : 100;
        String containerPeId = JsonHelper.optionalString(body, "containerPresentationId");
        boolean hasWidth = body.has("width");
        boolean hasHeight = body.has("height");

        if (hasWidth != hasHeight) {
            HttpBridgeServer.sendError(exchange, 400, "MISSING_PARAM",
                    "Request body must include both width and height, or neither");
            return;
        }

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
            ShapeElement shape = pem.createShapeElement(element, shapeParent, true, new Point(x, y));

            if (shape == null) {
                throw new IllegalStateException(
                        "Failed to create shape for element: " + elementId);
            }

            if (hasWidth && hasHeight) {
                int width = body.get("width").getAsInt();
                int height = body.get("height").getAsInt();
                pem.reshapeShapeElement(shape, new Rectangle(x, y, width, height));
            }

            JsonObject response = new JsonObject();
            response.addProperty("diagramId", diagramId);
            response.addProperty("elementId", elementId);
            response.addProperty("x", x);
            response.addProperty("y", y);
            try {
                Rectangle bounds = shape.getBounds();
                if (bounds != null) {
                    response.addProperty("width", bounds.width);
                    response.addProperty("height", bounds.height);
                }
            } catch (Exception e) {
                // Bounds may not be available for all shape types
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
            receipt.addProperty("x", x);
            receipt.addProperty("y", y);
            if (hasWidth && hasHeight) {
                receipt.addProperty("width", body.get("width").getAsInt());
                receipt.addProperty("height", body.get("height").getAsInt());
            }
            receipt.addProperty("status", "created");
            response.add("receipt", receipt);
            return response;
        });

        HttpBridgeServer.sendJson(exchange, 200, result);
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
            pem.setPresentationElementProperties(target, pm);

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

            PresentationElementsManager.getInstance().setPresentationElementProperties(target, pm);

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

                if (sourcePoint != null || targetPoint != null) {
                    pem.changePathPoints(path, sourcePoint, targetPoint, breakPoints);
                } else {
                    pem.changePathBreakPoints(path, breakPoints);
                }
                if (resetLabels) {
                    pem.resetLabelPositions(path);
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

    private String normalizePropertyKey(String value) {
        return value == null ? "" : value.replaceAll("[^A-Za-z0-9]", "").toLowerCase();
    }

    private Property resolveCompartmentProperty(Map<String, Property> propertyByName, String requestedKey) {
        String normalized = normalizePropertyKey(requestedKey);
        for (Map.Entry<String, Property> entry : propertyByName.entrySet()) {
            if (normalizePropertyKey(entry.getKey()).equals(normalized)) {
                return entry.getValue();
            }
        }

        Map<String, String[]> aliases = new LinkedHashMap<>();
        aliases.put("properties", new String[]{"Show Properties"});
        aliases.put("operations", new String[]{"Show Operations", "Suppress Operations"});
        aliases.put("constraints", new String[]{"Show Constraints"});
        aliases.put("taggedvalues", new String[]{"Show Tagged Values"});
        aliases.put("ports", new String[]{"Show Ports"});
        aliases.put("attributes", new String[]{"Suppress Attributes"});
        aliases.put("stereotype", new String[]{"Show Stereotype"});
        aliases.put("name", new String[]{"Show Name"});
        aliases.put("type", new String[]{"Show Type"});

        String[] candidates = aliases.get(normalized);
        if (candidates == null) {
            return null;
        }
        for (String candidate : candidates) {
            Property property = propertyByName.get(candidate);
            if (property != null) {
                return property;
            }
        }
        return null;
    }

    private void applyCompartmentValue(Property property, JsonElement value, String requestedKey) {
        String propertyName = property.getName();
        boolean boolValue = value.getAsBoolean();
        if ("Suppress Attributes".equals(propertyName) || "Suppress Operations".equals(propertyName)) {
            property.setValue(!boolValue);
            return;
        }
        if (value.isJsonPrimitive() && value.getAsJsonPrimitive().isBoolean()) {
            property.setValue(boolValue);
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
                return "SysML Requirement Diagram";
            case "parametric":
            case "parametric diagram":
            case "sysml parametric diagram":
                return "SysML Parametric Diagram";
            default:
                return input.trim();
        }
    }
}
