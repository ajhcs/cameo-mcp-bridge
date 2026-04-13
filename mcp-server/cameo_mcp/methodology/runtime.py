from __future__ import annotations

import inspect
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Mapping, Protocol, Sequence


def _normalize_name(value: str | None) -> str:
    return (value or "").strip().lower()


def _as_tuple(values: Sequence[str] | None) -> tuple[str, ...]:
    return tuple(values or ())


def _to_plain(value: Any) -> Any:
    if hasattr(value, "__dataclass_fields__"):
        return {key: _to_plain(item) for key, item in asdict(value).items()}
    if isinstance(value, dict):
        return {key: _to_plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_to_plain(item) for item in value]
    return value


def _resolve_value(value: Any, bindings: Mapping[str, str]) -> Any:
    if isinstance(value, Mapping):
        if "ref" in value and len(value) == 1:
            ref = str(value["ref"])
            if ref not in bindings:
                raise KeyError(f"Unknown artifact binding: {ref}")
            return bindings[ref]
        return {key: _resolve_value(item, bindings) for key, item in value.items()}
    if isinstance(value, list):
        return [_resolve_value(item, bindings) for item in value]
    if isinstance(value, tuple):
        return tuple(_resolve_value(item, bindings) for item in value)
    return value


def _matching_artifacts(
    completed_artifacts: Sequence["ArtifactSnapshot"],
) -> dict[str, "ArtifactSnapshot"]:
    return {artifact.key: artifact for artifact in completed_artifacts}


def _result_primary_id(result: Mapping[str, Any]) -> str | None:
    direct = result.get("id") or result.get("presentationId")
    if direct is not None:
        return str(direct)

    nested_element = result.get("element")
    if isinstance(nested_element, Mapping) and nested_element.get("id") is not None:
        return str(nested_element["id"])

    nested_relationship = result.get("relationship")
    if isinstance(nested_relationship, Mapping) and nested_relationship.get("id") is not None:
        return str(nested_relationship["id"])

    for entry in result.get("results", ()) if isinstance(result.get("results"), Sequence) else ():
        if isinstance(entry, Mapping):
            presentation_id = entry.get("presentationId")
            if presentation_id is not None:
                return str(presentation_id)
    diagram_id = result.get("diagramId")
    if diagram_id is not None:
        return str(diagram_id)
    return None


def _relationship_key(relationship: "RelationshipRequirement | RelationshipSnapshot") -> tuple[str, str, str, str]:
    return (
        _normalize_name(relationship.relationship_type),
        _normalize_name(relationship.source_key),
        _normalize_name(relationship.target_key),
        _normalize_name(getattr(relationship, "name", None)),
    )


@dataclass(frozen=True)
class ArtifactRequirement:
    key: str
    kind: str
    name: str | None = None
    parent_key: str | None = None
    stereotypes: tuple[str, ...] = ()
    properties: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RelationshipRequirement:
    relationship_type: str
    source_key: str
    target_key: str
    name: str | None = None
    required: bool = True


@dataclass(frozen=True)
class RelationshipSnapshot:
    relationship_type: str
    source_key: str
    target_key: str
    relationship_id: str | None = None
    name: str | None = None
    guard: str | None = None


@dataclass(frozen=True)
class ArtifactSnapshot:
    key: str
    kind: str
    name: str
    element_id: str | None = None
    parent_key: str | None = None
    stereotypes: tuple[str, ...] = ()
    properties: Mapping[str, Any] = field(default_factory=dict)
    relationships: tuple[RelationshipSnapshot, ...] = ()


@dataclass(frozen=True)
class RecipeOperationDefinition:
    kind: str
    artifact_key: str | None = None
    target_key: str | None = None
    parameters: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RecipeDefinition:
    recipe_id: str
    name: str
    phase: str
    description: str = ""
    required_artifacts: tuple[ArtifactRequirement, ...] = ()
    required_relationships: tuple[RelationshipRequirement, ...] = ()
    operations: tuple[RecipeOperationDefinition, ...] = ()
    review_checklist: tuple[str, ...] = ()
    evidence_sections: tuple[str, ...] = ()
    layout_recipe: str | None = None
    required_profiles: tuple[str, ...] = ()
    semantic_validations: tuple["SemanticValidationDefinition", ...] = ()

    def required_artifact_keys(self) -> tuple[str, ...]:
        return tuple(requirement.key for requirement in self.required_artifacts)


@dataclass(frozen=True)
class PackDefinition:
    pack_id: str
    name: str
    description: str = ""
    phases: tuple[str, ...] = ()
    recipes: tuple[RecipeDefinition, ...] = ()
    review_checklist: tuple[str, ...] = ()
    required_profiles: tuple[str, ...] = ()

    def recipe(self, recipe_id: str) -> RecipeDefinition:
        for recipe in self.recipes:
            if recipe.recipe_id == recipe_id:
                return recipe
        raise KeyError(f"Unknown recipe: {recipe_id}")

    def first_pending_recipe(
        self,
        completed_artifacts: Sequence[ArtifactSnapshot],
    ) -> RecipeDefinition | None:
        for recipe in self.recipes:
            if not _recipe_satisfied(recipe, completed_artifacts):
                return recipe
        return self.recipes[-1] if self.recipes else None


@dataclass(frozen=True)
class WorkflowGuidance:
    pack_id: str
    pack_name: str
    recipe_id: str
    recipe_name: str
    phase: str
    ready_to_execute: bool
    completion_ratio: float
    completed_artifact_keys: tuple[str, ...]
    missing_artifact_keys: tuple[str, ...]
    missing_relationships: tuple[str, ...]
    blockers: tuple[str, ...]
    recommended_actions: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return _to_plain(self)


@dataclass(frozen=True)
class PlannedOperation:
    step_id: str
    operation: RecipeOperationDefinition
    status: str
    reason: str | None = None
    resolved_parameters: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RecipeExecutionPlan:
    pack_id: str
    recipe_id: str
    recipe_name: str
    phase: str
    artifact_bindings: Mapping[str, str] = field(default_factory=dict)
    planned_operations: tuple[PlannedOperation, ...] = ()
    required_artifact_keys: tuple[str, ...] = ()
    missing_artifact_keys: tuple[str, ...] = ()
    required_relationships: tuple[RelationshipRequirement, ...] = ()
    ready_to_execute: bool = False
    notes: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return _to_plain(self)


@dataclass(frozen=True)
class OperationReceipt:
    step_id: str
    operation_kind: str
    status: str
    result: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RecipeExecutionResult:
    pack_id: str
    recipe_id: str
    recipe_name: str
    phase: str
    receipts: tuple[OperationReceipt, ...] = ()
    artifact_bindings: Mapping[str, str] = field(default_factory=dict)
    created_artifacts: tuple[ArtifactSnapshot, ...] = ()
    updated_artifacts: tuple[ArtifactSnapshot, ...] = ()
    notes: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return _to_plain(self)


@dataclass(frozen=True)
class ConformanceFinding:
    rule_id: str
    severity: str
    message: str
    artifact_key: str | None = None
    relationship_type: str | None = None


@dataclass(frozen=True)
class ConformanceReport:
    pack_id: str
    recipe_id: str
    passed: bool
    findings: tuple[ConformanceFinding, ...] = ()
    summary: str = ""

    def to_dict(self) -> dict[str, Any]:
        return _to_plain(self)


@dataclass(frozen=True)
class SemanticValidationDefinition:
    validator_id: str
    parameters: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return _to_plain(self)


@dataclass(frozen=True)
class EvidenceBundle:
    pack_id: str
    pack_name: str
    recipe_id: str
    recipe_name: str
    generated_at: str
    artifact_keys: tuple[str, ...]
    guidance: WorkflowGuidance
    execution_plan: RecipeExecutionPlan
    execution_result: RecipeExecutionResult
    conformance: ConformanceReport
    checklist: tuple[str, ...] = ()
    assumptions: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()
    bridge_evidence: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return _to_plain(self)


class BridgeClientProtocol(Protocol):
    async def create_element(self, **kwargs: Any) -> Mapping[str, Any]: ...

    async def create_relationship(self, **kwargs: Any) -> Mapping[str, Any]: ...

    async def create_diagram(self, **kwargs: Any) -> Mapping[str, Any]: ...

    async def add_to_diagram(self, **kwargs: Any) -> Mapping[str, Any]: ...

    async def add_diagram_paths(self, **kwargs: Any) -> Mapping[str, Any]: ...

    async def set_specification(self, **kwargs: Any) -> Mapping[str, Any]: ...

    async def set_shape_properties(self, **kwargs: Any) -> Mapping[str, Any]: ...

    async def set_shape_compartments(self, **kwargs: Any) -> Mapping[str, Any]: ...

    async def reparent_shapes(self, **kwargs: Any) -> Mapping[str, Any]: ...

    async def route_paths(self, **kwargs: Any) -> Mapping[str, Any]: ...

    async def apply_profile(self, **kwargs: Any) -> Mapping[str, Any]: ...

    async def apply_stereotype(self, **kwargs: Any) -> Mapping[str, Any]: ...

    async def set_usecase_subject(self, **kwargs: Any) -> Mapping[str, Any]: ...


def _recipe_satisfied(
    recipe: RecipeDefinition,
    completed_artifacts: Sequence[ArtifactSnapshot],
) -> bool:
    artifact_index = _matching_artifacts(completed_artifacts)
    return not _missing_artifact_requirements(recipe.required_artifacts, artifact_index)


def _missing_artifact_requirements(
    requirements: Sequence[ArtifactRequirement],
    artifact_index: Mapping[str, ArtifactSnapshot],
) -> tuple[ArtifactRequirement, ...]:
    missing: list[ArtifactRequirement] = []
    for requirement in requirements:
        artifact = artifact_index.get(requirement.key)
        if artifact is None:
            missing.append(requirement)
            continue
        if _normalize_name(artifact.kind) != _normalize_name(requirement.kind):
            missing.append(requirement)
            continue
        if requirement.name is not None and artifact.name != requirement.name:
            missing.append(requirement)
            continue
        if requirement.parent_key is not None and artifact.parent_key != requirement.parent_key:
            missing.append(requirement)
            continue
        if requirement.stereotypes and not set(requirement.stereotypes).issubset(set(artifact.stereotypes)):
            missing.append(requirement)
            continue
        for prop_name, expected_value in requirement.properties.items():
            if artifact.properties.get(prop_name) != expected_value:
                missing.append(requirement)
                break
    return tuple(missing)


def _missing_relationship_requirements(
    requirements: Sequence[RelationshipRequirement],
    artifacts: Sequence[ArtifactSnapshot],
) -> tuple[RelationshipRequirement, ...]:
    all_relationships: dict[tuple[str, str, str, str], RelationshipSnapshot] = {}
    for artifact in artifacts:
        for relationship in artifact.relationships:
            all_relationships[_relationship_key(relationship)] = relationship

    missing: list[RelationshipRequirement] = []
    for requirement in requirements:
        key = _relationship_key(requirement)
        if key not in all_relationships and requirement.required:
            missing.append(requirement)
    return tuple(missing)


def build_workflow_guidance(
    pack: PackDefinition,
    completed_artifacts: Sequence[ArtifactSnapshot],
    recipe_id: str | None = None,
) -> WorkflowGuidance:
    artifact_index = _matching_artifacts(completed_artifacts)
    recipe = pack.recipe(recipe_id) if recipe_id is not None else pack.first_pending_recipe(completed_artifacts)
    if recipe is None:
        raise ValueError("pack must contain at least one recipe")

    missing_artifacts = _missing_artifact_requirements(recipe.required_artifacts, artifact_index)
    missing_relationships = _missing_relationship_requirements(recipe.required_relationships, completed_artifacts)
    completed_keys = tuple(sorted(artifact_index))
    required_keys = recipe.required_artifact_keys()
    missing_keys = tuple(requirement.key for requirement in missing_artifacts)
    blockers = tuple(
        [f"missing artifact: {requirement.key}" for requirement in missing_artifacts]
        + [f"missing relationship: {requirement.relationship_type} {requirement.source_key}->{requirement.target_key}" for requirement in missing_relationships]
    )
    completion_ratio = 1.0 if not required_keys else round((len(required_keys) - len(missing_keys)) / len(required_keys), 3)
    recommended_actions = _recommended_actions(recipe, missing_artifacts, missing_relationships)

    return WorkflowGuidance(
        pack_id=pack.pack_id,
        pack_name=pack.name,
        recipe_id=recipe.recipe_id,
        recipe_name=recipe.name,
        phase=recipe.phase,
        ready_to_execute=not blockers,
        completion_ratio=completion_ratio,
        completed_artifact_keys=completed_keys,
        missing_artifact_keys=missing_keys,
        missing_relationships=tuple(
            f"{req.relationship_type}:{req.source_key}->{req.target_key}" for req in missing_relationships
        ),
        blockers=blockers,
        recommended_actions=recommended_actions,
    )


def _recommended_actions(
    recipe: RecipeDefinition,
    missing_artifacts: Sequence[ArtifactRequirement],
    missing_relationships: Sequence[RelationshipRequirement],
) -> tuple[str, ...]:
    actions: list[str] = []
    for requirement in missing_artifacts:
        action = f"create {requirement.kind} '{requirement.name or requirement.key}'"
        if requirement.parent_key is not None:
            action += f" under '{requirement.parent_key}'"
        actions.append(action)
    for requirement in missing_relationships:
        actions.append(
            f"create {requirement.relationship_type} from '{requirement.source_key}' to '{requirement.target_key}'"
        )
    if not actions:
        actions.extend(recipe.review_checklist or [f"Execute recipe '{recipe.name}'"])
    return tuple(actions)


def build_recipe_execution_plan(
    pack: PackDefinition,
    recipe_id: str,
    completed_artifacts: Sequence[ArtifactSnapshot],
) -> RecipeExecutionPlan:
    recipe = pack.recipe(recipe_id)
    artifact_index = _matching_artifacts(completed_artifacts)
    missing_artifacts = _missing_artifact_requirements(recipe.required_artifacts, artifact_index)
    missing_keys = {requirement.key for requirement in missing_artifacts}
    bindings = {artifact.key: artifact.element_id for artifact in completed_artifacts if artifact.element_id}

    planned_operations: list[PlannedOperation] = []
    for index, operation in enumerate(recipe.operations, start=1):
        target_key = operation.artifact_key or operation.target_key
        if target_key is not None and target_key in bindings and operation.kind.startswith("create_"):
            planned_operations.append(
                PlannedOperation(
                    step_id=f"{recipe.recipe_id}:{index}",
                    operation=operation,
                    status="skipped",
                    reason=f"artifact '{target_key}' already exists",
                    resolved_parameters=dict(operation.parameters),
                )
            )
            continue
        if target_key is not None and target_key in missing_keys and operation.kind.startswith("add_"):
            planned_operations.append(
                PlannedOperation(
                    step_id=f"{recipe.recipe_id}:{index}",
                    operation=operation,
                    status="pending",
                    reason=f"artifact '{target_key}' not yet satisfied",
                    resolved_parameters=dict(operation.parameters),
                )
            )
            continue
        planned_operations.append(
            PlannedOperation(
                step_id=f"{recipe.recipe_id}:{index}",
                operation=operation,
                status="pending",
                resolved_parameters=dict(operation.parameters),
            )
        )

    ready = not missing_artifacts
    notes = tuple(recipe.review_checklist)
    return RecipeExecutionPlan(
        pack_id=pack.pack_id,
        recipe_id=recipe.recipe_id,
        recipe_name=recipe.name,
        phase=recipe.phase,
        artifact_bindings=bindings,
        planned_operations=tuple(planned_operations),
        required_artifact_keys=recipe.required_artifact_keys(),
        missing_artifact_keys=tuple(requirement.key for requirement in missing_artifacts),
        required_relationships=recipe.required_relationships,
        ready_to_execute=ready,
        notes=notes,
    )


async def execute_recipe(
    plan: RecipeExecutionPlan,
    bridge: BridgeClientProtocol,
) -> RecipeExecutionResult:
    bindings = dict(plan.artifact_bindings)
    receipts: list[OperationReceipt] = []
    created_artifacts: list[ArtifactSnapshot] = []
    updated_artifacts: list[ArtifactSnapshot] = []

    for step in plan.planned_operations:
        if step.status == "skipped":
            receipts.append(
                OperationReceipt(
                    step_id=step.step_id,
                    operation_kind=step.operation.kind,
                    status="skipped",
                    result={"reason": step.reason},
                )
            )
            continue

        resolved_parameters = _resolve_value(step.resolved_parameters, bindings)
        result = await _invoke_operation(bridge, step.operation, resolved_parameters)
        receipt = OperationReceipt(
            step_id=step.step_id,
            operation_kind=step.operation.kind,
            status="applied",
            result=dict(result),
        )
        receipts.append(receipt)

        created_id = _result_primary_id(result)
        if step.operation.artifact_key and created_id is not None:
            bindings[step.operation.artifact_key] = str(created_id)
            created_artifacts.append(
                ArtifactSnapshot(
                    key=step.operation.artifact_key,
                    kind=str(
                        step.resolved_parameters.get(
                            "type",
                            "PresentationElement" if step.operation.kind == "add_to_diagram" else step.operation.kind,
                        )
                    ),
                    name=str(step.resolved_parameters.get("name", step.operation.artifact_key)),
                    element_id=str(created_id),
                )
            )
        if step.operation.kind == "set_specification" and step.operation.artifact_key:
            updated_artifacts.append(
                ArtifactSnapshot(
                    key=step.operation.artifact_key,
                    kind="specification",
                    name=step.operation.artifact_key,
                    element_id=bindings.get(step.operation.artifact_key),
                    properties=resolved_parameters.get("properties", {}),
                )
            )

    return RecipeExecutionResult(
        pack_id=plan.pack_id,
        recipe_id=plan.recipe_id,
        recipe_name=plan.recipe_name,
        phase=plan.phase,
        receipts=tuple(receipts),
        artifact_bindings=bindings,
        created_artifacts=tuple(created_artifacts),
        updated_artifacts=tuple(updated_artifacts),
        notes=plan.notes,
    )


async def _invoke_operation(
    bridge: BridgeClientProtocol,
    operation: RecipeOperationDefinition,
    parameters: Mapping[str, Any],
) -> Mapping[str, Any]:
    method_name = _operation_method_name(operation.kind)
    method = getattr(bridge, method_name, None)
    if method is None:
        raise AttributeError(f"Bridge client does not implement {method_name}()")
    call_kwargs = dict(parameters)
    result = method(**call_kwargs)
    if inspect.isawaitable(result):
        result = await result
    if not isinstance(result, Mapping):
        raise TypeError(f"{method_name}() must return a mapping, got {type(result)!r}")
    return result


def _operation_method_name(kind: str) -> str:
    mapping = {
        "create_element": "create_element",
        "create_relationship": "create_relationship",
        "create_diagram": "create_diagram",
        "add_to_diagram": "add_to_diagram",
        "add_diagram_paths": "add_diagram_paths",
        "set_specification": "set_specification",
        "set_shape_properties": "set_shape_properties",
        "set_shape_compartments": "set_shape_compartments",
        "reparent_shapes": "reparent_shapes",
        "route_paths": "route_paths",
        "apply_profile": "apply_profile",
        "apply_stereotype": "apply_stereotype",
        "set_usecase_subject": "set_usecase_subject",
    }
    if kind not in mapping:
        raise ValueError(f"Unsupported recipe operation: {kind}")
    return mapping[kind]


def run_conformance_checks(
    recipe: RecipeDefinition,
    current_artifacts: Sequence[ArtifactSnapshot],
    *,
    pack_id: str = "",
) -> ConformanceReport:
    artifact_index = _matching_artifacts(current_artifacts)
    findings: list[ConformanceFinding] = []

    for requirement in recipe.required_artifacts:
        artifact = artifact_index.get(requirement.key)
        if artifact is None:
            findings.append(
                ConformanceFinding(
                    rule_id=f"artifact:{requirement.key}",
                    severity="error",
                    message=f"Missing required artifact '{requirement.key}'",
                    artifact_key=requirement.key,
                )
            )
            continue
        if _normalize_name(artifact.kind) != _normalize_name(requirement.kind):
            findings.append(
                ConformanceFinding(
                    rule_id=f"kind:{requirement.key}",
                    severity="error",
                    message=f"Artifact '{requirement.key}' must be kind '{requirement.kind}'",
                    artifact_key=requirement.key,
                )
            )
        if requirement.name is not None and artifact.name != requirement.name:
            findings.append(
                ConformanceFinding(
                    rule_id=f"name:{requirement.key}",
                    severity="warning",
                    message=f"Artifact '{requirement.key}' should be named '{requirement.name}'",
                    artifact_key=requirement.key,
                )
            )
        missing_stereotypes = set(requirement.stereotypes) - set(artifact.stereotypes)
        for stereotype in sorted(missing_stereotypes):
            findings.append(
                ConformanceFinding(
                    rule_id=f"stereotype:{requirement.key}:{stereotype}",
                    severity="error",
                    message=f"Artifact '{requirement.key}' is missing stereotype '{stereotype}'",
                    artifact_key=requirement.key,
                )
            )
        for prop_name, expected_value in requirement.properties.items():
            if artifact.properties.get(prop_name) != expected_value:
                findings.append(
                    ConformanceFinding(
                        rule_id=f"property:{requirement.key}:{prop_name}",
                        severity="error",
                        message=(
                            f"Artifact '{requirement.key}' must set '{prop_name}' to {expected_value!r}"
                        ),
                        artifact_key=requirement.key,
                    )
                )

    relationship_findings = _missing_relationship_requirements(recipe.required_relationships, current_artifacts)
    for requirement in relationship_findings:
        findings.append(
            ConformanceFinding(
                rule_id=f"relationship:{requirement.relationship_type}:{requirement.source_key}->{requirement.target_key}",
                severity="error",
                message=(
                    f"Missing relationship '{requirement.relationship_type}' "
                    f"from '{requirement.source_key}' to '{requirement.target_key}'"
                ),
                relationship_type=requirement.relationship_type,
            )
        )

    passed = not findings
    summary = "passed" if passed else f"{len(findings)} issue(s) found"
    return ConformanceReport(
        pack_id=pack_id,
        recipe_id=recipe.recipe_id,
        passed=passed,
        findings=tuple(findings),
        summary=summary,
    )


def semantic_validation_findings(
    validation_results: Sequence[Mapping[str, Any]],
) -> tuple[ConformanceFinding, ...]:
    findings: list[ConformanceFinding] = []
    for validation in validation_results:
        validator_id = str(
            validation.get("validatorId")
            or validation.get("validationId")
            or "semantic"
        )
        for check in validation.get("checks") or ():
            if not isinstance(check, Mapping) or check.get("ok"):
                continue
            check_name = str(check.get("name") or "check")
            findings.append(
                ConformanceFinding(
                    rule_id=f"semantic:{validator_id}:{check_name}",
                    severity="error",
                    message=_semantic_failure_message(validator_id, check_name, check.get("details")),
                )
            )
    return tuple(findings)


def extend_conformance_report(
    report: ConformanceReport,
    extra_findings: Sequence[ConformanceFinding],
) -> ConformanceReport:
    combined = tuple(report.findings) + tuple(extra_findings)
    passed = not combined
    summary = "passed" if passed else f"{len(combined)} issue(s) found"
    return ConformanceReport(
        pack_id=report.pack_id,
        recipe_id=report.recipe_id,
        passed=passed,
        findings=combined,
        summary=summary,
    )


def _semantic_failure_message(
    validator_id: str,
    check_name: str,
    details: Any,
) -> str:
    if isinstance(details, Mapping):
        message = details.get("message")
        if isinstance(message, str) and message.strip():
            return message.strip()

    detail_map = details if isinstance(details, Mapping) else {}
    detail_keys = (
        "isolatedActionIds",
        "unreachableActionIds",
        "containerOnlyPartitions",
        "stereotypeStyleNames",
        "duplicateFlowProperties",
        "directionConflicts",
        "orphanPropertyIds",
        "missingDirectionIds",
        "missingIdIds",
        "blankTextIds",
        "weakTextIds",
        "missingPortTerms",
        "missingIbdTerms",
        "missingRequirementTraceIds",
        "missing",
    )
    for key in detail_keys:
        value = detail_map.get(key)
        if isinstance(value, Mapping) and value:
            preview = ", ".join(str(item) for item in list(value)[:3])
            return f"{validator_id} check '{check_name}' failed: {preview}"
        if isinstance(value, Sequence) and not isinstance(value, (str, bytes)) and value:
            preview = ", ".join(str(item) for item in list(value)[:3])
            suffix = "..." if len(value) > 3 else ""
            return f"{validator_id} check '{check_name}' failed: {preview}{suffix}"

    pretty_name = check_name.replace("-", " ")
    return f"{validator_id} check '{pretty_name}' failed"


def build_evidence_bundle(
    pack: PackDefinition,
    recipe: RecipeDefinition,
    guidance: WorkflowGuidance,
    execution_plan: RecipeExecutionPlan,
    execution_result: RecipeExecutionResult,
    conformance: ConformanceReport,
    *,
    assumptions: Sequence[str] = (),
    notes: Sequence[str] = (),
    bridge_evidence: Mapping[str, Any] | None = None,
) -> EvidenceBundle:
    artifact_keys = tuple(sorted(execution_result.artifact_bindings))
    return EvidenceBundle(
        pack_id=pack.pack_id,
        pack_name=pack.name,
        recipe_id=recipe.recipe_id,
        recipe_name=recipe.name,
        generated_at=datetime.now(timezone.utc).isoformat(),
        artifact_keys=artifact_keys,
        guidance=guidance,
        execution_plan=execution_plan,
        execution_result=execution_result,
        conformance=conformance,
        checklist=recipe.review_checklist,
        assumptions=tuple(assumptions),
        notes=tuple(notes),
        bridge_evidence=dict(bridge_evidence or {}),
    )
