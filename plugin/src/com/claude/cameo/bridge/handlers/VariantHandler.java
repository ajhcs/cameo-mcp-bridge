package com.claude.cameo.bridge.handlers;

import com.claude.cameo.bridge.HttpBridgeServer;
import com.claude.cameo.bridge.util.JsonHelper;
import com.claude.cameo.bridge.util.OptionalCapabilitySupport;
import com.google.gson.JsonArray;
import com.google.gson.JsonObject;
import com.sun.net.httpserver.HttpExchange;
import com.sun.net.httpserver.HttpHandler;

import java.io.IOException;

public class VariantHandler implements HttpHandler {

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
            if ("GET".equals(method) && path.equals("/api/v1/variants/capabilities")) {
                HttpBridgeServer.sendJson(exchange, 200, capabilities());
            } else if ("POST".equals(method) && path.equals("/api/v1/variants/pattern/install-preview")) {
                handlePreview(exchange, "install-pattern");
            } else if ("POST".equals(method) && path.equals("/api/v1/variants/configurations/evaluate")) {
                handleEvaluate(exchange);
            } else if ("POST".equals(method) && path.equals("/api/v1/variants/configurations/export")) {
                handlePreview(exchange, "export-configuration");
            } else {
                HttpBridgeServer.sendError(exchange, 404, "NOT_FOUND", "Unknown endpoint: " + path);
            }
        } catch (Exception e) {
            HttpBridgeServer.sendError(exchange, 500, "VARIANT_ERROR", e.getMessage());
        }
    }

    private JsonObject capabilities() {
        JsonObject response = OptionalCapabilitySupport.baseCapabilities("variants", "bridge-owned-plus-native-probe");
        JsonArray dirs = OptionalCapabilitySupport.pluginDirectories(
                "variant", "variability", "productline", "product-line", "ple");
        response.addProperty("available", true);
        response.addProperty("bridgeOwnedAvailable", true);
        response.addProperty("nativeAvailable", dirs.size() > 0);
        response.addProperty("status", dirs.size() > 0 ? "native-plugin-detected" : "bridge-owned");
        response.addProperty("nativeWriteSupported", false);
        response.addProperty("configurationEvaluationMode", "bridge-owned-preview");
        response.add("pluginDirectoriesFound", dirs);
        response.add("classProbe", OptionalCapabilitySupport.classProbe(
                "com.nomagic.magicdraw.variants.VariantsPlugin",
                "com.nomagic.magicdraw.productline.ProductLinePlugin"));
        return response;
    }

    private void handlePreview(HttpExchange exchange, String operation) throws Exception {
        JsonObject body = JsonHelper.parseBody(exchange);
        JsonObject response = OptionalCapabilitySupport.previewAccepted(
                "variants",
                body,
                "Variant " + operation + " preview recorded. No model content was hidden, deleted, or suppressed.");
        response.addProperty("operation", operation);
        response.add("capabilities", capabilities());
        HttpBridgeServer.sendJson(exchange, 200, response);
    }

    private void handleEvaluate(HttpExchange exchange) throws Exception {
        JsonObject body = JsonHelper.parseBody(exchange);
        JsonObject response = new JsonObject();
        response.addProperty("family", "variants");
        response.addProperty("evaluated", true);
        response.addProperty("mode", "bridge-owned");
        response.addProperty("writePerformed", false);
        response.add("request", body);
        response.add("includedElements", new JsonArray());
        response.add("excludedElements", new JsonArray());
        response.add("warnings", new JsonArray());
        response.add("capabilities", capabilities());
        HttpBridgeServer.sendJson(exchange, 200, response);
    }
}
