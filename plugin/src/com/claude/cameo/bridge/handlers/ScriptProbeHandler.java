package com.claude.cameo.bridge.handlers;

import com.claude.cameo.bridge.HttpBridgeServer;
import com.claude.cameo.bridge.util.EdtDispatcher;
import com.claude.cameo.bridge.util.JsonHelper;
import com.claude.cameo.bridge.util.PropertySerializer;
import com.google.gson.JsonArray;
import com.google.gson.JsonObject;
import com.nomagic.magicdraw.core.Project;
import com.nomagic.magicdraw.uml.symbols.DiagramPresentationElement;
import com.nomagic.magicdraw.uml.symbols.PresentationElement;
import com.nomagic.magicdraw.visualization.relationshipmap.RelationshipMapUtilities;
import com.nomagic.magicdraw.visualization.relationshipmap.model.settings.GraphSettings;
import com.nomagic.uml2.ext.magicdraw.classes.mdkernel.Diagram;
import com.sun.net.httpserver.HttpExchange;
import com.sun.net.httpserver.HttpHandler;

import java.io.IOException;
import java.lang.reflect.Method;
import java.lang.reflect.Modifier;
import java.util.Collection;

public class ScriptProbeHandler implements HttpHandler {

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
            if ("GET".equals(method) && path.equals("/api/v1/probes/templates")) {
                handleTemplates(exchange);
            } else if ("POST".equals(method) && path.equals("/api/v1/probes/execute")) {
                handleExecute(exchange);
            } else {
                HttpBridgeServer.sendError(exchange, 404, "NOT_FOUND", "Unknown endpoint: " + path);
            }
        } catch (IllegalArgumentException e) {
            HttpBridgeServer.sendError(exchange, 400, "PROBE_BAD_REQUEST", e.getMessage());
        } catch (Exception e) {
            HttpBridgeServer.sendError(exchange, 500, "PROBE_ERROR", e.getMessage());
        }
    }

    private void handleTemplates(HttpExchange exchange) throws IOException {
        JsonArray templates = new JsonArray();
        addTemplate(templates, "relationMap.listGraphSettingsMethods", "List public GraphSettings methods");
        addTemplate(templates, "relationMap.dumpCriteriaClasses", "Dump GraphSettings criteria value classes");
        addTemplate(templates, "relationMap.dumpPresentationClasses", "List presentation classes on Relation Maps");
        addTemplate(templates, "diagram.dumpSelectedPresentationMethods", "List PresentationElement methods");
        addTemplate(templates, "ui.dumpSelectionApi", "List likely UI selection APIs by reflection");
        JsonObject response = new JsonObject();
        response.addProperty("count", templates.size());
        response.add("templates", templates);
        HttpBridgeServer.sendJson(exchange, 200, response);
    }

    private void handleExecute(HttpExchange exchange) throws Exception {
        JsonObject body = JsonHelper.parseBody(exchange);
        String mode = JsonHelper.optionalString(body, "mode");
        if (mode == null) {
            mode = "read";
        }
        if (!"read".equalsIgnoreCase(mode)) {
            boolean writeEnabled = Boolean.getBoolean("cameo.bridge.probes.write.enabled");
            if (!writeEnabled) {
                HttpBridgeServer.sendError(exchange, 403, "WRITE_PROBES_DISABLED",
                        "Write probes require -Dcameo.bridge.probes.write.enabled=true");
                return;
            }
        }
        String template = JsonHelper.optionalString(body, "template");
        if (template == null) {
            String language = JsonHelper.optionalString(body, "language");
            if ("javaReflection".equalsIgnoreCase(language)) {
                JsonObject result = EdtDispatcher.read(project -> executeReflectionProbe(project, body));
                HttpBridgeServer.sendJson(exchange, 200, result);
            } else {
                String script = JsonHelper.optionalString(body, "script");
                JsonObject response = new JsonObject();
                response.addProperty("executed", false);
                response.addProperty("refused", true);
                response.addProperty("reason",
                        "Arbitrary script execution is intentionally disabled; use a built-in probe template or language=javaReflection with operation=listMethods/invokeGraphSettingsGetter.");
                response.addProperty("scriptLength", script != null ? script.length() : 0);
                HttpBridgeServer.sendJson(exchange, 200, response);
            }
            return;
        }
        JsonObject result = EdtDispatcher.read(project -> executeTemplate(project, template));
        HttpBridgeServer.sendJson(exchange, 200, result);
    }

    private JsonObject executeReflectionProbe(Project project, JsonObject body) throws Exception {
        String operation = JsonHelper.optionalString(body, "operation");
        if (operation == null) {
            operation = "listMethods";
        }
        JsonObject response = new JsonObject();
        response.addProperty("language", "javaReflection");
        response.addProperty("operation", operation);
        response.addProperty("executed", true);

        if ("listMethods".equals(operation)) {
            String className = JsonHelper.requireString(body, "className");
            Class<?> cls = safeProbeClass(className);
            response.addProperty("className", cls.getName());
            response.add("methods", methods(cls));
            return response;
        }

        if ("invokeGraphSettingsGetter".equals(operation)) {
            String relationMapId = JsonHelper.requireString(body, "relationMapId");
            String methodName = JsonHelper.requireString(body, "methodName");
            Object element = project.getElementByID(relationMapId);
            if (!(element instanceof Diagram)) {
                throw new IllegalArgumentException("Relation Map diagram not found: " + relationMapId);
            }
            GraphSettings settings = new GraphSettings((Diagram) element);
            Method method = GraphSettings.class.getMethod(methodName);
            if (method.getParameterCount() != 0 || method.getReturnType() == Void.TYPE
                    || (!methodName.startsWith("get") && !methodName.startsWith("is"))) {
                throw new IllegalArgumentException("Only public no-arg GraphSettings getters are allowed");
            }
            Object value = method.invoke(settings);
            response.addProperty("className", GraphSettings.class.getName());
            response.addProperty("methodName", methodName);
            response.add("value", PropertySerializer.serializeValue(value, true, false));
            return response;
        }

        if ("invokeStaticNoArg".equals(operation)) {
            String className = JsonHelper.requireString(body, "className");
            String methodName = JsonHelper.requireString(body, "methodName");
            Class<?> cls = safeProbeClass(className);
            Method method = cls.getMethod(methodName);
            if (!Modifier.isStatic(method.getModifiers()) || method.getParameterCount() != 0
                    || method.getReturnType() == Void.TYPE) {
                throw new IllegalArgumentException("Only public static no-arg methods with return values are allowed");
            }
            Object value = method.invoke(null);
            response.addProperty("className", cls.getName());
            response.addProperty("methodName", methodName);
            response.add("value", PropertySerializer.serializeValue(value, true, true));
            return response;
        }

        throw new IllegalArgumentException("Unsupported javaReflection operation: " + operation);
    }

    private Class<?> safeProbeClass(String className) throws ClassNotFoundException {
        if (!(className.startsWith("com.nomagic.magicdraw.visualization.relationshipmap.")
                || className.startsWith("com.nomagic.magicdraw.uml.symbols.")
                || className.startsWith("com.nomagic.magicdraw.core.")
                || className.startsWith("com.nomagic.magicdraw.validation.")
                || className.startsWith("com.nomagic.magicdraw.magicreport.")
                || className.startsWith("com.nomagic.magicreport.")
                || className.startsWith("com.nomagic.requirements.")
                || className.startsWith("com.nomagic.magicdraw.esi.")
                || className.startsWith("com.nomagic.magicdraw.simulation.")
                || className.startsWith("com.nomagic.uml2.ext.magicdraw."))) {
            throw new IllegalArgumentException("Class is outside the allowed CATIA probe package prefixes: " + className);
        }
        return Class.forName(className);
    }

    private JsonObject executeTemplate(Project project, String template) {
        JsonObject response = new JsonObject();
        response.addProperty("template", template);
        response.addProperty("executed", true);
        if ("relationMap.listGraphSettingsMethods".equals(template)) {
            response.add("methods", methods(GraphSettings.class));
        } else if ("relationMap.dumpCriteriaClasses".equals(template)) {
            response.add("criteria", criteriaClasses(project));
        } else if ("relationMap.dumpPresentationClasses".equals(template)) {
            response.add("presentations", relationMapPresentationClasses(project));
        } else if ("diagram.dumpSelectedPresentationMethods".equals(template)) {
            response.add("methods", methods(PresentationElement.class));
        } else if ("ui.dumpSelectionApi".equals(template)) {
            JsonArray classes = new JsonArray();
            classes.add(com.nomagic.magicdraw.core.Application.class.getName());
            classes.add(Project.class.getName());
            classes.add(DiagramPresentationElement.class.getName());
            response.add("candidateClasses", classes);
            response.add("applicationMethods", methods(com.nomagic.magicdraw.core.Application.class));
            response.add("projectMethods", methods(Project.class));
            response.add("diagramPresentationMethods", methods(DiagramPresentationElement.class));
        } else {
            throw new IllegalArgumentException("Unknown probe template: " + template);
        }
        return response;
    }

    private JsonArray criteriaClasses(Project project) {
        JsonArray array = new JsonArray();
        Collection<DiagramPresentationElement> diagrams = project.getDiagrams();
        if (diagrams != null) {
            for (DiagramPresentationElement dpe : diagrams) {
                if (dpe == null || dpe.getDiagramType() == null
                        || !"Relation Map Diagram".equals(dpe.getDiagramType().getType())) {
                    continue;
                }
                GraphSettings settings = new GraphSettings(dpe.getDiagram());
                JsonObject entry = new JsonObject();
                entry.addProperty("diagramId", dpe.getDiagram().getID());
                entry.addProperty("diagramName", dpe.getName());
                JsonArray criteria = new JsonArray();
                if (settings.getDependencyCriterion() != null) {
                    for (Object criterion : settings.getDependencyCriterion()) {
                        JsonObject criterionJson = new JsonObject();
                        criterionJson.addProperty("className", criterion != null ? criterion.getClass().getName() : "null");
                        criterionJson.addProperty("string", String.valueOf(criterion));
                        criteria.add(criterionJson);
                    }
                }
                entry.add("criteria", criteria);
                array.add(entry);
            }
        }
        return array;
    }

    private JsonArray relationMapPresentationClasses(Project project) {
        JsonArray array = new JsonArray();
        Collection<DiagramPresentationElement> diagrams = project.getDiagrams();
        if (diagrams != null) {
            for (DiagramPresentationElement dpe : diagrams) {
                if (dpe == null || dpe.getDiagramType() == null
                        || !"Relation Map Diagram".equals(dpe.getDiagramType().getType())) {
                    continue;
                }
                dpe.ensureLoaded();
                JsonObject entry = new JsonObject();
                entry.addProperty("diagramId", dpe.getDiagram().getID());
                entry.addProperty("diagramName", dpe.getName());
                JsonArray classes = new JsonArray();
                for (PresentationElement pe : com.claude.cameo.bridge.util.PresentationSerializer.flatten(dpe, null)) {
                    classes.add(pe.getClass().getName());
                }
                entry.addProperty("count", classes.size());
                entry.add("classes", classes);
                array.add(entry);
            }
        }
        return array;
    }

    private JsonArray methods(Class<?> cls) {
        JsonArray array = new JsonArray();
        for (Method method : cls.getMethods()) {
            JsonObject entry = new JsonObject();
            entry.addProperty("name", method.getName());
            entry.addProperty("returnType", method.getReturnType().getName());
            entry.addProperty("parameterCount", method.getParameterCount());
            entry.addProperty("static", Modifier.isStatic(method.getModifiers()));
            JsonArray params = new JsonArray();
            for (Class<?> param : method.getParameterTypes()) {
                params.add(param.getName());
            }
            entry.add("parameterTypes", params);
            array.add(entry);
        }
        return array;
    }

    private void addTemplate(JsonArray templates, String key, String description) {
        JsonObject template = new JsonObject();
        template.addProperty("key", key);
        template.addProperty("description", description);
        template.addProperty("mode", "read");
        templates.add(template);
    }
}
