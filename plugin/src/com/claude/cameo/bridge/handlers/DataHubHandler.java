package com.claude.cameo.bridge.handlers;

import com.claude.cameo.bridge.HttpBridgeServer;
import com.claude.cameo.bridge.util.JsonHelper;
import com.claude.cameo.bridge.util.OptionalCapabilitySupport;
import com.google.gson.JsonArray;
import com.google.gson.JsonObject;
import com.sun.net.httpserver.HttpExchange;
import com.sun.net.httpserver.HttpHandler;

import java.io.IOException;

public class DataHubHandler implements HttpHandler {

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
            if ("GET".equals(method) && path.equals("/api/v1/datahub/capabilities")) {
                HttpBridgeServer.sendJson(exchange, 200, capabilities());
            } else if ("GET".equals(method) && path.equals("/api/v1/datahub/sources")) {
                handleSources(exchange);
            } else if ("POST".equals(method) && path.equals("/api/v1/datahub/sync-preview")) {
                handleSyncPreview(exchange);
            } else {
                HttpBridgeServer.sendError(exchange, 404, "NOT_FOUND", "Unknown endpoint: " + path);
            }
        } catch (Exception e) {
            HttpBridgeServer.sendError(exchange, 500, "DATAHUB_ERROR", e.getMessage());
        }
    }

    private JsonObject capabilities() {
        JsonObject response = OptionalCapabilitySupport.baseCapabilities("datahub", "probe-first");
        JsonObject probe = OptionalCapabilitySupport.classProbe(
                "com.nomagic.datahub.DataHubPlugin",
                "com.nomagic.magicdraw.datahub.DataHubPlugin");
        JsonArray dirs = OptionalCapabilitySupport.pluginDirectories("datahub", "doors", "enovia");
        boolean available = probe.get("allFound").getAsBoolean() || dirs.size() > 0;
        response.addProperty("available", available);
        response.addProperty("status", available ? "probe-required" : "missing-plugin");
        response.add("classProbe", probe);
        response.add("pluginDirectoriesFound", dirs);
        response.addProperty("sourceReadbackSupported", false);
        response.addProperty("syncWriteSupported", false);
        return response;
    }

    private void handleSources(HttpExchange exchange) throws IOException {
        JsonObject response = capabilities();
        response.addProperty("sourceInventoryMode", "diagnostic");
        response.add("sources", new JsonArray());
        response.addProperty("message", "Configured DataHub source listing requires installed DataHub APIs.");
        HttpBridgeServer.sendJson(exchange, 200, response);
    }

    private void handleSyncPreview(HttpExchange exchange) throws Exception {
        JsonObject body = JsonHelper.parseBody(exchange);
        JsonObject response = OptionalCapabilitySupport.previewAccepted(
                "datahub",
                body,
                "DataHub sync preview recorded. No external synchronization was performed.");
        response.add("capabilities", capabilities());
        HttpBridgeServer.sendJson(exchange, 200, response);
    }
}
