package com.claude.cameo.bridge.handlers;

import com.claude.cameo.bridge.HttpBridgeServer;
import com.claude.cameo.bridge.util.EdtDispatcher;
import com.claude.cameo.bridge.util.ElementSerializer;
import com.claude.cameo.bridge.util.JsonHelper;
import com.claude.cameo.bridge.util.OptionalCapabilitySupport;
import com.claude.cameo.bridge.util.ValidationSerializer;
import com.google.gson.JsonArray;
import com.google.gson.JsonObject;
import com.nomagic.magicdraw.annotation.Annotation;
import com.nomagic.magicdraw.core.Application;
import com.nomagic.magicdraw.core.Project;
import com.nomagic.magicdraw.uml.Finder;
import com.nomagic.magicdraw.validation.RuleViolationResult;
import com.nomagic.magicdraw.validation.ValidationHelper;
import com.nomagic.magicdraw.validation.ValidationRunData;
import com.nomagic.uml2.ext.magicdraw.classes.mdkernel.Constraint;
import com.nomagic.uml2.ext.magicdraw.classes.mdkernel.Element;
import com.nomagic.uml2.ext.magicdraw.classes.mdkernel.EnumerationLiteral;
import com.nomagic.uml2.ext.magicdraw.classes.mdkernel.Package;
import com.sun.net.httpserver.HttpExchange;
import com.sun.net.httpserver.HttpHandler;

import java.io.IOException;
import java.time.Instant;
import java.util.ArrayList;
import java.util.Collection;
import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.UUID;

public class ValidationHandler implements HttpHandler {

    private static final String PREFIX = "/api/v1/validation/";
    private static final int DISCOVERY_LIMIT = 250;
    private static final int RESULT_STORE_LIMIT = 50;
    private static final Map<String, JsonObject> RESULTS = Collections.synchronizedMap(
            new LinkedHashMap<String, JsonObject>() {
                @Override
                protected boolean removeEldestEntry(Map.Entry<String, JsonObject> eldest) {
                    return size() > RESULT_STORE_LIMIT;
                }
            });

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

            if ("GET".equals(method) && path.equals("/api/v1/validation/capabilities")) {
                handleCapabilities(exchange);
            } else if ("GET".equals(method) && path.equals("/api/v1/validation/suites")) {
                handleSuites(exchange);
            } else if ("POST".equals(method) && path.equals("/api/v1/validation/run")) {
                handleRun(exchange);
            } else if ("GET".equals(method) && path.startsWith(PREFIX + "results/")) {
                handleGetResult(exchange, path.substring((PREFIX + "results/").length()));
            } else {
                HttpBridgeServer.sendError(exchange, 404, "NOT_FOUND", "Unknown endpoint: " + path);
            }
        } catch (IllegalArgumentException e) {
            HttpBridgeServer.sendError(exchange, 400, "VALIDATION_BAD_REQUEST", e.getMessage());
        } catch (IllegalStateException e) {
            HttpBridgeServer.sendError(exchange, 409, "VALIDATION_STATE_CONFLICT", e.getMessage());
        } catch (Exception e) {
            HttpBridgeServer.sendError(exchange, 500, "VALIDATION_ERROR", e.getMessage());
        }
    }

    private void handleCapabilities(HttpExchange exchange) throws IOException {
        JsonObject response = OptionalCapabilitySupport.baseCapabilities("validation", "native");
        JsonObject probe = OptionalCapabilitySupport.classProbe(
                "com.nomagic.magicdraw.validation.ValidationHelper",
                "com.nomagic.magicdraw.validation.ValidationRunData",
                "com.nomagic.magicdraw.validation.RuleViolationResult");
        response.addProperty("available", probe.get("allFound").getAsBoolean());
        response.addProperty("status", probe.get("allFound").getAsBoolean() ? "available" : "missing-class");
        response.add("classProbe", probe);
        JsonArray routes = new JsonArray();
        routes.add("GET /api/v1/validation/capabilities");
        routes.add("GET /api/v1/validation/suites");
        routes.add("POST /api/v1/validation/run");
        routes.add("GET /api/v1/validation/results/{runId}");
        response.add("routes", routes);
        response.addProperty("resultStoreLimit", RESULT_STORE_LIMIT);
        HttpBridgeServer.sendJson(exchange, 200, response);
    }

    private void handleSuites(HttpExchange exchange) throws Exception {
        JsonObject result = EdtDispatcher.read(project -> {
            JsonArray knownSuites = new JsonArray();
            addKnownSuite(project, knownSuites,
                    "UML Standard Profile::Validation Profile::Active Validation::UML Correctness");
            addKnownSuite(project, knownSuites,
                    "UML Standard Profile::Validation Profile::Active Validation");

            JsonArray candidateSuites = new JsonArray();
            JsonArray candidateConstraints = new JsonArray();
            Element root = project.getPrimaryModel();
            if (root != null) {
                Collection<? extends Element> packages = Finder.byTypeRecursively()
                        .find(root, new Class[]{Package.class});
                int suiteCount = 0;
                for (Element element : packages) {
                    if (element instanceof Package && looksValidationRelated(element) && suiteCount < DISCOVERY_LIMIT) {
                        candidateSuites.add(ValidationSerializer.suite((Package) element));
                        suiteCount++;
                    }
                }

                Collection<? extends Element> constraints = Finder.byTypeRecursively()
                        .find(root, new Class[]{Constraint.class});
                int constraintCount = 0;
                for (Element element : constraints) {
                    if (element instanceof Constraint && looksValidationRelated(element)
                            && constraintCount < DISCOVERY_LIMIT) {
                        candidateConstraints.add(ValidationSerializer.constraint((Constraint) element));
                        constraintCount++;
                    }
                }
            }

            JsonObject response = new JsonObject();
            response.addProperty("available", true);
            response.add("projectState", OptionalCapabilitySupport.projectState());
            response.add("knownSuites", knownSuites);
            response.add("candidateSuites", candidateSuites);
            response.add("candidateConstraints", candidateConstraints);
            response.addProperty("knownSuiteCount", knownSuites.size());
            response.addProperty("candidateSuiteCount", candidateSuites.size());
            response.addProperty("candidateConstraintCount", candidateConstraints.size());
            response.addProperty("discoveryLimit", DISCOVERY_LIMIT);
            response.addProperty("listingConfidence", knownSuites.size() > 0 ? "high" : "heuristic");
            return response;
        });
        HttpBridgeServer.sendJson(exchange, 200, result);
    }

    private void handleRun(HttpExchange exchange) throws Exception {
        JsonObject body = JsonHelper.parseBody(exchange);
        JsonObject result = EdtDispatcher.read(project -> {
            long started = System.currentTimeMillis();
            String runId = UUID.randomUUID().toString();
            ValidationRunData runData = buildRunData(project, body);
            runData.setEnableSettingsDialog(false);
            if (body.has("recursive")) {
                runData.setAddElementsRecursively(body.get("recursive").getAsBoolean());
            }

            Collection<RuleViolationResult> findings =
                    ValidationHelper.validate(runData, "MCP Bridge native validation", null);
            if (body.has("openNativeWindow") && body.get("openNativeWindow").getAsBoolean()) {
                ValidationHelper.openValidationWindow(runData, "MCP_BRIDGE_" + runId, findings);
            }

            JsonObject response = new JsonObject();
            response.addProperty("runId", runId);
            response.addProperty("startedAt", Instant.ofEpochMilli(started).toString());
            response.addProperty("completedAt", Instant.now().toString());
            response.addProperty("durationMillis", System.currentTimeMillis() - started);
            response.addProperty("openNativeWindow", body.has("openNativeWindow")
                    && body.get("openNativeWindow").getAsBoolean());
            response.add("projectState", OptionalCapabilitySupport.projectState());
            response.add("request", body);
            JsonArray findingArray = ValidationSerializer.findings(findings);
            response.addProperty("findingCount", findingArray.size());
            response.add("findings", findingArray);
            RESULTS.put(runId, response);
            return response;
        });
        HttpBridgeServer.sendJson(exchange, 200, result);
    }

    private void handleGetResult(HttpExchange exchange, String runId) throws IOException {
        JsonObject result = RESULTS.get(runId);
        if (result == null) {
            HttpBridgeServer.sendError(exchange, 404, "VALIDATION_RESULT_NOT_FOUND",
                    "No validation result cached for runId: " + runId);
            return;
        }
        HttpBridgeServer.sendJson(exchange, 200, result);
    }

    private ValidationRunData buildRunData(Project project, JsonObject body) {
        String suiteId = JsonHelper.optionalString(body, "suiteId");
        String suiteQualifiedName = JsonHelper.optionalString(body, "suiteQualifiedName");
        List<String> constraintIds = JsonHelper.optionalStringList(body, "constraintIds");
        boolean wholeProject = optionalBoolean(body, "wholeProject", true);
        boolean excludeReadOnly = optionalBoolean(body, "excludeReadOnly", true);
        String requestedSeverity = JsonHelper.optionalString(body, "minimumSeverity");
        if (requestedSeverity == null) {
            requestedSeverity = JsonHelper.optionalString(body, "minSeverity");
        }
        EnumerationLiteral severity = severity(project, requestedSeverity);
        Collection<Element> scope = scopeElements(project, body);

        if (constraintIds != null && !constraintIds.isEmpty()) {
            List<Constraint> constraints = new ArrayList<>();
            for (String constraintId : constraintIds) {
                Element element = (Element) project.getElementByID(constraintId);
                if (!(element instanceof Constraint)) {
                    throw new IllegalArgumentException("Constraint not found: " + constraintId);
                }
                constraints.add((Constraint) element);
            }
            return new ValidationRunData(constraints, "MCP Bridge native validation",
                    wholeProject, scope, severity, excludeReadOnly);
        }

        Element suiteElement = null;
        if (suiteId != null) {
            suiteElement = (Element) project.getElementByID(suiteId);
        } else if (suiteQualifiedName != null) {
            suiteElement = Finder.byQualifiedName().find(project, suiteQualifiedName);
        } else {
            suiteElement = Finder.byQualifiedName().find(project,
                    "UML Standard Profile::Validation Profile::Active Validation::UML Correctness");
        }

        if (!(suiteElement instanceof Package)) {
            throw new IllegalArgumentException("Validation suite package not found; provide suiteId or constraintIds");
        }
        return new ValidationRunData((Package) suiteElement, wholeProject, scope, severity, excludeReadOnly);
    }

    private Collection<Element> scopeElements(Project project, JsonObject body) {
        List<String> ids = JsonHelper.optionalStringList(body, "scopeElementIds");
        if (ids == null || ids.isEmpty()) {
            Element root = project.getPrimaryModel();
            return root == null ? Collections.emptyList() : Collections.singletonList(root);
        }
        List<Element> elements = new ArrayList<>();
        for (String id : ids) {
            Element element = (Element) project.getElementByID(id);
            if (element == null) {
                throw new IllegalArgumentException("Scope element not found: " + id);
            }
            elements.add(element);
        }
        return elements;
    }

    private EnumerationLiteral severity(Project project, String requested) {
        if (requested == null || "any".equalsIgnoreCase(requested)) {
            return null;
        }
        String normalized = requested.toLowerCase(Locale.ROOT);
        String constant;
        if ("fatal".equals(normalized)) {
            constant = Annotation.FATAL;
        } else if ("warning".equals(normalized) || "warn".equals(normalized)) {
            constant = Annotation.WARNING;
        } else if ("info".equals(normalized)) {
            constant = Annotation.INFO;
        } else if ("debug".equals(normalized)) {
            constant = Annotation.DEBUG;
        } else {
            constant = Annotation.ERROR;
        }
        return Annotation.getSeverityLevel(project, constant);
    }

    private void addKnownSuite(Project project, JsonArray array, String qualifiedName) {
        Element element = Finder.byQualifiedName().find(project, qualifiedName);
        if (element instanceof Package) {
            JsonObject suite = ValidationSerializer.suite((Package) element);
            suite.addProperty("qualifiedNameProbe", qualifiedName);
            suite.addProperty("discoveryType", "knownQualifiedName");
            array.add(suite);
        }
    }

    private boolean looksValidationRelated(Element element) {
        String text = (element instanceof com.nomagic.uml2.ext.magicdraw.classes.mdkernel.NamedElement)
                ? ((com.nomagic.uml2.ext.magicdraw.classes.mdkernel.NamedElement) element).getName()
                : "";
        if (text == null) {
            text = "";
        }
        Element owner = element.getOwner();
        if (owner instanceof com.nomagic.uml2.ext.magicdraw.classes.mdkernel.NamedElement) {
            String ownerName = ((com.nomagic.uml2.ext.magicdraw.classes.mdkernel.NamedElement) owner).getName();
            if (ownerName != null) {
                text += " " + ownerName;
            }
        }
        String lower = text.toLowerCase(Locale.ROOT);
        return lower.contains("validation")
                || lower.contains("correctness")
                || lower.contains("constraint")
                || lower.contains("suite")
                || lower.contains("sysml")
                || lower.contains("requirement");
    }

    private boolean optionalBoolean(JsonObject body, String key, boolean defaultValue) {
        return body.has(key) && !body.get(key).isJsonNull() ? body.get(key).getAsBoolean() : defaultValue;
    }
}
