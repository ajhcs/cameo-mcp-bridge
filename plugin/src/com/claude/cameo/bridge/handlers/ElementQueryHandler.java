package com.claude.cameo.bridge.handlers;

import com.claude.cameo.bridge.HttpBridgeServer;
import com.claude.cameo.bridge.util.EdtDispatcher;
import com.claude.cameo.bridge.util.ElementSerializer;
import com.claude.cameo.bridge.util.JsonHelper;
import com.nomagic.magicdraw.uml.ClassTypes;
import com.nomagic.magicdraw.uml.Finder;
import com.nomagic.uml2.ext.magicdraw.classes.mdkernel.DirectedRelationship;
import com.nomagic.uml2.ext.magicdraw.classes.mdkernel.Element;
import com.nomagic.uml2.ext.magicdraw.classes.mdkernel.NamedElement;
import com.nomagic.uml2.ext.magicdraw.classes.mdkernel.Package;
import com.nomagic.uml2.ext.magicdraw.classes.mdkernel.Relationship;
import com.nomagic.uml2.ext.magicdraw.mdprofiles.Stereotype;
import com.nomagic.uml2.ext.jmi.helpers.StereotypesHelper;
import com.sun.net.httpserver.HttpExchange;
import com.sun.net.httpserver.HttpHandler;
import com.google.gson.JsonArray;
import com.google.gson.JsonObject;

import java.io.IOException;
import java.util.ArrayList;
import java.util.Collection;
import java.util.List;
import java.util.Map;
import java.util.logging.Level;
import java.util.logging.Logger;

/**
 * Handles element query REST endpoints.
 */
public class ElementQueryHandler implements HttpHandler {

    private static final Logger LOG = Logger.getLogger(ElementQueryHandler.class.getName());
    private static final String PREFIX = "/api/v1/elements/";
    private static final int DEFAULT_LIMIT = 200;
    private static final int MAX_LIMIT = 1000;

    @Override
    public void handle(HttpExchange exchange) throws IOException {
        try {
            String method = exchange.getRequestMethod();

            if ("OPTIONS".equals(method)) {
                exchange.getResponseHeaders().set("Access-Control-Allow-Methods", "GET, OPTIONS");
                exchange.getResponseHeaders().set("Access-Control-Allow-Headers", "Content-Type");
                exchange.sendResponseHeaders(204, -1);
                return;
            }

            if (!"GET".equals(method)) {
                HttpBridgeServer.sendError(exchange, 405, "METHOD_NOT_ALLOWED",
                        "Only GET is supported");
                return;
            }

            String path = exchange.getRequestURI().getPath();

            if (path.equals("/api/v1/elements")) {
                handleQueryElements(exchange);
                return;
            }

            String subPath = JsonHelper.extractSubPath(exchange, PREFIX);
            String elementId = JsonHelper.extractPathParam(exchange, PREFIX);

            if (elementId != null && "relationships".equals(subPath)) {
                handleGetRelationships(exchange, elementId);
            } else if (elementId != null && subPath == null) {
                handleGetElement(exchange, elementId);
            } else {
                HttpBridgeServer.sendError(exchange, 404, "NOT_FOUND",
                        "Unknown endpoint: " + path);
            }

        } catch (IllegalArgumentException e) {
            HttpBridgeServer.sendError(exchange, 404, "NOT_FOUND", e.getMessage());
        } catch (Exception e) {
            LOG.log(Level.SEVERE, "Error in ElementQueryHandler", e);
            HttpBridgeServer.sendError(exchange, 500, "INTERNAL_ERROR", e.getMessage());
        }
    }

    private void handleGetElement(HttpExchange exchange, String elementId) throws Exception {
        JsonObject result = EdtDispatcher.read(project -> {
            Element element = (Element) project.getElementByID(elementId);
            if (element == null) {
                throw new IllegalArgumentException("Element not found: " + elementId);
            }
            return ElementSerializer.toJson(element);
        });
        HttpBridgeServer.sendJson(exchange, 200, result);
    }

    private void handleQueryElements(HttpExchange exchange) throws Exception {
        Map<String, String> params = JsonHelper.parseQuery(exchange);
        String typeFilter = params.get("type");
        String nameFilter = params.get("name");
        String packageId = params.get("package");
        String stereotypeFilter = params.get("stereotype");
        boolean recursive = !"false".equalsIgnoreCase(params.get("recursive"));

        int limit = DEFAULT_LIMIT;
        String limitStr = params.get("limit");
        if (limitStr != null) {
            try {
                limit = Math.min(Math.max(Integer.parseInt(limitStr), 1), MAX_LIMIT);
            } catch (NumberFormatException e) {
                // keep default
            }
        }

        final int finalLimit = limit;

        JsonObject result = EdtDispatcher.read(project -> {
            Element scope;
            if (packageId != null && !packageId.isEmpty()) {
                scope = (Element) project.getElementByID(packageId);
                if (scope == null) {
                    throw new IllegalArgumentException("Package element not found: " + packageId);
                }
            } else {
                scope = project.getPrimaryModel();
                if (scope == null) {
                    throw new IllegalStateException("No primary model found in project");
                }
            }

            Class<?> metaclass = null;
            if (typeFilter != null && !typeFilter.isEmpty()) {
                metaclass = resolveMetaclass(typeFilter);
            }

            Collection<? extends Element> candidates;
            if (metaclass != null && nameFilter != null && !nameFilter.isEmpty()) {
                if (recursive) {
                    candidates = Finder.byNameAllRecursively().find(scope, metaclass, nameFilter);
                } else {
                    candidates = Finder.byNameAll().find(scope, metaclass, nameFilter);
                }
            } else if (metaclass != null) {
                if (recursive) {
                    candidates = Finder.byTypeRecursively().find(scope, new Class[]{metaclass});
                } else {
                    candidates = Finder.byType().find(scope, metaclass);
                }
            } else if (nameFilter != null && !nameFilter.isEmpty()) {
                if (recursive) {
                    candidates = Finder.byNameAllRecursively().find(
                            scope, NamedElement.class, nameFilter);
                } else {
                    candidates = Finder.byNameAll().find(
                            scope, NamedElement.class, nameFilter);
                }
            } else {
                if (recursive) {
                    candidates = Finder.byTypeRecursively().find(
                            scope, new Class[]{Element.class});
                } else {
                    candidates = scope.getOwnedElement();
                }
            }

            List<Element> filtered = new ArrayList<>();
            int count = 0;
            for (Element el : candidates) {
                if (count >= finalLimit) break;
                if (stereotypeFilter != null && !stereotypeFilter.isEmpty()) {
                    if (!hasMatchingStereotype(el, stereotypeFilter)) {
                        continue;
                    }
                }
                filtered.add(el);
                count++;
            }

            JsonArray elements = new JsonArray();
            for (Element el : filtered) {
                elements.add(ElementSerializer.toJsonCompact(el));
            }

            JsonObject response = new JsonObject();
            response.addProperty("count", filtered.size());
            response.addProperty("limit", finalLimit);
            response.add("elements", elements);
            return response;
        });

        HttpBridgeServer.sendJson(exchange, 200, result);
    }

    private void handleGetRelationships(HttpExchange exchange, String elementId) throws Exception {
        JsonObject result = EdtDispatcher.read(project -> {
            Element element = (Element) project.getElementByID(elementId);
            if (element == null) {
                throw new IllegalArgumentException("Element not found: " + elementId);
            }

            JsonArray outgoing = new JsonArray();
            JsonArray incoming = new JsonArray();

            try {
                Collection<DirectedRelationship> sourceRels =
                        element.get_directedRelationshipOfSource();
                if (sourceRels != null) {
                    for (DirectedRelationship rel : sourceRels) {
                        outgoing.add(serializeRelationship(rel, "outgoing"));
                    }
                }
            } catch (Exception e) {
                LOG.log(Level.FINE, "Error reading outgoing relationships", e);
            }

            try {
                Collection<DirectedRelationship> targetRels =
                        element.get_directedRelationshipOfTarget();
                if (targetRels != null) {
                    for (DirectedRelationship rel : targetRels) {
                        incoming.add(serializeRelationship(rel, "incoming"));
                    }
                }
            } catch (Exception e) {
                LOG.log(Level.FINE, "Error reading incoming relationships", e);
            }

            JsonArray undirected = new JsonArray();
            try {
                Collection<Relationship> allRels = element.get_relationshipOfRelatedElement();
                if (allRels != null) {
                    for (Relationship rel : allRels) {
                        if (rel instanceof DirectedRelationship) {
                            continue;
                        }
                        undirected.add(serializeUndirectedRelationship(rel, elementId));
                    }
                }
            } catch (Exception e) {
                LOG.log(Level.FINE, "Error reading undirected relationships", e);
            }

            JsonObject response = new JsonObject();
            response.addProperty("elementId", elementId);
            response.add("outgoing", outgoing);
            response.add("incoming", incoming);
            if (undirected.size() > 0) {
                response.add("undirected", undirected);
            }
            response.addProperty("totalCount",
                    outgoing.size() + incoming.size() + undirected.size());
            return response;
        });

        HttpBridgeServer.sendJson(exchange, 200, result);
    }

    @SuppressWarnings("unchecked")
    private Class<?> resolveMetaclass(String typeInput) {
        String normalized = normalizeTypeName(typeInput);

        Class<?> clazz = ClassTypes.getClassType(normalized);
        if (clazz != null) return clazz;

        clazz = ClassTypes.getClassType(typeInput);
        if (clazz != null) return clazz;

        String capitalized = typeInput.substring(0, 1).toUpperCase() + typeInput.substring(1);
        clazz = ClassTypes.getClassType(capitalized);
        if (clazz != null) return clazz;

        LOG.warning("Could not resolve metaclass for type: " + typeInput);
        return null;
    }

    private String normalizeTypeName(String input) {
        if (input == null || input.isEmpty()) return input;
        String[] parts = input.split("[-_ ]+");
        StringBuilder sb = new StringBuilder();
        for (String part : parts) {
            if (!part.isEmpty()) {
                sb.append(Character.toUpperCase(part.charAt(0)));
                if (part.length() > 1) {
                    sb.append(part.substring(1));
                }
            }
        }
        return sb.toString();
    }

    private boolean hasMatchingStereotype(Element element, String stereotypeName) {
        try {
            List<Stereotype> stereotypes = StereotypesHelper.getStereotypes(element);
            if (stereotypes != null) {
                for (Stereotype st : stereotypes) {
                    if (st.getName().equalsIgnoreCase(stereotypeName)) {
                        return true;
                    }
                }
            }
        } catch (Exception e) {
            LOG.log(Level.FINE, "Error checking stereotypes", e);
        }
        return false;
    }

    private JsonObject serializeRelationship(DirectedRelationship rel, String direction) {
        JsonObject json = new JsonObject();
        json.addProperty("relationshipId", rel.getID());
        json.addProperty("direction", direction);

        try {
            String shortName = ClassTypes.getShortName(rel.getClassType());
            json.addProperty("type", shortName != null ? shortName : rel.getHumanType());
        } catch (Exception e) {
            json.addProperty("type", rel.getHumanType());
        }

        if (rel instanceof NamedElement) {
            String name = ((NamedElement) rel).getName();
            if (name != null && !name.isEmpty()) {
                json.addProperty("name", name);
            }
        }

        JsonArray sources = new JsonArray();
        try {
            for (Element src : rel.getSource()) {
                JsonObject srcJson = new JsonObject();
                srcJson.addProperty("id", src.getID());
                if (src instanceof NamedElement) {
                    srcJson.addProperty("name", ((NamedElement) src).getName());
                }
                sources.add(srcJson);
            }
        } catch (Exception e) {
            LOG.log(Level.FINE, "Error reading relationship sources", e);
        }
        json.add("sources", sources);

        JsonArray targets = new JsonArray();
        try {
            for (Element tgt : rel.getTarget()) {
                JsonObject tgtJson = new JsonObject();
                tgtJson.addProperty("id", tgt.getID());
                if (tgt instanceof NamedElement) {
                    tgtJson.addProperty("name", ((NamedElement) tgt).getName());
                }
                targets.add(tgtJson);
            }
        } catch (Exception e) {
            LOG.log(Level.FINE, "Error reading relationship targets", e);
        }
        json.add("targets", targets);

        return json;
    }

    private JsonObject serializeUndirectedRelationship(Relationship rel, String selfId) {
        JsonObject json = new JsonObject();
        json.addProperty("relationshipId", rel.getID());
        json.addProperty("direction", "undirected");

        try {
            String shortName = ClassTypes.getShortName(rel.getClassType());
            json.addProperty("type", shortName != null ? shortName : rel.getHumanType());
        } catch (Exception e) {
            json.addProperty("type", rel.getHumanType());
        }

        if (rel instanceof NamedElement) {
            String name = ((NamedElement) rel).getName();
            if (name != null && !name.isEmpty()) {
                json.addProperty("name", name);
            }
        }

        JsonArray relatedElements = new JsonArray();
        try {
            for (Element related : rel.getRelatedElement()) {
                if (!related.getID().equals(selfId)) {
                    JsonObject relJson = new JsonObject();
                    relJson.addProperty("id", related.getID());
                    if (related instanceof NamedElement) {
                        relJson.addProperty("name", ((NamedElement) related).getName());
                    }
                    relatedElements.add(relJson);
                }
            }
        } catch (Exception e) {
            LOG.log(Level.FINE, "Error reading related elements", e);
        }
        json.add("relatedElements", relatedElements);

        return json;
    }
}
