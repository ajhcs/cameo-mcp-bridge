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
import com.nomagic.uml2.ext.magicdraw.mdprofiles.Profile;
import com.nomagic.uml2.ext.magicdraw.mdprofiles.Stereotype;
import com.sun.net.httpserver.HttpExchange;
import com.sun.net.httpserver.HttpHandler;

import java.io.IOException;
import java.util.Collection;
import java.util.Locale;

public class ExtensionProbeHandler implements HttpHandler {

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
            if ("GET".equals(method) && path.equals("/api/v1/extensions/capabilities")) {
                HttpBridgeServer.sendJson(exchange, 200, capabilities());
            } else if ("GET".equals(method) && path.equals("/api/v1/extensions/profiles")) {
                handleProfiles(exchange);
            } else if ("POST".equals(method) && path.equals("/api/v1/extensions/model-scan")) {
                handleModelScan(exchange);
            } else if ("POST".equals(method) && path.equals("/api/v1/extensions/pattern/install-preview")) {
                handleInstallPreview(exchange);
            } else if ("POST".equals(method) && path.equals("/api/v1/extensions/compliance-claim")) {
                handleComplianceClaim(exchange);
            } else {
                HttpBridgeServer.sendError(exchange, 404, "NOT_FOUND", "Unknown endpoint: " + path);
            }
        } catch (Exception e) {
            HttpBridgeServer.sendError(exchange, 500, "EXTENSION_PROBE_ERROR", e.getMessage());
        }
    }

    private JsonObject capabilities() {
        JsonObject response = OptionalCapabilitySupport.baseCapabilities("extensions", "profile-and-plugin-probe");
        JsonArray dirs = OptionalCapabilitySupport.pluginDirectories(
                "safety", "reliability", "cyber", "security", "risk", "fmea", "fmeca", "hazard");
        response.addProperty("available", true);
        response.addProperty("nativeExtensionDetected", dirs.size() > 0);
        response.addProperty("status", dirs.size() > 0 ? "native-plugin-detected" : "profile-scan-only");
        response.add("pluginDirectoriesFound", dirs);
        response.addProperty("readOnlyScanSupported", true);
        response.addProperty("nativePatternWriteSupported", false);
        response.addProperty("complianceClaimsSupported", false);
        return response;
    }

    private void handleProfiles(HttpExchange exchange) throws Exception {
        JsonObject result = EdtDispatcher.read(project -> scanProfiles(false));
        HttpBridgeServer.sendJson(exchange, 200, result);
    }

    private void handleModelScan(HttpExchange exchange) throws Exception {
        JsonObject body = JsonHelper.parseBody(exchange);
        JsonObject result = EdtDispatcher.read(project -> {
            JsonObject response = scanProfiles(true);
            response.add("request", body);
            response.addProperty("claim", "evidence-only");
            response.addProperty("complianceClaim", false);
            return response;
        });
        HttpBridgeServer.sendJson(exchange, 200, result);
    }

    private void handleInstallPreview(HttpExchange exchange) throws Exception {
        JsonObject body = JsonHelper.parseBody(exchange);
        JsonObject response = OptionalCapabilitySupport.previewAccepted(
                "extensions",
                body,
                "Extension pattern install preview recorded. No safety/cyber profile was installed.");
        response.add("capabilities", capabilities());
        HttpBridgeServer.sendJson(exchange, 200, response);
    }

    private void handleComplianceClaim(HttpExchange exchange) throws Exception {
        JsonObject body = JsonHelper.parseBody(exchange);
        JsonObject response = OptionalCapabilitySupport.unsupported(
                "extensions",
                "The bridge reports safety/cyber evidence and traceability gaps only; it does not make compliance claims.",
                "Use model-scan and native validation evidence as input to a human compliance process.");
        response.addProperty("refused", true);
        response.addProperty("code", "COMPLIANCE_CLAIM_REFUSED");
        response.add("request", body);
        HttpBridgeServer.sendJson(exchange, 403, response);
    }

    private JsonObject scanProfiles(boolean includeElements) {
        JsonObject response = capabilities();
        JsonArray profiles = new JsonArray();
        JsonArray stereotypes = new JsonArray();
        JsonArray elements = new JsonArray();
        com.nomagic.magicdraw.core.Project project = com.nomagic.magicdraw.core.Application.getInstance().getProject();
        Element root = project != null ? project.getPrimaryModel() : null;
        if (root != null) {
            Collection<? extends Element> profileElements = Finder.byTypeRecursively()
                    .find(root, new Class[]{Profile.class});
            for (Element element : profileElements) {
                if (matchesExtensionTerms(element)) {
                    profiles.add(ElementSerializer.toJsonReference(element));
                }
            }
            Collection<? extends Element> stereotypeElements = Finder.byTypeRecursively()
                    .find(root, new Class[]{Stereotype.class});
            for (Element element : stereotypeElements) {
                if (matchesExtensionTerms(element)) {
                    stereotypes.add(ElementSerializer.toJsonReference(element));
                }
            }
            if (includeElements) {
                Collection<? extends Element> all = Finder.byTypeRecursively().find(root, new Class[]{Element.class});
                for (Element element : all) {
                    if (matchesExtensionTerms(element) && elements.size() < 500) {
                        elements.add(ElementSerializer.toJsonReference(element));
                    }
                }
            }
        }
        response.addProperty("profileCount", profiles.size());
        response.addProperty("stereotypeCount", stereotypes.size());
        response.addProperty("elementFindingCount", elements.size());
        response.add("profiles", profiles);
        response.add("stereotypes", stereotypes);
        response.add("elements", elements);
        return response;
    }

    private boolean matchesExtensionTerms(Element element) {
        StringBuilder text = new StringBuilder(element.getClass().getSimpleName()).append(' ');
        if (element instanceof NamedElement) {
            String name = ((NamedElement) element).getName();
            if (name != null) {
                text.append(name).append(' ');
            }
        }
        String lower = text.toString().toLowerCase(Locale.ROOT);
        return lower.contains("safety")
                || lower.contains("cyber")
                || lower.contains("security")
                || lower.contains("risk")
                || lower.contains("hazard")
                || lower.contains("failure")
                || lower.contains("fmea")
                || lower.contains("control")
                || lower.contains("threat")
                || lower.contains("classification");
    }
}
