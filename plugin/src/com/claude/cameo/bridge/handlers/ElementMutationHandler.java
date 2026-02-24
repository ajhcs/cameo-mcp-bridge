package com.claude.cameo.bridge.handlers;

import com.claude.cameo.bridge.HttpBridgeServer;
import com.claude.cameo.bridge.util.EdtDispatcher;
import com.claude.cameo.bridge.util.ElementSerializer;
import com.claude.cameo.bridge.util.JsonHelper;
import com.nomagic.magicdraw.openapi.uml.ModelElementsManager;
import com.nomagic.uml2.ext.magicdraw.classes.mdkernel.Comment;
import com.nomagic.uml2.ext.magicdraw.classes.mdkernel.Element;
import com.nomagic.uml2.ext.magicdraw.classes.mdkernel.NamedElement;
import com.nomagic.uml2.ext.magicdraw.mdprofiles.Profile;
import com.nomagic.uml2.ext.magicdraw.mdprofiles.Stereotype;
import com.nomagic.uml2.ext.jmi.helpers.StereotypesHelper;
import com.nomagic.uml2.impl.ElementsFactory;
import com.sun.net.httpserver.HttpExchange;
import com.sun.net.httpserver.HttpHandler;
import com.google.gson.JsonObject;

import java.io.IOException;
import java.util.Collection;
import java.util.logging.Level;
import java.util.logging.Logger;

public class ElementMutationHandler implements HttpHandler {

    private static final Logger LOG = Logger.getLogger(ElementMutationHandler.class.getName());
    private static final String PREFIX = "/api/v1/elements/";

    @Override
    public void handle(HttpExchange exchange) throws IOException {
        try {
            String method = exchange.getRequestMethod();
            if ("OPTIONS".equals(method)) {
                exchange.getResponseHeaders().set("Access-Control-Allow-Origin", "*");
                exchange.getResponseHeaders().set("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS");
                exchange.getResponseHeaders().set("Access-Control-Allow-Headers", "Content-Type");
                exchange.sendResponseHeaders(204, -1);
                return;
            }
            String path = exchange.getRequestURI().getPath();
            if ("POST".equals(method) && path.equals("/api/v1/elements")) { handleCreateElement(exchange); return; }
            String elementId = JsonHelper.extractPathParam(exchange, PREFIX);
            String subPath = JsonHelper.extractSubPath(exchange, PREFIX);
            if (elementId == null) { HttpBridgeServer.sendError(exchange, 400, "BAD_REQUEST", "Element ID required"); return; }
            if ("POST".equals(method) && "stereotypes".equals(subPath)) { handleApplyStereotype(exchange, elementId); return; }
            if ("PUT".equals(method) && "tagged-values".equals(subPath)) { handleSetTaggedValues(exchange, elementId); return; }
            if ("PUT".equals(method) && subPath == null) { handleModifyElement(exchange, elementId); return; }
            if ("DELETE".equals(method) && subPath == null) { handleDeleteElement(exchange, elementId); return; }
            HttpBridgeServer.sendError(exchange, 404, "NOT_FOUND", "Unknown endpoint: " + method + " " + path);
        } catch (IllegalArgumentException e) {
            HttpBridgeServer.sendError(exchange, 400, "BAD_REQUEST", e.getMessage());
        } catch (IllegalStateException e) {
            HttpBridgeServer.sendError(exchange, 409, "CONFLICT", e.getMessage());
        } catch (Exception e) {
            LOG.log(Level.SEVERE, "Error in ElementMutationHandler", e);
            HttpBridgeServer.sendError(exchange, 500, "INTERNAL_ERROR", e.getMessage());
        }
    }

    private void handleCreateElement(HttpExchange exchange) throws Exception {
        JsonObject body = JsonHelper.parseBody(exchange);
        String type = requireString(body, "type");
        String name = requireString(body, "name");
        String parentId = requireString(body, "parentId");
        String stereotype = optionalString(body, "stereotype");
        String documentation = optionalString(body, "documentation");

        JsonObject result = EdtDispatcher.write("Create " + type + " " + name, project -> {
            Element parent = (Element) project.getElementByID(parentId);
            if (parent == null) {
                throw new IllegalArgumentException("Parent element not found: " + parentId);
            }
            ElementsFactory ef = project.getElementsFactory();
            Element created = createElementByType(ef, type);
            if (created instanceof NamedElement) {
                ((NamedElement) created).setName(name);
            }
            ModelElementsManager.getInstance().addElement(created, parent);
            if (stereotype != null && !stereotype.isEmpty()) {
                Stereotype stereo = findStereotype(project, stereotype, null);
                if (stereo != null) {
                    StereotypesHelper.addStereotype(created, stereo);
                } else {
                    LOG.warning("Stereotype not found: " + stereotype);
                }
            }
            if (documentation != null && !documentation.isEmpty()) {
                Comment comment = ef.createCommentInstance();
                comment.setBody(documentation);
                ModelElementsManager.getInstance().addElement(comment, created);
            }
            JsonObject response = new JsonObject();
            response.addProperty("created", true);
            response.add("element", ElementSerializer.toJson(created));
            return response;
        });
        HttpBridgeServer.sendJson(exchange, 201, result);
    }

    private void handleModifyElement(HttpExchange exchange, String elementId) throws Exception {
        JsonObject body = JsonHelper.parseBody(exchange);
        String newName = optionalString(body, "name");
        String newDoc = optionalString(body, "documentation");
        if (newName == null && newDoc == null) {
            HttpBridgeServer.sendError(exchange, 400, "BAD_REQUEST",
                    "At least one of name or documentation is required");
            return;
        }
        JsonObject result = EdtDispatcher.write("Modify element " + elementId, project -> {
            Element element = (Element) project.getElementByID(elementId);
            if (element == null) {
                throw new IllegalArgumentException("Element not found: " + elementId);
            }
            if (newName != null && element instanceof NamedElement) {
                ((NamedElement) element).setName(newName);
            }
            if (newDoc != null) {
                Collection<Comment> comments = element.getOwnedComment();
                if (comments != null && !comments.isEmpty()) {
                    Comment first = comments.iterator().next();
                    first.setBody(newDoc);
                } else {
                    ElementsFactory ef = project.getElementsFactory();
                    Comment comment = ef.createCommentInstance();
                    comment.setBody(newDoc);
                    ModelElementsManager.getInstance().addElement(comment, element);
                }
            }
            JsonObject response = new JsonObject();
            response.addProperty("modified", true);
            response.add("element", ElementSerializer.toJson(element));
            return response;
        });
        HttpBridgeServer.sendJson(exchange, 200, result);
    }

    private void handleDeleteElement(HttpExchange exchange, String elementId) throws Exception {
        JsonObject result = EdtDispatcher.write("Delete element " + elementId, project -> {
            Element element = (Element) project.getElementByID(elementId);
            if (element == null) {
                throw new IllegalArgumentException("Element not found: " + elementId);
            }
            String name = (element instanceof NamedElement) ? ((NamedElement) element).getName() : null;
            String type = element.getHumanType();
            ModelElementsManager.getInstance().removeElement(element);
            JsonObject response = new JsonObject();
            response.addProperty("deleted", true);
            response.addProperty("elementId", elementId);
            if (name != null) { response.addProperty("name", name); }
            response.addProperty("type", type);
            return response;
        });
        HttpBridgeServer.sendJson(exchange, 200, result);
    }

    private void handleApplyStereotype(HttpExchange exchange, String elementId) throws Exception {
        JsonObject body = JsonHelper.parseBody(exchange);
        String stereotypeName = requireString(body, "stereotype");
        String profileName = optionalString(body, "profile");

        JsonObject result = EdtDispatcher.write(
                "Apply stereotype " + stereotypeName + " to " + elementId, project -> {
            Element element = (Element) project.getElementByID(elementId);
            if (element == null) {
                throw new IllegalArgumentException("Element not found: " + elementId);
            }
            Stereotype stereo = findStereotype(project, stereotypeName, profileName);
            if (stereo == null) {
                throw new IllegalArgumentException(
                        "Stereotype not found: " + stereotypeName
                                + (profileName != null ? " in profile " + profileName : ""));
            }
            StereotypesHelper.addStereotype(element, stereo);
            JsonObject response = new JsonObject();
            response.addProperty("applied", true);
            response.addProperty("stereotype", stereotypeName);
            response.add("element", ElementSerializer.toJson(element));
            return response;
        });
        HttpBridgeServer.sendJson(exchange, 200, result);
    }

    private void handleSetTaggedValues(HttpExchange exchange, String elementId) throws Exception {
        JsonObject body = JsonHelper.parseBody(exchange);
        String stereotypeName = requireString(body, "stereotype");
        if (!body.has("values") || !body.get("values").isJsonObject()) {
            HttpBridgeServer.sendError(exchange, 400, "BAD_REQUEST", "values object is required");
            return;
        }
        JsonObject values = body.getAsJsonObject("values");

        JsonObject result = EdtDispatcher.write("Set tagged values on " + elementId, project -> {
            Element element = (Element) project.getElementByID(elementId);
            if (element == null) {
                throw new IllegalArgumentException("Element not found: " + elementId);
            }
            Stereotype stereo = StereotypesHelper.getAppliedStereotypeByString(element, stereotypeName);
            if (stereo == null) {
                stereo = findStereotype(project, stereotypeName, null);
                if (stereo == null) {
                    throw new IllegalArgumentException("Stereotype not found: " + stereotypeName);
                }
                if (!StereotypesHelper.hasStereotype(element, stereo)) {
                    throw new IllegalStateException("Stereotype " + stereotypeName
                            + " is not applied to element " + elementId);
                }
            }
            int setCount = 0;
            for (String tagName : values.keySet()) {
                String tagValue = values.get(tagName).getAsString();
                StereotypesHelper.setStereotypePropertyValue(element, stereo, tagName, tagValue);
                setCount++;
            }
            JsonObject response = new JsonObject();
            response.addProperty("updated", true);
            response.addProperty("tagCount", setCount);
            response.add("element", ElementSerializer.toJson(element));
            return response;
        });
        HttpBridgeServer.sendJson(exchange, 200, result);
    }

    private Element createElementByType(ElementsFactory ef, String type) {
        switch (type.toLowerCase()) {
            case "package":       return ef.createPackageInstance();
            case "block":
            case "class":         return ef.createClassInstance();
            case "use-case":
            case "usecase":       return ef.createUseCaseInstance();
            case "activity":      return ef.createActivityInstance();
            case "actor":         return ef.createActorInstance();
            case "requirement":   return ef.createClassInstance();
            case "interface-block":
            case "interfaceblock":
            case "interface":     return ef.createInterfaceInstance();
            case "constraint-block":
            case "constraintblock": return ef.createClassInstance();
            case "value-type":
            case "valuetype":
            case "datatype":      return ef.createDataTypeInstance();
            case "signal":        return ef.createSignalInstance();
            case "property":      return ef.createPropertyInstance();
            case "operation":     return ef.createOperationInstance();
            case "port":          return ef.createPortInstance();
            case "enumeration":   return ef.createEnumerationInstance();
            case "component":     return ef.createComponentInstance();
            case "constraint":    return ef.createConstraintInstance();
            case "comment":       return ef.createCommentInstance();
            default:
                throw new IllegalArgumentException("Unsupported element type: " + type
                        + ". Supported: package, block, class, use-case, activity, actor, "
                        + "requirement, interface-block, constraint-block, value-type, "
                        + "signal, property, operation, port");
        }
    }

    private Stereotype findStereotype(com.nomagic.magicdraw.core.Project project,
            String stereotypeName, String profileName) {
        if (profileName != null && !profileName.isEmpty()) {
            Profile profile = StereotypesHelper.getProfile(project, profileName);
            if (profile != null) {
                Stereotype stereo = StereotypesHelper.getStereotype(project, stereotypeName, profile);
                if (stereo != null) return stereo;
            }
        }
        Collection<Stereotype> allStereotypes = StereotypesHelper.getAllStereotypes(project);
        if (allStereotypes != null) {
            for (Stereotype st : allStereotypes) {
                if (stereotypeName.equalsIgnoreCase(st.getName())) {
                    return st;
                }
            }
        }
        return null;
    }

    private String requireString(JsonObject body, String key) {
        if (!body.has(key) || body.get(key).isJsonNull()) {
            throw new IllegalArgumentException("Required field missing: " + key);
        }
        String value = body.get(key).getAsString();
        if (value.isEmpty()) {
            throw new IllegalArgumentException("Required field is empty: " + key);
        }
        return value;
    }

    private String optionalString(JsonObject body, String key) {
        if (!body.has(key) || body.get(key).isJsonNull()) {
            return null;
        }
        String value = body.get(key).getAsString();
        return value.isEmpty() ? null : value;
    }
}
