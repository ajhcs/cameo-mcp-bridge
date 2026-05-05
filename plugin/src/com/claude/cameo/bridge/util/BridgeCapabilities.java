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
    public static final String PLUGIN_VERSION = "2.3.5";
    public static final String API_VERSION = "v1";
    public static final String HANDSHAKE_VERSION = "1";
    public static final String LEGACY_STATUS_PATH = "/status";
    public static final String LEGACY_CAPABILITIES_PATH = "/capabilities";
    public static final String STATUS_PATH = "/api/v1/status";
    public static final String CAPABILITIES_PATH = "/api/v1/capabilities";

    private static final List<Capability> CAPABILITIES = List.of(
            new Capability("health", "cameo_status", "GET", STATUS_PATH, "read"),
            new Capability("health", "cameo_capabilities", "GET", CAPABILITIES_PATH, "read"),
            new Capability("project", "cameo_get_project", "GET", "/api/v1/project", "read"),
            new Capability("project", "cameo_save_project", "POST", "/api/v1/project/save", "write"),
            new Capability("ui", "cameo_get_ui_state", "GET", "/api/v1/ui/state", "read"),
            new Capability("ui", "cameo_get_active_diagram", "GET", "/api/v1/ui/active-diagram", "read"),
            new Capability("ui", "cameo_get_ui_selection", "GET", "/api/v1/ui/selection", "read"),
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
            new Capability("genericTables", "cameo_list_generic_tables", "GET", "/api/v1/generic-tables", "read"),
            new Capability("genericTables", "cameo_get_generic_table", "GET", "/api/v1/generic-tables/{tableId}", "read"),
            new Capability("genericTables", "cameo_create_generic_table", "POST", "/api/v1/generic-tables", "write"),
            new Capability("genericTables", "cameo_list_generic_table_columns", "GET", "/api/v1/generic-tables/columns", "read"),
            new Capability("diagrams", "cameo_list_diagrams", "GET", "/api/v1/diagrams", "read"),
            new Capability("diagrams", "cameo_create_diagram", "POST", "/api/v1/diagrams", "write"),
            new Capability("diagrams", "cameo_add_to_diagram", "POST", "/api/v1/diagrams/{diagramId}/elements", "write"),
            new Capability("diagrams", "cameo_get_diagram_image", "GET", "/api/v1/diagrams/{diagramId}/image", "read"),
            new Capability("diagrams", "cameo_auto_layout", "POST", "/api/v1/diagrams/{diagramId}/layout", "write"),
            new Capability("diagrams", "cameo_list_diagram_shapes", "GET", "/api/v1/diagrams/{diagramId}/shapes", "read"),
            new Capability("diagrams", "cameo_get_shape_properties", "GET", "/api/v1/diagrams/{diagramId}/shapes/{presentationId}/properties", "read"),
            new Capability("inspection", "cameo_dump_diagram_properties", "GET", "/api/v1/inspect/diagrams/{diagramId}/properties", "read"),
            new Capability("inspection", "cameo_dump_presentation_properties", "GET", "/api/v1/inspect/diagrams/{diagramId}/presentations/{presentationId}/properties", "read"),
            new Capability("diagrams", "cameo_move_shapes", "PUT", "/api/v1/diagrams/{diagramId}/shapes", "write"),
            new Capability("diagrams", "cameo_delete_shapes", "DELETE", "/api/v1/diagrams/{diagramId}/shapes", "write"),
            new Capability("diagrams", "cameo_add_diagram_paths", "POST", "/api/v1/diagrams/{diagramId}/paths", "write"),
            new Capability("diagrams", "cameo_set_shape_properties", "PUT", "/api/v1/diagrams/{diagramId}/shapes/{presentationId}/properties", "write"),
            new Capability("diagrams", "cameo_set_shape_compartments", "PUT", "/api/v1/diagrams/{diagramId}/shapes/{presentationId}/compartments", "write"),
            new Capability("diagrams", "cameo_set_transition_label_presentation", "PUT", "/api/v1/diagrams/{diagramId}/presentation/transition-labels", "write"),
            new Capability("diagrams", "cameo_set_item_flow_label_presentation", "PUT", "/api/v1/diagrams/{diagramId}/presentation/item-flow-labels", "write"),
            new Capability("diagrams", "cameo_set_allocation_compartment_presentation", "PUT", "/api/v1/diagrams/{diagramId}/presentation/allocation-compartments", "write"),
            new Capability("diagrams", "cameo_prune_path_decorations", "PUT", "/api/v1/diagrams/{diagramId}/repair/path-decorations", "write"),
            new Capability("diagrams", "cameo_repair_hidden_labels", "PUT", "/api/v1/diagrams/{diagramId}/repair/hidden-labels", "write"),
            new Capability("diagrams", "cameo_repair_label_positions", "PUT", "/api/v1/diagrams/{diagramId}/repair/label-positions", "write"),
            new Capability("diagrams", "cameo_repair_conveyed_item_labels", "PUT", "/api/v1/diagrams/{diagramId}/repair/conveyed-item-labels", "write"),
            new Capability("diagrams", "cameo_normalize_compartment_presets", "PUT", "/api/v1/diagrams/{diagramId}/repair/compartment-presets", "write"),
            new Capability("diagrams", "cameo_prune_diagram_presentations", "PUT", "/api/v1/diagrams/{diagramId}/repair/prune-presentations", "write"),
            new Capability("diagrams", "cameo_reparent_shapes", "PUT", "/api/v1/diagrams/{diagramId}/shapes/reparent", "write"),
            new Capability("diagrams", "cameo_route_paths", "PUT", "/api/v1/diagrams/{diagramId}/paths/route", "write"),
            new Capability("relationMaps", "cameo_list_relation_maps", "GET", "/api/v1/relation-maps", "read"),
            new Capability("relationMaps", "cameo_get_relation_map", "GET", "/api/v1/relation-maps/{relationMapId}", "read"),
            new Capability("relationMaps", "cameo_create_relation_map", "POST", "/api/v1/relation-maps", "write"),
            new Capability("relationMaps", "cameo_configure_relation_map", "PUT", "/api/v1/relation-maps/{relationMapId}/settings", "write"),
            new Capability("relationMaps", "cameo_dump_relation_map_raw_settings", "GET", "/api/v1/relation-maps/{relationMapId}/settings/raw", "read"),
            new Capability("relationMaps", "cameo_list_relation_map_presentations", "GET", "/api/v1/relation-maps/{relationMapId}/presentations", "read"),
            new Capability("relationMaps", "cameo_refresh_relation_map", "POST", "/api/v1/relation-maps/{relationMapId}/refresh", "write"),
            new Capability("relationMaps", "cameo_get_traceability_graph", "POST", "/api/v1/relation-maps/traceability-graph", "read"),
            new Capability("relationMaps", "cameo_list_relation_map_criteria_templates", "GET", "/api/v1/relation-maps/criteria/templates", "read"),
            new Capability("relationMaps", "cameo_set_relation_map_criteria", "PUT", "/api/v1/relation-maps/{relationMapId}/criteria", "write"),
            new Capability("relationMaps", "cameo_expand_relation_map", "POST", "/api/v1/relation-maps/{relationMapId}/expand", "write"),
            new Capability("relationMaps", "cameo_collapse_relation_map", "POST", "/api/v1/relation-maps/{relationMapId}/collapse", "write"),
            new Capability("relationMaps", "cameo_render_relation_map", "POST", "/api/v1/relation-maps/{relationMapId}/render", "write"),
            new Capability("relationMaps", "cameo_verify_relation_map", "POST", "/api/v1/relation-maps/{relationMapId}/verify", "read"),
            new Capability("relationMaps", "cameo_compare_relation_maps", "POST", "/api/v1/relation-maps/compare", "read"),
            new Capability("snapshots", "cameo_create_snapshot", "POST", "/api/v1/snapshots", "read"),
            new Capability("snapshots", "cameo_list_snapshots", "GET", "/api/v1/snapshots", "read"),
            new Capability("snapshots", "cameo_get_snapshot", "GET", "/api/v1/snapshots/{snapshotId}", "read"),
            new Capability("snapshots", "cameo_delete_snapshot", "DELETE", "/api/v1/snapshots/{snapshotId}", "write"),
            new Capability("snapshots", "cameo_diff_snapshots", "POST", "/api/v1/snapshots/diff", "read"),
            new Capability("validation", "cameo_get_validation_capabilities", "GET", "/api/v1/validation/capabilities", "read"),
            new Capability("validation", "cameo_list_validation_suites", "GET", "/api/v1/validation/suites", "read"),
            new Capability("validation", "cameo_run_native_validation", "POST", "/api/v1/validation/run", "read"),
            new Capability("validation", "cameo_get_validation_result", "GET", "/api/v1/validation/results/{runId}", "read"),
            new Capability("probes", "cameo_list_probe_templates", "GET", "/api/v1/probes/templates", "read"),
            new Capability("probes", "cameo_execute_probe", "POST", "/api/v1/probes/execute", "read"),
            new Capability("specification", "cameo_get_specification", "GET", "/api/v1/elements/{elementId}/specification", "read"),
            new Capability("specification", "cameo_set_specification", "PUT", "/api/v1/elements/{elementId}/specification", "write"),
            new Capability("validation", "cameo_run_validation", "POST", "/api/v1/validation/run", "read"),
            new Capability("reports", "cameo_get_report_capabilities", "GET", "/api/v1/reports/capabilities", "read"),
            new Capability("reports", "cameo_list_report_templates", "GET", "/api/v1/reports/templates", "read"),
            new Capability("reports", "cameo_generate_report_preview", "POST", "/api/v1/reports/generate-preview", "read"),
            new Capability("reports", "cameo_generate_report", "POST", "/api/v1/reports/generate", "write"),
            new Capability("reports", "cameo_get_report_job", "GET", "/api/v1/reports/jobs/{jobId}", "read"),
            new Capability("requirements", "cameo_get_requirements_capabilities", "GET", "/api/v1/requirements/capabilities", "read"),
            new Capability("requirements", "cameo_export_requirements_preview", "POST", "/api/v1/requirements/export", "read"),
            new Capability("requirements", "cameo_import_requirements_preview", "POST", "/api/v1/requirements/import/preview", "read"),
            new Capability("importExport", "cameo_get_import_export_capabilities", "GET", "/api/v1/import-export/capabilities", "read"),
            new Capability("importExport", "cameo_export_requirements", "POST", "/api/v1/import-export/requirements/export", "read"),
            new Capability("importExport", "cameo_preview_requirements_import", "POST", "/api/v1/import-export/requirements/import-preview", "read"),
            new Capability("importExport", "cameo_apply_requirements_import", "POST", "/api/v1/import-export/requirements/apply", "write"),
            new Capability("simulation", "cameo_get_simulation_capabilities", "GET", "/api/v1/simulation/capabilities", "read"),
            new Capability("simulation", "cameo_list_simulation_configurations", "GET", "/api/v1/simulation/configurations", "read"),
            new Capability("simulation", "cameo_run_simulation_preview", "POST", "/api/v1/simulation/run-preview", "read"),
            new Capability("simulation", "cameo_run_simulation", "POST", "/api/v1/simulation/run", "write"),
            new Capability("simulation", "cameo_run_simulation_async", "POST", "/api/v1/simulation/run-async", "write"),
            new Capability("simulation", "cameo_get_simulation_result", "GET", "/api/v1/simulation/results/{runId}", "read"),
            new Capability("simulation", "cameo_terminate_simulation", "POST", "/api/v1/simulation/results/{runId}/terminate", "write"),
            new Capability("teamwork", "cameo_get_teamwork_capabilities", "GET", "/api/v1/teamwork/capabilities", "read"),
            new Capability("teamwork", "cameo_get_teamwork_project", "GET", "/api/v1/teamwork/project", "read"),
            new Capability("teamwork", "cameo_list_teamwork_descriptors", "GET", "/api/v1/teamwork/descriptors", "read"),
            new Capability("teamwork", "cameo_list_teamwork_branches", "GET", "/api/v1/teamwork/branches", "read"),
            new Capability("teamwork", "cameo_get_teamwork_history", "GET", "/api/v1/teamwork/history", "read"),
            new Capability("teamwork", "cameo_get_teamwork_locks", "GET", "/api/v1/teamwork/locks", "read"),
            new Capability("teamwork", "cameo_preview_teamwork_update", "POST", "/api/v1/teamwork/update-preview", "read"),
            new Capability("teamwork", "cameo_preview_teamwork_commit", "POST", "/api/v1/teamwork/commit-preview", "read"),
            new Capability("teamwork", "cameo_commit_teamwork", "POST", "/api/v1/teamwork/commit", "write"),
            new Capability("datahub", "cameo_get_datahub_capabilities", "GET", "/api/v1/datahub/capabilities", "read"),
            new Capability("datahub", "cameo_list_datahub_sources", "GET", "/api/v1/datahub/sources", "read"),
            new Capability("datahub", "cameo_preview_datahub_sync", "POST", "/api/v1/datahub/sync-preview", "read"),
            new Capability("criteria", "cameo_get_criteria_capabilities", "GET", "/api/v1/criteria/capabilities", "read"),
            new Capability("criteria", "cameo_list_criteria_templates", "GET", "/api/v1/criteria/templates", "read"),
            new Capability("criteria", "cameo_build_criteria_expression", "POST", "/api/v1/criteria/build", "read"),
            new Capability("criteria", "cameo_parse_criteria_expression", "POST", "/api/v1/criteria/parse", "read"),
            new Capability("criteria", "cameo_apply_criteria_template", "POST", "/api/v1/criteria/apply", "write"),
            new Capability("criteria", "cameo_capture_criteria_template_from_diff", "POST", "/api/v1/criteria/capture-template-from-diff", "read"),
            new Capability("profiles", "cameo_get_profile_capabilities", "GET", "/api/v1/profiles/capabilities", "read"),
            new Capability("profiles", "cameo_create_profile_preview", "POST", "/api/v1/profiles/create", "read"),
            new Capability("profiles", "cameo_create_stereotype_preview", "POST", "/api/v1/profiles/stereotypes/create", "read"),
            new Capability("profiles", "cameo_create_tag_preview", "POST", "/api/v1/profiles/tags/create", "read"),
            new Capability("profiles", "cameo_apply_profile_preview", "POST", "/api/v1/profiles/apply", "read"),
            new Capability("profiles", "cameo_set_profile_tags_preview", "PUT", "/api/v1/profiles/tags", "read"),
            new Capability("profiles", "cameo_export_profile_summary", "POST", "/api/v1/profiles/export-summary", "read"),
            new Capability("variants", "cameo_get_variant_capabilities", "GET", "/api/v1/variants/capabilities", "read"),
            new Capability("variants", "cameo_install_variant_pattern_preview", "POST", "/api/v1/variants/pattern/install-preview", "read"),
            new Capability("variants", "cameo_evaluate_variant_configuration", "POST", "/api/v1/variants/configurations/evaluate", "read"),
            new Capability("variants", "cameo_export_variant_configuration", "POST", "/api/v1/variants/configurations/export", "read"),
            new Capability("extensions", "cameo_get_extension_capabilities", "GET", "/api/v1/extensions/capabilities", "read"),
            new Capability("extensions", "cameo_list_extension_profiles", "GET", "/api/v1/extensions/profiles", "read"),
            new Capability("extensions", "cameo_scan_extensions", "POST", "/api/v1/extensions/model-scan", "read"),
            new Capability("extensions", "cameo_install_extension_pattern_preview", "POST", "/api/v1/extensions/pattern/install-preview", "read"),
            new Capability("extensions", "cameo_refuse_compliance_claim", "POST", "/api/v1/extensions/compliance-claim", "read"),
            new Capability("typedDiagrams", "cameo_get_typed_diagram_capabilities", "GET", "/api/v1/typed-diagrams/capabilities", "read"),
            new Capability("typedDiagrams", "cameo_list_typed_diagrams", "GET", "/api/v1/typed-diagrams", "read"),
            new Capability("typedDiagrams", "cameo_inspect_typed_diagram", "POST", "/api/v1/typed-diagrams/inspect", "read"),
            new Capability("typedDiagrams", "cameo_create_sequence_message_preview", "POST", "/api/v1/typed-diagrams/sequence/messages", "read"),
            new Capability("typedDiagrams", "cameo_create_state_transition_preview", "POST", "/api/v1/typed-diagrams/state/transitions", "read"),
            new Capability("typedDiagrams", "cameo_create_parametric_binding_preview", "POST", "/api/v1/typed-diagrams/parametric/bindings", "read"),
            new Capability("typedDiagrams", "cameo_apply_diagram_legend_preview", "POST", "/api/v1/typed-diagrams/legends/apply", "read"),
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
        JsonArray statusAliases = new JsonArray();
        statusAliases.add(LEGACY_STATUS_PATH);
        statusAliases.add(STATUS_PATH);
        json.add("statusAliases", statusAliases);
        json.addProperty("capabilitiesEndpoint", CAPABILITIES_PATH);
        JsonArray capabilityAliases = new JsonArray();
        capabilityAliases.add(LEGACY_CAPABILITIES_PATH);
        capabilityAliases.add(CAPABILITIES_PATH);
        json.add("capabilitiesAliases", capabilityAliases);
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
