package com.claude.cameo.bridge.handlers;

import com.claude.cameo.bridge.HttpBridgeServer;
import com.claude.cameo.bridge.util.JsonHelper;
import com.nomagic.magicdraw.core.Application;
import com.nomagic.magicdraw.core.Project;
import com.nomagic.magicdraw.openapi.uml.SessionManager;
import com.sun.net.httpserver.HttpExchange;
import com.sun.net.httpserver.HttpHandler;
import com.google.gson.JsonObject;

import javax.script.ScriptEngine;
import javax.script.ScriptEngineFactory;
import javax.script.ScriptEngineManager;
import javax.script.ScriptContext;
import javax.script.SimpleScriptContext;
import javax.swing.SwingUtilities;
import java.io.IOException;
import java.io.PrintWriter;
import java.io.StringWriter;
import java.util.List;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.TimeUnit;
import java.util.logging.Level;
import java.util.logging.Logger;
import java.util.stream.Collectors;

/**
 * Handles macro execution REST endpoint.
 * Executes scripts inside the Cameo JVM using javax.script.
 *
 * POST /api/v1/macros/execute
 * Body: {"script": "groovy or javascript code", "engine": "groovy"}
 *
 * The project and application variables are injected into the script context.
 */
public class MacroHandler implements HttpHandler {

    private static final Logger LOG = Logger.getLogger(MacroHandler.class.getName());

    @Override
    public void handle(HttpExchange exchange) throws IOException {
        try {
            String method = exchange.getRequestMethod();
            String path = exchange.getRequestURI().getPath();

            if ("OPTIONS".equals(method)) {
                exchange.getResponseHeaders().set("Access-Control-Allow-Methods",
                        "GET, POST, OPTIONS");
                exchange.getResponseHeaders().set("Access-Control-Allow-Headers", "Content-Type");
                exchange.sendResponseHeaders(204, -1);
                return;
            }

            if ("GET".equals(method) && path.equals("/api/v1/macros/engines")) {
                handleListEngines(exchange);
                return;
            }

            if ("POST".equals(method) && path.equals("/api/v1/macros/execute")) {
                handleExecute(exchange);
                return;
            }

            HttpBridgeServer.sendError(exchange, 405, "METHOD_NOT_ALLOWED",
                    "Use POST /api/v1/macros/execute or GET /api/v1/macros/engines");
        } catch (Exception e) {
            LOG.log(Level.SEVERE, "Error in MacroHandler", e);
            HttpBridgeServer.sendError(exchange, 500, "INTERNAL_ERROR", e.getMessage());
        }
    }

    /**
     * GET /api/v1/macros/engines - List available script engines.
     */
    private void handleListEngines(HttpExchange exchange) throws Exception {
        ScriptEngineManager manager = new ScriptEngineManager(
                getClass().getClassLoader());
        List<ScriptEngineFactory> factories = manager.getEngineFactories();

        JsonObject response = new JsonObject();
        com.google.gson.JsonArray engines = new com.google.gson.JsonArray();

        for (ScriptEngineFactory factory : factories) {
            JsonObject engineJson = new JsonObject();
            engineJson.addProperty("name", factory.getEngineName());
            engineJson.addProperty("version", factory.getEngineVersion());
            engineJson.addProperty("language", factory.getLanguageName());
            engineJson.addProperty("languageVersion", factory.getLanguageVersion());

            com.google.gson.JsonArray names = new com.google.gson.JsonArray();
            for (String n : factory.getNames()) {
                names.add(n);
            }
            engineJson.add("aliases", names);

            engines.add(engineJson);
        }

        response.addProperty("count", engines.size());
        response.add("engines", engines);
        HttpBridgeServer.sendJson(exchange, 200, response);
    }

    /**
     * POST /api/v1/macros/execute - Execute a script in the Cameo JVM.
     *
     * Request body:
     * {
     *   "script": "println project.getName()",
     *   "engine": "groovy"  // optional, defaults to "groovy", falls back to "javascript"
     * }
     *
     * Response:
     * {
     *   "success": true/false,
     *   "result": "return value as string",
     *   "output": "captured stdout/stderr",
     *   "engine": "engine name actually used"
     * }
     */
    private void handleExecute(HttpExchange exchange) throws Exception {
        JsonObject body = JsonHelper.parseBody(exchange);

        if (!body.has("script") || body.get("script").getAsString().isEmpty()) {
            HttpBridgeServer.sendError(exchange, 400, "MISSING_PARAM",
                    "Request body must include a non-empty script field");
            return;
        }

        String script = body.get("script").getAsString();
        String requestedEngine = body.has("engine") ? body.get("engine").getAsString() : "groovy";

        // Find a working script engine
        ScriptEngineManager manager = new ScriptEngineManager(
                getClass().getClassLoader());
        ScriptEngine engine = manager.getEngineByName(requestedEngine);
        String engineUsed = requestedEngine;

        if (engine == null) {
            // Try fallback engines
            String[] fallbacks = {"groovy", "javascript", "js", "nashorn", "Groovy"};
            for (String fallback : fallbacks) {
                if (fallback.equals(requestedEngine)) continue;
                engine = manager.getEngineByName(fallback);
                if (engine != null) {
                    engineUsed = fallback;
                    break;
                }
            }
        }

        if (engine == null) {
            List<String> available = manager.getEngineFactories().stream()
                    .flatMap(f -> f.getNames().stream())
                    .collect(Collectors.toList());
            HttpBridgeServer.sendError(exchange, 400, "NO_SCRIPT_ENGINE",
                    "No script engine found for: " + requestedEngine
                            + ". Available engines: " + available);
            return;
        }

        final ScriptEngine finalEngine = engine;
        final String finalEngineUsed = engineUsed;

        // Get project outside EDT — Application.getInstance() is thread-safe
        Project project = Application.getInstance().getProject();
        if (project == null) {
            HttpBridgeServer.sendError(exchange, 400, "NO_PROJECT",
                    "No project is open in Cameo");
            return;
        }

        // Dispatch to EDT directly — NO SessionManager session.
        // Scripts are responsible for their own session management
        // (createSession/closeSession) when they need to modify the model.
        CompletableFuture<JsonObject> future = new CompletableFuture<>();

        SwingUtilities.invokeLater(() -> {
            // Clean up any stale session left by a previous failed macro
            SessionManager sm = SessionManager.getInstance();
            if (sm.isSessionCreated(project)) {
                LOG.warning("Stale session detected before macro execution — cancelling");
                try {
                    sm.cancelSession(project);
                } catch (Exception e) {
                    LOG.log(Level.WARNING, "Failed to cancel stale session, trying close", e);
                    try {
                        sm.closeSession(project);
                    } catch (Exception e2) {
                        LOG.log(Level.SEVERE, "Failed to close stale session", e2);
                    }
                }
            }

            // Set up output capture
            StringWriter outputWriter = new StringWriter();
            StringWriter errorWriter = new StringWriter();
            PrintWriter outputPrint = new PrintWriter(outputWriter, true);
            PrintWriter errorPrint = new PrintWriter(errorWriter, true);

            ScriptContext context = new SimpleScriptContext();
            context.setWriter(outputPrint);
            context.setErrorWriter(errorPrint);

            // Inject variables into the script context
            context.setAttribute("project", project,
                    ScriptContext.ENGINE_SCOPE);
            context.setAttribute("application", Application.getInstance(),
                    ScriptContext.ENGINE_SCOPE);
            context.setAttribute("primaryModel", project.getPrimaryModel(),
                    ScriptContext.ENGINE_SCOPE);

            // Inject ElementsFactory for convenience
            context.setAttribute("ef",
                    project.getElementsFactory(),
                    ScriptContext.ENGINE_SCOPE);

            finalEngine.setContext(context);

            JsonObject response = new JsonObject();

            try {
                Object evalResult = finalEngine.eval(script);

                response.addProperty("success", true);
                response.addProperty("result",
                        evalResult != null ? evalResult.toString() : "null");
                response.addProperty("output", outputWriter.toString());
                if (errorWriter.toString().length() > 0) {
                    response.addProperty("errors", errorWriter.toString());
                }
            } catch (Exception e) {
                response.addProperty("success", false);
                response.addProperty("error", e.getMessage());
                response.addProperty("output", outputWriter.toString());

                // Include stack trace
                StringWriter sw = new StringWriter();
                e.printStackTrace(new PrintWriter(sw));
                response.addProperty("stackTrace", sw.toString());
            }

            response.addProperty("engine", finalEngineUsed);
            future.complete(response);
        });

        // 60-second timeout — macros can be slow
        JsonObject result = future.get(60, TimeUnit.SECONDS);
        HttpBridgeServer.sendJson(exchange, 200, result);
    }
}
