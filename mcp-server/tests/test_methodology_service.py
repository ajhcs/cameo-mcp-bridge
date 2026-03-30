import unittest

from cameo_mcp.methodology.service import (
    execute_methodology_recipe,
    generate_review_packet,
    get_workflow_guidance,
    list_methodology_packs,
    validate_methodology_recipe,
)


class FakeBridge:
    def __init__(self) -> None:
        self.counter = 0

    async def create_element(self, **kwargs):
        self.counter += 1
        return {"id": f"el-{self.counter}", "name": kwargs.get("name")}

    async def create_relationship(self, **kwargs):
        self.counter += 1
        return {"id": f"rel-{self.counter}", "name": kwargs.get("name")}

    async def create_diagram(self, **kwargs):
        self.counter += 1
        return {"id": f"dia-{self.counter}", "name": kwargs.get("name")}

    async def add_to_diagram(self, **kwargs):
        self.counter += 1
        return {"presentationId": f"pe-{self.counter}", "diagramId": kwargs.get("diagram_id")}

    async def add_diagram_paths(self, **kwargs):
        self.counter += 1
        return {"results": [{"presentationId": f"path-{self.counter}"}]}

    async def set_shape_compartments(self, **kwargs):
        return {"updated": True}

    async def route_paths(self, **kwargs):
        return {"updated": True}

    async def set_usecase_subject(self, **kwargs):
        return {"updated": True}

    async def list_diagrams(self, **kwargs):
        return {"diagrams": []}

    async def query_elements(self, **kwargs):
        return {"elements": []}

    async def get_element(self, element_id, **kwargs):
        return {"id": element_id, "name": element_id, "humanType": "Class", "ownerId": "root-1"}

    async def get_specification(self, element_id, **kwargs):
        return {"elementId": element_id, "properties": {}}

    async def get_relationships(self, element_id, **kwargs):
        return {"elementId": element_id, "outgoing": [], "incoming": [], "totalCount": 0}

    async def get_diagram_image(self, diagram_id, **kwargs):
        return {"id": diagram_id, "format": "png", "width": 10, "height": 10, "image": "stub"}


class MethodologyServiceTests(unittest.IsolatedAsyncioTestCase):
    def test_list_methodology_packs_returns_oosem(self) -> None:
        result = list_methodology_packs()

        self.assertGreaterEqual(result["count"], 2)
        self.assertEqual("oosem", result["packs"][0]["id"])
        self.assertIn("uaf", {pack["id"] for pack in result["packs"]})

    def test_guidance_reports_missing_artifacts(self) -> None:
        result = get_workflow_guidance(
            pack_id="oosem",
            recipe_id="stakeholder_needs_package",
            recipe_parameters={"subject_name": "ATM", "root_package_id": "root-1"},
            completed_artifacts=[{"key": "workspace", "kind": "Package", "name": "Workspace", "element_id": "root-1"}],
        )

        guidance = result["guidance"]
        self.assertEqual("stakeholder_needs_package", guidance["recipe_id"])
        self.assertIn("stakeholder_needs_package", guidance["missing_artifact_keys"])

    async def test_execute_methodology_recipe_returns_evidence_bundle(self) -> None:
        result = await execute_methodology_recipe(
            pack_id="oosem",
            recipe_id="use_case_model",
            root_package_id="root-1",
            recipe_parameters={
                "root_package_id": "root-1",
                "subject_name": "ATM",
                "actor_names": ["Customer"],
                "use_case_names": ["Withdraw Cash"],
            },
            bridge=FakeBridge(),
        )

        self.assertEqual("oosem", result["pack"]["id"])
        self.assertIn("executionResult", result)
        self.assertIn("evidenceBundle", result)
        self.assertIn("# OOSEM Viewpoint Pack Review Packet", result["reviewPacketMarkdown"])

    async def test_validate_and_review_packet_are_non_mutating(self) -> None:
        artifacts = [
            {
                "key": "workspace",
                "kind": "Package",
                "name": "Workspace",
                "element_id": "root-1",
            }
        ]

        validation = await validate_methodology_recipe(
            pack_id="oosem",
            recipe_id="system_requirements_package",
            recipe_parameters={"root_package_id": "root-1", "system_name": "ATM"},
            current_artifacts=artifacts,
            bridge=FakeBridge(),
        )
        packet = await generate_review_packet(
            pack_id="oosem",
            recipe_id="system_requirements_package",
            recipe_parameters={"root_package_id": "root-1", "system_name": "ATM"},
            current_artifacts=artifacts,
            assumptions=["Requirements IDs are still provisional."],
            bridge=FakeBridge(),
        )

        self.assertIn("conformance", validation)
        self.assertIn("evidenceBundle", packet)
        self.assertIn("Requirements IDs are still provisional.", packet["reviewPacketMarkdown"])


if __name__ == "__main__":
    unittest.main()
