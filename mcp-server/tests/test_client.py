import base64
import unittest
from io import BytesIO
from typing import Any
from unittest.mock import AsyncMock, patch

from PIL import Image

from cameo_mcp import client


def reset_client_state() -> None:
    client._shared_client = None
    client._shared_client_base_url = None
    client._capabilities_cache = None
    client._capabilities_cache_base_url = None


def _make_base64_png(width: int = 20, height: int = 10) -> str:
    image = Image.new("RGBA", (width, height), (255, 0, 0, 255))
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("ascii")


class BridgeMetadataTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_client_state()

    def test_annotate_bridge_metadata_marks_compatible_bridge(self) -> None:
        annotated = client._annotate_bridge_metadata(
            {
                "pluginVersion": client.BRIDGE_PLUGIN_VERSION,
                "apiVersion": client.BRIDGE_API_VERSION,
                "handshakeVersion": client.BRIDGE_HANDSHAKE_VERSION,
            }
        )

        compatibility = annotated["compatibility"]
        self.assertTrue(compatibility["clientCompatible"])
        self.assertEqual([], compatibility["clientCompatibilityErrors"])

    def test_require_compatible_bridge_rejects_mismatch(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "plugin version mismatch"):
            client._require_compatible_bridge(
                {
                    "pluginVersion": "9.9.9",
                    "apiVersion": client.BRIDGE_API_VERSION,
                    "handshakeVersion": client.BRIDGE_HANDSHAKE_VERSION,
                }
            )


class ClientRequestTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        reset_client_state()

    async def test_status_returns_annotated_metadata(self) -> None:
        with patch(
            "cameo_mcp.client._request_raw",
            new=AsyncMock(
                return_value={
                    "status": "ok",
                    "pluginVersion": client.BRIDGE_PLUGIN_VERSION,
                    "apiVersion": client.BRIDGE_API_VERSION,
                    "handshakeVersion": client.BRIDGE_HANDSHAKE_VERSION,
                }
            ),
        ):
            result = await client.status()

        self.assertEqual("ok", result["status"])
        self.assertTrue(result["compatibility"]["clientCompatible"])

    async def test_ensure_compatible_bridge_caches_capabilities_by_base_url(self) -> None:
        with patch(
            "cameo_mcp.client._request_raw",
            new=AsyncMock(
                return_value={
                    "pluginVersion": client.BRIDGE_PLUGIN_VERSION,
                    "apiVersion": client.BRIDGE_API_VERSION,
                    "handshakeVersion": client.BRIDGE_HANDSHAKE_VERSION,
                }
            ),
        ) as request_raw:
            first = await client._ensure_compatible_bridge()
            second = await client._ensure_compatible_bridge()

        self.assertTrue(first["compatibility"]["clientCompatible"])
        self.assertEqual(first, second)
        request_raw.assert_awaited_once_with("GET", "/capabilities")

    async def test_query_elements_passes_paging_and_view_params(self) -> None:
        with patch("cameo_mcp.client._request", new=AsyncMock(return_value={"count": 0})) as request:
            await client.query_elements(
                type="Block",
                name="ATM",
                package="pkg-1",
                stereotype="requirement",
                recursive=False,
                limit=25,
                offset=50,
                view="full",
            )

        request.assert_awaited_once()
        self.assertEqual("GET", request.await_args.args[0])
        self.assertEqual("/elements", request.await_args.args[1])
        self.assertEqual(
            {
                "type": "Block",
                "name": "ATM",
                "package": "pkg-1",
                "stereotype": "requirement",
                "recursive": "false",
                "limit": "25",
                "offset": "50",
                "view": "full",
            },
            request.await_args.kwargs["params"],
        )

    async def test_list_containment_children_passes_filters_and_view(self) -> None:
        with patch("cameo_mcp.client._request", new=AsyncMock(return_value={"count": 0})) as request:
            await client.list_containment_children(
                root_id="root-1",
                limit=10,
                offset=20,
                type="Block",
                name="Power",
                stereotype="block",
                view="full",
            )

        request.assert_awaited_once()
        self.assertEqual("GET", request.await_args.args[0])
        self.assertEqual("/containment-tree/children", request.await_args.args[1])
        self.assertEqual(
            {
                "limit": "10",
                "offset": "20",
                "rootId": "root-1",
                "type": "Block",
                "name": "Power",
                "stereotype": "block",
                "view": "full",
            },
            request.await_args.kwargs["params"],
        )

    async def test_add_to_diagram_omits_negative_auto_size_dimensions(self) -> None:
        with patch("cameo_mcp.client._request", new=AsyncMock(return_value={"added": True})) as request:
            await client.add_to_diagram(
                diagram_id="dia-1",
                element_id="el-1",
                x=120,
                y=220,
                width=-1,
                height=-1,
            )

        request.assert_awaited_once()
        self.assertEqual(
            {"elementId": "el-1", "x": 120, "y": 220},
            request.await_args.kwargs["json_body"],
        )

    async def test_add_to_diagram_keeps_explicit_dimensions(self) -> None:
        with patch("cameo_mcp.client._request", new=AsyncMock(return_value={"added": True})) as request:
            await client.add_to_diagram(
                diagram_id="dia-1",
                element_id="el-1",
                width=320,
                height=180,
            )

        request.assert_awaited_once()
        self.assertEqual(
            {"elementId": "el-1", "width": 320, "height": 180},
            request.await_args.kwargs["json_body"],
        )

    async def test_add_to_diagram_rejects_mixed_explicit_and_auto_size_dimensions(self) -> None:
        with self.assertRaisesRegex(ValueError, "width and height must both be non-negative"):
            await client.add_to_diagram(
                diagram_id="dia-1",
                element_id="el-1",
                width=-1,
                height=180,
            )

    async def test_add_to_diagram_uses_rest_path_for_activity_partitions(self) -> None:
        with patch(
            "cameo_mcp.client._request",
            new=AsyncMock(return_value={"added": True, "presentationId": "pe-partition"}),
        ) as request:
            result = await client.add_to_diagram(
                diagram_id="dia-1",
                element_id="partition-1",
                x=80,
                y=120,
                width=220,
                height=320,
            )

        self.assertEqual("pe-partition", result["presentationId"])
        request.assert_awaited_once()
        self.assertEqual(
            {"elementId": "partition-1", "x": 80, "y": 120, "width": 220, "height": 320},
            request.await_args.kwargs["json_body"],
        )

    async def test_add_to_diagram_keeps_rest_path_for_non_partition_elements(self) -> None:
        with patch("cameo_mcp.client._request", new=AsyncMock(return_value={"added": True})) as request:
            await client.add_to_diagram(
                diagram_id="dia-1",
                element_id="el-1",
                x=120,
                y=220,
                width=140,
                height=48,
            )

        request.assert_awaited_once()
        self.assertEqual(
            {"elementId": "el-1", "x": 120, "y": 220, "width": 140, "height": 48},
            request.await_args.kwargs["json_body"],
        )

    async def test_get_diagram_image_passes_native_scale_percentage(self) -> None:
        with patch(
            "cameo_mcp.client._request",
            new=AsyncMock(return_value={"format": "png", "image": _make_base64_png()}),
        ) as request:
            result = await client.get_diagram_image("dia-1", scale_percentage=300)

        self.assertIn("imageBytes", result)
        request.assert_awaited_once()
        self.assertEqual("GET", request.await_args.args[0])
        self.assertEqual("/diagrams/dia-1/image", request.await_args.args[1])
        self.assertEqual({"scalePercentage": 300}, request.await_args.kwargs["params"])

    async def test_get_diagram_image_rejects_invalid_native_scale_percentage(self) -> None:
        with self.assertRaisesRegex(ValueError, "scale_percentage must be between 25 and 1000"):
            await client.get_diagram_image("dia-1", scale_percentage=10)

    async def test_run_validation_passes_bounded_request_body(self) -> None:
        with patch("cameo_mcp.client._request", new=AsyncMock(return_value={"dryRun": True})) as request:
            await client.run_validation(
                suite_id="suite-1",
                scope_mode="elements",
                scope_element_ids=["el-1"],
                min_severity="warning",
                timeout_ms=12000,
            )

        request.assert_awaited_once()
        self.assertEqual("POST", request.await_args.args[0])
        self.assertEqual("/validation/run", request.await_args.args[1])
        self.assertEqual(
            {
                "scopeMode": "elements",
                "timeoutMs": 12000,
                "suiteId": "suite-1",
                "scopeElementIds": ["el-1"],
                "minSeverity": "warning",
            },
            request.await_args.kwargs["json_body"],
        )

    async def test_generate_report_preview_passes_template_and_parameters(self) -> None:
        with patch("cameo_mcp.client._request", new=AsyncMock(return_value={"dryRun": True})) as request:
            await client.generate_report_preview(
                template_id="template-1",
                template_name="Use Case (Simple)",
                report_name="Built-in",
                output_path="C:/tmp/report.docx",
                output_format="docx",
                scope_element_ids=["pkg-1"],
                recursive=True,
                parameters={"scopeId": "pkg-1"},
            )

        request.assert_awaited_once()
        self.assertEqual("POST", request.await_args.args[0])
        self.assertEqual("/reports/generate-preview", request.await_args.args[1])
        self.assertEqual(
            {
                "templateId": "template-1",
                "templateName": "Use Case (Simple)",
                "reportName": "Built-in",
                "outputPath": "C:/tmp/report.docx",
                "format": "docx",
                "scopeElementIds": ["pkg-1"],
                "recursive": True,
                "parameters": {"scopeId": "pkg-1"},
            },
            request.await_args.kwargs["json_body"],
        )

    async def test_generate_report_passes_native_generation_options(self) -> None:
        with patch("cameo_mcp.client._request", new=AsyncMock(return_value={"generated": True})) as request:
            await client.generate_report(
                template_name="Use Case (Simple)",
                output_path="C:/tmp/report.docx",
                output_format="docx",
                scope_element_ids=["pkg-1"],
                recursive=True,
                display_in_viewer=False,
            )

        request.assert_awaited_once()
        self.assertEqual("POST", request.await_args.args[0])
        self.assertEqual("/reports/generate", request.await_args.args[1])
        self.assertEqual(
            {
                "allowWrite": False,
                "templateName": "Use Case (Simple)",
                "outputPath": "C:/tmp/report.docx",
                "format": "docx",
                "scopeElementIds": ["pkg-1"],
                "recursive": True,
                "displayInViewer": False,
            },
            request.await_args.kwargs["json_body"],
        )

    async def test_export_requirements_passes_root_filters(self) -> None:
        with patch("cameo_mcp.client._request", new=AsyncMock(return_value={"count": 2})) as request:
            await client.export_requirements(root_id="pkg-1", package_id="pkg-2", limit=25)

        request.assert_awaited_once_with(
            "POST",
            "/import-export/requirements/export",
            json_body={
                "format": "json",
                "limit": 25,
                "rootId": "pkg-1",
                "packageId": "pkg-2",
            },
        )

    async def test_apply_requirements_import_passes_direct_rows(self) -> None:
        rows = [{"externalId": "REQ-1", "name": "Requirement 1"}]
        with patch("cameo_mcp.client._request", new=AsyncMock(return_value={"applied": True})) as request:
            await client.apply_requirements_import(
                target_package_id="pkg-1",
                requirements=rows,
                dry_run=False,
                allow_write=True,
            )

        request.assert_awaited_once_with(
            "POST",
            "/import-export/requirements/apply",
            json_body={
                "format": "json",
                "dryRun": False,
                "allowWrite": True,
                "targetPackageId": "pkg-1",
                "requirements": rows,
            },
        )

    async def test_create_relationship_omits_optional_connector_fields_when_absent(self) -> None:
        with patch("cameo_mcp.client._request", new=AsyncMock(return_value={"created": True})) as request:
            await client.create_relationship(
                type="Transition",
                source_id="src-1",
                target_id="tgt-1",
            )

        request.assert_awaited_once()
        self.assertEqual(
            {"type": "Transition", "sourceId": "src-1", "targetId": "tgt-1"},
            request.await_args.kwargs["json_body"],
        )

    async def test_create_element_includes_typed_property_and_port_fields(self) -> None:
        with patch("cameo_mcp.client._request", new=AsyncMock(return_value={"created": True})) as request:
            await client.create_element(
                type="Port",
                name="status",
                parent_id="block-1",
                stereotype="FullPort",
                type_id="if-1",
                lower=0,
                upper="*",
                is_ordered=False,
                is_unique=True,
                is_behavior=True,
                is_conjugated=False,
                is_service=True,
            )

        request.assert_awaited_once()
        self.assertEqual(
            {
                "type": "Port",
                "name": "status",
                "parentId": "block-1",
                "stereotype": "FullPort",
                "typeId": "if-1",
                "lower": 0,
                "upper": "*",
                "isOrdered": False,
                "isUnique": True,
                "isBehavior": True,
                "isConjugated": False,
                "isService": True,
            },
            request.await_args.kwargs["json_body"],
        )

    async def test_create_element_includes_flow_property_direction(self) -> None:
        with patch("cameo_mcp.client._request", new=AsyncMock(return_value={"created": True})) as request:
            await client.create_element(
                type="FlowProperty",
                name="payload",
                parent_id="if-1",
                type_id="signal-1",
                direction="out",
            )

        request.assert_awaited_once()
        self.assertEqual(
            {
                "type": "FlowProperty",
                "name": "payload",
                "parentId": "if-1",
                "typeId": "signal-1",
                "direction": "out",
            },
            request.await_args.kwargs["json_body"],
        )

    async def test_create_relationship_includes_connector_fields(self) -> None:
        with patch("cameo_mcp.client._request", new=AsyncMock(return_value={"created": True})) as request:
            await client.create_relationship(
                type="Connector",
                source_id="port-a",
                target_id="port-b",
                owner_id="block-1",
                source_part_with_port_id="part-a",
                target_part_with_port_id="part-b",
            )

        request.assert_awaited_once()
        self.assertEqual(
            {
                "type": "Connector",
                "sourceId": "port-a",
                "targetId": "port-b",
                "ownerId": "block-1",
                "sourcePartWithPortId": "part-a",
                "targetPartWithPortId": "part-b",
            },
            request.await_args.kwargs["json_body"],
        )

    async def test_create_relationship_includes_information_flow_fields(self) -> None:
        with patch("cameo_mcp.client._request", new=AsyncMock(return_value={"created": True})) as request:
            await client.create_relationship(
                type="ItemFlow",
                source_id="port-a",
                target_id="port-b",
                owner_id="system-block",
                realizing_connector_id="connector-1",
                conveyed_ids=["io-block"],
                item_property_id="flow-prop-1",
            )

        request.assert_awaited_once()
        self.assertEqual(
            {
                "type": "ItemFlow",
                "sourceId": "port-a",
                "targetId": "port-b",
                "ownerId": "system-block",
                "realizingConnectorId": "connector-1",
                "conveyedIds": ["io-block"],
                "itemPropertyId": "flow-prop-1",
            },
            request.await_args.kwargs["json_body"],
        )

    async def test_get_interface_flow_properties_uses_native_endpoint(self) -> None:
        with patch("cameo_mcp.client._request", new=AsyncMock(return_value={"flowProperties": []})) as request:
            await client.get_interface_flow_properties(["if-1", "if-2"])

        request.assert_awaited_once_with(
            "POST",
            "/elements/interface-flow-properties",
            json_body={"interfaceIds": ["if-1", "if-2"]},
        )

    async def test_list_matrices_passes_filters(self) -> None:
        with patch("cameo_mcp.client._request", new=AsyncMock(return_value={"count": 0})) as request:
            await client.list_matrices(
                kind="refine",
                owner_id="pkg-1",
            )

        request.assert_awaited_once()
        self.assertEqual("GET", request.await_args.args[0])
        self.assertEqual("/matrices", request.await_args.args[1])
        self.assertEqual(
            {
                "kind": "refine",
                "ownerId": "pkg-1",
            },
            request.await_args.kwargs["params"],
        )

    async def test_get_matrix_uses_matrix_endpoint(self) -> None:
        with patch("cameo_mcp.client._request", new=AsyncMock(return_value={"id": "matrix-1"})) as request:
            await client.get_matrix("matrix-1")

        request.assert_awaited_once_with("GET", "/matrices/matrix-1")

    async def test_create_matrix_includes_scopes(self) -> None:
        with patch("cameo_mcp.client._request", new=AsyncMock(return_value={"created": True})) as request:
            await client.create_matrix(
                kind="derive",
                parent_id="pkg-1",
                name="Derive Coverage",
                scope_id="pkg-2",
                row_scope_id="pkg-3",
                column_scope_id="pkg-4",
            )

        request.assert_awaited_once()
        self.assertEqual("POST", request.await_args.args[0])
        self.assertEqual("/matrices", request.await_args.args[1])
        self.assertEqual(
            {
                "kind": "derive",
                "parentId": "pkg-1",
                "name": "Derive Coverage",
                "scopeId": "pkg-2",
                "rowScopeId": "pkg-3",
                "columnScopeId": "pkg-4",
            },
            request.await_args.kwargs["json_body"],
        )

    async def test_create_matrix_includes_type_domains(self) -> None:
        with patch("cameo_mcp.client._request", new=AsyncMock(return_value={"created": True})) as request:
            await client.create_matrix(
                kind="refine",
                parent_id="pkg-1",
                row_types=["Activity"],
                column_types=["Requirement"],
            )

        request.assert_awaited_once()
        self.assertEqual(
            {
                "kind": "refine",
                "parentId": "pkg-1",
                "rowTypes": ["Activity"],
                "columnTypes": ["Requirement"],
            },
            request.await_args.kwargs["json_body"],
        )

    async def test_create_matrix_normalizes_kind_aliases(self) -> None:
        with patch("cameo_mcp.client._request", new=AsyncMock(return_value={"created": True})) as request:
            await client.create_matrix(
                kind="Refine Requirement Matrix",
                parent_id="pkg-1",
            )

        self.assertEqual(
            {
                "kind": "refine",
                "parentId": "pkg-1",
            },
            request.await_args.kwargs["json_body"],
        )

    async def test_create_matrix_normalizes_satisfy_aliases(self) -> None:
        with patch("cameo_mcp.client._request", new=AsyncMock(return_value={"created": True})) as request:
            await client.create_matrix(
                kind="Satisfy Requirement Matrix",
                parent_id="pkg-1",
            )

        self.assertEqual(
            {
                "kind": "satisfy",
                "parentId": "pkg-1",
            },
            request.await_args.kwargs["json_body"],
        )

    async def test_list_matrices_normalizes_allocation_aliases(self) -> None:
        with patch("cameo_mcp.client._request", new=AsyncMock(return_value={"count": 0})) as request:
            await client.list_matrices(
                kind="System Allocation Matrix",
            )

        self.assertEqual(
            {
                "kind": "allocation",
            },
            request.await_args.kwargs["params"],
        )

    async def test_create_matrix_normalizes_dependency_alias(self) -> None:
        with patch("cameo_mcp.client._request", new=AsyncMock(return_value={"created": True})) as request:
            await client.create_matrix(
                kind="Dependency Matrix",
                parent_id="pkg-1",
                row_types=["OpaqueAction"],
                column_types=["OpaqueAction"],
            )

        self.assertEqual(
            {
                "kind": "dependency",
                "parentId": "pkg-1",
                "rowTypes": ["OpaqueAction"],
                "columnTypes": ["OpaqueAction"],
            },
            request.await_args.kwargs["json_body"],
        )

    async def test_create_relation_map_includes_native_graph_settings(self) -> None:
        with patch("cameo_mcp.client._request", new=AsyncMock(return_value={"created": True})) as request:
            await client.create_relation_map(
                parent_id="pkg-1",
                name="Traceability Map",
                context_element_id="req-1",
                scope_ids=["pkg-2"],
                element_type_ids=["stereotype-1"],
                dependency_criteria=["DeriveReqt", "Satisfy"],
                depth=2,
                layout="hierarchic",
                legend_enabled=True,
                show_stereotypes=True,
                make_element_as_context=True,
            )

        request.assert_awaited_once()
        self.assertEqual("POST", request.await_args.args[0])
        self.assertEqual("/relation-maps", request.await_args.args[1])
        self.assertEqual(
            {
                "parentId": "pkg-1",
                "name": "Traceability Map",
                "contextElementId": "req-1",
                "scopeIds": ["pkg-2"],
                "elementTypeIds": ["stereotype-1"],
                "dependencyCriteria": ["DeriveReqt", "Satisfy"],
                "depth": 2,
                "layout": "hierarchic",
                "legendEnabled": True,
                "showStereotypes": True,
                "makeElementAsContext": True,
            },
            request.await_args.kwargs["json_body"],
        )

    async def test_configure_relation_map_omits_absent_settings(self) -> None:
        with patch("cameo_mcp.client._request", new=AsyncMock(return_value={"configured": True})) as request:
            await client.configure_relation_map(
                relation_map_id="rm-1",
                context_element_id="block-1",
                depth=3,
                legend_enabled=False,
            )

        request.assert_awaited_once()
        self.assertEqual("PUT", request.await_args.args[0])
        self.assertEqual("/relation-maps/rm-1/settings", request.await_args.args[1])
        self.assertEqual(
            {
                "contextElementId": "block-1",
                "depth": 3,
                "legendEnabled": False,
            },
            request.await_args.kwargs["json_body"],
        )

    async def test_refresh_relation_map_uses_relation_map_endpoint(self) -> None:
        with patch("cameo_mcp.client._request", new=AsyncMock(return_value={"refreshed": True})) as request:
            await client.refresh_relation_map("rm-1")

        request.assert_awaited_once_with(
            "POST",
            "/relation-maps/rm-1/refresh",
            json_body={"refreshTimeoutSeconds": 120},
            timeout=120.0,
        )

    async def test_ui_state_uses_summary_query(self) -> None:
        with patch("cameo_mcp.client._request", new=AsyncMock(return_value={"selection": {}})) as request:
            await client.get_ui_state(summary_only=True)

        request.assert_awaited_once_with(
            "GET",
            "/ui/state",
            params={"summaryOnly": True},
        )

    async def test_active_diagram_and_selection_paths(self) -> None:
        with patch("cameo_mcp.client._request", new=AsyncMock(return_value={})) as request:
            await client.get_active_diagram()
            await client.get_ui_selection()

        self.assertEqual(("GET", "/ui/active-diagram"), request.await_args_list[0].args)
        self.assertEqual(("GET", "/ui/selection"), request.await_args_list[1].args)

    async def test_relation_map_raw_settings_path_and_params(self) -> None:
        with patch("cameo_mcp.client._request", new=AsyncMock(return_value={"rawSettings": {}})) as request:
            await client.get_relation_map_raw_settings("rm-1", include_raw=True, summary_only=True)

        request.assert_awaited_once_with(
            "GET",
            "/relation-maps/rm-1/settings/raw",
            params={"includeRaw": True, "summaryOnly": True},
        )

    async def test_relation_map_presentations_path_and_params(self) -> None:
        with patch("cameo_mcp.client._request", new=AsyncMock(return_value={"presentationCount": 0})) as request:
            await client.get_relation_map_presentations(
                "rm-1",
                include_properties=True,
                include_raw=True,
                summary_only=False,
                limit=10,
                offset=5,
            )

        request.assert_awaited_once_with(
            "GET",
            "/relation-maps/rm-1/presentations",
            params={
                "includeProperties": True,
                "includeRaw": True,
                "summaryOnly": False,
                "limit": 10,
                "offset": 5,
            },
        )

    async def test_relation_map_mutation_paths_and_bodies(self) -> None:
        with patch("cameo_mcp.client._request", new=AsyncMock(return_value={})) as request:
            await client.list_relation_map_criteria_templates()
            await client.set_relation_map_criteria(
                "rm-1",
                mode="append",
                criteria=[{"template": "satisfy.sourceToTarget"}],
                refresh=False,
            )
            await client.expand_relation_map("rm-1", mode="byDepth", depth=2, layout="hierarchic")
            await client.collapse_relation_map("rm-1", element_ids=["el-1"], refresh=False)
            await client.render_relation_map("rm-1", expand="all", include_image=False, scale_percentage=150)
            await client.verify_relation_map(
                "rm-1",
                expected_min_nodes=2,
                expected_min_edges=1,
                expected_rendered_nodes=3,
                relationship_types=["Satisfy"],
                max_depth=4,
            )
            await client.compare_relation_maps("left", "right", include_presentations=False, include_raw=True)

        self.assertEqual(("GET", "/relation-maps/criteria/templates"), request.await_args_list[0].args)
        request.assert_any_await(
            "PUT",
            "/relation-maps/rm-1/criteria",
            json_body={
                "mode": "append",
                "criteria": [{"template": "satisfy.sourceToTarget"}],
                "refresh": False,
            },
        )
        request.assert_any_await(
            "POST",
            "/relation-maps/rm-1/expand",
            json_body={
                "mode": "byDepth",
                "refresh": False,
                "depth": 2,
                "layout": "hierarchic",
                "actionTimeoutSeconds": 120,
            },
            timeout=120.0,
        )
        request.assert_any_await(
            "POST",
            "/relation-maps/rm-1/collapse",
            json_body={
                "mode": "all",
                "refresh": False,
                "elementIds": ["el-1"],
                "actionTimeoutSeconds": 120,
            },
            timeout=120.0,
        )
        request.assert_any_await(
            "POST",
            "/relation-maps/rm-1/render",
            json_body={
                "refresh": False,
                "expand": "all",
                "scalePercentage": 150,
                "includeImage": False,
                "includePresentationSummary": True,
                "renderTimeoutSeconds": 120,
            },
            timeout=120.0,
        )
        request.assert_any_await(
            "POST",
            "/relation-maps/rm-1/verify",
            json_body={
                "expectedMinNodes": 2,
                "expectedMinEdges": 1,
                "expectedRenderedNodes": 3,
                "maxDepth": 4,
                "relationshipTypes": ["Satisfy"],
            },
        )
        request.assert_any_await(
            "POST",
            "/relation-maps/compare",
            json_body={
                "leftRelationMapId": "left",
                "rightRelationMapId": "right",
                "includePresentations": False,
                "includeRaw": True,
            },
        )

    async def test_diagram_property_dump_path_and_params(self) -> None:
        with patch("cameo_mcp.client._request", new=AsyncMock(return_value={"presentationCount": 1})) as request:
            await client.get_diagram_properties(
                "dia-1",
                include_raw=True,
                include_presentation_properties=True,
                summary_only=False,
                limit=25,
                offset=2,
            )

        request.assert_awaited_once_with(
            "GET",
            "/inspect/diagrams/dia-1/properties",
            params={
                "includeRaw": True,
                "includePresentationProperties": True,
                "summaryOnly": False,
                "limit": 25,
                "offset": 2,
            },
        )

    async def test_presentation_property_dump_path_and_params(self) -> None:
        with patch("cameo_mcp.client._request", new=AsyncMock(return_value={"presentation": {}})) as request:
            await client.get_presentation_properties("dia-1", "pe-1", include_raw=True, summary_only=True)

        request.assert_awaited_once_with(
            "GET",
            "/inspect/diagrams/dia-1/presentations/pe-1/properties",
            params={"includeRaw": True, "summaryOnly": True},
        )

    async def test_create_snapshot_body_omits_absent_optional_flags(self) -> None:
        with patch("cameo_mcp.client._request", new=AsyncMock(return_value={"snapshotId": "s1"})) as request:
            await client.create_snapshot(
                target_type="relationMap",
                target_id="rm-1",
                name="before",
                include_raw=True,
                include_presentations=True,
            )

        request.assert_awaited_once_with(
            "POST",
            "/snapshots",
            json_body={
                "targetType": "relationMap",
                "targetId": "rm-1",
                "name": "before",
                "includeRaw": True,
                "includePresentations": True,
            },
        )

    async def test_snapshot_list_get_delete_paths(self) -> None:
        with patch("cameo_mcp.client._request", new=AsyncMock(return_value={})) as request:
            await client.list_snapshots()
            await client.get_snapshot("s1")
            await client.delete_snapshot("s1")

        self.assertEqual(("GET", "/snapshots"), request.await_args_list[0].args)
        self.assertEqual(("GET", "/snapshots/s1"), request.await_args_list[1].args)
        self.assertEqual(("DELETE", "/snapshots/s1"), request.await_args_list[2].args)

    async def test_diff_snapshots_body(self) -> None:
        with patch("cameo_mcp.client._request", new=AsyncMock(return_value={"changeCount": 1})) as request:
            await client.diff_snapshots(
                before_snapshot_id="before",
                after_snapshot_id="after",
                ignore_paths=["$.createdAt"],
                include_details=False,
                max_changes=25,
            )

        request.assert_awaited_once_with(
            "POST",
            "/snapshots/diff",
            json_body={
                "beforeSnapshotId": "before",
                "afterSnapshotId": "after",
                "ignorePaths": ["$.createdAt"],
                "includeDetails": False,
                "maxChanges": 25,
            },
        )

    async def test_probe_paths_and_bodies(self) -> None:
        with patch("cameo_mcp.client._request", new=AsyncMock(return_value={})) as request:
            await client.list_probe_templates()
            await client.execute_probe(
                template="relationMap.listGraphSettingsMethods",
                description="inspect graph settings",
            )
            await client.execute_probe(
                operation="invokeGraphSettingsGetter",
                relation_map_id="rm-1",
                method_name="getDependencyCriterion",
            )

        self.assertEqual(("GET", "/probes/templates"), request.await_args_list[0].args)
        request.assert_any_await(
            "POST",
            "/probes/execute",
            json_body={
                "mode": "read",
                "language": "javaReflection",
                "timeoutMs": 5000,
                "requiresProject": True,
                "template": "relationMap.listGraphSettingsMethods",
                "description": "inspect graph settings",
            },
        )
        request.assert_any_await(
            "POST",
            "/probes/execute",
            json_body={
                "mode": "read",
                "language": "javaReflection",
                "timeoutMs": 5000,
                "requiresProject": True,
                "operation": "invokeGraphSettingsGetter",
                "methodName": "getDependencyCriterion",
                "relationMapId": "rm-1",
            },
        )

    async def test_get_traceability_graph_uses_roots_endpoint(self) -> None:
        with patch("cameo_mcp.client._request", new=AsyncMock(return_value={"nodeCount": 2})) as request:
            await client.get_traceability_graph(
                root_element_ids=["req-1"],
                relationship_types=["DeriveReqt", "Satisfy"],
                direction="incoming",
                max_depth=2,
                max_nodes=50,
            )

        request.assert_awaited_once_with(
            "POST",
            "/relation-maps/traceability-graph",
            json_body={
                "direction": "incoming",
                "maxDepth": 2,
                "maxNodes": 50,
                "rootElementIds": ["req-1"],
                "relationshipTypes": ["DeriveReqt", "Satisfy"],
            },
        )

    async def test_get_traceability_graph_can_use_relation_map_context(self) -> None:
        with patch("cameo_mcp.client._request", new=AsyncMock(return_value={"nodeCount": 1})) as request:
            await client.get_traceability_graph(
                relation_map_id="rm-1",
                max_depth=4,
            )

        request.assert_awaited_once_with(
            "POST",
            "/relation-maps/rm-1/graph",
            json_body={
                "direction": "both",
                "maxDepth": 4,
                "maxNodes": 250,
            },
        )

    async def test_create_diagram_normalizes_internal_block_alias(self) -> None:
        with patch("cameo_mcp.client._request", new=AsyncMock(return_value={"id": "dia-1"})) as request:
            await client.create_diagram(
                type="InternalBlockDiagram",
                name="Context",
                parent_id="block-1",
            )

        self.assertEqual(
            {
                "type": "IBD",
                "name": "Context",
                "parentId": "block-1",
            },
            request.await_args.kwargs["json_body"],
        )

    async def test_create_diagram_normalizes_sysml_ibd_alias(self) -> None:
        with patch("cameo_mcp.client._request", new=AsyncMock(return_value={"id": "dia-1"})) as request:
            await client.create_diagram(
                type="SysML IBD",
                name="Context",
                parent_id="block-1",
            )

        self.assertEqual(
            {
                "type": "IBD",
                "name": "Context",
                "parentId": "block-1",
            },
            request.await_args.kwargs["json_body"],
        )

    async def test_create_diagram_normalizes_relationship_map_alias(self) -> None:
        with patch("cameo_mcp.client._request", new=AsyncMock(return_value={"id": "dia-1"})) as request:
            await client.create_diagram(
                type="Relationship Map",
                name="Traceability",
                parent_id="pkg-1",
            )

        self.assertEqual(
            {
                "type": "RelationMap",
                "name": "Traceability",
                "parentId": "pkg-1",
            },
            request.await_args.kwargs["json_body"],
        )

    async def test_create_diagram_sends_relation_map_options(self) -> None:
        with patch("cameo_mcp.client._request", new=AsyncMock(return_value={"id": "dia-1"})) as request:
            await client.create_diagram(
                type="RelationMap",
                name="Traceability",
                parent_id="pkg-1",
                relation_map_context_id="block-1",
                relation_map_scope_ids=["pkg-1"],
                relation_map_element_types=["Block", "Requirement"],
                relation_map_dependency_criteria=["<criteria/>"],
                relation_map_depth=2,
            )

        self.assertEqual(
            {
                "type": "RelationMap",
                "name": "Traceability",
                "parentId": "pkg-1",
                "relationMapContextId": "block-1",
                "relationMapScopeIds": ["pkg-1"],
                "relationMapElementTypes": ["Block", "Requirement"],
                "relationMapDependencyCriteria": ["<criteria/>"],
                "relationMapDepth": 2,
            },
            request.await_args.kwargs["json_body"],
        )

    async def test_create_diagram_rejects_invalid_relation_map_depth(self) -> None:
        with self.assertRaisesRegex(ValueError, "relation_map_depth must be"):
            await client.create_diagram(
                type="RelationMap",
                name="Traceability",
                parent_id="pkg-1",
                relation_map_depth=-2,
            )

    async def test_create_diagram_normalizes_content_diagram_alias(self) -> None:
        with patch("cameo_mcp.client._request", new=AsyncMock(return_value={"id": "dia-1"})) as request:
            await client.create_diagram(
                type="content",
                name="Navigation",
                parent_id="pkg-1",
            )

        self.assertEqual(
            {
                "type": "Content Diagram",
                "name": "Navigation",
                "parentId": "pkg-1",
            },
            request.await_args.kwargs["json_body"],
        )

    async def test_get_diagram_image_can_omit_base64_payload_client_side(self) -> None:
        payload = {
            "id": "dia-1",
            "name": "Demo",
            "format": "png",
            "width": 20,
            "height": 10,
            "image": _make_base64_png(20, 10),
        }

        with patch("cameo_mcp.client._request", new=AsyncMock(return_value=payload)):
            result = await client.get_diagram_image("dia-1", include_image=False)

        self.assertEqual("dia-1", result["id"])
        self.assertTrue(result["imageOmitted"])
        self.assertNotIn("image", result)
        self.assertGreater(result["imageBytes"], 0)

    async def test_get_diagram_image_can_resize_and_transcode_client_side(self) -> None:
        payload = {
            "id": "dia-1",
            "name": "Demo",
            "format": "png",
            "width": 20,
            "height": 10,
            "image": _make_base64_png(20, 10),
        }

        with patch("cameo_mcp.client._request", new=AsyncMock(return_value=payload)):
            result = await client.get_diagram_image(
                "dia-1",
                format="jpeg",
                max_width=5,
                max_height=5,
                quality=70,
            )

        self.assertEqual("jpg", result["format"])
        self.assertLessEqual(result["width"], 5)
        self.assertLessEqual(result["height"], 5)
        self.assertIn("image", result)
        self.assertGreater(result["imageBytes"], 0)

    async def test_list_diagram_shapes_can_filter_and_page_client_side(self) -> None:
        payload = {
            "diagramId": "dia-1",
            "shapeCount": 3,
            "shapes": [
                {
                    "presentationId": "pe-1",
                    "shapeType": "ActionView",
                    "elementId": "el-1",
                    "elementType": "OpaqueAction",
                    "bounds": {"x": 0, "y": 0, "width": 10, "height": 10},
                    "childCount": 2,
                },
                {
                    "presentationId": "pe-2",
                    "shapeType": "ActionView",
                    "elementId": "el-2",
                    "elementType": "OpaqueAction",
                    "bounds": {"x": 20, "y": 0, "width": 10, "height": 10},
                },
                {
                    "presentationId": "pe-3",
                    "shapeType": "ControlFlowView",
                    "elementId": "el-3",
                    "elementType": "ControlFlow",
                    "parentPresentationId": "pe-1",
                },
            ],
        }

        with patch("cameo_mcp.client._request", new=AsyncMock(return_value=payload)):
            result = await client.list_diagram_shapes(
                "dia-1",
                limit=1,
                offset=1,
                element_type="OpaqueAction",
                include_bounds=False,
                include_child_count=False,
            )

        self.assertEqual(2, result["totalCount"])
        self.assertEqual(["pe-2"], [shape["presentationId"] for shape in result["shapes"]])
        self.assertNotIn("bounds", result["shapes"][0])
        self.assertNotIn("childCount", result["shapes"][0])

    async def test_set_transition_label_presentation_builds_request_body(self) -> None:
        with patch("cameo_mcp.client._request", new=AsyncMock(return_value={"resultCount": 1})) as request:
            await client.set_transition_label_presentation(
                "dia-1",
                presentation_ids=["pe-1"],
                show_name=True,
                show_triggers=False,
                show_guard=True,
                show_effect=False,
                reset_labels=True,
            )

        request.assert_awaited_once()
        self.assertEqual(
            {
                "presentationIds": ["pe-1"],
                "showName": True,
                "showTriggers": False,
                "showGuard": True,
                "showEffect": False,
                "resetLabels": True,
            },
            request.await_args.kwargs["json_body"],
        )

    async def test_set_item_flow_label_presentation_builds_request_body(self) -> None:
        with patch("cameo_mcp.client._request", new=AsyncMock(return_value={"resultCount": 1})) as request:
            await client.set_item_flow_label_presentation(
                "dia-1",
                presentation_ids=["pe-1"],
                show_name=False,
                show_conveyed=True,
                show_item_property=False,
                show_direction=True,
                show_stereotype=True,
                reset_labels=False,
            )

        request.assert_awaited_once()
        self.assertEqual(
            {
                "presentationIds": ["pe-1"],
                "showName": False,
                "showConveyed": True,
                "showItemProperty": False,
                "showDirection": True,
                "showStereotype": True,
                "resetLabels": False,
            },
            request.await_args.kwargs["json_body"],
        )

    async def test_set_allocation_compartment_presentation_builds_request_body(self) -> None:
        with patch("cameo_mcp.client._request", new=AsyncMock(return_value={"resultCount": 1})) as request:
            await client.set_allocation_compartment_presentation(
                "dia-1",
                presentation_ids=["pe-1"],
                show_allocated_elements=True,
                show_element_properties=False,
                show_ports=True,
                show_full_ports=False,
                apply_allocation_naming=True,
            )

        request.assert_awaited_once()
        self.assertEqual(
            {
                "presentationIds": ["pe-1"],
                "showAllocatedElements": True,
                "showElementProperties": False,
                "showPorts": True,
                "showFullPorts": False,
                "applyAllocationNaming": True,
            },
            request.await_args.kwargs["json_body"],
        )

    async def test_repair_hidden_labels_builds_request_body(self) -> None:
        with patch("cameo_mcp.client._request", new=AsyncMock(return_value={"resultCount": 1})) as request:
            await client.repair_hidden_labels(
                "dia-1",
                presentation_ids=["pe-1"],
                dry_run=True,
            )

        request.assert_awaited_once()
        self.assertEqual(
            {
                "presentationIds": ["pe-1"],
                "dryRun": True,
            },
            request.await_args.kwargs["json_body"],
        )

    async def test_repair_label_positions_builds_request_body(self) -> None:
        with patch("cameo_mcp.client._request", new=AsyncMock(return_value={"resultCount": 1})) as request:
            await client.repair_label_positions(
                "dia-1",
                presentation_ids=["pe-1"],
                dry_run=False,
                only_overlapping=False,
                overlap_padding=24,
            )

        request.assert_awaited_once()
        self.assertEqual(
            {
                "presentationIds": ["pe-1"],
                "dryRun": False,
                "onlyOverlapping": False,
                "overlapPadding": 24,
            },
            request.await_args.kwargs["json_body"],
        )

    async def test_repair_conveyed_item_labels_builds_request_body(self) -> None:
        with patch("cameo_mcp.client._request", new=AsyncMock(return_value={"resultCount": 1})) as request:
            await client.repair_conveyed_item_labels(
                "dia-1",
                presentation_ids=["pe-1"],
                dry_run=True,
                reset_labels=False,
            )

        request.assert_awaited_once()
        self.assertEqual(
            {
                "presentationIds": ["pe-1"],
                "dryRun": True,
                "resetLabels": False,
            },
            request.await_args.kwargs["json_body"],
        )

    async def test_normalize_compartment_presets_builds_request_body(self) -> None:
        with patch("cameo_mcp.client._request", new=AsyncMock(return_value={"resultCount": 1})) as request:
            await client.normalize_compartment_presets(
                "dia-1",
                presentation_ids=["pe-1"],
                dry_run=True,
            )

        request.assert_awaited_once()
        self.assertEqual(
            {
                "presentationIds": ["pe-1"],
                "dryRun": True,
            },
            request.await_args.kwargs["json_body"],
        )

    async def test_prune_diagram_presentations_builds_request_body(self) -> None:
        with patch("cameo_mcp.client._request", new=AsyncMock(return_value={"deletedCount": 2})) as request:
            await client.prune_diagram_presentations(
                "dia-1",
                keep_element_ids=["el-1", "el-2"],
                drop_element_types=["Item Flow"],
                drop_shape_types=["ConnectorEndView"],
                exclude_element_ids=["el-safe"],
                exclude_presentation_ids=["pe-safe"],
                dry_run=True,
            )

        request.assert_awaited_once()
        self.assertEqual(
            {
                "dryRun": True,
                "keepElementIds": ["el-1", "el-2"],
                "dropElementTypes": ["Item Flow"],
                "dropShapeTypes": ["ConnectorEndView"],
                "excludeElementIds": ["el-safe"],
                "excludePresentationIds": ["pe-safe"],
            },
            request.await_args.kwargs["json_body"],
        )

    async def test_prune_path_decorations_builds_request_body(self) -> None:
        with patch("cameo_mcp.client._request", new=AsyncMock(return_value={"deletedDecorationCount": 2})) as request:
            await client.prune_path_decorations(
                "dia-1",
                presentation_ids=["pe-1"],
                drop_child_shape_types=["RoleView", "TextBoxView"],
                dry_run=True,
            )

        request.assert_awaited_once()
        self.assertEqual(
            {
                "presentationIds": ["pe-1"],
                "dropChildShapeTypes": ["RoleView", "TextBoxView"],
                "dryRun": True,
            },
            request.await_args.kwargs["json_body"],
        )

    async def test_run_native_validation_builds_request_body(self) -> None:
        with patch("cameo_mcp.client._request", new=AsyncMock(return_value={"runId": "run-1"})) as request:
            await client.run_native_validation(
                suite_id="suite-1",
                scope_element_ids=["pkg-1"],
                whole_project=False,
                recursive=False,
                exclude_read_only=False,
                minimum_severity="warning",
                open_native_window=True,
                name="Review gate",
            )

        request.assert_awaited_once()
        self.assertEqual("POST", request.await_args.args[0])
        self.assertEqual("/validation/run", request.await_args.args[1])
        self.assertEqual(
            {
                "suiteId": "suite-1",
                "scopeElementIds": ["pkg-1"],
                "wholeProject": False,
                "recursive": False,
                "excludeReadOnly": False,
                "minimumSeverity": "warning",
                "openNativeWindow": True,
                "name": "Review gate",
            },
            request.await_args.kwargs["json_body"],
        )

    async def test_validation_probe_and_result_paths(self) -> None:
        with patch("cameo_mcp.client._request", new=AsyncMock(return_value={"available": True})) as request:
            await client.get_validation_capabilities()
            await client.list_validation_suites()
            await client.get_validation_result("run-1")

        self.assertEqual(
            [
                ("GET", "/validation/capabilities"),
                ("GET", "/validation/suites"),
                ("GET", "/validation/results/run-1"),
            ],
            [tuple(call.args) for call in request.await_args_list],
        )

    async def test_probe_bridge_reports_preferred_paths(self) -> None:
        class _ProbeResponse:
            def __init__(self, status_code: int, payload: dict[str, Any]) -> None:
                self.status_code = status_code
                self._payload = payload
                self.content = b"{}"
                self.text = "{}"

            def json(self) -> dict[str, Any]:
                return self._payload

        class _ProbeClient:
            def __init__(self, *args, **kwargs) -> None:
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb) -> None:
                return None

            async def get(self, path: str) -> _ProbeResponse:
                payload = {
                    "pluginVersion": client.BRIDGE_PLUGIN_VERSION,
                    "apiVersion": client.BRIDGE_API_VERSION,
                    "handshakeVersion": client.BRIDGE_HANDSHAKE_VERSION,
                }
                return _ProbeResponse(200, payload)

        with patch("cameo_mcp.client.httpx.AsyncClient", _ProbeClient):
            result = await client.probe_bridge()

        self.assertTrue(result["reachable"])
        self.assertEqual("/status", result["preferredStatusPath"])
        self.assertEqual("/capabilities", result["preferredCapabilitiesPath"])
