package com.claude.cameo.bridge.handlers;

import com.claude.cameo.bridge.HttpBridgeServer;
import com.claude.cameo.bridge.util.EdtDispatcher;
import com.claude.cameo.bridge.util.ElementSerializer;
import com.claude.cameo.bridge.util.JsonHelper;
import com.claude.cameo.bridge.util.TaggedValueCoercion;
import com.nomagic.magicdraw.openapi.uml.ModelElementsManager;
import com.nomagic.uml2.ext.magicdraw.classes.mdkernel.Comment;
import com.nomagic.uml2.ext.magicdraw.classes.mdkernel.Classifier;
import com.nomagic.uml2.ext.magicdraw.classes.mdkernel.Element;
import com.nomagic.uml2.ext.magicdraw.classes.mdkernel.LiteralInteger;
import com.nomagic.uml2.ext.magicdraw.classes.mdkernel.LiteralUnlimitedNatural;
import com.nomagic.uml2.ext.magicdraw.classes.mdkernel.MultiplicityElement;
import com.nomagic.uml2.ext.magicdraw.classes.mdkernel.NamedElement;
import com.nomagic.uml2.ext.magicdraw.classes.mdkernel.Package;
import com.nomagic.uml2.ext.magicdraw.classes.mdkernel.Property;
import com.nomagic.uml2.ext.magicdraw.classes.mdkernel.Type;
import com.nomagic.uml2.ext.magicdraw.classes.mdkernel.TypedElement;
import com.nomagic.uml2.ext.magicdraw.classes.mdkernel.AggregationKindEnum;
import com.nomagic.uml2.ext.magicdraw.compositestructures.mdports.Port;
import com.nomagic.uml2.ext.magicdraw.mdprofiles.Profile;
import com.nomagic.uml2.ext.magicdraw.mdprofiles.Stereotype;
import com.nomagic.uml2.ext.magicdraw.mdusecases.UseCase;
import com.nomagic.uml2.ext.jmi.helpers.StereotypesHelper;
import com.nomagic.uml2.ext.magicdraw.actions.mdbasicactions.CallBehaviorAction;
import com.nomagic.uml2.ext.magicdraw.commonbehaviors.mdbasicbehaviors.Behavior;
import com.nomagic.uml2.ext.magicdraw.activities.mdintermediateactivities.ActivityPartition;
import com.nomagic.uml2.ext.magicdraw.statemachines.mdbehaviorstatemachines.Pseudostate;
import com.nomagic.uml2.ext.magicdraw.statemachines.mdbehaviorstatemachines.PseudostateKindEnum;
import com.nomagic.uml2.ext.magicdraw.statemachines.mdbehaviorstatemachines.Region;
import com.nomagic.uml2.ext.magicdraw.statemachines.mdbehaviorstatemachines.State;
import com.nomagic.uml2.ext.magicdraw.statemachines.mdbehaviorstatemachines.StateMachine;
import com.nomagic.uml2.impl.ElementsFactory;
import com.sun.net.httpserver.HttpExchange;
import com.sun.net.httpserver.HttpHandler;
import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import com.google.gson.JsonPrimitive;

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
        String typeId = JsonHelper.optionalString(body, "typeId");
        Integer lower = optionalInteger(body, "lower");
        Integer upper = optionalUnlimitedInteger(body, "upper");
        Boolean isOrdered = optionalBoolean(body, "isOrdered");
        Boolean isUnique = optionalBoolean(body, "isUnique");
        String aggregation = JsonHelper.optionalString(body, "aggregation");
        Boolean isBehavior = optionalBoolean(body, "isBehavior");
        Boolean isConjugated = optionalBoolean(body, "isConjugated");
        Boolean isService = optionalBoolean(body, "isService");
        String direction = JsonHelper.optionalString(body, "direction");
        List<String> metaclasses = parseStringList(body, "metaclasses");

        JsonObject result = EdtDispatcher.write("Create " + type + " " + name, project -> {
            Element parent = (Element) project.getElementByID(parentId);
            if (parent == null) {
                throw new IllegalArgumentException("Parent element not found: " + parentId);
            }
            ElementsFactory ef = project.getElementsFactory();
            Element created = createElement(project, ef, parent, type, name, metaclasses);
            if (created instanceof StateMachine) {
                ModelElementsManager.getInstance().addElement(created, parent);
                ensureDefaultRegion(ef, (StateMachine) created);
            } else if (created instanceof State) {
                Region ownerRegion = resolveStateRegion(ef, parent, type);
                ((State) created).setContainer(ownerRegion);
            } else if (created instanceof Pseudostate) {
                Region ownerRegion = resolveStateRegion(ef, parent, type);
                ((Pseudostate) created).setContainer(ownerRegion);
                ((Pseudostate) created).setKind(PseudostateKindEnum.INITIAL);
            }
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
            for (String requestedStereotype : effectiveCreationStereotypes(type, stereotype)) {
                Stereotype stereo = findStereotype(project, requestedStereotype, null);
                if (stereo == null) {
                    throw new IllegalArgumentException("Stereotype not found: " + requestedStereotype);
                }
                if (!StereotypesHelper.hasStereotype(created, stereo)) {
                    StereotypesHelper.addStereotype(created, stereo);
                }
            }
            applyCreationSemantics(
                    project,
                    ef,
                    created,
                    typeId,
                    lower,
                    upper,
                    isOrdered,
                    isUnique,
                    aggregation,
                    isBehavior,
                    isConjugated,
                    isService,
                    direction);
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
                Object tagValue = TaggedValueCoercion.coerceForTag(
                        project,
                        stereo,
                        tagName,
                        values.get(tagName));
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
        if (!(created instanceof StateMachine) && !(created instanceof State) && !(created instanceof Pseudostate)) {
            ModelElementsManager.getInstance().addElement(created, parent);
        }
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
            case "statemachine":
            case "state-machine":
            case "state machine":
                return ef.createStateMachineInstance();
            case "state":         return ef.createStateInstance();
            case "pseudostate":
            case "initialstate":
            case "initial-state":
                return ef.createPseudostateInstance();
            case "requirement":   return ef.createClassInstance();
            case "interface-block":
            case "interfaceblock":
                return ef.createClassInstance();
            case "interface":
                return ef.createInterfaceInstance();
            case "constraint-block":
            case "constraintblock": return ef.createClassInstance();
            case "value-type":
            case "valuetype":
            case "datatype":      return ef.createDataTypeInstance();
            case "signal":        return ef.createSignalInstance();
            case "property":      return ef.createPropertyInstance();
            case "flow-property":
            case "flowproperty":
                return ef.createPropertyInstance();
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
                        + "statemachine, state, pseudostate, initial-state, requirement, interface-block, interface, "
                        + "constraint-block, value-type, datatype, signal, property, flow-property, operation, port, enumeration, component, "
                        + "constraint, comment, call-behavior-action, activity-partition, "
                        + "initial-node, activity-final, decision, merge, fork, join, "
                        + "flow-final, input-pin, output-pin, opaque-action, action");
        }
    }

    private Region resolveStateRegion(
            ElementsFactory ef,
            Element parent,
            String type) {
        if (parent instanceof Region) {
            return (Region) parent;
        }
        if (parent instanceof StateMachine) {
            return ensureDefaultRegion(ef, (StateMachine) parent);
        }
        if (parent instanceof State) {
            return ensureDefaultRegion(ef, (State) parent);
        }
        throw new IllegalArgumentException("Parent for " + type + " must be a Region, StateMachine, or State: "
                + parent.getID());
    }

    private Region ensureDefaultRegion(ElementsFactory ef, StateMachine stateMachine) {
        Collection<Region> regions = stateMachine.getRegion();
        if (regions != null && !regions.isEmpty()) {
            return regions.iterator().next();
        }
        Region region = ef.createRegionInstance();
        region.setStateMachine(stateMachine);
        return region;
    }

    private Region ensureDefaultRegion(ElementsFactory ef, State state) {
        Collection<Region> regions = state.getRegion();
        if (regions != null && !regions.isEmpty()) {
            return regions.iterator().next();
        }
        Region region = ef.createRegionInstance();
        region.setState(state);
        return region;
    }

    private List<String> effectiveCreationStereotypes(String type, String explicitStereotype) {
        List<String> stereotypes = new ArrayList<>();

        String defaultStereotype = defaultCreationStereotype(type);
        if (defaultStereotype != null) {
            stereotypes.add(defaultStereotype);
        }

        if (explicitStereotype != null && !explicitStereotype.isEmpty()) {
            boolean alreadyPresent = stereotypes.stream()
                    .anyMatch(existing -> existing.equalsIgnoreCase(explicitStereotype));
            if (!alreadyPresent) {
                stereotypes.add(explicitStereotype);
            }
        }

        return stereotypes;
    }

    private String defaultCreationStereotype(String type) {
        switch (type.toLowerCase()) {
            case "block":
                return "block";
            case "requirement":
                return "requirement";
            case "interface-block":
            case "interfaceblock":
                return "interfaceBlock";
            case "constraint-block":
            case "constraintblock":
                return "constraintBlock";
            case "value-type":
            case "valuetype":
                return "valueType";
            case "flow-property":
            case "flowproperty":
                return "flowProperty";
            default:
                return null;
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

    private Integer optionalInteger(JsonObject body, String key) {
        if (!body.has(key) || body.get(key).isJsonNull()) {
            return null;
        }
        try {
            return body.get(key).getAsInt();
        } catch (Exception e) {
            throw new IllegalArgumentException(key + " must be an integer");
        }
    }

    private Integer optionalUnlimitedInteger(JsonObject body, String key) {
        if (!body.has(key) || body.get(key).isJsonNull()) {
            return null;
        }
        JsonElement element = body.get(key);
        try {
            if (element.isJsonPrimitive() && element.getAsJsonPrimitive().isString()) {
                String text = element.getAsString().trim();
                if ("*".equals(text)) {
                    return -1;
                }
                return Integer.parseInt(text);
            }
            return element.getAsInt();
        } catch (Exception e) {
            throw new IllegalArgumentException(key + " must be an integer or '*'");
        }
    }

    private Boolean optionalBoolean(JsonObject body, String key) {
        if (!body.has(key) || body.get(key).isJsonNull()) {
            return null;
        }
        try {
            return body.get(key).getAsBoolean();
        } catch (Exception e) {
            throw new IllegalArgumentException(key + " must be a boolean");
        }
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

    private void applyCreationSemantics(
            com.nomagic.magicdraw.core.Project project,
            ElementsFactory ef,
            Element created,
            String typeId,
            Integer lower,
            Integer upper,
            Boolean isOrdered,
            Boolean isUnique,
            String aggregation,
            Boolean isBehavior,
            Boolean isConjugated,
            Boolean isService,
            String direction) {
        if (typeId != null) {
            applyCreatedType(project, created, typeId);
        }
        if (lower != null || upper != null || isOrdered != null || isUnique != null) {
            applyMultiplicity(project, ef, created, lower, upper, isOrdered, isUnique);
        }
        if (aggregation != null) {
            applyAggregation(created, aggregation);
        }
        if (isBehavior != null || isConjugated != null || isService != null) {
            applyPortFlags(created, isBehavior, isConjugated, isService);
        }
        if (direction != null) {
            applyFlowPropertyDirection(project, created, direction);
        }
    }

    private void applyCreatedType(
            com.nomagic.magicdraw.core.Project project,
            Element created,
            String typeId) {
        if (!(created instanceof TypedElement)) {
            throw new IllegalArgumentException(
                    "typeId is only supported for TypedElement instances: " + created.getHumanType());
        }
        Element resolved = (Element) project.getElementByID(typeId);
        if (!(resolved instanceof Type)) {
            throw new IllegalArgumentException("Type element not found or not a Type: " + typeId);
        }
        ((TypedElement) created).setType((Type) resolved);
    }

    private void applyMultiplicity(
            com.nomagic.magicdraw.core.Project project,
            ElementsFactory ef,
            Element created,
            Integer lower,
            Integer upper,
            Boolean isOrdered,
            Boolean isUnique) {
        if (!(created instanceof MultiplicityElement)) {
            throw new IllegalArgumentException(
                    "Multiplicity fields are only supported for MultiplicityElement instances: "
                            + created.getHumanType());
        }
        MultiplicityElement multiplicityElement = (MultiplicityElement) created;
        if (lower != null) {
            if (lower < 0) {
                throw new IllegalArgumentException("lower must be zero or greater");
            }
            LiteralInteger lowerValue = ef.createLiteralIntegerInstance();
            lowerValue.setValue(lower);
            multiplicityElement.setLowerValue(lowerValue);
        }
        if (upper != null) {
            if (upper < 0) {
                LiteralUnlimitedNatural upperValue = ef.createLiteralUnlimitedNaturalInstance();
                upperValue.setValue(-1);
                multiplicityElement.setUpperValue(upperValue);
            } else {
                LiteralUnlimitedNatural upperValue = ef.createLiteralUnlimitedNaturalInstance();
                upperValue.setValue(upper);
                multiplicityElement.setUpperValue(upperValue);
            }
        }
        if (isOrdered != null) {
            multiplicityElement.setOrdered(isOrdered);
        }
        if (isUnique != null) {
            multiplicityElement.setUnique(isUnique);
        }
    }

    private void applyAggregation(Element created, String aggregation) {
        if (!(created instanceof Property)) {
            throw new IllegalArgumentException(
                    "aggregation is only supported for Property instances: " + created.getHumanType());
        }
        AggregationKindEnum resolved = AggregationKindEnum.getByName(aggregation.toLowerCase());
        if (resolved == null) {
            resolved = AggregationKindEnum.get(aggregation.toLowerCase());
        }
        if (resolved == null) {
            throw new IllegalArgumentException(
                    "Unsupported aggregation value: " + aggregation + ". Expected none, shared, or composite.");
        }
        ((Property) created).setAggregation(resolved);
    }

    private void applyPortFlags(
            Element created,
            Boolean isBehavior,
            Boolean isConjugated,
            Boolean isService) {
        if (!(created instanceof Port)) {
            throw new IllegalArgumentException(
                    "Port flags are only supported for Port instances: " + created.getHumanType());
        }
        Port port = (Port) created;
        if (isBehavior != null) {
            port.setBehavior(isBehavior);
        }
        if (isConjugated != null) {
            port.setConjugated(isConjugated);
        }
        if (isService != null) {
            port.setService(isService);
        }
    }

    private void applyFlowPropertyDirection(
            com.nomagic.magicdraw.core.Project project,
            Element created,
            String direction) {
        if (!(created instanceof Property)) {
            throw new IllegalArgumentException(
                    "direction is only supported for Property / FlowProperty instances: "
                            + created.getHumanType());
        }
        Stereotype flowPropertyStereo = getFlowPropertyStereotype(created);
        if (flowPropertyStereo == null) {
            throw new IllegalArgumentException(
                    "direction requires the FlowProperty stereotype to be applied");
        }
        StereotypesHelper.setStereotypePropertyValue(
                created,
                flowPropertyStereo,
                "direction",
                TaggedValueCoercion.coerceForTag(
                        project,
                        flowPropertyStereo,
                        "direction",
                        new JsonPrimitive(direction)));
    }

    private Object coerceJsonValue(JsonElement value) {
        if (value == null || value.isJsonNull()) {
            return null;
        }
        if (value.isJsonArray()) {
            List<Object> coerced = new ArrayList<>();
            for (JsonElement item : value.getAsJsonArray()) {
                coerced.add(coerceJsonValue(item));
            }
            return coerced;
        }
        if (value.isJsonObject()) {
            return value.toString();
        }

        var primitive = value.getAsJsonPrimitive();
        if (primitive.isBoolean()) {
            return primitive.getAsBoolean();
        }
        if (primitive.isNumber()) {
            return primitive.getAsNumber();
        }
        return primitive.getAsString();
    }

    private Stereotype getFlowPropertyStereotype(Element element) {
        Stereotype applied = StereotypesHelper.getAppliedStereotypeByString(element, "FlowProperty");
        if (applied != null) {
            return applied;
        }
        return StereotypesHelper.getAppliedStereotypeByString(element, "flowProperty");
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
        List<Stereotype> matches = new ArrayList<>();
        Collection<Stereotype> allStereotypes = StereotypesHelper.getAllStereotypes(project);
        if (allStereotypes != null) {
            for (Stereotype st : allStereotypes) {
                if (stereotypeName.equalsIgnoreCase(st.getName())) {
                    matches.add(st);
                }
            }
        }
        if (matches.isEmpty()) {
            return null;
        }
        for (String preferredContext : preferredStereotypeContexts(stereotypeName)) {
            for (Stereotype stereotype : matches) {
                if (ownerChainContains(stereotype, preferredContext)) {
                    return stereotype;
                }
            }
        }
        return matches.get(0);
    }

    private List<String> preferredStereotypeContexts(String stereotypeName) {
        switch (stereotypeName.toLowerCase()) {
            case "refine":
            case "derivereqt":
            case "satisfy":
            case "verify":
            case "trace":
                return List.of("Requirements", "SysML", "SysML Profile");
            case "allocate":
            case "itemflow":
            case "flowproperty":
            case "block":
            case "requirement":
            case "interfaceblock":
            case "constraintblock":
            case "valuetype":
                return List.of("SysML", "SysML Profile", "Requirements");
            default:
                return List.of("SysML", "SysML Profile", "Requirements");
        }
    }

    private boolean ownerChainContains(Element element, String ownerName) {
        Element current = element;
        while (current != null) {
            if (current instanceof NamedElement) {
                String currentName = ((NamedElement) current).getName();
                if (currentName != null && ownerName.equalsIgnoreCase(currentName)) {
                    return true;
                }
            }
            current = current.getOwner();
        }
        return false;
    }

}
