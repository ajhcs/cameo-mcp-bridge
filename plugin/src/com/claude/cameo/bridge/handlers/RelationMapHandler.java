package com.claude.cameo.bridge.handlers;

import com.claude.cameo.bridge.HttpBridgeServer;
import com.claude.cameo.bridge.util.EdtDispatcher;
import com.claude.cameo.bridge.util.ElementSerializer;
import com.claude.cameo.bridge.util.JsonHelper;
import com.claude.cameo.bridge.util.PresentationSerializer;
import com.claude.cameo.bridge.util.PropertySerializer;
import com.claude.cameo.bridge.util.JsonDiff;
import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import com.nomagic.magicdraw.core.Project;
import com.nomagic.magicdraw.export.image.ImageExporter;
import com.nomagic.magicdraw.openapi.uml.ModelElementsManager;
import com.nomagic.magicdraw.uml.ClassTypes;
import com.nomagic.magicdraw.uml2.Connectors;
import com.nomagic.magicdraw.uml.symbols.DiagramPresentationElement;
import com.nomagic.magicdraw.uml.symbols.PresentationElement;
import com.nomagic.magicdraw.expressions.specification.CallExpressionSpecification;
import com.nomagic.magicdraw.expressions.specification.DSLRelationExpressionSpecification;
import com.nomagic.magicdraw.expressions.specification.Direction;
import com.nomagic.magicdraw.expressions.specification.ExpressionSpecificationUtil;
import com.nomagic.magicdraw.visualization.relationshipmap.GraphUtils;
import com.nomagic.magicdraw.visualization.relationshipmap.RelationMapManager;
import com.nomagic.magicdraw.visualization.relationshipmap.RelationshipMapUtilities;
import com.nomagic.magicdraw.visualization.relationshipmap.model.settings.GraphSettings;
import com.nomagic.uml2.ext.magicdraw.activities.mdbasicactivities.ActivityEdge;
import com.nomagic.uml2.ext.magicdraw.activities.mdfundamentalactivities.ActivityNode;
import com.nomagic.uml2.ext.magicdraw.compositestructures.mdinternalstructures.ConnectableElement;
import com.nomagic.uml2.ext.magicdraw.compositestructures.mdinternalstructures.Connector;
import com.nomagic.uml2.ext.magicdraw.compositestructures.mdinternalstructures.ConnectorEnd;
import com.nomagic.uml2.ext.magicdraw.classes.mdkernel.DirectedRelationship;
import com.nomagic.uml2.ext.magicdraw.classes.mdkernel.Diagram;
import com.nomagic.uml2.ext.magicdraw.classes.mdkernel.Element;
import com.nomagic.uml2.ext.magicdraw.classes.mdkernel.NamedElement;
import com.nomagic.uml2.ext.magicdraw.classes.mdkernel.Namespace;
import com.nomagic.uml2.ext.magicdraw.classes.mdkernel.Relationship;
import com.nomagic.uml2.ext.magicdraw.mdprofiles.Stereotype;
import com.nomagic.uml2.ext.jmi.helpers.StereotypesHelper;
import com.sun.net.httpserver.HttpExchange;
import com.sun.net.httpserver.HttpHandler;

import javax.imageio.ImageIO;
import java.awt.image.BufferedImage;
import java.io.ByteArrayOutputStream;
import java.lang.reflect.Method;
import java.io.IOException;
import java.util.Base64;
import java.util.ArrayList;
import java.util.ArrayDeque;
import java.util.Collection;
import java.util.HashSet;
import java.util.Locale;
import java.util.List;
import java.util.Queue;
import java.util.Set;
import java.util.LinkedHashMap;
import java.util.Map;

/**
 * Handles native Relation Map artifacts.
 */
public class RelationMapHandler implements HttpHandler {

    private static final String PREFIX = "/api/v1/relation-maps/";
    private static final String RELATION_MAP_TYPE = "Relation Map Diagram";
    private static final Map<String, CriteriaTemplate> CRITERIA_TEMPLATES = buildCriteriaTemplates();

    @Override
    public void handle(HttpExchange exchange) throws IOException {
        try {
            String method = exchange.getRequestMethod();
            String path = exchange.getRequestURI().getPath();

            if ("OPTIONS".equals(method)) {
                exchange.getResponseHeaders().set("Access-Control-Allow-Methods",
                        "GET, POST, PUT, OPTIONS");
                exchange.getResponseHeaders().set("Access-Control-Allow-Headers", "Content-Type");
                exchange.sendResponseHeaders(204, -1);
                return;
            }

            if ("GET".equals(method) && path.equals("/api/v1/relation-maps")) {
                handleList(exchange);
                return;
            }
            if ("GET".equals(method) && path.equals("/api/v1/relation-maps/criteria/templates")) {
                handleCriteriaTemplates(exchange);
                return;
            }
            if ("POST".equals(method) && path.equals("/api/v1/relation-maps")) {
                handleCreate(exchange);
                return;
            }
            if ("POST".equals(method) && path.equals("/api/v1/relation-maps/compare")) {
                handleCompare(exchange);
                return;
            }
            if ("POST".equals(method) && path.equals("/api/v1/relation-maps/traceability-graph")) {
                handleTraceabilityGraph(exchange);
                return;
            }

            String relationMapId = JsonHelper.extractPathParam(exchange, PREFIX);
            String subPath = JsonHelper.extractSubPath(exchange, PREFIX);
            if (relationMapId == null) {
                HttpBridgeServer.sendError(exchange, 404, "NOT_FOUND", "Unknown endpoint: " + path);
                return;
            }

            if ("GET".equals(method) && subPath == null) {
                handleGet(exchange, relationMapId);
            } else if ("GET".equals(method) && "settings/raw".equals(subPath)) {
                handleRawSettings(exchange, relationMapId);
            } else if ("GET".equals(method) && "presentations".equals(subPath)) {
                handlePresentations(exchange, relationMapId);
            } else if ("PUT".equals(method) && "criteria".equals(subPath)) {
                handleSetCriteria(exchange, relationMapId);
            } else if ("PUT".equals(method) && "settings".equals(subPath)) {
                handleConfigure(exchange, relationMapId);
            } else if ("POST".equals(method) && "expand".equals(subPath)) {
                handleExpandCollapse(exchange, relationMapId, true);
            } else if ("POST".equals(method) && "collapse".equals(subPath)) {
                handleExpandCollapse(exchange, relationMapId, false);
            } else if ("POST".equals(method) && "render".equals(subPath)) {
                handleRender(exchange, relationMapId);
            } else if ("POST".equals(method) && "verify".equals(subPath)) {
                handleVerify(exchange, relationMapId);
            } else if ("POST".equals(method) && "refresh".equals(subPath)) {
                handleRefresh(exchange, relationMapId);
            } else if ("POST".equals(method) && "graph".equals(subPath)) {
                handleRelationMapGraph(exchange, relationMapId);
            } else {
                HttpBridgeServer.sendError(exchange, 404, "NOT_FOUND", "Unknown endpoint: " + path);
            }
        } catch (IllegalArgumentException e) {
            HttpBridgeServer.sendError(exchange, 400, "RELATION_MAP_BAD_REQUEST", e.getMessage());
        } catch (Exception e) {
            HttpBridgeServer.sendError(exchange, 500, "RELATION_MAP_ERROR", describeException(e));
        }
    }

    private void handleList(HttpExchange exchange) throws Exception {
        JsonObject result = EdtDispatcher.read(project -> {
            JsonArray maps = new JsonArray();
            Collection<DiagramPresentationElement> diagrams = project.getDiagrams();
            if (diagrams != null) {
                for (DiagramPresentationElement dpe : diagrams) {
                    if (isRelationMap(dpe)) {
                        maps.add(toSummaryJson(dpe));
                    }
                }
            }
            JsonObject response = new JsonObject();
            response.addProperty("count", maps.size());
            response.add("relationMaps", maps);
            return response;
        });
        HttpBridgeServer.sendJson(exchange, 200, result);
    }

    private void handleGet(HttpExchange exchange, String relationMapId) throws Exception {
        JsonObject result = EdtDispatcher.read(project -> serializeRelationMap(project, relationMapId));
        HttpBridgeServer.sendJson(exchange, 200, result);
    }

    private void handleCreate(HttpExchange exchange) throws Exception {
        JsonObject body = JsonHelper.parseBody(exchange);
        String parentId = JsonHelper.requireString(body, "parentId");
        String name = JsonHelper.optionalString(body, "name");
        if (name == null || name.isEmpty()) {
            name = "Relation Map";
        }

        String finalName = name;
        JsonObject result = EdtDispatcher.write("MCP Bridge: Create Relation Map", project -> {
            Element parentElement = resolveElement(project, parentId, "Parent element");
            if (!(parentElement instanceof Namespace)) {
                throw new IllegalArgumentException("Parent element is not a Namespace: " + parentId);
            }

            Diagram diagram = ModelElementsManager.getInstance()
                    .createDiagram(RELATION_MAP_TYPE, (Namespace) parentElement);
            if (diagram == null) {
                throw new IllegalStateException("Failed to create Relation Map");
            }
            diagram.setName(finalName);

            GraphSettings settings = new GraphSettings(diagram);
            applySettings(project, settings, body);
            boolean refresh = optionalBoolean(body, "refresh", false);
            if (refresh) {
                RelationshipMapUtilities.refreshMap(diagram);
            }

            JsonObject response = new JsonObject();
            response.addProperty("created", true);
            response.addProperty("refreshRequested", refresh);
            response.add("relationMap", serializeRelationMap(project, diagram.getID()));
            return response;
        });
        HttpBridgeServer.sendJson(exchange, 201, result);
    }

    private void handleCriteriaTemplates(HttpExchange exchange) throws IOException {
        JsonArray templates = new JsonArray();
        for (CriteriaTemplate template : CRITERIA_TEMPLATES.values()) {
            templates.add(template.toJson());
        }
        JsonObject response = new JsonObject();
        response.addProperty("count", templates.size());
        response.add("templates", templates);
        HttpBridgeServer.sendJson(exchange, 200, response);
    }

    private void handleCompare(HttpExchange exchange) throws Exception {
        JsonObject body = JsonHelper.parseBody(exchange);
        String leftId = JsonHelper.requireString(body, "leftRelationMapId");
        String rightId = JsonHelper.requireString(body, "rightRelationMapId");
        boolean includePresentations = optionalBoolean(body, "includePresentations", true);
        boolean includeRaw = optionalBoolean(body, "includeRaw", false);
        JsonObject result = EdtDispatcher.read(project -> {
            JsonObject left = captureRelationMap(project, leftId, includePresentations, includeRaw);
            JsonObject right = captureRelationMap(project, rightId, includePresentations, includeRaw);
            JsonObject response = new JsonObject();
            response.add("left", left);
            response.add("right", right);
            response.add("diff", JsonDiff.diff(left, right, Set.of(), 500, true));
            return response;
        });
        HttpBridgeServer.sendJson(exchange, 200, result);
    }

    private void handleConfigure(HttpExchange exchange, String relationMapId) throws Exception {
        JsonObject body = JsonHelper.parseBody(exchange);
        JsonObject result = EdtDispatcher.write("MCP Bridge: Configure Relation Map", project -> {
            Diagram diagram = resolveRelationMap(project, relationMapId);
            GraphSettings settings = new GraphSettings(diagram);
            applySettings(project, settings, body);
            boolean refresh = optionalBoolean(body, "refresh", false);
            if (refresh) {
                RelationshipMapUtilities.refreshMap(diagram);
            }

            JsonObject response = new JsonObject();
            response.addProperty("configured", true);
            response.addProperty("refreshRequested", refresh);
            response.add("relationMap", serializeRelationMap(project, relationMapId));
            return response;
        });
        HttpBridgeServer.sendJson(exchange, 200, result);
    }

    private void handleRefresh(HttpExchange exchange, String relationMapId) throws Exception {
        JsonObject body = JsonHelper.parseBody(exchange);
        int refreshTimeoutSeconds = clamp(optionalInt(body, "refreshTimeoutSeconds"), 1, 600, 120);
        JsonObject result = EdtDispatcher.write("MCP Bridge: Refresh Relation Map", project -> {
            Diagram diagram = resolveRelationMap(project, relationMapId);
            RelationshipMapUtilities.refreshMap(diagram);

            JsonObject response = new JsonObject();
            response.addProperty("refreshed", true);
            response.addProperty("refreshTimeoutSeconds", refreshTimeoutSeconds);
            response.add("relationMap", serializeRelationMap(project, relationMapId));
            return response;
        }, refreshTimeoutSeconds);
        HttpBridgeServer.sendJson(exchange, 200, result);
    }

    private void handleTraceabilityGraph(HttpExchange exchange) throws Exception {
        JsonObject body = JsonHelper.parseBody(exchange);
        JsonObject result = EdtDispatcher.read(project -> buildTraceabilityGraph(project, body, null));
        HttpBridgeServer.sendJson(exchange, 200, result);
    }

    private void handleRelationMapGraph(HttpExchange exchange, String relationMapId) throws Exception {
        JsonObject body = JsonHelper.parseBody(exchange);
        JsonObject result = EdtDispatcher.read(project -> buildTraceabilityGraph(project, body, relationMapId));
        HttpBridgeServer.sendJson(exchange, 200, result);
    }

    private void handleRawSettings(HttpExchange exchange, String relationMapId) throws Exception {
        Map<String, String> params = JsonHelper.parseQuery(exchange);
        boolean includeRaw = optionalQueryBoolean(params, "includeRaw", false);
        boolean summaryOnly = optionalQueryBoolean(params, "summaryOnly", false);
        JsonObject result = EdtDispatcher.read(project -> {
            Diagram diagram = resolveRelationMap(project, relationMapId);
            GraphSettings settings = new GraphSettings(diagram);
            JsonObject response = serializeRelationMap(project, relationMapId);
            JsonObject raw = new JsonObject();
            JsonArray warnings = new JsonArray();
            raw.addProperty("settingsClassName", settings.getClass().getName());
            raw.addProperty("valid", safeIsValid(settings));
            raw.addProperty("criteriaCount",
                    settings.getDependencyCriterion() != null ? settings.getDependencyCriterion().size() : 0);
            raw.add("publicNoArgGetters", reflectGetterValues(settings, includeRaw, summaryOnly, warnings));
            response.add("rawSettings", raw);
            response.add("warnings", warnings);
            return response;
        });
        HttpBridgeServer.sendJson(exchange, 200, result);
    }

    private void handlePresentations(HttpExchange exchange, String relationMapId) throws Exception {
        Map<String, String> params = JsonHelper.parseQuery(exchange);
        int limit = optionalQueryInt(params, "limit", 250);
        int offset = optionalQueryInt(params, "offset", 0);
        boolean includeProperties = optionalQueryBoolean(params, "includeProperties", false);
        boolean includeRaw = optionalQueryBoolean(params, "includeRaw", false);
        boolean summaryOnly = optionalQueryBoolean(params, "summaryOnly", true);
        JsonObject result = EdtDispatcher.read(project -> {
            Diagram diagram = resolveRelationMap(project, relationMapId);
            DiagramPresentationElement dpe = project.getDiagram(diagram);
            JsonArray warnings = new JsonArray();
            try {
                dpe.ensureLoaded();
                warnings.add("Relation Map ensureLoaded() was called before presentation inspection");
            } catch (Exception e) {
                warnings.add("ensureLoaded failed: " + e.getMessage());
            }
            Map<String, String> parentById = new LinkedHashMap<>();
            List<PresentationElement> presentations = PresentationSerializer.flatten(dpe, parentById);
            JsonArray array = new JsonArray();
            int start = Math.max(0, offset);
            int end = Math.min(presentations.size(), start + Math.max(0, limit));
            for (int i = start; i < end; i++) {
                PresentationElement pe = presentations.get(i);
                array.add(includeProperties
                        ? PresentationSerializer.presentationWithProperties(pe, parentById.get(pe.getID()), includeRaw, summaryOnly)
                        : PresentationSerializer.presentationSummary(pe, parentById.get(pe.getID())));
            }
            JsonObject response = new JsonObject();
            response.add("relationMap", PresentationSerializer.diagramSummary(dpe));
            response.addProperty("presentationCount", presentations.size());
            response.add("countsByType", PresentationSerializer.countByType(presentations));
            response.addProperty("limit", limit);
            response.addProperty("offset", offset);
            response.addProperty("returnedPresentationCount", array.size());
            response.add("presentations", array);
            response.add("warnings", warnings);
            return response;
        });
        HttpBridgeServer.sendJson(exchange, 200, result);
    }

    private void handleSetCriteria(HttpExchange exchange, String relationMapId) throws Exception {
        JsonObject body = JsonHelper.parseBody(exchange);
        String mode = JsonHelper.optionalString(body, "mode");
        if (mode == null) {
            mode = "replace";
        }
        String finalMode = mode;
        JsonArray requested = body.has("criteria") && body.get("criteria").isJsonArray()
                ? body.getAsJsonArray("criteria") : new JsonArray();
        boolean refresh = optionalBoolean(body, "refresh", false);
        JsonObject result = EdtDispatcher.write("MCP Bridge: Set Relation Map Criteria", project -> {
            Diagram diagram = resolveRelationMap(project, relationMapId);
            GraphSettings settings = new GraphSettings(diagram);
            List<String> before = settings.getDependencyCriterion() != null
                    ? new ArrayList<>(settings.getDependencyCriterion()) : new ArrayList<>();
            List<String> criteria = criteriaFromRequest(project, requested);
            List<String> after = new ArrayList<>(before);
            if ("replace".equalsIgnoreCase(finalMode)) {
                after = criteria;
            } else if ("append".equalsIgnoreCase(finalMode)) {
                after.addAll(criteria);
            } else if ("remove".equalsIgnoreCase(finalMode)) {
                after.removeAll(criteria);
            } else {
                throw new IllegalArgumentException("mode must be replace, append, or remove");
            }
            settings.setDependencyCriterion(after);
            settings.setInitialized(true);
            if (refresh) {
                RelationshipMapUtilities.refreshMap(diagram);
            }
            JsonObject response = new JsonObject();
            response.addProperty("criteriaUpdated", true);
            response.addProperty("mode", finalMode);
            response.addProperty("refreshed", refresh);
            response.addProperty("beforeCriteriaCount", before.size());
            response.addProperty("afterCriteriaCount", after.size());
            response.add("beforeCriteria", stringsToJson(before));
            response.add("afterCriteria", stringsToJson(after));
            response.add("relationMap", serializeRelationMap(project, relationMapId));
            return response;
        });
        HttpBridgeServer.sendJson(exchange, 200, result);
    }

    private void handleExpandCollapse(HttpExchange exchange, String relationMapId, boolean expand) throws Exception {
        JsonObject body = JsonHelper.parseBody(exchange);
        boolean refresh = optionalBoolean(body, "refresh", false);
        String mode = JsonHelper.optionalString(body, "mode");
        if (mode == null) {
            mode = "all";
        }
        String finalMode = mode;
        String layout = JsonHelper.optionalString(body, "layout");
        int actionTimeoutSeconds = clamp(optionalInt(body, "actionTimeoutSeconds"), 1, 600, 120);
        JsonObject result = EdtDispatcher.write(
                "MCP Bridge: " + (expand ? "Expand" : "Collapse") + " Relation Map",
                project -> {
                    Diagram diagram = resolveRelationMap(project, relationMapId);
                    DiagramPresentationElement dpe = project.getDiagram(diagram);
                    dpe.ensureLoaded();
                    int before = PresentationSerializer.flatten(dpe, null).size();
                    JsonObject graphBefore = graphSummary(project, relationMapId);
                    JsonObject displayBefore = relationMapDisplaySummary(dpe);
                    JsonArray attempts = new JsonArray();
                    boolean applied = invokeRelationMapAction(dpe, expand, attempts);
                    if (refresh && applied) {
                        RelationshipMapUtilities.refreshMap(diagram);
                    }
                    if (layout != null && applied) {
                        new GraphSettings(diagram).setLayout(layout);
                        dpe.layout(true);
                    }
                    dpe.ensureLoaded();
                    int after = PresentationSerializer.flatten(dpe, null).size();
                    JsonObject graphAfter = graphSummary(project, relationMapId);
                    JsonObject displayAfter = relationMapDisplaySummary(dpe);
                    JsonObject response = new JsonObject();
                    response.addProperty(expand ? "expanded" : "collapsed", applied);
                    response.addProperty("supported", applied);
                    response.addProperty("mode", finalMode);
                    response.addProperty("refreshed", refresh);
                    response.addProperty("actionTimeoutSeconds", actionTimeoutSeconds);
                    response.addProperty("presentationCountBefore", before);
                    response.addProperty("presentationCountAfter", after);
                    response.addProperty("presentationCountDelta", after - before);
                    response.add("graphBefore", graphBefore);
                    response.add("graphAfter", graphAfter);
                    response.add("displayBefore", displayBefore);
                    response.add("displayAfter", displayAfter);
                    response.add("attempts", attempts);
                    if (!applied) {
                        response.addProperty("unsupportedReason",
                                expand
                                        ? "Relation Map display expansion failed"
                                        : "No CATIA Relation Map collapse API has been validated; generic diagram close is not treated as collapse");
                    }
                    return response;
                }, actionTimeoutSeconds);
        HttpBridgeServer.sendJson(exchange, 200, result);
    }

    private void handleRender(HttpExchange exchange, String relationMapId) throws Exception {
        JsonObject body = JsonHelper.parseBody(exchange);
        boolean refresh = optionalBoolean(body, "refresh", false);
        String expand = JsonHelper.optionalString(body, "expand");
        String layout = JsonHelper.optionalString(body, "layout");
        int scalePercentage = clamp(optionalInt(body, "scalePercentage"), 25, 1000, 200);
        boolean includeImage = optionalBoolean(body, "includeImage", true);
        boolean exportImage = optionalBoolean(body, "exportImage", true);
        boolean includePresentationSummary = optionalBoolean(body, "includePresentationSummary", true);
        int renderTimeoutSeconds = clamp(optionalInt(body, "renderTimeoutSeconds"), 1, 600, 120);
        boolean mutatesPresentationState = refresh || layout != null
                || (expand != null && !"none".equalsIgnoreCase(expand));
        EdtDispatcher.ModelAction<JsonObject> renderAction = project -> {
            Diagram diagram = resolveRelationMap(project, relationMapId);
            DiagramPresentationElement dpe = project.getDiagram(diagram);
            dpe.ensureLoaded();
            int before = PresentationSerializer.flatten(dpe, null).size();
            JsonArray warnings = new JsonArray();
            JsonArray expandAttempts = new JsonArray();
            boolean refreshed = false;
            if (expand != null && !"none".equalsIgnoreCase(expand)) {
                if (!invokeRelationMapAction(dpe, true, expandAttempts)) {
                    warnings.add("Expand requested but Relation Map display expansion failed");
                }
            }
            if (refresh) {
                try {
                    RelationshipMapUtilities.refreshMap(diagram);
                    refreshed = true;
                } catch (Exception e) {
                    warnings.add("Relation Map refresh failed: " + describeException(e));
                }
            }
            if (layout != null) {
                try {
                    new GraphSettings(diagram).setLayout(layout);
                    dpe.layout(true);
                } catch (Exception e) {
                    warnings.add("Relation Map layout failed: " + describeException(e));
                }
            }
            dpe.ensureLoaded();
            List<PresentationElement> presentations = PresentationSerializer.flatten(dpe, null);
            BufferedImage image = null;
            if (exportImage) {
                try {
                    image = ImageExporter.export(dpe, false, scalePercentage);
                } catch (Exception e) {
                    warnings.add("Relation Map image export failed: " + describeException(e));
                }
            } else {
                warnings.add("Relation Map image export skipped because exportImage=false");
            }
            JsonObject response = new JsonObject();
            response.addProperty("rendered", image != null);
            response.addProperty("refreshRequested", refresh);
            response.addProperty("refreshed", refreshed);
            response.addProperty("exportImage", exportImage);
            response.addProperty("renderTimeoutSeconds", renderTimeoutSeconds);
            response.addProperty("scalePercentage", scalePercentage);
            response.addProperty("presentationCountBefore", before);
            response.addProperty("presentationCountAfter", presentations.size());
            response.addProperty("presentationCountDelta", presentations.size() - before);
            response.add("graphSummary", graphSummary(project, relationMapId));
            response.add("expandAttempts", expandAttempts);
            if (includePresentationSummary) {
                response.add("presentationCountsByType", PresentationSerializer.countByType(presentations));
            }
            if (image != null) {
                response.add("image", imageJson(image, includeImage));
            }
            response.add("warnings", warnings);
            return response;
        };
        JsonObject result = mutatesPresentationState
                ? EdtDispatcher.write("MCP Bridge: Render Relation Map", renderAction, renderTimeoutSeconds)
                : EdtDispatcher.readOnEdt("MCP Bridge: Render Relation Map", renderAction, renderTimeoutSeconds);
        HttpBridgeServer.sendJson(exchange, 200, result);
    }

    private void handleVerify(HttpExchange exchange, String relationMapId) throws Exception {
        JsonObject body = JsonHelper.parseBody(exchange);
        int expectedMinNodes = clamp(optionalInt(body, "expectedMinNodes"), 0, 100000, 0);
        int expectedMinEdges = clamp(optionalInt(body, "expectedMinEdges"), 0, 100000, 0);
        int expectedRenderedNodes = clamp(optionalInt(body, "expectedRenderedNodes"), 0, 100000, 0);
        JsonObject result = EdtDispatcher.read(project -> {
            Diagram diagram = resolveRelationMap(project, relationMapId);
            DiagramPresentationElement dpe = project.getDiagram(diagram);
            GraphSettings settings = new GraphSettings(diagram);
            JsonObject graphRequest = new JsonObject();
            if (body.has("relationshipTypes")) {
                graphRequest.add("relationshipTypes", body.get("relationshipTypes"));
            }
            graphRequest.addProperty("maxDepth", clamp(optionalInt(body, "maxDepth"), 1, 12, 3));
            graphRequest.addProperty("maxNodes", 1000);
            graphRequest.addProperty("direction", "both");
            JsonObject graph = buildTraceabilityGraph(project, graphRequest, relationMapId);
            dpe.ensureLoaded();
            int rendered = PresentationSerializer.flatten(dpe, null).size();
            boolean graphPasses = graph.get("nodeCount").getAsInt() >= expectedMinNodes
                    && graph.get("edgeCount").getAsInt() >= expectedMinEdges;
            boolean settingsPasses = safeIsValid(settings);
            boolean renderPasses = rendered >= expectedRenderedNodes;
            JsonObject checks = new JsonObject();
            checks.addProperty("graphTraversalPasses", graphPasses);
            checks.addProperty("settingsValidityPasses", settingsPasses);
            checks.addProperty("renderedNodeCountPasses", renderPasses);
            JsonObject response = new JsonObject();
            response.addProperty("ok", graphPasses && settingsPasses && renderPasses);
            response.add("checks", checks);
            response.add("graph", graph);
            response.addProperty("renderedPresentationCount", rendered);
            response.addProperty("expectedMinNodes", expectedMinNodes);
            response.addProperty("expectedMinEdges", expectedMinEdges);
            response.addProperty("expectedRenderedNodes", expectedRenderedNodes);
            response.add("settings", serializeRelationMap(project, relationMapId).get("settings"));
            response.add("presentationCountsByType",
                    PresentationSerializer.countByType(PresentationSerializer.flatten(dpe, null)));
            return response;
        });
        HttpBridgeServer.sendJson(exchange, 200, result);
    }

    private void applySettings(Project project, GraphSettings settings, JsonObject body) {
        String contextElementId = JsonHelper.optionalString(body, "contextElementId");
        if (contextElementId != null) {
            settings.setContextElement(resolveElement(project, contextElementId, "Context element"));
            settings.setMakeElementAsContext(optionalBoolean(body, "makeElementAsContext", true));
        }

        List<String> scopeIds = JsonHelper.optionalStringList(body, "scopeIds");
        if (scopeIds != null) {
            settings.setScopeRoots(resolveElements(project, scopeIds, "Scope element"));
        }

        List<String> elementTypeIds = JsonHelper.optionalStringList(body, "elementTypeIds");
        if (elementTypeIds != null) {
            settings.setElementTypes(resolveElements(project, elementTypeIds, "Element type"));
        }

        List<String> criteria = JsonHelper.optionalStringList(body, "dependencyCriteria");
        if (criteria != null) {
            settings.setDependencyCriterion(criteria);
        }

        Integer depth = optionalInt(body, "depth");
        if (depth != null) {
            settings.setDepth(depth);
        }

        String layout = JsonHelper.optionalString(body, "layout");
        if (layout != null) {
            settings.setLayout(layout);
        }

        applyOptionalBoolean(body, "legendEnabled", settings::setLegendEnabled);
        applyOptionalBoolean(body, "showFullTypes", settings::setShowFullTypes);
        applyOptionalBoolean(body, "showStereotypes", settings::setShowStereotypes);
        applyOptionalBoolean(body, "showParameters", settings::setShowParameters);
        applyOptionalBoolean(body, "showElementNumbers", settings::setShowElementNumbers);
        applyOptionalBoolean(body, "singleNodePerElement", settings::setEnabledSingleNodePerElementMode);
        applyOptionalBoolean(body, "shortNodeNames", settings::setEnabledShortNodeNamesMode);
        applyOptionalBoolean(body, "typesIncludeSubtypes", settings::setTypesIncludeSubtypes);
        applyOptionalBoolean(body, "typesIncludeCustomTypes", settings::setIncludeCustomTypes);

        settings.setInitialized(true);
    }

    private JsonObject serializeRelationMap(Project project, String relationMapId) {
        Diagram diagram = resolveRelationMap(project, relationMapId);
        DiagramPresentationElement dpe = project.getDiagram(diagram);
        GraphSettings settings = new GraphSettings(diagram);

        JsonObject response = toSummaryJson(dpe);
        JsonObject settingsJson = new JsonObject();
        settingsJson.addProperty("initialized", settings.isInitialized());
        settingsJson.addProperty("depth", settings.getDepth());
        settingsJson.addProperty("layout", settings.getLayout());
        settingsJson.addProperty("legendEnabled", settings.isLegendEnabled());
        settingsJson.addProperty("showFullTypes", settings.isShowFullTypes());
        settingsJson.addProperty("showStereotypes", settings.isShowStereotypes());
        settingsJson.addProperty("showParameters", settings.isShowParameters());
        settingsJson.addProperty("showElementNumbers", settings.isShowElementNumbers());
        settingsJson.addProperty("singleNodePerElement", settings.isEnabledSingleNodePerElementMode());
        settingsJson.addProperty("shortNodeNames", settings.isEnabledShortNodeNamesMode());
        settingsJson.addProperty("typesIncludeSubtypes", settings.isTypesIncludeSubtypes());
        settingsJson.addProperty("typesIncludeCustomTypes", settings.isTypesIncludeCustomTypes());
        settingsJson.addProperty("valid", safeIsValid(settings));

        Element context = settings.getContextElement();
        if (context != null) {
            settingsJson.add("contextElement", ElementSerializer.toJsonCompact(context));
        }
        settingsJson.add("scopeRoots", elementsToJson(settings.getScopeRoots()));
        settingsJson.add("elementTypes", elementsToJson(settings.getElementTypes()));
        settingsJson.add("dependencyCriteria", stringsToJson(settings.getDependencyCriterion()));

        response.add("settings", settingsJson);
        return response;
    }

    private JsonObject buildTraceabilityGraph(Project project, JsonObject body, String relationMapId) {
        List<Element> roots = resolveGraphRoots(project, body, relationMapId);
        Set<String> relationshipTypeFilter = normalizedFilter(JsonHelper.optionalStringList(body, "relationshipTypes"));
        String direction = normalizeDirection(JsonHelper.optionalString(body, "direction"));
        int maxDepth = clamp(optionalInt(body, "maxDepth"), 1, 12, 3);
        int maxNodes = clamp(optionalInt(body, "maxNodes"), 1, 1000, 250);

        JsonArray nodes = new JsonArray();
        JsonArray edges = new JsonArray();
        Set<String> nodeIds = new HashSet<>();
        Set<String> edgeIds = new HashSet<>();
        Set<String> expandedAtDepth = new HashSet<>();
        Queue<GraphFrontierItem> frontier = new ArrayDeque<>();

        for (Element root : roots) {
            addNode(nodes, nodeIds, root, 0, true);
            frontier.add(new GraphFrontierItem(root, 0));
        }

        boolean truncated = false;
        while (!frontier.isEmpty()) {
            GraphFrontierItem item = frontier.remove();
            if (item.depth >= maxDepth) {
                continue;
            }
            String expansionKey = item.element.getID() + "@" + item.depth;
            if (!expandedAtDepth.add(expansionKey)) {
                continue;
            }

            List<GraphEdge> adjacent = collectAdjacentEdges(item.element, direction, relationshipTypeFilter);
            for (GraphEdge edge : adjacent) {
                if (!edgeIds.add(edge.relationship.getID())) {
                    continue;
                }
                edges.add(edge.toJson(item.depth + 1));

                for (Element endpoint : edge.traversalTargets) {
                    if (endpoint == null || endpoint.getID() == null) {
                        continue;
                    }
                    boolean added = addNode(nodes, nodeIds, endpoint, item.depth + 1, false);
                    if (nodeIds.size() >= maxNodes) {
                        truncated = true;
                        break;
                    }
                    if (added && item.depth + 1 < maxDepth) {
                        frontier.add(new GraphFrontierItem(endpoint, item.depth + 1));
                    }
                }
                if (truncated) {
                    break;
                }
            }
            if (truncated) {
                break;
            }
        }

        JsonObject response = new JsonObject();
        response.addProperty("rootCount", roots.size());
        response.add("rootElements", elementsToJson(roots));
        response.addProperty("nodeCount", nodes.size());
        response.addProperty("edgeCount", edges.size());
        response.addProperty("maxDepth", maxDepth);
        response.addProperty("maxNodes", maxNodes);
        response.addProperty("direction", direction);
        response.addProperty("truncated", truncated);
        response.add("nodes", nodes);
        response.add("edges", edges);
        if (relationMapId != null) {
            response.addProperty("relationMapId", relationMapId);
        }
        return response;
    }

    private List<Element> resolveGraphRoots(Project project, JsonObject body, String relationMapId) {
        List<String> rootIds = JsonHelper.optionalStringList(body, "rootElementIds");
        String contextElementId = JsonHelper.optionalString(body, "contextElementId");
        if (rootIds == null && contextElementId != null) {
            rootIds = List.of(contextElementId);
        }

        if (rootIds != null && !rootIds.isEmpty()) {
            return resolveElements(project, rootIds, "Root element");
        }

        if (relationMapId != null) {
            Diagram diagram = resolveRelationMap(project, relationMapId);
            Element context = new GraphSettings(diagram).getContextElement();
            if (context != null) {
                return List.of(context);
            }
        }

        throw new IllegalArgumentException(
                "Provide rootElementIds or contextElementId, or call /relation-maps/{id}/graph on a map with a context element.");
    }

    private List<GraphEdge> collectAdjacentEdges(
            Element element,
            String direction,
            Set<String> relationshipTypeFilter) {
        List<GraphEdge> edges = new ArrayList<>();
        String selfId = element.getID();

        if (includeOutgoing(direction)) {
            Collection<DirectedRelationship> relationships = element.get_directedRelationshipOfSource();
            if (relationships != null) {
                for (DirectedRelationship rel : relationships) {
                    if (matchesRelationshipFilter(rel, relationshipTypeFilter)) {
                        edges.add(GraphEdge.directed(rel, "outgoing", rel.getSource(), rel.getTarget()));
                    }
                }
            }

            if (element instanceof ActivityNode) {
                Collection<ActivityEdge> outgoingEdges = ((ActivityNode) element).getOutgoing();
                if (outgoingEdges != null) {
                    for (ActivityEdge edge : outgoingEdges) {
                        if (matchesRelationshipFilter(edge, relationshipTypeFilter)) {
                            List<Element> sources = new ArrayList<>();
                            List<Element> targets = new ArrayList<>();
                            if (edge.getSource() != null) {
                                sources.add(edge.getSource());
                            }
                            if (edge.getTarget() != null) {
                                targets.add(edge.getTarget());
                            }
                            edges.add(GraphEdge.directed(edge, "outgoing", sources, targets));
                        }
                    }
                }
            }
        }

        if (includeIncoming(direction)) {
            Collection<DirectedRelationship> relationships = element.get_directedRelationshipOfTarget();
            if (relationships != null) {
                for (DirectedRelationship rel : relationships) {
                    if (matchesRelationshipFilter(rel, relationshipTypeFilter)) {
                        edges.add(GraphEdge.directed(rel, "incoming", rel.getSource(), rel.getTarget()));
                    }
                }
            }

            if (element instanceof ActivityNode) {
                Collection<ActivityEdge> incomingEdges = ((ActivityNode) element).getIncoming();
                if (incomingEdges != null) {
                    for (ActivityEdge edge : incomingEdges) {
                        if (matchesRelationshipFilter(edge, relationshipTypeFilter)) {
                            List<Element> sources = new ArrayList<>();
                            List<Element> targets = new ArrayList<>();
                            if (edge.getSource() != null) {
                                sources.add(edge.getSource());
                            }
                            if (edge.getTarget() != null) {
                                targets.add(edge.getTarget());
                            }
                            edges.add(GraphEdge.directed(edge, "incoming", sources, targets));
                        }
                    }
                }
            }
        }

        if ("both".equals(direction)) {
            Collection<Relationship> relationships = element.get_relationshipOfRelatedElement();
            if (relationships != null) {
                for (Relationship rel : relationships) {
                    if (rel instanceof DirectedRelationship) {
                        continue;
                    }
                    if (matchesRelationshipFilter(rel, relationshipTypeFilter)) {
                        edges.add(GraphEdge.undirected(rel, selfId, rel.getRelatedElement()));
                    }
                }
            }

            if (element instanceof ConnectableElement) {
                Collection<Connector> connectors = Connectors.collectDirectConnectors((ConnectableElement) element);
                if (connectors != null) {
                    for (Connector connector : connectors) {
                        if (matchesRelationshipFilter(connector, relationshipTypeFilter)) {
                            edges.add(GraphEdge.connector(connector, selfId));
                        }
                    }
                }
            }
        }

        return edges;
    }

    private boolean addNode(JsonArray nodes, Set<String> nodeIds, Element element, int depth, boolean root) {
        if (element == null || element.getID() == null || !nodeIds.add(element.getID())) {
            return false;
        }
        JsonObject node = ElementSerializer.toJsonReference(element);
        node.addProperty("depth", depth);
        node.addProperty("root", root);
        nodes.add(node);
        return true;
    }

    private boolean matchesRelationshipFilter(Element relationship, Set<String> filter) {
        if (filter.isEmpty()) {
            return true;
        }
        for (String token : relationshipTokens(relationship)) {
            if (filter.contains(token)) {
                return true;
            }
        }
        return false;
    }

    private Set<String> relationshipTokens(Element relationship) {
        Set<String> tokens = new HashSet<>();
        addToken(tokens, relationship.getHumanType());
        try {
            String shortName = ClassTypes.getShortName(relationship.getClassType());
            addToken(tokens, shortName);
        } catch (Exception ignored) {
            // Human type above is enough when the metaclass lookup is unavailable.
        }
        if (relationship instanceof NamedElement) {
            addToken(tokens, ((NamedElement) relationship).getName());
        }
        try {
            List<Stereotype> stereotypes = StereotypesHelper.getStereotypes(relationship);
            if (stereotypes != null) {
                for (Stereotype stereotype : stereotypes) {
                    if (stereotype != null) {
                        addToken(tokens, stereotype.getName());
                    }
                }
            }
        } catch (Exception ignored) {
            // Metaclass/human type matching remains available if stereotype lookup fails.
        }
        return tokens;
    }

    private void addToken(Set<String> tokens, String value) {
        String normalized = normalizeToken(value);
        if (!normalized.isEmpty()) {
            tokens.add(normalized);
        }
    }

    private Set<String> normalizedFilter(List<String> values) {
        Set<String> filter = new HashSet<>();
        if (values != null) {
            for (String value : values) {
                addToken(filter, value);
            }
        }
        return filter;
    }

    private String normalizeToken(String value) {
        if (value == null) {
            return "";
        }
        return value.toLowerCase(Locale.ROOT).replaceAll("[^a-z0-9]", "");
    }

    private String normalizeDirection(String value) {
        if (value == null || value.isBlank() || "both".equalsIgnoreCase(value)) {
            return "both";
        }
        if ("incoming".equalsIgnoreCase(value) || "outgoing".equalsIgnoreCase(value)) {
            return value.toLowerCase(Locale.ROOT);
        }
        throw new IllegalArgumentException("direction must be incoming, outgoing, or both");
    }

    private boolean includeOutgoing(String direction) {
        return "both".equals(direction) || "outgoing".equals(direction);
    }

    private boolean includeIncoming(String direction) {
        return "both".equals(direction) || "incoming".equals(direction);
    }

    private int clamp(Integer value, int min, int max, int defaultValue) {
        if (value == null) {
            return defaultValue;
        }
        return Math.max(min, Math.min(max, value));
    }

    private boolean safeIsValid(GraphSettings settings) {
        try {
            return GraphUtils.isGraphSettingValid(settings);
        } catch (Exception e) {
            return false;
        }
    }

    private JsonArray elementsToJson(Collection<Element> elements) {
        JsonArray array = new JsonArray();
        if (elements != null) {
            for (Element element : elements) {
                array.add(ElementSerializer.toJsonCompact(element));
            }
        }
        return array;
    }

    private JsonArray stringsToJson(List<String> values) {
        JsonArray array = new JsonArray();
        if (values != null) {
            for (String value : values) {
                array.add(value);
            }
        }
        return array;
    }

    private JsonObject reflectGetterValues(
            Object target,
            boolean includeRaw,
            boolean summaryOnly,
            JsonArray warnings) {
        JsonObject values = new JsonObject();
        for (Method method : target.getClass().getMethods()) {
            if (method.getParameterCount() != 0
                    || method.getReturnType() == Void.TYPE
                    || "getClass".equals(method.getName())) {
                continue;
            }
            String name = method.getName();
            if (!name.startsWith("get") && !name.startsWith("is")) {
                continue;
            }
            try {
                Object value = method.invoke(target);
                values.add(name, PropertySerializer.serializeValue(value, includeRaw, summaryOnly));
            } catch (Exception e) {
                warnings.add(name + " failed: " + e.getClass().getSimpleName() + ": " + e.getMessage());
            }
        }
        return values;
    }

    private List<String> criteriaFromRequest(Project project, JsonArray requested) {
        List<String> criteria = new ArrayList<>();
        for (JsonElement item : requested) {
            if (item.isJsonPrimitive()) {
                criteria.add(item.getAsString());
                continue;
            }
            if (!item.isJsonObject()) {
                throw new IllegalArgumentException("criteria entries must be strings or objects");
            }
            JsonObject object = item.getAsJsonObject();
            String raw = JsonHelper.optionalString(object, "rawExpression");
            if (raw != null) {
                criteria.add(raw);
                continue;
            }
            String templateKey = JsonHelper.optionalString(object, "template");
            if (templateKey != null) {
                CriteriaTemplate template = CRITERIA_TEMPLATES.get(templateKey);
                if (template == null) {
                    throw new IllegalArgumentException("Unknown criteria template: " + templateKey);
                }
                criteria.add(template.toExpression(project));
                continue;
            }
            String relationshipType = JsonHelper.optionalString(object, "relationshipType");
            String direction = JsonHelper.optionalString(object, "direction");
            if (relationshipType != null) {
                criteria.add(direction != null ? relationshipType + ":" + direction : relationshipType);
                continue;
            }
            throw new IllegalArgumentException("criteria object requires rawExpression, template, or relationshipType");
        }
        return criteria;
    }

    private JsonObject captureRelationMap(Project project, String relationMapId, boolean includePresentations, boolean includeRaw) {
        JsonObject json = serializeRelationMap(project, relationMapId);
        Diagram diagram = resolveRelationMap(project, relationMapId);
        GraphSettings settings = new GraphSettings(diagram);
        JsonArray warnings = new JsonArray();
        JsonObject raw = new JsonObject();
        raw.addProperty("settingsClassName", settings.getClass().getName());
        raw.add("publicNoArgGetters", reflectGetterValues(settings, includeRaw, true, warnings));
        json.add("rawSettings", raw);
        if (includePresentations) {
            DiagramPresentationElement dpe = project.getDiagram(diagram);
            dpe.ensureLoaded();
            Map<String, String> parentById = new LinkedHashMap<>();
            List<PresentationElement> presentations = PresentationSerializer.flatten(dpe, parentById);
            json.addProperty("presentationCount", presentations.size());
            json.add("presentationCountsByType", PresentationSerializer.countByType(presentations));
            json.add("presentations", PresentationSerializer.summarizePresentations(presentations, parentById));
        }
        json.add("warnings", warnings);
        return json;
    }

    private JsonObject graphSummary(Project project, String relationMapId) {
        JsonObject summary = new JsonObject();
        try {
            JsonObject request = new JsonObject();
            request.addProperty("direction", "both");
            request.addProperty("maxDepth", 3);
            request.addProperty("maxNodes", 1000);
            JsonObject graph = buildTraceabilityGraph(project, request, relationMapId);
            summary.addProperty("available", true);
            summary.addProperty("nodeCount", graph.get("nodeCount").getAsInt());
            summary.addProperty("edgeCount", graph.get("edgeCount").getAsInt());
            summary.addProperty("truncated", graph.get("truncated").getAsBoolean());
        } catch (Exception e) {
            summary.addProperty("available", false);
            summary.addProperty("error", e.getClass().getSimpleName() + ": " + e.getMessage());
        }
        return summary;
    }

    private JsonObject relationMapDisplaySummary(DiagramPresentationElement dpe) {
        JsonObject summary = new JsonObject();
        try {
            summary.addProperty("diagramWindowOpen", dpe.isDiagramWindowOpen());
            summary.addProperty("diagramWindowActive", dpe.isDiagramWindowActive());
            if (!dpe.isDiagramWindowOpen()) {
                summary.addProperty("available", false);
                summary.addProperty("reason", "Relation Map diagram window is not open");
                return summary;
            }
            Object display = getRelationMapDisplay(dpe);
            if (display == null) {
                summary.addProperty("available", false);
                summary.addProperty("reason", "Relation Map display is unavailable");
                return summary;
            }
            summary.addProperty("available", true);
            summary.addProperty("nodeCount", invokeInt(display, "getNodeCount"));
            summary.addProperty("containsGraph", invokeBoolean(display, "containsGraph"));
            Object root = invokeNoArg(display, "getRoot");
            summary.addProperty("rootChildCount", root != null ? invokeInt(root, "getChildCount") : 0);
            JsonArray relationshipTypes = new JsonArray();
            Object dataManager = invokeNoArg(display, "getDataManager");
            Object relationshipTypeValues = dataManager != null ? invokeNoArg(dataManager, "getRelationshipTypes") : null;
            if (relationshipTypeValues instanceof Iterable<?>) {
                for (Object relationshipType : (Iterable<?>) relationshipTypeValues) {
                    relationshipTypes.add(getRelationshipTypeName(relationshipType));
                }
            }
            summary.add("relationshipTypes", relationshipTypes);
        } catch (Exception e) {
            summary.addProperty("available", false);
            summary.addProperty("error", e.getClass().getSimpleName() + ": " + e.getMessage());
        }
        return summary;
    }

    private boolean invokeRelationMapAction(
            DiagramPresentationElement dpe,
            boolean expand,
            JsonArray attempts) {
        JsonObject attempt = new JsonObject();
        attempt.addProperty("className", "com.nomagic.magicdraw.visualization.relationshipmap.ui.diagram.view.AbstractGraphDisplay");
        attempt.addProperty("method", expand ? "expandElements" : "collapseElements");
        attempts.add(attempt);
        if (!expand) {
            attempt.addProperty("invoked", false);
            attempt.addProperty("unsupportedReason",
                    "No validated Relation Map display collapse API is available");
            return false;
        }
        try {
            if (!dpe.isDiagramWindowOpen()) {
                dpe.open();
            }
            Object display = getRelationMapDisplay(dpe);
            if (display == null) {
                attempt.addProperty("invoked", false);
                attempt.addProperty("error", "Relation Map display is unavailable");
                return false;
            }
            attempt.addProperty("nodeCountBefore", invokeInt(display, "getNodeCount"));
            invokeNoArg(display, "expandElements");
            invokeNoArg(display, "refreshView");
            attempt.addProperty("nodeCountAfter", invokeInt(display, "getNodeCount"));
            attempt.addProperty("invoked", true);
            return true;
        } catch (Exception e) {
            attempt.addProperty("invoked", false);
            attempt.addProperty("error", e.getClass().getSimpleName() + ": " + e.getMessage());
            return false;
        }
    }

    private Object getRelationMapDisplay(DiagramPresentationElement dpe) throws Exception {
        Object component = RelationMapManager.getRMDiagramComponent(dpe);
        if (component == null) {
            return null;
        }
        invokeNoArg(component, "ensureDisplayIsBuilt");
        return invokeNoArg(component, "getRelationMapDisplay");
    }

    private Object invokeNoArg(Object target, String methodName) throws Exception {
        return target.getClass().getMethod(methodName).invoke(target);
    }

    private int invokeInt(Object target, String methodName) throws Exception {
        Object value = invokeNoArg(target, methodName);
        return value instanceof Number ? ((Number) value).intValue() : 0;
    }

    private boolean invokeBoolean(Object target, String methodName) throws Exception {
        Object value = invokeNoArg(target, methodName);
        return value instanceof Boolean && (Boolean) value;
    }

    private String getRelationshipTypeName(Object relationshipType) {
        if (relationshipType == null) {
            return "";
        }
        try {
            Object name = relationshipType.getClass().getMethod("getName").invoke(relationshipType);
            if (name != null) {
                return String.valueOf(name);
            }
        } catch (Exception ignored) {
            // Fall back to class name when CATIA's relationship property object has no public name.
        }
        return String.valueOf(relationshipType);
    }

    private boolean containsAny(String value, String[] tokens) {
        for (String token : tokens) {
            if (value.contains(token)) {
                return true;
            }
        }
        return false;
    }

    private JsonObject imageJson(BufferedImage image, boolean includeImage) throws IOException {
        ByteArrayOutputStream out = new ByteArrayOutputStream();
        ImageIO.write(image, "png", out);
        byte[] bytes = out.toByteArray();
        JsonObject json = new JsonObject();
        json.addProperty("format", "png");
        json.addProperty("width", image.getWidth());
        json.addProperty("height", image.getHeight());
        json.addProperty("imageBytes", bytes.length);
        json.addProperty("imageIncluded", includeImage);
        if (includeImage) {
            json.addProperty("image", Base64.getEncoder().encodeToString(bytes));
        }
        return json;
    }

    private static Map<String, CriteriaTemplate> buildCriteriaTemplates() {
        Map<String, CriteriaTemplate> templates = new LinkedHashMap<>();
        addTemplate(templates, "dependency.direct", "Dependency", "Dependency", "both", false);
        addTemplate(templates, "abstraction.direct", "Abstraction", "Abstraction", "both", false);
        addDslTemplate(templates, "refine.sourceToTarget", "Refine", "DIRECT", "Refine source-to-target", "sourceToTarget", false);
        addDslTemplate(templates, "refine.targetToSource", "Refine", "OPPOSITE", "Refine target-to-source", "targetToSource", true);
        addDslTemplate(templates, "refine.both", "Refine", "BOTH", "Refine both directions", "both", true);
        addDslTemplate(templates, "deriveReqt.sourceToTarget", "DeriveReqt", "DIRECT", "DeriveReqt source-to-target", "sourceToTarget", false);
        addDslTemplate(templates, "deriveReqt.targetToSource", "DeriveReqt", "OPPOSITE", "DeriveReqt target-to-source", "targetToSource", true);
        addDslTemplate(templates, "deriveReqt.both", "DeriveReqt", "BOTH", "DeriveReqt both directions", "both", true);
        addDslTemplate(templates, "satisfy.sourceToTarget", "Satisfy", "DIRECT", "Satisfy source-to-target", "sourceToTarget", false);
        addDslTemplate(templates, "satisfy.targetToSource", "Satisfy", "OPPOSITE", "Satisfy target-to-source", "targetToSource", false);
        addDslTemplate(templates, "satisfy.both", "Satisfy", "BOTH", "Satisfy relationships", "both", true);
        addDslTemplate(templates, "allocate.sourceToTarget", "Allocate", "DIRECT", "Allocate source-to-target", "sourceToTarget", false);
        addDslTemplate(templates, "allocate.targetToSource", "Allocate", "OPPOSITE", "Allocate target-to-source", "targetToSource", false);
        addDslTemplate(templates, "allocate.both", "Allocate", "BOTH", "Allocated to/from", "both", true);
        addDslTemplate(templates, "allocatedTo", "Allocate", "BOTH", "Allocated to/from", "both", true);
        return templates;
    }

    private static void addTemplate(
            Map<String, CriteriaTemplate> templates,
            String key,
            String expression,
            String relationshipType,
            String direction,
            boolean verified) {
        templates.put(key, new CriteriaTemplate(key, expression, relationshipType, direction, verified));
    }

    private static void addDslTemplate(
            Map<String, CriteriaTemplate> templates,
            String key,
            String stereotypeName,
            String dslDirection,
            String displayName,
            String direction,
            boolean verified) {
        templates.put(key, CriteriaTemplate.dsl(
                key,
                stereotypeName,
                dslDirection,
                displayName,
                direction,
                verified));
    }

    private static String createDslCriteriaExpression(
            Project project,
            String stereotypeName,
            String direction,
            String displayName) {
        Stereotype stereotype = findStereotype(project, stereotypeName);
        DSLRelationExpressionSpecification expression = new DSLRelationExpressionSpecification(stereotype);
        expression.setDirection(Direction.valueOf(direction));
        CallExpressionSpecification call = ExpressionSpecificationUtil.makeCallExpressionSpecification(expression, true);
        call.setName(displayName);
        return ExpressionSpecificationUtil.convertToString(call);
    }

    private static Stereotype findStereotype(Project project, String stereotypeName) {
        Collection<Stereotype> stereotypes = StereotypesHelper.getAllStereotypes(project);
        for (Stereotype stereotype : stereotypes) {
            if (stereotypeName.equals(stereotype.getName())) {
                return stereotype;
            }
        }
        throw new IllegalArgumentException("Stereotype not found for Relation Map criteria template: " + stereotypeName);
    }

    private boolean optionalQueryBoolean(Map<String, String> params, String key, boolean defaultValue) {
        String value = params.get(key);
        return value == null ? defaultValue : Boolean.parseBoolean(value);
    }

    private int optionalQueryInt(Map<String, String> params, String key, int defaultValue) {
        String value = params.get(key);
        if (value == null || value.isBlank()) {
            return defaultValue;
        }
        return Integer.parseInt(value);
    }

    private JsonObject toSummaryJson(DiagramPresentationElement dpe) {
        Diagram diagram = dpe != null ? dpe.getDiagram() : null;
        JsonObject json = new JsonObject();
        json.addProperty("id", diagram != null ? diagram.getID() : "");
        json.addProperty("name", dpe != null && dpe.getName() != null ? dpe.getName() : "");
        json.addProperty("type", dpe != null && dpe.getDiagramType() != null
                ? dpe.getDiagramType().getType() : RELATION_MAP_TYPE);
        if (diagram != null && diagram.getOwner() instanceof Element) {
            Element owner = (Element) diagram.getOwner();
            json.addProperty("ownerId", owner.getID());
            if (owner instanceof NamedElement) {
                json.addProperty("ownerName", ((NamedElement) owner).getName());
            }
        }
        return json;
    }

    private boolean isRelationMap(DiagramPresentationElement dpe) {
        return dpe != null
                && dpe.getDiagramType() != null
                && RELATION_MAP_TYPE.equals(dpe.getDiagramType().getType());
    }

    private Diagram resolveRelationMap(Project project, String relationMapId) {
        Object element = project.getElementByID(relationMapId);
        if (element instanceof Diagram) {
            Diagram diagram = (Diagram) element;
            DiagramPresentationElement dpe = project.getDiagram(diagram);
            if (isRelationMap(dpe)) {
                return diagram;
            }
        }
        throw new IllegalArgumentException("Relation Map not found: " + relationMapId);
    }

    private Element resolveElement(Project project, String elementId, String label) {
        Object element = project.getElementByID(elementId);
        if (element instanceof Element) {
            return (Element) element;
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

    private Integer optionalInt(JsonObject body, String key) {
        if (!body.has(key) || body.get(key).isJsonNull()) {
            return null;
        }
        return body.get(key).getAsInt();
    }

    private String describeException(Exception e) {
        String message = e.getMessage();
        if (message == null || message.isBlank()) {
            return e.getClass().getName();
        }
        return e.getClass().getName() + ": " + message;
    }

    private boolean optionalBoolean(JsonObject body, String key, boolean defaultValue) {
        if (!body.has(key) || body.get(key).isJsonNull()) {
            return defaultValue;
        }
        return body.get(key).getAsBoolean();
    }

    private void applyOptionalBoolean(JsonObject body, String key, BooleanSetter setter) {
        if (body.has(key) && !body.get(key).isJsonNull()) {
            setter.set(body.get(key).getAsBoolean());
        }
    }

    private static final class CriteriaTemplate {
        private final String key;
        private final String expression;
        private final String relationshipType;
        private final String direction;
        private final boolean verifiedWithUiDiff;
        private final String stereotypeName;
        private final String dslDirection;
        private final String displayName;

        private CriteriaTemplate(
                String key,
                String expression,
                String relationshipType,
                String direction,
                boolean verifiedWithUiDiff) {
            this.key = key;
            this.expression = expression;
            this.relationshipType = relationshipType;
            this.direction = direction;
            this.verifiedWithUiDiff = verifiedWithUiDiff;
            this.stereotypeName = null;
            this.dslDirection = null;
            this.displayName = null;
        }

        private CriteriaTemplate(
                String key,
                String relationshipType,
                String direction,
                boolean verifiedWithUiDiff,
                String stereotypeName,
                String dslDirection,
                String displayName) {
            this.key = key;
            this.expression = null;
            this.relationshipType = relationshipType;
            this.direction = direction;
            this.verifiedWithUiDiff = verifiedWithUiDiff;
            this.stereotypeName = stereotypeName;
            this.dslDirection = dslDirection;
            this.displayName = displayName;
        }

        private static CriteriaTemplate dsl(
                String key,
                String stereotypeName,
                String dslDirection,
                String displayName,
                String direction,
                boolean verifiedWithUiDiff) {
            return new CriteriaTemplate(
                    key,
                    stereotypeName,
                    direction,
                    verifiedWithUiDiff,
                    stereotypeName,
                    dslDirection,
                    displayName);
        }

        private String toExpression(Project project) {
            if (stereotypeName == null) {
                return expression;
            }
            return createDslCriteriaExpression(project, stereotypeName, dslDirection, displayName);
        }

        private JsonObject toJson() {
            JsonObject json = new JsonObject();
            json.addProperty("key", key);
            if (stereotypeName == null) {
                json.addProperty("rawExpression", expression);
                json.addProperty("expressionKind", "raw");
            } else {
                json.addProperty("rawExpression", relationshipType + ":" + direction);
                json.addProperty("expressionKind", "dslRelation");
                json.addProperty("stereotypeName", stereotypeName);
                json.addProperty("dslDirection", dslDirection);
                json.addProperty("displayName", displayName);
            }
            json.addProperty("relationshipType", relationshipType);
            json.addProperty("direction", direction);
            json.addProperty("verifiedWithUiDiff", verifiedWithUiDiff);
            return json;
        }
    }

    @FunctionalInterface
    private interface BooleanSetter {
        void set(boolean value);
    }

    private static final class GraphFrontierItem {
        private final Element element;
        private final int depth;

        private GraphFrontierItem(Element element, int depth) {
            this.element = element;
            this.depth = depth;
        }
    }

    private static final class GraphEdge {
        private final Element relationship;
        private final String traversalDirection;
        private final List<Element> sources;
        private final List<Element> targets;
        private final List<Element> relatedElements;
        private final List<Element> traversalTargets;

        private GraphEdge(
                Element relationship,
                String traversalDirection,
                Collection<? extends Element> sources,
                Collection<? extends Element> targets,
                Collection<? extends Element> relatedElements,
                Collection<? extends Element> traversalTargets) {
            this.relationship = relationship;
            this.traversalDirection = traversalDirection;
            this.sources = nonNullElements(sources);
            this.targets = nonNullElements(targets);
            this.relatedElements = nonNullElements(relatedElements);
            this.traversalTargets = nonNullElements(traversalTargets);
        }

        private static GraphEdge directed(
                Element relationship,
                String traversalDirection,
                Collection<? extends Element> sources,
                Collection<? extends Element> targets) {
            Collection<? extends Element> next = "incoming".equals(traversalDirection) ? sources : targets;
            return new GraphEdge(
                    relationship,
                    traversalDirection,
                    sources,
                    targets,
                    List.of(),
                    next);
        }

        private static GraphEdge undirected(
                Element relationship,
                String selfId,
                Collection<? extends Element> related) {
            List<Element> traversalTargets = new ArrayList<>();
            if (related != null) {
                for (Element element : related) {
                    if (element != null && !element.getID().equals(selfId)) {
                        traversalTargets.add(element);
                    }
                }
            }
            return new GraphEdge(
                    relationship,
                    "undirected",
                    List.of(),
                    List.of(),
                    related,
                    traversalTargets);
        }

        private static GraphEdge connector(Connector connector, String selfId) {
            List<Element> related = new ArrayList<>();
            Collection<ConnectorEnd> ends = connector.getEnd();
            if (ends != null) {
                for (ConnectorEnd end : ends) {
                    if (end == null) {
                        continue;
                    }
                    if (end.getRole() != null) {
                        related.add(end.getRole());
                    }
                    if (end.getPartWithPort() != null) {
                        related.add(end.getPartWithPort());
                    }
                }
            }
            return undirected(connector, selfId, related);
        }

        private JsonObject toJson(int depth) {
            JsonObject json = ElementSerializer.toJsonReference(relationship);
            json.addProperty("relationshipId", relationship.getID());
            json.addProperty("id", relationship.getID());
            json.addProperty("direction", traversalDirection);
            json.addProperty("depth", depth);
            json.add("sources", elementsToJsonArray(sources));
            json.add("targets", elementsToJsonArray(targets));
            json.add("relatedElements", elementsToJsonArray(relatedElements));
            json.add("traversalTargets", elementsToJsonArray(traversalTargets));
            return json;
        }

        private static JsonArray elementsToJsonArray(Collection<Element> elements) {
            JsonArray array = new JsonArray();
            if (elements != null) {
                for (Element element : elements) {
                    array.add(ElementSerializer.toJsonCompact(element));
                }
            }
            return array;
        }

        private static List<Element> nonNullElements(Collection<? extends Element> elements) {
            List<Element> result = new ArrayList<>();
            if (elements != null) {
                for (Element element : elements) {
                    if (element != null) {
                        result.add(element);
                    }
                }
            }
            return result;
        }
    }
}
