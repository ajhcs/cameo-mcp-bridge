package com.claude.cameo.bridge.handlers;

import com.claude.cameo.bridge.HttpBridgeServer;
import com.claude.cameo.bridge.util.EdtDispatcher;
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
import java.util.Collection;
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

    @Override
    public void handle(HttpExchange exchange) throws IOException {
        try {
            String method = exchange.getRequestMethod();

            if ("GET".equals(method)) {
                handleGetTree(exchange);
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
                Collection<Element> ownedElements = element.getOwnedElement();
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
                Collection<Element> ownedElements = element.getOwnedElement();
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
}
