package com.claude.cameo.bridge.util;

import com.google.gson.JsonArray;
import com.google.gson.JsonObject;

import java.util.List;

/**
 * Stable plugin metadata and machine-readable capability manifest.
 *
 * The Python MCP layer can read this payload to reject version skew before
 * attempting to call into the bridge.
 */
public final class BridgeCapabilities {

    public static final String PLUGIN_ID = "com.claude.cameo.bridge";
    public static final String PLUGIN_NAME = "Cameo MCP Bridge";
    public static final String PLUGIN_VERSION = "2.0.0";
    public static final String API_VERSION = "v1";
    public static final String HANDSHAKE_VERSION = "1";
    public static final String STATUS_PATH = "/api/v1/status";
    public static final String CAPABILITIES_PATH = "/api/v1/capabilities";

    private static final List<Capability> CAPABILITIES = List.of(
            new Capability("health", "cameo_status", "GET", STATUS_PATH, "read"),
            new Capability("health", "cameo_capabilities", "GET", CAPABILITIES_PATH, "read"),
            new Capability("project", "cameo_get_project", "GET", "/api/v1/project", "read"),
            new Capability("project", "cameo_save_project", "POST", "/api/v1/project/save", "write"),
            new Capability("session", "cameo_reset_session", "POST", "/api/v1/session/reset", "write"),
            new Capability("elements", "cameo_query_elements", "GET", "/api/v1/elements", "read"),
            new Capability("elements", "cameo_get_element", "GET", "/api/v1/elements/{elementId}", "read"),
            new Capability("elements", "cameo_create_element", "POST", "/api/v1/elements", "write"),
            new Capability("elements", "cameo_modify_element", "PUT", "/api/v1/elements/{elementId}", "write"),
            new Capability("elements", "cameo_delete_element", "DELETE", "/api/v1/elements/{elementId}", "write"),
            new Capability("elements", "cameo_get_containment_tree", "GET", "/api/v1/containment-tree", "read"),
            new Capability("elements", "cameo_list_containment_children", "GET", "/api/v1/containment-tree/children", "read"),
            new Capability("elements", "cameo_set_usecase_subject", "PUT", "/api/v1/elements/{elementId}/usecase-subject", "write"),
            new Capability("stereotypes", "cameo_apply_profile", "POST", "/api/v1/elements/{elementId}/apply-profile", "write"),
            new Capability("stereotypes", "cameo_apply_stereotype", "POST", "/api/v1/elements/{elementId}/stereotypes", "write"),
            new Capability("stereotypes", "cameo_set_tagged_values", "PUT", "/api/v1/elements/{elementId}/tagged-values", "write"),
            new Capability("stereotypes", "cameo_set_stereotype_metaclasses", "PUT", "/api/v1/elements/{elementId}/metaclasses", "write"),
            new Capability("relationships", "cameo_create_relationship", "POST", "/api/v1/relationships", "write"),
            new Capability("relationships", "cameo_get_relationships", "GET", "/api/v1/elements/{elementId}/relationships", "read"),
            new Capability("matrices", "cameo_list_matrices", "GET", "/api/v1/matrices", "read"),
            new Capability("matrices", "cameo_get_matrix", "GET", "/api/v1/matrices/{matrixId}", "read"),
            new Capability("matrices", "cameo_create_matrix", "POST", "/api/v1/matrices", "write"),
            new Capability("diagrams", "cameo_list_diagrams", "GET", "/api/v1/diagrams", "read"),
            new Capability("diagrams", "cameo_create_diagram", "POST", "/api/v1/diagrams", "write"),
            new Capability("diagrams", "cameo_add_to_diagram", "POST", "/api/v1/diagrams/{diagramId}/elements", "write"),
            new Capability("diagrams", "cameo_get_diagram_image", "GET", "/api/v1/diagrams/{diagramId}/image", "read"),
            new Capability("diagrams", "cameo_auto_layout", "POST", "/api/v1/diagrams/{diagramId}/layout", "write"),
            new Capability("diagrams", "cameo_list_diagram_shapes", "GET", "/api/v1/diagrams/{diagramId}/shapes", "read"),
            new Capability("diagrams", "cameo_get_shape_properties", "GET", "/api/v1/diagrams/{diagramId}/shapes/{presentationId}/properties", "read"),
            new Capability("diagrams", "cameo_move_shapes", "PUT", "/api/v1/diagrams/{diagramId}/shapes", "write"),
            new Capability("diagrams", "cameo_delete_shapes", "DELETE", "/api/v1/diagrams/{diagramId}/shapes", "write"),
            new Capability("diagrams", "cameo_add_diagram_paths", "POST", "/api/v1/diagrams/{diagramId}/paths", "write"),
            new Capability("diagrams", "cameo_set_shape_properties", "PUT", "/api/v1/diagrams/{diagramId}/shapes/{presentationId}/properties", "write"),
            new Capability("diagrams", "cameo_set_shape_compartments", "PUT", "/api/v1/diagrams/{diagramId}/shapes/{presentationId}/compartments", "write"),
            new Capability("diagrams", "cameo_reparent_shapes", "PUT", "/api/v1/diagrams/{diagramId}/shapes/reparent", "write"),
            new Capability("diagrams", "cameo_route_paths", "PUT", "/api/v1/diagrams/{diagramId}/paths/route", "write"),
            new Capability("specification", "cameo_get_specification", "GET", "/api/v1/elements/{elementId}/specification", "read"),
            new Capability("specification", "cameo_set_specification", "PUT", "/api/v1/elements/{elementId}/specification", "write"),
            new Capability("macros", "cameo_execute_macro", "POST", "/api/v1/macros/execute", "write")
    );

    private BridgeCapabilities() {
    }

    public static JsonObject buildStatus(int port) {
        JsonObject json = buildMetadata(port);
        json.addProperty("status", "ok");
        json.addProperty("healthy", true);
        return json;
    }

    public static JsonObject buildCapabilities(int port) {
        return buildMetadata(port);
    }

    public static JsonArray supportedPluginVersions() {
        JsonArray versions = new JsonArray();
        versions.add(PLUGIN_VERSION);
        return versions;
    }

    private static JsonObject buildMetadata(int port) {
        JsonObject json = new JsonObject();
        json.addProperty("pluginId", PLUGIN_ID);
        json.addProperty("plugin", "CameoMCPBridge");
        json.addProperty("pluginName", PLUGIN_NAME);
        json.addProperty("version", PLUGIN_VERSION);
        json.addProperty("pluginVersion", PLUGIN_VERSION);
        json.addProperty("apiVersion", API_VERSION);
        json.addProperty("handshakeVersion", HANDSHAKE_VERSION);
        json.addProperty("port", port);
        json.addProperty("statusEndpoint", STATUS_PATH);
        json.addProperty("capabilitiesEndpoint", CAPABILITIES_PATH);
        json.add("compatibility", buildCompatibility());
        json.add("capabilities", buildCapabilityManifest());
        return json;
    }

    private static JsonObject buildCompatibility() {
        JsonObject compatibility = new JsonObject();
        compatibility.addProperty("requiresExactPluginVersionMatch", true);
        compatibility.addProperty("expectedPluginVersion", PLUGIN_VERSION);
        compatibility.addProperty("supportedHandshakeVersion", HANDSHAKE_VERSION);
        compatibility.add("supportedPluginVersions", supportedPluginVersions());
        return compatibility;
    }

    private static JsonObject buildCapabilityManifest() {
        JsonObject manifest = new JsonObject();
        JsonObject groups = new JsonObject();
        JsonArray endpoints = new JsonArray();

        for (Capability capability : CAPABILITIES) {
            JsonArray group = groups.has(capability.group)
                    ? groups.getAsJsonArray(capability.group)
                    : new JsonArray();
            group.add(capability.name);
            groups.add(capability.group, group);
            endpoints.add(capability.toJson());
        }

        manifest.addProperty("count", endpoints.size());
        manifest.add("groups", groups);
        manifest.add("endpoints", endpoints);
        return manifest;
    }

    private static final class Capability {
        private final String group;
        private final String name;
        private final String method;
        private final String path;
        private final String mode;

        private Capability(String group, String name, String method, String path, String mode) {
            this.group = group;
            this.name = name;
            this.method = method;
            this.path = path;
            this.mode = mode;
        }

        private JsonObject toJson() {
            JsonObject json = new JsonObject();
            json.addProperty("group", group);
            json.addProperty("name", name);
            json.addProperty("method", method);
            json.addProperty("path", path);
            json.addProperty("mode", mode);
            return json;
        }
    }
}
