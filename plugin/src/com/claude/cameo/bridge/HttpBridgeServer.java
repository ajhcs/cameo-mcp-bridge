package com.claude.cameo.bridge;

import com.claude.cameo.bridge.handlers.ContainmentTreeHandler;
import com.claude.cameo.bridge.handlers.ElementMutationHandler;
import com.claude.cameo.bridge.handlers.ElementQueryHandler;
import com.claude.cameo.bridge.handlers.ProjectHandler;
import com.claude.cameo.bridge.handlers.RelationshipHandler;
import com.sun.net.httpserver.HttpServer;
import com.sun.net.httpserver.HttpExchange;
import com.google.gson.JsonObject;
import java.io.IOException;
import java.io.OutputStream;
import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import java.util.concurrent.Executors;
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
        server.createContext("/api/v1/project", new ProjectHandler());
        server.createContext("/api/v1/containment-tree", new ContainmentTreeHandler());

        // Route /elements by HTTP method: GET -> query, POST/PUT/DELETE -> mutation
        ElementQueryHandler queryHandler = new ElementQueryHandler();
        ElementMutationHandler mutationHandler = new ElementMutationHandler();
        server.createContext("/api/v1/elements", exchange -> {
            if ("GET".equals(exchange.getRequestMethod())) {
                queryHandler.handle(exchange);
            } else {
                mutationHandler.handle(exchange);
            }
        });

        server.createContext("/api/v1/relationships", new RelationshipHandler());
    }

    public void start() {
        server.start();
    }

    public void stop() {
        server.stop(2);
    }

    private void handleStatus(HttpExchange exchange) throws IOException {
        if (!"GET".equals(exchange.getRequestMethod())) {
            sendError(exchange, 405, "METHOD_NOT_ALLOWED", "Only GET is supported");
            return;
        }
        JsonObject response = new JsonObject();
        response.addProperty("status", "ok");
        response.addProperty("plugin", "CameoMCPBridge");
        response.addProperty("version", "1.0.0");
        response.addProperty("port", server.getAddress().getPort());
        sendJson(exchange, 200, response);
    }

    public static void sendJson(HttpExchange exchange, int status, JsonObject json) throws IOException {
        byte[] bytes = json.toString().getBytes(StandardCharsets.UTF_8);
        exchange.getResponseHeaders().set("Content-Type", "application/json; charset=utf-8");
        exchange.getResponseHeaders().set("Access-Control-Allow-Origin", "*");
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
