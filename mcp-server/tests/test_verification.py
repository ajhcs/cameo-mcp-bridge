import base64
import io
import unittest

from PIL import Image, ImageDraw

from cameo_mcp.verification import (
    analyze_diagram_image,
    verify_diagram_visual,
    verify_matrix_consistency,
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


if __name__ == "__main__":
    unittest.main()
