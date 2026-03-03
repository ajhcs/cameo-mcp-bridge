package com.claude.cameo.bridge.handlers;

import com.claude.cameo.bridge.HttpBridgeServer;
import com.claude.cameo.bridge.util.EdtDispatcher;
import com.claude.cameo.bridge.util.ElementSerializer;
import com.claude.cameo.bridge.util.JsonHelper;
import com.nomagic.magicdraw.openapi.uml.ModelElementsManager;
import com.nomagic.uml2.ext.magicdraw.activities.mdbasicactivities.ActivityEdge;
import com.nomagic.uml2.ext.magicdraw.activities.mdbasicactivities.ControlFlow;
import com.nomagic.uml2.ext.magicdraw.activities.mdbasicactivities.ObjectFlow;
import com.nomagic.uml2.ext.magicdraw.activities.mdfundamentalactivities.ActivityNode;
import com.nomagic.uml2.ext.magicdraw.classes.mddependencies.Abstraction;
import com.nomagic.uml2.ext.magicdraw.classes.mddependencies.Dependency;
import com.nomagic.uml2.ext.magicdraw.classes.mdkernel.AggregationKindEnum;
import com.nomagic.uml2.ext.magicdraw.classes.mdkernel.Association;
import com.nomagic.uml2.ext.magicdraw.classes.mdkernel.Classifier;
import com.nomagic.uml2.ext.magicdraw.classes.mdkernel.Element;
import com.nomagic.uml2.ext.magicdraw.classes.mdkernel.Generalization;
import com.nomagic.uml2.ext.magicdraw.classes.mdkernel.LiteralString;
import com.nomagic.uml2.ext.magicdraw.classes.mdkernel.NamedElement;
import com.nomagic.uml2.ext.magicdraw.classes.mdkernel.Property;
import com.nomagic.uml2.ext.magicdraw.classes.mdkernel.Type;
import com.nomagic.uml2.ext.magicdraw.mdprofiles.Stereotype;
import com.nomagic.uml2.ext.magicdraw.mdusecases.Extend;
import com.nomagic.uml2.ext.magicdraw.mdusecases.Include;
import com.nomagic.uml2.ext.magicdraw.mdusecases.UseCase;
import com.nomagic.uml2.ext.jmi.helpers.StereotypesHelper;
import com.nomagic.uml2.impl.ElementsFactory;
import com.sun.net.httpserver.HttpExchange;
import com.sun.net.httpserver.HttpHandler;
import com.google.gson.JsonObject;

import java.io.IOException;
import java.util.Collection;
import java.util.List;
import java.util.logging.Level;
import java.util.logging.Logger;

/**
 * Handles relationship creation REST endpoint.
 * POST /api/v1/relationships
 * Body: {type, sourceId, targetId, name?, guard?}
 */
public class RelationshipHandler implements HttpHandler {

    private static final Logger LOG = Logger.getLogger(RelationshipHandler.class.getName());

    @Override
    public void handle(HttpExchange exchange) throws IOException {
        try {
            String method = exchange.getRequestMethod();
            if ("OPTIONS".equals(method)) {
                exchange.getResponseHeaders().set("Access-Control-Allow-Methods", "POST, OPTIONS");
                exchange.getResponseHeaders().set("Access-Control-Allow-Headers", "Content-Type");
                exchange.sendResponseHeaders(204, -1);
                return;
            }
            if (!"POST".equals(method)) {
                HttpBridgeServer.sendError(exchange, 405, "METHOD_NOT_ALLOWED", "Only POST is supported");
                return;
            }
            handleCreateRelationship(exchange);
        } catch (IllegalArgumentException e) {
            HttpBridgeServer.sendError(exchange, 400, "BAD_REQUEST", e.getMessage());
        } catch (Exception e) {
            LOG.log(Level.SEVERE, "Error in RelationshipHandler", e);
            HttpBridgeServer.sendError(exchange, 500, "INTERNAL_ERROR", e.getMessage());
        }
    }

    private void handleCreateRelationship(HttpExchange exchange) throws Exception {
        JsonObject body = JsonHelper.parseBody(exchange);
        String type = JsonHelper.requireString(body, "type");
        String sourceId = JsonHelper.requireString(body, "sourceId");
        String targetId = JsonHelper.requireString(body, "targetId");
        String name = JsonHelper.optionalString(body, "name");
        String guard = JsonHelper.optionalString(body, "guard");

        JsonObject result = EdtDispatcher.write("Create " + type + " relationship", project -> {
            Element source = (Element) project.getElementByID(sourceId);
            if (source == null) {
                throw new IllegalArgumentException("Source element not found: " + sourceId);
            }
            Element target = (Element) project.getElementByID(targetId);
            if (target == null) {
                throw new IllegalArgumentException("Target element not found: " + targetId);
            }

            ElementsFactory ef = project.getElementsFactory();
            Element relationship;

            switch (type.toLowerCase()) {
                case "generalization":
                    relationship = createGeneralization(ef, source, target);
                    break;
                case "include":
                    relationship = createInclude(ef, source, target);
                    break;
                case "extend":
                    relationship = createExtend(ef, source, target);
                    break;
                case "dependency":
                    relationship = createDependency(ef, source, target);
                    break;
                case "association":
                    relationship = createAssociation(ef, source, target, false, false);
                    break;
                case "directed-association":
                case "directedassociation":
                    relationship = createAssociation(ef, source, target, true, false);
                    break;
                case "composition":
                    relationship = createAssociation(ef, source, target, true, true);
                    break;
                case "control-flow":
                case "controlflow":
                    relationship = createControlFlow(ef, project, source, target, guard);
                    break;
                case "object-flow":
                case "objectflow":
                    relationship = createObjectFlow(ef, project, source, target, guard);
                    break;
                case "allocate":
                    relationship = createStereotypedAbstraction(ef, project, source, target, "Allocate");
                    break;
                case "satisfy":
                    relationship = createStereotypedAbstraction(ef, project, source, target, "Satisfy");
                    break;
                case "derive":
                    relationship = createStereotypedAbstraction(ef, project, source, target, "DeriveReqt");
                    break;
                case "refine":
                    relationship = createStereotypedAbstraction(ef, project, source, target, "Refine");
                    break;
                case "trace":
                    relationship = createStereotypedAbstraction(ef, project, source, target, "Trace");
                    break;
                default:
                    throw new IllegalArgumentException("Unsupported relationship type: " + type
                            + ". Supported: association, directed-association, generalization, "
                            + "include, extend, dependency, control-flow, object-flow, "
                            + "composition, allocate, satisfy, derive, refine, trace");
            }

            if (name != null && relationship instanceof NamedElement) {
                ((NamedElement) relationship).setName(name);
            }

            JsonObject response = new JsonObject();
            response.addProperty("created", true);
            response.addProperty("relationshipType", type);
            response.add("relationship", ElementSerializer.toJson(relationship));
            return response;
        });
        HttpBridgeServer.sendJson(exchange, 201, result);
    }

    private Generalization createGeneralization(ElementsFactory ef, Element source, Element target) throws Exception {
        if (!(source instanceof Classifier) || !(target instanceof Classifier)) {
            throw new IllegalArgumentException("Generalization requires Classifier source and target");
        }
        Generalization gen = ef.createGeneralizationInstance();
        gen.setSpecific((Classifier) source);
        gen.setGeneral((Classifier) target);
        ModelElementsManager.getInstance().addElement(gen, source);
        return gen;
    }

    private Include createInclude(ElementsFactory ef, Element source, Element target) throws Exception {
        if (!(source instanceof UseCase) || !(target instanceof UseCase)) {
            throw new IllegalArgumentException("Include requires UseCase source and target");
        }
        Include inc = ef.createIncludeInstance();
        inc.setIncludingCase((UseCase) source);
        inc.setAddition((UseCase) target);
        ModelElementsManager.getInstance().addElement(inc, source);
        return inc;
    }

    private Extend createExtend(ElementsFactory ef, Element source, Element target) throws Exception {
        if (!(source instanceof UseCase) || !(target instanceof UseCase)) {
            throw new IllegalArgumentException("Extend requires UseCase source and target");
        }
        Extend ext = ef.createExtendInstance();
        ext.setExtension((UseCase) source);
        ext.setExtendedCase((UseCase) target);
        ModelElementsManager.getInstance().addElement(ext, source);
        return ext;
    }

    private Dependency createDependency(ElementsFactory ef, Element source, Element target) throws Exception {
        if (!(source instanceof NamedElement) || !(target instanceof NamedElement)) {
            throw new IllegalArgumentException("Dependency requires NamedElement source and target");
        }
        Dependency dep = ef.createDependencyInstance();
        dep.getClient().add((NamedElement) source);
        dep.getSupplier().add((NamedElement) target);
        ModelElementsManager.getInstance().addElement(dep, source);
        return dep;
    }

    private Association createAssociation(ElementsFactory ef, Element source, Element target,
            boolean directed, boolean composition) throws Exception {
        if (!(source instanceof Type) || !(target instanceof Type)) {
            throw new IllegalArgumentException("Association requires Type source and target");
        }
        Association assoc = ef.createAssociationInstance();

        // The factory pre-creates two owned ends - use them directly
        Property sourceEnd = (Property) assoc.getOwnedEnd().get(0);
        sourceEnd.setType((Type) source);
        Property targetEnd = (Property) assoc.getOwnedEnd().get(1);
        targetEnd.setType((Type) target);

        if (composition) {
            sourceEnd.setAggregation(AggregationKindEnum.COMPOSITE);
        }

        // For directed association, make target end navigable
        if (directed) {
            targetEnd.setAssociation(assoc);
        }

        // Set owner to source's package so the association persists
        Element owner = source.getOwner();
        if (owner != null) {
            ModelElementsManager.getInstance().addElement(assoc, owner);
        }
        return assoc;
    }

    private ControlFlow createControlFlow(ElementsFactory ef,
            com.nomagic.magicdraw.core.Project project,
            Element source, Element target, String guard) throws Exception {
        if (!(source instanceof ActivityNode) || !(target instanceof ActivityNode)) {
            throw new IllegalArgumentException("ControlFlow requires ActivityNode source and target");
        }
        ControlFlow flow = ef.createControlFlowInstance();
        flow.setSource((ActivityNode) source);
        flow.setTarget((ActivityNode) target);
        if (guard != null && !guard.isEmpty()) {
            LiteralString guardSpec = ef.createLiteralStringInstance();
            guardSpec.setValue(guard);
            flow.setGuard(guardSpec);
        }
        Element owner = source.getOwner();
        if (owner != null) {
            ModelElementsManager.getInstance().addElement(flow, owner);
        }
        return flow;
    }

    private ObjectFlow createObjectFlow(ElementsFactory ef,
            com.nomagic.magicdraw.core.Project project,
            Element source, Element target, String guard) throws Exception {
        if (!(source instanceof ActivityNode) || !(target instanceof ActivityNode)) {
            throw new IllegalArgumentException("ObjectFlow requires ActivityNode source and target");
        }
        ObjectFlow flow = ef.createObjectFlowInstance();
        flow.setSource((ActivityNode) source);
        flow.setTarget((ActivityNode) target);
        if (guard != null && !guard.isEmpty()) {
            LiteralString guardSpec = ef.createLiteralStringInstance();
            guardSpec.setValue(guard);
            flow.setGuard(guardSpec);
        }
        Element owner = source.getOwner();
        if (owner != null) {
            ModelElementsManager.getInstance().addElement(flow, owner);
        }
        return flow;
    }

    private Abstraction createStereotypedAbstraction(ElementsFactory ef,
            com.nomagic.magicdraw.core.Project project,
            Element source, Element target, String stereotypeName) throws Exception {
        if (!(source instanceof NamedElement) || !(target instanceof NamedElement)) {
            throw new IllegalArgumentException(
                    stereotypeName + " requires NamedElement source and target");
        }
        Abstraction abstraction = ef.createAbstractionInstance();
        abstraction.getClient().add((NamedElement) source);
        abstraction.getSupplier().add((NamedElement) target);

        // Find and apply the SysML stereotype
        Collection<Stereotype> allStereotypes = StereotypesHelper.getAllStereotypes(project);
        Stereotype stereo = null;
        if (allStereotypes != null) {
            for (Stereotype st : allStereotypes) {
                if (stereotypeName.equalsIgnoreCase(st.getName())) {
                    stereo = st;
                    break;
                }
            }
        }
        if (stereo != null) {
            StereotypesHelper.addStereotype(abstraction, stereo);
        } else {
            throw new IllegalStateException("SysML stereotype not found: " + stereotypeName
                    + ". Ensure the SysML profile is applied to the project.");
        }

        Element owner = source.getOwner();
        if (owner != null) {
            ModelElementsManager.getInstance().addElement(abstraction, owner);
        }
        return abstraction;
    }

}
