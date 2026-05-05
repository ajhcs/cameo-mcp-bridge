package com.claude.cameo.bridge.handlers;

import com.claude.cameo.bridge.HttpBridgeServer;
import com.claude.cameo.bridge.util.EdtDispatcher;
import com.claude.cameo.bridge.util.JsonHelper;
import com.claude.cameo.bridge.util.OptionalCapabilitySupport;
import com.claude.cameo.bridge.util.PresentationSerializer;
import com.google.gson.JsonArray;
import com.google.gson.JsonObject;
import com.nomagic.magicdraw.uml.symbols.DiagramPresentationElement;
import com.nomagic.uml2.ext.magicdraw.classes.mdkernel.Diagram;
import com.sun.net.httpserver.HttpExchange;
import com.sun.net.httpserver.HttpHandler;

import java.io.IOException;
import java.util.Collection;

public class TypedDiagramHandler implements HttpHandler {

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
            if ("GET".equals(method) && path.equals("/api/v1/typed-diagrams/capabilities")) {
                HttpBridgeServer.sendJson(exchange, 200, capabilities());
            } else if ("GET".equals(method) && path.equals("/api/v1/typed-diagrams")) {
                handleList(exchange);
            } else if ("POST".equals(method) && path.equals("/api/v1/typed-diagrams/inspect")) {
                handleInspect(exchange);
            } else if ("POST".equals(method) && path.equals("/api/v1/typed-diagrams/sequence/messages")) {
                handlePreview(exchange, "sequence-message");
            } else if ("POST".equals(method) && path.equals("/api/v1/typed-diagrams/state/transitions")) {
                handlePreview(exchange, "state-transition");
            } else if ("POST".equals(method) && path.equals("/api/v1/typed-diagrams/parametric/bindings")) {
                handlePreview(exchange, "parametric-binding");
            } else if ("POST".equals(method) && path.equals("/api/v1/typed-diagrams/legends/apply")) {
                handlePreview(exchange, "legend-apply");
            } else {
                HttpBridgeServer.sendError(exchange, 404, "NOT_FOUND", "Unknown endpoint: " + path);
            }
        } catch (Exception e) {
            HttpBridgeServer.sendError(exchange, 500, "TYPED_DIAGRAM_ERROR", e.getMessage());
        }
    }

    private JsonObject capabilities() {
        JsonObject response = OptionalCapabilitySupport.baseCapabilities("typedDiagrams", "native-read-plus-preview");
        response.addProperty("available", true);
        response.addProperty("status", "available");
        response.add("sequenceApiProbe", OptionalCapabilitySupport.classProbe(
                "com.nomagic.magicdraw.openapi.uml.PresentationElementsManager",
                "com.nomagic.magicdraw.uml.symbols.DiagramPresentationElement",
                "com.nomagic.uml2.ext.jmi.helpers.InteractionHelper"));
        response.addProperty("writeMode", "diagram-type-gated-preview");
        return response;
    }

    private void handleList(HttpExchange exchange) throws Exception {
        JsonObject result = EdtDispatcher.read(project -> {
            JsonArray diagrams = new JsonArray();
            Collection<DiagramPresentationElement> presentations = project.getDiagrams();
            if (presentations != null) {
                for (DiagramPresentationElement dpe : presentations) {
                    JsonObject entry = new JsonObject();
                    Diagram diagram = dpe.getDiagram();
                    entry.addProperty("id", diagram != null ? diagram.getID() : "");
                    entry.addProperty("name", dpe.getName());
                    entry.addProperty("diagramType", dpe.getDiagramType() != null
                            ? dpe.getDiagramType().getType()
                            : "");
                    diagrams.add(entry);
                }
            }
            JsonObject response = capabilities();
            response.addProperty("count", diagrams.size());
            response.add("diagrams", diagrams);
            return response;
        });
        HttpBridgeServer.sendJson(exchange, 200, result);
    }

    private void handleInspect(HttpExchange exchange) throws Exception {
        JsonObject body = JsonHelper.parseBody(exchange);
        String diagramId = JsonHelper.requireString(body, "diagramId");
        JsonObject result = EdtDispatcher.read(project -> {
            DiagramPresentationElement dpe = findDiagramById(project.getDiagrams(), diagramId);
            if (dpe == null) {
                throw new IllegalArgumentException("Diagram not found: " + diagramId);
            }
            dpe.ensureLoaded();
            JsonObject response = capabilities();
            response.addProperty("diagramId", diagramId);
            response.addProperty("name", dpe.getName());
            response.addProperty("diagramType", dpe.getDiagramType() != null
                    ? dpe.getDiagramType().getType()
                    : "");
            response.add("presentations", PresentationSerializer.summarizePresentations(
                    PresentationSerializer.flatten(dpe, null), null));
            return response;
        });
        HttpBridgeServer.sendJson(exchange, 200, result);
    }

    private void handlePreview(HttpExchange exchange, String operation) throws Exception {
        JsonObject body = JsonHelper.parseBody(exchange);
        JsonObject response = OptionalCapabilitySupport.previewAccepted(
                "typedDiagrams",
                body,
                "Typed diagram " + operation + " preview recorded. No diagram write was performed.");
        response.addProperty("operation", operation);
        response.addProperty("requiresDiagramTypeGate", true);
        response.add("capabilities", capabilities());
        HttpBridgeServer.sendJson(exchange, 200, response);
    }

    private DiagramPresentationElement findDiagramById(Collection<DiagramPresentationElement> diagrams, String diagramId) {
        if (diagrams == null) {
            return null;
        }
        for (DiagramPresentationElement dpe : diagrams) {
            Diagram diagram = dpe.getDiagram();
            if (diagram != null && diagramId.equals(diagram.getID())) {
                return dpe;
            }
        }
        return null;
    }
}
