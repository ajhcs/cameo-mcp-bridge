package com.claude.cameo.bridge.handlers;

import com.claude.cameo.bridge.HttpBridgeServer;
import com.claude.cameo.bridge.util.EdtDispatcher;
import com.claude.cameo.bridge.util.ElementSerializer;
import com.claude.cameo.bridge.util.JsonHelper;
import com.claude.cameo.bridge.util.OptionalCapabilitySupport;
import com.nomagic.magicdraw.openapi.uml.ModelElementsManager;
import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import com.nomagic.uml2.ext.magicdraw.classes.mdkernel.Comment;
import com.nomagic.uml2.ext.magicdraw.classes.mdkernel.Element;
import com.nomagic.uml2.ext.magicdraw.classes.mdkernel.NamedElement;
import com.nomagic.uml2.ext.magicdraw.classes.mdkernel.Package;
import com.nomagic.uml2.ext.magicdraw.mdprofiles.Stereotype;
import com.nomagic.uml2.ext.jmi.helpers.StereotypesHelper;
import com.nomagic.uml2.impl.ElementsFactory;
import com.sun.net.httpserver.HttpExchange;
import com.sun.net.httpserver.HttpHandler;

import java.io.IOException;
import java.util.ArrayList;
import java.util.Collection;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;

public class ImportExportHandler implements HttpHandler {

    private static final String REQIF_UTILS = "com.nomagic.requirements.reqif.ReqIFUtils";
    private static final String REQIF_MAPPING_MANAGER = "com.nomagic.requirements.reqif.mapping.ReqIFMappingManager";

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

            if ("GET".equals(method) && path.equals("/api/v1/import-export/capabilities")) {
                handleCapabilities(exchange);
            } else if ("POST".equals(method) && path.equals("/api/v1/import-export/requirements/export")) {
                handleRequirementsExport(exchange);
            } else if ("POST".equals(method) && path.equals("/api/v1/import-export/requirements/import-preview")) {
                handleImportPreview(exchange);
            } else if ("POST".equals(method) && path.equals("/api/v1/import-export/requirements/apply")) {
                handleApply(exchange);
            } else {
                HttpBridgeServer.sendError(exchange, 404, "NOT_FOUND", "Unknown endpoint: " + path);
            }
        } catch (IllegalArgumentException e) {
            HttpBridgeServer.sendError(exchange, 400, "IMPORT_EXPORT_BAD_REQUEST", e.getMessage());
        } catch (Exception e) {
            HttpBridgeServer.sendError(exchange, 500, "IMPORT_EXPORT_ERROR", e.getMessage());
        }
    }

    private void handleCapabilities(HttpExchange exchange) throws IOException {
        HttpBridgeServer.sendJson(exchange, 200, capabilities());
    }

    private JsonObject capabilities() {
        JsonObject response = OptionalCapabilitySupport.baseCapabilities("importExport", "bridge-owned-plus-native-probe");
        response.addProperty("available", true);
        response.addProperty("status", "available");
        response.addProperty("csvJsonBridgeOwned", true);
        response.addProperty("xlsxBridgeOwned", false);
        JsonObject reqifProbe = OptionalCapabilitySupport.classProbe(REQIF_UTILS, REQIF_MAPPING_MANAGER);
        response.add("reqifClassProbe", reqifProbe);
        response.addProperty("nativeReqifAvailable", reqifProbe.get("allFound").getAsBoolean());
        response.add("pluginDirectoriesFound", OptionalCapabilitySupport.pluginDirectories("requirements", "reqif", "import"));
        response.addProperty("nativeImportMode", "preview-required");
        return response;
    }

    private void handleRequirementsExport(HttpExchange exchange) throws Exception {
        JsonObject body = JsonHelper.parseBody(exchange);
        JsonObject result = EdtDispatcher.read(project -> {
            JsonArray requirements = new JsonArray();
            String rootId = JsonHelper.optionalString(body, "rootId");
            if (rootId == null) {
                rootId = JsonHelper.optionalString(body, "packageId");
            }
            Element root = rootId != null ? (Element) project.getElementByID(rootId) : project.getPrimaryModel();
            if (root != null) {
                int limit = body.has("limit") ? Math.max(1, Math.min(5000, body.get("limit").getAsInt())) : 1000;
                List<Element> elements = new ArrayList<>();
                collectElements(root, elements, limit);
                for (Element element : elements) {
                    if (requirements.size() >= limit) {
                        break;
                    }
                    if (isRequirementLike(element)) {
                        requirements.add(ElementSerializer.toJson(element));
                    }
                }
            }
            JsonObject response = new JsonObject();
            response.addProperty("format", "json");
            response.addProperty("rootId", root != null ? root.getID() : "");
            response.addProperty("nativeReqifRequested", body.has("format")
                    && "reqif".equalsIgnoreCase(body.get("format").getAsString()));
            response.addProperty("nativeReqifWritten", false);
            response.addProperty("count", requirements.size());
            response.add("requirements", requirements);
            response.add("capabilities", capabilities());
            response.add("request", body);
            return response;
        });
        HttpBridgeServer.sendJson(exchange, 200, result);
    }

    private void collectElements(Element root, List<Element> elements, int limit) {
        if (root == null || elements.size() >= limit) {
            return;
        }
        elements.add(root);
        Collection<Element> children = root.getOwnedElement();
        if (children == null) {
            return;
        }
        for (Element child : children) {
            if (elements.size() >= limit) {
                return;
            }
            collectElements(child, elements, limit);
        }
    }

    private void handleImportPreview(HttpExchange exchange) throws Exception {
        JsonObject body = JsonHelper.parseBody(exchange);
        JsonObject response = buildImportPreview(
                body,
                "Requirements import preview accepted. No model write was performed.");
        HttpBridgeServer.sendJson(exchange, 200, response);
    }

    private void handleApply(HttpExchange exchange) throws Exception {
        JsonObject body = JsonHelper.parseBody(exchange);
        String format = JsonHelper.optionalString(body, "format");
        if (format == null || format.isEmpty()) {
            format = "json";
        }
        if ("reqif".equalsIgnoreCase(format)) {
            JsonObject response = OptionalCapabilitySupport.unsupported(
                    "importExport",
                    "Native ReqIF apply remains gated until a sample ReqIF import/export roundtrip is captured.",
                    "Use JSON/CSV bridge-owned apply for disposable-package tests; keep ReqIF preview-only.");
            response.add("request", body);
            HttpBridgeServer.sendJson(exchange, 403, response);
            return;
        }
        boolean dryRun = !body.has("dryRun") || body.get("dryRun").getAsBoolean();
        if (dryRun) {
            JsonObject response = buildImportPreview(body, "Requirements import dry run accepted. No model write was performed.");
            response.addProperty("dryRun", true);
            HttpBridgeServer.sendJson(exchange, 200, response);
            return;
        }
        boolean allowWrite = body.has("allowWrite") && body.get("allowWrite").getAsBoolean();
        if (!allowWrite) {
            JsonObject response = OptionalCapabilitySupport.unsupported(
                    "importExport",
                    "Requirements import apply requires allowWrite=true in addition to dryRun=false.",
                    "Preview first, then repeat the request with dryRun=false, allowWrite=true, and a disposable targetPackageId.");
            response.add("request", body);
            HttpBridgeServer.sendJson(exchange, 403, response);
            return;
        }
        final String finalFormat = format;

        JsonObject result = EdtDispatcher.write("Apply requirements import", project -> {
            String targetPackageId = JsonHelper.requireString(body, "targetPackageId");
            Element target = (Element) project.getElementByID(targetPackageId);
            if (!(target instanceof Package)) {
                throw new IllegalArgumentException("targetPackageId must reference a Package: " + targetPackageId);
            }
            List<Map<String, String>> rows = parseRequirementRows(body);
            if (rows.isEmpty()) {
                throw new IllegalArgumentException("No requirements supplied. Use requirements array, rows array, or csvText.");
            }

            ElementsFactory ef = project.getElementsFactory();
            Stereotype requirementStereo = findStereotype(project, "requirement");
            JsonArray created = new JsonArray();
            for (Map<String, String> row : rows) {
                String name = firstNonBlank(row.get("name"), row.get("id"), row.get("externalId"), row.get("key"));
                if (name == null) {
                    throw new IllegalArgumentException("Each imported requirement needs name, id, externalId, or key");
                }
                com.nomagic.uml2.ext.magicdraw.classes.mdkernel.Class requirement = ef.createClassInstance();
                requirement.setName(name);
                ModelElementsManager.getInstance().addElement(requirement, target);
                if (requirementStereo != null && !StereotypesHelper.hasStereotype(requirement, requirementStereo)) {
                    StereotypesHelper.addStereotype(requirement, requirementStereo);
                }
                String text = firstNonBlank(row.get("text"), row.get("documentation"), row.get("description"));
                if (text != null) {
                    Comment comment = ef.createCommentInstance();
                    comment.setBody(text);
                    ModelElementsManager.getInstance().addElement(comment, requirement);
                }
                JsonObject entry = ElementSerializer.toJson(requirement);
                String externalId = firstNonBlank(row.get("externalId"), row.get("id"), row.get("key"));
                if (externalId != null) {
                    entry.addProperty("externalId", externalId);
                }
                created.add(entry);
            }

            JsonObject response = new JsonObject();
            response.addProperty("applied", true);
            response.addProperty("writePerformed", true);
            response.addProperty("format", finalFormat.toLowerCase(Locale.ROOT));
            response.addProperty("targetPackageId", targetPackageId);
            response.addProperty("createdCount", created.size());
            response.add("created", created);
            response.add("capabilities", capabilities());
            response.add("request", body);
            return response;
        }, 60);
        HttpBridgeServer.sendJson(exchange, 200, result);
    }

    private JsonObject buildImportPreview(JsonObject body, String message) {
        JsonObject response = OptionalCapabilitySupport.previewAccepted("importExport", body, message);
        response.addProperty("patchPlanReady", true);
        JsonObject patchPlan = new JsonObject();
        patchPlan.addProperty("operation", "requirements-import");
        patchPlan.addProperty("writePerformed", false);
        patchPlan.addProperty("requiresStableElementIdsOrExternalKeys", true);
        patchPlan.addProperty("nativeReqifImportEnabled", false);
        response.add("patchPlan", patchPlan);
        response.add("capabilities", capabilities());
        return response;
    }

    private List<Map<String, String>> parseRequirementRows(JsonObject body) {
        List<Map<String, String>> rows = new ArrayList<>();
        JsonArray array = null;
        if (body.has("requirements") && body.get("requirements").isJsonArray()) {
            array = body.getAsJsonArray("requirements");
        } else if (body.has("rows") && body.get("rows").isJsonArray()) {
            array = body.getAsJsonArray("rows");
        }
        if (array != null) {
            for (JsonElement item : array) {
                if (!item.isJsonObject()) {
                    throw new IllegalArgumentException("Requirement rows must be objects");
                }
                rows.add(rowFromObject(item.getAsJsonObject()));
            }
        }

        String csvText = JsonHelper.optionalString(body, "csvText");
        if (csvText != null && !csvText.trim().isEmpty()) {
            rows.addAll(rowsFromCsv(csvText));
        }
        return rows;
    }

    private Map<String, String> rowFromObject(JsonObject object) {
        Map<String, String> row = new LinkedHashMap<>();
        for (String key : object.keySet()) {
            JsonElement value = object.get(key);
            if (value != null && !value.isJsonNull() && value.isJsonPrimitive()) {
                row.put(key, value.getAsString());
            }
        }
        return row;
    }

    private List<Map<String, String>> rowsFromCsv(String csvText) {
        String[] lines = csvText.replace("\r\n", "\n").replace('\r', '\n').split("\n");
        List<Map<String, String>> rows = new ArrayList<>();
        List<String> headers = null;
        for (String line : lines) {
            if (line == null || line.trim().isEmpty()) {
                continue;
            }
            List<String> cells = parseCsvLine(line);
            if (headers == null) {
                headers = cells;
                continue;
            }
            Map<String, String> row = new LinkedHashMap<>();
            for (int i = 0; i < Math.min(headers.size(), cells.size()); i++) {
                row.put(headers.get(i), cells.get(i));
            }
            rows.add(row);
        }
        return rows;
    }

    private List<String> parseCsvLine(String line) {
        List<String> cells = new ArrayList<>();
        StringBuilder current = new StringBuilder();
        boolean quoted = false;
        for (int i = 0; i < line.length(); i++) {
            char ch = line.charAt(i);
            if (ch == '"') {
                if (quoted && i + 1 < line.length() && line.charAt(i + 1) == '"') {
                    current.append('"');
                    i++;
                } else {
                    quoted = !quoted;
                }
            } else if (ch == ',' && !quoted) {
                cells.add(current.toString());
                current.setLength(0);
            } else {
                current.append(ch);
            }
        }
        cells.add(current.toString());
        return cells;
    }

    private Stereotype findStereotype(com.nomagic.magicdraw.core.Project project, String stereotypeName) {
        Collection<Stereotype> allStereotypes = StereotypesHelper.getAllStereotypes(project);
        if (allStereotypes == null) {
            return null;
        }
        List<Stereotype> matches = new ArrayList<>();
        for (Stereotype stereotype : allStereotypes) {
            if (stereotype.getName() != null && stereotypeName.equalsIgnoreCase(stereotype.getName())) {
                matches.add(stereotype);
            }
        }
        for (String preferred : List.of("SysML", "SysML Profile", "Requirements")) {
            for (Stereotype stereotype : matches) {
                if (ownerChainContains(stereotype, preferred)) {
                    return stereotype;
                }
            }
        }
        return matches.isEmpty() ? null : matches.get(0);
    }

    private boolean ownerChainContains(Element element, String ownerName) {
        Element current = element;
        while (current != null) {
            if (current instanceof NamedElement) {
                String currentName = ((NamedElement) current).getName();
                if (currentName != null && ownerName.equalsIgnoreCase(currentName)) {
                    return true;
                }
            }
            current = current.getOwner();
        }
        return false;
    }

    private String firstNonBlank(String... values) {
        for (String value : values) {
            if (value != null && !value.trim().isEmpty()) {
                return value.trim();
            }
        }
        return null;
    }

    private boolean isRequirementLike(Element element) {
        String className = element.getClass().getSimpleName();
        if (className != null && className.toLowerCase(Locale.ROOT).contains("requirement")) {
            return true;
        }
        try {
            for (Stereotype stereotype : StereotypesHelper.getStereotypes(element)) {
                String stereotypeName = stereotype.getName();
                if (stereotypeName != null
                        && stereotypeName.toLowerCase(Locale.ROOT).contains("requirement")) {
                    return true;
                }
            }
        } catch (Exception ignored) {
            // Some element kinds do not expose stereotype state cleanly.
        }
        return false;
    }
}
