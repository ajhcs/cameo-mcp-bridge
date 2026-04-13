import unittest

from cameo_mcp.semantic_validation import (
    verify_activity_flow_semantics_for_diagram,
    verify_cross_diagram_traceability,
    verify_port_boundary_consistency_for_interfaces,
    verify_requirement_quality_for_ids,
)


class FakeBridge:
    def __init__(self) -> None:
        self.interface_flow_properties_calls: list[list[str]] = []
        self.shapes = {
            "act-1": {
                "shapes": [
                    {"presentationId": "pe-start", "elementId": "n1", "elementType": "InitialNode"},
                    {"presentationId": "pe-a1", "elementId": "a1", "elementType": "OpaqueAction"},
                    {"presentationId": "pe-f1", "elementId": "f1", "elementType": "ActivityFinalNode"},
                ]
            },
            "ibd-1": {
                "shapes": [
                    {"presentationId": "pe-port", "elementId": "p1", "elementType": "Port"},
                    {"presentationId": "pe-flow", "elementId": "iflow-1", "elementType": "InformationFlow"},
                ]
            },
        }
        self.elements = {
            "n1": {"id": "n1", "type": "InitialNode", "name": "Start"},
            "a1": {"id": "a1", "type": "OpaqueAction", "name": "Display Available Slots"},
            "f1": {"id": "f1", "type": "ActivityFinalNode", "name": "Done"},
            "p1": {"id": "p1", "type": "Port", "name": "Customer UI"},
            "iflow-1": {"id": "iflow-1", "type": "InformationFlow", "name": "Availability Query"},
            "req-1": {"id": "req-1", "type": "Class", "name": "Appointment Response Time"},
            "req-2": {"id": "req-2", "type": "Class", "name": "System Availability"},
        }
        self.specifications = {
            "req-1": {
                "elementId": "req-1",
                "documentation": "The system shall respond within 5 seconds.",
                "appliedStereotypes": [
                    {"stereotype": "Requirement", "taggedValues": {"id": "REQ-1", "text": "The system shall respond within 5 seconds."}}
                ],
            },
            "req-2": {
                "elementId": "req-2",
                "documentation": "",
                "appliedStereotypes": [
                    {"stereotype": "Requirement", "taggedValues": {"id": "", "text": ""}}
                ],
            },
        }
        self.relationships = {
            "n1": {
                "outgoing": [
                    {
                        "relationshipId": "r1",
                        "type": "ControlFlow",
                        "sources": [{"id": "n1"}],
                        "targets": [{"id": "a1"}],
                    }
                ],
                "incoming": [],
            },
            "a1": {
                "outgoing": [
                    {
                        "relationshipId": "r2",
                        "type": "ControlFlow",
                        "sources": [{"id": "a1"}],
                        "targets": [{"id": "f1"}],
                    }
                ],
                "incoming": [
                    {
                        "relationshipId": "r1",
                        "type": "ControlFlow",
                        "sources": [{"id": "n1"}],
                        "targets": [{"id": "a1"}],
                    }
                ],
            },
            "f1": {
                "outgoing": [],
                "incoming": [
                    {
                        "relationshipId": "r2",
                        "type": "ControlFlow",
                        "sources": [{"id": "a1"}],
                        "targets": [{"id": "f1"}],
                    }
                ],
            },
            "p1": {
                "outgoing": [],
                "incoming": [],
                "undirected": [
                    {
                        "relationshipId": "iflow-1",
                        "type": "InformationFlow",
                        "name": "Availability Query",
                        "conveyed": [{"id": "blk-1", "name": "Available Slots"}],
                        "relatedElements": [{"id": "blk-2", "name": "Scheduling System"}],
                    }
                ],
            },
            "iflow-1": {
                "outgoing": [],
                "incoming": [],
                "undirected": [],
            },
            "req-1": {
                "outgoing": [
                    {
                        "relationshipId": "trace-1",
                        "type": "Trace",
                        "sources": [{"id": "req-1"}],
                        "targets": [{"id": "blk-1"}],
                    }
                ],
                "incoming": [],
            },
            "req-2": {
                "outgoing": [],
                "incoming": [],
            },
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

    async def list_diagram_shapes(self, diagram_id):
        return self.shapes[diagram_id]

    async def get_element(self, element_id):
        return self.elements[element_id]

    async def get_relationships(self, element_id):
        return self.relationships.get(element_id, {"outgoing": [], "incoming": [], "undirected": []})

    async def get_specification(self, element_id):
        return self.specifications[element_id]

    async def get_interface_flow_properties(self, interface_block_ids):
        self.interface_flow_properties_calls.append(list(interface_block_ids))
        return self.interface_flow_payload


class SemanticValidationTests(unittest.IsolatedAsyncioTestCase):
    async def test_verify_activity_flow_semantics_for_diagram_reads_snapshot(self) -> None:
        result = await verify_activity_flow_semantics_for_diagram("act-1", bridge=FakeBridge())

        self.assertTrue(result["ok"])
        self.assertEqual("act-1", result["diagramId"])
        self.assertEqual(2, result["metrics"]["flowRelationshipCount"])
        self.assertEqual(2, len(result["relationships"]))

    async def test_verify_port_boundary_consistency_for_interfaces_uses_native_readback(self) -> None:
        bridge = FakeBridge()
        result = await verify_port_boundary_consistency_for_interfaces(
            ["if-1", "if-2"],
            bridge=bridge,
        )

        self.assertFalse(result["ok"])
        self.assertEqual(2, len(result["interfaceBlocks"]))
        self.assertIn("available slots", result["metrics"]["duplicateFlowProperties"])
        self.assertEqual([["if-1", "if-2"]], bridge.interface_flow_properties_calls)
        self.assertEqual([], getattr(bridge, "scripts", []))

    async def test_verify_requirement_quality_for_ids_merges_element_and_specification(self) -> None:
        result = await verify_requirement_quality_for_ids(
            ["req-1", "req-2"],
            bridge=FakeBridge(),
        )

        self.assertFalse(result["ok"])
        self.assertEqual(2, len(result["requirements"]))
        self.assertIn("req-2", result["metrics"]["blankTextIds"])

    async def test_verify_cross_diagram_traceability_reads_all_artifact_sets(self) -> None:
        bridge = FakeBridge()
        result = await verify_cross_diagram_traceability(
            activity_diagram_id="act-1",
            interface_block_ids=["if-1", "if-2"],
            ibd_diagram_id="ibd-1",
            requirement_ids=["req-1", "req-2"],
            architecture_element_ids=["blk-1"],
            bridge=bridge,
        )

        self.assertFalse(result["ok"])
        self.assertIn("Available Slots", result["portTerms"])
        self.assertIn("Availability Query", result["ibdTerms"])
        self.assertIn("req-2", result["metrics"]["missingRequirementTraceIds"])
        self.assertEqual([["if-1", "if-2"]], bridge.interface_flow_properties_calls)


if __name__ == "__main__":
    unittest.main()
