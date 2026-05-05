package com.claude.cameo.bridge.handlers;

import com.claude.cameo.bridge.HttpBridgeServer;
import com.claude.cameo.bridge.util.EdtDispatcher;
import com.claude.cameo.bridge.util.JsonHelper;
import com.claude.cameo.bridge.util.OptionalCapabilitySupport;
import com.claude.cameo.bridge.util.PropertySerializer;
import com.google.gson.JsonArray;
import com.google.gson.JsonObject;
import com.nomagic.magicdraw.core.project.ProjectDescriptor;
import com.nomagic.magicdraw.core.project.ProjectDescriptorsFactory;
import com.sun.net.httpserver.HttpExchange;
import com.sun.net.httpserver.HttpHandler;

import java.io.IOException;
import java.lang.reflect.Method;

public class TeamworkHandler implements HttpHandler {

    private static final String ESI_UTILS = "com.nomagic.magicdraw.esi.EsiUtils";

    @Override
    public void handle(HttpExchange exchange) throws IOException {
        try {
            String method = exchange.getRequestMethod();
            String path = exchange.getRequestURI().getPath();
            if ("OPTIONS".equals(method)) {
                exchange.getResponseHeaders().set("Access-Control-Allow-Methods", "GET, POST, OPTIONS");
                exchange.getResponseHeaders().set("Access-Control-Allow-Headers", "Content-Type");
                exchange.sendResponseHeaders(204, -1);
                return;
            }

            if ("GET".equals(method) && path.equals("/api/v1/teamwork/capabilities")) {
                handleCapabilities(exchange);
            } else if ("GET".equals(method) && path.equals("/api/v1/teamwork/project")) {
                handleProject(exchange);
            } else if ("GET".equals(method) && path.equals("/api/v1/teamwork/descriptors")) {
                handleDescriptors(exchange);
            } else if ("GET".equals(method) && path.equals("/api/v1/teamwork/branches")) {
                handleReadOnlyPlaceholder(exchange, "branches");
            } else if ("GET".equals(method) && path.equals("/api/v1/teamwork/history")) {
                handleReadOnlyPlaceholder(exchange, "history");
            } else if ("GET".equals(method) && path.equals("/api/v1/teamwork/locks")) {
                handleReadOnlyPlaceholder(exchange, "locks");
            } else if ("POST".equals(method) && path.equals("/api/v1/teamwork/update-preview")) {
                handlePreview(exchange, "update");
            } else if ("POST".equals(method) && path.equals("/api/v1/teamwork/commit-preview")) {
                handlePreview(exchange, "commit");
            } else if ("POST".equals(method) && path.equals("/api/v1/teamwork/commit")) {
                handleCommit(exchange);
            } else {
                HttpBridgeServer.sendError(exchange, 404, "NOT_FOUND", "Unknown endpoint: " + path);
            }
        } catch (IllegalArgumentException e) {
            HttpBridgeServer.sendError(exchange, 400, "TEAMWORK_BAD_REQUEST", e.getMessage());
        } catch (Exception e) {
            HttpBridgeServer.sendError(exchange, 500, "TEAMWORK_ERROR", e.getMessage());
        }
    }

    private void handleCapabilities(HttpExchange exchange) throws IOException {
        HttpBridgeServer.sendJson(exchange, 200, capabilities());
    }

    private JsonObject capabilities() {
        JsonObject response = OptionalCapabilitySupport.baseCapabilities("teamwork", "native-readonly");
        JsonObject probe = OptionalCapabilitySupport.classProbe(ESI_UTILS);
        response.addProperty("available", probe.get("allFound").getAsBoolean());
        response.addProperty("status", probe.get("allFound").getAsBoolean() ? "available" : "missing-class");
        response.add("classProbe", probe);
        response.add("pluginDirectoriesFound", OptionalCapabilitySupport.pluginDirectories("teamwork", "twcloud", "esi"));
        response.addProperty("writeSupported", false);
        response.addProperty("writeReason", "Commit/update remain gated until disposable Teamwork project validation exists.");
        response.addProperty("descriptorReadSupported", true);
        response.addProperty("branchHistoryLockReadSupported", false);
        JsonArray readRoutes = new JsonArray();
        readRoutes.add("GET /api/v1/teamwork/project");
        readRoutes.add("GET /api/v1/teamwork/descriptors");
        readRoutes.add("GET /api/v1/teamwork/branches");
        readRoutes.add("GET /api/v1/teamwork/history");
        readRoutes.add("GET /api/v1/teamwork/locks");
        response.add("readRoutes", readRoutes);
        return response;
    }

    private void handleProject(HttpExchange exchange) throws Exception {
        JsonObject result = EdtDispatcher.read(project -> {
            JsonObject response = capabilities();
            response.addProperty("projectMode", project.isRemote() ? "teamwork" : "local");
            ProjectDescriptor descriptor = ProjectDescriptorsFactory.getDescriptorForProject(project);
            if (descriptor != null) {
                JsonObject descriptorJson = new JsonObject();
                descriptorJson.addProperty("className", descriptor.getClass().getName());
                descriptorJson.addProperty("string", descriptor.toString());
                descriptorJson.add("properties", PropertySerializer.serializeValue(descriptor, false, false));
                response.add("descriptor", descriptorJson);
            }
            response.add("esiDiagnostics", esiDiagnostics());
            return response;
        });
        HttpBridgeServer.sendJson(exchange, 200, result);
    }

    private void handleDescriptors(HttpExchange exchange) throws Exception {
        JsonObject result = EdtDispatcher.read(project -> {
            JsonObject response = capabilities();
            response.addProperty("authenticatedDiscoveryAttempted", true);
            try {
                Class<?> cls = Class.forName(ESI_UTILS, false, Thread.currentThread().getContextClassLoader());
                Method method = cls.getMethod("getRemoteProjectDescriptors");
                Object value = method.invoke(null);
                response.add("descriptors", PropertySerializer.serializeValue(value, true, false));
                response.addProperty("status", "available");
            } catch (Exception e) {
                response.addProperty("status", "auth-or-server-unavailable");
                response.addProperty("reason", e.getClass().getName() + ": "
                        + OptionalCapabilitySupport.safe(e.getMessage()));
                response.add("descriptors", new JsonArray());
            }
            return response;
        });
        HttpBridgeServer.sendJson(exchange, 200, result);
    }

    private void handleReadOnlyPlaceholder(HttpExchange exchange, String target) throws Exception {
        JsonObject result = EdtDispatcher.read(project -> {
            JsonObject response = capabilities();
            response.addProperty("target", target);
            response.addProperty("projectMode", project.isRemote() ? "teamwork" : "local");
            response.addProperty("available", project.isRemote());
            response.addProperty("typedReadbackSupported", false);
            response.addProperty("status", project.isRemote() ? "probe-required" : "local-project");
            response.addProperty("message", "Native " + target
                    + " serialization requires live Teamwork server evidence before typed output is claimed.");
            return response;
        });
        HttpBridgeServer.sendJson(exchange, 200, result);
    }

    private void handlePreview(HttpExchange exchange, String operation) throws Exception {
        JsonObject body = JsonHelper.parseBody(exchange);
        JsonObject response = OptionalCapabilitySupport.previewAccepted(
                "teamwork",
                body,
                "Teamwork " + operation + " preview recorded. No server write was performed.");
        response.addProperty("operation", operation);
        response.addProperty("approvalTokenIssued", false);
        response.addProperty("writeEnabled", false);
        response.addProperty("requiredGate", "Disposable Teamwork project validation plus validationGate=pass");
        HttpBridgeServer.sendJson(exchange, 200, response);
    }

    private void handleCommit(HttpExchange exchange) throws Exception {
        JsonObject body = JsonHelper.parseBody(exchange);
        JsonObject response = OptionalCapabilitySupport.unsupported(
                "teamwork",
                "Commit is disabled until preview/readback is proven against a disposable Teamwork project.",
                "Run /api/v1/teamwork/commit-preview and live_validate_teamwork_readonly.py first.");
        response.add("request", body);
        HttpBridgeServer.sendJson(exchange, 403, response);
    }

    private JsonObject esiDiagnostics() {
        JsonObject diagnostics = new JsonObject();
        try {
            Class<?> cls = Class.forName(ESI_UTILS, false, Thread.currentThread().getContextClassLoader());
            for (String methodName : new String[]{"getLoggedUserName", "getServerInfo"}) {
                try {
                    Method method = cls.getMethod(methodName);
                    diagnostics.add(methodName, PropertySerializer.serializeValue(method.invoke(null), true, false));
                } catch (Exception e) {
                    diagnostics.addProperty(methodName + "Error", e.getClass().getName() + ": "
                            + OptionalCapabilitySupport.safe(e.getMessage()));
                }
            }
        } catch (Exception e) {
            diagnostics.addProperty("error", e.getClass().getName() + ": "
                    + OptionalCapabilitySupport.safe(e.getMessage()));
        }
        return diagnostics;
    }
}
