package com.claude.cameo.bridge.handlers;

import com.claude.cameo.bridge.HttpBridgeServer;
import com.claude.cameo.bridge.util.EdtDispatcher;
import com.claude.cameo.bridge.util.ElementSerializer;
import com.claude.cameo.bridge.util.JsonHelper;
import com.nomagic.magicdraw.uml.ClassTypes;
import com.nomagic.magicdraw.uml.Finder;
import com.nomagic.magicdraw.uml2.Connectors;
import com.nomagic.uml2.ext.magicdraw.activities.mdbasicactivities.ActivityEdge;
import com.nomagic.uml2.ext.magicdraw.activities.mdfundamentalactivities.ActivityNode;
import com.nomagic.uml2.ext.magicdraw.auxiliaryconstructs.mdinformationflows.InformationFlow;
import com.nomagic.uml2.ext.magicdraw.compositestructures.mdinternalstructures.ConnectableElement;
import com.nomagic.uml2.ext.magicdraw.compositestructures.mdinternalstructures.Connector;
import com.nomagic.uml2.ext.magicdraw.compositestructures.mdinternalstructures.ConnectorEnd;
import com.nomagic.uml2.ext.magicdraw.classes.mdkernel.DirectedRelationship;
import com.nomagic.uml2.ext.magicdraw.classes.mdkernel.Element;
import com.nomagic.uml2.ext.magicdraw.classes.mdkernel.NamedElement;
import com.nomagic.uml2.ext.magicdraw.classes.mdkernel.Package;
import com.nomagic.uml2.ext.magicdraw.classes.mdkernel.Property;
import com.nomagic.uml2.ext.magicdraw.classes.mdkernel.Relationship;
import com.nomagic.uml2.ext.magicdraw.mdprofiles.Stereotype;
import com.nomagic.uml2.ext.jmi.helpers.StereotypesHelper;
import com.sun.net.httpserver.HttpExchange;
import com.sun.net.httpserver.HttpHandler;
import com.google.gson.JsonArray;
import com.google.gson.JsonObject;

import java.io.IOException;
import java.lang.reflect.Method;
import java.util.ArrayList;
import java.util.Collection;
import java.util.Comparator;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Locale;
import java.util.Set;
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
    private static final String VIEW_COMPACT = "compact";
    private static final String VIEW_FULL = "full";
    private static final Comparator<Element> ELEMENT_ORDER = Comparator
            .comparing(ElementQueryHandler::safeType, String.CASE_INSENSITIVE_ORDER)
            .thenComparing(ElementQueryHandler::safeName, String.CASE_INSENSITIVE_ORDER)
            .thenComparing(Element::getID, String.CASE_INSENSITIVE_ORDER);

    @Override
    public void handle(HttpExchange exchange) throws IOException {
        try {
            String method = exchange.getRequestMethod();
            String path = exchange.getRequestURI().getPath();

            if (path.equals("/api/v1/elements/interface-flow-properties")) {
                if ("OPTIONS".equals(method)) {
                    exchange.getResponseHeaders().set("Access-Control-Allow-Methods", "POST, OPTIONS");
                    exchange.getResponseHeaders().set("Access-Control-Allow-Headers", "Content-Type");
                    exchange.sendResponseHeaders(204, -1);
                    return;
                }
                if (!"POST".equals(method)) {
                    HttpBridgeServer.sendError(exchange, 405, "METHOD_NOT_ALLOWED",
                            "Only POST is supported");
                    return;
                }
                handleInterfaceFlowProperties(exchange);
                return;
            }

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

        } catch (ValidationException e) {
            HttpBridgeServer.sendError(exchange, 400, "INVALID_PARAM", e.getMessage());
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
        String typeFilter = normalizeOptional(params.get("type"));
        String nameFilter = normalizeOptional(params.get("name"));
        String packageId = normalizeOptional(params.get("package"));
        String stereotypeFilter = normalizeOptional(params.get("stereotype"));
        boolean recursive = parseBoolean(params.get("recursive"), true, "recursive");
        String view = normalizeView(params.get("view"));
        int limit = parseLimit(params.get("limit"));
        int offset = parseOffset(params.get("offset"));

        JsonObject result = EdtDispatcher.read(project -> {
            Element scope;
            if (packageId != null) {
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
            if (typeFilter != null) {
                metaclass = resolveMetaclass(typeFilter);
                if (metaclass == null) {
                    throw new ValidationException("Unknown type filter: " + typeFilter);
                }
            }

            Collection<? extends Element> candidates;
            if (metaclass != null && nameFilter != null) {
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
            } else if (nameFilter != null) {
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
            for (Element el : candidates) {
                if (stereotypeFilter != null) {
                    if (!hasMatchingStereotype(el, stereotypeFilter)) {
                        continue;
                    }
                }
                filtered.add(el);
            }

            filtered.sort(ELEMENT_ORDER);

            int totalCount = filtered.size();
            int pageOffset = Math.min(offset, totalCount);
            int pageEnd = Math.min(pageOffset + limit, totalCount);

            JsonArray elements = new JsonArray();
            for (int i = pageOffset; i < pageEnd; i++) {
                Element el = filtered.get(i);
                if (VIEW_FULL.equals(view)) {
                    elements.add(ElementSerializer.toJson(el));
                } else {
                    elements.add(ElementSerializer.toJsonCompact(el));
                }
            }

            JsonObject response = new JsonObject();
            response.addProperty("view", view);
            response.addProperty("count", elements.size());
            response.addProperty("returned", elements.size());
            response.addProperty("totalCount", totalCount);
            response.addProperty("limit", limit);
            response.addProperty("offset", pageOffset);
            response.addProperty("hasMore", pageEnd < totalCount);
            if (pageEnd < totalCount) {
                response.addProperty("nextOffset", pageEnd);
                response.addProperty("nextCursor", cursorToken(pageEnd));
            }
            if (pageOffset > 0) {
                int previousOffset = Math.max(0, pageOffset - limit);
                response.addProperty("previousOffset", previousOffset);
                response.addProperty("previousCursor", cursorToken(previousOffset));
            }
            JsonObject filters = new JsonObject();
            if (typeFilter != null) {
                filters.addProperty("type", typeFilter);
            }
            if (nameFilter != null) {
                filters.addProperty("name", nameFilter);
            }
            if (packageId != null) {
                filters.addProperty("package", packageId);
            }
            if (stereotypeFilter != null) {
                filters.addProperty("stereotype", stereotypeFilter);
            }
            filters.addProperty("recursive", recursive);
            response.add("filters", filters);
            response.add("elements", elements);
            return response;
        });

        HttpBridgeServer.sendJson(exchange, 200, result);
    }

    private void handleInterfaceFlowProperties(HttpExchange exchange) throws Exception {
        JsonObject body = JsonHelper.parseBody(exchange);
        List<String> interfaceIds = JsonHelper.optionalStringList(body, "interfaceIds");
        if (interfaceIds == null || interfaceIds.isEmpty()) {
            HttpBridgeServer.sendError(exchange, 400, "BAD_REQUEST",
                    "interfaceIds must be a non-empty array of interface block IDs");
            return;
        }

        JsonObject result = EdtDispatcher.read(project -> {
            JsonArray interfaceBlocks = new JsonArray();
            JsonArray flowProperties = new JsonArray();

            for (String interfaceId : interfaceIds) {
                Element element = (Element) project.getElementByID(interfaceId);
                if (element == null) {
                    throw new IllegalArgumentException("Interface block not found: " + interfaceId);
                }
                if (!(element instanceof com.nomagic.uml2.ext.magicdraw.classes.mdkernel.Class)) {
                    throw new IllegalArgumentException("Interface block is not a class: " + interfaceId);
                }

                com.nomagic.uml2.ext.magicdraw.classes.mdkernel.Class interfaceBlock =
                        (com.nomagic.uml2.ext.magicdraw.classes.mdkernel.Class) element;
                interfaceBlocks.add(ElementSerializer.toJsonCompact(interfaceBlock));

                Collection<Property> ownedAttributes = interfaceBlock.getOwnedAttribute();
                if (ownedAttributes == null || ownedAttributes.isEmpty()) {
                    continue;
                }

                for (Property prop : ownedAttributes) {
                    if (prop == null) {
                        continue;
                    }

                    Stereotype flowPropertyStereo = getFlowPropertyStereotype(prop);
                    if (flowPropertyStereo == null) {
                        continue;
                    }

                    JsonObject flowProperty = ElementSerializer.toJsonCompact(prop);
                    flowProperty.addProperty("ownerId", interfaceBlock.getID());
                    flowProperty.addProperty("ownerName", safeName(interfaceBlock));

                    String direction = readFlowPropertyDirection(prop, flowPropertyStereo);
                    if (direction != null) {
                        flowProperty.addProperty("direction", direction);
                    }

                    flowProperties.add(flowProperty);
                }
            }

            JsonObject response = new JsonObject();
            response.add("interfaceBlocks", interfaceBlocks);
            response.add("flowProperties", flowProperties);
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
            Set<String> directedRelationshipIds = new HashSet<>();

            try {
                Collection<DirectedRelationship> sourceRels =
                        element.get_directedRelationshipOfSource();
                if (sourceRels != null) {
                    for (DirectedRelationship rel : sourceRels) {
                        directedRelationshipIds.add(rel.getID());
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
                        directedRelationshipIds.add(rel.getID());
                        incoming.add(serializeRelationship(rel, "incoming"));
                    }
                }
            } catch (Exception e) {
                LOG.log(Level.FINE, "Error reading incoming relationships", e);
            }

            try {
                if (element instanceof ActivityNode) {
                    ActivityNode node = (ActivityNode) element;
                    Collection<ActivityEdge> outgoingEdges = node.getOutgoing();
                    if (outgoingEdges != null) {
                        for (ActivityEdge edge : outgoingEdges) {
                            if (edge != null && directedRelationshipIds.add(edge.getID())) {
                                outgoing.add(serializeActivityEdge(edge, "outgoing"));
                            }
                        }
                    }

                    Collection<ActivityEdge> incomingEdges = node.getIncoming();
                    if (incomingEdges != null) {
                        for (ActivityEdge edge : incomingEdges) {
                            if (edge != null && directedRelationshipIds.add(edge.getID())) {
                                incoming.add(serializeActivityEdge(edge, "incoming"));
                            }
                        }
                    }
                }
            } catch (Exception e) {
                LOG.log(Level.FINE, "Error reading activity edges", e);
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

            try {
                if (element instanceof ConnectableElement) {
                    Collection<Connector> connectors =
                            Connectors.collectDirectConnectors((ConnectableElement) element);
                    if (connectors != null) {
                        for (Connector connector : connectors) {
                            undirected.add(serializeConnector(connector, elementId));
                        }
                    }
                }
            } catch (Exception e) {
                LOG.log(Level.FINE, "Error reading connectors", e);
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
                    String name = st.getName();
                    if (name != null && name.equalsIgnoreCase(stereotypeName)) {
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
        json.addProperty("humanType", rel.getHumanType());
        appendRelationshipMetadata(json, rel);

        json.add("sources", serializeElementsSafe(rel.getSource(), "relationship sources"));
        json.add("targets", serializeElementsSafe(rel.getTarget(), "relationship targets"));

        if (rel instanceof InformationFlow) {
            appendInformationFlowFields(json, (InformationFlow) rel);
        }

        return json;
    }

    private JsonObject serializeActivityEdge(ActivityEdge edge, String direction) {
        JsonObject json = new JsonObject();
        json.addProperty("relationshipId", edge.getID());
        json.addProperty("direction", direction);

        try {
            String shortName = ClassTypes.getShortName(edge.getClassType());
            json.addProperty("type", shortName != null ? shortName : edge.getHumanType());
        } catch (Exception e) {
            json.addProperty("type", edge.getHumanType());
        }
        json.addProperty("humanType", edge.getHumanType());
        appendRelationshipMetadata(json, edge);

        JsonArray sources = new JsonArray();
        if (edge.getSource() != null) {
            sources.add(ElementSerializer.toJsonCompact(edge.getSource()));
        }
        json.add("sources", sources);

        JsonArray targets = new JsonArray();
        if (edge.getTarget() != null) {
            targets.add(ElementSerializer.toJsonCompact(edge.getTarget()));
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

    private void appendRelationshipMetadata(JsonObject json, Element relationship) {
        if (relationship instanceof NamedElement) {
            String name = ((NamedElement) relationship).getName();
            if (name != null && !name.isEmpty()) {
                json.addProperty("name", name);
            }
        }
        Element owner = relationship.getOwner();
        if (owner != null) {
            json.addProperty("ownerId", owner.getID());
        }
        try {
            List<Stereotype> stereotypes = StereotypesHelper.getStereotypes(relationship);
            if (stereotypes != null && !stereotypes.isEmpty()) {
                JsonArray stereotypeNames = new JsonArray();
                for (Stereotype stereotype : stereotypes) {
                    stereotypeNames.add(stereotype.getName());
                }
                json.add("stereotypes", stereotypeNames);
            }
        } catch (Exception e) {
            LOG.log(Level.FINE, "Error reading relationship stereotypes", e);
        }
    }

    private void appendInformationFlowFields(JsonObject json, InformationFlow informationFlow) {
        json.add(
                "conveyed",
                serializeElementsSafe(informationFlow.getConveyed(), "information flow conveyed"));
        json.add(
                "realizingConnectors",
                serializeElementsSafe(
                        informationFlow.getRealizingConnector(),
                        "information flow realizing connectors"));
        try {
            Stereotype itemFlow = StereotypesHelper.getAppliedStereotypeByString(
                    informationFlow,
                    "ItemFlow");
            if (itemFlow != null) {
                Object itemProperty = StereotypesHelper.getStereotypePropertyFirst(
                        informationFlow,
                        itemFlow,
                        "itemProperty");
                if (itemProperty instanceof Element) {
                    json.add("itemProperty", ElementSerializer.toJsonCompact((Element) itemProperty));
                }
            }
        } catch (Exception e) {
            LOG.log(Level.FINE, "Error reading information flow itemProperty", e);
        }
    }

    private JsonArray serializeElementsSafe(
            Collection<? extends Element> elements,
            String label) {
        JsonArray serialized = new JsonArray();
        try {
            if (elements == null) {
                return serialized;
            }
            for (Element element : elements) {
                if (element != null) {
                    serialized.add(ElementSerializer.toJsonCompact(element));
                }
            }
        } catch (Exception e) {
            LOG.log(Level.FINE, "Error reading " + label, e);
        }
        return serialized;
    }

    private JsonObject serializeConnector(Connector connector, String selfId) {
        JsonObject json = new JsonObject();
        json.addProperty("relationshipId", connector.getID());
        json.addProperty("direction", "undirected");
        json.addProperty("type", "Connector");

        if (connector instanceof NamedElement) {
            String name = ((NamedElement) connector).getName();
            if (name != null && !name.isEmpty()) {
                json.addProperty("name", name);
            }
        }

        JsonArray relatedElements = new JsonArray();
        try {
            Collection<ConnectorEnd> ends = connector.getEnd();
            if (ends != null) {
                for (ConnectorEnd end : ends) {
                    ConnectableElement role = end.getRole();
                    if (role == null || selfId.equals(role.getID())) {
                        continue;
                    }
                    JsonObject relJson = new JsonObject();
                    relJson.addProperty("id", role.getID());
                    if (role instanceof NamedElement) {
                        relJson.addProperty("name", ((NamedElement) role).getName());
                    }
                    relatedElements.add(relJson);
                }
            }
        } catch (Exception e) {
            LOG.log(Level.FINE, "Error reading connector ends", e);
        }
        json.add("relatedElements", relatedElements);
        return json;
    }

    private Stereotype getFlowPropertyStereotype(Property property) {
        try {
            Stereotype flowPropertyStereo = StereotypesHelper.getAppliedStereotypeByString(
                    property,
                    "FlowProperty");
            if (flowPropertyStereo == null) {
                flowPropertyStereo = StereotypesHelper.getAppliedStereotypeByString(
                        property,
                        "flowProperty");
            }
            return flowPropertyStereo;
        } catch (Exception e) {
            LOG.log(Level.FINE, "Error reading flow property stereotype", e);
            return null;
        }
    }

    private String readFlowPropertyDirection(Property property, Stereotype flowPropertyStereo) {
        try {
            Object direction = StereotypesHelper.getStereotypePropertyFirst(
                    property,
                    flowPropertyStereo,
                    "direction");
            if (direction == null) {
                return null;
            }
            if (direction instanceof Enum<?>) {
                return ((Enum<?>) direction).name();
            }
            try {
                Method getName = direction.getClass().getMethod("getName");
                Object name = getName.invoke(direction);
                if (name != null) {
                    String text = String.valueOf(name).trim();
                    if (!text.isEmpty()) {
                        return text;
                    }
                }
            } catch (Exception ignored) {
                // Fall back to String.valueOf below.
            }
            return String.valueOf(direction);
        } catch (Exception e) {
            LOG.log(Level.FINE, "Error reading flow property direction", e);
            return null;
        }
    }

    private static String normalizeOptional(String value) {
        if (value == null) {
            return null;
        }
        String trimmed = value.trim();
        return trimmed.isEmpty() ? null : trimmed;
    }

    private static boolean parseBoolean(String rawValue, boolean defaultValue, String name) {
        String value = normalizeOptional(rawValue);
        if (value == null) {
            return defaultValue;
        }
        if ("true".equalsIgnoreCase(value)) {
            return true;
        }
        if ("false".equalsIgnoreCase(value)) {
            return false;
        }
        throw new ValidationException(name + " must be 'true' or 'false'");
    }

    private static String normalizeView(String rawValue) {
        String value = normalizeOptional(rawValue);
        if (value == null) {
            return VIEW_COMPACT;
        }
        String normalized = value.toLowerCase(Locale.ROOT);
        if (VIEW_COMPACT.equals(normalized) || VIEW_FULL.equals(normalized)) {
            return normalized;
        }
        throw new ValidationException("view must be either 'compact' or 'full'");
    }

    private static int parseLimit(String rawValue) {
        String value = normalizeOptional(rawValue);
        if (value == null) {
            return DEFAULT_LIMIT;
        }
        try {
            int parsed = Integer.parseInt(value);
            if (parsed < 1) {
                throw new ValidationException("limit must be greater than zero");
            }
            return Math.min(parsed, MAX_LIMIT);
        } catch (NumberFormatException e) {
            throw new ValidationException("limit must be an integer");
        }
    }

    private static int parseOffset(String rawValue) {
        String value = normalizeOptional(rawValue);
        if (value == null) {
            return 0;
        }
        try {
            int parsed = Integer.parseInt(value);
            if (parsed < 0) {
                throw new ValidationException("offset must be zero or greater");
            }
            return parsed;
        } catch (NumberFormatException e) {
            throw new ValidationException("offset must be an integer");
        }
    }

    private static String cursorToken(int offset) {
        return "offset:" + offset;
    }

    private static String safeType(Element element) {
        try {
            String shortName = ClassTypes.getShortName(element.getClassType());
            if (shortName != null && !shortName.isEmpty()) {
                return shortName;
            }
        } catch (Exception e) {
            // Fall through to human type.
        }
        String humanType = element.getHumanType();
        return humanType != null ? humanType : "";
    }

    private static String safeName(Element element) {
        if (element instanceof NamedElement) {
            String name = ((NamedElement) element).getName();
            if (name != null) {
                return name;
            }
        }
        return "";
    }

    private static final class ValidationException extends RuntimeException {
        private ValidationException(String message) {
            super(message);
        }
    }
}
