package com.claude.cameo.bridge.handlers;

import com.claude.cameo.bridge.HttpBridgeServer;
import com.claude.cameo.bridge.util.JsonHelper;
import com.claude.cameo.bridge.util.OptionalCapabilitySupport;
import com.google.gson.JsonArray;
import com.google.gson.JsonObject;
import com.sun.net.httpserver.HttpExchange;
import com.sun.net.httpserver.HttpHandler;

import java.io.IOException;

public class CriteriaHandler implements HttpHandler {

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
            if ("GET".equals(method) && path.equals("/api/v1/criteria/capabilities")) {
                HttpBridgeServer.sendJson(exchange, 200, capabilities());
            } else if ("GET".equals(method) && path.equals("/api/v1/criteria/templates")) {
                handleTemplates(exchange);
            } else if ("POST".equals(method) && path.equals("/api/v1/criteria/build")) {
                handleBuild(exchange);
            } else if ("POST".equals(method) && path.equals("/api/v1/criteria/parse")) {
                handleParse(exchange);
            } else if ("POST".equals(method) && path.equals("/api/v1/criteria/apply")) {
                handleApply(exchange);
            } else if ("POST".equals(method) && path.equals("/api/v1/criteria/capture-template-from-diff")) {
                handleCapture(exchange);
            } else {
                HttpBridgeServer.sendError(exchange, 404, "NOT_FOUND", "Unknown endpoint: " + path);
            }
        } catch (IllegalArgumentException e) {
            HttpBridgeServer.sendError(exchange, 400, "CRITERIA_BAD_REQUEST", e.getMessage());
        } catch (Exception e) {
            HttpBridgeServer.sendError(exchange, 500, "CRITERIA_ERROR", e.getMessage());
        }
    }

    private JsonObject capabilities() {
        JsonObject response = OptionalCapabilitySupport.baseCapabilities("criteria", "bridge-owned-plus-ui-diff");
        response.addProperty("available", true);
        response.addProperty("status", "available");
        response.addProperty("verifiedTemplateWrites", false);
        response.addProperty("sourceOfTruth", "UI snapshot/diff evidence");
        response.addProperty("relationMapRefreshDefault", false);
        response.add("nativeExpressionClasses", OptionalCapabilitySupport.classProbe(
                "com.nomagic.magicdraw.expressions.specification.ExpressionSpecification",
                "com.nomagic.magicdraw.expressions.specification.ExpressionSpecificationUtil",
                "com.nomagic.magicdraw.expressions.specification.DSLRelationExpressionSpecification"));
        return response;
    }

    private void handleTemplates(HttpExchange exchange) throws IOException {
        JsonArray templates = new JsonArray();
        templates.add(template("refine.targetToSource", "Refine target-to-source", "relationMap",
                "Refine", "targetToSource", true));
        templates.add(template("refine.both", "Refine both directions", "relationMap",
                "Refine", "both", true));
        templates.add(template("deriveReqt.targetToSource", "DeriveReqt target-to-source", "relationMap",
                "DeriveReqt", "targetToSource", true));
        templates.add(template("deriveReqt.both", "DeriveReqt both directions", "relationMap",
                "DeriveReqt", "both", true));
        templates.add(template("satisfy.both", "Satisfy relationships", "relationMap",
                "Satisfy", "both", true));
        templates.add(template("allocate.both", "Allocated to/from", "relationMap",
                "Allocate", "both", true));
        templates.add(template("dependency.direct", "Trace direct dependencies", "relationMap,matrix,table",
                "Dependency", "both", false));
        templates.add(template("satisfy.sourceToTarget", "Satisfy source-to-target", "relationMap",
                "Satisfy", "sourceToTarget", false));
        templates.add(template("allocate.sourceToTarget", "Allocate source-to-target", "relationMap",
                "Allocate", "sourceToTarget", false));
        JsonObject response = capabilities();
        response.addProperty("count", templates.size());
        response.add("templates", templates);
        HttpBridgeServer.sendJson(exchange, 200, response);
    }

    private void handleBuild(HttpExchange exchange) throws Exception {
        JsonObject body = JsonHelper.parseBody(exchange);
        JsonObject response = new JsonObject();
        response.addProperty("built", true);
        response.addProperty("verifiedWithUiDiff", isUiVerified(JsonHelper.optionalString(body, "id")));
        response.addProperty("writePerformed", false);
        response.add("request", body);
        response.add("criteriaExpression", buildExpression(body));
        response.add("capabilities", capabilities());
        HttpBridgeServer.sendJson(exchange, 200, response);
    }

    private void handleParse(HttpExchange exchange) throws Exception {
        JsonObject body = JsonHelper.parseBody(exchange);
        JsonObject response = new JsonObject();
        response.addProperty("parsed", true);
        response.addProperty("verifiedWithUiDiff", false);
        response.add("request", body);
        response.add("capabilities", capabilities());
        HttpBridgeServer.sendJson(exchange, 200, response);
    }

    private void handleApply(HttpExchange exchange) throws Exception {
        JsonObject body = JsonHelper.parseBody(exchange);
        JsonObject response = OptionalCapabilitySupport.unsupported(
                "criteria",
                "Criteria writes are gated until UI-created native expressions are captured and replayed by snapshot diff.",
                "Run capture-template-from-diff after creating the expression in CATIA UI.");
        response.add("request", body);
        response.add("capabilities", capabilities());
        HttpBridgeServer.sendJson(exchange, 403, response);
    }

    private void handleCapture(HttpExchange exchange) throws Exception {
        JsonObject body = JsonHelper.parseBody(exchange);
        JsonObject response = OptionalCapabilitySupport.previewAccepted(
                "criteria",
                body,
                "Criteria capture request recorded. Use snapshot IDs and diff evidence to promote this into a verified template.");
        response.addProperty("verifiedWithUiDiff", false);
        response.addProperty("requiresBeforeSnapshotId", true);
        response.addProperty("requiresAfterSnapshotId", true);
        response.add("capabilities", capabilities());
        HttpBridgeServer.sendJson(exchange, 200, response);
    }

    private JsonObject template(String id, String description, String targets,
            String relationshipKind, String direction, boolean verifiedWithUiDiff) {
        JsonObject json = new JsonObject();
        json.addProperty("id", id);
        json.addProperty("description", description);
        json.addProperty("targetKinds", targets);
        json.addProperty("verifiedWithUiDiff", verifiedWithUiDiff);
        json.addProperty("relationshipKind", relationshipKind);
        json.addProperty("direction", direction);
        json.add("expression", buildExpression(json));
        return json;
    }

    private JsonObject buildExpression(JsonObject body) {
        JsonObject expression = new JsonObject();
        expression.addProperty("mode", "bridge-owned-template");
        String id = JsonHelper.optionalString(body, "id");
        expression.addProperty("verifiedWithUiDiff", isUiVerified(id));
        expression.addProperty("relationshipKind", JsonHelper.optionalString(body, "relationshipKind") != null
                ? JsonHelper.optionalString(body, "relationshipKind")
                : relationshipKindFromId(id));
        expression.addProperty("direction", JsonHelper.optionalString(body, "direction") != null
                ? JsonHelper.optionalString(body, "direction")
                : "both");
        return expression;
    }

    private boolean isUiVerified(String id) {
        if (id == null) {
            return false;
        }
        return "refine.targetToSource".equals(id)
                || "refine.both".equals(id)
                || "deriveReqt.targetToSource".equals(id)
                || "deriveReqt.both".equals(id)
                || "satisfy.both".equals(id)
                || "allocate.both".equals(id)
                || "allocatedTo".equals(id);
    }

    private String relationshipKindFromId(String id) {
        if (id == null || id.isEmpty()) {
            return "";
        }
        int dot = id.indexOf('.');
        return dot > 0 ? id.substring(0, dot) : id;
    }
}
