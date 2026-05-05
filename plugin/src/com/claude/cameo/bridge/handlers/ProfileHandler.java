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
import com.nomagic.uml2.ext.magicdraw.mdprofiles.Profile;
import com.nomagic.uml2.ext.magicdraw.mdprofiles.Stereotype;
import com.sun.net.httpserver.HttpExchange;
import com.sun.net.httpserver.HttpHandler;

import java.io.IOException;
import java.util.Collection;

public class ProfileHandler implements HttpHandler {

    @Override
    public void handle(HttpExchange exchange) throws IOException {
        try {
            String method = exchange.getRequestMethod();
            String path = exchange.getRequestURI().getPath();
            if ("OPTIONS".equals(method)) {
                exchange.getResponseHeaders().set("Access-Control-Allow-Methods", "GET, POST, PUT, OPTIONS");
                exchange.getResponseHeaders().set("Access-Control-Allow-Headers", "Content-Type");
                exchange.sendResponseHeaders(204, -1);
                return;
            }
            if ("GET".equals(method) && path.equals("/api/v1/profiles/capabilities")) {
                HttpBridgeServer.sendJson(exchange, 200, capabilities());
            } else if ("POST".equals(method) && path.equals("/api/v1/profiles/create")) {
                handlePreview(exchange, "profile-create");
            } else if ("POST".equals(method) && path.equals("/api/v1/profiles/stereotypes/create")) {
                handlePreview(exchange, "stereotype-create");
            } else if ("POST".equals(method) && path.equals("/api/v1/profiles/tags/create")) {
                handlePreview(exchange, "tag-create");
            } else if ("POST".equals(method) && path.equals("/api/v1/profiles/apply")) {
                handlePreview(exchange, "profile-apply");
            } else if ("PUT".equals(method) && path.equals("/api/v1/profiles/tags")) {
                handlePreview(exchange, "tag-set");
            } else if ("POST".equals(method) && path.equals("/api/v1/profiles/export-summary")) {
                handleExportSummary(exchange);
            } else {
                HttpBridgeServer.sendError(exchange, 404, "NOT_FOUND", "Unknown endpoint: " + path);
            }
        } catch (Exception e) {
            HttpBridgeServer.sendError(exchange, 500, "PROFILE_ERROR", e.getMessage());
        }
    }

    private JsonObject capabilities() {
        JsonObject response = OptionalCapabilitySupport.baseCapabilities("profiles", "core-profile-api");
        response.addProperty("available", true);
        response.addProperty("status", "available");
        response.addProperty("writeMode", "preview-first");
        response.addProperty("summaryReadSupported", true);
        response.addProperty("typedProfileWriteSupported", false);
        response.add("classProbe", OptionalCapabilitySupport.classProbe(
                "com.nomagic.uml2.ext.magicdraw.mdprofiles.Profile",
                "com.nomagic.uml2.ext.magicdraw.mdprofiles.Stereotype",
                "com.nomagic.uml2.ext.jmi.helpers.StereotypesHelper",
                "com.nomagic.uml2.ext.jmi.helpers.TagsHelper"));
        return response;
    }

    private void handlePreview(HttpExchange exchange, String operation) throws Exception {
        JsonObject body = JsonHelper.parseBody(exchange);
        JsonObject response = OptionalCapabilitySupport.previewAccepted(
                "profiles",
                body,
                "Profile operation preview recorded. Use existing element stereotype/tag tools or implement typed writes after disposable profile validation.");
        response.addProperty("operation", operation);
        response.addProperty("writePerformed", false);
        response.add("capabilities", capabilities());
        HttpBridgeServer.sendJson(exchange, 200, response);
    }

    private void handleExportSummary(HttpExchange exchange) throws Exception {
        JsonObject result = EdtDispatcher.read(project -> {
            JsonArray profiles = new JsonArray();
            JsonArray stereotypes = new JsonArray();
            Element root = project.getPrimaryModel();
            if (root != null) {
                Collection<? extends Element> profileElements = Finder.byTypeRecursively()
                        .find(root, new Class[]{Profile.class});
                for (Element element : profileElements) {
                    if (element instanceof Profile) {
                        profiles.add(ElementSerializer.toJsonReference(element));
                    }
                }
                Collection<? extends Element> stereotypeElements = Finder.byTypeRecursively()
                        .find(root, new Class[]{Stereotype.class});
                for (Element element : stereotypeElements) {
                    if (element instanceof Stereotype) {
                        stereotypes.add(ElementSerializer.toJsonReference(element));
                    }
                }
            }
            JsonObject response = capabilities();
            response.addProperty("profileCount", profiles.size());
            response.addProperty("stereotypeCount", stereotypes.size());
            response.add("profiles", profiles);
            response.add("stereotypes", stereotypes);
            return response;
        });
        HttpBridgeServer.sendJson(exchange, 200, result);
    }
}
