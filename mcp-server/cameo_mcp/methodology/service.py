"""High-level methodology services built on top of the bridge client."""

from __future__ import annotations

import re
from typing import Any, Mapping, Sequence

from cameo_mcp import client as default_bridge_client
from cameo_mcp.semantic_validation import (
    verify_activity_flow_semantics_for_diagram,
    verify_cross_diagram_traceability as run_cross_diagram_traceability,
    verify_port_boundary_consistency_for_interfaces,
    verify_requirement_quality_for_ids,
)

from . import registry, runtime


def list_methodology_packs() -> dict[str, Any]:
    packs = [pack.to_dict() for pack in registry.list_packs()]
    return {"count": len(packs), "packs": packs}


def get_methodology_pack(pack_id: str) -> dict[str, Any]:
    pack = registry.get_pack(pack_id)
    return pack.to_dict()


def get_workflow_guidance(
    pack_id: str,
    recipe_id: str | None = None,
    recipe_parameters: Mapping[str, Any] | None = None,
    completed_artifacts: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    pack = registry.get_pack(pack_id)
    runtime_pack = _build_runtime_pack(
        pack,
        recipe_parameters or {},
        target_recipe_id=recipe_id,
        strict=False,
    )
    artifacts = _artifact_snapshots(completed_artifacts or ())
    artifacts.extend(_reference_artifacts(recipe_id, recipe_parameters or {}))
    guidance = runtime.build_workflow_guidance(runtime_pack, artifacts, recipe_id=recipe_id)
    return {
        "pack": pack.to_dict(),
        "guidance": guidance.to_dict(),
    }


async def execute_methodology_recipe(
    pack_id: str,
    recipe_id: str,
    recipe_parameters: Mapping[str, Any],
    *,
    root_package_id: str,
    completed_artifacts: Sequence[Mapping[str, Any]] | None = None,
    assumptions: Sequence[str] | None = None,
    bridge: Any = default_bridge_client,
) -> dict[str, Any]:
    pack = registry.get_pack(pack_id)
    runtime_pack = _build_runtime_pack(
        pack,
        recipe_parameters,
        target_recipe_id=recipe_id,
        strict=True,
    )
    runtime_recipe = runtime_pack.recipe(recipe_id)
    artifacts = _seed_completed_artifacts(root_package_id, completed_artifacts or ())
    artifacts.extend(_reference_artifacts(recipe_id, recipe_parameters))
    artifacts = await _discover_live_artifacts(
        runtime_recipe,
        artifacts,
        recipe_parameters=recipe_parameters,
        root_package_id=root_package_id,
        bridge=bridge,
    )
    plan = runtime.build_recipe_execution_plan(runtime_pack, recipe_id, artifacts)
    before_diagram_ids = _diagram_ids_for_evidence(plan.artifact_bindings)
    before_snapshots = await _capture_diagram_snapshots(before_diagram_ids, bridge)
    result = await runtime.execute_recipe(plan, bridge)
    current_artifacts = _merge_current_artifacts(runtime_recipe, artifacts, plan, result)
    current_artifacts = await _discover_live_artifacts(
        runtime_recipe,
        current_artifacts,
        recipe_parameters=recipe_parameters,
        root_package_id=root_package_id,
        bridge=bridge,
    )
    guidance = runtime.build_workflow_guidance(runtime_pack, current_artifacts, recipe_id=recipe_id)
    conformance = runtime.run_conformance_checks(
        runtime_recipe,
        current_artifacts,
        pack_id=runtime_pack.pack_id,
    )
    semantic_validations = await _run_semantic_validations(
        runtime_recipe,
        current_artifacts,
        bridge=bridge,
    )
    conformance = runtime.extend_conformance_report(
        conformance,
        runtime.semantic_validation_findings(semantic_validations),
    )
    after_diagram_ids = _diagram_ids_for_evidence(result.artifact_bindings)
    bridge_evidence = await _build_bridge_evidence(
        current_artifacts,
        result,
        before_diagram_ids=before_diagram_ids,
        before_snapshots=before_snapshots,
        after_diagram_ids=after_diagram_ids,
        semantic_validations=semantic_validations,
        bridge=bridge,
    )
    bundle = runtime.build_evidence_bundle(
        runtime_pack,
        runtime_recipe,
        guidance,
        plan,
        result,
        conformance,
        assumptions=tuple(assumptions or ()),
        bridge_evidence=bridge_evidence,
    )
    return {
        "pack": pack.to_dict(),
        "recipe": _registry_recipe_dict(pack_id, recipe_id),
        "workflowGuidance": guidance.to_dict(),
        "executionPlan": plan.to_dict(),
        "executionResult": result.to_dict(),
        "conformance": conformance.to_dict(),
        "semanticValidations": semantic_validations,
        "evidenceBundle": bundle.to_dict(),
        "reviewPacketMarkdown": _render_review_packet(pack, bundle),
    }


async def validate_methodology_recipe(
    pack_id: str,
    recipe_id: str,
    recipe_parameters: Mapping[str, Any] | None = None,
    current_artifacts: Sequence[Mapping[str, Any]] | None = None,
    bridge: Any = default_bridge_client,
) -> dict[str, Any]:
    pack = registry.get_pack(pack_id)
    runtime_pack = _build_runtime_pack(
        pack,
        recipe_parameters or {},
        target_recipe_id=recipe_id,
        strict=False,
    )
    runtime_recipe = runtime_pack.recipe(recipe_id)
    params = recipe_parameters or {}
    artifacts = _artifact_snapshots(current_artifacts or ())
    artifacts.extend(_reference_artifacts(recipe_id, params))
    artifacts = await _discover_live_artifacts(
        runtime_recipe,
        artifacts,
        recipe_parameters=params,
        root_package_id=_root_package_id(params, artifacts),
        bridge=bridge,
    )
    guidance = runtime.build_workflow_guidance(runtime_pack, artifacts, recipe_id=recipe_id)
    conformance = runtime.run_conformance_checks(
        runtime_recipe,
        artifacts,
        pack_id=runtime_pack.pack_id,
    )
    semantic_validations = await _run_semantic_validations(
        runtime_recipe,
        artifacts,
        bridge=bridge,
    )
    conformance = runtime.extend_conformance_report(
        conformance,
        runtime.semantic_validation_findings(semantic_validations),
    )
    return {
        "pack": pack.to_dict(),
        "recipe": _registry_recipe_dict(pack_id, recipe_id),
        "workflowGuidance": guidance.to_dict(),
        "conformance": conformance.to_dict(),
        "semanticValidations": semantic_validations,
    }


async def generate_review_packet(
    pack_id: str,
    recipe_id: str,
    recipe_parameters: Mapping[str, Any] | None = None,
    current_artifacts: Sequence[Mapping[str, Any]] | None = None,
    assumptions: Sequence[str] | None = None,
    notes: Sequence[str] | None = None,
    bridge: Any = default_bridge_client,
) -> dict[str, Any]:
    pack = registry.get_pack(pack_id)
    runtime_pack = _build_runtime_pack(
        pack,
        recipe_parameters or {},
        target_recipe_id=recipe_id,
        strict=False,
    )
    runtime_recipe = runtime_pack.recipe(recipe_id)
    params = recipe_parameters or {}
    artifacts = _artifact_snapshots(current_artifacts or ())
    artifacts.extend(_reference_artifacts(recipe_id, params))
    artifacts = await _discover_live_artifacts(
        runtime_recipe,
        artifacts,
        recipe_parameters=params,
        root_package_id=_root_package_id(params, artifacts),
        bridge=bridge,
    )
    guidance = runtime.build_workflow_guidance(runtime_pack, artifacts, recipe_id=recipe_id)
    plan = runtime.build_recipe_execution_plan(runtime_pack, recipe_id, artifacts)
    empty_result = runtime.RecipeExecutionResult(
        pack_id=runtime_pack.pack_id,
        recipe_id=runtime_recipe.recipe_id,
        recipe_name=runtime_recipe.name,
        phase=runtime_recipe.phase,
        receipts=(),
        artifact_bindings={artifact.key: artifact.element_id for artifact in artifacts if artifact.element_id},
        created_artifacts=(),
        updated_artifacts=(),
        notes=(),
    )
    conformance = runtime.run_conformance_checks(
        runtime_recipe,
        artifacts,
        pack_id=runtime_pack.pack_id,
    )
    semantic_validations = await _run_semantic_validations(
        runtime_recipe,
        artifacts,
        bridge=bridge,
    )
    conformance = runtime.extend_conformance_report(
        conformance,
        runtime.semantic_validation_findings(semantic_validations),
    )
    bridge_evidence = await _build_bridge_evidence(
        artifacts,
        empty_result,
        before_diagram_ids=_diagram_ids_for_evidence(plan.artifact_bindings),
        before_snapshots=await _capture_diagram_snapshots(
            _diagram_ids_for_evidence(plan.artifact_bindings),
            bridge,
        ),
        after_diagram_ids=_diagram_ids_for_evidence(plan.artifact_bindings),
        semantic_validations=semantic_validations,
        bridge=bridge,
    )
    bundle = runtime.build_evidence_bundle(
        runtime_pack,
        runtime_recipe,
        guidance,
        plan,
        empty_result,
        conformance,
        assumptions=tuple(assumptions or ()),
        notes=tuple(notes or ()),
        bridge_evidence=bridge_evidence,
    )
    return {
        "pack": pack.to_dict(),
        "recipe": _registry_recipe_dict(pack_id, recipe_id),
        "semanticValidations": semantic_validations,
        "evidenceBundle": bundle.to_dict(),
        "reviewPacketMarkdown": _render_review_packet(pack, bundle),
    }


def _registry_recipe_dict(pack_id: str, recipe_id: str) -> dict[str, Any]:
    return registry.get_recipe(pack_id, recipe_id).to_dict()


def _artifact_snapshots(
    artifacts: Sequence[Mapping[str, Any]],
) -> list[runtime.ArtifactSnapshot]:
    snapshots: list[runtime.ArtifactSnapshot] = []
    for artifact in artifacts:
        relationships = tuple(
            runtime.RelationshipSnapshot(
                relationship_type=str(rel.get("relationship_type") or rel.get("relationshipType") or ""),
                source_key=str(rel.get("source_key") or rel.get("sourceKey") or ""),
                target_key=str(rel.get("target_key") or rel.get("targetKey") or ""),
                relationship_id=_optional_str(rel.get("relationship_id") or rel.get("relationshipId")),
                name=_optional_str(rel.get("name")),
                guard=_optional_str(rel.get("guard")),
            )
            for rel in artifact.get("relationships", ())
        )
        snapshots.append(
            runtime.ArtifactSnapshot(
                key=str(artifact["key"]),
                kind=str(artifact["kind"]),
                name=str(artifact["name"]),
                element_id=_optional_str(artifact.get("element_id") or artifact.get("elementId")),
                parent_key=_optional_str(artifact.get("parent_key") or artifact.get("parentKey")),
                stereotypes=tuple(str(item) for item in artifact.get("stereotypes", ())),
                properties=dict(artifact.get("properties", {})),
                relationships=relationships,
            )
        )
    return snapshots


def _seed_completed_artifacts(
    root_package_id: str,
    completed_artifacts: Sequence[Mapping[str, Any]],
) -> list[runtime.ArtifactSnapshot]:
    artifacts = _artifact_snapshots(completed_artifacts)
    if not any(artifact.key == "workspace" for artifact in artifacts):
        artifacts.insert(
            0,
            runtime.ArtifactSnapshot(
                key="workspace",
                kind="Package",
                name="Workspace",
                element_id=root_package_id,
            ),
        )
    return artifacts


def _reference_artifacts(
    recipe_id: str | None,
    recipe_parameters: Mapping[str, Any],
) -> list[runtime.ArtifactSnapshot]:
    if recipe_id == "system_requirements_package":
        return [
            runtime.ArtifactSnapshot(
                key=f"source_need_{index}",
                kind="Requirement",
                name=f"Source Need {index}",
                element_id=element_id,
            )
            for index, element_id in enumerate(
                _string_list(recipe_parameters.get("source_need_ids")),
                start=1,
            )
        ]
    if recipe_id == "verification_evidence_scaffold":
        return [
            runtime.ArtifactSnapshot(
                key=f"requirement_ref_{index}",
                kind="Requirement",
                name=requirement_id,
                element_id=requirement_id,
            )
            for index, requirement_id in enumerate(
                _string_list(recipe_parameters.get("requirement_ids")),
                start=1,
            )
        ]
    if recipe_id == "requirements_to_architecture_allocation":
        return [
            runtime.ArtifactSnapshot(
                key=f"requirement_ref_{index}",
                kind="Requirement",
                name=requirement_id,
                element_id=requirement_id,
            )
            for index, requirement_id in enumerate(
                _string_list(recipe_parameters.get("requirement_ids")),
                start=1,
            )
        ]
    return []


def _merge_current_artifacts(
    recipe: runtime.RecipeDefinition,
    existing_artifacts: Sequence[runtime.ArtifactSnapshot],
    plan: runtime.RecipeExecutionPlan,
    result: runtime.RecipeExecutionResult,
) -> list[runtime.ArtifactSnapshot]:
    artifact_index = {artifact.key: artifact for artifact in existing_artifacts}
    bindings = dict(result.artifact_bindings)

    for requirement in recipe.required_artifacts:
        binding = bindings.get(requirement.key)
        if binding is None:
            continue
        artifact_index[requirement.key] = runtime.ArtifactSnapshot(
            key=requirement.key,
            kind=requirement.kind,
            name=requirement.name or requirement.key,
            element_id=binding,
            parent_key=requirement.parent_key,
            stereotypes=requirement.stereotypes,
            properties=dict(requirement.properties),
            relationships=artifact_index.get(requirement.key, runtime.ArtifactSnapshot(
                key=requirement.key,
                kind=requirement.kind,
                name=requirement.name or requirement.key,
            )).relationships,
        )

    reverse_bindings = {value: key for key, value in bindings.items() if value}
    relationship_receipts: list[runtime.RelationshipSnapshot] = []
    for step in plan.planned_operations:
        if step.operation.kind != "create_relationship" or step.status == "skipped":
            continue
        resolved = _resolve_runtime_parameters(step.operation.parameters, bindings)
        source_key = reverse_bindings.get(str(resolved["source_id"]), "")
        target_key = reverse_bindings.get(str(resolved["target_id"]), "")
        relationship_receipts.append(
            runtime.RelationshipSnapshot(
                relationship_type=str(resolved["type"]),
                source_key=source_key,
                target_key=target_key,
                name=_optional_str(resolved.get("name")),
            )
        )

    if relationship_receipts:
        by_source: dict[str, list[runtime.RelationshipSnapshot]] = {}
        for relationship in relationship_receipts:
            by_source.setdefault(relationship.source_key, []).append(relationship)
        for source_key, relationships in by_source.items():
            artifact = artifact_index.get(source_key)
            if artifact is None:
                continue
            artifact_index[source_key] = runtime.ArtifactSnapshot(
                key=artifact.key,
                kind=artifact.kind,
                name=artifact.name,
                element_id=artifact.element_id,
                parent_key=artifact.parent_key,
                stereotypes=artifact.stereotypes,
                properties=artifact.properties,
                relationships=artifact.relationships + tuple(relationships),
            )

    for artifact in result.created_artifacts:
        existing = artifact_index.get(artifact.key)
        artifact_index[artifact.key] = runtime.ArtifactSnapshot(
            key=artifact.key,
            kind=artifact.kind,
            name=artifact.name,
            element_id=artifact.element_id or (existing.element_id if existing is not None else None),
            parent_key=existing.parent_key if existing is not None else artifact.parent_key,
            stereotypes=existing.stereotypes if existing is not None and existing.stereotypes else artifact.stereotypes,
            properties=existing.properties if existing is not None else artifact.properties,
            relationships=existing.relationships if existing is not None else artifact.relationships,
        )

    for artifact in result.updated_artifacts:
        existing = artifact_index.get(artifact.key)
        if existing is None:
            artifact_index[artifact.key] = runtime.ArtifactSnapshot(
                key=artifact.key,
                kind=artifact.kind,
                name=artifact.name,
                element_id=artifact.element_id,
                parent_key=artifact.parent_key,
                stereotypes=artifact.stereotypes,
                properties=dict(artifact.properties),
                relationships=artifact.relationships,
            )
            continue
        artifact_index[artifact.key] = runtime.ArtifactSnapshot(
            key=existing.key,
            kind=existing.kind,
            name=existing.name,
            element_id=existing.element_id or artifact.element_id,
            parent_key=existing.parent_key,
            stereotypes=existing.stereotypes,
            properties={**existing.properties, **artifact.properties},
            relationships=existing.relationships,
        )

    return list(artifact_index.values())


def _resolve_runtime_parameters(
    parameters: Mapping[str, Any],
    bindings: Mapping[str, str],
) -> dict[str, Any]:
    resolved: dict[str, Any] = {}
    for key, value in parameters.items():
        if isinstance(value, Mapping) and set(value) == {"ref"}:
            resolved[key] = bindings[str(value["ref"])]
        else:
            resolved[key] = value
    return resolved


def _build_runtime_pack(
    pack: registry.PackDefinition,
    recipe_parameters: Mapping[str, Any],
    *,
    target_recipe_id: str | None = None,
    strict: bool,
) -> runtime.PackDefinition:
    recipes = (
        (registry.get_recipe(pack.id, target_recipe_id),)
        if target_recipe_id is not None
        else pack.recipes
    )
    return runtime.PackDefinition(
        pack_id=pack.id,
        name=pack.title,
        description=f"{pack.domain} methodology pack",
        phases=tuple(phase.id for phase in pack.method_phases),
        recipes=tuple(
            _build_runtime_recipe(pack.id, recipe, recipe_parameters, strict=strict)
            for recipe in recipes
        ),
        review_checklist=tuple(item.title for item in pack.checklist_items),
        required_profiles=pack.required_profiles,
    )


def _build_runtime_recipe(
    pack_id: str,
    recipe: registry.ArtifactRecipe,
    parameters: Mapping[str, Any],
    *,
    strict: bool,
) -> runtime.RecipeDefinition:
    params = _materialize_parameters(recipe.parameters, parameters, strict=strict)
    builders = {
        "stakeholder_needs_package": _build_stakeholder_needs_recipe,
        "use_case_model": _build_use_case_recipe,
        "use_case_subject_containment": _build_use_case_subject_containment_recipe,
        "system_requirements_package": _build_system_requirements_recipe,
        "logical_architecture_scaffold": _build_architecture_recipe,
        "logical_activity_flow": _build_logical_activity_flow_recipe,
        "logical_port_bdd": _build_logical_port_bdd_recipe,
        "logical_ibd_traceability": _build_logical_ibd_traceability_recipe,
        "requirements_to_architecture_allocation": _build_requirements_to_architecture_recipe,
        "verification_evidence_scaffold": _build_verification_recipe,
        "uaf_operational_activity_starter": _build_uaf_operational_activity_recipe,
    }
    try:
        return builders[recipe.id](pack_id, recipe, params)
    except KeyError as exc:
        raise KeyError(f"Unsupported executable methodology recipe: {recipe.id}") from exc


def _build_stakeholder_needs_recipe(
    pack_id: str,
    recipe: registry.ArtifactRecipe,
    params: Mapping[str, Any],
) -> runtime.RecipeDefinition:
    subject_name = str(params["subject_name"])
    package_name = f"{subject_name} Needs"
    need_statements = _string_list(params.get("need_statements"))
    stakeholder_names = _string_list(params.get("stakeholder_names"))

    required_artifacts: list[runtime.ArtifactRequirement] = [
        runtime.ArtifactRequirement(key="workspace", kind="Package"),
        runtime.ArtifactRequirement(
            key="stakeholder_needs_package",
            kind="Package",
            name=package_name,
            parent_key="workspace",
        ),
        runtime.ArtifactRequirement(
            key="stakeholder_needs_diagram",
            kind="SysML Requirement Diagram",
            name=package_name,
            parent_key="stakeholder_needs_package",
        ),
    ]
    operations: list[runtime.RecipeOperationDefinition] = [
        runtime.RecipeOperationDefinition(
            kind="create_element",
            artifact_key="stakeholder_needs_package",
            parameters={
                "type": "Package",
                "name": package_name,
                "parent_id": {"ref": "workspace"},
            },
        ),
        runtime.RecipeOperationDefinition(
            kind="create_diagram",
            artifact_key="stakeholder_needs_diagram",
            parameters={
                "type": "SysML Requirement Diagram",
                "name": package_name,
                "parent_id": {"ref": "stakeholder_needs_package"},
            },
        ),
    ]
    relationship_requirements: list[runtime.RelationshipRequirement] = []

    for index, stakeholder_name in enumerate(stakeholder_names, start=1):
        key = f"stakeholder_{index}"
        required_artifacts.append(
            runtime.ArtifactRequirement(
                key=key,
                kind="Actor",
                name=stakeholder_name,
                parent_key="stakeholder_needs_package",
            )
        )
        operations.append(
            runtime.RecipeOperationDefinition(
                kind="create_element",
                artifact_key=key,
                parameters={
                    "type": "Actor",
                    "name": stakeholder_name,
                    "parent_id": {"ref": "stakeholder_needs_package"},
                },
            )
        )

    for index, statement in enumerate(need_statements, start=1):
        key = f"need_{index}"
        operations.append(
            runtime.RecipeOperationDefinition(
                kind="create_element",
                artifact_key=key,
                parameters={
                    "type": "Requirement",
                    "name": statement,
                    "parent_id": {"ref": "stakeholder_needs_package"},
                    "documentation": statement,
                },
            )
        )
        operations.append(
            runtime.RecipeOperationDefinition(
                kind="add_to_diagram",
                parameters={
                    "diagram_id": {"ref": "stakeholder_needs_diagram"},
                    "element_id": {"ref": key},
                    "x": 180,
                    "y": 80 + ((index - 1) * 110),
                },
            )
        )
        required_artifacts.append(
            runtime.ArtifactRequirement(
                key=key,
                kind="Requirement",
                name=statement,
                parent_key="stakeholder_needs_package",
            )
        )

    for stakeholder_key, need_key in _broadcast_pairs(
        [f"stakeholder_{index}" for index in range(1, len(stakeholder_names) + 1)],
        [f"need_{index}" for index in range(1, len(need_statements) + 1)],
    ):
        relationship_requirements.append(
            runtime.RelationshipRequirement(
                relationship_type="Trace",
                source_key=stakeholder_key,
                target_key=need_key,
                name="originates",
                required=True,
            )
        )
        operations.append(
            runtime.RecipeOperationDefinition(
                kind="create_relationship",
                parameters={
                    "type": "Trace",
                    "source_id": {"ref": stakeholder_key},
                    "target_id": {"ref": need_key},
                    "name": "originates",
                },
            )
        )

    return runtime.RecipeDefinition(
        recipe_id=recipe.id,
        name=recipe.title,
        phase=recipe.phase_id,
        description=recipe.goal,
        required_artifacts=tuple(required_artifacts),
        required_relationships=tuple(relationship_requirements),
        operations=tuple(operations),
        review_checklist=tuple(recipe.review_sections),
        evidence_sections=tuple(recipe.evidence_sections),
        layout_recipe=recipe.layout_profile,
        required_profiles=tuple(),
    )


def _build_use_case_recipe(
    pack_id: str,
    recipe: registry.ArtifactRecipe,
    params: Mapping[str, Any],
) -> runtime.RecipeDefinition:
    subject_name = str(params["subject_name"])
    package_name = f"{subject_name} Use Cases"
    actor_names = _string_list(params.get("actor_names"))
    use_case_names = _string_list(params.get("use_case_names"))
    required_artifacts: list[runtime.ArtifactRequirement] = [
        runtime.ArtifactRequirement(key="workspace", kind="Package"),
        runtime.ArtifactRequirement(
            key="use_case_package",
            kind="Package",
            name=package_name,
            parent_key="workspace",
        ),
        runtime.ArtifactRequirement(
            key="subject_boundary",
            kind="Block",
            name=subject_name,
            parent_key="use_case_package",
        ),
        runtime.ArtifactRequirement(
            key="use_case_diagram",
            kind="Use Case Diagram",
            name=package_name,
            parent_key="use_case_package",
        ),
    ]
    operations: list[runtime.RecipeOperationDefinition] = [
        runtime.RecipeOperationDefinition(
            kind="create_element",
            artifact_key="use_case_package",
            parameters={
                "type": "Package",
                "name": package_name,
                "parent_id": {"ref": "workspace"},
            },
        ),
        runtime.RecipeOperationDefinition(
            kind="create_element",
            artifact_key="subject_boundary",
            parameters={
                "type": "Block",
                "name": subject_name,
                "parent_id": {"ref": "use_case_package"},
            },
        ),
        runtime.RecipeOperationDefinition(
            kind="create_diagram",
            artifact_key="use_case_diagram",
            parameters={
                "type": "Use Case Diagram",
                "name": package_name,
                "parent_id": {"ref": "use_case_package"},
            },
        ),
        runtime.RecipeOperationDefinition(
            kind="add_to_diagram",
            artifact_key="subject_boundary_shape",
            parameters={
                "diagram_id": {"ref": "use_case_diagram"},
                "element_id": {"ref": "subject_boundary"},
                "x": 280,
                "y": 60,
                "width": 420,
                "height": max(220, 140 + (len(use_case_names) * 90)),
            },
        ),
        runtime.RecipeOperationDefinition(
            kind="set_shape_compartments",
            parameters={
                "diagram_id": {"ref": "use_case_diagram"},
                "presentation_id": {"ref": "subject_boundary_shape"},
                "compartments": {
                    "properties": False,
                    "operations": False,
                    "attributes": False,
                    "stereotype": False,
                },
            },
        ),
    ]
    relationship_requirements: list[runtime.RelationshipRequirement] = []

    for index, actor_name in enumerate(actor_names, start=1):
        key = f"actor_{index}"
        shape_key = f"{key}_shape"
        required_artifacts.append(
            runtime.ArtifactRequirement(
                key=key,
                kind="Actor",
                name=actor_name,
                parent_key="use_case_package",
            )
        )
        operations.extend(
            [
                runtime.RecipeOperationDefinition(
                    kind="create_element",
                    artifact_key=key,
                    parameters={
                        "type": "Actor",
                        "name": actor_name,
                        "parent_id": {"ref": "use_case_package"},
                    },
                ),
                runtime.RecipeOperationDefinition(
                    kind="add_to_diagram",
                    artifact_key=shape_key,
                    parameters={
                        "diagram_id": {"ref": "use_case_diagram"},
                        "element_id": {"ref": key},
                        "x": 100,
                        "y": 100 + ((index - 1) * 120),
                    },
                ),
            ]
        )

    for index, use_case_name in enumerate(use_case_names, start=1):
        key = f"use_case_{index}"
        shape_key = f"{key}_shape"
        required_artifacts.append(
            runtime.ArtifactRequirement(
                key=key,
                kind="UseCase",
                name=use_case_name,
                parent_key="use_case_package",
            )
        )
        operations.extend(
            [
                runtime.RecipeOperationDefinition(
                    kind="create_element",
                    artifact_key=key,
                    parameters={
                        "type": "UseCase",
                        "name": use_case_name,
                        "parent_id": {"ref": "use_case_package"},
                    },
                ),
                runtime.RecipeOperationDefinition(
                    kind="set_usecase_subject",
                    parameters={
                        "element_id": {"ref": key},
                        "subject_ids": [{"ref": "subject_boundary"}],
                        "append": False,
                    },
                ),
                runtime.RecipeOperationDefinition(
                    kind="add_to_diagram",
                    artifact_key=shape_key,
                    parameters={
                        "diagram_id": {"ref": "use_case_diagram"},
                        "element_id": {"ref": key},
                        "container_presentation_id": {"ref": "subject_boundary_shape"},
                        "x": 360,
                        "y": 100 + ((index - 1) * 95),
                    },
                ),
            ]
        )
        relationship_requirements.append(
            runtime.RelationshipRequirement(
                relationship_type="Subject",
                source_key="subject_boundary",
                target_key=key,
                name="subject",
            )
        )

    for pair_index, (actor_key, use_case_key) in enumerate(_broadcast_pairs(
        [f"actor_{index}" for index in range(1, len(actor_names) + 1)],
        [f"use_case_{index}" for index in range(1, len(use_case_names) + 1)],
    ), start=1):
        relationship_key = f"association_{pair_index}"
        relationship_requirements.append(
            runtime.RelationshipRequirement(
                relationship_type="Association",
                source_key=actor_key,
                target_key=use_case_key,
                name="participates in",
            )
        )
        operations.append(
            runtime.RecipeOperationDefinition(
                kind="create_relationship",
                artifact_key=relationship_key,
                parameters={
                    "type": "Association",
                    "source_id": {"ref": actor_key},
                    "target_id": {"ref": use_case_key},
                    "name": "participates in",
                },
            )
        )
        operations.append(
            runtime.RecipeOperationDefinition(
                kind="add_diagram_paths",
                artifact_key=f"{relationship_key}_path",
                parameters={
                    "diagram_id": {"ref": "use_case_diagram"},
                    "paths": [
                        {
                            "relationshipId": {"ref": relationship_key},
                            "sourceShapeId": {"ref": f"{actor_key}_shape"},
                            "targetShapeId": {"ref": f"{use_case_key}_shape"},
                        }
                    ],
                },
            )
        )
        operations.append(
            runtime.RecipeOperationDefinition(
                kind="route_paths",
                parameters={
                    "diagram_id": {"ref": "use_case_diagram"},
                    "routes": [
                        {
                            "presentationId": {"ref": f"{relationship_key}_path"},
                            "resetLabels": True,
                        }
                    ],
                },
            )
        )

    return runtime.RecipeDefinition(
        recipe_id=recipe.id,
        name=recipe.title,
        phase=recipe.phase_id,
        description=recipe.goal,
        required_artifacts=tuple(required_artifacts),
        required_relationships=tuple(relationship_requirements),
        operations=tuple(operations),
        review_checklist=tuple(recipe.review_sections),
        evidence_sections=tuple(recipe.evidence_sections),
        layout_recipe=recipe.layout_profile,
        required_profiles=tuple(),
    )


def _build_use_case_subject_containment_recipe(
    pack_id: str,
    recipe: registry.ArtifactRecipe,
    params: Mapping[str, Any],
) -> runtime.RecipeDefinition:
    return _build_use_case_recipe(pack_id, recipe, params)


def _build_system_requirements_recipe(
    pack_id: str,
    recipe: registry.ArtifactRecipe,
    params: Mapping[str, Any],
) -> runtime.RecipeDefinition:
    system_name = str(params["system_name"])
    package_name = f"{system_name} Requirements"
    requirement_ids = _string_list(params.get("requirement_ids"))
    requirement_texts = _string_list(params.get("requirement_texts"))
    source_need_ids = _string_list(params.get("source_need_ids"))
    required_artifacts: list[runtime.ArtifactRequirement] = [
        runtime.ArtifactRequirement(key="workspace", kind="Package"),
        runtime.ArtifactRequirement(
            key="requirements_package",
            kind="Package",
            name=package_name,
            parent_key="workspace",
        ),
        runtime.ArtifactRequirement(
            key="requirements_diagram",
            kind="SysML Requirement Diagram",
            name=package_name,
            parent_key="requirements_package",
        ),
    ]
    operations: list[runtime.RecipeOperationDefinition] = [
        runtime.RecipeOperationDefinition(
            kind="create_element",
            artifact_key="requirements_package",
            parameters={
                "type": "Package",
                "name": package_name,
                "parent_id": {"ref": "workspace"},
            },
        ),
        runtime.RecipeOperationDefinition(
            kind="create_diagram",
            artifact_key="requirements_diagram",
            parameters={
                "type": "SysML Requirement Diagram",
                "name": package_name,
                "parent_id": {"ref": "requirements_package"},
            },
        ),
    ]
    relationship_requirements: list[runtime.RelationshipRequirement] = []
    requirement_keys: list[str] = []
    for index, requirement_id in enumerate(_coalesce_requirement_ids(requirement_ids, requirement_texts), start=1):
        key = f"requirement_{index}"
        requirement_keys.append(key)
        requirement_text = requirement_texts[index - 1] if index - 1 < len(requirement_texts) else requirement_id
        required_artifacts.append(
            runtime.ArtifactRequirement(
                key=key,
                kind="Requirement",
                name=requirement_id,
                parent_key="requirements_package",
            )
        )
        operations.extend(
            [
                runtime.RecipeOperationDefinition(
                    kind="create_element",
                    artifact_key=key,
                    parameters={
                        "type": "Requirement",
                        "name": requirement_id,
                        "parent_id": {"ref": "requirements_package"},
                        "documentation": requirement_text,
                    },
                ),
                runtime.RecipeOperationDefinition(
                    kind="add_to_diagram",
                    parameters={
                        "diagram_id": {"ref": "requirements_diagram"},
                        "element_id": {"ref": key},
                        "x": 180,
                        "y": 80 + ((index - 1) * 110),
                    },
                ),
            ]
        )
        if index - 1 < len(source_need_ids):
            need_key = f"source_need_{index}"
            relationship_requirements.append(
                runtime.RelationshipRequirement(
                    relationship_type="Refine",
                    source_key=need_key,
                    target_key=key,
                    name="refines",
                )
            )
            operations.append(
                runtime.RecipeOperationDefinition(
                    kind="create_relationship",
                    parameters={
                        "type": "Refine",
                        "source_id": source_need_ids[index - 1],
                        "target_id": {"ref": key},
                        "name": "refines",
                    },
                )
            )
    semantic_validations = ()
    if requirement_keys:
        semantic_validations = (
            runtime.SemanticValidationDefinition(
                validator_id="requirement_quality",
                parameters={
                    "requirement_ids": [{"ref": key} for key in requirement_keys],
                    "require_id": True,
                    "require_measurement": True,
                    "min_text_length": 20,
                },
            ),
        )
    return runtime.RecipeDefinition(
        recipe_id=recipe.id,
        name=recipe.title,
        phase=recipe.phase_id,
        description=recipe.goal,
        required_artifacts=tuple(required_artifacts),
        required_relationships=tuple(relationship_requirements),
        operations=tuple(operations),
        review_checklist=tuple(recipe.review_sections),
        evidence_sections=tuple(recipe.evidence_sections),
        layout_recipe=recipe.layout_profile,
        required_profiles=tuple(),
        semantic_validations=semantic_validations,
    )


def _build_architecture_recipe(
    pack_id: str,
    recipe: registry.ArtifactRecipe,
    params: Mapping[str, Any],
) -> runtime.RecipeDefinition:
    architecture_name = str(params["architecture_name"])
    package_name = f"{architecture_name} Architecture"
    block_names = _string_list(params.get("block_names"))
    allocation_targets = _string_list(params.get("allocation_targets"))
    required_artifacts: list[runtime.ArtifactRequirement] = [
        runtime.ArtifactRequirement(key="workspace", kind="Package"),
        runtime.ArtifactRequirement(
            key="architecture_package",
            kind="Package",
            name=package_name,
            parent_key="workspace",
        ),
        runtime.ArtifactRequirement(
            key="architecture_bdd",
            kind="SysML Block Definition Diagram",
            name=package_name,
            parent_key="architecture_package",
        ),
    ]
    operations: list[runtime.RecipeOperationDefinition] = [
        runtime.RecipeOperationDefinition(
            kind="create_element",
            artifact_key="architecture_package",
            parameters={
                "type": "Package",
                "name": package_name,
                "parent_id": {"ref": "workspace"},
            },
        ),
        runtime.RecipeOperationDefinition(
            kind="create_diagram",
            artifact_key="architecture_bdd",
            parameters={
                "type": "SysML Block Definition Diagram",
                "name": package_name,
                "parent_id": {"ref": "architecture_package"},
            },
        ),
    ]
    relationship_requirements: list[runtime.RelationshipRequirement] = []
    for index, block_name in enumerate(block_names, start=1):
        key = f"block_{index}"
        required_artifacts.append(
            runtime.ArtifactRequirement(
                key=key,
                kind="Block",
                name=block_name,
                parent_key="architecture_package",
            )
        )
        operations.extend(
            [
                runtime.RecipeOperationDefinition(
                    kind="create_element",
                    artifact_key=key,
                    parameters={
                        "type": "Block",
                        "name": block_name,
                        "parent_id": {"ref": "architecture_package"},
                    },
                ),
                runtime.RecipeOperationDefinition(
                    kind="add_to_diagram",
                    parameters={
                        "diagram_id": {"ref": "architecture_bdd"},
                        "element_id": {"ref": key},
                        "x": 180 + ((index - 1) * 180),
                        "y": 160,
                    },
                ),
            ]
        )
        if index - 1 < len(allocation_targets):
            target_id = allocation_targets[index - 1]
            operations.append(
                runtime.RecipeOperationDefinition(
                    kind="create_relationship",
                    parameters={
                        "type": "Satisfy",
                        "source_id": target_id,
                        "target_id": {"ref": key},
                        "name": "satisfies",
                    },
                )
            )
    return runtime.RecipeDefinition(
        recipe_id=recipe.id,
        name=recipe.title,
        phase=recipe.phase_id,
        description=recipe.goal,
        required_artifacts=tuple(required_artifacts),
        required_relationships=tuple(relationship_requirements),
        operations=tuple(operations),
        review_checklist=tuple(recipe.review_sections),
        evidence_sections=tuple(recipe.evidence_sections),
        layout_recipe=recipe.layout_profile,
        required_profiles=tuple(),
    )


def _build_logical_activity_flow_recipe(
    pack_id: str,
    recipe: registry.ArtifactRecipe,
    params: Mapping[str, Any],
) -> runtime.RecipeDefinition:
    activity_name = str(params["activity_name"])
    package_name = f"{activity_name} Activity"
    performer_names = _string_list(params.get("performer_names")) or [f"{activity_name} Performer"]
    action_names = _string_list(params.get("action_names")) or [
        f"Capture {activity_name} Request",
        f"Perform {activity_name}",
        f"Confirm {activity_name} Outcome",
    ]

    required_artifacts: list[runtime.ArtifactRequirement] = [
        runtime.ArtifactRequirement(key="workspace", kind="Package"),
        runtime.ArtifactRequirement(
            key="logical_activity_package",
            kind="Package",
            name=package_name,
            parent_key="workspace",
        ),
        runtime.ArtifactRequirement(
            key="logical_activity",
            kind="Activity",
            name=activity_name,
            parent_key="logical_activity_package",
        ),
        runtime.ArtifactRequirement(
            key="logical_activity_diagram",
            kind="Activity Diagram",
            name=package_name,
            parent_key="logical_activity",
        ),
    ]
    operations: list[runtime.RecipeOperationDefinition] = [
        runtime.RecipeOperationDefinition(
            kind="create_element",
            artifact_key="logical_activity_package",
            parameters={
                "type": "Package",
                "name": package_name,
                "parent_id": {"ref": "workspace"},
            },
        ),
        runtime.RecipeOperationDefinition(
            kind="create_element",
            artifact_key="logical_activity",
            parameters={
                "type": "Activity",
                "name": activity_name,
                "parent_id": {"ref": "logical_activity_package"},
            },
        ),
        runtime.RecipeOperationDefinition(
            kind="create_diagram",
            artifact_key="logical_activity_diagram",
            parameters={
                "type": "Activity Diagram",
                "name": package_name,
                "parent_id": {"ref": "logical_activity"},
            },
        ),
    ]

    lane_height = max(240, 140 + (len(action_names) * 90))
    performer_count = max(len(performer_names), 1)
    lane_width = 220
    action_shape_keys: list[str] = []
    partition_visual_operations: list[runtime.RecipeOperationDefinition] = []

    for index, performer_name in enumerate(performer_names, start=1):
        performer_key = f"performer_{index}"
        partition_key = f"partition_{index}"
        partition_shape_key = f"{partition_key}_shape"
        lane_x = 80 + ((index - 1) * lane_width)

        operations.extend(
            [
                runtime.RecipeOperationDefinition(
                    kind="create_element",
                    artifact_key=performer_key,
                    parameters={
                        "type": "Block",
                        "name": performer_name,
                        "parent_id": {"ref": "logical_activity_package"},
                    },
                ),
                runtime.RecipeOperationDefinition(
                    kind="create_element",
                    artifact_key=partition_key,
                    parameters={
                        "type": "ActivityPartition",
                        "name": performer_name,
                        "parent_id": {"ref": "logical_activity"},
                        "represents_id": {"ref": performer_key},
                    },
                ),
                runtime.RecipeOperationDefinition(
                    kind="add_to_diagram",
                    artifact_key=partition_shape_key,
                    parameters={
                        "diagram_id": {"ref": "logical_activity_diagram"},
                        "element_id": {"ref": partition_key},
                        "x": lane_x,
                        "y": 80,
                        "width": lane_width,
                        "height": lane_height,
                    },
                ),
            ],
        )
        partition_visual_operations.append(operations.pop())

    operations.extend(partition_visual_operations)

    operations.extend(
        [
            runtime.RecipeOperationDefinition(
                kind="create_element",
                artifact_key="initial_node",
                parameters={
                    "type": "InitialNode",
                    "name": "Start",
                    "parent_id": {"ref": "logical_activity"},
                },
            ),
            runtime.RecipeOperationDefinition(
                kind="create_element",
                artifact_key="activity_final",
                parameters={
                    "type": "ActivityFinalNode",
                    "name": "Done",
                    "parent_id": {"ref": "logical_activity"},
                },
            ),
                runtime.RecipeOperationDefinition(
                    kind="add_to_diagram",
                    artifact_key="initial_node_shape",
                    parameters={
                        "diagram_id": {"ref": "logical_activity_diagram"},
                        "element_id": {"ref": "initial_node"},
                        "x": 104,
                        "y": 112,
                    },
                ),
                runtime.RecipeOperationDefinition(
                    kind="add_to_diagram",
                    artifact_key="activity_final_shape",
                    parameters={
                        "diagram_id": {"ref": "logical_activity_diagram"},
                        "element_id": {"ref": "activity_final"},
                        "x": 80 + ((performer_count - 1) * lane_width) + 150,
                        "y": 124 + ((max(len(action_names), 1) - 1) * 80),
                    },
                ),
            ]
    )

    for index, action_name in enumerate(action_names, start=1):
        action_key = f"action_{index}"
        action_shape_key = f"{action_key}_shape"
        action_shape_keys.append(action_shape_key)
        lane_index = (index - 1) % performer_count
        row_index = (index - 1) // performer_count
        lane_x = 80 + (lane_index * lane_width)

        operations.extend(
            [
                runtime.RecipeOperationDefinition(
                    kind="create_element",
                    artifact_key=action_key,
                    parameters={
                        "type": "OpaqueAction",
                        "name": action_name,
                        "parent_id": {"ref": "logical_activity"},
                    },
                ),
                runtime.RecipeOperationDefinition(
                    kind="add_to_diagram",
                    artifact_key=action_shape_key,
                    parameters={
                        "diagram_id": {"ref": "logical_activity_diagram"},
                        "element_id": {"ref": action_key},
                        "x": lane_x + 56,
                        "y": 164 + (row_index * 90),
                        "width": 140,
                        "height": 48,
                    },
                ),
            ]
        )

    flow_source_keys = ["initial_node"] + [f"action_{index}" for index in range(1, len(action_names) + 1)]
    flow_target_keys = [f"action_{index}" for index in range(1, len(action_names) + 1)] + ["activity_final"]
    flow_source_shape_keys = ["initial_node_shape"] + action_shape_keys
    flow_target_shape_keys = action_shape_keys + ["activity_final_shape"]

    for index, (source_key, target_key, source_shape_key, target_shape_key) in enumerate(
        zip(flow_source_keys, flow_target_keys, flow_source_shape_keys, flow_target_shape_keys),
        start=1,
    ):
        flow_key = f"control_flow_{index}"
        path_key = f"{flow_key}_path"
        operations.extend(
            [
                runtime.RecipeOperationDefinition(
                    kind="create_relationship",
                    artifact_key=flow_key,
                    parameters={
                        "type": "ControlFlow",
                        "source_id": {"ref": source_key},
                        "target_id": {"ref": target_key},
                    },
                ),
                runtime.RecipeOperationDefinition(
                    kind="add_diagram_paths",
                    artifact_key=path_key,
                    parameters={
                        "diagram_id": {"ref": "logical_activity_diagram"},
                        "paths": [
                            {
                                "relationshipId": {"ref": flow_key},
                                "sourceShapeId": {"ref": source_shape_key},
                                "targetShapeId": {"ref": target_shape_key},
                            }
                        ],
                    },
                ),
                runtime.RecipeOperationDefinition(
                    kind="route_paths",
                    parameters={
                        "diagram_id": {"ref": "logical_activity_diagram"},
                        "routes": [
                            {
                                "presentationId": {"ref": path_key},
                                "resetLabels": True,
                            }
                        ],
                    },
                ),
            ]
        )

    return runtime.RecipeDefinition(
        recipe_id=recipe.id,
        name=recipe.title,
        phase=recipe.phase_id,
        description=recipe.goal,
        required_artifacts=tuple(required_artifacts),
        required_relationships=(),
        operations=tuple(operations),
        review_checklist=tuple(recipe.review_sections),
        evidence_sections=tuple(recipe.evidence_sections),
        layout_recipe=recipe.layout_profile,
        required_profiles=tuple(),
        semantic_validations=(
            runtime.SemanticValidationDefinition(
                validator_id="activity_flow_semantics",
                parameters={
                    "diagram_id": {"ref": "logical_activity_diagram"},
                    "max_partition_depth": 1,
                    "allow_stereotype_partition_labels": False,
                },
            ),
        ),
    )


def _build_logical_port_bdd_recipe(
    pack_id: str,
    recipe: registry.ArtifactRecipe,
    params: Mapping[str, Any],
) -> runtime.RecipeDefinition:
    system_name = str(params["system_name"])
    package_name = f"{system_name} Ports"
    interface_definitions = _interface_definitions(params.get("interface_definitions")) or [
        {
            "name": f"{system_name} Port Type",
            "port_name": _default_port_name(system_name),
            "flow_properties": [
                {"name": "Request", "direction": "in"},
                {"name": "Response", "direction": "out"},
            ],
        }
    ]

    required_artifacts: list[runtime.ArtifactRequirement] = [
        runtime.ArtifactRequirement(key="workspace", kind="Package"),
        runtime.ArtifactRequirement(
            key="logical_port_package",
            kind="Package",
            name=package_name,
            parent_key="workspace",
        ),
        runtime.ArtifactRequirement(
            key="logical_port_system",
            kind="Block",
            name=system_name,
            parent_key="logical_port_package",
        ),
        runtime.ArtifactRequirement(
            key="logical_port_bdd",
            kind="SysML Block Definition Diagram",
            name=package_name,
            parent_key="logical_port_package",
        ),
    ]
    operations: list[runtime.RecipeOperationDefinition] = [
        runtime.RecipeOperationDefinition(
            kind="create_element",
            artifact_key="logical_port_package",
            parameters={
                "type": "Package",
                "name": package_name,
                "parent_id": {"ref": "workspace"},
            },
        ),
        runtime.RecipeOperationDefinition(
            kind="create_element",
            artifact_key="logical_port_system",
            parameters={
                "type": "Block",
                "name": system_name,
                "parent_id": {"ref": "logical_port_package"},
            },
        ),
        runtime.RecipeOperationDefinition(
            kind="create_diagram",
            artifact_key="logical_port_bdd",
            parameters={
                "type": "SysML Block Definition Diagram",
                "name": package_name,
                "parent_id": {"ref": "logical_port_package"},
            },
        ),
        runtime.RecipeOperationDefinition(
            kind="add_to_diagram",
            artifact_key="logical_port_system_shape",
            parameters={
                "diagram_id": {"ref": "logical_port_bdd"},
                "element_id": {"ref": "logical_port_system"},
                "x": 360,
                "y": 140,
                "width": 320,
                "height": max(220, 120 + (len(interface_definitions) * 80)),
            },
        ),
        runtime.RecipeOperationDefinition(
            kind="set_shape_compartments",
            parameters={
                "diagram_id": {"ref": "logical_port_bdd"},
                "presentation_id": {"ref": "logical_port_system_shape"},
                "compartments": {
                    "properties": True,
                    "ports": True,
                    "operations": False,
                    "attributes": False,
                    "stereotype": False,
                },
            },
        ),
    ]

    interface_keys: list[str] = []
    for index, interface_definition in enumerate(interface_definitions, start=1):
        interface_key = f"interface_block_{index}"
        interface_shape_key = f"{interface_key}_shape"
        interface_keys.append(interface_key)
        x_position = 100 if index % 2 else 760
        y_position = 100 + ((index - 1) * 140)

        operations.extend(
            [
                runtime.RecipeOperationDefinition(
                    kind="create_element",
                    artifact_key=interface_key,
                    parameters={
                        "type": "InterfaceBlock",
                        "name": interface_definition["name"],
                        "parent_id": {"ref": "logical_port_package"},
                    },
                ),
                runtime.RecipeOperationDefinition(
                    kind="add_to_diagram",
                    artifact_key=interface_shape_key,
                    parameters={
                        "diagram_id": {"ref": "logical_port_bdd"},
                        "element_id": {"ref": interface_key},
                        "x": x_position,
                        "y": y_position,
                        "width": 220,
                        "height": max(120, 70 + (len(interface_definition["flow_properties"]) * 26)),
                    },
                ),
            ]
        )

        for flow_index, flow_property in enumerate(interface_definition["flow_properties"], start=1):
            flow_property_key = f"{interface_key}_flow_property_{flow_index}"
            operations.extend(
                [
                    runtime.RecipeOperationDefinition(
                        kind="create_element",
                        artifact_key=flow_property_key,
                        parameters={
                            "type": "FlowProperty",
                            "name": flow_property["name"],
                            "parent_id": {"ref": interface_key},
                        },
                    ),
                    runtime.RecipeOperationDefinition(
                        kind="set_specification",
                        artifact_key=flow_property_key,
                        parameters={
                            "element_id": {"ref": flow_property_key},
                            "properties": {"direction": flow_property["direction"]},
                        },
                    ),
                ]
            )

        port_key = f"system_port_{index}"
        port_shape_key = f"{port_key}_shape"
        port_y = 36 + ((index - 1) * 52)
        port_x = 12 if index % 2 else 272
        operations.extend(
            [
                runtime.RecipeOperationDefinition(
                    kind="create_element",
                    artifact_key=port_key,
                    parameters={
                        "type": "Port",
                        "name": interface_definition["port_name"],
                        "parent_id": {"ref": "logical_port_system"},
                    },
                ),
                runtime.RecipeOperationDefinition(
                    kind="set_specification",
                    artifact_key=port_key,
                    parameters={
                        "element_id": {"ref": port_key},
                        "properties": {"type": {"id": {"ref": interface_key}}},
                    },
                ),
                runtime.RecipeOperationDefinition(
                    kind="add_to_diagram",
                    artifact_key=port_shape_key,
                    parameters={
                        "diagram_id": {"ref": "logical_port_bdd"},
                        "element_id": {"ref": port_key},
                        "container_presentation_id": {"ref": "logical_port_system_shape"},
                        "x": port_x,
                        "y": port_y,
                        "width": 28,
                        "height": 18,
                    },
                ),
            ]
        )

    return runtime.RecipeDefinition(
        recipe_id=recipe.id,
        name=recipe.title,
        phase=recipe.phase_id,
        description=recipe.goal,
        required_artifacts=tuple(required_artifacts),
        required_relationships=(),
        operations=tuple(operations),
        review_checklist=tuple(recipe.review_sections),
        evidence_sections=tuple(recipe.evidence_sections),
        layout_recipe=recipe.layout_profile,
        required_profiles=tuple(),
        semantic_validations=(
            runtime.SemanticValidationDefinition(
                validator_id="port_boundary_consistency",
                parameters={
                    "interface_block_ids": [{"ref": key} for key in interface_keys],
                },
            ),
        ),
    )


def _build_logical_ibd_traceability_recipe(
    pack_id: str,
    recipe: registry.ArtifactRecipe,
    params: Mapping[str, Any],
) -> runtime.RecipeDefinition:
    context_name = str(params["context_name"])
    package_name = f"{context_name} Context"
    activity_diagram_id = _optional_str(params.get("activity_diagram_id"))
    interface_block_ids = [str(item) for item in params.get("interface_block_ids") or () if str(item)]
    part_names = _string_list(params.get("part_names"))
    flow_names = _string_list(params.get("flow_names"))

    if not part_names:
        part_names = [f"{context_name} External System"] if not flow_names else [
            f"{context_name} External System {index}" for index in range(1, len(flow_names) + 1)
        ]
    if not flow_names:
        flow_names = [f"{part_name} Exchange" for part_name in part_names]

    required_artifacts: list[runtime.ArtifactRequirement] = [
        runtime.ArtifactRequirement(key="workspace", kind="Package"),
        runtime.ArtifactRequirement(
            key="logical_context_package",
            kind="Package",
            name=package_name,
            parent_key="workspace",
        ),
        runtime.ArtifactRequirement(
            key="logical_context_block",
            kind="Block",
            name=context_name,
            parent_key="logical_context_package",
        ),
        runtime.ArtifactRequirement(
            key="logical_context_ibd",
            kind="SysML Internal Block Diagram",
            name=package_name,
            parent_key="logical_context_block",
        ),
    ]
    operations: list[runtime.RecipeOperationDefinition] = [
        runtime.RecipeOperationDefinition(
            kind="create_element",
            artifact_key="logical_context_package",
            parameters={
                "type": "Package",
                "name": package_name,
                "parent_id": {"ref": "workspace"},
            },
        ),
        runtime.RecipeOperationDefinition(
            kind="create_element",
            artifact_key="logical_context_block",
            parameters={
                "type": "Block",
                "name": context_name,
                "parent_id": {"ref": "logical_context_package"},
            },
        ),
        runtime.RecipeOperationDefinition(
            kind="create_diagram",
            artifact_key="logical_context_ibd",
            parameters={
                "type": "SysML Internal Block Diagram",
                "name": package_name,
                "parent_id": {"ref": "logical_context_block"},
            },
        ),
        runtime.RecipeOperationDefinition(
            kind="add_to_diagram",
            artifact_key="logical_context_shape",
            parameters={
                "diagram_id": {"ref": "logical_context_ibd"},
                "element_id": {"ref": "logical_context_block"},
                "x": 300,
                "y": 120,
                "width": 420,
                "height": max(260, 150 + (len(part_names) * 90)),
            },
        ),
        runtime.RecipeOperationDefinition(
            kind="set_shape_compartments",
            parameters={
                "diagram_id": {"ref": "logical_context_ibd"},
                "presentation_id": {"ref": "logical_context_shape"},
                "compartments": {
                    "properties": True,
                    "ports": True,
                    "operations": False,
                    "attributes": False,
                    "stereotype": False,
                },
            },
        ),
    ]

    connector_refs: list[tuple[str, str, str, str]] = []
    part_count = max(len(part_names), 1)
    for index, part_name in enumerate(part_names, start=1):
        external_block_key = f"external_block_{index}"
        part_key = f"context_part_{index}"
        part_shape_key = f"{part_key}_shape"
        context_port_key = f"context_port_{index}"
        external_port_key = f"external_port_{index}"
        context_port_shape_key = f"{context_port_key}_shape"
        external_port_shape_key = f"{external_port_key}_shape"
        connector_key = f"context_connector_{index}"
        interface_block_id = interface_block_ids[(index - 1) % len(interface_block_ids)] if interface_block_ids else None

        part_y = 30 + ((index - 1) * 76)
        context_port_y = 40 + ((index - 1) * 60)
        context_port_x = 360
        external_port_x = 150

        operations.extend(
            [
                runtime.RecipeOperationDefinition(
                    kind="create_element",
                    artifact_key=external_block_key,
                    parameters={
                        "type": "Block",
                        "name": part_name,
                        "parent_id": {"ref": "logical_context_package"},
                    },
                ),
                runtime.RecipeOperationDefinition(
                    kind="create_element",
                    artifact_key=part_key,
                    parameters={
                        "type": "Property",
                        "name": part_name,
                        "parent_id": {"ref": "logical_context_block"},
                    },
                ),
                runtime.RecipeOperationDefinition(
                    kind="set_specification",
                    artifact_key=part_key,
                    parameters={
                        "element_id": {"ref": part_key},
                        "properties": {"type": {"id": {"ref": external_block_key}}},
                    },
                ),
                runtime.RecipeOperationDefinition(
                    kind="add_to_diagram",
                    artifact_key=part_shape_key,
                    parameters={
                        "diagram_id": {"ref": "logical_context_ibd"},
                        "element_id": {"ref": part_key},
                        "container_presentation_id": {"ref": "logical_context_shape"},
                        "x": 24,
                        "y": part_y,
                        "width": 180,
                        "height": 56,
                    },
                ),
                runtime.RecipeOperationDefinition(
                    kind="create_element",
                    artifact_key=context_port_key,
                    parameters={
                        "type": "Port",
                        "name": f"{_default_port_name(part_name)}_context",
                        "parent_id": {"ref": "logical_context_block"},
                    },
                ),
                runtime.RecipeOperationDefinition(
                    kind="create_element",
                    artifact_key=external_port_key,
                    parameters={
                        "type": "Port",
                        "name": _default_port_name(part_name),
                        "parent_id": {"ref": external_block_key},
                    },
                ),
            ]
        )

        if interface_block_id is not None:
            operations.extend(
                [
                    runtime.RecipeOperationDefinition(
                        kind="set_specification",
                        artifact_key=context_port_key,
                        parameters={
                            "element_id": {"ref": context_port_key},
                            "properties": {"type": {"id": interface_block_id}},
                        },
                    ),
                    runtime.RecipeOperationDefinition(
                        kind="set_specification",
                        artifact_key=external_port_key,
                        parameters={
                            "element_id": {"ref": external_port_key},
                            "properties": {"type": {"id": interface_block_id}},
                        },
                    ),
                ]
            )

        operations.extend(
            [
                runtime.RecipeOperationDefinition(
                    kind="add_to_diagram",
                    artifact_key=context_port_shape_key,
                    parameters={
                        "diagram_id": {"ref": "logical_context_ibd"},
                        "element_id": {"ref": context_port_key},
                        "container_presentation_id": {"ref": "logical_context_shape"},
                        "x": context_port_x,
                        "y": context_port_y,
                        "width": 28,
                        "height": 18,
                    },
                ),
                runtime.RecipeOperationDefinition(
                    kind="add_to_diagram",
                    artifact_key=external_port_shape_key,
                    parameters={
                        "diagram_id": {"ref": "logical_context_ibd"},
                        "element_id": {"ref": external_port_key},
                        "container_presentation_id": {"ref": part_shape_key},
                        "x": external_port_x,
                        "y": 18,
                        "width": 28,
                        "height": 18,
                    },
                ),
                runtime.RecipeOperationDefinition(
                    kind="create_relationship",
                    artifact_key=connector_key,
                    parameters={
                        "type": "Connector",
                        "name": f"{part_name} Connector",
                        "source_id": {"ref": context_port_key},
                        "target_id": {"ref": external_port_key},
                        "owner_id": {"ref": "logical_context_block"},
                        "target_part_with_port_id": {"ref": part_key},
                    },
                ),
                runtime.RecipeOperationDefinition(
                    kind="add_diagram_paths",
                    artifact_key=f"{connector_key}_path",
                    parameters={
                        "diagram_id": {"ref": "logical_context_ibd"},
                        "paths": [
                            {
                                "relationshipId": {"ref": connector_key},
                                "sourceShapeId": {"ref": context_port_shape_key},
                                "targetShapeId": {"ref": external_port_shape_key},
                            }
                        ],
                    },
                ),
                runtime.RecipeOperationDefinition(
                    kind="route_paths",
                    parameters={
                        "diagram_id": {"ref": "logical_context_ibd"},
                        "routes": [
                            {
                                "presentationId": {"ref": f"{connector_key}_path"},
                                "resetLabels": True,
                            }
                        ],
                    },
                ),
            ]
        )

        connector_refs.append((connector_key, context_port_key, external_port_key, part_key))

    for index, flow_name in enumerate(flow_names, start=1):
        connector_key, context_port_key, external_port_key, _ = connector_refs[(index - 1) % len(connector_refs)]
        information_flow_key = f"information_flow_{index}"
        operations.extend(
            [
                runtime.RecipeOperationDefinition(
                    kind="create_relationship",
                    artifact_key=information_flow_key,
                    parameters={
                        "type": "InformationFlow",
                        "name": flow_name,
                        "source_id": {"ref": context_port_key},
                        "target_id": {"ref": external_port_key},
                        "owner_id": {"ref": "logical_context_package"},
                        "realizing_connector_id": {"ref": connector_key},
                    },
                ),
                runtime.RecipeOperationDefinition(
                    kind="add_diagram_paths",
                    artifact_key=f"{information_flow_key}_path",
                    parameters={
                        "diagram_id": {"ref": "logical_context_ibd"},
                        "paths": [
                            {
                                "relationshipId": {"ref": information_flow_key},
                                "sourceShapeId": {"ref": f"{context_port_key}_shape"},
                                "targetShapeId": {"ref": f"{external_port_key}_shape"},
                            }
                        ],
                    },
                ),
                runtime.RecipeOperationDefinition(
                    kind="route_paths",
                    parameters={
                        "diagram_id": {"ref": "logical_context_ibd"},
                        "routes": [
                            {
                                "presentationId": {"ref": f"{information_flow_key}_path"},
                                "resetLabels": True,
                            }
                        ],
                    },
                ),
            ]
        )

    semantic_validations: tuple[runtime.SemanticValidationDefinition, ...] = ()
    if activity_diagram_id:
        semantic_parameters: dict[str, Any] = {
            "activity_diagram_id": activity_diagram_id,
            "ibd_diagram_id": {"ref": "logical_context_ibd"},
        }
        if interface_block_ids:
            semantic_parameters["interface_block_ids"] = interface_block_ids
        semantic_validations = (
            runtime.SemanticValidationDefinition(
                validator_id="cross_diagram_traceability",
                parameters=semantic_parameters,
            ),
        )

    return runtime.RecipeDefinition(
        recipe_id=recipe.id,
        name=recipe.title,
        phase=recipe.phase_id,
        description=recipe.goal,
        required_artifacts=tuple(required_artifacts),
        required_relationships=(),
        operations=tuple(operations),
        review_checklist=tuple(recipe.review_sections),
        evidence_sections=tuple(recipe.evidence_sections),
        layout_recipe=recipe.layout_profile,
        required_profiles=tuple(),
        semantic_validations=semantic_validations,
    )


def _build_requirements_to_architecture_recipe(
    pack_id: str,
    recipe: registry.ArtifactRecipe,
    params: Mapping[str, Any],
) -> runtime.RecipeDefinition:
    architecture_name = str(params["architecture_name"])
    package_name = f"{architecture_name} Allocation"
    requirement_ids = _string_list(params.get("requirement_ids"))
    block_names = _string_list(params.get("block_names"))
    required_artifacts: list[runtime.ArtifactRequirement] = [
        runtime.ArtifactRequirement(key="workspace", kind="Package"),
        runtime.ArtifactRequirement(
            key="allocation_package",
            kind="Package",
            name=package_name,
            parent_key="workspace",
        ),
        runtime.ArtifactRequirement(
            key="allocation_bdd",
            kind="SysML Block Definition Diagram",
            name=package_name,
            parent_key="allocation_package",
        ),
    ]
    operations: list[runtime.RecipeOperationDefinition] = [
        runtime.RecipeOperationDefinition(
            kind="create_element",
            artifact_key="allocation_package",
            parameters={
                "type": "Package",
                "name": package_name,
                "parent_id": {"ref": "workspace"},
            },
        ),
        runtime.RecipeOperationDefinition(
            kind="create_diagram",
            artifact_key="allocation_bdd",
            parameters={
                "type": "SysML Block Definition Diagram",
                "name": package_name,
                "parent_id": {"ref": "allocation_package"},
            },
        ),
    ]
    relationship_requirements: list[runtime.RelationshipRequirement] = []
    requirement_ref_keys: list[str] = []
    allocated_block_keys: list[str] = []

    for index, requirement_id in enumerate(requirement_ids, start=1):
        requirement_ref_keys.append(f"requirement_ref_{index}")
        required_artifacts.append(
            runtime.ArtifactRequirement(
                key=f"requirement_ref_{index}",
                kind="Requirement",
                name=requirement_id,
            )
        )

    for index, block_name in enumerate(block_names, start=1):
        block_key = f"allocated_block_{index}"
        allocated_block_keys.append(block_key)
        required_artifacts.append(
            runtime.ArtifactRequirement(
                key=block_key,
                kind="Block",
                name=block_name,
                parent_key="allocation_package",
            )
        )
        operations.extend(
            [
                runtime.RecipeOperationDefinition(
                    kind="create_element",
                    artifact_key=block_key,
                    parameters={
                        "type": "Block",
                        "name": block_name,
                        "parent_id": {"ref": "allocation_package"},
                    },
                ),
                runtime.RecipeOperationDefinition(
                    kind="add_to_diagram",
                    artifact_key=f"{block_key}_shape",
                    parameters={
                        "diagram_id": {"ref": "allocation_bdd"},
                        "element_id": {"ref": block_key},
                        "x": 160 + ((index - 1) * 220),
                        "y": 160,
                    },
                ),
            ]
        )
        if index - 1 < len(requirement_ids):
            requirement_key = f"requirement_ref_{index}"
            relationship_requirements.append(
                runtime.RelationshipRequirement(
                    relationship_type="Satisfy",
                    source_key=block_key,
                    target_key=requirement_key,
                    name="satisfies",
                )
            )
            operations.append(
                runtime.RecipeOperationDefinition(
                    kind="create_relationship",
                    artifact_key=f"satisfy_{index}",
                    parameters={
                        "type": "Satisfy",
                        "source_id": {"ref": block_key},
                        "target_id": requirement_ids[index - 1],
                        "name": "satisfies",
                    },
                )
            )
    semantic_validations = ()
    if requirement_ref_keys and allocated_block_keys:
        semantic_validations = (
            runtime.SemanticValidationDefinition(
                validator_id="requirements_to_architecture_trace",
                parameters={
                    "requirement_ids": [{"ref": key} for key in requirement_ref_keys],
                    "architecture_element_ids": [{"ref": key} for key in allocated_block_keys],
                },
            ),
        )
    return runtime.RecipeDefinition(
        recipe_id=recipe.id,
        name=recipe.title,
        phase=recipe.phase_id,
        description=recipe.goal,
        required_artifacts=tuple(required_artifacts),
        required_relationships=tuple(relationship_requirements),
        operations=tuple(operations),
        review_checklist=tuple(recipe.review_sections),
        evidence_sections=tuple(recipe.evidence_sections),
        layout_recipe=recipe.layout_profile,
        required_profiles=tuple(),
        semantic_validations=semantic_validations,
    )


def _build_verification_recipe(
    pack_id: str,
    recipe: registry.ArtifactRecipe,
    params: Mapping[str, Any],
) -> runtime.RecipeDefinition:
    verification_name = str(params["verification_name"])
    package_name = f"{verification_name} Verification"
    requirement_ids = _string_list(params.get("requirement_ids"))
    verification_methods = _string_list(params.get("verification_methods"))
    required_artifacts: list[runtime.ArtifactRequirement] = [
        runtime.ArtifactRequirement(key="workspace", kind="Package"),
        runtime.ArtifactRequirement(
            key="verification_package",
            kind="Package",
            name=package_name,
            parent_key="workspace",
        ),
    ]
    operations: list[runtime.RecipeOperationDefinition] = [
        runtime.RecipeOperationDefinition(
            kind="create_element",
            artifact_key="verification_package",
            parameters={
                "type": "Package",
                "name": package_name,
                "parent_id": {"ref": "workspace"},
            },
        ),
    ]
    relationship_requirements: list[runtime.RelationshipRequirement] = []
    for index, requirement_id in enumerate(requirement_ids, start=1):
        method = verification_methods[index - 1] if index - 1 < len(verification_methods) else "analysis"
        key = f"verification_case_{index}"
        case_name = f"Verify {requirement_id}"
        required_artifacts.append(
            runtime.ArtifactRequirement(
                key=key,
                kind="Constraint",
                name=case_name,
                parent_key="verification_package",
            )
        )
        operations.append(
            runtime.RecipeOperationDefinition(
                kind="create_element",
                artifact_key=key,
                parameters={
                    "type": "Constraint",
                    "name": case_name,
                    "parent_id": {"ref": "verification_package"},
                    "documentation": f"Verification method: {method}",
                },
            )
        )
        relationship_requirements.append(
            runtime.RelationshipRequirement(
                relationship_type="Verify",
                source_key=key,
                target_key=f"requirement_ref_{index}",
                name=method,
            )
        )
        operations.append(
            runtime.RecipeOperationDefinition(
                kind="create_relationship",
                parameters={
                    "type": "Verify",
                    "source_id": {"ref": key},
                    "target_id": requirement_id,
                    "name": method,
                },
            )
        )
    return runtime.RecipeDefinition(
        recipe_id=recipe.id,
        name=recipe.title,
        phase=recipe.phase_id,
        description=recipe.goal,
        required_artifacts=tuple(required_artifacts),
        required_relationships=tuple(relationship_requirements),
        operations=tuple(operations),
        review_checklist=tuple(recipe.review_sections),
        evidence_sections=tuple(recipe.evidence_sections),
        layout_recipe=recipe.layout_profile,
        required_profiles=tuple(),
    )


def _build_uaf_operational_activity_recipe(
    pack_id: str,
    recipe: registry.ArtifactRecipe,
    params: Mapping[str, Any],
) -> runtime.RecipeDefinition:
    activity_name = str(params["activity_name"])
    package_name = f"{activity_name} Operational View"
    action_names = _string_list(params.get("action_names"))
    required_artifacts: list[runtime.ArtifactRequirement] = [
        runtime.ArtifactRequirement(key="workspace", kind="Package"),
        runtime.ArtifactRequirement(
            key="uaf_operational_package",
            kind="Package",
            name=package_name,
            parent_key="workspace",
        ),
        runtime.ArtifactRequirement(
            key="uaf_operational_diagram",
            kind="Activity Diagram",
            name=package_name,
            parent_key="uaf_operational_package",
        ),
    ]
    operations: list[runtime.RecipeOperationDefinition] = [
        runtime.RecipeOperationDefinition(
            kind="create_element",
            artifact_key="uaf_operational_package",
            parameters={
                "type": "Package",
                "name": package_name,
                "parent_id": {"ref": "workspace"},
            },
        ),
        runtime.RecipeOperationDefinition(
            kind="create_diagram",
            artifact_key="uaf_operational_diagram",
            parameters={
                "type": "Activity Diagram",
                "name": package_name,
                "parent_id": {"ref": "uaf_operational_package"},
            },
        ),
    ]
    for index, action_name in enumerate(action_names, start=1):
        key = f"uaf_action_{index}"
        required_artifacts.append(
            runtime.ArtifactRequirement(
                key=key,
                kind="Activity",
                name=action_name,
                parent_key="uaf_operational_package",
            )
        )
        operations.extend(
            [
                runtime.RecipeOperationDefinition(
                    kind="create_element",
                    artifact_key=key,
                    parameters={
                        "type": "Activity",
                        "name": action_name,
                        "parent_id": {"ref": "uaf_operational_package"},
                    },
                ),
                runtime.RecipeOperationDefinition(
                    kind="add_to_diagram",
                    artifact_key=f"{key}_shape",
                    parameters={
                        "diagram_id": {"ref": "uaf_operational_diagram"},
                        "element_id": {"ref": key},
                        "x": 120 + ((index - 1) * 180),
                        "y": 140,
                    },
                ),
            ]
        )

    return runtime.RecipeDefinition(
        recipe_id=recipe.id,
        name=recipe.title,
        phase=recipe.phase_id,
        description=recipe.goal,
        required_artifacts=tuple(required_artifacts),
        required_relationships=(),
        operations=tuple(operations),
        review_checklist=tuple(recipe.review_sections),
        evidence_sections=tuple(recipe.evidence_sections),
        layout_recipe=recipe.layout_profile,
        required_profiles=tuple(),
    )


def _materialize_parameters(
    definitions: Sequence[registry.RecipeParameter],
    provided: Mapping[str, Any],
    *,
    strict: bool,
) -> dict[str, Any]:
    values: dict[str, Any] = {}
    for definition in definitions:
        if definition.name in provided:
            values[definition.name] = provided[definition.name]
        elif definition.default is not None:
            values[definition.name] = definition.default
        elif definition.required:
            if strict:
                raise ValueError(f"Missing required recipe parameter: {definition.name}")
            values[definition.name] = f"<{definition.name}>"
    for key, value in provided.items():
        values.setdefault(key, value)
    return values


def _string_list(value: Any) -> list[str]:
    if not value:
        return []
    if isinstance(value, str):
        return [value]
    return [str(item) for item in value]


def _default_port_name(value: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9]+", "_", value).strip("_").lower()
    return normalized or "port"


def _normalize_flow_property_direction(value: Any) -> str:
    direction = _default_port_name(str(value or "out")).replace("_", "")
    if direction in {"in", "input", "incoming", "receive", "required"}:
        return "in"
    if direction in {"out", "output", "outgoing", "send", "provided"}:
        return "out"
    if direction in {"inout", "bidirectional", "both"}:
        return "inout"
    return "out"


def _interface_definitions(value: Any) -> list[dict[str, Any]]:
    if not value:
        return []
    if isinstance(value, Mapping) or isinstance(value, str):
        raw_items = [value]
    else:
        raw_items = list(value)

    normalized: list[dict[str, Any]] = []
    for index, raw_item in enumerate(raw_items, start=1):
        if isinstance(raw_item, Mapping):
            name = _optional_str(raw_item.get("name")) or f"Interface {index}"
            port_name = _optional_str(raw_item.get("port_name") or raw_item.get("portName")) or _default_port_name(name)
            raw_flow_properties = (
                raw_item.get("flow_properties")
                or raw_item.get("flowProperties")
                or ()
            )
        else:
            name = str(raw_item)
            port_name = _default_port_name(name)
            raw_flow_properties = ()

        if isinstance(raw_flow_properties, Mapping) or isinstance(raw_flow_properties, str):
            flow_property_items = [raw_flow_properties]
        else:
            flow_property_items = list(raw_flow_properties)

        flow_properties: list[dict[str, str]] = []
        for flow_index, raw_flow_property in enumerate(flow_property_items, start=1):
            if isinstance(raw_flow_property, Mapping):
                flow_name = _optional_str(
                    raw_flow_property.get("name") or raw_flow_property.get("label")
                ) or f"Flow {flow_index}"
                direction = _normalize_flow_property_direction(raw_flow_property.get("direction"))
            else:
                flow_name = str(raw_flow_property)
                direction = "out"
            flow_properties.append({"name": flow_name, "direction": direction})

        normalized.append(
            {
                "name": name,
                "port_name": port_name,
                "flow_properties": flow_properties,
            }
        )
    return normalized


def _coalesce_requirement_ids(
    requirement_ids: Sequence[str],
    requirement_texts: Sequence[str],
) -> list[str]:
    if requirement_ids:
        return list(requirement_ids)
    if not requirement_texts:
        return []
    return [f"REQ-{index:03d}" for index in range(1, len(requirement_texts) + 1)]


def _broadcast_pairs(left: Sequence[str], right: Sequence[str]) -> list[tuple[str, str]]:
    if not left or not right:
        return []
    if len(left) == 1:
        return [(left[0], item) for item in right]
    if len(right) == 1:
        return [(item, right[0]) for item in left]
    if len(left) == len(right):
        return list(zip(left, right))
    return [(left[index % len(left)], item) for index, item in enumerate(right)]


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text if text else None


def _preferred_live_kind(existing_kind: str, live_kind: Any) -> str:
    live_text = _optional_str(live_kind) or existing_kind
    live_normalized = re.sub(r"\s+", "", live_text).lower()
    existing_normalized = re.sub(r"\s+", "", existing_kind).lower()
    if live_normalized == "diagram" and "diagram" in existing_normalized:
        return existing_kind
    if live_normalized == "model" and existing_normalized == "package":
        return existing_kind
    return live_text


def _root_package_id(
    recipe_parameters: Mapping[str, Any],
    artifacts: Sequence[runtime.ArtifactSnapshot],
) -> str | None:
    root_package_id = _optional_str(recipe_parameters.get("root_package_id"))
    if root_package_id is not None:
        return root_package_id
    for artifact in artifacts:
        if artifact.key == "workspace" and artifact.element_id:
            return artifact.element_id
    return None


async def _discover_live_artifacts(
    recipe: runtime.RecipeDefinition,
    artifacts: Sequence[runtime.ArtifactSnapshot],
    *,
    recipe_parameters: Mapping[str, Any],
    root_package_id: str | None,
    bridge: Any,
) -> list[runtime.ArtifactSnapshot]:
    artifact_index = {artifact.key: artifact for artifact in artifacts}
    workspace_id = root_package_id or _root_package_id(recipe_parameters, artifacts)
    if workspace_id and "workspace" not in artifact_index:
        artifact_index["workspace"] = runtime.ArtifactSnapshot(
            key="workspace",
            kind="Package",
            name="Workspace",
            element_id=workspace_id,
        )

    for _ in range(3):
        changed = False
        bindings = {key: artifact.element_id for key, artifact in artifact_index.items() if artifact.element_id}
        for requirement in recipe.required_artifacts:
            existing = artifact_index.get(requirement.key)
            if existing is not None and existing.element_id:
                continue
            discovered = await _find_live_artifact(
                requirement,
                bindings=bindings,
                workspace_id=workspace_id,
                bridge=bridge,
            )
            if discovered is not None:
                artifact_index[requirement.key] = discovered
                changed = True
        if not changed:
            break

    return await _hydrate_live_artifacts(list(artifact_index.values()), bridge=bridge)


async def _find_live_artifact(
    requirement: runtime.ArtifactRequirement,
    *,
    bindings: Mapping[str, str | None],
    workspace_id: str | None,
    bridge: Any,
) -> runtime.ArtifactSnapshot | None:
    if requirement.key == "workspace" and workspace_id:
        return runtime.ArtifactSnapshot(
            key="workspace",
            kind="Package",
            name="Workspace",
            element_id=workspace_id,
        )

    parent_id = None
    if requirement.parent_key is not None:
        parent_id = bindings.get(requirement.parent_key)
    if parent_id is None:
        parent_id = workspace_id

    if _is_diagram_kind(requirement.kind):
        diagram = await _find_live_diagram(
            requirement= requirement,
            parent_id=parent_id,
            bridge=bridge,
            bindings=bindings,
        )
        if diagram is not None:
            return diagram
        return None

    result = await _safe_bridge_call(
        bridge,
        "query_elements",
        type=_query_type(requirement.kind),
        name=requirement.name,
        package=parent_id,
        recursive=True,
        limit=10,
        view="full",
    )
    for element in (result or {}).get("elements", ()):
        if requirement.name is not None and _optional_str(element.get("name")) != requirement.name:
            continue
        if parent_id is not None and _optional_str(element.get("ownerId")) not in {parent_id, None}:
            continue
        return runtime.ArtifactSnapshot(
            key=requirement.key,
            kind=str(element.get("humanType") or element.get("type") or requirement.kind),
            name=str(element.get("name") or requirement.name or requirement.key),
            element_id=_optional_str(element.get("id")),
            parent_key=requirement.parent_key,
            stereotypes=tuple(str(item) for item in element.get("stereotypes", ())),
        )
    return None


async def _find_live_diagram(
    *,
    requirement: runtime.ArtifactRequirement,
    parent_id: str | None,
    bridge: Any,
    bindings: Mapping[str, str | None],
) -> runtime.ArtifactSnapshot | None:
    result = await _safe_bridge_call(bridge, "list_diagrams")
    for diagram in (result or {}).get("diagrams", ()):
        if requirement.name is not None and _optional_str(diagram.get("name")) != requirement.name:
            continue
        if parent_id is not None and _optional_str(diagram.get("ownerId")) not in {parent_id, None}:
            continue
        if not _kind_matches(
            str(diagram.get("type") or ""),
            requirement.kind,
        ):
            continue
        return runtime.ArtifactSnapshot(
            key=requirement.key,
            kind=str(diagram.get("type") or requirement.kind),
            name=str(diagram.get("name") or requirement.name or requirement.key),
            element_id=_optional_str(diagram.get("id")),
            parent_key=requirement.parent_key,
        )
    return None


async def _hydrate_live_artifacts(
    artifacts: Sequence[runtime.ArtifactSnapshot],
    *,
    bridge: Any,
) -> list[runtime.ArtifactSnapshot]:
    bindings = {artifact.key: artifact.element_id for artifact in artifacts if artifact.element_id}
    reverse_bindings = {value: key for key, value in bindings.items() if value}
    hydrated: list[runtime.ArtifactSnapshot] = []

    for artifact in artifacts:
        if artifact.element_id is None:
            hydrated.append(artifact)
            continue

        element = await _safe_bridge_call(bridge, "get_element", artifact.element_id)
        spec = await _safe_bridge_call(bridge, "get_specification", artifact.element_id)
        properties = dict(artifact.properties)
        properties.update(dict((spec or {}).get("properties", {})))
        if spec and spec.get("constraints"):
            properties["constraints"] = dict(spec["constraints"])
        subject_ids = [
            _optional_str(item.get("id"))
            for item in properties.get("subject", ())
            if isinstance(item, Mapping)
        ]
        subject_ids = [item for item in subject_ids if item]
        if subject_ids:
            properties["subject_ids"] = subject_ids

        relationships = tuple(
            _unique_relationships(
                list(artifact.relationships)
                + await _collect_live_relationships(
                    artifact_key=artifact.key,
                    element_id=artifact.element_id,
                    reverse_bindings=reverse_bindings,
                    properties=properties,
                    bridge=bridge,
                )
            )
        )

        hydrated.append(
            runtime.ArtifactSnapshot(
                key=artifact.key,
                kind=_preferred_live_kind(
                    artifact.kind,
                    (element or {}).get("humanType") or (element or {}).get("type"),
                ),
                name=str((element or {}).get("name") or artifact.name),
                element_id=artifact.element_id,
                parent_key=artifact.parent_key
                or reverse_bindings.get(_optional_str((element or {}).get("ownerId")) or ""),
                stereotypes=tuple(
                    str(item) for item in (element or {}).get("stereotypes", artifact.stereotypes)
                ),
                properties=properties,
                relationships=relationships,
            )
        )

    return hydrated


async def _collect_live_relationships(
    *,
    artifact_key: str,
    element_id: str,
    reverse_bindings: Mapping[str, str],
    properties: Mapping[str, Any],
    bridge: Any,
) -> list[runtime.RelationshipSnapshot]:
    response = await _safe_bridge_call(bridge, "get_relationships", element_id)
    snapshots: list[runtime.RelationshipSnapshot] = []
    for bucket in ("outgoing", "incoming", "undirected"):
        for relationship in (response or {}).get(bucket, ()):
            relationship_id = _optional_str(relationship.get("relationshipId"))
            name = _optional_str(relationship.get("name"))
            relationship_type = str(relationship.get("type") or relationship.get("relationshipType") or "")
            sources = relationship.get("sources", ())
            targets = relationship.get("targets", ())
            for source in sources:
                source_key = reverse_bindings.get(str(source.get("id") or ""))
                if source_key is None:
                    continue
                for target in targets:
                    target_key = reverse_bindings.get(str(target.get("id") or ""))
                    if target_key is None:
                        continue
                    snapshots.append(
                        runtime.RelationshipSnapshot(
                            relationship_type=relationship_type,
                            source_key=source_key,
                            target_key=target_key,
                            relationship_id=relationship_id,
                            name=name,
                        )
                    )

    for subject_id in properties.get("subject_ids", ()):
        subject_key = reverse_bindings.get(str(subject_id))
        if subject_key is None:
            continue
        snapshots.append(
            runtime.RelationshipSnapshot(
                relationship_type="Subject",
                source_key=subject_key,
                target_key=artifact_key,
                name="subject",
            )
        )
    return _unique_relationships(snapshots)


def _unique_relationships(
    relationships: Sequence[runtime.RelationshipSnapshot],
) -> list[runtime.RelationshipSnapshot]:
    unique: dict[tuple[str, str, str, str], runtime.RelationshipSnapshot] = {}
    for relationship in relationships:
        unique[
            (
                relationship.relationship_type.lower(),
                relationship.source_key.lower(),
                relationship.target_key.lower(),
                _optional_str(relationship.name or "") or "",
            )
        ] = relationship
    return list(unique.values())


def _is_diagram_kind(kind: str) -> bool:
    return "diagram" in kind.lower() or kind.lower() in {"bdd", "ibd"}


def _query_type(kind: str) -> str:
    kind_map = {
        "sysml block definition diagram": "Diagram",
        "sysml internal block diagram": "Diagram",
        "sysml requirement diagram": "Diagram",
        "use case diagram": "Diagram",
        "block": "Class",
    }
    return kind_map.get(kind.lower(), kind)


def _kind_matches(actual: str, expected: str) -> bool:
    actual_normalized = actual.lower().replace("_", " ").replace("-", " ")
    expected_normalized = expected.lower().replace("_", " ").replace("-", " ")
    return actual_normalized == expected_normalized or actual_normalized.endswith(expected_normalized)


async def _safe_bridge_call(bridge: Any, method_name: str, *args: Any, **kwargs: Any) -> Any:
    method = getattr(bridge, method_name, None)
    if method is None:
        return None
    try:
        result = method(*args, **kwargs)
        if hasattr(result, "__await__"):
            return await result
        return result
    except Exception:
        return None


def _diagram_ids_for_evidence(bindings: Mapping[str, str]) -> tuple[str, ...]:
    return tuple(
        binding
        for key, binding in bindings.items()
        if binding and ("diagram" in key.lower() or key.lower().endswith("_bdd") or key.lower().endswith("_ibd"))
    )


async def _capture_diagram_snapshots(
    diagram_ids: Sequence[str],
    bridge: Any,
) -> list[dict[str, Any]]:
    snapshots: list[dict[str, Any]] = []
    for diagram_id in sorted(set(diagram_ids)):
        if not diagram_id:
            continue
        image = await _safe_bridge_call(bridge, "get_diagram_image", diagram_id)
        shapes = await _safe_bridge_call(bridge, "list_diagram_shapes", diagram_id)
        if image is None and shapes is None:
            continue
        snapshot = {"diagramId": diagram_id}
        if image is not None:
            snapshot["image"] = image
        if shapes is not None:
            snapshot["shapes"] = shapes
        snapshots.append(snapshot)
    return snapshots


async def _run_semantic_validations(
    recipe: runtime.RecipeDefinition,
    artifacts: Sequence[runtime.ArtifactSnapshot],
    *,
    bridge: Any,
) -> list[dict[str, Any]]:
    if not recipe.semantic_validations:
        return []

    bindings = {
        artifact.key: artifact.element_id
        for artifact in artifacts
        if artifact.element_id
    }
    results: list[dict[str, Any]] = []
    for definition in recipe.semantic_validations:
        validator_id = definition.validator_id
        try:
            resolved_parameters = runtime._resolve_value(definition.parameters, bindings)
        except KeyError as exc:
            results.append(
                {
                    "validatorId": validator_id,
                    "ok": False,
                    "checks": [
                        {
                            "name": "binding-resolution",
                            "ok": False,
                            "details": {"message": str(exc)},
                        }
                    ],
                }
            )
            continue

        try:
            result = await _invoke_semantic_validator(
                validator_id,
                resolved_parameters,
                bridge=bridge,
            )
        except Exception as exc:
            results.append(
                {
                    "validatorId": validator_id,
                    "ok": False,
                    "checks": [
                        {
                            "name": "execution",
                            "ok": False,
                            "details": {"message": str(exc)},
                        }
                    ],
                }
            )
            continue

        normalized = dict(result)
        normalized.setdefault("validatorId", validator_id)
        results.append(normalized)
    return results


async def _invoke_semantic_validator(
    validator_id: str,
    parameters: Mapping[str, Any],
    *,
    bridge: Any,
) -> dict[str, Any]:
    if validator_id == "activity_flow_semantics":
        return await verify_activity_flow_semantics_for_diagram(
            str(parameters["diagram_id"]),
            max_partition_depth=int(parameters.get("max_partition_depth", 1)),
            allow_stereotype_partition_labels=bool(
                parameters.get("allow_stereotype_partition_labels", False)
            ),
            bridge=bridge,
        )
    if validator_id == "port_boundary_consistency":
        return await verify_port_boundary_consistency_for_interfaces(
            parameters.get("interface_block_ids") or (),
            allow_shared_flow_property_names=parameters.get("allow_shared_flow_property_names"),
            bridge=bridge,
        )
    if validator_id == "requirement_quality":
        return await verify_requirement_quality_for_ids(
            parameters.get("requirement_ids") or (),
            require_id=bool(parameters.get("require_id", True)),
            require_measurement=bool(parameters.get("require_measurement", True)),
            min_text_length=int(parameters.get("min_text_length", 20)),
            bridge=bridge,
        )
    if validator_id == "cross_diagram_traceability":
        return await run_cross_diagram_traceability(
            activity_diagram_id=_optional_str(parameters.get("activity_diagram_id")),
            interface_block_ids=parameters.get("interface_block_ids") or (),
            ibd_diagram_id=_optional_str(parameters.get("ibd_diagram_id")),
            requirement_ids=parameters.get("requirement_ids") or (),
            architecture_element_ids=parameters.get("architecture_element_ids") or (),
            bridge=bridge,
        )
    if validator_id == "requirements_to_architecture_trace":
        return await run_cross_diagram_traceability(
            requirement_ids=parameters.get("requirement_ids") or (),
            architecture_element_ids=parameters.get("architecture_element_ids") or (),
            bridge=bridge,
        )
    raise ValueError(f"Unsupported semantic validator: {validator_id}")


async def _build_bridge_evidence(
    artifacts: Sequence[runtime.ArtifactSnapshot],
    execution_result: runtime.RecipeExecutionResult,
    *,
    before_diagram_ids: Sequence[str],
    before_snapshots: Sequence[Mapping[str, Any]],
    after_diagram_ids: Sequence[str],
    semantic_validations: Sequence[Mapping[str, Any]],
    bridge: Any,
) -> dict[str, Any]:
    created_element_ids: list[str] = []
    created_relationship_ids: list[str] = []
    created_presentation_ids: list[str] = []
    for receipt in execution_result.receipts:
        result = receipt.result
        if "presentationId" in result:
            created_presentation_ids.append(str(result["presentationId"]))
        elif "diagramId" in result and receipt.operation_kind == "create_diagram":
            created_element_ids.append(str(result["diagramId"]))
        elif "id" in result:
            if receipt.operation_kind == "create_relationship":
                created_relationship_ids.append(str(result["id"]))
            else:
                created_element_ids.append(str(result["id"]))

    return {
        "createdElementIds": created_element_ids,
        "createdRelationshipIds": created_relationship_ids,
        "createdPresentationIds": created_presentation_ids,
        "receipts": [receipt.result for receipt in execution_result.receipts],
        "liveArtifacts": [runtime._to_plain(artifact) for artifact in artifacts],
        "semanticValidations": list(semantic_validations),
        "diagramSnapshots": {
            "before": list(before_snapshots),
            "after": await _capture_diagram_snapshots(after_diagram_ids, bridge),
        },
    }


def _render_review_packet(
    pack: registry.PackDefinition,
    bundle: runtime.EvidenceBundle,
) -> str:
    conformance = bundle.conformance
    lines = [
        f"# {pack.title} Review Packet",
        "",
        f"- Pack: `{bundle.pack_id}`",
        f"- Recipe: `{bundle.recipe_id}`",
        f"- Generated: `{bundle.generated_at}`",
        f"- Conformance: `{'PASS' if conformance.passed else 'FAIL'}` ({conformance.summary})",
        "",
        "## Artifact Keys",
    ]
    lines.extend(f"- `{artifact_key}`" for artifact_key in bundle.artifact_keys or ("none",))
    lines.extend(
        [
            "",
            "## Workflow Guidance",
            f"- Phase: `{bundle.guidance.phase}`",
            f"- Ready To Execute: `{bundle.guidance.ready_to_execute}`",
            f"- Missing Artifacts: {', '.join(bundle.guidance.missing_artifact_keys) or 'none'}",
            "",
            "## Bridge Evidence",
            f"- Created Elements: {len(bundle.bridge_evidence.get('createdElementIds', ())) if bundle.bridge_evidence else 0}",
            f"- Created Relationships: {len(bundle.bridge_evidence.get('createdRelationshipIds', ())) if bundle.bridge_evidence else 0}",
            f"- Created Presentations: {len(bundle.bridge_evidence.get('createdPresentationIds', ())) if bundle.bridge_evidence else 0}",
            f"- Diagram Snapshots: {len((bundle.bridge_evidence.get('diagramSnapshots', {}) or {}).get('after', ())) if bundle.bridge_evidence else 0}",
            "",
            "## Findings",
        ]
    )
    if conformance.findings:
        lines.extend(
            f"- `{finding.severity}` {finding.rule_id}: {finding.message}"
            for finding in conformance.findings
        )
    else:
        lines.append("- No findings.")
    semantic_validations = (bundle.bridge_evidence.get("semanticValidations") if bundle.bridge_evidence else ()) or ()
    if semantic_validations:
        semantic_passed = sum(1 for validation in semantic_validations if validation.get("ok"))
        semantic_failed = len(semantic_validations) - semantic_passed
        lines.extend(
            [
                "",
                "## Semantic Validation",
                f"- Validators Run: {len(semantic_validations)}",
                f"- Passed: {semantic_passed}",
                f"- Failed: {semantic_failed}",
            ]
        )
        for validation in semantic_validations:
            validator_id = str(validation.get("validatorId") or validation.get("validationId") or "semantic")
            failed_checks = [
                str(check.get("name"))
                for check in validation.get("checks", ())
                if isinstance(check, Mapping) and not check.get("ok")
            ]
            status = "PASS" if validation.get("ok") else "FAIL"
            lines.append(
                f"- `{validator_id}`: `{status}`"
                + (f" ({', '.join(failed_checks)})" if failed_checks else "")
            )
            if failed_checks:
                for check in validation.get("checks", ()):
                    if not isinstance(check, Mapping) or check.get("ok"):
                        continue
                    details = check.get("details")
                    if not isinstance(details, Mapping):
                        continue
                    highlights = []
                    for key in (
                        "missing",
                        "missingIdIds",
                        "blankTextIds",
                        "weakTextIds",
                        "missingPortTerms",
                        "missingIbdTerms",
                        "missingRequirementTraceIds",
                        "isolatedActionIds",
                        "unreachableActionIds",
                    ):
                        value = details.get(key)
                        if value:
                            highlights.append(f"{key}={value}")
                    if highlights:
                        lines.append(f"  - `{check.get('name')}` details: " + "; ".join(highlights))
    if bundle.assumptions:
        lines.extend(["", "## Assumptions"])
        lines.extend(f"- {assumption}" for assumption in bundle.assumptions)
    return "\n".join(lines)
