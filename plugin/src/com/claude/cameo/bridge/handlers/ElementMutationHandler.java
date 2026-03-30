package com.claude.cameo.bridge.handlers;

import com.claude.cameo.bridge.HttpBridgeServer;
import com.claude.cameo.bridge.util.EdtDispatcher;
import com.claude.cameo.bridge.util.ElementSerializer;
import com.claude.cameo.bridge.util.JsonHelper;
import com.nomagic.magicdraw.openapi.uml.ModelElementsManager;
import com.nomagic.uml2.ext.magicdraw.classes.mdkernel.Comment;
import com.nomagic.uml2.ext.magicdraw.classes.mdkernel.Element;
import com.nomagic.uml2.ext.magicdraw.classes.mdkernel.Classifier;
import com.nomagic.uml2.ext.magicdraw.classes.mdkernel.NamedElement;
import com.nomagic.uml2.ext.magicdraw.classes.mdkernel.Package;
import com.nomagic.uml2.ext.magicdraw.mdprofiles.Profile;
import com.nomagic.uml2.ext.magicdraw.mdprofiles.Stereotype;
import com.nomagic.uml2.ext.magicdraw.mdusecases.UseCase;
import com.nomagic.uml2.ext.jmi.helpers.StereotypesHelper;
import com.nomagic.uml2.ext.magicdraw.actions.mdbasicactions.CallBehaviorAction;
import com.nomagic.uml2.ext.magicdraw.commonbehaviors.mdbasicbehaviors.Behavior;
import com.nomagic.uml2.ext.magicdraw.activities.mdintermediateactivities.ActivityPartition;
import com.nomagic.uml2.impl.ElementsFactory;
import com.sun.net.httpserver.HttpExchange;
import com.sun.net.httpserver.HttpHandler;
import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;

import java.io.IOException;
import java.util.ArrayList;
import java.util.Collection;
import java.util.Collections;
import java.util.List;
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
            if ("POST".equals(method) && "apply-profile".equals(subPath)) { handleApplyProfile(exchange, elementId); return; }
            if ("PUT".equals(method) && "metaclasses".equals(subPath)) { handleSetMetaclasses(exchange, elementId); return; }
            if ("PUT".equals(method) && "tagged-values".equals(subPath)) { handleSetTaggedValues(exchange, elementId); return; }
            if ("PUT".equals(method) && "usecase-subject".equals(subPath)) { handleSetUseCaseSubject(exchange, elementId); return; }
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
        String type = JsonHelper.requireString(body, "type");
        String name = JsonHelper.requireString(body, "name");
        String parentId = JsonHelper.requireString(body, "parentId");
        String stereotype = JsonHelper.optionalString(body, "stereotype");
        String documentation = JsonHelper.optionalString(body, "documentation");
        String behaviorId = JsonHelper.optionalString(body, "behaviorId");
        String representsId = JsonHelper.optionalString(body, "representsId");
        List<String> metaclasses = parseStringList(body, "metaclasses");

        JsonObject result = EdtDispatcher.write("Create " + type + " " + name, project -> {
            Element parent = (Element) project.getElementByID(parentId);
            if (parent == null) {
                throw new IllegalArgumentException("Parent element not found: " + parentId);
            }
            ElementsFactory ef = project.getElementsFactory();
            Element created = createElement(project, ef, parent, type, name, metaclasses);
            if (behaviorId != null && created instanceof CallBehaviorAction) {
                Element behavior = (Element) project.getElementByID(behaviorId);
                if (behavior instanceof Behavior) {
                    ((CallBehaviorAction) created).setBehavior((Behavior) behavior);
                }
            }
            if (representsId != null && created instanceof ActivityPartition) {
                Element represents = (Element) project.getElementByID(representsId);
                if (represents != null) {
                    ((ActivityPartition) created).setRepresents(represents);
                }
            }
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

    private void handleSetMetaclasses(HttpExchange exchange, String elementId) throws Exception {
        JsonObject body = JsonHelper.parseBody(exchange);
        List<String> metaclasses = parseStringList(body, "metaclasses");
        if (metaclasses == null || metaclasses.isEmpty()) {
            HttpBridgeServer.sendError(exchange, 400, "BAD_REQUEST",
                    "metaclasses must be a non-empty array of strings");
            return;
        }

        JsonObject result = EdtDispatcher.write("Set metaclasses for " + elementId, project -> {
            Element element = (Element) project.getElementByID(elementId);
            if (!(element instanceof Stereotype)) {
                throw new IllegalArgumentException("Element is not a stereotype: " + elementId);
            }

            Stereotype stereotype = (Stereotype) element;
            StereotypesHelper.setBaseClassesByName(stereotype, metaclasses);

            JsonObject response = new JsonObject();
            response.addProperty("updated", true);
            response.addProperty("stereotypeId", stereotype.getID());
            response.addProperty("stereotypeName",
                    stereotype.getName() != null ? stereotype.getName() : "");
            response.add("metaclasses", toJsonArray(StereotypesHelper.getBaseClasses(stereotype)));
            response.add("element", ElementSerializer.toJson(stereotype));
            return response;
        });
        HttpBridgeServer.sendJson(exchange, 200, result);
    }

    private void handleApplyProfile(HttpExchange exchange, String elementId) throws Exception {
        JsonObject body = JsonHelper.parseBody(exchange);
        String profileId = JsonHelper.optionalString(body, "profileId");
        String profileName = JsonHelper.optionalString(body, "profileName");
        if (profileId == null && profileName == null) {
            HttpBridgeServer.sendError(exchange, 400, "BAD_REQUEST",
                    "profileId or profileName is required");
            return;
        }

        JsonObject result = EdtDispatcher.write("Apply profile to " + elementId, project -> {
            Element element = (Element) project.getElementByID(elementId);
            if (!(element instanceof Package)) {
                throw new IllegalArgumentException("Element is not a package/model: " + elementId);
            }

            Profile profile = resolveProfile(project, profileId, profileName);
            Package pkg = (Package) element;

            JsonObject response = new JsonObject();
            response.addProperty("packageId", pkg.getID());
            response.addProperty("packageName", pkg.getName() != null ? pkg.getName() : "");
            response.addProperty("profileId", profile.getID());
            response.addProperty("profileName", profile.getName() != null ? profile.getName() : "");

            Collection<Profile> appliedProfiles = StereotypesHelper.getAppliedProfiles(pkg);
            boolean alreadyApplied = appliedProfiles != null && appliedProfiles.contains(profile);
            if (!alreadyApplied) {
                if (!StereotypesHelper.canApplyProfile(pkg, profile)) {
                    throw new IllegalStateException(
                            "Profile cannot be applied to package: " + profile.getName());
                }
                StereotypesHelper.applyProfile(pkg, profile);
                appliedProfiles = StereotypesHelper.getAppliedProfiles(pkg);
            }

            response.addProperty("applied", !alreadyApplied);
            response.addProperty("alreadyApplied", alreadyApplied);
            response.add("appliedProfiles", toProfileNameArray(appliedProfiles));
            return response;
        });
        HttpBridgeServer.sendJson(exchange, 200, result);
    }

    private void handleModifyElement(HttpExchange exchange, String elementId) throws Exception {
        JsonObject body = JsonHelper.parseBody(exchange);
        String newName = JsonHelper.optionalString(body, "name");
        String newDoc = JsonHelper.optionalString(body, "documentation");
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
        String stereotypeName = JsonHelper.requireString(body, "stereotype");
        String profileName = JsonHelper.optionalString(body, "profile");

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
        String stereotypeName = JsonHelper.requireString(body, "stereotype");
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

    private void handleSetUseCaseSubject(HttpExchange exchange, String elementId) throws Exception {
        JsonObject body = JsonHelper.parseBody(exchange);
        List<String> subjectIds = parseStringList(body, "subjectIds");
        boolean append = body.has("append") && body.get("append").getAsBoolean();
        if (subjectIds == null || subjectIds.isEmpty()) {
            HttpBridgeServer.sendError(exchange, 400, "BAD_REQUEST",
                    "subjectIds must be a non-empty array of classifier IDs");
            return;
        }

        JsonObject result = EdtDispatcher.write("Set UseCase subject on " + elementId, project -> {
            Element element = (Element) project.getElementByID(elementId);
            if (!(element instanceof UseCase)) {
                throw new IllegalArgumentException("Element is not a UseCase: " + elementId);
            }

            UseCase useCase = (UseCase) element;
            Collection<Classifier> subjects = useCase.getSubject();
            if (!append) {
                subjects.clear();
            }

            JsonArray subjectArray = new JsonArray();
            for (String subjectId : subjectIds) {
                Element subjectElement = (Element) project.getElementByID(subjectId);
                if (!(subjectElement instanceof Classifier)) {
                    throw new IllegalArgumentException(
                            "Subject element is not a Classifier: " + subjectId);
                }
                Classifier classifier = (Classifier) subjectElement;
                if (!subjects.contains(classifier)) {
                    subjects.add(classifier);
                }
                JsonObject subjectJson = new JsonObject();
                subjectJson.addProperty("id", classifier.getID());
                if (classifier instanceof NamedElement) {
                    subjectJson.addProperty("name", ((NamedElement) classifier).getName());
                }
                subjectArray.add(subjectJson);
            }

            JsonObject response = new JsonObject();
            response.addProperty("updated", true);
            response.addProperty("elementId", useCase.getID());
            response.addProperty("append", append);
            response.addProperty("subjectCount", subjects.size());
            response.add("subjects", subjectArray);
            response.add("element", ElementSerializer.toJson(useCase));
            return response;
        });
        HttpBridgeServer.sendJson(exchange, 200, result);
    }

    private Element createElement(
            com.nomagic.magicdraw.core.Project project,
            ElementsFactory ef,
            Element parent,
            String type,
            String name,
            List<String> metaclasses) throws Exception {
        if ("stereotype".equalsIgnoreCase(type)) {
            if (!(parent instanceof Profile)) {
                throw new IllegalArgumentException(
                        "Stereotype parent must be a Profile: " + parent.getID());
            }
            Collection<com.nomagic.uml2.ext.magicdraw.classes.mdkernel.Class> baseClasses =
                    resolveMetaclasses(project, metaclasses);
            Stereotype created = StereotypesHelper.createStereotype(
                    (Profile) parent, name, baseClasses);
            if (created == null) {
                throw new IllegalStateException("Failed to create stereotype: " + name);
            }
            return created;
        }

        Element created = createElementByType(ef, type);
        if (created instanceof NamedElement) {
            ((NamedElement) created).setName(name);
        }
        ModelElementsManager.getInstance().addElement(created, parent);
        return created;
    }

    private Element createElementByType(ElementsFactory ef, String type) {
        switch (type.toLowerCase()) {
            case "package":       return ef.createPackageInstance();
            case "profile":       return ef.createProfileInstance();
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
            case "callbehavioraction":
            case "call-behavior-action": return ef.createCallBehaviorActionInstance();
            case "activitypartition":
            case "activity-partition":
            case "partition":         return ef.createActivityPartitionInstance();
            case "initialnode":
            case "initial-node":      return ef.createInitialNodeInstance();
            case "activityfinalnode":
            case "activity-final":
            case "finalnode":
            case "final-node":        return ef.createActivityFinalNodeInstance();
            case "decisionnode":
            case "decision-node":
            case "decision":          return ef.createDecisionNodeInstance();
            case "mergenode":
            case "merge-node":
            case "merge":             return ef.createMergeNodeInstance();
            case "forknode":
            case "fork-node":
            case "fork":              return ef.createForkNodeInstance();
            case "joinnode":
            case "join-node":
            case "join":              return ef.createJoinNodeInstance();
            case "flowfinalnode":
            case "flow-final":        return ef.createFlowFinalNodeInstance();
            case "inputpin":
            case "input-pin":         return ef.createInputPinInstance();
            case "outputpin":
            case "output-pin":        return ef.createOutputPinInstance();
            case "opaqueaction":
            case "opaque-action":     return ef.createOpaqueActionInstance();
            case "action":            return ef.createCallBehaviorActionInstance();
            default:
                throw new IllegalArgumentException("Unsupported element type: " + type
                        + ". Supported: package, profile, stereotype, block, class, use-case, activity, actor, "
                        + "requirement, interface-block, constraint-block, value-type, "
                        + "signal, property, operation, port, enumeration, component, "
                        + "constraint, comment, call-behavior-action, activity-partition, "
                        + "initial-node, activity-final, decision, merge, fork, join, "
                        + "flow-final, input-pin, output-pin, opaque-action, action");
        }
    }

    private List<String> parseStringList(JsonObject body, String key) {
        if (!body.has(key) || body.get(key).isJsonNull()) {
            return null;
        }
        if (!body.get(key).isJsonArray()) {
            throw new IllegalArgumentException(key + " must be an array of strings");
        }

        List<String> values = new ArrayList<>();
        JsonArray array = body.getAsJsonArray(key);
        for (JsonElement item : array) {
            if (!item.isJsonPrimitive() || !item.getAsJsonPrimitive().isString()) {
                throw new IllegalArgumentException(key + " must contain only strings");
            }
            values.add(item.getAsString());
        }
        return values;
    }

    private Collection<com.nomagic.uml2.ext.magicdraw.classes.mdkernel.Class> resolveMetaclasses(
            com.nomagic.magicdraw.core.Project project,
            List<String> metaclasses) {
        if (metaclasses == null || metaclasses.isEmpty()) {
            return Collections.emptyList();
        }

        List<com.nomagic.uml2.ext.magicdraw.classes.mdkernel.Class> resolved =
                new ArrayList<>(metaclasses.size());
        for (String metaclassName : metaclasses) {
            com.nomagic.uml2.ext.magicdraw.classes.mdkernel.Class metaClass =
                    StereotypesHelper.getMetaClassByName(project, metaclassName);
            if (metaClass == null) {
                throw new IllegalArgumentException("Metaclass not found: " + metaclassName);
            }
            resolved.add(metaClass);
        }
        return resolved;
    }

    private JsonArray toJsonArray(
            Collection<com.nomagic.uml2.ext.magicdraw.classes.mdkernel.Class> metaclasses) {
        JsonArray array = new JsonArray();
        if (metaclasses == null) {
            return array;
        }
        for (com.nomagic.uml2.ext.magicdraw.classes.mdkernel.Class metaClass : metaclasses) {
            if (metaClass != null && metaClass.getName() != null) {
                array.add(metaClass.getName());
            }
        }
        return array;
    }

    private JsonArray toProfileNameArray(Collection<Profile> profiles) {
        JsonArray array = new JsonArray();
        if (profiles == null) {
            return array;
        }
        for (Profile profile : profiles) {
            if (profile != null && profile.getName() != null) {
                array.add(profile.getName());
            }
        }
        return array;
    }

    private Profile resolveProfile(
            com.nomagic.magicdraw.core.Project project,
            String profileId,
            String profileName) {
        Profile profile = null;
        if (profileId != null) {
            Element profileElement = (Element) project.getElementByID(profileId);
            if (!(profileElement instanceof Profile)) {
                throw new IllegalArgumentException("Profile not found: " + profileId);
            }
            profile = (Profile) profileElement;
        } else if (profileName != null) {
            profile = StereotypesHelper.getProfile(project, profileName);
            if (profile == null) {
                throw new IllegalArgumentException("Profile not found: " + profileName);
            }
        }
        return profile;
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

}
