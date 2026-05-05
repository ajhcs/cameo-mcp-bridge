package com.claude.cameo.bridge.handlers;

import com.claude.cameo.bridge.HttpBridgeServer;
import com.claude.cameo.bridge.util.JsonHelper;
import com.google.gson.JsonArray;
import com.google.gson.JsonObject;
import com.sun.net.httpserver.HttpExchange;
import com.sun.net.httpserver.HttpHandler;

import java.io.File;
import java.io.IOException;
import java.util.List;
import java.util.Locale;

/**
 * Probe-first route family for optional CATIA/Cameo product surfaces.
 *
 * These endpoints intentionally do not compile against optional product APIs.
 * They expose stable detection, dry-run, and refusal contracts first so the MCP
 * layer can fail closed before native handlers are promoted.
 */
public class AdvancedCapabilityHandler implements HttpHandler {

    private static final List<FeatureSpec> FEATURES = List.of(
            new FeatureSpec("validation", "native",
                    List.of("com.nomagic.magicdraw.validation.ValidationHelper",
                            "com.nomagic.magicdraw.validation.ValidationRunData",
                            "com.nomagic.magicdraw.validation.RuleViolationResult"),
                    List.of()),
            new FeatureSpec("reports", "optional-native",
                    List.of("com.nomagic.magicdraw.magicreport.helper.TemplateHelper",
                            "com.nomagic.magicdraw.magicreport.GenerateTask"),
                    List.of("com.nomagic.magicdraw.reportwizard")),
            new FeatureSpec("requirements", "optional-native",
                    List.of("com.nomagic.requirements.reqif.ReqIFUtils",
                            "com.nomagic.requirements.reqif.mapping.ReqIFMappingManager"),
                    List.of("com.nomagic.requirements")),
            new FeatureSpec("simulation", "probe-only",
                    List.of("com.nomagic.magicdraw.simulation.SimulationManager",
                            "com.nomagic.magicdraw.simulation.execution.SimulationResult"),
                    List.of("simulation")),
            new FeatureSpec("teamwork", "read-only-probe",
                    List.of("com.nomagic.magicdraw.esi.EsiUtils"),
                    List.of("teamwork", "collaboration")),
            new FeatureSpec("datahub", "probe-only",
                    List.of("com.nomagic.datahub.DataHubPlugin"),
                    List.of("datahub")),
            new FeatureSpec("variants", "probe-only",
                    List.of("com.nomagic.magicdraw.variants.VariantsPlugin"),
                    List.of("variant", "productline", "product-line")),
            new FeatureSpec("extensions", "read-only-probe",
                    List.of("com.nomagic.magicdraw.safety.SafetyPlugin",
                            "com.nomagic.magicdraw.cyber.CyberPlugin"),
                    List.of("safety", "cyber"))
    );

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

            FeatureSpec feature = featureForPath(path);
            if (feature == null) {
                HttpBridgeServer.sendError(exchange, 404, "NOT_FOUND", "Unknown advanced capability endpoint: " + path);
                return;
            }

            if ("GET".equals(method) && path.endsWith("/capabilities")) {
                HttpBridgeServer.sendJson(exchange, 200, capabilityResponse(feature));
            } else if ("GET".equals(method)) {
                HttpBridgeServer.sendJson(exchange, 200, readOnlyPlaceholder(feature, path));
            } else if ("POST".equals(method)) {
                JsonObject body = JsonHelper.parseBody(exchange);
                HttpBridgeServer.sendJson(exchange, 200, guardedActionPlaceholder(feature, path, body));
            } else {
                HttpBridgeServer.sendError(exchange, 405, "METHOD_NOT_ALLOWED",
                        "Method " + method + " not allowed for " + path);
            }
        } catch (IllegalArgumentException e) {
            HttpBridgeServer.sendError(exchange, 400, "ADVANCED_BAD_REQUEST", e.getMessage());
        } catch (Exception e) {
            HttpBridgeServer.sendError(exchange, 500, "ADVANCED_CAPABILITY_ERROR", e.getMessage());
        }
    }

    private FeatureSpec featureForPath(String path) {
        for (FeatureSpec feature : FEATURES) {
            if (path.startsWith("/api/v1/" + feature.name + "/")) {
                return feature;
            }
        }
        return null;
    }

    private JsonObject readOnlyPlaceholder(FeatureSpec feature, String path) {
        JsonObject response = baseResponse(feature, path);
        if ("teamwork".equals(feature.name) && path.endsWith("/project")) {
            response.addProperty("readOnly", true);
            response.addProperty("projectMode", "unknown");
            response.addProperty("message", "Teamwork project descriptor introspection is route-stable but awaits live native API proof.");
            return response;
        }
        response.addProperty("count", 0);
        response.add("items", new JsonArray());
        response.add("capabilityProbe", capabilityResponse(feature));
        response.addProperty("message", "Native readback is not promoted yet; use the capability probe evidence first.");
        return response;
    }

    private JsonObject guardedActionPlaceholder(FeatureSpec feature, String path, JsonObject body) {
        JsonObject response = baseResponse(feature, path);
        response.add("requestEcho", body);
        response.add("capabilityProbe", capabilityResponse(feature));
        if ("extensions".equals(feature.name) && path.endsWith("/compliance-claim")) {
            response.addProperty("refused", true);
            response.addProperty("code", "COMPLIANCE_CLAIM_REFUSED");
            response.addProperty("message", "The bridge reports evidence gaps only; it will not claim safety, cyber, regulatory, or certification compliance.");
            return response;
        }
        response.addProperty("dryRun", true);
        response.addProperty("executed", false);
        response.addProperty("message", "This endpoint is intentionally preview/probe-only until native live evidence promotes it.");
        return response;
    }

    private JsonObject capabilityResponse(FeatureSpec feature) {
        JsonObject response = baseResponse(feature, "/api/v1/" + feature.name + "/capabilities");
        JsonArray classesFound = new JsonArray();
        JsonArray classesMissing = new JsonArray();
        for (String className : feature.classNames) {
            if (classAvailable(className)) {
                classesFound.add(className);
            } else {
                classesMissing.add(className);
            }
        }

        JsonArray pluginDirs = pluginDirectories(feature.pluginHints);
        boolean installed = feature.pluginHints.isEmpty() || pluginDirs.size() > 0;
        boolean classesAvailable = classesMissing.size() == 0;
        boolean available = installed && classesAvailable;
        response.addProperty("available", available);
        response.addProperty("installed", installed);
        response.addProperty("licensed", "unknown");
        response.addProperty("mode", available ? feature.mode : "unsupported");
        response.add("classesFound", classesFound);
        response.add("classesMissing", classesMissing);
        response.add("pluginDirectoriesFound", pluginDirs);
        JsonArray warnings = new JsonArray();
        if (!installed) {
            warnings.add("No matching plugin directory was found under the local CATIA/Cameo plugins folder.");
        }
        if (!classesAvailable) {
            warnings.add("One or more expected native API classes were not loadable from the bridge classloader.");
        }
        if (available && !"validation".equals(feature.name)) {
            warnings.add("Capability probe is positive; typed native operations still require live validation before writes are enabled.");
        }
        response.add("warnings", warnings);
        response.addProperty("nextProbe", "/api/v1/probes/execute");
        return response;
    }

    private JsonObject baseResponse(FeatureSpec feature, String path) {
        JsonObject response = new JsonObject();
        response.addProperty("feature", feature.name);
        response.addProperty("path", path);
        return response;
    }

    private boolean classAvailable(String className) {
        try {
            Class.forName(className, false, Thread.currentThread().getContextClassLoader());
            return true;
        } catch (ClassNotFoundException | LinkageError | SecurityException e) {
            return false;
        }
    }

    private JsonArray pluginDirectories(List<String> hints) {
        JsonArray matches = new JsonArray();
        if (hints.isEmpty()) {
            return matches;
        }
        File pluginRoot = new File(cameoHome(), "plugins");
        File[] children = pluginRoot.listFiles(File::isDirectory);
        if (children == null) {
            return matches;
        }
        for (File child : children) {
            String name = child.getName().toLowerCase(Locale.ROOT);
            for (String hint : hints) {
                if (name.contains(hint.toLowerCase(Locale.ROOT))) {
                    matches.add(child.getAbsolutePath());
                    break;
                }
            }
        }
        return matches;
    }

    private String cameoHome() {
        String configured = System.getProperty("cameo.home");
        if (configured == null || configured.isEmpty()) {
            configured = System.getenv("CAMEO_HOME");
        }
        if (configured == null || configured.isEmpty()) {
            configured = "D:/DevTools/CatiaMagic";
        }
        return configured;
    }

    private static final class FeatureSpec {
        final String name;
        final String mode;
        final List<String> classNames;
        final List<String> pluginHints;

        FeatureSpec(String name, String mode, List<String> classNames, List<String> pluginHints) {
            this.name = name;
            this.mode = mode;
            this.classNames = classNames;
            this.pluginHints = pluginHints;
        }
    }
}
