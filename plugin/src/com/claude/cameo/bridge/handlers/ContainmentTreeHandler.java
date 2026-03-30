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
        String rootId = params.get("rootId");
        int depth = DEFAULT_DEPTH;

        String depthStr = params.get("depth");
        if (depthStr != null) {
            try {
                depth = Math.min(Math.max(Integer.parseInt(depthStr), 1), MAX_DEPTH);
            } catch (NumberFormatException e) {
                HttpBridgeServer.sendError(exchange, 400, "INVALID_PARAM",
                        "depth must be an integer (1-" + MAX_DEPTH + ")");
                return;
            }
        }

        final int maxDepth = depth;
        final String finalRootId = rootId;

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

            JsonObject tree = buildTreeNode(root, maxDepth, 0);

            JsonObject response = new JsonObject();
            response.addProperty("rootId", root.getID());
            response.addProperty("depth", maxDepth);
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
        String rootId = params.get("rootId");
        int limit;
        int offset;
        try {
            limit = parseBoundedInt(params.get("limit"), DEFAULT_CHILD_LIMIT, 1, MAX_CHILD_LIMIT, "limit");
            offset = parseBoundedInt(params.get("offset"), 0, 0, Integer.MAX_VALUE, "offset");
        } catch (IllegalArgumentException e) {
            HttpBridgeServer.sendError(exchange, 400, "INVALID_PARAM", e.getMessage());
            return;
        }

        final String finalRootId = rootId;
        final int finalLimit = limit;
        final int finalOffset = offset;

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
            JsonArray children = new JsonArray();
            int totalChildren = ownedElements != null ? ownedElements.size() : 0;
            int start = Math.min(finalOffset, totalChildren);
            int end = Math.min(start + finalLimit, totalChildren);
            int index = 0;

            if (ownedElements != null) {
                for (Element child : ownedElements) {
                    if (index >= start && index < end) {
                        JsonObject childJson = ElementSerializer.toJsonCompact(child);
                        try {
                            Collection<Element> grandchildren = child.getOwnedElement();
                            childJson.addProperty("childCount",
                                    grandchildren != null ? grandchildren.size() : 0);
                        } catch (Exception e) {
                            childJson.addProperty("childCount", 0);
                        }
                        children.add(childJson);
                    }
                    index++;
                    if (index >= end) {
                        break;
                    }
                }
            }

            JsonObject response = new JsonObject();
            response.add("root", ElementSerializer.toJsonCompact(root));
            response.addProperty("rootId", root.getID());
            response.addProperty("limit", finalLimit);
            response.addProperty("offset", finalOffset);
            response.addProperty("totalChildren", totalChildren);
            response.addProperty("returned", children.size());
            response.addProperty("hasMore", end < totalChildren);
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
    private JsonObject buildTreeNode(Element element, int maxDepth, int currentDepth) {
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

        // Children (recurse if within depth limit)
        JsonArray childrenArray = new JsonArray();
        if (currentDepth < maxDepth) {
            try {
                List<Element> ownedElements = sortOwnedElements(element.getOwnedElement());
                if (ownedElements != null) {
                    for (Element child : ownedElements) {
                        childrenArray.add(buildTreeNode(child, maxDepth, currentDepth + 1));
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
        if (rawValue == null || rawValue.isEmpty()) {
            return defaultValue;
        }
        try {
            int parsed = Integer.parseInt(rawValue);
            if (parsed < minValue || parsed > maxValue) {
                throw new IllegalArgumentException(
                        name + " must be between " + minValue + " and " + maxValue);
            }
            return parsed;
        } catch (NumberFormatException e) {
            throw new IllegalArgumentException(name + " must be an integer");
        }
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
}
