package com.claude.cameo.bridge.handlers;

import com.claude.cameo.bridge.HttpBridgeServer;
import com.claude.cameo.bridge.util.EdtDispatcher;
import com.claude.cameo.bridge.util.ElementSerializer;
import com.claude.cameo.bridge.util.JsonHelper;
import com.claude.cameo.bridge.util.PresentationSerializer;
import com.google.gson.JsonArray;
import com.google.gson.JsonObject;
import com.nomagic.magicdraw.core.Application;
import com.nomagic.magicdraw.core.Project;
import com.nomagic.magicdraw.uml.symbols.DiagramPresentationElement;
import com.nomagic.magicdraw.uml.symbols.PresentationElement;
import com.nomagic.uml2.ext.magicdraw.classes.mdkernel.Element;

import com.sun.net.httpserver.HttpExchange;
import com.sun.net.httpserver.HttpHandler;

import java.io.IOException;
import java.lang.reflect.Method;
import java.util.Collection;
import java.util.LinkedHashSet;
import java.util.Map;
import java.util.Set;
import java.util.logging.Level;
import java.util.logging.Logger;

public class UiStateHandler implements HttpHandler {

    private static final Logger LOG = Logger.getLogger(UiStateHandler.class.getName());

    @Override
    public void handle(HttpExchange exchange) throws IOException {
        try {
            String method = exchange.getRequestMethod();
            String path = exchange.getRequestURI().getPath();
            if ("OPTIONS".equals(method)) {
                exchange.getResponseHeaders().set("Access-Control-Allow-Methods", "GET, OPTIONS");
                exchange.getResponseHeaders().set("Access-Control-Allow-Headers", "Content-Type");
                exchange.sendResponseHeaders(204, -1);
                return;
            }
            if (!"GET".equals(method)) {
                HttpBridgeServer.sendError(exchange, 405, "METHOD_NOT_ALLOWED", "Only GET is supported");
                return;
            }

            Map<String, String> params = JsonHelper.parseQuery(exchange);
            boolean summaryOnly = parseBoolean(params.get("summaryOnly"), false);
            JsonObject state = EdtDispatcher.read(project -> buildState(project, summaryOnly));
            if (path.endsWith("/active-diagram")) {
                JsonObject response = new JsonObject();
                response.add("activeDiagram", state.get("activeDiagram"));
                response.add("warnings", state.get("warnings"));
                HttpBridgeServer.sendJson(exchange, 200, response);
            } else if (path.endsWith("/selection")) {
                JsonObject response = new JsonObject();
                response.add("selection", state.get("selection"));
                response.add("selectedElements", state.get("selectedElements"));
                response.add("selectedPresentations", state.get("selectedPresentations"));
                response.add("browserSelection", state.get("browserSelection"));
                response.add("warnings", state.get("warnings"));
                HttpBridgeServer.sendJson(exchange, 200, response);
            } else {
                HttpBridgeServer.sendJson(exchange, 200, state);
            }
        } catch (Exception e) {
            LOG.log(Level.SEVERE, "Error reading UI state", e);
            HttpBridgeServer.sendError(exchange, 500, "UI_STATE_ERROR", e.getMessage());
        }
    }

    private JsonObject buildState(Project project, boolean summaryOnly) {
        JsonArray warnings = new JsonArray();
        JsonObject response = new JsonObject();
        response.add("project", projectJson(project, warnings));

        DiagramPresentationElement activeDiagram = findActiveDiagram(project, warnings);
        if (activeDiagram != null) {
            response.add("activeDiagram", PresentationSerializer.diagramSummary(activeDiagram));
        } else {
            response.add("activeDiagram", new JsonObject());
        }

        JsonArray selectedPresentations = selectedPresentations(activeDiagram, warnings);
        JsonArray browserSelection = browserSelection(warnings);
        JsonArray selectedElements = selectedElements(selectedPresentations, browserSelection);

        JsonObject selection = new JsonObject();
        selection.addProperty("selectedElementCount", selectedElements.size());
        selection.addProperty("selectedPresentationCount", selectedPresentations.size());
        selection.addProperty("browserSelectionCount", browserSelection.size());
        response.add("selection", selection);
        response.add("selectedElements", selectedElements);
        response.add("selectedPresentations", summaryOnly ? limitArray(selectedPresentations, 50) : selectedPresentations);
        response.add("browserSelection", browserSelection);
        response.add("warnings", warnings);
        return response;
    }

    private JsonObject projectJson(Project project, JsonArray warnings) {
        JsonObject json = new JsonObject();
        json.addProperty("name", project.getName() != null ? project.getName() : "");
        Object file = invokeZeroArg(project, "getFile", null);
        if (file != null) {
            Object path = firstNonNull(
                    invokeZeroArg(file, "getAbsolutePath", null),
                    invokeZeroArg(file, "getPath", null),
                    String.valueOf(file));
            json.addProperty("filePath", String.valueOf(path));
        } else {
            warnings.add("Project file path unavailable");
        }
        try {
            Element primary = project.getPrimaryModel();
            if (primary != null) {
                json.addProperty("primaryModelId", primary.getID());
            }
        } catch (Exception e) {
            warnings.add("Primary model unavailable: " + e.getMessage());
        }
        try {
            json.addProperty("isDirty", project.isDirty());
        } catch (Exception e) {
            warnings.add("Project dirty state unavailable: " + e.getMessage());
        }
        return json;
    }

    private DiagramPresentationElement findActiveDiagram(Project project, JsonArray warnings) {
        Object candidate = invokeZeroArg(project, "getActiveDiagram", warnings);
        if (candidate instanceof DiagramPresentationElement) {
            return (DiagramPresentationElement) candidate;
        }
        Object app = Application.getInstance();
        candidate = invokeZeroArg(app, "getActiveDiagram", warnings);
        if (candidate instanceof DiagramPresentationElement) {
            return (DiagramPresentationElement) candidate;
        }
        Object mainFrame = invokeZeroArg(app, "getMainFrame", warnings);
        Object browser = invokeZeroArg(mainFrame, "getBrowser", warnings);
        Object diagram = invokeZeroArg(browser, "getActiveDiagram", warnings);
        if (diagram instanceof DiagramPresentationElement) {
            return (DiagramPresentationElement) diagram;
        }
        warnings.add("Active diagram API was unavailable or returned null");
        return null;
    }

    private JsonArray selectedPresentations(DiagramPresentationElement activeDiagram, JsonArray warnings) {
        JsonArray array = new JsonArray();
        if (activeDiagram == null) {
            return array;
        }
        Object selected = firstNonNull(
                invokeZeroArg(activeDiagram, "getSelected", warnings),
                invokeZeroArg(activeDiagram, "getSelectedPresentationElements", warnings),
                invokeZeroArg(activeDiagram, "getSelectedElements", warnings));
        if (selected instanceof Collection<?>) {
            for (Object item : (Collection<?>) selected) {
                if (item instanceof PresentationElement) {
                    array.add(PresentationSerializer.presentationSummary((PresentationElement) item, null));
                }
            }
        } else if (selected instanceof PresentationElement) {
            array.add(PresentationSerializer.presentationSummary((PresentationElement) selected, null));
        } else {
            warnings.add("Selected presentation API was unavailable or returned no presentation collection");
        }
        return array;
    }

    private JsonArray browserSelection(JsonArray warnings) {
        JsonArray array = new JsonArray();
        Object app = Application.getInstance();
        Object mainFrame = invokeZeroArg(app, "getMainFrame", warnings);
        Object browser = invokeZeroArg(mainFrame, "getBrowser", warnings);
        Object containment = firstNonNull(
                invokeZeroArg(browser, "getContainmentTree", warnings),
                invokeZeroArg(browser, "getActiveTree", warnings));
        Object selected = firstNonNull(
                invokeZeroArg(containment, "getSelectedNodes", warnings),
                invokeZeroArg(containment, "getSelectedNode", warnings));
        if (selected instanceof Collection<?>) {
            for (Object node : (Collection<?>) selected) {
                addBrowserNode(array, node);
            }
        } else {
            addBrowserNode(array, selected);
        }
        return array;
    }

    private void addBrowserNode(JsonArray array, Object node) {
        if (node == null) {
            return;
        }
        Object userObject = invokeZeroArg(node, "getUserObject", null);
        Object element = userObject instanceof Element ? userObject : invokeZeroArg(node, "getElement", null);
        if (element instanceof Element) {
            array.add(ElementSerializer.toJsonCompact((Element) element));
        }
    }

    private JsonArray selectedElements(JsonArray selectedPresentations, JsonArray browserSelection) {
        JsonArray array = new JsonArray();
        Set<String> seen = new LinkedHashSet<>();
        for (int i = 0; i < selectedPresentations.size(); i++) {
            JsonObject presentation = selectedPresentations.get(i).getAsJsonObject();
            if (presentation.has("element")) {
                JsonObject element = presentation.getAsJsonObject("element");
                if (element.has("id") && seen.add(element.get("id").getAsString())) {
                    array.add(element);
                }
            }
        }
        for (int i = 0; i < browserSelection.size(); i++) {
            JsonObject element = browserSelection.get(i).getAsJsonObject();
            if (element.has("id") && seen.add(element.get("id").getAsString())) {
                array.add(element);
            }
        }
        return array;
    }

    private JsonArray limitArray(JsonArray array, int limit) {
        JsonArray limited = new JsonArray();
        for (int i = 0; i < array.size() && i < limit; i++) {
            limited.add(array.get(i));
        }
        return limited;
    }

    private Object firstNonNull(Object... values) {
        for (Object value : values) {
            if (value != null) {
                return value;
            }
        }
        return null;
    }

    private Object invokeZeroArg(Object target, String methodName, JsonArray warnings) {
        if (target == null) {
            return null;
        }
        try {
            Method method = target.getClass().getMethod(methodName);
            return method.invoke(target);
        } catch (Exception e) {
            if (warnings != null) {
                warnings.add(target.getClass().getName() + "." + methodName + " unavailable");
            }
            return null;
        }
    }

    private boolean parseBoolean(String value, boolean defaultValue) {
        return value == null ? defaultValue : Boolean.parseBoolean(value);
    }
}
