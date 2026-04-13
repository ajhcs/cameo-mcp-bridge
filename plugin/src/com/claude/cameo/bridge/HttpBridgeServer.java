package com.claude.cameo.bridge;

import com.claude.cameo.bridge.handlers.ContainmentTreeHandler;
import com.claude.cameo.bridge.handlers.DiagramHandler;
import com.claude.cameo.bridge.handlers.ElementMutationHandler;
import com.claude.cameo.bridge.handlers.ElementQueryHandler;
import com.claude.cameo.bridge.handlers.MacroHandler;
import com.claude.cameo.bridge.handlers.MatrixHandler;
import com.claude.cameo.bridge.handlers.ProjectHandler;
import com.claude.cameo.bridge.handlers.RelationshipHandler;
import com.claude.cameo.bridge.handlers.SpecificationHandler;
import com.claude.cameo.bridge.util.BridgeCapabilities;
import com.nomagic.magicdraw.core.Application;
import com.nomagic.magicdraw.core.Project;
import com.nomagic.magicdraw.openapi.uml.SessionManager;
import com.sun.net.httpserver.HttpServer;
import com.sun.net.httpserver.HttpExchange;
import com.google.gson.JsonObject;
import javax.swing.SwingUtilities;
import java.io.IOException;
import java.io.OutputStream;
import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.Executors;
import java.util.logging.Level;
import java.util.logging.Logger;

public class HttpBridgeServer {

    private static final Logger LOG = Logger.getLogger(HttpBridgeServer.class.getName());
    private final HttpServer server;

    public HttpBridgeServer(int port) throws IOException {
        server = HttpServer.create(new InetSocketAddress("127.0.0.1", port), 0);
        server.setExecutor(Executors.newFixedThreadPool(4));
        registerHandlers();
    }

    private void registerHandlers() {
        server.createContext("/api/v1/status", this::handleStatus);
        server.createContext("/api/v1/capabilities", this::handleCapabilities);
        server.createContext("/api/v1/project", new ProjectHandler());
        server.createContext("/api/v1/containment-tree", new ContainmentTreeHandler());
        server.createContext("/api/v1/containment-tree/children", new ContainmentTreeHandler());

        // Route /elements by HTTP method and sub-path
        ElementQueryHandler queryHandler = new ElementQueryHandler();
        ElementMutationHandler mutationHandler = new ElementMutationHandler();
        SpecificationHandler specificationHandler = new SpecificationHandler();
        server.createContext("/api/v1/elements/interface-flow-properties", queryHandler);
        server.createContext("/api/v1/elements", exchange -> {
            String path = exchange.getRequestURI().getPath();
            // Route /specification sub-paths to SpecificationHandler (GET and PUT)
            if (path.contains("/specification")) {
                specificationHandler.handle(exchange);
            } else if ("GET".equals(exchange.getRequestMethod())) {
                queryHandler.handle(exchange);
            } else {
                mutationHandler.handle(exchange);
            }
        });

        server.createContext("/api/v1/relationships", new RelationshipHandler());
        server.createContext("/api/v1/diagrams", new DiagramHandler());
        server.createContext("/api/v1/matrices", new MatrixHandler());
        server.createContext("/api/v1/macros", new MacroHandler());
        server.createContext("/api/v1/session/reset", this::handleSessionReset);
    }

    public void start() {
        server.start();
    }

    public void stop() {
        server.stop(2);
    }

    private void handleStatus(HttpExchange exchange) throws IOException {
        if (!allowGetOrOptions(exchange, "GET")) {
            return;
        }

        JsonObject response = BridgeCapabilities.buildStatus(server.getAddress().getPort());
        sendJson(exchange, 200, response);
    }

    private void handleCapabilities(HttpExchange exchange) throws IOException {
        if (!allowGetOrOptions(exchange, "GET")) {
            return;
        }

        JsonObject response = BridgeCapabilities.buildCapabilities(server.getAddress().getPort());
        sendJson(exchange, 200, response);
    }

    private boolean allowGetOrOptions(HttpExchange exchange, String allowedMethod) throws IOException {
        if ("OPTIONS".equals(exchange.getRequestMethod())) {
            exchange.getResponseHeaders().set("Access-Control-Allow-Methods", allowedMethod + ", OPTIONS");
            exchange.getResponseHeaders().set("Access-Control-Allow-Headers", "Content-Type");
            exchange.sendResponseHeaders(204, -1);
            return false;
        }
        if (!allowedMethod.equals(exchange.getRequestMethod())) {
            sendError(exchange, 405, "METHOD_NOT_ALLOWED", "Only " + allowedMethod + " is supported");
            return false;
        }
        return true;
    }

    /**
     * POST /api/v1/session/reset - Force-close any stuck SessionManager session.
     *
     * When a macro crashes mid-session, all subsequent API calls that create
     * sessions will fail with "Session is already created". This endpoint
     * cancels (or closes) the dangling session so work can continue without
     * restarting Cameo.
     *
     * Runs on the Swing EDT because SessionManager operations must execute on
     * the same thread that created the session.
     */
    private void handleSessionReset(HttpExchange exchange) throws IOException {
        if (!"POST".equals(exchange.getRequestMethod())) {
            sendError(exchange, 405, "METHOD_NOT_ALLOWED", "Only POST is supported");
            return;
        }

        Project project = Application.getInstance().getProject();
        if (project == null) {
            sendError(exchange, 400, "NO_PROJECT", "No project is open in Cameo");
            return;
        }

        try {
            CompletableFuture<JsonObject> future = new CompletableFuture<>();

            SwingUtilities.invokeLater(() -> {
                SessionManager sm = SessionManager.getInstance();
                JsonObject response = new JsonObject();

                if (!sm.isSessionCreated(project)) {
                    response.addProperty("reset", false);
                    response.addProperty("message", "No active session");
                    future.complete(response);
                    return;
                }

                // Try cancel first (rolls back partial changes), fall back to close
                try {
                    sm.cancelSession(project);
                    response.addProperty("reset", true);
                    future.complete(response);
                } catch (Exception cancelEx) {
                    LOG.log(Level.WARNING, "cancelSession failed, trying closeSession", cancelEx);
                    try {
                        sm.closeSession(project);
                        response.addProperty("reset", true);
                        future.complete(response);
                    } catch (Exception closeEx) {
                        LOG.log(Level.SEVERE, "closeSession also failed", closeEx);
                        future.completeExceptionally(new RuntimeException(
                                "cancelSession failed: " + cancelEx.getMessage()
                                        + "; closeSession failed: " + closeEx.getMessage()));
                    }
                }
            });

            JsonObject result = future.get(30, java.util.concurrent.TimeUnit.SECONDS);
            sendJson(exchange, 200, result);
        } catch (Exception e) {
            sendError(exchange, 500, "SESSION_RESET_FAILED", e.getMessage());
        }
    }

    public static void sendJson(HttpExchange exchange, int status, JsonObject json) throws IOException {
        byte[] bytes = json.toString().getBytes(StandardCharsets.UTF_8);
        exchange.getResponseHeaders().set("Content-Type", "application/json; charset=utf-8");
        exchange.sendResponseHeaders(status, bytes.length);
        try (OutputStream os = exchange.getResponseBody()) {
            os.write(bytes);
        }
    }

    public static void sendError(HttpExchange exchange, int status, String code, String message) throws IOException {
        JsonObject error = new JsonObject();
        error.addProperty("error", true);
        error.addProperty("code", code);
        error.addProperty("message", message);
        sendJson(exchange, status, error);
    }
}
