package com.claude.cameo.bridge.handlers;

import com.claude.cameo.bridge.HttpBridgeServer;
import com.claude.cameo.bridge.util.EdtDispatcher;
import com.nomagic.magicdraw.core.Application;
import com.nomagic.magicdraw.core.Project;
import com.nomagic.magicdraw.core.project.ProjectDescriptorsFactory;
import com.nomagic.magicdraw.core.project.ProjectDescriptor;
import com.nomagic.magicdraw.core.project.ProjectsManager;
import com.nomagic.uml2.ext.magicdraw.classes.mdkernel.Package;
import com.sun.net.httpserver.HttpExchange;
import com.sun.net.httpserver.HttpHandler;
import com.google.gson.JsonObject;

import java.io.IOException;
import java.util.logging.Level;
import java.util.logging.Logger;

/**
 * Handles project-level REST endpoints:
 * <ul>
 *   <li>{@code GET  /api/v1/project}      - project name, file path, primary model ID</li>
 *   <li>{@code POST /api/v1/project/save}  - save the current project</li>
 * </ul>
 */
public class ProjectHandler implements HttpHandler {

    private static final Logger LOG = Logger.getLogger(ProjectHandler.class.getName());

    @Override
    public void handle(HttpExchange exchange) throws IOException {
        try {
            String path = exchange.getRequestURI().getPath();
            String method = exchange.getRequestMethod();

            if (path.equals("/api/v1/project") && "GET".equals(method)) {
                handleGetProject(exchange);
            } else if (path.equals("/api/v1/project/save") && "POST".equals(method)) {
                handleSaveProject(exchange);
            } else if ("OPTIONS".equals(method)) {
                exchange.getResponseHeaders().set("Access-Control-Allow-Methods", "GET, POST, OPTIONS");
                exchange.getResponseHeaders().set("Access-Control-Allow-Headers", "Content-Type");
                exchange.sendResponseHeaders(204, -1);
            } else {
                HttpBridgeServer.sendError(exchange, 405, "METHOD_NOT_ALLOWED",
                        "Method " + method + " not allowed for " + path);
            }
        } catch (Exception e) {
            LOG.log(Level.SEVERE, "Error in ProjectHandler", e);
            HttpBridgeServer.sendError(exchange, 500, "INTERNAL_ERROR", e.getMessage());
        }
    }

    /**
     * GET /api/v1/project - returns project name, file path, and primary model ID.
     */
    private void handleGetProject(HttpExchange exchange) throws Exception {
        JsonObject result = EdtDispatcher.read(project -> {
            JsonObject json = new JsonObject();
            json.addProperty("name", project.getName());

            String fileName = project.getFileName();
            json.addProperty("filePath", fileName != null ? fileName : "");

            json.addProperty("isRemote", project.isRemote());
            json.addProperty("isDirty", project.isDirty());

            Package primaryModel = project.getPrimaryModel();
            if (primaryModel != null) {
                json.addProperty("primaryModelId", primaryModel.getID());
                json.addProperty("primaryModelName",
                        primaryModel.getName() != null ? primaryModel.getName() : "");
            }

            return json;
        });

        HttpBridgeServer.sendJson(exchange, 200, result);
    }

    /**
     * POST /api/v1/project/save - saves the current project to its existing location.
     */
    private void handleSaveProject(HttpExchange exchange) throws Exception {
        JsonObject result = EdtDispatcher.write("MCP Bridge: Save Project", project -> {
            ProjectsManager pm = Application.getInstance().getProjectsManager();
            ProjectDescriptor descriptor = ProjectDescriptorsFactory.getDescriptorForProject(project);

            if (descriptor == null) {
                throw new IllegalStateException(
                        "Cannot save: no project descriptor found (project may not have been saved before)");
            }

            boolean success = pm.saveProject(descriptor, true);

            JsonObject json = new JsonObject();
            json.addProperty("saved", success);
            json.addProperty("filePath", project.getFileName() != null ? project.getFileName() : "");
            return json;
        });

        HttpBridgeServer.sendJson(exchange, 200, result);
    }
}
