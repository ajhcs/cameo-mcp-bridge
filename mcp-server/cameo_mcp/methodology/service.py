"""High-level methodology services built on top of the bridge client."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from cameo_mcp import client as default_bridge_client

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
    after_diagram_ids = _diagram_ids_for_evidence(result.artifact_bindings)
    bridge_evidence = await _build_bridge_evidence(
        current_artifacts,
        result,
        before_diagram_ids=before_diagram_ids,
        before_snapshots=before_snapshots,
        after_diagram_ids=after_diagram_ids,
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
    return {
        "pack": pack.to_dict(),
        "recipe": _registry_recipe_dict(pack_id, recipe_id),
        "workflowGuidance": guidance.to_dict(),
        "conformance": conformance.to_dict(),
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
    bridge_evidence = await _build_bridge_evidence(
        artifacts,
        empty_result,
        before_diagram_ids=_diagram_ids_for_evidence(plan.artifact_bindings),
        before_snapshots=await _capture_diagram_snapshots(
            _diagram_ids_for_evidence(plan.artifact_bindings),
            bridge,
        ),
        after_diagram_ids=_diagram_ids_for_evidence(plan.artifact_bindings),
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
    for index, requirement_id in enumerate(_coalesce_requirement_ids(requirement_ids, requirement_texts), start=1):
        key = f"requirement_{index}"
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

    for index, requirement_id in enumerate(requirement_ids, start=1):
        required_artifacts.append(
            runtime.ArtifactRequirement(
                key=f"requirement_ref_{index}",
                kind="Requirement",
                name=requirement_id,
            )
        )

    for index, block_name in enumerate(block_names, start=1):
        block_key = f"allocated_block_{index}"
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
                kind=str((element or {}).get("humanType") or (element or {}).get("type") or artifact.kind),
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


async def _build_bridge_evidence(
    artifacts: Sequence[runtime.ArtifactSnapshot],
    execution_result: runtime.RecipeExecutionResult,
    *,
    before_diagram_ids: Sequence[str],
    before_snapshots: Sequence[Mapping[str, Any]],
    after_diagram_ids: Sequence[str],
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
    if bundle.assumptions:
        lines.extend(["", "## Assumptions"])
        lines.extend(f"- {assumption}" for assumption in bundle.assumptions)
    return "\n".join(lines)
