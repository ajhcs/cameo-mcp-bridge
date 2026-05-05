package com.claude.cameo.bridge.handlers;

import com.claude.cameo.bridge.HttpBridgeServer;
import com.claude.cameo.bridge.util.EdtDispatcher;
import com.claude.cameo.bridge.util.JsonHelper;
import com.claude.cameo.bridge.util.OptionalCapabilitySupport;
import com.claude.cameo.bridge.util.PropertySerializer;
import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import com.nomagic.magicdraw.core.Project;
import com.sun.net.httpserver.HttpExchange;
import com.sun.net.httpserver.HttpHandler;

import java.io.File;
import java.io.IOException;
import java.lang.reflect.Array;
import java.lang.reflect.Constructor;
import java.lang.reflect.Method;
import java.util.ArrayList;
import java.util.Collection;
import java.util.List;
import java.util.Locale;

public class ReportWizardHandler implements HttpHandler {

    private static final String TEMPLATE_HELPER = "com.nomagic.magicdraw.magicreport.helper.TemplateHelper";
    private static final String GENERATE_TASK = "com.nomagic.magicdraw.magicreport.GenerateTask";
    private static final String REPORT_COMMAND_LINE = "com.nomagic.magicdraw.magicreport.commandline.ReportCommandLine";
    private static final String TEMPLATE_BEAN = "com.nomagic.magicdraw.magicreport.ui.bean.TemplateBean";
    private static final String REPORT_PROPERTY_BEAN = "com.nomagic.magicdraw.magicreport.ui.bean.ReportPropertyBean";
    private static final String PACKAGE_SELECTION_BEAN = "com.nomagic.magicdraw.magicreport.ui.bean.PackageSelectionBean";
    private static final String TASK = "com.nomagic.task.Task";

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

            if ("GET".equals(method) && path.equals("/api/v1/reports/capabilities")) {
                handleCapabilities(exchange);
            } else if ("GET".equals(method) && path.equals("/api/v1/reports/templates")) {
                handleTemplates(exchange);
            } else if ("POST".equals(method) && path.equals("/api/v1/reports/generate-preview")) {
                handleGeneratePreview(exchange);
            } else if ("POST".equals(method) && path.equals("/api/v1/reports/generate")) {
                handleGenerate(exchange);
            } else if ("GET".equals(method) && path.startsWith("/api/v1/reports/jobs/")) {
                handleJob(exchange, path.substring("/api/v1/reports/jobs/".length()));
            } else {
                HttpBridgeServer.sendError(exchange, 404, "NOT_FOUND", "Unknown endpoint: " + path);
            }
        } catch (IllegalArgumentException e) {
            HttpBridgeServer.sendError(exchange, 400, "REPORT_WIZARD_BAD_REQUEST", e.getMessage());
        } catch (Exception e) {
            HttpBridgeServer.sendError(exchange, 500, "REPORT_WIZARD_ERROR", e.getMessage());
        }
    }

    private void handleCapabilities(HttpExchange exchange) throws IOException {
        HttpBridgeServer.sendJson(exchange, 200, capabilities());
    }

    private JsonObject capabilities() {
        JsonObject response = OptionalCapabilitySupport.baseCapabilities("reportWizard", "native-direct");
        JsonObject classProbe = OptionalCapabilitySupport.classProbe(TEMPLATE_HELPER, GENERATE_TASK, REPORT_COMMAND_LINE);
        boolean available = classProbe.get("classesFound").getAsJsonArray().size() >= 2;
        response.addProperty("available", available);
        response.addProperty("status", available ? "available" : "missing-plugin");
        response.add("classProbe", classProbe);
        response.add("pluginDirectoriesFound", OptionalCapabilitySupport.pluginDirectories("reportwizard", "report"));
        JsonArray formats = new JsonArray();
        formats.add("docx");
        formats.add("pdf");
        formats.add("html");
        formats.add("xlsx");
        formats.add("pptx");
        response.add("knownOutputFormats", formats);
        response.addProperty("generationMode", available ? "native-generate-task" : "unavailable");
        response.addProperty("generationWriteEnabled", available);
        response.addProperty("requiresOutputPath", true);
        return response;
    }

    private void handleTemplates(HttpExchange exchange) throws Exception {
        JsonObject response = capabilities();
        JsonArray templates = new JsonArray();
        try {
            int index = 0;
            for (Object template : listTemplates()) {
                templates.add(serializeTemplate(template, index++));
            }
            response.addProperty("templateDiscovery", "native");
        } catch (ClassNotFoundException e) {
            response.addProperty("templateDiscovery", "unavailable");
            response.addProperty("reason", "Report Wizard TemplateHelper class is not available");
        }
        response.addProperty("count", templates.size());
        response.add("templates", templates);
        HttpBridgeServer.sendJson(exchange, 200, response);
    }

    private void handleGeneratePreview(HttpExchange exchange) throws Exception {
        JsonObject body = JsonHelper.parseBody(exchange);
        JsonObject response = OptionalCapabilitySupport.previewAccepted(
                "reportWizard",
                body,
                "Report preview accepted. Native generation uses the same template/output selection without mutating the model.");
        response.add("capabilities", capabilities());
        response.addProperty("outputPathAccepted", firstString(body, null, "outputPath") != null);
        response.addProperty("templateSpecified", firstString(body, null, "templateId", "templateName") != null);
        HttpBridgeServer.sendJson(exchange, 200, response);
    }

    private void handleGenerate(HttpExchange exchange) throws Exception {
        JsonObject body = JsonHelper.parseBody(exchange);
        if (!firstBoolean(body, jsonObject(body, "parameters"), "allowWrite", false)) {
            JsonObject response = OptionalCapabilitySupport.unsupported(
                    "reportWizard",
                    "Report generation requires allowWrite=true because it writes an output file.",
                    "Call /api/v1/reports/generate-preview first, then repeat with allowWrite=true and an explicit outputPath.");
            response.add("request", body);
            HttpBridgeServer.sendJson(exchange, 403, response);
            return;
        }
        int timeoutSeconds = boundedInt(body, "timeoutSeconds", 120, 10, 600);
        JsonObject result = EdtDispatcher.readOnEdt(
                "Generate Report Wizard output",
                project -> generateReport(project, body),
                timeoutSeconds);
        HttpBridgeServer.sendJson(exchange, 200, result);
    }

    private JsonObject generateReport(Project project, JsonObject body) throws Exception {
        JsonObject parameters = jsonObject(body, "parameters");
        String outputPath = firstString(body, parameters, "outputPath", "outputFile");
        if (outputPath == null || outputPath.trim().isEmpty()) {
            throw new IllegalArgumentException("outputPath is required");
        }

        File outputFile = new File(outputPath);
        File parent = outputFile.getParentFile();
        if (parent != null && !parent.isDirectory() && !parent.mkdirs()) {
            throw new IllegalArgumentException("Could not create output directory: " + parent.getAbsolutePath());
        }

        List<Object> templates = listTemplates();
        Object selectedTemplate = selectTemplate(templates, body, parameters);
        Object workingTemplate = cloneIfPossible(selectedTemplate);
        Object report = selectReport(workingTemplate, firstString(body, parameters, "reportName", "reportId"));
        configureReport(project, report, body, parameters, outputFile);
        invokeIfPresent(workingTemplate, "setSelectedReport", report);

        Class<?> generateTaskClass = OptionalCapabilitySupport.loadClass(GENERATE_TASK);
        Class<?> templateBeanClass = OptionalCapabilitySupport.loadClass(TEMPLATE_BEAN);
        Constructor<?> constructor = generateTaskClass.getConstructor(templateBeanClass);
        Object task = constructor.newInstance(workingTemplate);

        Class<?> taskClass = OptionalCapabilitySupport.loadClass(TASK);
        Method executeTask = taskClass.getMethod("executeTaskOnSameThread", taskClass);
        executeTask.invoke(null, task);

        Object taskException = invokeZeroArg(task, "getException");
        boolean exists = outputFile.isFile();
        long length = exists ? outputFile.length() : 0L;
        if (taskException != null || !exists || length <= 0L) {
            throw new IllegalStateException("Report generation failed for " + outputFile.getAbsolutePath()
                    + (taskException != null ? ": " + taskException : ""));
        }

        JsonObject response = new JsonObject();
        response.addProperty("family", "reportWizard");
        response.addProperty("generated", true);
        response.addProperty("writePerformed", true);
        response.addProperty("jobId", "inline-" + System.currentTimeMillis());
        response.addProperty("status", "completed");
        response.addProperty("templateName", stringGetter(workingTemplate, "getName"));
        response.addProperty("reportName", stringGetter(report, "getName"));
        response.addProperty("outputPath", outputFile.getAbsolutePath());
        response.addProperty("outputFormat", firstString(body, parameters, "format", "outputFormat"));
        response.addProperty("outputBytes", length);
        response.add("capabilities", capabilities());
        response.add("request", body);
        return response;
    }

    private void configureReport(Project project, Object report, JsonObject body, JsonObject parameters, File outputFile)
            throws Exception {
        Object selection = invokeZeroArg(report, "getSelectedPackage");
        if (selection == null) {
            selection = OptionalCapabilitySupport.loadClass(PACKAGE_SELECTION_BEAN).getConstructor().newInstance();
            invokeIfPresent(report, "setSelectedPackage", selection);
        }
        List<String> scopeIds = firstStringList(body, parameters, "scopeElementIds", "packageIds");
        if (scopeIds.isEmpty()) {
            scopeIds.add(project.getPrimaryModel().getID());
        }
        invokeIfPresent(selection, "setPackageIds", toStringArray(scopeIds));
        invokeIfPresent(selection, "setSelectRecursive", Boolean.valueOf(firstBoolean(body, parameters, "recursive", true)));
        invokeIfPresent(selection, "setShowAuxiliary", Boolean.valueOf(firstBoolean(body, parameters, "showAuxiliary", false)));
        invokeIfPresent(selection, "setShowOnlyPackageElement",
                Boolean.valueOf(firstBoolean(body, parameters, "showOnlyPackageElement", false)));

        Object reportProperty = invokeZeroArg(report, "getReportProperty");
        if (reportProperty == null) {
            reportProperty = OptionalCapabilitySupport.loadClass(REPORT_PROPERTY_BEAN).getConstructor().newInstance();
            invokeIfPresent(report, "setReportProperty", reportProperty);
        }
        String format = normalizeFormat(firstString(body, parameters, "format", "outputFormat"), outputFile);
        invokeIfPresent(reportProperty, "setOutputFile", outputFile.getAbsolutePath());
        invokeIfPresent(reportProperty, "setOutputFormat", format);
        invokeIfPresent(reportProperty, "setDisplayInViewer",
                Boolean.valueOf(firstBoolean(body, parameters, "displayInViewer", false)));
        invokeIfPresent(report, "setFileName", outputFile.getAbsolutePath());
    }

    private void handleJob(HttpExchange exchange, String jobId) throws IOException {
        JsonObject response = new JsonObject();
        response.addProperty("jobId", jobId);
        response.addProperty("status", "not-found");
        response.addProperty("message", "Report generation currently runs inline and does not persist job state.");
        HttpBridgeServer.sendJson(exchange, 404, response);
    }

    private List<Object> listTemplates() throws Exception {
        Class<?> helper = OptionalCapabilitySupport.loadClass(TEMPLATE_HELPER);
        Method listTemplates = helper.getMethod("listTemplates");
        Object value = listTemplates.invoke(null);
        List<Object> templates = new ArrayList<>();
        if (value instanceof Collection) {
            templates.addAll((Collection<?>) value);
        }
        return templates;
    }

    private Object selectTemplate(List<Object> templates, JsonObject body, JsonObject parameters) {
        if (templates.isEmpty()) {
            throw new IllegalArgumentException("No Report Wizard templates are available");
        }
        String requested = firstString(body, parameters, "templateId", "templateName", "template");
        if (requested == null || requested.trim().isEmpty()) {
            return templates.get(0);
        }
        String normalized = requested.trim().toLowerCase(Locale.ROOT);
        try {
            int index = Integer.parseInt(normalized);
            if (index >= 0 && index < templates.size()) {
                return templates.get(index);
            }
        } catch (NumberFormatException ignored) {
            // Fall through to name/path matching.
        }
        for (Object template : templates) {
            String name = stringGetter(template, "getName");
            String path = stringGetter(template, "getPath");
            String file = stringGetter(template, "getTemplateFileName");
            if (equalsIgnoreCase(normalized, name)
                    || equalsIgnoreCase(normalized, path)
                    || equalsIgnoreCase(normalized, file)) {
                return template;
            }
        }
        throw new IllegalArgumentException("Report template not found: " + requested);
    }

    private Object selectReport(Object template, String reportName) throws Exception {
        Object report = null;
        if (reportName != null && !reportName.trim().isEmpty()) {
            Collection<?> reports = asCollection(invokeZeroArg(template, "getReportList"));
            for (Object candidate : reports) {
                if (equalsIgnoreCase(reportName.trim().toLowerCase(Locale.ROOT), stringGetter(candidate, "getName"))) {
                    report = candidate;
                    break;
                }
            }
        }
        if (report == null) {
            report = invokeZeroArg(template, "getDefaultReport");
        }
        if (report == null) {
            report = invokeZeroArg(template, "getSelectedReport");
        }
        if (report == null) {
            Collection<?> reports = asCollection(invokeZeroArg(template, "getReportList"));
            if (!reports.isEmpty()) {
                report = reports.iterator().next();
            }
        }
        if (report == null) {
            throw new IllegalArgumentException("Selected report template has no report configuration");
        }
        return cloneIfPossible(report);
    }

    private JsonObject serializeTemplate(Object template, int index) {
        JsonObject json = new JsonObject();
        json.addProperty("index", index);
        json.addProperty("id", String.valueOf(index));
        json.addProperty("className", template.getClass().getName());
        putGetter(json, template, "name", "getName");
        putGetter(json, template, "category", "getCategory");
        putGetter(json, template, "description", "getDescription");
        putGetter(json, template, "path", "getPath");
        putGetter(json, template, "templateFileName", "getTemplateFileName");
        putGetter(json, template, "readOnly", "getReadOnly");
        putGetter(json, template, "enabled", "getEnabled");
        putGetter(json, template, "configFile", "getConfigFile");
        putGetter(json, template, "requiredPlugins", "getRequiredPlugins");
        Object reportList = invokeZeroArg(template, "getReportList");
        if (reportList instanceof Collection) {
            json.addProperty("reportCount", ((Collection<?>) reportList).size());
        }
        return json;
    }

    private void putGetter(JsonObject json, Object target, String key, String methodName) {
        try {
            Method method = target.getClass().getMethod(methodName);
            if (method.getParameterCount() == 0) {
                Object value = method.invoke(target);
                json.add(key, PropertySerializer.serializeValue(value, true, false));
            }
        } catch (Exception ignored) {
            // TemplateBean versions differ across CATIA Magic releases.
        }
    }

    private Object cloneIfPossible(Object value) {
        Object clone = invokeZeroArg(value, "clone");
        return clone != null ? clone : value;
    }

    private Object invokeZeroArg(Object target, String methodName) {
        if (target == null) {
            return null;
        }
        try {
            Method method = target.getClass().getMethod(methodName);
            return method.invoke(target);
        } catch (Exception e) {
            return null;
        }
    }

    private void invokeIfPresent(Object target, String methodName, Object arg) throws Exception {
        if (target == null || arg == null) {
            return;
        }
        for (Method method : target.getClass().getMethods()) {
            if (!method.getName().equals(methodName) || method.getParameterCount() != 1) {
                continue;
            }
            Class<?> parameterType = method.getParameterTypes()[0];
            if (parameterType.isPrimitive()
                    || parameterType.isAssignableFrom(arg.getClass())
                    || (parameterType.isArray() && arg.getClass().isArray())) {
                method.invoke(target, arg);
                return;
            }
        }
    }

    private static JsonObject jsonObject(JsonObject source, String key) {
        if (source != null && source.has(key) && source.get(key).isJsonObject()) {
            return source.getAsJsonObject(key);
        }
        return null;
    }

    private static String firstString(JsonObject body, JsonObject parameters, String... keys) {
        for (String key : keys) {
            String value = stringValue(body, key);
            if (value != null) {
                return value;
            }
            value = stringValue(parameters, key);
            if (value != null) {
                return value;
            }
        }
        return null;
    }

    private static String stringValue(JsonObject source, String key) {
        if (source == null || !source.has(key)) {
            return null;
        }
        JsonElement value = source.get(key);
        if (value == null || value.isJsonNull() || !value.isJsonPrimitive()) {
            return null;
        }
        return value.getAsString();
    }

    private static List<String> firstStringList(JsonObject body, JsonObject parameters, String... keys) {
        for (String key : keys) {
            List<String> values = stringList(body, key);
            if (!values.isEmpty()) {
                return values;
            }
            values = stringList(parameters, key);
            if (!values.isEmpty()) {
                return values;
            }
        }
        return new ArrayList<>();
    }

    private static List<String> stringList(JsonObject source, String key) {
        List<String> values = new ArrayList<>();
        if (source == null || !source.has(key)) {
            return values;
        }
        JsonElement value = source.get(key);
        if (value.isJsonArray()) {
            for (JsonElement item : value.getAsJsonArray()) {
                if (item != null && item.isJsonPrimitive()) {
                    values.add(item.getAsString());
                }
            }
        } else if (value.isJsonPrimitive()) {
            values.add(value.getAsString());
        }
        return values;
    }

    private static boolean firstBoolean(JsonObject body, JsonObject parameters, String key, boolean defaultValue) {
        Boolean value = booleanValue(body, key);
        if (value != null) {
            return value;
        }
        value = booleanValue(parameters, key);
        return value != null ? value : defaultValue;
    }

    private static Boolean booleanValue(JsonObject source, String key) {
        if (source == null || !source.has(key) || !source.get(key).isJsonPrimitive()) {
            return null;
        }
        return source.get(key).getAsBoolean();
    }

    private static int boundedInt(JsonObject body, String key, int defaultValue, int min, int max) {
        if (body == null || !body.has(key) || !body.get(key).isJsonPrimitive()) {
            return defaultValue;
        }
        int value = body.get(key).getAsInt();
        return Math.max(min, Math.min(max, value));
    }

    private static Object toStringArray(List<String> values) {
        Object array = Array.newInstance(String.class, values.size());
        for (int i = 0; i < values.size(); i++) {
            Array.set(array, i, values.get(i));
        }
        return array;
    }

    private static String normalizeFormat(String requested, File outputFile) {
        if (requested != null && !requested.trim().isEmpty()) {
            return requested.trim().toLowerCase(Locale.ROOT);
        }
        String name = outputFile.getName();
        int dot = name.lastIndexOf('.');
        if (dot >= 0 && dot + 1 < name.length()) {
            return name.substring(dot + 1).toLowerCase(Locale.ROOT);
        }
        return "docx";
    }

    private static Collection<?> asCollection(Object value) {
        if (value instanceof Collection) {
            return (Collection<?>) value;
        }
        return List.of();
    }

    private static String stringGetter(Object target, String methodName) {
        if (target == null) {
            return "";
        }
        try {
            Object value = target.getClass().getMethod(methodName).invoke(target);
            return value != null ? String.valueOf(value) : "";
        } catch (Exception e) {
            return "";
        }
    }

    private static boolean equalsIgnoreCase(String normalizedNeedle, String candidate) {
        return candidate != null && normalizedNeedle.equals(candidate.trim().toLowerCase(Locale.ROOT));
    }
}
