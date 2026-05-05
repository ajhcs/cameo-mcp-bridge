package com.claude.cameo.bridge.handlers;

import com.claude.cameo.bridge.HttpBridgeServer;
import com.claude.cameo.bridge.util.EdtDispatcher;
import com.claude.cameo.bridge.util.JsonHelper;
import com.claude.cameo.bridge.util.PresentationSerializer;
import com.claude.cameo.bridge.util.PropertySerializer;
import com.google.gson.JsonArray;
import com.google.gson.JsonObject;
import com.nomagic.magicdraw.core.Project;
import com.nomagic.magicdraw.properties.PropertyManager;
import com.nomagic.magicdraw.uml.symbols.DiagramPresentationElement;
import com.nomagic.magicdraw.uml.symbols.PresentationElement;
import com.nomagic.uml2.ext.magicdraw.classes.mdkernel.Diagram;

import com.sun.net.httpserver.HttpExchange;
import com.sun.net.httpserver.HttpHandler;

import java.io.IOException;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

public class PropertyDumpHandler implements HttpHandler {

    private static final String PREFIX = "/api/v1/inspect/diagrams/";

    @Override
    public void handle(HttpExchange exchange) throws IOException {
        try {
            String method = exchange.getRequestMethod();
            String path = exchange.getRequestURI().getPath();
            if ("OPTIONS".equals(method)) {
                exchange.getResponseHeaders().set("Access-Control-Allow-Methods", "GET, OPTIONS");
                exchange.getResponseHeaders().set("Access-Control-Allow-Headers", "Content-Type");
                exchange.sendResponseHeaders(204, -1);
                return;
            }
            if (!"GET".equals(method)) {
                HttpBridgeServer.sendError(exchange, 405, "METHOD_NOT_ALLOWED", "Only GET is supported");
                return;
            }

            String diagramId = JsonHelper.extractPathParam(exchange, PREFIX);
            String subPath = JsonHelper.extractSubPath(exchange, PREFIX);
            if (diagramId != null && "properties".equals(subPath)) {
                handleDiagramProperties(exchange, diagramId);
            } else if (diagramId != null && subPath != null
                    && subPath.startsWith("presentations/") && subPath.endsWith("/properties")) {
                String presentationId = subPath.substring(
                        "presentations/".length(),
                        subPath.length() - "/properties".length());
                handlePresentationProperties(exchange, diagramId, presentationId);
            } else {
                HttpBridgeServer.sendError(exchange, 404, "NOT_FOUND", "Unknown endpoint: " + path);
            }
        } catch (IllegalArgumentException e) {
            HttpBridgeServer.sendError(exchange, 404, "NOT_FOUND", e.getMessage());
        } catch (Exception e) {
            HttpBridgeServer.sendError(exchange, 500, "PROPERTY_DUMP_ERROR", e.getMessage());
        }
    }

    private void handleDiagramProperties(HttpExchange exchange, String diagramId) throws Exception {
        Map<String, String> params = JsonHelper.parseQuery(exchange);
        boolean includeRaw = parseBoolean(params.get("includeRaw"), false);
        boolean includePresentationProperties = parseBoolean(params.get("includePresentationProperties"), false);
        boolean summaryOnly = parseBoolean(params.get("summaryOnly"), true);
        int limit = parseInt(params.get("limit"), 100);
        int offset = parseInt(params.get("offset"), 0);

        JsonObject result = EdtDispatcher.read(project -> {
            DiagramPresentationElement dpe = findDiagram(project, diagramId);
            JsonArray warnings = new JsonArray();
            try {
                dpe.ensureLoaded();
                warnings.add("Diagram ensureLoaded() was called before presentation inspection");
            } catch (Exception e) {
                warnings.add("ensureLoaded failed: " + e.getMessage());
            }

            JsonObject response = new JsonObject();
            response.add("diagram", PresentationSerializer.diagramSummary(dpe));
            Diagram diagram = dpe.getDiagram();
            response.add("diagramProperties", PropertySerializer.serializeValue(diagram, includeRaw, true));
            try {
                PropertyManager manager = dpe.getPropertyManager();
                response.add("diagramPresentationProperties",
                        PropertySerializer.serializeManager(manager, includeRaw, summaryOnly));
            } catch (Exception e) {
                warnings.add("Could not read diagram presentation property manager: " + e.getMessage());
            }

            Map<String, String> parentById = new LinkedHashMap<>();
            List<PresentationElement> presentations = PresentationSerializer.flatten(dpe, parentById);
            response.addProperty("presentationCount", presentations.size());
            response.add("presentationCountsByType", PresentationSerializer.countByType(presentations));

            JsonArray page = new JsonArray();
            int end = Math.min(presentations.size(), Math.max(0, offset) + Math.max(0, limit));
            for (int i = Math.max(0, offset); i < end; i++) {
                PresentationElement pe = presentations.get(i);
                page.add(includePresentationProperties
                        ? PresentationSerializer.presentationWithProperties(pe, parentById.get(pe.getID()), includeRaw, summaryOnly)
                        : PresentationSerializer.presentationSummary(pe, parentById.get(pe.getID())));
            }
            response.addProperty("limit", limit);
            response.addProperty("offset", offset);
            response.addProperty("returnedPresentationCount", page.size());
            response.add("presentations", page);
            response.add("warnings", warnings);
            return response;
        });
        HttpBridgeServer.sendJson(exchange, 200, result);
    }

    private void handlePresentationProperties(HttpExchange exchange, String diagramId, String presentationId) throws Exception {
        Map<String, String> params = JsonHelper.parseQuery(exchange);
        boolean includeRaw = parseBoolean(params.get("includeRaw"), false);
        boolean summaryOnly = parseBoolean(params.get("summaryOnly"), false);
        JsonObject result = EdtDispatcher.read(project -> {
            DiagramPresentationElement dpe = findDiagram(project, diagramId);
            dpe.ensureLoaded();
            Map<String, String> parentById = new LinkedHashMap<>();
            PresentationSerializer.flatten(dpe, parentById);
            PresentationElement target = PresentationSerializer.findById(dpe, presentationId);
            if (target == null) {
                throw new IllegalArgumentException("Presentation element not found: " + presentationId);
            }
            JsonObject response = new JsonObject();
            response.add("diagram", PresentationSerializer.diagramSummary(dpe));
            response.add("presentation",
                    PresentationSerializer.presentationWithProperties(target, parentById.get(target.getID()), includeRaw, summaryOnly));
            return response;
        });
        HttpBridgeServer.sendJson(exchange, 200, result);
    }

    private DiagramPresentationElement findDiagram(Project project, String diagramId) {
        Object element = project.getElementByID(diagramId);
        if (element instanceof Diagram) {
            DiagramPresentationElement dpe = project.getDiagram((Diagram) element);
            if (dpe != null) {
                return dpe;
            }
        }
        throw new IllegalArgumentException("Diagram not found: " + diagramId);
    }

    private boolean parseBoolean(String value, boolean defaultValue) {
        return value == null ? defaultValue : Boolean.parseBoolean(value);
    }

    private int parseInt(String value, int defaultValue) {
        if (value == null || value.isBlank()) {
            return defaultValue;
        }
        return Integer.parseInt(value);
    }
}
