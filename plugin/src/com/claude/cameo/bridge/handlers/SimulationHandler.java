package com.claude.cameo.bridge.handlers;

import com.claude.cameo.bridge.HttpBridgeServer;
import com.claude.cameo.bridge.util.EdtDispatcher;
import com.claude.cameo.bridge.util.ElementSerializer;
import com.claude.cameo.bridge.util.JsonHelper;
import com.claude.cameo.bridge.util.OptionalCapabilitySupport;
import com.google.gson.JsonArray;
import com.google.gson.JsonObject;
import com.nomagic.magicdraw.uml.Finder;
import com.nomagic.uml2.ext.magicdraw.classes.mdkernel.Element;
import com.nomagic.uml2.ext.magicdraw.classes.mdkernel.NamedElement;
import com.nomagic.uml2.ext.magicdraw.mdprofiles.Stereotype;
import com.nomagic.uml2.ext.jmi.helpers.StereotypesHelper;
import com.sun.net.httpserver.HttpExchange;
import com.sun.net.httpserver.HttpHandler;

import java.io.IOException;
import java.util.Collection;
import java.util.Locale;

public class SimulationHandler implements HttpHandler {

    private static final String SIMULATION_MANAGER = "com.nomagic.magicdraw.simulation.SimulationManager";
    private static final String SIMULATION_RESULT = "com.nomagic.magicdraw.simulation.execution.SimulationResult";
    private static final String SIMULATION_SESSION = "com.nomagic.magicdraw.simulation.execution.SimulationSession";

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

            if ("GET".equals(method) && path.equals("/api/v1/simulation/capabilities")) {
                handleCapabilities(exchange);
            } else if ("GET".equals(method) && path.equals("/api/v1/simulation/configurations")) {
                handleConfigurations(exchange);
            } else if ("POST".equals(method) && path.equals("/api/v1/simulation/run-preview")) {
                handlePreview(exchange);
            } else if ("POST".equals(method) && (path.equals("/api/v1/simulation/run")
                    || path.equals("/api/v1/simulation/run-async"))) {
                handleRun(exchange);
            } else if ("GET".equals(method) && path.startsWith("/api/v1/simulation/results/")) {
                handleResult(exchange, path.substring("/api/v1/simulation/results/".length()));
            } else if ("POST".equals(method) && path.startsWith("/api/v1/simulation/results/")
                    && path.endsWith("/terminate")) {
                String runId = path.substring("/api/v1/simulation/results/".length(),
                        path.length() - "/terminate".length());
                handleTerminate(exchange, runId);
            } else {
                HttpBridgeServer.sendError(exchange, 404, "NOT_FOUND", "Unknown endpoint: " + path);
            }
        } catch (IllegalArgumentException e) {
            HttpBridgeServer.sendError(exchange, 400, "SIMULATION_BAD_REQUEST", e.getMessage());
        } catch (Exception e) {
            HttpBridgeServer.sendError(exchange, 500, "SIMULATION_ERROR", e.getMessage());
        }
    }

    private void handleCapabilities(HttpExchange exchange) throws IOException {
        HttpBridgeServer.sendJson(exchange, 200, capabilities());
    }

    private JsonObject capabilities() {
        JsonObject response = OptionalCapabilitySupport.baseCapabilities("simulation", "probe-first");
        JsonObject probe = OptionalCapabilitySupport.classProbe(SIMULATION_MANAGER, SIMULATION_RESULT, SIMULATION_SESSION);
        boolean available = probe.get("allFound").getAsBoolean();
        response.addProperty("available", available);
        response.addProperty("status", available ? "available" : "missing-plugin");
        response.add("classProbe", probe);
        response.add("pluginDirectoriesFound", OptionalCapabilitySupport.pluginDirectories("simulation"));
        response.addProperty("executionEnabled", Boolean.getBoolean("cameo.bridge.simulation.execute.enabled"));
        response.addProperty("safeDefault", "No simulation execution without explicit allowExecute and live runtime proof.");
        return response;
    }

    private void handleConfigurations(HttpExchange exchange) throws Exception {
        JsonObject caps = capabilities();
        if (!caps.get("available").getAsBoolean()) {
            JsonObject response = OptionalCapabilitySupport.unsupported(
                    "simulation",
                    "Simulation Toolkit runtime classes were not found.",
                    "Install/enable Simulation Toolkit and rerun live_probe_simulation.py.");
            response.add("capabilities", caps);
            HttpBridgeServer.sendJson(exchange, 200, response);
            return;
        }

        JsonObject result = EdtDispatcher.read(project -> {
            JsonArray configurations = new JsonArray();
            Element root = project.getPrimaryModel();
            if (root != null) {
                Collection<? extends Element> elements = Finder.byTypeRecursively()
                        .find(root, new Class[]{Element.class});
                for (Element element : elements) {
                    if (looksSimulationConfiguration(element)) {
                        configurations.add(ElementSerializer.toJsonReference(element));
                    }
                }
            }
            JsonObject response = capabilities();
            response.addProperty("count", configurations.size());
            response.add("configurations", configurations);
            return response;
        });
        HttpBridgeServer.sendJson(exchange, 200, result);
    }

    private void handlePreview(HttpExchange exchange) throws Exception {
        JsonObject body = JsonHelper.parseBody(exchange);
        JsonObject response = OptionalCapabilitySupport.previewAccepted(
                "simulation",
                body,
                "Simulation run preview recorded. No executable model was run.");
        response.add("capabilities", capabilities());
        response.addProperty("requiresAllowExecute", true);
        response.addProperty("requiresRuntimeClasses", true);
        HttpBridgeServer.sendJson(exchange, 200, response);
    }

    private void handleRun(HttpExchange exchange) throws Exception {
        JsonObject body = JsonHelper.parseBody(exchange);
        JsonObject response = OptionalCapabilitySupport.unsupported(
                "simulation",
                "Simulation execution is disabled until runtime classes and a disposable executable model are validated.",
                "Use /api/v1/simulation/run-preview first, then live_validate_simulation.py with --allow-execute.");
        response.add("request", body);
        response.add("capabilities", capabilities());
        HttpBridgeServer.sendJson(exchange, 501, response);
    }

    private void handleResult(HttpExchange exchange, String runId) throws IOException {
        JsonObject response = new JsonObject();
        response.addProperty("runId", runId);
        response.addProperty("status", "not-found");
        response.addProperty("message", "Simulation jobs are not persisted until execution support is enabled.");
        HttpBridgeServer.sendJson(exchange, 404, response);
    }

    private void handleTerminate(HttpExchange exchange, String runId) throws IOException {
        JsonObject response = OptionalCapabilitySupport.unsupported(
                "simulation",
                "No active simulation job store exists in probe-first mode.",
                "Enable execution only after live simulation validation.");
        response.addProperty("runId", runId);
        HttpBridgeServer.sendJson(exchange, 404, response);
    }

    private boolean looksSimulationConfiguration(Element element) {
        StringBuilder text = new StringBuilder(element.getClass().getSimpleName()).append(' ');
        if (element instanceof NamedElement) {
            String name = ((NamedElement) element).getName();
            if (name != null) {
                text.append(name).append(' ');
            }
        }
        try {
            for (Stereotype stereotype : StereotypesHelper.getStereotypes(element)) {
                if (stereotype.getName() != null) {
                    text.append(stereotype.getName()).append(' ');
                }
            }
        } catch (Exception ignored) {
            // Best-effort discovery only.
        }
        String lower = text.toString().toLowerCase(Locale.ROOT);
        return lower.contains("simulation") || lower.contains("config") || lower.contains("parametric");
    }
}
