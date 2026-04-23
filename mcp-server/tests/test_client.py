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
