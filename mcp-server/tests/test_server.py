import base64
import unittest
from io import BytesIO
from unittest.mock import AsyncMock, patch

from PIL import Image

from cameo_mcp.server import (
    _mcp_result,
    cameo_get_capabilities,
    cameo_get_diagram_image,
    cameo_list_diagram_types,
    cameo_list_diagram_shapes,
    cameo_list_matrix_kinds,
    cameo_list_methodology_packs,
    cameo_get_state_behaviors,
    cameo_get_transition_triggers,
    mcp,
    cameo_set_state_behaviors,
    cameo_set_transition_trigger,
    cameo_verify_activity_flow_semantics,
    cameo_verify_cross_diagram_traceability,
    cameo_verify_diagram_visual,
    cameo_verify_matrix_consistency,
    cameo_verify_port_boundary_consistency,
    cameo_verify_requirement_quality,
)


def _make_base64_png(width: int = 20, height: int = 10) -> str:
    image = Image.new("RGBA", (width, height), (255, 0, 0, 255))
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("ascii")


class McpResultTests(unittest.TestCase):
    def test_mcp_result_returns_dict_by_default(self) -> None:
        payload = {"status": "ok", "port": 18740}

        result = _mcp_result(payload)

        self.assertIs(result, payload)


class ToolSchemaAliasTests(unittest.TestCase):
    def test_cameo_get_diagram_image_accepts_camel_case_diagram_id(self) -> None:
        tool = mcp._tool_manager.get_tool("cameo_get_diagram_image")

        validated = tool.fn_metadata.arg_model.model_validate({"diagramId": "dia-1"})

        self.assertEqual("dia-1", validated.diagram_id)

    def test_cameo_get_relationships_accepts_camel_case_element_id(self) -> None:
        tool = mcp._tool_manager.get_tool("cameo_get_relationships")

        validated = tool.fn_metadata.arg_model.model_validate({"elementId": "el-1"})

        self.assertEqual("el-1", validated.element_id)

    def test_cameo_add_to_diagram_accepts_camel_case_ids(self) -> None:
        tool = mcp._tool_manager.get_tool("cameo_add_to_diagram")

        validated = tool.fn_metadata.arg_model.model_validate(
            {"diagramId": "dia-1", "elementId": "el-1", "containerPresentationId": "pe-1"}
        )

        self.assertEqual("dia-1", validated.diagram_id)
        self.assertEqual("el-1", validated.element_id)
        self.assertEqual("pe-1", validated.container_presentation_id)

    def test_cameo_list_containment_children_accepts_parent_id_alias(self) -> None:
        tool = mcp._tool_manager.get_tool("cameo_list_containment_children")

        validated = tool.fn_metadata.arg_model.model_validate({"parentId": "pkg-1"})

        self.assertEqual("pkg-1", validated.root_id)

    def test_cameo_query_elements_accepts_owner_id_alias(self) -> None:
        tool = mcp._tool_manager.get_tool("cameo_query_elements")

        validated = tool.fn_metadata.arg_model.model_validate({"ownerId": "pkg-1"})

        self.assertEqual("pkg-1", validated.package_id)


class ServerToolTests(unittest.IsolatedAsyncioTestCase):
    async def test_cameo_get_capabilities_returns_native_dict(self) -> None:
        payload = {"pluginVersion": "2.1.0", "compatibility": {"clientCompatible": True}}

        with patch(
            "cameo_mcp.server.client.get_capabilities",
            new=AsyncMock(return_value=payload),
        ) as get_capabilities:
            result = await cameo_get_capabilities()

        self.assertIs(result, payload)
        get_capabilities.assert_awaited_once_with()

    async def test_cameo_list_methodology_packs_returns_native_dict(self) -> None:
        payload = {"count": 1, "packs": [{"id": "oosem"}]}

        with patch(
            "cameo_mcp.server.list_methodology_packs",
            return_value=payload,
        ) as list_packs:
            result = await cameo_list_methodology_packs()

        self.assertIs(result, payload)
        list_packs.assert_called_once_with()

    async def test_cameo_list_diagram_types_returns_validated_metadata(self) -> None:
        result = await cameo_list_diagram_types()

        self.assertEqual(len(result["diagramTypes"]), result["count"])
        self.assertGreater(result["count"], 0)

    async def test_cameo_list_matrix_kinds_returns_validated_metadata(self) -> None:
        result = await cameo_list_matrix_kinds()

        self.assertEqual(len(result["matrixKinds"]), result["count"])
        self.assertGreater(result["count"], 0)

    async def test_cameo_get_diagram_image_can_omit_base64_payload(self) -> None:
        payload = {
            "id": "dia-1",
            "name": "Demo",
            "format": "png",
            "width": 20,
            "height": 10,
            "image": _make_base64_png(20, 10),
        }

        with patch(
            "cameo_mcp.server.client.get_diagram_image",
            new=AsyncMock(return_value=payload),
        ) as get_diagram_image:
            result = await cameo_get_diagram_image("dia-1", include_image=False)

        self.assertEqual("dia-1", result["id"])
        self.assertTrue(result["imageOmitted"])
        self.assertNotIn("image", result)
        self.assertGreater(result["imageBytes"], 0)
        get_diagram_image.assert_awaited_once_with("dia-1")

    async def test_cameo_get_diagram_image_can_resize_and_transcode(self) -> None:
        payload = {
            "id": "dia-1",
            "name": "Demo",
            "format": "png",
            "width": 20,
            "height": 10,
            "image": _make_base64_png(20, 10),
        }

        with patch(
            "cameo_mcp.server.client.get_diagram_image",
            new=AsyncMock(return_value=payload),
        ):
            result = await cameo_get_diagram_image(
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

    async def test_cameo_list_diagram_shapes_can_filter_and_page(self) -> None:
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

        with patch(
            "cameo_mcp.server.client.list_diagram_shapes",
            new=AsyncMock(return_value=payload),
        ) as list_diagram_shapes:
            result = await cameo_list_diagram_shapes(
                "dia-1",
                limit=1,
                offset=1,
                element_type="OpaqueAction",
                include_bounds=False,
                include_child_count=False,
            )

        self.assertEqual(2, result["totalCount"])
        self.assertFalse(result["hasMore"])
        self.assertNotIn("nextOffset", result)
        self.assertEqual(["pe-2"], [shape["presentationId"] for shape in result["shapes"]])
        self.assertNotIn("bounds", result["shapes"][0])
        self.assertNotIn("childCount", result["shapes"][0])
        list_diagram_shapes.assert_awaited_once_with("dia-1")

    async def test_cameo_list_diagram_shapes_can_return_summary_only(self) -> None:
        payload = {
            "diagramId": "dia-1",
            "shapeCount": 3,
            "shapes": [
                {"presentationId": "pe-1", "shapeType": "ActionView", "elementType": "OpaqueAction"},
                {"presentationId": "pe-2", "shapeType": "ActionView", "elementType": "OpaqueAction"},
                {
                    "presentationId": "pe-3",
                    "shapeType": "ControlFlowView",
                    "elementType": "ControlFlow",
                    "parentPresentationId": "pe-1",
                },
            ],
        }

        with patch(
            "cameo_mcp.server.client.list_diagram_shapes",
            new=AsyncMock(return_value=payload),
        ):
            result = await cameo_list_diagram_shapes("dia-1", summary_only=True)

        self.assertEqual(3, result["totalCount"])
        self.assertNotIn("shapes", result)
        self.assertEqual({"ActionView": 2, "ControlFlowView": 1}, result["shapeTypeCounts"])
        self.assertEqual({"OpaqueAction": 2, "ControlFlow": 1}, result["elementTypeCounts"])
        self.assertEqual(1, result["parentedShapeCount"])

    async def test_cameo_verify_diagram_visual_wraps_client_and_helper(self) -> None:
        diagram_image = {"image": "abc", "width": 100, "height": 50}
        diagram_shapes = {"shapeCount": 2, "shapes": []}
        payload = {"ok": True, "checks": []}

        with patch(
            "cameo_mcp.server.client.get_diagram_image",
            new=AsyncMock(return_value=diagram_image),
        ) as get_diagram_image, patch(
            "cameo_mcp.server.client.list_diagram_shapes",
            new=AsyncMock(return_value=diagram_shapes),
        ) as list_diagram_shapes, patch(
            "cameo_mcp.server.verification.verify_diagram_visual",
            return_value=payload.copy(),
        ) as verify_diagram_visual:
            result = await cameo_verify_diagram_visual(
                "dia-1",
                expected_element_ids=["el-1"],
                expected_relationship_ids=["rel-1"],
                min_shape_count=2,
                min_relationship_shape_count=1,
                min_width=100,
                min_height=50,
                min_image_bytes=128,
                min_content_coverage_ratio=0.05,
                max_overlap_ratio=0.2,
            )

        self.assertTrue(result["ok"])
        self.assertIs(result["diagramImage"], diagram_image)
        self.assertIs(result["diagramShapes"], diagram_shapes)
        get_diagram_image.assert_awaited_once_with("dia-1")
        list_diagram_shapes.assert_awaited_once_with("dia-1")
        verify_diagram_visual.assert_called_once_with(
            diagram_image,
            diagram_shapes,
            expected_element_ids=["el-1"],
            expected_relationship_ids=["rel-1"],
            min_shape_count=2,
            min_relationship_shape_count=1,
            min_width=100,
            min_height=50,
            min_image_bytes=128,
            min_content_coverage_ratio=0.05,
            max_overlap_ratio=0.2,
        )

    async def test_cameo_verify_matrix_consistency_wraps_client_and_helper(self) -> None:
        matrix = {"id": "matrix-1", "rows": [], "columns": [], "populatedCells": []}
        payload = {"ok": True, "checks": []}

        with patch(
            "cameo_mcp.server.client.get_matrix",
            new=AsyncMock(return_value=matrix),
        ) as get_matrix, patch(
            "cameo_mcp.server.verification.verify_matrix_consistency",
            return_value=payload.copy(),
        ) as verify_matrix_consistency:
            result = await cameo_verify_matrix_consistency(
                "matrix-1",
                expected_row_ids=["row-1"],
                expected_column_ids=["col-1"],
                expected_dependency_names=["Refine"],
                min_populated_cell_count=1,
                min_density=0.25,
            )

        self.assertTrue(result["ok"])
        self.assertIs(result["matrix"], matrix)
        get_matrix.assert_awaited_once_with("matrix-1")
        verify_matrix_consistency.assert_called_once_with(
            matrix,
            expected_row_ids=["row-1"],
            expected_column_ids=["col-1"],
            expected_dependency_names=["Refine"],
            min_populated_cell_count=1,
            min_density=0.25,
        )

    async def test_cameo_verify_activity_flow_semantics_wraps_helper(self) -> None:
        payload = {"ok": True, "checks": []}

        with patch(
            "cameo_mcp.server.verify_activity_flow_semantics_for_diagram",
            new=AsyncMock(return_value=payload),
        ) as helper:
            result = await cameo_verify_activity_flow_semantics(
                "dia-1",
                max_partition_depth=2,
                allow_stereotype_partition_labels=True,
            )

        self.assertIs(result, payload)
        helper.assert_awaited_once_with(
            "dia-1",
            max_partition_depth=2,
            allow_stereotype_partition_labels=True,
        )

    async def test_cameo_verify_port_boundary_consistency_wraps_helper(self) -> None:
        payload = {"ok": True, "checks": []}

        with patch(
            "cameo_mcp.server.verify_port_boundary_consistency_for_interfaces",
            new=AsyncMock(return_value=payload),
        ) as helper:
            result = await cameo_verify_port_boundary_consistency(
                ["if-1", "if-2"],
                allow_shared_flow_property_names=["Heartbeat"],
            )

        self.assertIs(result, payload)
        helper.assert_awaited_once_with(
            ["if-1", "if-2"],
            allow_shared_flow_property_names=["Heartbeat"],
        )

    async def test_cameo_verify_requirement_quality_wraps_helper(self) -> None:
        payload = {"ok": True, "checks": []}

        with patch(
            "cameo_mcp.server.verify_requirement_quality_for_ids",
            new=AsyncMock(return_value=payload),
        ) as helper:
            result = await cameo_verify_requirement_quality(
                ["req-1"],
                require_id=False,
                require_measurement=False,
                min_text_length=10,
            )

        self.assertIs(result, payload)
        helper.assert_awaited_once_with(
            ["req-1"],
            require_id=False,
            require_measurement=False,
            min_text_length=10,
        )

    async def test_cameo_verify_cross_diagram_traceability_wraps_helper(self) -> None:
        payload = {"ok": True, "checks": []}

        with patch(
            "cameo_mcp.server.run_cross_diagram_traceability",
            new=AsyncMock(return_value=payload),
        ) as helper:
            result = await cameo_verify_cross_diagram_traceability(
                activity_diagram_id="act-1",
                interface_block_ids=["if-1"],
                ibd_diagram_id="ibd-1",
                requirement_ids=["req-1"],
                architecture_element_ids=["blk-1"],
            )

        self.assertIs(result, payload)
        helper.assert_awaited_once_with(
            activity_diagram_id="act-1",
            interface_block_ids=["if-1"],
            ibd_diagram_id="ibd-1",
            requirement_ids=["req-1"],
            architecture_element_ids=["blk-1"],
        )

    async def test_cameo_get_transition_triggers_wraps_helper(self) -> None:
        payload = {"transitionId": "tr-1", "triggerCount": 1, "triggers": []}

        with patch(
            "cameo_mcp.server.get_transition_triggers",
            new=AsyncMock(return_value=payload),
        ) as helper:
            result = await cameo_get_transition_triggers("tr-1")

        self.assertIs(result, payload)
        helper.assert_awaited_once_with("tr-1")

    async def test_cameo_set_transition_trigger_wraps_helper(self) -> None:
        payload = {"transitionId": "tr-1", "triggerCount": 1, "triggers": []}

        with patch(
            "cameo_mcp.server.set_transition_trigger",
            new=AsyncMock(return_value=payload),
        ) as helper:
            result = await cameo_set_transition_trigger(
                "tr-1",
                trigger_kind="change",
                expression="when ticket is inserted",
                name="TicketInserted",
                replace=False,
            )

        self.assertIs(result, payload)
        helper.assert_awaited_once_with(
            "tr-1",
            trigger_kind="change",
            expression="when ticket is inserted",
            signal_id=None,
            name="TicketInserted",
            replace=False,
        )

    async def test_cameo_get_state_behaviors_wraps_helper(self) -> None:
        payload = {"stateId": "st-1", "entry": None, "doActivity": None, "exit": None}

        with patch(
            "cameo_mcp.server.get_state_behaviors",
            new=AsyncMock(return_value=payload),
        ) as helper:
            result = await cameo_get_state_behaviors("st-1")

        self.assertIs(result, payload)
        helper.assert_awaited_once_with("st-1")

    async def test_cameo_set_state_behaviors_wraps_helper(self) -> None:
        payload = {"stateId": "st-1", "entry": None, "doActivity": None, "exit": None}

        with patch(
            "cameo_mcp.server.set_state_behaviors",
            new=AsyncMock(return_value=payload),
        ) as helper:
            result = await cameo_set_state_behaviors(
                "st-1",
                entry="initialize reader",
                do_activity="wait for card",
                exit_behavior="clear display",
                language="StructuredText",
                clear_unspecified=True,
            )

        self.assertIs(result, payload)
        helper.assert_awaited_once_with(
            "st-1",
            entry="initialize reader",
            do_activity="wait for card",
            exit_behavior="clear display",
            language="StructuredText",
            clear_unspecified=True,
        )


if __name__ == "__main__":
    unittest.main()
