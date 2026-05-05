package com.claude.cameo.bridge.handlers;

import com.claude.cameo.bridge.HttpBridgeServer;
import com.claude.cameo.bridge.util.EdtDispatcher;
import com.claude.cameo.bridge.util.ElementSerializer;
import com.claude.cameo.bridge.util.JsonDiff;
import com.claude.cameo.bridge.util.JsonHelper;
import com.claude.cameo.bridge.util.PresentationSerializer;
import com.claude.cameo.bridge.util.PropertySerializer;
import com.claude.cameo.bridge.util.SnapshotStore;
import com.google.gson.JsonArray;
import com.google.gson.JsonObject;
import com.nomagic.magicdraw.core.Project;
import com.nomagic.magicdraw.uml.symbols.DiagramPresentationElement;
import com.nomagic.magicdraw.uml.symbols.PresentationElement;
import com.nomagic.magicdraw.visualization.relationshipmap.GraphUtils;
import com.nomagic.magicdraw.visualization.relationshipmap.model.settings.GraphSettings;
import com.nomagic.uml2.ext.magicdraw.classes.mdkernel.Diagram;
import com.nomagic.uml2.ext.magicdraw.classes.mdkernel.Element;

import com.sun.net.httpserver.HttpExchange;
import com.sun.net.httpserver.HttpHandler;

import java.io.IOException;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

public class SnapshotHandler implements HttpHandler {

    private static final String PREFIX = "/api/v1/snapshots/";

    @Override
    public void handle(HttpExchange exchange) throws IOException {
        try {
            String method = exchange.getRequestMethod();
            String path = exchange.getRequestURI().getPath();
            if ("OPTIONS".equals(method)) {
                exchange.getResponseHeaders().set("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS");
                exchange.getResponseHeaders().set("Access-Control-Allow-Headers", "Content-Type");
                exchange.sendResponseHeaders(204, -1);
                return;
            }
            if ("POST".equals(method) && path.equals("/api/v1/snapshots")) {
                handleCreate(exchange);
            } else if ("GET".equals(method) && path.equals("/api/v1/snapshots")) {
                handleList(exchange);
            } else if ("POST".equals(method) && path.equals("/api/v1/snapshots/diff")) {
                handleDiff(exchange);
            } else {
                String snapshotId = JsonHelper.extractPathParam(exchange, PREFIX);
                if (snapshotId == null) {
                    HttpBridgeServer.sendError(exchange, 404, "NOT_FOUND", "Unknown endpoint: " + path);
                } else if ("GET".equals(method)) {
                    handleGet(exchange, snapshotId);
                } else if ("DELETE".equals(method)) {
                    handleDelete(exchange, snapshotId);
                } else {
                    HttpBridgeServer.sendError(exchange, 405, "METHOD_NOT_ALLOWED", "Unsupported method");
                }
            }
        } catch (IllegalArgumentException e) {
            HttpBridgeServer.sendError(exchange, 400, "SNAPSHOT_BAD_REQUEST", e.getMessage());
        } catch (Exception e) {
            HttpBridgeServer.sendError(exchange, 500, "SNAPSHOT_ERROR", e.getMessage());
        }
    }

    private void handleCreate(HttpExchange exchange) throws Exception {
        JsonObject body = JsonHelper.parseBody(exchange);
        String targetType = JsonHelper.requireString(body, "targetType");
        String targetId = JsonHelper.optionalString(body, "targetId");
        String name = JsonHelper.optionalString(body, "name");
        boolean includeRaw = optionalBoolean(body, "includeRaw", false);
        boolean includePresentations = optionalBoolean(body, "includePresentations", true);
        boolean includeProperties = optionalBoolean(body, "includeProperties", true);

        JsonObject result = EdtDispatcher.read(project -> {
            JsonObject snapshot = new JsonObject();
            if (name != null) {
                snapshot.addProperty("name", name);
            }
            JsonObject target = new JsonObject();
            target.addProperty("targetType", targetType);
            if (targetId != null) {
                target.addProperty("targetId", targetId);
            }
            snapshot.add("target", target);
            snapshot.add("payload", capture(project, targetType, targetId, includeRaw, includePresentations, includeProperties));
            JsonObject summary = new JsonObject();
            summary.addProperty("includeRaw", includeRaw);
            summary.addProperty("includePresentations", includePresentations);
            summary.addProperty("includeProperties", includeProperties);
            snapshot.add("summary", summary);
            return SnapshotStore.create(snapshot);
        });
        HttpBridgeServer.sendJson(exchange, 201, result);
    }

    private void handleList(HttpExchange exchange) throws IOException {
        JsonArray snapshots = new JsonArray();
        for (JsonObject snapshot : SnapshotStore.list()) {
            snapshots.add(snapshot);
        }
        JsonObject response = new JsonObject();
        response.addProperty("count", snapshots.size());
        response.add("snapshots", snapshots);
        HttpBridgeServer.sendJson(exchange, 200, response);
    }

    private void handleGet(HttpExchange exchange, String snapshotId) throws IOException {
        JsonObject snapshot = SnapshotStore.get(snapshotId);
        if (snapshot == null) {
            HttpBridgeServer.sendError(exchange, 404, "NOT_FOUND", "Snapshot not found: " + snapshotId);
            return;
        }
        HttpBridgeServer.sendJson(exchange, 200, snapshot);
    }

    private void handleDelete(HttpExchange exchange, String snapshotId) throws IOException {
        JsonObject response = new JsonObject();
        response.addProperty("deleted", SnapshotStore.delete(snapshotId));
        response.addProperty("snapshotId", snapshotId);
        HttpBridgeServer.sendJson(exchange, 200, response);
    }

    private void handleDiff(HttpExchange exchange) throws IOException {
        JsonObject body = JsonHelper.parseBody(exchange);
        String beforeId = JsonHelper.requireString(body, "beforeSnapshotId");
        String afterId = JsonHelper.requireString(body, "afterSnapshotId");
        JsonObject before = SnapshotStore.get(beforeId);
        JsonObject after = SnapshotStore.get(afterId);
        if (before == null || after == null) {
            HttpBridgeServer.sendError(exchange, 404, "NOT_FOUND", "Both snapshots must exist");
            return;
        }
        int maxChanges = body.has("maxChanges") ? body.get("maxChanges").getAsInt() : 500;
        boolean includeDetails = optionalBoolean(body, "includeDetails", true);
        JsonArray ignorePaths = body.has("ignorePaths") && body.get("ignorePaths").isJsonArray()
                ? body.getAsJsonArray("ignorePaths") : new JsonArray();
        JsonObject response = JsonDiff.diff(
                before.get("payload"),
                after.get("payload"),
                JsonDiff.ignoreSet(ignorePaths),
                maxChanges,
                includeDetails);
        response.addProperty("beforeSnapshotId", beforeId);
        response.addProperty("afterSnapshotId", afterId);
        HttpBridgeServer.sendJson(exchange, 200, response);
    }

    private JsonObject capture(
            Project project,
            String targetType,
            String targetId,
            boolean includeRaw,
            boolean includePresentations,
            boolean includeProperties) {
        if ("project".equalsIgnoreCase(targetType)) {
            JsonObject json = new JsonObject();
            json.addProperty("name", project.getName());
            Element primary = project.getPrimaryModel();
            if (primary != null) {
                json.add("primaryModel", ElementSerializer.toJsonCompact(primary));
            }
            json.addProperty("diagramCount", project.getDiagrams() != null ? project.getDiagrams().size() : 0);
            return json;
        }
        if ("element".equalsIgnoreCase(targetType)) {
            return ElementSerializer.toJson(projectElement(project, targetId));
        }
        if ("diagram".equalsIgnoreCase(targetType) || "relationMap".equalsIgnoreCase(targetType)) {
            DiagramPresentationElement dpe = diagram(project, targetId);
            JsonObject json = new JsonObject();
            json.add("diagram", PresentationSerializer.diagramSummary(dpe));
            if ("relationMap".equalsIgnoreCase(targetType)) {
                json.add("relationMapSettings", relationMapSettings(dpe.getDiagram()));
            }
            if (includeProperties) {
                try {
                    json.add("diagramPresentationProperties",
                            PropertySerializer.serializeManager(dpe.getPropertyManager(), includeRaw, true));
                } catch (Exception e) {
                    JsonArray warnings = new JsonArray();
                    warnings.add("Could not read diagram property manager: " + e.getMessage());
                    json.add("warnings", warnings);
                }
            }
            if (includePresentations) {
                dpe.ensureLoaded();
                Map<String, String> parentById = new LinkedHashMap<>();
                List<PresentationElement> presentations = PresentationSerializer.flatten(dpe, parentById);
                json.addProperty("presentationCount", presentations.size());
                json.add("presentationCountsByType", PresentationSerializer.countByType(presentations));
                json.add("presentations", PresentationSerializer.summarizePresentations(presentations, parentById));
            }
            return json;
        }
        if ("ui".equalsIgnoreCase(targetType)) {
            JsonObject json = new JsonObject();
            json.addProperty("note", "Use /api/v1/ui/state for live UI details; snapshot captured project identity only.");
            json.addProperty("projectName", project.getName());
            return json;
        }
        throw new IllegalArgumentException("Unsupported snapshot targetType: " + targetType);
    }

    private JsonObject relationMapSettings(Diagram diagram) {
        GraphSettings settings = new GraphSettings(diagram);
        JsonObject json = new JsonObject();
        json.addProperty("settingsClassName", settings.getClass().getName());
        json.addProperty("initialized", settings.isInitialized());
        json.addProperty("depth", settings.getDepth());
        json.addProperty("layout", settings.getLayout());
        json.addProperty("legendEnabled", settings.isLegendEnabled());
        json.addProperty("valid", safeIsValid(settings));
        json.add("contextElement", settings.getContextElement() != null
                ? ElementSerializer.toJsonCompact(settings.getContextElement()) : new JsonObject());
        JsonArray criteria = new JsonArray();
        if (settings.getDependencyCriterion() != null) {
            for (String criterion : settings.getDependencyCriterion()) {
                criteria.add(criterion);
            }
        }
        json.add("dependencyCriteria", criteria);
        json.addProperty("criteriaCount", criteria.size());
        return json;
    }

    private boolean safeIsValid(GraphSettings settings) {
        try {
            return GraphUtils.isGraphSettingValid(settings);
        } catch (Exception e) {
            return false;
        }
    }

    private Element projectElement(Project project, String id) {
        Object element = project.getElementByID(id);
        if (element instanceof Element) {
            return (Element) element;
        }
        throw new IllegalArgumentException("Element not found: " + id);
    }

    private DiagramPresentationElement diagram(Project project, String id) {
        Object element = project.getElementByID(id);
        if (element instanceof Diagram) {
            DiagramPresentationElement dpe = project.getDiagram((Diagram) element);
            if (dpe != null) {
                return dpe;
            }
        }
        throw new IllegalArgumentException("Diagram not found: " + id);
    }

    private boolean optionalBoolean(JsonObject body, String key, boolean defaultValue) {
        if (!body.has(key) || body.get(key).isJsonNull()) {
            return defaultValue;
        }
        return body.get(key).getAsBoolean();
    }
}
