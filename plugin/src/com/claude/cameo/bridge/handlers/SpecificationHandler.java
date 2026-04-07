package com.claude.cameo.bridge.handlers;

import com.claude.cameo.bridge.HttpBridgeServer;
import com.claude.cameo.bridge.util.EdtDispatcher;
import com.claude.cameo.bridge.util.ElementSerializer;
import com.claude.cameo.bridge.util.JsonHelper;
import com.nomagic.magicdraw.openapi.uml.ModelElementsManager;
import com.nomagic.uml2.ext.magicdraw.classes.mdkernel.Classifier;
import com.nomagic.uml2.ext.magicdraw.classes.mdkernel.Comment;
import com.nomagic.uml2.ext.magicdraw.classes.mdkernel.Constraint;
import com.nomagic.uml2.ext.magicdraw.classes.mdkernel.Element;
import com.nomagic.uml2.ext.magicdraw.classes.mdkernel.LiteralString;
import com.nomagic.uml2.ext.magicdraw.classes.mdkernel.NamedElement;
import com.nomagic.uml2.ext.magicdraw.classes.mdkernel.OpaqueExpression;
import com.nomagic.uml2.ext.magicdraw.classes.mdkernel.Property;
import com.nomagic.uml2.ext.magicdraw.classes.mdkernel.Type;
import com.nomagic.uml2.ext.magicdraw.classes.mdkernel.TypedElement;
import com.nomagic.uml2.ext.magicdraw.classes.mdkernel.ValueSpecification;
import com.nomagic.uml2.ext.magicdraw.classes.mdkernel.VisibilityKind;
import com.nomagic.uml2.ext.magicdraw.classes.mdkernel.VisibilityKindEnum;
import com.nomagic.uml2.ext.magicdraw.mdprofiles.Profile;
import com.nomagic.uml2.ext.magicdraw.mdprofiles.Stereotype;
import com.nomagic.uml2.ext.jmi.helpers.StereotypesHelper;
import com.nomagic.uml2.impl.ElementsFactory;
import com.sun.net.httpserver.HttpExchange;
import com.sun.net.httpserver.HttpHandler;
import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import com.google.gson.JsonPrimitive;

import java.io.IOException;
import java.util.Collection;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.logging.Level;
import java.util.logging.Logger;

/**
 * Handles specification read/write endpoints for full element property access.
 * <p>
 * GET  /api/v1/elements/{id}/specification - returns all editable properties
 * PUT  /api/v1/elements/{id}/specification - sets properties by name
 * <p>
 * Returns standard UML properties via JMI reflection and tagged values from
 * all applied stereotypes.
 */
public class SpecificationHandler implements HttpHandler {

    private static final Logger LOG = Logger.getLogger(SpecificationHandler.class.getName());
    private static final String PREFIX = "/api/v1/elements/";

    private static final String[] STANDARD_FEATURES = {
        "name",
        "visibility",
        "isAbstract",
        "isFinalSpecialization",
        "isLeaf",
        "isStatic",
        "isQuery",
        "isReadOnly",
        "isDerived",
        "isDerivedUnion",
        "isOrdered",
        "isUnique",
        "isActive",
        "type"
    };

    @Override
    public void handle(HttpExchange exchange) throws IOException {
        try {
            String method = exchange.getRequestMethod();

            if ("OPTIONS".equals(method)) {
                exchange.getResponseHeaders().set("Access-Control-Allow-Methods",
                        "GET, PUT, OPTIONS");
                exchange.getResponseHeaders().set("Access-Control-Allow-Headers",
                        "Content-Type");
                exchange.sendResponseHeaders(204, -1);
                return;
            }

            String path = exchange.getRequestURI().getPath();
            String elementId = extractElementId(path);
            if (elementId == null) {
                HttpBridgeServer.sendError(exchange, 400, "BAD_REQUEST",
                        "Element ID required in path");
                return;
            }

            if ("GET".equals(method)) {
                handleGetSpecification(exchange, elementId);
            } else if ("PUT".equals(method)) {
                handleSetSpecification(exchange, elementId);
            } else {
                HttpBridgeServer.sendError(exchange, 405, "METHOD_NOT_ALLOWED",
                        "Only GET and PUT are supported");
            }

        } catch (IllegalArgumentException e) {
            HttpBridgeServer.sendError(exchange, 400, "BAD_REQUEST", e.getMessage());
        } catch (IllegalStateException e) {
            HttpBridgeServer.sendError(exchange, 409, "CONFLICT", e.getMessage());
        } catch (Exception e) {
            LOG.log(Level.SEVERE, "Error in SpecificationHandler", e);
            HttpBridgeServer.sendError(exchange, 500, "INTERNAL_ERROR", e.getMessage());
        }
    }

    private void handleGetSpecification(HttpExchange exchange, String elementId)
            throws Exception {

        JsonObject result = EdtDispatcher.read(project -> {
            Element element = (Element) project.getElementByID(elementId);
            if (element == null) {
                throw new IllegalArgumentException("Element not found: " + elementId);
            }

            JsonObject response = new JsonObject();
            response.addProperty("elementId", element.getID());

            if (element instanceof NamedElement) {
                String name = ((NamedElement) element).getName();
                response.addProperty("name", name != null ? name : "");
            }
            response.addProperty("type", element.getHumanType());

            JsonObject properties = readStandardProperties(element);
            response.add("properties", properties);

            String documentation = readDocumentation(element);
            if (documentation != null) {
                response.addProperty("documentation", documentation);
            }

            JsonArray appliedStereotypes = readAppliedStereotypes(element);
            if (appliedStereotypes.size() > 0) {
                response.add("appliedStereotypes", appliedStereotypes);
            }

            // Read owned constraints (Use Case Description fields, etc.)
            JsonObject constraints = readOwnedConstraints(element);
            if (constraints.size() > 0) {
                response.add("constraints", constraints);
            }

            return response;
        });

        HttpBridgeServer.sendJson(exchange, 200, result);
    }

    private void handleSetSpecification(HttpExchange exchange, String elementId)
            throws Exception {

        JsonObject body = JsonHelper.parseBody(exchange);
        boolean hasProps = body.has("properties") && body.get("properties").isJsonObject()
                && body.getAsJsonObject("properties").size() > 0;
        boolean hasConstraints = body.has("constraints") && body.get("constraints").isJsonObject()
                && body.getAsJsonObject("constraints").size() > 0;
        if (!hasProps && !hasConstraints) {
            HttpBridgeServer.sendError(exchange, 400, "BAD_REQUEST",
                    "Request body must contain a \"properties\" and/or \"constraints\" object");
            return;
        }
        JsonObject props = hasProps ? body.getAsJsonObject("properties") : new JsonObject();
        JsonObject constraintProps = hasConstraints ? body.getAsJsonObject("constraints") : new JsonObject();

        JsonObject result = EdtDispatcher.write(
                "Set specification on " + elementId, project -> {

            Element element = (Element) project.getElementByID(elementId);
            if (element == null) {
                throw new IllegalArgumentException("Element not found: " + elementId);
            }

            Map<String, Stereotype> tagToStereotype = new LinkedHashMap<>();
            List<Stereotype> stereotypes = StereotypesHelper.getStereotypes(element);
            if (stereotypes != null) {
                for (Stereotype st : stereotypes) {
                    List<Property> attrs = st.getAttribute();
                    if (attrs != null) {
                        for (Property attr : attrs) {
                            if (StereotypesHelper.isExtensionProperty(attr)) {
                                continue;
                            }
                            String tagName = attr.getName();
                            if (tagName != null && !tagName.isEmpty()) {
                                tagToStereotype.put(tagName, st);
                            }
                        }
                    }
                }
            }

            JsonArray setPropertiesArr = new JsonArray();
            JsonArray unrecognized = new JsonArray();
            int setCount = 0;

            for (String propName : props.keySet()) {
                JsonElement valueElement = props.get(propName);
                // 1. Check tagged values first
                if (tagToStereotype.containsKey(propName)) {
                    Stereotype stereo = tagToStereotype.get(propName);
                    StereotypesHelper.setStereotypePropertyValue(
                            element, stereo, propName, coerceJsonValue(valueElement, project));
                    setPropertiesArr.add(propName);
                    setCount++;
                    continue;
                }

                // 2. Try standard UML property via typed setters
                boolean handled = trySetStandardProperty(
                        element, propName, valueElement, project);
                if (handled) {
                    setPropertiesArr.add(propName);
                    setCount++;
                    continue;
                }

                // 3. Unrecognized
                unrecognized.add(propName);
            }

            // Handle constraints (Use Case Description fields, etc.)
            JsonArray setConstraintsArr = new JsonArray();
            for (String cName : constraintProps.keySet()) {
                String cValue = constraintProps.get(cName).getAsString();
                setOrCreateConstraint(element, cName, cValue, project);
                setConstraintsArr.add(cName);
                setCount++;
            }

            JsonObject response = new JsonObject();
            response.addProperty("updated", true);
            response.addProperty("setCount", setCount);
            response.add("setProperties", setPropertiesArr);
            if (setConstraintsArr.size() > 0) {
                response.add("setConstraints", setConstraintsArr);
            }
            if (unrecognized.size() > 0) {
                response.add("unrecognized", unrecognized);
            }
            response.add("element", ElementSerializer.toJson(element));
            return response;
        });

        HttpBridgeServer.sendJson(exchange, 200, result);
    }

    // -----------------------------------------------------------------------
    //  Private helpers -- GET specification
    // -----------------------------------------------------------------------

    private JsonObject readStandardProperties(Element element) {
        JsonObject properties = new JsonObject();

        for (String featureName : STANDARD_FEATURES) {
            try {
                Object value = element.refGetValue(featureName);
                if (value != null) {
                    addPropertyValue(properties, featureName, value);
                }
            } catch (Exception e) {
                LOG.log(Level.FINEST, "Feature " + featureName
                        + " not available on " + element.getHumanType(), e);
            }
        }

        // Read subject for UseCases (collection-valued)
        try {
            Object subjectVal = element.refGetValue("subject");
            if (subjectVal instanceof Collection) {
                JsonArray subjectArray = new JsonArray();
                for (Object item : (Collection<?>) subjectVal) {
                    if (item instanceof NamedElement) {
                        JsonObject ref = new JsonObject();
                        ref.addProperty("id", ((Element) item).getID());
                        ref.addProperty("name", ((NamedElement) item).getName());
                        subjectArray.add(ref);
                    }
                }
                if (subjectArray.size() > 0) {
                    properties.add("subject", subjectArray);
                }
            }
        } catch (Exception e) {
            // Not a UseCase or feature not available -- skip
        }

        return properties;
    }

    private void addPropertyValue(JsonObject target, String name, Object value) {
        if (value instanceof Boolean) {
            target.addProperty(name, (Boolean) value);
        } else if (value instanceof Number) {
            target.addProperty(name, (Number) value);
        } else if (value instanceof VisibilityKind) {
            target.addProperty(name, value.toString());
        } else if (value instanceof String) {
            target.addProperty(name, (String) value);
        } else if (value instanceof NamedElement) {
            JsonObject ref = new JsonObject();
            ref.addProperty("id", ((Element) value).getID());
            ref.addProperty("name", ((NamedElement) value).getName());
            target.add(name, ref);
        } else if (value instanceof Element) {
            JsonObject ref = new JsonObject();
            ref.addProperty("id", ((Element) value).getID());
            target.add(name, ref);
        } else if (value instanceof Collection) {
            JsonArray arr = new JsonArray();
            for (Object item : (Collection<?>) value) {
                if (item instanceof NamedElement) {
                    JsonObject ref = new JsonObject();
                    ref.addProperty("id", ((Element) item).getID());
                    ref.addProperty("name", ((NamedElement) item).getName());
                    arr.add(ref);
                } else if (item != null) {
                    arr.add(String.valueOf(item));
                }
            }
            if (arr.size() > 0) {
                target.add(name, arr);
            }
        } else {
            target.addProperty(name, String.valueOf(value));
        }
    }

    private JsonElement serializeTaggedValue(Object value) {
        if (value == null) {
            return null;
        }
        if (value instanceof Boolean) {
            return new JsonPrimitive((Boolean) value);
        }
        if (value instanceof Number) {
            return new JsonPrimitive((Number) value);
        }
        if (value instanceof String) {
            return new JsonPrimitive((String) value);
        }
        if (value instanceof Character) {
            return new JsonPrimitive((Character) value);
        }
        if (value instanceof VisibilityKind) {
            return new JsonPrimitive(value.toString());
        }
        if (value instanceof Element) {
            return ElementSerializer.toJsonCompact((Element) value);
        }
        if (value instanceof Collection<?>) {
            JsonArray arr = new JsonArray();
            for (Object item : (Collection<?>) value) {
                JsonElement serialized = serializeTaggedValue(item);
                if (serialized != null) {
                    arr.add(serialized);
                }
            }
            return arr;
        }
        return new JsonPrimitive(String.valueOf(value));
    }

    private String readDocumentation(Element element) {
        try {
            Collection<Comment> comments = element.getOwnedComment();
            if (comments != null && !comments.isEmpty()) {
                StringBuilder doc = new StringBuilder();
                for (Comment c : comments) {
                    String body = c.getBody();
                    if (body != null && !body.isEmpty()) {
                        if (doc.length() > 0) {
                            doc.append("\n");
                        }
                        doc.append(body);
                    }
                }
                if (doc.length() > 0) {
                    return doc.toString();
                }
            }
        } catch (Exception e) {
            LOG.log(Level.FINE, "Could not read comments", e);
        }
        return null;
    }

    @SuppressWarnings("rawtypes")
    private JsonArray readAppliedStereotypes(Element element) {
        JsonArray result = new JsonArray();
        try {
            List<Stereotype> stereotypes = StereotypesHelper.getStereotypes(element);
            if (stereotypes == null || stereotypes.isEmpty()) {
                return result;
            }

            for (Stereotype stereo : stereotypes) {
                JsonObject stereoObj = new JsonObject();
                stereoObj.addProperty("stereotype", stereo.getName());

                try {
                    Profile profile = stereo.getProfile();
                    if (profile != null) {
                        stereoObj.addProperty("profile", profile.getName());
                    }
                } catch (Exception e) {
                    try {
                        com.nomagic.uml2.ext.magicdraw.classes.mdkernel.Package pkg =
                                StereotypesHelper.getProfileForStereotype(stereo);
                        if (pkg != null) {
                            stereoObj.addProperty("profile", pkg.getName());
                        }
                    } catch (Exception e2) {
                        LOG.log(Level.FINE, "Could not resolve profile for "
                                + stereo.getName(), e2);
                    }
                }

                JsonObject taggedValues = new JsonObject();
                List<Property> attrs = stereo.getAttribute();
                if (attrs != null) {
                    for (Property attr : attrs) {
                        if (StereotypesHelper.isExtensionProperty(attr)) {
                            continue;
                        }
                        String tagName = attr.getName();
                        if (tagName == null || tagName.isEmpty()) {
                            continue;
                        }
                        try {
                            List values = StereotypesHelper
                                    .getStereotypePropertyValue(
                                            element, stereo, tagName);
                            if (values != null && !values.isEmpty()) {
                                if (values.size() == 1) {
                                    JsonElement serialized = serializeTaggedValue(values.get(0));
                                    if (serialized != null) {
                                        taggedValues.add(tagName, serialized);
                                    }
                                } else {
                                    JsonElement serialized = serializeTaggedValue(values);
                                    if (serialized != null) {
                                        taggedValues.add(tagName, serialized);
                                    }
                                }
                            }
                        } catch (Exception e) {
                            LOG.log(Level.FINE,
                                    "Could not read tag " + tagName, e);
                        }
                    }
                }

                if (taggedValues.size() > 0) {
                    stereoObj.add("taggedValues", taggedValues);
                }

                result.add(stereoObj);
            }
        } catch (Exception e) {
            LOG.log(Level.FINE, "Could not read stereotypes", e);
        }
        return result;
    }

    // -----------------------------------------------------------------------
    //  Private helpers -- SET specification
    // -----------------------------------------------------------------------

    private boolean trySetStandardProperty(Element element, String propName,
            JsonElement value,
            com.nomagic.magicdraw.core.Project project) {

        try {
            switch (propName) {
                case "name":
                    if (element instanceof NamedElement) {
                        ((NamedElement) element).setName(value.getAsString());
                        return true;
                    }
                    break;

                case "visibility":
                    if (element instanceof NamedElement) {
                        VisibilityKindEnum vk = VisibilityKindEnum.getByName(
                                value.getAsString().toLowerCase());
                        if (vk != null) {
                            ((NamedElement) element).setVisibility(vk);
                            return true;
                        }
                    }
                    break;

                case "isAbstract":
                    if (element instanceof Classifier) {
                        ((Classifier) element).setAbstract(
                                value.getAsBoolean());
                        return true;
                    }
                    break;

                case "isFinalSpecialization":
                    if (element instanceof Classifier) {
                        ((Classifier) element).setFinalSpecialization(
                                value.getAsBoolean());
                        return true;
                    }
                    break;

                case "documentation":
                    return setDocumentation(element,
                            value.getAsString(), project);

                case "type":
                    return setTypedElementType(element, value, project);

                default:
                    return tryRefSetValue(element, propName, value);
            }
        } catch (Exception e) {
            LOG.log(Level.WARNING,
                    "Failed to set property " + propName, e);
        }
        return false;
    }

    private boolean tryRefSetValue(Element element, String propName,
            JsonElement value) {
        for (String feat : STANDARD_FEATURES) {
            if (feat.equals(propName)) {
                try {
                    if (value.isJsonPrimitive()) {
                        JsonPrimitive prim = value.getAsJsonPrimitive();
                        if (prim.isBoolean()) {
                            element.refSetValue(propName,
                                    prim.getAsBoolean());
                        } else if (prim.isNumber()) {
                            element.refSetValue(propName,
                                    prim.getAsNumber().intValue());
                        } else {
                            element.refSetValue(propName,
                                    prim.getAsString());
                        }
                    } else {
                        element.refSetValue(propName,
                                value.toString());
                    }
                    return true;
                } catch (Exception e) {
                    LOG.log(Level.FINE,
                            "refSetValue failed for " + propName, e);
                    return false;
                }
            }
        }
        return false;
    }

    private boolean setTypedElementType(
            Element element,
            JsonElement value,
            com.nomagic.magicdraw.core.Project project) {
        if (!(element instanceof TypedElement)) {
            return false;
        }
        if (value == null || value.isJsonNull()) {
            ((TypedElement) element).setType(null);
            return true;
        }

        String typeId = null;
        if (value.isJsonPrimitive() && value.getAsJsonPrimitive().isString()) {
            typeId = value.getAsString();
        } else if (value.isJsonObject()) {
            JsonObject obj = value.getAsJsonObject();
            if (obj.has("id") && obj.get("id").isJsonPrimitive()) {
                typeId = obj.get("id").getAsString();
            }
        }

        if (typeId == null || typeId.isEmpty()) {
            return false;
        }

        Element resolved = (Element) project.getElementByID(typeId);
        if (!(resolved instanceof Type)) {
            throw new IllegalArgumentException("Type element not found or not a Type: " + typeId);
        }

        ((TypedElement) element).setType((Type) resolved);
        return true;
    }

    private Object coerceJsonValue(
            JsonElement value,
            com.nomagic.magicdraw.core.Project project) {
        if (value == null || value.isJsonNull()) {
            return null;
        }
        if (value.isJsonArray()) {
            JsonArray array = value.getAsJsonArray();
            List<Object> converted = new java.util.ArrayList<>(array.size());
            for (JsonElement item : array) {
                converted.add(coerceJsonValue(item, project));
            }
            return converted;
        }
        if (value.isJsonObject()) {
            JsonObject obj = value.getAsJsonObject();
            if (obj.has("id") && obj.get("id").isJsonPrimitive()) {
                String id = obj.get("id").getAsString();
                Element referenced = (Element) project.getElementByID(id);
                if (referenced != null) {
                    return referenced;
                }
            }
            return obj.toString();
        }

        JsonPrimitive primitive = value.getAsJsonPrimitive();
        if (primitive.isBoolean()) {
            return primitive.getAsBoolean();
        }
        if (primitive.isNumber()) {
            return primitive.getAsNumber();
        }
        return primitive.getAsString();
    }

    private boolean setDocumentation(Element element, String doc,
            com.nomagic.magicdraw.core.Project project) {
        try {
            Collection<Comment> comments = element.getOwnedComment();
            if (comments != null && !comments.isEmpty()) {
                Comment first = comments.iterator().next();
                first.setBody(doc);
            } else {
                ElementsFactory ef = project.getElementsFactory();
                Comment comment = ef.createCommentInstance();
                comment.setBody(doc);
                ModelElementsManager.getInstance()
                        .addElement(comment, element);
            }
            return true;
        } catch (Exception e) {
            LOG.log(Level.WARNING, "Failed to set documentation", e);
            return false;
        }
    }

    // -----------------------------------------------------------------------
    //  Private helpers -- Constraints (Use Case Description, etc.)
    // -----------------------------------------------------------------------

    private JsonObject readOwnedConstraints(Element element) {
        JsonObject constraints = new JsonObject();
        try {
            Collection<Element> owned = element.getOwnedElement();
            if (owned != null) {
                for (Element child : owned) {
                    if (child instanceof Constraint) {
                        Constraint c = (Constraint) child;
                        String name = (c instanceof NamedElement)
                                ? ((NamedElement) c).getName() : null;
                        if (name == null || name.isEmpty()) continue;
                        String body = readConstraintBody(c);
                        constraints.addProperty(name, body != null ? body : "");
                    }
                }
            }
        } catch (Exception e) {
            LOG.log(Level.FINE, "Could not read owned constraints", e);
        }
        return constraints;
    }

    private String readConstraintBody(Constraint c) {
        try {
            ValueSpecification spec = c.getSpecification();
            if (spec == null) return null;
            if (spec instanceof LiteralString) {
                return ((LiteralString) spec).getValue();
            }
            if (spec instanceof OpaqueExpression) {
                java.util.List<String> bodies = ((OpaqueExpression) spec).getBody();
                if (bodies != null && !bodies.isEmpty()) {
                    return bodies.get(0);
                }
            }
            // Fallback: try stringValue via JMI
            try {
                Object sv = spec.refGetValue("value");
                return sv != null ? String.valueOf(sv) : null;
            } catch (Exception e) {
                return null;
            }
        } catch (Exception e) {
            LOG.log(Level.FINE, "Could not read constraint specification", e);
            return null;
        }
    }

    private void setOrCreateConstraint(Element owner, String name, String text,
            com.nomagic.magicdraw.core.Project project) throws Exception {
        // Try to find existing constraint with this name
        for (Element child : owner.getOwnedElement()) {
            if (child instanceof Constraint) {
                Constraint c = (Constraint) child;
                String cName = (c instanceof NamedElement)
                        ? ((NamedElement) c).getName() : null;
                if (name.equalsIgnoreCase(cName)) {
                    setConstraintText(c, text, project);
                    return;
                }
            }
        }
        // Create new constraint
        ElementsFactory ef = project.getElementsFactory();
        Constraint c = ef.createConstraintInstance();
        ((NamedElement) c).setName(name);
        setConstraintText(c, text, project);
        ModelElementsManager.getInstance().addElement(c, owner);
    }

    private void setConstraintText(Constraint c, String text,
            com.nomagic.magicdraw.core.Project project) {
        ValueSpecification existing = c.getSpecification();
        // Update existing OpaqueExpression or LiteralString if present
        if (existing instanceof OpaqueExpression) {
            java.util.List<String> bodies = ((OpaqueExpression) existing).getBody();
            bodies.clear();
            bodies.add(text);
            return;
        }
        if (existing instanceof LiteralString) {
            ((LiteralString) existing).setValue(text);
            return;
        }
        // Create a new OpaqueExpression
        ElementsFactory ef = project.getElementsFactory();
        OpaqueExpression oe = ef.createOpaqueExpressionInstance();
        oe.getBody().add(text);
        c.setSpecification(oe);
    }

    // -----------------------------------------------------------------------
    //  Path extraction
    // -----------------------------------------------------------------------

    private String extractElementId(String path) {
        if (path == null || !path.startsWith(PREFIX)) {
            return null;
        }
        String remainder = path.substring(PREFIX.length());
        int slash = remainder.indexOf('/');
        if (slash > 0) {
            return remainder.substring(0, slash);
        }
        return null;
    }
}
