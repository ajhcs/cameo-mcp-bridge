import unittest

from cameo_mcp.methodology import runtime
from cameo_mcp.methodology.service import (
    _hydrate_live_artifacts,
    execute_methodology_recipe,
    generate_review_packet,
    get_workflow_guidance,
    list_methodology_packs,
    validate_methodology_recipe,
)


class FakeBridge:
    def __init__(self) -> None:
        self.counter = 0
        self.calls: list[tuple[str, dict[str, object]]] = []
        self.elements = {
            "root-1": {"id": "root-1", "name": "Workspace", "humanType": "Package"},
            "pkg-req": {"id": "pkg-req", "name": "ATM Requirements", "humanType": "Package", "ownerId": "root-1"},
            "dia-req": {"id": "dia-req", "name": "ATM Requirements", "humanType": "SysML Requirement Diagram", "ownerId": "pkg-req"},
            "req-blank": {"id": "req-blank", "name": "REQ-1", "humanType": "Requirement", "ownerId": "pkg-req"},
            "pkg-act": {"id": "pkg-act", "name": "Schedule Appointment Activity", "humanType": "Package", "ownerId": "root-1"},
            "activity-1": {"id": "activity-1", "name": "Schedule Appointment", "humanType": "Activity", "ownerId": "pkg-act"},
            "act-diagram-1": {"id": "act-diagram-1", "name": "Schedule Appointment Activity", "humanType": "Activity Diagram", "ownerId": "activity-1"},
            "act-start": {"id": "act-start", "name": "Start", "type": "InitialNode"},
            "act-a1": {"id": "act-a1", "name": "Display Service Options", "type": "OpaqueAction"},
            "act-a2": {"id": "act-a2", "name": "Send Confirmation", "type": "OpaqueAction"},
            "act-final": {"id": "act-final", "name": "Done", "type": "ActivityFinalNode"},
            "act-partition": {"id": "act-partition", "name": "Scheduling System", "type": "ActivityPartition"},
            "pkg-port": {"id": "pkg-port", "name": "AAS Ports", "humanType": "Package", "ownerId": "root-1"},
            "sys-port": {"id": "sys-port", "name": "AAS", "humanType": "Block", "ownerId": "pkg-port"},
            "bdd-port": {"id": "bdd-port", "name": "AAS Ports", "humanType": "SysML Block Definition Diagram", "ownerId": "pkg-port"},
            "if-1": {"id": "if-1", "name": "Customer UI Port Type", "humanType": "Interface Block", "ownerId": "pkg-port"},
            "if-2": {"id": "if-2", "name": "Scheduling System Port Type", "humanType": "Interface Block", "ownerId": "pkg-port"},
            "pkg-ibd": {"id": "pkg-ibd", "name": "AAS Context", "humanType": "Package", "ownerId": "root-1"},
            "blk-ibd": {"id": "blk-ibd", "name": "AAS", "humanType": "Block", "ownerId": "pkg-ibd"},
            "ibd-1": {"id": "ibd-1", "name": "AAS Context", "humanType": "SysML Internal Block Diagram", "ownerId": "blk-ibd"},
            "ibd-port": {"id": "ibd-port", "name": "Customer UI", "type": "Port"},
            "ibd-flow": {"id": "ibd-flow", "name": "Availability Query", "type": "InformationFlow"},
        }
        self.specifications = {
            "req-blank": {
                "elementId": "req-blank",
                "properties": {},
                "appliedStereotypes": [
                    {"stereotype": "Requirement", "taggedValues": {"id": "", "text": ""}}
                ],
            }
        }
        self.shapes = {
            "act-diagram-1": {
                "shapes": [
                    {"presentationId": "pe-partition", "elementId": "act-partition", "elementType": "ActivityPartition"},
                    {"presentationId": "pe-start", "parentPresentationId": "pe-partition", "elementId": "act-start", "elementType": "InitialNode"},
                    {"presentationId": "pe-a1", "parentPresentationId": "pe-partition", "elementId": "act-a1", "elementType": "OpaqueAction"},
                    {"presentationId": "pe-a2", "parentPresentationId": "pe-partition", "elementId": "act-a2", "elementType": "OpaqueAction"},
                    {"presentationId": "pe-final", "parentPresentationId": "pe-partition", "elementId": "act-final", "elementType": "ActivityFinalNode"},
                ]
            },
            "ibd-1": {
                "shapes": [
                    {"presentationId": "pe-ibd-port", "elementId": "ibd-port", "elementType": "Port"},
                    {"presentationId": "pe-ibd-flow", "elementId": "ibd-flow", "elementType": "InformationFlow"},
                ]
            },
        }
        self.relationships = {
            "act-start": {
                "outgoing": [
                    {
                        "relationshipId": "cf-1",
                        "type": "ControlFlow",
                        "sources": [{"id": "act-start"}],
                        "targets": [{"id": "act-a1"}],
                    }
                ],
                "incoming": [],
                "undirected": [],
            },
            "act-a1": {
                "outgoing": [
                    {
                        "relationshipId": "cf-2",
                        "type": "ControlFlow",
                        "sources": [{"id": "act-a1"}],
                        "targets": [{"id": "act-final"}],
                    }
                ],
                "incoming": [
                    {
                        "relationshipId": "cf-1",
                        "type": "ControlFlow",
                        "sources": [{"id": "act-start"}],
                        "targets": [{"id": "act-a1"}],
                    }
                ],
                "undirected": [],
            },
            "act-a2": {"outgoing": [], "incoming": [], "undirected": []},
            "act-final": {
                "outgoing": [],
                "incoming": [
                    {
                        "relationshipId": "cf-2",
                        "type": "ControlFlow",
                        "sources": [{"id": "act-a1"}],
                        "targets": [{"id": "act-final"}],
                    }
                ],
                "undirected": [],
            },
            "ibd-port": {
                "outgoing": [],
                "incoming": [],
                "undirected": [
                    {
                        "relationshipId": "ibd-flow",
                        "type": "InformationFlow",
                        "name": "Availability Query",
                        "conveyed": [{"id": "conveyed-1", "name": "Available Slots"}],
                        "relatedElements": [{"id": "rel-1", "name": "Scheduling System"}],
                    }
                ],
            },
            "ibd-flow": {"outgoing": [], "incoming": [], "undirected": []},
        }
        self.interface_flow_payload = {
            "interfaceBlocks": [
                {"id": "if-1", "name": "Customer UI Port Type"},
                {"id": "if-2", "name": "Scheduling System Port Type"},
            ],
            "flowProperties": [
                {"id": "fp-1", "name": "Available Slots", "ownerId": "if-1", "direction": "out"},
                {"id": "fp-2", "name": "Available Slots", "ownerId": "if-2", "direction": "in"},
            ],
        }

    async def create_element(self, **kwargs):
        self.calls.append(("create_element", dict(kwargs)))
        self.counter += 1
        return {"id": f"el-{self.counter}", "name": kwargs.get("name")}

    async def create_relationship(self, **kwargs):
        self.calls.append(("create_relationship", dict(kwargs)))
        self.counter += 1
        return {"id": f"rel-{self.counter}", "name": kwargs.get("name")}

    async def create_diagram(self, **kwargs):
        self.calls.append(("create_diagram", dict(kwargs)))
        self.counter += 1
        return {"id": f"dia-{self.counter}", "name": kwargs.get("name")}

    async def add_to_diagram(self, **kwargs):
        self.calls.append(("add_to_diagram", dict(kwargs)))
        self.counter += 1
        return {"presentationId": f"pe-{self.counter}", "diagramId": kwargs.get("diagram_id")}

    async def add_diagram_paths(self, **kwargs):
        self.counter += 1
        return {"results": [{"presentationId": f"path-{self.counter}"}]}

    async def set_shape_compartments(self, **kwargs):
        return {"updated": True}

    async def set_specification(self, **kwargs):
        self.calls.append(("set_specification", dict(kwargs)))
        return {"updated": True}

    async def route_paths(self, **kwargs):
        return {"updated": True}

    async def set_usecase_subject(self, **kwargs):
        return {"updated": True}

    async def list_diagrams(self, **kwargs):
        return {"diagrams": []}

    async def query_elements(self, **kwargs):
        return {"elements": []}

    async def list_diagram_shapes(self, diagram_id, **kwargs):
        return self.shapes.get(diagram_id, {"shapes": []})

    async def get_element(self, element_id, **kwargs):
        return self.elements.get(
            element_id,
            {"id": element_id, "name": element_id, "humanType": "Class", "ownerId": "root-1"},
        )

    async def get_specification(self, element_id, **kwargs):
        return self.specifications.get(element_id, {"elementId": element_id, "properties": {}})

    async def get_relationships(self, element_id, **kwargs):
        response = self.relationships.get(
            element_id,
            {"outgoing": [], "incoming": [], "undirected": []},
        )
        response.setdefault("elementId", element_id)
        response.setdefault("totalCount", 0)
        return response

    async def get_diagram_image(self, diagram_id, **kwargs):
        return {"id": diagram_id, "format": "png", "width": 10, "height": 10, "image": "stub"}

    async def get_interface_flow_properties(self, interface_block_ids, **kwargs):
        self.calls.append(("get_interface_flow_properties", {"interface_block_ids": list(interface_block_ids)}))
        return self.interface_flow_payload


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

    async def test_requirement_semantics_are_merged_into_methodology_conformance(self) -> None:
        artifacts = [
            {"key": "workspace", "kind": "Package", "name": "Workspace", "element_id": "root-1"},
            {"key": "requirements_package", "kind": "Package", "name": "ATM Requirements", "element_id": "pkg-req", "parent_key": "workspace"},
            {"key": "requirements_diagram", "kind": "SysML Requirement Diagram", "name": "ATM Requirements", "element_id": "dia-req", "parent_key": "requirements_package"},
            {"key": "requirement_1", "kind": "Requirement", "name": "REQ-1", "element_id": "req-blank", "parent_key": "requirements_package"},
        ]

        validation = await validate_methodology_recipe(
            pack_id="oosem",
            recipe_id="system_requirements_package",
            recipe_parameters={
                "root_package_id": "root-1",
                "system_name": "ATM",
                "requirement_ids": ["REQ-1"],
                "requirement_texts": [""],
            },
            current_artifacts=artifacts,
            bridge=FakeBridge(),
        )
        packet = await generate_review_packet(
            pack_id="oosem",
            recipe_id="system_requirements_package",
            recipe_parameters={
                "root_package_id": "root-1",
                "system_name": "ATM",
                "requirement_ids": ["REQ-1"],
                "requirement_texts": [""],
            },
            current_artifacts=artifacts,
            bridge=FakeBridge(),
        )

        self.assertIn("semanticValidations", validation)
        self.assertFalse(validation["conformance"]["passed"])
        self.assertTrue(
            any(
                finding["rule_id"].startswith("semantic:requirement_quality")
                for finding in validation["conformance"]["findings"]
            )
        )
        self.assertIn("## Semantic Validation", packet["reviewPacketMarkdown"])

    async def test_logical_activity_recipe_surfaces_activity_semantic_findings(self) -> None:
        artifacts = [
            {"key": "workspace", "kind": "Package", "name": "Workspace", "element_id": "root-1"},
            {"key": "logical_activity_package", "kind": "Package", "name": "Schedule Appointment Activity", "element_id": "pkg-act", "parent_key": "workspace"},
            {"key": "logical_activity", "kind": "Activity", "name": "Schedule Appointment", "element_id": "activity-1", "parent_key": "logical_activity_package"},
            {"key": "logical_activity_diagram", "kind": "Activity Diagram", "name": "Schedule Appointment Activity", "element_id": "act-diagram-1", "parent_key": "logical_activity"},
        ]

        validation = await validate_methodology_recipe(
            pack_id="oosem",
            recipe_id="logical_activity_flow",
            recipe_parameters={
                "root_package_id": "root-1",
                "activity_name": "Schedule Appointment",
            },
            current_artifacts=artifacts,
            bridge=FakeBridge(),
        )

        self.assertFalse(validation["conformance"]["passed"])
        self.assertTrue(
            any(
                finding["rule_id"].startswith("semantic:activity_flow_semantics")
                for finding in validation["conformance"]["findings"]
            )
        )

    async def test_logical_activity_recipe_creates_partitions_before_visuals_and_uses_absolute_positions(self) -> None:
        bridge = FakeBridge()

        await execute_methodology_recipe(
            pack_id="oosem",
            recipe_id="logical_activity_flow",
            root_package_id="root-1",
            recipe_parameters={
                "root_package_id": "root-1",
                "activity_name": "Schedule Appointment",
                "performer_names": ["Customer", "Scheduling System"],
                "action_names": ["Capture Need", "Schedule Slot"],
            },
            bridge=bridge,
        )

        last_partition_create_index = max(
            index
            for index, (method_name, kwargs) in enumerate(bridge.calls)
            if method_name == "create_element" and kwargs.get("type") == "ActivityPartition"
        )
        first_add_to_diagram_index = next(
            index
            for index, (method_name, _) in enumerate(bridge.calls)
            if method_name == "add_to_diagram"
        )

        self.assertLess(last_partition_create_index, first_add_to_diagram_index)
        self.assertTrue(
            all(
                "container_presentation_id" not in kwargs
                for method_name, kwargs in bridge.calls
                if method_name == "add_to_diagram"
            )
        )
        self.assertEqual(
            3,
            sum(
                1
                for method_name, kwargs in bridge.calls
                if method_name == "create_relationship" and kwargs.get("type") == "ControlFlow"
            ),
        )

    async def test_logical_port_recipe_surfaces_port_boundary_findings(self) -> None:
        artifacts = [
            {"key": "workspace", "kind": "Package", "name": "Workspace", "element_id": "root-1"},
            {"key": "logical_port_package", "kind": "Package", "name": "AAS Ports", "element_id": "pkg-port", "parent_key": "workspace"},
            {"key": "logical_port_system", "kind": "Block", "name": "AAS", "element_id": "sys-port", "parent_key": "logical_port_package"},
            {"key": "logical_port_bdd", "kind": "SysML Block Definition Diagram", "name": "AAS Ports", "element_id": "bdd-port", "parent_key": "logical_port_package"},
            {"key": "interface_block_1", "kind": "Interface Block", "name": "Customer UI Port Type", "element_id": "if-1", "parent_key": "logical_port_package"},
            {"key": "interface_block_2", "kind": "Interface Block", "name": "Scheduling System Port Type", "element_id": "if-2", "parent_key": "logical_port_package"},
        ]

        validation = await validate_methodology_recipe(
            pack_id="oosem",
            recipe_id="logical_port_bdd",
            recipe_parameters={
                "root_package_id": "root-1",
                "system_name": "AAS",
                "interface_definitions": [
                    {"name": "Customer UI Port Type", "flow_properties": [{"name": "Available Slots", "direction": "out"}]},
                    {"name": "Scheduling System Port Type", "flow_properties": [{"name": "Available Slots", "direction": "in"}]},
                ],
            },
            current_artifacts=artifacts,
            bridge=FakeBridge(),
        )

        self.assertFalse(validation["conformance"]["passed"])
        self.assertTrue(
            any(
                finding["rule_id"].startswith("semantic:port_boundary_consistency")
                for finding in validation["conformance"]["findings"]
            )
        )

    async def test_execute_logical_port_recipe_keeps_created_bindings_for_semantic_validation(self) -> None:
        result = await execute_methodology_recipe(
            pack_id="oosem",
            recipe_id="logical_port_bdd",
            root_package_id="root-1",
            recipe_parameters={
                "root_package_id": "root-1",
                "system_name": "AAS",
                "interface_definitions": [
                    {"name": "Customer UI Port Type", "flow_properties": [{"name": "Available Slots", "direction": "out"}]},
                    {"name": "Scheduling System Port Type", "flow_properties": [{"name": "Available Slots", "direction": "in"}]},
                ],
            },
            bridge=FakeBridge(),
        )

        self.assertIn("semanticValidations", result)
        port_validation = next(
            item for item in result["semanticValidations"]
            if item["validatorId"] == "port_boundary_consistency"
        )
        self.assertFalse(
            any(check["name"] == "binding-resolution" for check in port_validation["checks"])
        )

    async def test_hydrate_live_artifacts_keeps_specific_kinds_when_live_kind_is_generic(self) -> None:
        bridge = FakeBridge()
        bridge.elements["root-1"]["humanType"] = "Model"
        bridge.elements["bdd-port"]["humanType"] = "Diagram"

        hydrated = await _hydrate_live_artifacts(
            [
                runtime.ArtifactSnapshot(
                    key="workspace",
                    kind="Package",
                    name="Workspace",
                    element_id="root-1",
                ),
                runtime.ArtifactSnapshot(
                    key="logical_port_bdd",
                    kind="SysML Block Definition Diagram",
                    name="AAS Ports",
                    element_id="bdd-port",
                ),
            ],
            bridge=bridge,
        )

        self.assertEqual("Package", hydrated[0].kind)
        self.assertEqual("SysML Block Definition Diagram", hydrated[1].kind)

    async def test_logical_ibd_recipe_surfaces_traceability_findings(self) -> None:
        artifacts = [
            {"key": "workspace", "kind": "Package", "name": "Workspace", "element_id": "root-1"},
            {"key": "logical_context_package", "kind": "Package", "name": "AAS Context", "element_id": "pkg-ibd", "parent_key": "workspace"},
            {"key": "logical_context_block", "kind": "Block", "name": "AAS", "element_id": "blk-ibd", "parent_key": "logical_context_package"},
            {"key": "logical_context_ibd", "kind": "SysML Internal Block Diagram", "name": "AAS Context", "element_id": "ibd-1", "parent_key": "logical_context_block"},
        ]

        validation = await validate_methodology_recipe(
            pack_id="oosem",
            recipe_id="logical_ibd_traceability",
            recipe_parameters={
                "root_package_id": "root-1",
                "context_name": "AAS",
                "activity_diagram_id": "act-diagram-1",
                "flow_names": ["Availability Query"],
            },
            current_artifacts=artifacts,
            bridge=FakeBridge(),
        )

        self.assertFalse(validation["conformance"]["passed"])
        self.assertTrue(
            any(
                finding["rule_id"].startswith("semantic:cross_diagram_traceability")
                for finding in validation["conformance"]["findings"]
            )
        )


if __name__ == "__main__":
    unittest.main()
