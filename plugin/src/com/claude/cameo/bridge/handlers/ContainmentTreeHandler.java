package com.claude.cameo.bridge.handlers;

import com.claude.cameo.bridge.HttpBridgeServer;
import com.claude.cameo.bridge.util.EdtDispatcher;
import com.claude.cameo.bridge.util.ElementSerializer;
import com.claude.cameo.bridge.util.JsonHelper;
import com.nomagic.magicdraw.uml.ClassTypes;
import com.nomagic.uml2.ext.magicdraw.classes.mdkernel.Element;
import com.nomagic.uml2.ext.magicdraw.classes.mdkernel.NamedElement;
import com.nomagic.uml2.ext.magicdraw.classes.mdkernel.Package;
import com.nomagic.uml2.ext.magicdraw.mdprofiles.Stereotype;
import com.nomagic.uml2.ext.jmi.helpers.StereotypesHelper;
import com.sun.net.httpserver.HttpExchange;
import com.sun.net.httpserver.HttpHandler;
import com.google.gson.JsonArray;
import com.google.gson.JsonObject;

import java.io.IOException;
import java.util.ArrayList;
import java.util.Collection;
import java.util.Comparator;
import java.util.List;
import java.util.Map;
import java.util.logging.Level;
import java.util.logging.Logger;

/**
 * Handles the containment tree REST endpoint:
 * <ul>
 *   <li>{@code GET /api/v1/containment-tree?rootId=&depth=3} - nested containment tree</li>
 * </ul>
 *
 * Returns a nested JSON tree where each node has: id, name, type, stereotypes[], children[].
 * Depth is limited to prevent performance issues on large models.
 */
public class ContainmentTreeHandler implements HttpHandler {

    private static final Logger LOG = Logger.getLogger(ContainmentTreeHandler.class.getName());
    private static final int DEFAULT_DEPTH = 3;
    private static final int MAX_DEPTH = 10;
    private static final int DEFAULT_CHILD_LIMIT = 50;
    private static final int MAX_CHILD_LIMIT = 500;
    private static final String VIEW_COMPACT = "compact";
    private static final String VIEW_FULL = "full";

    @Override
    public void handle(HttpExchange exchange) throws IOException {
        try {
            String method = exchange.getRequestMethod();
            String path = exchange.getRequestURI().getPath();

            if ("GET".equals(method)) {
                if (path.endsWith("/children")) {
                    handleListChildren(exchange);
                } else {
                    handleGetTree(exchange);
                }
            } else if ("OPTIONS".equals(method)) {
                exchange.getResponseHeaders().set("Access-Control-Allow-Methods", "GET, OPTIONS");
                exchange.getResponseHeaders().set("Access-Control-Allow-Headers", "Content-Type");
                exchange.sendResponseHeaders(204, -1);
            } else {
                HttpBridgeServer.sendError(exchange, 405, "METHOD_NOT_ALLOWED",
                        "Only GET is supported");
            }
        } catch (ValidationException e) {
            HttpBridgeServer.sendError(exchange, 400, "INVALID_PARAM", e.getMessage());
        } catch (IllegalArgumentException e) {
            HttpBridgeServer.sendError(exchange, 404, "NOT_FOUND", e.getMessage());
        } catch (Exception e) {
            LOG.log(Level.SEVERE, "Error in ContainmentTreeHandler", e);
            HttpBridgeServer.sendError(exchange, 500, "INTERNAL_ERROR", e.getMessage());
        }
    }

    /**
     * GET /api/v1/containment-tree?rootId=&depth=3
     * If rootId is omitted, uses the project's primary model as root.
     */
    private void handleGetTree(HttpExchange exchange) throws Exception {
        Map<String, String> params = JsonHelper.parseQuery(exchange);
        String rootId = normalizeOptional(params.get("rootId"));
        int depth = DEFAULT_DEPTH;
        String view = normalizeView(params.get("view"));

        String depthStr = params.get("depth");
        if (depthStr != null) {
            try {
                depth = Math.min(Math.max(Integer.parseInt(depthStr.trim()), 1), MAX_DEPTH);
            } catch (NumberFormatException e) {
                throw new ValidationException(
                        "depth must be an integer (1-" + MAX_DEPTH + ")");
            }
        }

        final int maxDepth = depth;
        final String finalRootId = rootId;
        final boolean includeFullView = VIEW_FULL.equals(view);

        JsonObject result = EdtDispatcher.read(project -> {
            Element root;

            if (finalRootId != null && !finalRootId.isEmpty()) {
                root = (Element) project.getElementByID(finalRootId);
                if (root == null) {
                    throw new IllegalArgumentException("Element not found: " + finalRootId);
                }
            } else {
                Package primaryModel = project.getPrimaryModel();
                if (primaryModel == null) {
                    throw new IllegalStateException("No primary model found in project");
                }
                root = primaryModel;
            }

            JsonObject tree = buildTreeNode(root, maxDepth, 0, includeFullView);

            JsonObject response = new JsonObject();
            response.addProperty("rootId", root.getID());
            response.addProperty("depth", maxDepth);
            response.addProperty("view", view);
            response.add("tree", tree);
            return response;
        });

        HttpBridgeServer.sendJson(exchange, 200, result);
    }

    /**
     * GET /api/v1/containment-tree/children?rootId=&limit=50&offset=0
     *
     * Returns only the immediate children of the selected root, paginated and compact.
     * This is the browsing path for large models.
     */
    private void handleListChildren(HttpExchange exchange) throws Exception {
        Map<String, String> params = JsonHelper.parseQuery(exchange);
        String rootId = normalizeOptional(params.get("rootId"));
        String typeFilter = normalizeOptional(params.get("type"));
        String nameFilter = normalizeOptional(params.get("name"));
        String stereotypeFilter = normalizeOptional(params.get("stereotype"));
        int limit = parseBoundedInt(params.get("limit"), DEFAULT_CHILD_LIMIT, 1, MAX_CHILD_LIMIT, "limit");
        int offset = parseBoundedInt(params.get("offset"), 0, 0, Integer.MAX_VALUE, "offset");
        String view = normalizeView(params.get("view"));

        final String finalRootId = rootId;
        final int finalLimit = limit;
        final int finalOffset = offset;
        final boolean includeFullView = VIEW_FULL.equals(view);
        final String finalTypeFilter = typeFilter;
        final String finalNameFilter = nameFilter;
        final String finalStereotypeFilter = stereotypeFilter;

        JsonObject result = EdtDispatcher.read(project -> {
            Element root;

            if (finalRootId != null && !finalRootId.isEmpty()) {
                root = (Element) project.getElementByID(finalRootId);
                if (root == null) {
                    throw new IllegalArgumentException("Element not found: " + finalRootId);
                }
            } else {
                Package primaryModel = project.getPrimaryModel();
                if (primaryModel == null) {
                    throw new IllegalStateException("No primary model found in project");
                }
                root = primaryModel;
            }

            List<Element> ownedElements = sortOwnedElements(root.getOwnedElement());
            List<Element> filteredElements = new ArrayList<>();
            if (ownedElements != null) {
                for (Element child : ownedElements) {
                    if (!matchesFilters(child, finalTypeFilter, finalNameFilter, finalStereotypeFilter)) {
                        continue;
                    }
                    filteredElements.add(child);
                }
            }

            JsonArray children = new JsonArray();
            int totalChildren = ownedElements != null ? ownedElements.size() : 0;
            int matchedChildren = filteredElements.size();
            int start = Math.min(finalOffset, matchedChildren);
            int end = Math.min(start + finalLimit, matchedChildren);

            for (int i = start; i < end; i++) {
                Element child = filteredElements.get(i);
                if (includeFullView) {
                    children.add(ElementSerializer.toJson(child));
                } else {
                    children.add(ElementSerializer.toJsonCompact(child));
                }
            }

            JsonObject response = new JsonObject();
            response.add("root", includeFullView ? ElementSerializer.toJson(root) : ElementSerializer.toJsonCompact(root));
            response.addProperty("rootId", root.getID());
            response.addProperty("view", view);
            response.addProperty("limit", finalLimit);
            response.addProperty("offset", start);
            response.addProperty("totalChildren", totalChildren);
            response.addProperty("matchedChildren", matchedChildren);
            response.addProperty("returned", children.size());
            response.addProperty("count", children.size());
            response.addProperty("hasMore", end < matchedChildren);
            if (end < matchedChildren) {
                response.addProperty("nextOffset", end);
                response.addProperty("nextCursor", cursorToken(end));
            }
            if (start > 0) {
                int previousOffset = Math.max(0, start - finalLimit);
                response.addProperty("previousOffset", previousOffset);
                response.addProperty("previousCursor", cursorToken(previousOffset));
            }
            JsonObject filters = new JsonObject();
            if (finalTypeFilter != null) {
                filters.addProperty("type", finalTypeFilter);
            }
            if (finalNameFilter != null) {
                filters.addProperty("name", finalNameFilter);
            }
            if (finalStereotypeFilter != null) {
                filters.addProperty("stereotype", finalStereotypeFilter);
            }
            response.add("filters", filters);
            response.add("children", children);
            return response;
        });

        HttpBridgeServer.sendJson(exchange, 200, result);
    }

    /**
     * Recursively builds a tree node for the given element.
     *
     * @param element      the current element
     * @param maxDepth     the maximum depth to recurse
     * @param currentDepth the current recursion depth
     * @return a JsonObject representing this node and its children
     */
    private JsonObject buildTreeNode(Element element, int maxDepth, int currentDepth,
            boolean includeFullView) {
        JsonObject node = new JsonObject();

        node.addProperty("id", element.getID());

        // Type
        try {
            String shortName = ClassTypes.getShortName(element.getClassType());
            node.addProperty("type", shortName != null ? shortName : element.getHumanType());
        } catch (Exception e) {
            node.addProperty("type", element.getHumanType());
        }

        // Name
        if (element instanceof NamedElement) {
            String name = ((NamedElement) element).getName();
            node.addProperty("name", name != null ? name : "");
        } else {
            node.addProperty("name", "");
        }

        // Stereotypes
        JsonArray stereotypesArray = new JsonArray();
        try {
            List<Stereotype> stereotypes = StereotypesHelper.getStereotypes(element);
            if (stereotypes != null) {
                for (Stereotype st : stereotypes) {
                    stereotypesArray.add(st.getName());
                }
            }
        } catch (Exception e) {
            LOG.log(Level.FINE, "Could not read stereotypes for " + element.getID(), e);
        }
        node.add("stereotypes", stereotypesArray);

        if (includeFullView) {
            node.add("element", ElementSerializer.toJson(element));
        }

        // Children (recurse if within depth limit)
        JsonArray childrenArray = new JsonArray();
        if (currentDepth < maxDepth) {
            try {
                List<Element> ownedElements = sortOwnedElements(element.getOwnedElement());
                if (ownedElements != null) {
                    for (Element child : ownedElements) {
                        childrenArray.add(buildTreeNode(child, maxDepth, currentDepth + 1,
                                includeFullView));
                    }
                }
            } catch (Exception e) {
                LOG.log(Level.FINE, "Could not read children for " + element.getID(), e);
            }
        } else {
            // At max depth, just report the child count so the caller knows there's more
            try {
                List<Element> ownedElements = sortOwnedElements(element.getOwnedElement());
                if (ownedElements != null && !ownedElements.isEmpty()) {
                    node.addProperty("childCount", ownedElements.size());
                }
            } catch (Exception e) {
                // ignore
            }
        }
        node.add("children", childrenArray);

        return node;
    }

    private int parseBoundedInt(String rawValue, int defaultValue, int minValue, int maxValue, String name) {
        String value = normalizeOptional(rawValue);
        if (value == null) {
            return defaultValue;
        }
        try {
            int parsed = Integer.parseInt(value);
            if (parsed < minValue || parsed > maxValue) {
                throw new ValidationException(
                        name + " must be between " + minValue + " and " + maxValue);
            }
            return parsed;
        } catch (NumberFormatException e) {
            throw new ValidationException(name + " must be an integer");
        }
    }

    private String normalizeView(String rawValue) {
        String value = normalizeOptional(rawValue);
        if (value == null) {
            return VIEW_COMPACT;
        }
        String normalized = value.toLowerCase(java.util.Locale.ROOT);
        if (VIEW_COMPACT.equals(normalized) || VIEW_FULL.equals(normalized)) {
            return normalized;
        }
        throw new ValidationException("view must be either 'compact' or 'full'");
    }

    private String normalizeOptional(String rawValue) {
        if (rawValue == null) {
            return null;
        }
        String trimmed = rawValue.trim();
        return trimmed.isEmpty() ? null : trimmed;
    }

    private boolean matchesFilters(Element element, String typeFilter, String nameFilter,
            String stereotypeFilter) {
        if (typeFilter != null && !matchesTypeFilter(element, typeFilter)) {
            return false;
        }
        if (nameFilter != null && !matchesNameFilter(element, nameFilter)) {
            return false;
        }
        if (stereotypeFilter != null && !hasMatchingStereotype(element, stereotypeFilter)) {
            return false;
        }
        return true;
    }

    private boolean matchesTypeFilter(Element element, String typeFilter) {
        String normalizedFilter = normalizeTypeName(typeFilter);
        String shortName = safeType(element);
        if (normalizedFilter.equalsIgnoreCase(normalizeTypeName(shortName))) {
            return true;
        }
        if (element.getClassType() != null) {
            String className = element.getClassType().getSimpleName();
            if (normalizedFilter.equalsIgnoreCase(normalizeTypeName(className))) {
                return true;
            }
        }
        String humanType = element.getHumanType();
        return humanType != null
                && normalizedFilter.equalsIgnoreCase(normalizeTypeName(humanType));
    }

    private boolean matchesNameFilter(Element element, String nameFilter) {
        String elementName = safeName(element);
        return elementName.toLowerCase(java.util.Locale.ROOT)
                .contains(nameFilter.toLowerCase(java.util.Locale.ROOT));
    }

    private boolean hasMatchingStereotype(Element element, String stereotypeName) {
        try {
            List<Stereotype> stereotypes = StereotypesHelper.getStereotypes(element);
            if (stereotypes != null) {
                for (Stereotype st : stereotypes) {
                    if (st.getName() != null && st.getName().equalsIgnoreCase(stereotypeName)) {
                        return true;
                    }
                }
            }
        } catch (Exception e) {
            LOG.log(Level.FINE, "Error checking stereotypes for " + element.getID(), e);
        }
        return false;
    }

    private String normalizeTypeName(String input) {
        if (input == null || input.isEmpty()) {
            return "";
        }
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

    private String safeType(Element element) {
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

    private String safeName(Element element) {
        if (element instanceof NamedElement) {
            String name = ((NamedElement) element).getName();
            if (name != null) {
                return name;
            }
        }
        return "";
    }

    private String cursorToken(int offset) {
        return "offset:" + offset;
    }

    private List<Element> sortOwnedElements(Collection<Element> elements) {
        if (elements == null) {
            return null;
        }
        List<Element> ordered = new ArrayList<>(elements);
        ordered.sort(Comparator
                .comparing(this::sortName, String.CASE_INSENSITIVE_ORDER)
                .thenComparing(Element::getID));
        return ordered;
    }

    private String sortName(Element element) {
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
