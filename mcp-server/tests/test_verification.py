import base64
import io
import unittest

from PIL import Image, ImageDraw

from cameo_mcp.verification import (
    analyze_diagram_image,
    extract_activity_trace_terms,
    extract_ibd_trace_terms,
    verify_activity_flow_semantics,
    verify_cross_diagram_traceability,
    verify_diagram_visual,
    verify_matrix_consistency,
    verify_port_boundary_consistency,
    verify_requirement_quality,
)


def _png_payload(width: int = 100, height: int = 80) -> dict[str, object]:
    image = Image.new("RGBA", (width, height), "white")
    draw = ImageDraw.Draw(image)
    draw.rectangle((10, 10, 40, 40), fill="black")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return {
        "image": base64.b64encode(buffer.getvalue()).decode("ascii"),
        "width": width,
        "height": height,
    }


class DiagramVerificationTests(unittest.TestCase):
    def test_analyze_diagram_image_handles_invalid_base64(self) -> None:
        metrics = analyze_diagram_image({"image": "%%%not-base64%%%", "width": 10, "height": 10})

        self.assertEqual(0, metrics["byteCount"])
        self.assertFalse(metrics["pngSignatureOk"])
        self.assertEqual(0, metrics["imageWidth"])
        self.assertEqual(0, metrics["imageHeight"])

    def test_verify_diagram_visual_requires_real_relationship_paths(self) -> None:
        result = verify_diagram_visual(
            _png_payload(),
            {
                "shapes": [
                    {
                        "presentationId": "shape-1",
                        "elementId": "rel-1",
                        "shapeType": "PathLabelElement",
                        "elementType": "InformationFlow",
                    }
                ]
            },
            expected_relationship_ids=["rel-1"],
        )

        self.assertFalse(result["ok"])
        relationship_check = next(
            check for check in result["checks"]
            if check["name"] == "expected-relationships-present"
        )
        self.assertFalse(relationship_check["ok"])
        self.assertEqual(["rel-1"], relationship_check["details"]["missing"])

    def test_verify_diagram_visual_reports_overlap_and_content_metrics(self) -> None:
        result = verify_diagram_visual(
            _png_payload(),
            {
                "shapes": [
                    {
                        "presentationId": "shape-a",
                        "elementId": "part-a",
                        "shapeType": "ShapeElement",
                        "elementType": "Property",
                        "parentPresentationId": None,
                        "bounds": {"x": 10, "y": 10, "width": 80, "height": 60},
                    },
                    {
                        "presentationId": "shape-b",
                        "elementId": "part-b",
                        "shapeType": "ShapeElement",
                        "elementType": "Property",
                        "parentPresentationId": None,
                        "bounds": {"x": 20, "y": 15, "width": 80, "height": 60},
                    },
                    {
                        "presentationId": "path-1",
                        "elementId": "connector-1",
                        "shapeType": "ConnectorPathElement",
                        "elementType": "Connector",
                    },
                ]
            },
            expected_element_ids=["part-a", "part-b"],
            expected_relationship_ids=["connector-1"],
            min_shape_count=3,
            min_relationship_shape_count=1,
            min_width=100,
            min_height=80,
            min_image_bytes=100,
            min_content_coverage_ratio=0.05,
            max_overlap_ratio=0.2,
        )

        self.assertFalse(result["ok"])
        self.assertGreater(result["image"]["contentCoverageRatio"], 0.05)
        self.assertEqual(["connector-1"], result["shapes"]["relationshipElementIds"])
        overlap_check = next(check for check in result["checks"] if check["name"] == "shape-overlap")
        self.assertFalse(overlap_check["ok"])

    def test_verify_diagram_visual_checks_reported_dimensions(self) -> None:
        payload = _png_payload(width=100, height=80)
        payload["width"] = 90

        result = verify_diagram_visual(
            payload,
            {"shapes": []},
        )

        self.assertFalse(result["ok"])
        dimension_check = next(
            check for check in result["checks"]
            if check["name"] == "reported-image-dimensions"
        )
        self.assertFalse(dimension_check["ok"])


class MatrixVerificationTests(unittest.TestCase):
    def test_verify_matrix_consistency_reads_dependencies_and_density(self) -> None:
        result = verify_matrix_consistency(
            {
                "rowCount": 2,
                "columnCount": 2,
                "rows": [{"id": "row-1"}, {"id": "row-2"}],
                "columns": [{"id": "col-1"}, {"id": "col-2"}],
                "populatedCellCount": 1,
                "populatedCells": [
                    {
                        "rowId": "row-1",
                        "columnId": "col-1",
                        "dependencies": [{"name": "Refine"}],
                    }
                ],
            },
            expected_row_ids=["row-1"],
            expected_column_ids=["col-1"],
            expected_dependency_names=["Refine"],
            min_populated_cell_count=1,
            min_density=0.25,
        )

        self.assertTrue(result["ok"])
        self.assertEqual(0.25, result["metrics"]["density"])
        self.assertEqual(["Refine"], result["metrics"]["dependencyNames"])

    def test_verify_matrix_consistency_accepts_legacy_dependency_name_field(self) -> None:
        result = verify_matrix_consistency(
            {
                "rows": [{"id": "row-1"}],
                "columns": [{"id": "col-1"}],
                "populatedCells": [
                    {
                        "dependencies": [{"dependencyName": "DeriveReqt"}],
                    }
                ],
            },
            expected_dependency_names=["DeriveReqt"],
            min_populated_cell_count=1,
            min_density=1.0,
        )

        self.assertTrue(result["ok"])
        self.assertEqual(["DeriveReqt"], result["metrics"]["dependencyNames"])

    def test_verify_matrix_consistency_flags_payload_count_mismatch(self) -> None:
        result = verify_matrix_consistency(
            {
                "rowCount": 3,
                "columnCount": 1,
                "populatedCellCount": 2,
                "rows": [{"id": "row-1"}],
                "columns": [{"id": "col-1"}],
                "populatedCells": [{"dependencies": []}],
            },
        )

        self.assertFalse(result["ok"])
        count_check = next(
            check for check in result["checks"]
            if check["name"] == "payload-counts-consistent"
        )
        self.assertFalse(count_check["ok"])


class ActivityFlowVerificationTests(unittest.TestCase):
    def test_verify_activity_flow_semantics_flags_islands_and_partition_smells(self) -> None:
        result = verify_activity_flow_semantics(
            [
                {"id": "n1", "type": "InitialNode", "name": "Start"},
                {"id": "a1", "type": "OpaqueAction", "name": "Query Available Slots"},
                {"id": "a2", "type": "OpaqueAction", "name": "Display Available Slots"},
                {"id": "f1", "type": "ActivityFinalNode", "name": "Done"},
                {"id": "a3", "type": "OpaqueAction", "name": "Send Confirmation"},
                {"id": "p1", "type": "ActivityPartition", "name": "«allocate»"},
                {"id": "p2", "type": "ActivityPartition", "name": "Scheduling System"},
            ],
            [
                {
                    "relationshipId": "r1",
                    "type": "ControlFlow",
                    "sources": [{"id": "n1"}],
                    "targets": [{"id": "a1"}],
                },
                {
                    "relationshipId": "r2",
                    "type": "ControlFlow",
                    "sources": [{"id": "a1"}],
                    "targets": [{"id": "a2"}],
                },
                {
                    "relationshipId": "r3",
                    "type": "ControlFlow",
                    "sources": [{"id": "a2"}],
                    "targets": [{"id": "f1"}],
                },
            ],
            shapes=[
                {
                    "presentationId": "pe-p1",
                    "elementId": "p1",
                    "elementType": "ActivityPartition",
                },
                {
                    "presentationId": "pe-p2",
                    "parentPresentationId": "pe-p1",
                    "elementId": "p2",
                    "elementType": "ActivityPartition",
                },
                {
                    "presentationId": "pe-a1",
                    "parentPresentationId": "pe-p2",
                    "elementId": "a1",
                    "elementType": "OpaqueAction",
                },
                {
                    "presentationId": "pe-a2",
                    "parentPresentationId": "pe-p2",
                    "elementId": "a2",
                    "elementType": "OpaqueAction",
                },
                {
                    "presentationId": "pe-a3",
                    "parentPresentationId": "pe-p2",
                    "elementId": "a3",
                    "elementType": "OpaqueAction",
                },
            ],
        )

        self.assertFalse(result["ok"])
        self.assertIn("a3", result["metrics"]["isolatedActionIds"])
        self.assertIn("a3", result["metrics"]["unreachableActionIds"])
        partition_check = next(check for check in result["checks"] if check["name"] == "partition-sanity")
        self.assertFalse(partition_check["ok"])

    def test_verify_activity_flow_semantics_accepts_connected_flow(self) -> None:
        result = verify_activity_flow_semantics(
            [
                {"id": "n1", "type": "InitialNode"},
                {"id": "a1", "type": "OpaqueAction", "name": "Select Provider and Service"},
                {"id": "a2", "type": "OpaqueAction", "name": "Select Time Slot"},
                {"id": "f1", "type": "ActivityFinalNode"},
            ],
            [
                {
                    "relationshipId": "r1",
                    "type": "ControlFlow",
                    "sources": [{"id": "n1"}],
                    "targets": [{"id": "a1"}],
                },
                {
                    "relationshipId": "r2",
                    "type": "ControlFlow",
                    "sources": [{"id": "a1"}],
                    "targets": [{"id": "a2"}],
                },
                {
                    "relationshipId": "r3",
                    "type": "ControlFlow",
                    "sources": [{"id": "a2"}],
                    "targets": [{"id": "f1"}],
                },
            ],
        )

        self.assertTrue(result["ok"])


class PortBoundaryVerificationTests(unittest.TestCase):
    def test_verify_port_boundary_consistency_scopes_direction_conflicts_to_owner(self) -> None:
        result = verify_port_boundary_consistency(
            [
                {"id": "if-1", "name": "Customer UI Port Type"},
                {"id": "if-2", "name": "Scheduling System Port Type"},
            ],
            [
                {"id": "fp-1", "name": "Available Slots", "ownerId": "if-1", "direction": "out"},
                {"id": "fp-2", "name": "Available Slots", "ownerId": "if-1", "direction": "in"},
                {"id": "fp-3", "name": "Available Slots", "ownerId": "if-2", "direction": "in"},
            ],
            allow_shared_flow_property_names=["Available Slots"],
        )

        self.assertFalse(result["ok"])
        self.assertNotIn("available slots", result["metrics"]["duplicateFlowProperties"])
        self.assertIn("Customer UI Port Type", result["metrics"]["directionConflicts"])
        self.assertIn("available slots", result["metrics"]["directionConflicts"]["Customer UI Port Type"])
        self.assertNotIn("Scheduling System Port Type", result["metrics"]["directionConflicts"])


class RequirementQualityVerificationTests(unittest.TestCase):
    def test_verify_requirement_quality_flags_blank_and_weak_requirements(self) -> None:
        result = verify_requirement_quality(
            [
                {
                    "id": "req-1",
                    "name": "Appointment Response Time",
                    "appliedStereotypes": [{"stereotype": "Requirement", "taggedValues": {"id": "REQ-1", "text": ""}}],
                },
                {
                    "id": "req-2",
                    "name": "System Availability",
                    "appliedStereotypes": [{"stereotype": "Requirement", "taggedValues": {"id": "", "text": "The system shall be easy to use."}}],
                },
                {
                    "id": "req-3",
                    "name": "Confirmation",
                    "documentation": "The system shall send confirmation within 5 seconds of booking.",
                },
            ],
        )

        self.assertFalse(result["ok"])
        self.assertIn("req-1", result["metrics"]["blankTextIds"])
        self.assertIn("req-2", result["metrics"]["missingIdIds"])
        self.assertIn("req-2", result["metrics"]["weakTextIds"])
        req3 = next(item for item in result["metrics"]["evaluatedRequirements"] if item["elementId"] == "req-3")
        self.assertTrue(req3["isMeasurable"])


class CrossDiagramTraceabilityVerificationTests(unittest.TestCase):
    def test_verify_cross_diagram_traceability_flags_missing_matches(self) -> None:
        result = verify_cross_diagram_traceability(
            activity_terms=[
                "Query Available Slots",
                "Display Available Slots",
                "Select Provider and Service",
            ],
            port_terms=["Available Slots", "Appointment Record"],
            ibd_terms=["Available Slots", "Provider Selection"],
            requirement_links={"req-1": ["blk-1"], "req-2": []},
            requirement_ids=["req-1", "req-2"],
            architecture_element_ids=["blk-1"],
        )

        self.assertFalse(result["ok"])
        self.assertIn("Appointment Record", result["metrics"]["missingPortTerms"])
        self.assertIn("req-2", result["metrics"]["missingRequirementTraceIds"])

    def test_verify_cross_diagram_traceability_rejects_single_token_overlap_false_positive(self) -> None:
        result = verify_cross_diagram_traceability(
            activity_terms=["AAS System Status"],
            port_terms=["System"],
            ibd_terms=["System"],
        )

        self.assertFalse(result["ok"])
        self.assertIn("System", result["metrics"]["missingPortTerms"])
        self.assertIn("System", result["metrics"]["missingIbdTerms"])

    def test_extract_trace_terms_include_flow_labels(self) -> None:
        activity_terms = extract_activity_trace_terms(
            [
                {"id": "a1", "type": "OpaqueAction", "name": "Display Available Slots"},
                {"id": "o1", "type": "ObjectNode", "name": "Available Slots"},
            ],
            [
                {
                    "relationshipId": "r1",
                    "type": "ObjectFlow",
                    "itemProperty": {"id": "p1", "name": "Available Slots"},
                    "conveyed": [{"id": "blk-1", "name": "Appointment Record"}],
                }
            ],
        )
        ibd_terms = extract_ibd_trace_terms(
            [{"id": "p1", "type": "Port", "name": "Customer UI"}],
            [
                {
                    "relationshipId": "r2",
                    "type": "ItemFlow",
                    "name": "Availability Query",
                    "conveyed": [{"id": "blk-2", "name": "Available Slots"}],
                }
            ],
        )

        self.assertIn("Available Slots", activity_terms)
        self.assertIn("Appointment Record", activity_terms)
        self.assertIn("Availability Query", ibd_terms)


if __name__ == "__main__":
    unittest.main()
