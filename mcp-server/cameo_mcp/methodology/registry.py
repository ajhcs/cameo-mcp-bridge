"""Methodology pack registry for high-level MBSE workflows.

The registry is intentionally data-first: packs, phases, recipes, checks, and
evidence sections are structured definitions that future runtime code can
consume without reinterpreting prose.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class NamingRule:
    scope: str
    pattern: str
    examples: tuple[str, ...]
    rationale: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "scope": self.scope,
            "pattern": self.pattern,
            "examples": list(self.examples),
            "rationale": self.rationale,
        }


@dataclass(frozen=True, slots=True)
class MethodPhase:
    id: str
    order: int
    title: str
    goal: str
    required_artifacts: tuple[str, ...]
    exit_criteria: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "order": self.order,
            "title": self.title,
            "goal": self.goal,
            "required_artifacts": list(self.required_artifacts),
            "exit_criteria": list(self.exit_criteria),
        }


@dataclass(frozen=True, slots=True)
class MandatoryRelationship:
    source_role: str
    relationship: str
    target_role: str
    required: bool
    rationale: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_role": self.source_role,
            "relationship": self.relationship,
            "target_role": self.target_role,
            "required": self.required,
            "rationale": self.rationale,
        }


@dataclass(frozen=True, slots=True)
class ChecklistItem:
    id: str
    title: str
    scope: str
    required: bool
    signals: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "scope": self.scope,
            "required": self.required,
            "signals": list(self.signals),
        }


@dataclass(frozen=True, slots=True)
class ReviewSection:
    id: str
    title: str
    fields: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "fields": list(self.fields),
        }


@dataclass(frozen=True, slots=True)
class EvidenceSection:
    id: str
    title: str
    fields: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "fields": list(self.fields),
        }


@dataclass(frozen=True, slots=True)
class RecipeParameter:
    name: str
    type: str
    required: bool
    default: Any | None
    description: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "type": self.type,
            "required": self.required,
            "default": self.default,
            "description": self.description,
        }


@dataclass(frozen=True, slots=True)
class RecipeStep:
    order: int
    action: str
    target: str
    inputs: tuple[str, ...]
    outputs: tuple[str, ...]
    emit_receipt: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "order": self.order,
            "action": self.action,
            "target": self.target,
            "inputs": list(self.inputs),
            "outputs": list(self.outputs),
            "emit_receipt": self.emit_receipt,
        }


@dataclass(frozen=True, slots=True)
class ArtifactRecipe:
    id: str
    title: str
    phase_id: str
    artifact_kind: str
    goal: str
    layout_profile: str
    parameters: tuple[RecipeParameter, ...]
    prerequisites: tuple[str, ...]
    creates: tuple[str, ...]
    mandatory_relationships: tuple[MandatoryRelationship, ...]
    conformance_checks: tuple[str, ...]
    review_sections: tuple[str, ...]
    evidence_sections: tuple[str, ...]
    steps: tuple[RecipeStep, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "phase_id": self.phase_id,
            "artifact_kind": self.artifact_kind,
            "goal": self.goal,
            "layout_profile": self.layout_profile,
            "parameters": [parameter.to_dict() for parameter in self.parameters],
            "prerequisites": list(self.prerequisites),
            "creates": list(self.creates),
            "mandatory_relationships": [
                relationship.to_dict() for relationship in self.mandatory_relationships
            ],
            "conformance_checks": list(self.conformance_checks),
            "review_sections": list(self.review_sections),
            "evidence_sections": list(self.evidence_sections),
            "steps": [step.to_dict() for step in self.steps],
        }


@dataclass(frozen=True, slots=True)
class PackDefinition:
    id: str
    title: str
    version: str
    domain: str
    required_profiles: tuple[str, ...]
    required_stereotypes: tuple[str, ...]
    allowed_artifact_types: tuple[str, ...]
    method_phases: tuple[MethodPhase, ...]
    naming_rules: tuple[NamingRule, ...]
    mandatory_relationships: tuple[MandatoryRelationship, ...]
    checklist_items: tuple[ChecklistItem, ...]
    review_sections: tuple[ReviewSection, ...]
    evidence_sections: tuple[EvidenceSection, ...]
    recipes: tuple[ArtifactRecipe, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "version": self.version,
            "domain": self.domain,
            "required_profiles": list(self.required_profiles),
            "required_stereotypes": list(self.required_stereotypes),
            "allowed_artifact_types": list(self.allowed_artifact_types),
            "method_phases": [phase.to_dict() for phase in self.method_phases],
            "naming_rules": [rule.to_dict() for rule in self.naming_rules],
            "mandatory_relationships": [
                relationship.to_dict() for relationship in self.mandatory_relationships
            ],
            "checklist_items": [item.to_dict() for item in self.checklist_items],
            "review_sections": [section.to_dict() for section in self.review_sections],
            "evidence_sections": [section.to_dict() for section in self.evidence_sections],
            "recipes": [recipe.to_dict() for recipe in self.recipes],
        }
OOSEM_PACK = PackDefinition(
    id="oosem",
    title="OOSEM Viewpoint Pack",
    version="2.3.4",
    domain="OOSEM",
    required_profiles=("SysML", "UML"),
    required_stereotypes=(
        "block",
        "requirement",
        "actor",
        "useCase",
        "satisfy",
        "verify",
        "refine",
        "trace",
    ),
    allowed_artifact_types=(
        "package",
        "requirement",
        "requirementDiagram",
        "useCase",
        "useCaseDiagram",
        "actor",
        "activity",
        "activityDiagram",
        "block",
        "bdd",
        "ibd",
        "testCase",
        "evidencePackage",
    ),
    method_phases=(
        MethodPhase(
            id="discovery",
            order=1,
            title="Discovery",
            goal="Establish subject boundary, stakeholders, and analysis scope.",
            required_artifacts=("subject boundary", "stakeholder roster"),
            exit_criteria=(
                "subject boundary is named and bounded",
                "stakeholders are identified",
                "candidate use cases are captured",
            ),
        ),
        MethodPhase(
            id="needs",
            order=2,
            title="Needs",
            goal="Capture stakeholder needs and convert them into structured demand.",
            required_artifacts=("stakeholder needs package", "need statements"),
            exit_criteria=(
                "need statements are normalized",
                "needs package exists",
                "trace links from stakeholders are recorded",
            ),
        ),
        MethodPhase(
            id="requirements",
            order=3,
            title="Requirements",
            goal="Translate needs into system requirements with traceability.",
            required_artifacts=("system requirements package", "requirement diagram"),
            exit_criteria=(
                "requirements have stable identifiers",
                "requirements trace to originating needs",
                "requirements package is reviewable",
            ),
        ),
        MethodPhase(
            id="architecture",
            order=4,
            title="Architecture",
            goal="Build a logical architecture scaffold and allocation chain.",
            required_artifacts=("logical architecture package", "bdd", "ibd"),
            exit_criteria=(
                "logical blocks are named and grouped",
                "allocation relationships are present",
                "subject containment is correct",
            ),
        ),
        MethodPhase(
            id="verification",
            order=5,
            title="Verification",
            goal="Create verification scaffolding and review evidence.",
            required_artifacts=("verification package", "test cases", "evidence bundle"),
            exit_criteria=(
                "requirements have verification links",
                "review packet includes conformance summary",
                "evidence bundle is complete enough for review",
            ),
        ),
    ),
    naming_rules=(
        NamingRule(
            scope="package",
            pattern="[Subject] [Artifact Kind]",
            examples=("ATM Needs", "Flight Control Requirements", "Sensor Architecture"),
            rationale="Package names should surface the subject and the method artifact at a glance.",
        ),
        NamingRule(
            scope="requirement_id",
            pattern="[PROJECT]-REQ-###",
            examples=("ATM-REQ-001", "FC-REQ-014"),
            rationale="Requirement identifiers must be stable and easy to trace in review packets.",
        ),
        NamingRule(
            scope="use_case",
            pattern="[verb phrase]",
            examples=("Authenticate user", "Dispense cash", "Detect fault"),
            rationale="Use case names should read as actions, not nouns.",
        ),
        NamingRule(
            scope="logical_block",
            pattern="[noun phrase]",
            examples=("Session Controller", "Display Assembly", "Sensor Array"),
            rationale="Logical blocks should name the architecture element, not the implementation detail.",
        ),
        NamingRule(
            scope="evidence_bundle",
            pattern="[subject]-evidence-[phase]",
            examples=("ATM-evidence-requirements", "ATM-evidence-verification"),
            rationale="Evidence bundles should encode both subject and lifecycle phase.",
        ),
    ),
    mandatory_relationships=(
        MandatoryRelationship(
            source_role="stakeholder_need",
            relationship="refine",
            target_role="system_requirement",
            required=True,
            rationale="Every need should become at least one traceable requirement.",
        ),
        MandatoryRelationship(
            source_role="system_requirement",
            relationship="satisfy",
            target_role="logical_block",
            required=True,
            rationale="Architecture must explain how requirements are satisfied.",
        ),
        MandatoryRelationship(
            source_role="actor",
            relationship="associate",
            target_role="use_case",
            required=True,
            rationale="Actors and use cases need explicit behavior links.",
        ),
        MandatoryRelationship(
            source_role="use_case",
            relationship="trace",
            target_role="stakeholder_need",
            required=False,
            rationale="Use cases should trace back to the needs they serve when available.",
        ),
        MandatoryRelationship(
            source_role="verification_case",
            relationship="verify",
            target_role="system_requirement",
            required=True,
            rationale="Verification artifacts must prove requirements, not just mention them.",
        ),
    ),
    checklist_items=(
        ChecklistItem(
            id="pack.profile",
            title="Required profiles are applied",
            scope="package",
            required=True,
            signals=("SysML profile applied", "UML profile available"),
        ),
        ChecklistItem(
            id="pack.naming",
            title="Naming rules are satisfied",
            scope="artifact",
            required=True,
            signals=("package names match pack pattern", "requirement IDs are stable"),
        ),
        ChecklistItem(
            id="pack.trace",
            title="Traceability chain is present",
            scope="model",
            required=True,
            signals=("needs trace to requirements", "blocks satisfy requirements", "test cases verify requirements"),
        ),
        ChecklistItem(
            id="pack.layout",
            title="Default layouts are applied where needed",
            scope="diagram",
            required=False,
            signals=("subject-with-usecases layout", "hierarchical architecture layout"),
        ),
        ChecklistItem(
            id="pack.evidence",
            title="Evidence bundle is complete",
            scope="review",
            required=True,
            signals=("review sections present", "validation output attached", "diagram snapshots attached"),
        ),
    ),
    review_sections=(
        ReviewSection(
            id="scope",
            title="Scope",
            fields=("subject", "phase", "method", "requested_artifacts"),
        ),
        ReviewSection(
            id="artifact_inventory",
            title="Artifact Inventory",
            fields=("packages", "diagrams", "elements", "relationships"),
        ),
        ReviewSection(
            id="traceability",
            title="Traceability",
            fields=("needs_to_requirements", "requirements_to_architecture", "requirements_to_verification"),
        ),
        ReviewSection(
            id="conformance",
            title="Conformance",
            fields=("checks", "warnings", "errors"),
        ),
        ReviewSection(
            id="open_gaps",
            title="Open Gaps",
            fields=("missing_artifacts", "missing_relationships", "manual_follow_up"),
        ),
        ReviewSection(
            id="approval",
            title="Approval Readiness",
            fields=("ready", "blocked_by", "next_action"),
        ),
    ),
    evidence_sections=(
        EvidenceSection(
            id="inputs",
            title="Inputs",
            fields=("prompt", "selected_pack", "selected_recipe", "source_package"),
        ),
        EvidenceSection(
            id="changes",
            title="Changes",
            fields=("created_elements", "updated_elements", "deleted_elements", "receipts"),
        ),
        EvidenceSection(
            id="validation",
            title="Validation",
            fields=("conformance_checks", "traceability_checks", "layout_checks"),
        ),
        EvidenceSection(
            id="snapshots",
            title="Snapshots",
            fields=("before_images", "after_images", "diagram_ids"),
        ),
        EvidenceSection(
            id="assumptions",
            title="Assumptions",
            fields=("open_assumptions", "manual_follow_up", "notes"),
        ),
    ),
    recipes=(
        ArtifactRecipe(
            id="stakeholder_needs_package",
            title="Stakeholder Needs Package",
            phase_id="needs",
            artifact_kind="package",
            goal="Create a package for stakeholder needs, baseline needs statements, and review-ready trace anchors.",
            layout_profile="hierarchical",
            parameters=(
                RecipeParameter(
                    name="root_package_id",
                    type="str",
                    required=True,
                    default=None,
                    description="Owning package or model that receives the new needs package.",
                ),
                RecipeParameter(
                    name="subject_name",
                    type="str",
                    required=True,
                    default=None,
                    description="Method subject used in package naming and trace labeling.",
                ),
                RecipeParameter(
                    name="need_statements",
                    type="list[str]",
                    required=False,
                    default=None,
                    description="Normalized stakeholder need statements to seed requirements.",
                ),
                RecipeParameter(
                    name="stakeholder_names",
                    type="list[str]",
                    required=False,
                    default=None,
                    description="Stakeholder names used to seed trace anchors.",
                ),
            ),
            prerequisites=(
                "subject boundary defined",
                "stakeholders identified",
            ),
            creates=(
                "stakeholder needs package",
                "need statements",
                "needs diagram",
            ),
            mandatory_relationships=(
                MandatoryRelationship(
                    source_role="stakeholder",
                    relationship="trace",
                    target_role="need_statement",
                    required=True,
                    rationale="Stakeholders should trace to the needs they originated.",
                ),
                MandatoryRelationship(
                    source_role="stakeholder_need",
                    relationship="refine",
                    target_role="system_requirement",
                    required=False,
                    rationale="Needs produced here should be ready to refine into requirements downstream.",
                ),
            ),
            conformance_checks=(
                "pack.profile",
                "pack.naming",
                "pack.trace",
            ),
            review_sections=(
                "scope",
                "artifact_inventory",
                "traceability",
                "conformance",
            ),
            evidence_sections=(
                "inputs",
                "changes",
                "validation",
                "snapshots",
            ),
            steps=(
                RecipeStep(
                    order=1,
                    action="create_package",
                    target="stakeholder needs package",
                    inputs=("root_package_id", "subject_name"),
                    outputs=("package_id",),
                    emit_receipt=True,
                ),
                RecipeStep(
                    order=2,
                    action="seed_need_statements",
                    target="requirements model",
                    inputs=("need_statements", "stakeholder_names"),
                    outputs=("need_element_ids",),
                    emit_receipt=True,
                ),
                RecipeStep(
                    order=3,
                    action="layout_diagram",
                    target="needs diagram",
                    inputs=("layout_profile",),
                    outputs=("diagram_snapshot",),
                    emit_receipt=False,
                ),
            ),
        ),
        ArtifactRecipe(
            id="use_case_model",
            title="Use Case Model",
            phase_id="needs",
            artifact_kind="useCaseDiagram",
            goal="Create a subject-centered use case model with actors and named use cases.",
            layout_profile="subject-with-usecases",
            parameters=(
                RecipeParameter(
                    name="root_package_id",
                    type="str",
                    required=True,
                    default=None,
                    description="Owning package or model that receives the use case model.",
                ),
                RecipeParameter(
                    name="subject_name",
                    type="str",
                    required=True,
                    default=None,
                    description="Subject boundary name used for containment and labels.",
                ),
                RecipeParameter(
                    name="actor_names",
                    type="list[str]",
                    required=False,
                    default=None,
                    description="Actor names to create and connect to use cases.",
                ),
                RecipeParameter(
                    name="use_case_names",
                    type="list[str]",
                    required=False,
                    default=None,
                    description="Use case names to create in the subject boundary.",
                ),
            ),
            prerequisites=(
                "subject boundary defined",
                "stakeholder roster available",
            ),
            creates=(
                "subject block",
                "actors",
                "use cases",
                "use case diagram",
            ),
            mandatory_relationships=(
                MandatoryRelationship(
                    source_role="actor",
                    relationship="associate",
                    target_role="use_case",
                    required=True,
                    rationale="Actors must be explicitly linked to the use cases they participate in.",
                ),
                MandatoryRelationship(
                    source_role="subject",
                    relationship="contain",
                    target_role="use_case",
                    required=True,
                    rationale="The subject boundary must contain the use cases it owns.",
                ),
                MandatoryRelationship(
                    source_role="use_case",
                    relationship="trace",
                    target_role="stakeholder_need",
                    required=False,
                    rationale="Use cases should trace back to originating needs when available.",
                ),
            ),
            conformance_checks=(
                "pack.profile",
                "pack.naming",
                "pack.trace",
                "pack.layout",
            ),
            review_sections=(
                "scope",
                "artifact_inventory",
                "traceability",
                "approval",
            ),
            evidence_sections=(
                "inputs",
                "changes",
                "validation",
                "snapshots",
            ),
            steps=(
                RecipeStep(
                    order=1,
                    action="create_subject_boundary",
                    target="use case model",
                    inputs=("root_package_id", "subject_name"),
                    outputs=("subject_block_id", "diagram_id"),
                    emit_receipt=True,
                ),
                RecipeStep(
                    order=2,
                    action="create_actors",
                    target="use case diagram",
                    inputs=("actor_names",),
                    outputs=("actor_ids",),
                    emit_receipt=True,
                ),
                RecipeStep(
                    order=3,
                    action="create_use_cases",
                    target="use case diagram",
                    inputs=("use_case_names",),
                    outputs=("use_case_ids",),
                    emit_receipt=True,
                ),
                RecipeStep(
                    order=4,
                    action="apply_layout",
                    target="use case diagram",
                    inputs=("layout_profile",),
                    outputs=("diagram_snapshot",),
                    emit_receipt=False,
                ),
            ),
        ),
        ArtifactRecipe(
            id="system_requirements_package",
            title="System Requirements Package",
            phase_id="requirements",
            artifact_kind="requirementDiagram",
            goal="Create a requirements package with traceable system requirements and a reviewable requirements diagram.",
            layout_profile="hierarchical",
            parameters=(
                RecipeParameter(
                    name="root_package_id",
                    type="str",
                    required=True,
                    default=None,
                    description="Owning package or model that receives the requirements package.",
                ),
                RecipeParameter(
                    name="system_name",
                    type="str",
                    required=True,
                    default=None,
                    description="System name used in package and requirement labels.",
                ),
                RecipeParameter(
                    name="requirement_ids",
                    type="list[str]",
                    required=False,
                    default=None,
                    description="Stable requirement identifiers to create or reconcile.",
                ),
                RecipeParameter(
                    name="requirement_texts",
                    type="list[str]",
                    required=False,
                    default=None,
                    description="Requirement bodies aligned to the identifiers above.",
                ),
            ),
            prerequisites=(
                "needs package exists",
                "trace anchors are available",
            ),
            creates=(
                "system requirements package",
                "requirement elements",
                "requirement diagram",
            ),
            mandatory_relationships=(
                MandatoryRelationship(
                    source_role="stakeholder_need",
                    relationship="refine",
                    target_role="system_requirement",
                    required=True,
                    rationale="Requirements must preserve traceability back to the originating needs.",
                ),
                MandatoryRelationship(
                    source_role="system_requirement",
                    relationship="trace",
                    target_role="stakeholder_need",
                    required=True,
                    rationale="The requirements package must surface back-trace links for review.",
                ),
                MandatoryRelationship(
                    source_role="logical_block",
                    relationship="satisfy",
                    target_role="system_requirement",
                    required=False,
                    rationale="Logical blocks should explicitly satisfy the system requirements they implement.",
                ),
            ),
            conformance_checks=(
                "pack.profile",
                "pack.naming",
                "pack.trace",
            ),
            review_sections=(
                "artifact_inventory",
                "traceability",
                "conformance",
                "open_gaps",
            ),
            evidence_sections=(
                "inputs",
                "changes",
                "validation",
                "assumptions",
            ),
            steps=(
                RecipeStep(
                    order=1,
                    action="create_requirements_package",
                    target="requirements model",
                    inputs=("root_package_id", "system_name"),
                    outputs=("package_id",),
                    emit_receipt=True,
                ),
                RecipeStep(
                    order=2,
                    action="create_requirement_elements",
                    target="requirements diagram",
                    inputs=("requirement_ids", "requirement_texts"),
                    outputs=("requirement_ids",),
                    emit_receipt=True,
                ),
                RecipeStep(
                    order=3,
                    action="link_to_needs",
                    target="requirements package",
                    inputs=("requirement_ids",),
                    outputs=("trace_links",),
                    emit_receipt=True,
                ),
            ),
        ),
        ArtifactRecipe(
            id="logical_architecture_scaffold",
            title="Logical Architecture Scaffold",
            phase_id="architecture",
            artifact_kind="bdd",
            goal="Create a logical architecture scaffold with allocation-ready blocks and diagram structure.",
            layout_profile="hierarchical",
            parameters=(
                RecipeParameter(
                    name="root_package_id",
                    type="str",
                    required=True,
                    default=None,
                    description="Owning package or model that receives the architecture package.",
                ),
                RecipeParameter(
                    name="architecture_name",
                    type="str",
                    required=True,
                    default=None,
                    description="Architecture package and diagram name stem.",
                ),
                RecipeParameter(
                    name="block_names",
                    type="list[str]",
                    required=False,
                    default=None,
                    description="Logical block names to seed in the scaffold.",
                ),
                RecipeParameter(
                    name="allocation_targets",
                    type="list[str]",
                    required=False,
                    default=None,
                    description="Target elements that should receive allocation links.",
                ),
            ),
            prerequisites=(
                "requirements package exists",
                "requirements are traceable",
            ),
            creates=(
                "logical architecture package",
                "block definition diagram",
                "logical blocks",
                "allocation links",
            ),
            mandatory_relationships=(
                MandatoryRelationship(
                    source_role="logical_block",
                    relationship="satisfy",
                    target_role="system_requirement",
                    required=True,
                    rationale="Architecture must explain which logical blocks satisfy each requirement.",
                ),
                MandatoryRelationship(
                    source_role="logical_block",
                    relationship="allocate",
                    target_role="behavior",
                    required=False,
                    rationale="Logical blocks should be able to allocate behavior where needed.",
                ),
            ),
            conformance_checks=(
                "pack.profile",
                "pack.naming",
                "pack.trace",
                "pack.layout",
            ),
            review_sections=(
                "artifact_inventory",
                "traceability",
                "conformance",
            ),
            evidence_sections=(
                "changes",
                "validation",
                "snapshots",
                "assumptions",
            ),
            steps=(
                RecipeStep(
                    order=1,
                    action="create_architecture_package",
                    target="architecture model",
                    inputs=("root_package_id", "architecture_name"),
                    outputs=("package_id", "diagram_id"),
                    emit_receipt=True,
                ),
                RecipeStep(
                    order=2,
                    action="seed_logical_blocks",
                    target="block definition diagram",
                    inputs=("block_names",),
                    outputs=("block_ids",),
                    emit_receipt=True,
                ),
                RecipeStep(
                    order=3,
                    action="apply_allocations",
                    target="architecture package",
                    inputs=("allocation_targets",),
                    outputs=("allocation_links",),
                    emit_receipt=True,
                ),
                RecipeStep(
                    order=4,
                    action="apply_layout",
                    target="block definition diagram",
                    inputs=("layout_profile",),
                    outputs=("diagram_snapshot",),
                    emit_receipt=False,
                ),
            ),
        ),
        ArtifactRecipe(
            id="verification_evidence_scaffold",
            title="Verification Evidence Scaffold",
            phase_id="verification",
            artifact_kind="evidencePackage",
            goal="Create verification scaffolding with requirement verification links and review evidence sections.",
            layout_profile="traceability-ladder",
            parameters=(
                RecipeParameter(
                    name="root_package_id",
                    type="str",
                    required=True,
                    default=None,
                    description="Owning package or model that receives the evidence package.",
                ),
                RecipeParameter(
                    name="verification_name",
                    type="str",
                    required=True,
                    default=None,
                    description="Evidence package name stem.",
                ),
                RecipeParameter(
                    name="requirement_ids",
                    type="list[str]",
                    required=False,
                    default=None,
                    description="Requirement identifiers to verify.",
                ),
                RecipeParameter(
                    name="verification_methods",
                    type="list[str]",
                    required=False,
                    default=None,
                    description="Verification methods to seed, such as analysis, inspection, or test.",
                ),
            ),
            prerequisites=(
                "requirements package exists",
                "verification methods are chosen",
            ),
            creates=(
                "verification package",
                "test cases",
                "verify links",
                "review packet scaffold",
            ),
            mandatory_relationships=(
                MandatoryRelationship(
                    source_role="verification_case",
                    relationship="verify",
                    target_role="system_requirement",
                    required=True,
                    rationale="Verification artifacts must prove the requirements they cover.",
                ),
                MandatoryRelationship(
                    source_role="system_requirement",
                    relationship="trace",
                    target_role="verification_case",
                    required=True,
                    rationale="Each requirement should have at least one visible verification path.",
                ),
            ),
            conformance_checks=(
                "pack.profile",
                "pack.naming",
                "pack.trace",
                "pack.evidence",
            ),
            review_sections=(
                "artifact_inventory",
                "traceability",
                "conformance",
                "approval",
            ),
            evidence_sections=(
                "inputs",
                "changes",
                "validation",
                "snapshots",
                "assumptions",
            ),
            steps=(
                RecipeStep(
                    order=1,
                    action="create_verification_package",
                    target="verification model",
                    inputs=("root_package_id", "verification_name"),
                    outputs=("package_id",),
                    emit_receipt=True,
                ),
                RecipeStep(
                    order=2,
                    action="seed_verification_cases",
                    target="verification package",
                    inputs=("requirement_ids", "verification_methods"),
                    outputs=("verification_case_ids",),
                    emit_receipt=True,
                ),
                RecipeStep(
                    order=3,
                    action="assemble_review_packet",
                    target="evidence bundle",
                    inputs=("requirement_ids",),
                    outputs=("review_packet",),
                    emit_receipt=False,
                ),
            ),
        ),
        ArtifactRecipe(
            id="logical_activity_flow",
            title="Logical Activity Flow",
            phase_id="architecture",
            artifact_kind="activityDiagram",
            goal="Create a logical activity flow with performer lanes, a connected action chain, and reviewable control flow.",
            layout_profile="swimlane",
            parameters=(
                RecipeParameter(
                    name="root_package_id",
                    type="str",
                    required=True,
                    default=None,
                    description="Owning package or model that receives the logical activity package.",
                ),
                RecipeParameter(
                    name="activity_name",
                    type="str",
                    required=True,
                    default=None,
                    description="Logical activity name stem.",
                ),
                RecipeParameter(
                    name="performer_names",
                    type="list[str]",
                    required=False,
                    default=None,
                    description="Performer or swimlane names to seed in the activity flow.",
                ),
                RecipeParameter(
                    name="action_names",
                    type="list[str]",
                    required=False,
                    default=None,
                    description="Action names to chain from initial node to final node.",
                ),
            ),
            prerequisites=(
                "scenario scope is bounded",
                "performers and actions are identified",
            ),
            creates=(
                "logical activity package",
                "activity",
                "activity diagram",
                "performer lanes",
                "control-flow chain",
            ),
            mandatory_relationships=(
                MandatoryRelationship(
                    source_role="activity_node",
                    relationship="control-flow",
                    target_role="activity_node",
                    required=True,
                    rationale="The activity diagram must read as a connected behavior chain, not isolated action islands.",
                ),
            ),
            conformance_checks=(
                "pack.profile",
                "pack.naming",
                "pack.layout",
            ),
            review_sections=(
                "scope",
                "artifact_inventory",
                "conformance",
                "open_gaps",
            ),
            evidence_sections=(
                "inputs",
                "changes",
                "validation",
                "snapshots",
            ),
            steps=(
                RecipeStep(
                    order=1,
                    action="create_logical_activity_package",
                    target="activity model",
                    inputs=("root_package_id", "activity_name"),
                    outputs=("package_id", "activity_id", "diagram_id"),
                    emit_receipt=True,
                ),
                RecipeStep(
                    order=2,
                    action="seed_performer_lanes",
                    target="activity diagram",
                    inputs=("performer_names",),
                    outputs=("performer_ids", "partition_ids"),
                    emit_receipt=True,
                ),
                RecipeStep(
                    order=3,
                    action="seed_action_chain",
                    target="activity diagram",
                    inputs=("action_names",),
                    outputs=("node_ids", "flow_ids"),
                    emit_receipt=True,
                ),
            ),
        ),
        ArtifactRecipe(
            id="logical_port_bdd",
            title="Logical Port BDD",
            phase_id="architecture",
            artifact_kind="bdd",
            goal="Create a high-level port BDD with a system block, interface blocks, and typed ports ready for boundary review.",
            layout_profile="hierarchical",
            parameters=(
                RecipeParameter(
                    name="root_package_id",
                    type="str",
                    required=True,
                    default=None,
                    description="Owning package or model that receives the logical port package.",
                ),
                RecipeParameter(
                    name="system_name",
                    type="str",
                    required=True,
                    default=None,
                    description="System name used for the owning block and package labels.",
                ),
                RecipeParameter(
                    name="interface_definitions",
                    type="list[dict]",
                    required=False,
                    default=None,
                    description="Interface definitions shaped like {name, port_name?, flow_properties:[{name, direction}]}",
                ),
            ),
            prerequisites=(
                "system boundary is known",
                "candidate interfaces are identified",
            ),
            creates=(
                "logical port package",
                "block definition diagram",
                "system block",
                "interface blocks",
                "typed ports",
            ),
            mandatory_relationships=(),
            conformance_checks=(
                "pack.profile",
                "pack.naming",
                "pack.layout",
            ),
            review_sections=(
                "artifact_inventory",
                "traceability",
                "conformance",
                "open_gaps",
            ),
            evidence_sections=(
                "inputs",
                "changes",
                "validation",
                "snapshots",
            ),
            steps=(
                RecipeStep(
                    order=1,
                    action="create_logical_port_package",
                    target="architecture model",
                    inputs=("root_package_id", "system_name"),
                    outputs=("package_id", "system_block_id", "diagram_id"),
                    emit_receipt=True,
                ),
                RecipeStep(
                    order=2,
                    action="seed_interface_blocks",
                    target="block definition diagram",
                    inputs=("interface_definitions",),
                    outputs=("interface_block_ids", "flow_property_ids"),
                    emit_receipt=True,
                ),
                RecipeStep(
                    order=3,
                    action="type_system_ports",
                    target="system block",
                    inputs=("interface_definitions",),
                    outputs=("port_ids",),
                    emit_receipt=True,
                ),
            ),
        ),
        ArtifactRecipe(
            id="logical_ibd_traceability",
            title="Logical IBD Traceability",
            phase_id="architecture",
            artifact_kind="ibd",
            goal="Create a logical context IBD with external parts, connectors, and named flows that can be traced back to behavior.",
            layout_profile="traceability-ladder",
            parameters=(
                RecipeParameter(
                    name="root_package_id",
                    type="str",
                    required=True,
                    default=None,
                    description="Owning package or model that receives the logical context package.",
                ),
                RecipeParameter(
                    name="context_name",
                    type="str",
                    required=True,
                    default=None,
                    description="Context/system name used for the owning block and IBD labels.",
                ),
                RecipeParameter(
                    name="part_names",
                    type="list[str]",
                    required=False,
                    default=None,
                    description="External participant names to place around the context block.",
                ),
                RecipeParameter(
                    name="flow_names",
                    type="list[str]",
                    required=False,
                    default=None,
                    description="Named flows to realize across the connector set.",
                ),
                RecipeParameter(
                    name="activity_diagram_id",
                    type="str",
                    required=False,
                    default=None,
                    description="Optional activity diagram ID used for traceability validation.",
                ),
                RecipeParameter(
                    name="interface_block_ids",
                    type="list[str]",
                    required=False,
                    default=None,
                    description="Optional interface block IDs used to type ports and compare flow vocabulary.",
                ),
            ),
            prerequisites=(
                "context participants are identified",
                "behavior vocabulary is available for comparison",
            ),
            creates=(
                "logical context package",
                "context block",
                "internal block diagram",
                "external parts",
                "connectors",
                "named information flows",
            ),
            mandatory_relationships=(
                MandatoryRelationship(
                    source_role="context_port",
                    relationship="connector",
                    target_role="external_port",
                    required=True,
                    rationale="The IBD should make the interaction structure explicit with real connectors.",
                ),
                MandatoryRelationship(
                    source_role="context_port",
                    relationship="information-flow",
                    target_role="external_port",
                    required=True,
                    rationale="Named flows should be visible on the context view for traceability review.",
                ),
            ),
            conformance_checks=(
                "pack.profile",
                "pack.naming",
                "pack.trace",
                "pack.layout",
            ),
            review_sections=(
                "artifact_inventory",
                "traceability",
                "conformance",
                "open_gaps",
            ),
            evidence_sections=(
                "inputs",
                "changes",
                "validation",
                "snapshots",
            ),
            steps=(
                RecipeStep(
                    order=1,
                    action="create_logical_context_package",
                    target="context model",
                    inputs=("root_package_id", "context_name"),
                    outputs=("package_id", "context_block_id", "diagram_id"),
                    emit_receipt=True,
                ),
                RecipeStep(
                    order=2,
                    action="seed_context_parts",
                    target="internal block diagram",
                    inputs=("part_names", "interface_block_ids"),
                    outputs=("part_ids", "port_ids"),
                    emit_receipt=True,
                ),
                RecipeStep(
                    order=3,
                    action="connect_named_flows",
                    target="internal block diagram",
                    inputs=("flow_names", "activity_diagram_id"),
                    outputs=("connector_ids", "flow_ids"),
                    emit_receipt=True,
                ),
            ),
        ),
        ArtifactRecipe(
            id="use_case_subject_containment",
            title="Use Case Subject Containment",
            phase_id="needs",
            artifact_kind="useCaseDiagram",
            goal="Create a use case model that explicitly sets UseCase subjects and keeps the diagram visually contained.",
            layout_profile="subject-with-usecases",
            parameters=(
                RecipeParameter(
                    name="root_package_id",
                    type="str",
                    required=True,
                    default=None,
                    description="Owning package or model that receives the use case package.",
                ),
                RecipeParameter(
                    name="subject_name",
                    type="str",
                    required=True,
                    default=None,
                    description="Name of the system subject boundary.",
                ),
                RecipeParameter(
                    name="actor_names",
                    type="list[str]",
                    required=False,
                    default=None,
                    description="Actors to place around the subject boundary.",
                ),
                RecipeParameter(
                    name="use_case_names",
                    type="list[str]",
                    required=False,
                    default=None,
                    description="Use cases to create and bind to the subject.",
                ),
            ),
            prerequisites=("subject boundary defined", "candidate use cases captured"),
            creates=("subject boundary", "use case diagram", "actor associations", "subject traces"),
            mandatory_relationships=(
                MandatoryRelationship(
                    source_role="subject",
                    relationship="subject",
                    target_role="use_case",
                    required=True,
                    rationale="Each use case must declare its owning subject classifier.",
                ),
                MandatoryRelationship(
                    source_role="actor",
                    relationship="associate",
                    target_role="use_case",
                    required=True,
                    rationale="Actor participation must remain explicit in the model and the view.",
                ),
            ),
            conformance_checks=("pack.naming", "pack.trace", "pack.layout"),
            review_sections=("scope", "artifact_inventory", "traceability", "conformance"),
            evidence_sections=("inputs", "changes", "validation", "snapshots"),
            steps=(
                RecipeStep(
                    order=1,
                    action="create_subject_boundary",
                    target="use case model",
                    inputs=("root_package_id", "subject_name"),
                    outputs=("subject_block_id", "diagram_id"),
                    emit_receipt=True,
                ),
                RecipeStep(
                    order=2,
                    action="set_usecase_subjects",
                    target="use case model",
                    inputs=("use_case_names",),
                    outputs=("subject_links",),
                    emit_receipt=True,
                ),
                RecipeStep(
                    order=3,
                    action="contain_use_cases_on_diagram",
                    target="use case diagram",
                    inputs=("layout_profile",),
                    outputs=("presentation_receipts", "diagram_snapshot"),
                    emit_receipt=True,
                ),
            ),
        ),
        ArtifactRecipe(
            id="requirements_to_architecture_allocation",
            title="Requirements To Architecture Allocation",
            phase_id="architecture",
            artifact_kind="bdd",
            goal="Create a bounded allocation scaffold from system requirements into logical architecture blocks.",
            layout_profile="hierarchical",
            parameters=(
                RecipeParameter(
                    name="root_package_id",
                    type="str",
                    required=True,
                    default=None,
                    description="Owning package or model that receives the allocation scaffold.",
                ),
                RecipeParameter(
                    name="architecture_name",
                    type="str",
                    required=True,
                    default=None,
                    description="Allocation package and diagram name stem.",
                ),
                RecipeParameter(
                    name="requirement_ids",
                    type="list[str]",
                    required=False,
                    default=None,
                    description="Existing requirement identifiers to allocate.",
                ),
                RecipeParameter(
                    name="block_names",
                    type="list[str]",
                    required=False,
                    default=None,
                    description="Logical block names that will satisfy the requirement set.",
                ),
            ),
            prerequisites=("system requirements package exists", "requirements are traceable"),
            creates=("allocation package", "block definition diagram", "logical blocks", "satisfy links"),
            mandatory_relationships=(
                MandatoryRelationship(
                    source_role="logical_block",
                    relationship="satisfy",
                    target_role="system_requirement",
                    required=True,
                    rationale="The allocation flow is only useful if the architecture satisfies the requirements explicitly.",
                ),
            ),
            conformance_checks=("pack.naming", "pack.trace", "pack.layout"),
            review_sections=("artifact_inventory", "traceability", "conformance", "open_gaps"),
            evidence_sections=("inputs", "changes", "validation", "snapshots"),
            steps=(
                RecipeStep(
                    order=1,
                    action="create_allocation_scaffold",
                    target="architecture model",
                    inputs=("root_package_id", "architecture_name"),
                    outputs=("package_id", "diagram_id"),
                    emit_receipt=True,
                ),
                RecipeStep(
                    order=2,
                    action="seed_allocated_blocks",
                    target="block definition diagram",
                    inputs=("block_names",),
                    outputs=("block_ids",),
                    emit_receipt=True,
                ),
                RecipeStep(
                    order=3,
                    action="create_satisfy_links",
                    target="allocation package",
                    inputs=("requirement_ids",),
                    outputs=("satisfy_ids",),
                    emit_receipt=True,
                ),
            ),
        ),
    ),
)

UAF_STARTER_PACK = PackDefinition(
    id="uaf",
    title="UAF Starter Pack",
    version="0.1.0",
    domain="UAF",
    required_profiles=("UAF",),
    required_stereotypes=("OperationalActivity", "Performer"),
    allowed_artifact_types=("package", "activity", "activityDiagram"),
    method_phases=(
        MethodPhase(
            id="starter",
            order=1,
            title="Starter",
            goal="Create one bounded operational activity starter artifact with evidence.",
            required_artifacts=("operational activity package", "activity diagram"),
            exit_criteria=(
                "starter package exists",
                "operational activity diagram exists",
                "evidence bundle captures what was created",
            ),
        ),
    ),
    naming_rules=(
        NamingRule(
            scope="uaf starter package",
            pattern="[activity]-operational-view",
            examples=("Mission Planning-operational-view",),
            rationale="Keep the starter artifact narrow and easy to validate.",
        ),
    ),
    mandatory_relationships=(),
    checklist_items=(
        ChecklistItem(
            id="uaf.scope",
            title="Starter scope stays narrow",
            scope="recipe",
            required=True,
            signals=("single bounded artifact", "review packet generated"),
        ),
    ),
    review_sections=(
        ReviewSection("scope", "Scope", ("subject", "artifact")),
        ReviewSection("artifact_inventory", "Artifact Inventory", ("created", "updated")),
        ReviewSection("conformance", "Conformance", ("findings", "gaps")),
    ),
    evidence_sections=(
        EvidenceSection("inputs", "Inputs", ("parameters",)),
        EvidenceSection("changes", "Changes", ("created_ids", "receipts")),
        EvidenceSection("snapshots", "Snapshots", ("diagram_images",)),
    ),
    recipes=(
        ArtifactRecipe(
            id="uaf_operational_activity_starter",
            title="UAF Operational Activity Starter",
            phase_id="starter",
            artifact_kind="activityDiagram",
            goal="Create a minimal operational activity starter package and diagram with evidence.",
            layout_profile="activity-chain",
            parameters=(
                RecipeParameter(
                    name="root_package_id",
                    type="str",
                    required=True,
                    default=None,
                    description="Owning package or model for the starter artifact.",
                ),
                RecipeParameter(
                    name="activity_name",
                    type="str",
                    required=True,
                    default=None,
                    description="Operational activity name stem.",
                ),
                RecipeParameter(
                    name="action_names",
                    type="list[str]",
                    required=False,
                    default=None,
                    description="Seed activities to place on the starter diagram.",
                ),
            ),
            prerequisites=("operator selected a bounded operational starter",),
            creates=("operational package", "activity diagram", "activities"),
            mandatory_relationships=(),
            conformance_checks=("pack.naming", "pack.evidence"),
            review_sections=("scope", "artifact_inventory", "conformance"),
            evidence_sections=("inputs", "changes", "snapshots"),
            steps=(
                RecipeStep(
                    order=1,
                    action="create_operational_package",
                    target="uaf starter",
                    inputs=("root_package_id", "activity_name"),
                    outputs=("package_id", "diagram_id"),
                    emit_receipt=True,
                ),
                RecipeStep(
                    order=2,
                    action="seed_operational_activities",
                    target="activity diagram",
                    inputs=("action_names",),
                    outputs=("activity_ids",),
                    emit_receipt=True,
                ),
            ),
        ),
    ),
)


class MethodologyRegistry:
    def __init__(self, packs: tuple[PackDefinition, ...] = (OOSEM_PACK, UAF_STARTER_PACK)) -> None:
        pack_map: dict[str, PackDefinition] = {}
        for pack in packs:
            key = pack.id.lower()
            if key in pack_map:
                raise ValueError(f"Duplicate methodology pack id: {pack.id}")
            pack_map[key] = pack
        self._packs = pack_map

    def list_packs(self) -> tuple[PackDefinition, ...]:
        return tuple(self._packs[key] for key in sorted(self._packs))

    def get_pack(self, pack_id: str) -> PackDefinition:
        try:
            return self._packs[pack_id.lower()]
        except KeyError as exc:
            raise KeyError(f"Unknown methodology pack: {pack_id}") from exc

    def list_recipes(self, pack_id: str) -> tuple[ArtifactRecipe, ...]:
        return self.get_pack(pack_id).recipes

    def get_recipe(self, pack_id: str, recipe_id: str) -> ArtifactRecipe:
        pack = self.get_pack(pack_id)
        for recipe in pack.recipes:
            if recipe.id == recipe_id:
                return recipe
        raise KeyError(f"Unknown recipe for pack {pack_id}: {recipe_id}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "packs": [pack.to_dict() for pack in self.list_packs()],
        }


DEFAULT_REGISTRY = MethodologyRegistry()
REGISTRY = DEFAULT_REGISTRY


def list_packs() -> tuple[PackDefinition, ...]:
    return DEFAULT_REGISTRY.list_packs()


def get_pack(pack_id: str) -> PackDefinition:
    return DEFAULT_REGISTRY.get_pack(pack_id)


def list_recipes(pack_id: str) -> tuple[ArtifactRecipe, ...]:
    return DEFAULT_REGISTRY.list_recipes(pack_id)


def get_recipe(pack_id: str, recipe_id: str) -> ArtifactRecipe:
    return DEFAULT_REGISTRY.get_recipe(pack_id, recipe_id)


def to_dict() -> dict[str, Any]:
    return DEFAULT_REGISTRY.to_dict()


__all__ = [
    "ArtifactRecipe",
    "ChecklistItem",
    "DEFAULT_REGISTRY",
    "EvidenceSection",
    "MethodPhase",
    "MethodologyRegistry",
    "MandatoryRelationship",
    "NamingRule",
    "OOSEM_PACK",
    "PackDefinition",
    "REGISTRY",
    "RecipeParameter",
    "RecipeStep",
    "ReviewSection",
    "UAF_STARTER_PACK",
    "get_pack",
    "get_recipe",
    "list_packs",
    "list_recipes",
    "to_dict",
]
