import unittest

from cameo_mcp.methodology.runtime import (
    ArtifactRequirement,
    ArtifactSnapshot,
    EvidenceBundle,
    PackDefinition,
    RecipeDefinition,
    RecipeOperationDefinition,
    RelationshipRequirement,
    build_evidence_bundle,
    build_recipe_execution_plan,
    build_workflow_guidance,
    execute_recipe,
    run_conformance_checks,
)


def build_sample_pack() -> PackDefinition:
    recipe = RecipeDefinition(
        recipe_id="oosem.stakeholder_needs",
        name="Stakeholder Needs Package",
        phase="analysis",
        description="Create a starter OOSEM stakeholder needs package.",
        required_artifacts=(
            ArtifactRequirement(
                key="stakeholder_needs_package",
                kind="Package",
                name="Stakeholder Needs",
                parent_key="workspace",
            ),
            ArtifactRequirement(
                key="stakeholder_actor",
                kind="Actor",
                name="Stakeholder",
                parent_key="stakeholder_needs_package",
                stereotypes=("stakeholder",),
            ),
            ArtifactRequirement(
                key="stakeholder_need_usecase",
                kind="UseCase",
                name="Capture Stakeholder Need",
                parent_key="stakeholder_needs_package",
            ),
            ArtifactRequirement(
                key="stakeholder_needs_diagram",
                kind="Use Case Diagram",
                name="Stakeholder Needs",
                parent_key="stakeholder_needs_package",
            ),
        ),
        required_relationships=(
            RelationshipRequirement(
                relationship_type="Association",
                source_key="stakeholder_actor",
                target_key="stakeholder_need_usecase",
                name="identifies",
            ),
        ),
        operations=(
            RecipeOperationDefinition(
                kind="create_element",
                artifact_key="stakeholder_needs_package",
                parameters={
                    "type": "Package",
                    "name": "Stakeholder Needs",
                    "parent_id": {"ref": "workspace"},
                },
            ),
            RecipeOperationDefinition(
                kind="create_element",
                artifact_key="stakeholder_actor",
                parameters={
                    "type": "Actor",
                    "name": "Stakeholder",
                    "parent_id": {"ref": "stakeholder_needs_package"},
                    "stereotype": "stakeholder",
                },
            ),
            RecipeOperationDefinition(
                kind="create_element",
                artifact_key="stakeholder_need_usecase",
                parameters={
                    "type": "UseCase",
                    "name": "Capture Stakeholder Need",
                    "parent_id": {"ref": "stakeholder_needs_package"},
                },
            ),
            RecipeOperationDefinition(
                kind="create_diagram",
                artifact_key="stakeholder_needs_diagram",
                parameters={
                    "type": "Use Case Diagram",
                    "name": "Stakeholder Needs",
                    "parent_id": {"ref": "stakeholder_needs_package"},
                },
            ),
            RecipeOperationDefinition(
                kind="add_to_diagram",
                parameters={
                    "diagram_id": {"ref": "stakeholder_needs_diagram"},
                    "element_id": {"ref": "stakeholder_actor"},
                    "x": 120,
                    "y": 80,
                },
            ),
            RecipeOperationDefinition(
                kind="add_to_diagram",
                parameters={
                    "diagram_id": {"ref": "stakeholder_needs_diagram"},
                    "element_id": {"ref": "stakeholder_need_usecase"},
                    "x": 320,
                    "y": 80,
                },
            ),
            RecipeOperationDefinition(
                kind="create_relationship",
                parameters={
                    "type": "Association",
                    "source_id": {"ref": "stakeholder_actor"},
                    "target_id": {"ref": "stakeholder_need_usecase"},
                    "name": "identifies",
                },
            ),
        ),
        review_checklist=(
            "Confirm the package, actor, use case, and diagram exist.",
            "Verify the actor-to-use-case association is present.",
        ),
        evidence_sections=(
            "scope",
            "trace",
            "diagram",
            "conformance",
        ),
        layout_recipe="subject-with-usecases",
    )

    return PackDefinition(
        pack_id="oosem",
        name="OOSEM",
        description="Opinionated starter pack for OOSEM-style analysis artifacts.",
        phases=("analysis", "architecture"),
        recipes=(recipe,),
        review_checklist=("Pack definitions should drive the workflow.",),
        required_profiles=("sysml",),
    )


class FakeBridge:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, object]]] = []
        self.counter = 0

    async def create_element(self, **kwargs):
        self.calls.append(("create_element", dict(kwargs)))
        self.counter += 1
        return {"id": f"el-{self.counter}"}

    async def create_relationship(self, **kwargs):
        self.calls.append(("create_relationship", dict(kwargs)))
        self.counter += 1
        return {"id": f"rel-{self.counter}"}

    async def create_diagram(self, **kwargs):
        self.calls.append(("create_diagram", dict(kwargs)))
        self.counter += 1
        return {"id": f"dia-{self.counter}"}

    async def add_to_diagram(self, **kwargs):
        self.calls.append(("add_to_diagram", dict(kwargs)))
        self.counter += 1
        return {"presentationId": f"pe-{self.counter}"}


class MethodologyRuntimeTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.pack = build_sample_pack()
        self.recipe = self.pack.recipe("oosem.stakeholder_needs")
        self.workspace = ArtifactSnapshot(
            key="workspace",
            kind="Package",
            name="Workspace",
            element_id="pkg-root",
        )

    def test_workflow_guidance_reports_missing_artifacts_and_actions(self) -> None:
        guidance = build_workflow_guidance(self.pack, [self.workspace])

        self.assertEqual("oosem", guidance.pack_id)
        self.assertEqual("oosem.stakeholder_needs", guidance.recipe_id)
        self.assertFalse(guidance.ready_to_execute)
        self.assertIn("stakeholder_needs_package", guidance.missing_artifact_keys)
        self.assertIn("create Package 'Stakeholder Needs' under 'workspace'", guidance.recommended_actions)

    def test_execution_plan_skips_existing_artifacts(self) -> None:
        completed = [
            self.workspace,
            ArtifactSnapshot(
                key="stakeholder_needs_package",
                kind="Package",
                name="Stakeholder Needs",
                element_id="pkg-1",
            ),
        ]

        plan = build_recipe_execution_plan(self.pack, self.recipe.recipe_id, completed)

        self.assertFalse(plan.ready_to_execute)
        self.assertEqual("skipped", plan.planned_operations[0].status)
        self.assertIn("already exists", plan.planned_operations[0].reason or "")
        self.assertEqual("pending", plan.planned_operations[1].status)
        self.assertEqual("pkg-1", plan.artifact_bindings["stakeholder_needs_package"])

    async def test_execute_recipe_runs_bridge_operations_and_tracks_bindings(self) -> None:
        plan = build_recipe_execution_plan(self.pack, self.recipe.recipe_id, [self.workspace])
        bridge = FakeBridge()

        result = await execute_recipe(plan, bridge)

        self.assertEqual(7, len(result.receipts))
        self.assertEqual("applied", result.receipts[0].status)
        self.assertIn("stakeholder_needs_package", result.artifact_bindings)
        self.assertIn("stakeholder_needs_diagram", result.artifact_bindings)
        self.assertTrue(any(call[0] == "create_relationship" for call in bridge.calls))
        self.assertTrue(any(call[0] == "add_to_diagram" for call in bridge.calls))

    def test_conformance_and_evidence_bundle_are_compact_and_useful(self) -> None:
        current_artifacts = [
            ArtifactSnapshot(
                key="stakeholder_needs_package",
                kind="Package",
                name="Stakeholder Needs",
                element_id="pkg-1",
            ),
            ArtifactSnapshot(
                key="stakeholder_actor",
                kind="Actor",
                name="Stakeholder",
                element_id="el-1",
            ),
            ArtifactSnapshot(
                key="stakeholder_need_usecase",
                kind="UseCase",
                name="Capture Stakeholder Need",
                element_id="el-2",
            ),
            ArtifactSnapshot(
                key="stakeholder_needs_diagram",
                kind="Use Case Diagram",
                name="Stakeholder Needs",
                element_id="dia-1",
            ),
        ]

        guidance = build_workflow_guidance(self.pack, [self.workspace])
        plan = build_recipe_execution_plan(self.pack, self.recipe.recipe_id, [self.workspace])
        execution_result = self._fake_execution_result()
        conformance = run_conformance_checks(self.recipe, current_artifacts, pack_id=self.pack.pack_id)
        bundle = build_evidence_bundle(
            self.pack,
            self.recipe,
            guidance,
            plan,
            execution_result,
            conformance,
            assumptions=("All artifacts created in a local Cameo session.",),
        )

        self.assertFalse(conformance.passed)
        self.assertGreaterEqual(len(conformance.findings), 1)
        self.assertIsInstance(bundle, EvidenceBundle)
        self.assertEqual("oosem", bundle.pack_id)
        self.assertIn("stakeholder_actor", bundle.artifact_keys)
        self.assertIn("conformance", bundle.to_dict())

    def _fake_execution_result(self):
        from cameo_mcp.methodology.runtime import OperationReceipt, RecipeExecutionResult

        return RecipeExecutionResult(
            pack_id=self.pack.pack_id,
            recipe_id=self.recipe.recipe_id,
            recipe_name=self.recipe.name,
            phase=self.recipe.phase,
            receipts=(OperationReceipt(step_id="s1", operation_kind="create_element", status="applied", result={"id": "el-1"}),),
            artifact_bindings={"stakeholder_actor": "el-1"},
            created_artifacts=(),
            updated_artifacts=(),
            notes=(),
        )


if __name__ == "__main__":
    unittest.main()
