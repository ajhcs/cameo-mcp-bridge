import base64
import tempfile
import unittest
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from cameo_mcp.methodology_workflows import (
    assemble_ppt_pdf_live,
    compare_against_expected_artifact_list,
    export_required_diagrams_live,
    validate_methodology_package,
)


def _make_base64_png(width: int = 20, height: int = 10) -> str:
    image = Image.new("RGBA", (width, height), (0, 128, 255, 255))
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("ascii")


class FakeMethodologyBridge:
    async def get_diagram_image(self, diagram_id: str, **kwargs):
        return {
            "id": diagram_id,
            "name": "Logical IBD",
            "format": kwargs.get("format", "png"),
            "width": 20,
            "height": 10,
            "image": _make_base64_png(),
        }


class MethodologyWorkflowTests(unittest.TestCase):
    def test_compare_against_expected_artifact_list_returns_patch_plan(self) -> None:
        result = compare_against_expected_artifact_list(
            expected_artifacts=[
                {"key": "workspace", "kind": "Package", "name": "Workspace"},
                {"key": "logical_ibd", "kind": "ibd", "name": "Logical IBD"},
            ],
            current_artifacts=[
                {"key": "workspace", "kind": "Package", "name": "Workspace", "element_id": "pkg-1"},
            ],
        )

        self.assertFalse(result["ready"])
        self.assertEqual(["logical_ibd"], result["missingArtifactKeys"])
        self.assertGreater(len(result["patchPlan"]), 0)

    def test_validate_methodology_package_uses_custom_expected_artifacts(self) -> None:
        result = validate_methodology_package(
            "oosem",
            current_artifacts=[
                {"key": "workspace", "kind": "Package", "name": "Workspace", "element_id": "pkg-1"},
            ],
            expected_artifacts=[
                {"key": "workspace", "kind": "Package", "name": "Workspace"},
                {"key": "logical_ibd", "kind": "ibd", "name": "Logical IBD"},
            ],
        )

        self.assertFalse(result["ready"])
        self.assertIn("artifactComparison", result)
        self.assertIn("recommendedActions", result)


class MethodologyWorkflowLiveTests(unittest.IsolatedAsyncioTestCase):
    async def test_export_required_diagrams_live_writes_images(self) -> None:
        bridge = FakeMethodologyBridge()
        with tempfile.TemporaryDirectory() as tmp_dir:
            result = await export_required_diagrams_live(
                "oosem",
                current_artifacts=[
                    {"key": "logical_ibd", "kind": "ibd", "name": "Logical IBD", "element_id": "dia-1"},
                ],
                expected_artifacts=[
                    {"key": "logical_ibd", "kind": "ibd", "name": "Logical IBD"},
                ],
                output_dir=tmp_dir,
                bridge=bridge,
            )

            self.assertFalse(result["dryRun"])
            self.assertEqual(1, result["exportedCount"])
            export_path = Path(result["exports"][0]["outputFile"])
            self.assertTrue(export_path.exists())
            self.assertGreater(export_path.stat().st_size, 0)

    async def test_assemble_ppt_pdf_live_creates_files(self) -> None:
        bridge = FakeMethodologyBridge()
        with tempfile.TemporaryDirectory() as tmp_dir:
            def _fake_write_pptx(image_paths, output_path, *, title):
                Path(output_path).write_bytes(b"pptx")

            with patch("cameo_mcp.methodology_workflows._write_pptx", _fake_write_pptx):
                result = await assemble_ppt_pdf_live(
                    "oosem",
                    current_artifacts=[
                        {"key": "logical_ibd", "kind": "ibd", "name": "Logical IBD", "element_id": "dia-1"},
                    ],
                    expected_artifacts=[
                        {"key": "logical_ibd", "kind": "ibd", "name": "Logical IBD"},
                    ],
                    output_dir=tmp_dir,
                    title="Demo Deck",
                    bridge=bridge,
                )

            self.assertFalse(result["dryRun"])
            created = {item["kind"]: Path(item["path"]) for item in result["createdFiles"]}
            self.assertTrue(created["pdf"].exists())
            self.assertTrue(created["pptx"].exists())


if __name__ == "__main__":
    unittest.main()
