"""MCP server exposing CATIA Magic / Cameo Systems Modeler tools to Claude Code."""

from __future__ import annotations

import base64
from collections import Counter
from io import BytesIO
from typing import Annotated, Any, Optional

from mcp.server.fastmcp import FastMCP
from PIL import Image
from pydantic import AliasChoices, Field

from cameo_mcp import client, verification
from cameo_mcp.auto_remediation import (
    build_cross_diagram_remediation_plan,
    detect_cross_diagram_inconsistencies_for_artifacts,
)
from cameo_mcp.methodology import (
    execute_methodology_recipe,
    generate_review_packet,
    get_methodology_pack,
    get_workflow_guidance,
    list_methodology_packs,
    validate_methodology_recipe,
)
from cameo_mcp.proofing import apply_patch_plan as apply_proofing_patch_plan
from cameo_mcp.proofing import proof_model_text
from cameo_mcp.methodology_workflows import (
    assemble_ppt_pdf_live,
    compare_against_expected_artifact_list,
    export_required_diagrams_live,
    validate_methodology_package_live,
)
from cameo_mcp.semantic_validation import (
    verify_activity_flow_semantics_for_diagram,
    verify_cross_diagram_traceability as run_cross_diagram_traceability,
    verify_port_boundary_consistency_for_interfaces,
    verify_requirement_quality_for_ids,
)
from cameo_mcp.state_machine_semantics import (
    get_state_behaviors,
    get_transition_triggers,
    set_state_behaviors,
    set_transition_trigger,
)

mcp = FastMCP(
    "CameoMCPBridge",
    instructions=(
        "Bridge to CATIA Magic (Cameo Systems Modeler) for SysML/UML model "
        "creation, querying, and manipulation via the CameoMCPBridge plugin."
    ),
)


def _mcp_result(result: dict[str, Any]) -> dict[str, Any]:
    """Return native MCP objects.

    Older bridge builds serialized tool results to JSON strings so legacy
    clients could parse them manually. Newer MCP runtimes validate tool
    results against the annotated return schema, so returning strings here
    causes every `dict[...]` tool to fail validation before the payload
    reaches the client.
    """
    return result


def _count_by_key(items: list[dict[str, Any]], key: str) -> dict[str, int]:
    counter = Counter(str(item.get(key)) for item in items if item.get(key))
    return dict(sorted(counter.items(), key=lambda entry: (-entry[1], entry[0].lower())))


def _filter_diagram_shapes(
    result: dict[str, Any],
    *,
    limit: int,
    offset: int,
    shape_type: Optional[str],
    element_type: Optional[str],
    parent_presentation_id: Optional[str],
    include_bounds: bool,
    include_child_count: bool,
    summary_only: bool,
) -> dict[str, Any]:
    shapes = [shape for shape in (result.get("shapes") or []) if isinstance(shape, dict)]

    def _matches(shape: dict[str, Any]) -> bool:
        if shape_type and str(shape.get("shapeType", "")).lower() != shape_type.lower():
            return False
        if element_type and str(shape.get("elementType", "")).lower() != element_type.lower():
            return False
        if (
            parent_presentation_id
            and str(shape.get("parentPresentationId", "")) != parent_presentation_id
        ):
            return False
        return True

    filtered = [shape for shape in shapes if _matches(shape)]
    start = min(max(offset, 0), len(filtered))
    end = min(start + max(limit, 0), len(filtered))
    page = filtered[start:end]

    if not include_bounds or not include_child_count:
        projected_page: list[dict[str, Any]] = []
        for shape in page:
            projected = dict(shape)
            if not include_bounds:
                projected.pop("bounds", None)
            if not include_child_count:
                projected.pop("childCount", None)
            projected_page.append(projected)
        page = projected_page

    response: dict[str, Any] = {
        "diagramId": result.get("diagramId"),
        "count": len(page),
        "returned": len(page),
        "totalCount": len(filtered),
        "shapeCount": len(filtered),
        "limit": limit,
        "offset": start,
        "hasMore": end < len(filtered),
        "filters": {
            "shapeType": shape_type,
            "elementType": element_type,
            "parentPresentationId": parent_presentation_id,
            "includeBounds": include_bounds,
            "includeChildCount": include_child_count,
            "summaryOnly": summary_only,
        },
    }
    if end < len(filtered):
        response["nextOffset"] = end

    if summary_only:
        response["shapeTypeCounts"] = _count_by_key(filtered, "shapeType")
        response["elementTypeCounts"] = _count_by_key(filtered, "elementType")
        response["parentedShapeCount"] = sum(
            1 for shape in filtered if shape.get("parentPresentationId")
        )
        return response

    response["shapes"] = page
    return response


def _transform_diagram_image(
    result: dict[str, Any],
    *,
    include_image: bool,
    format: str,
    max_width: Optional[int],
    max_height: Optional[int],
    quality: int,
) -> dict[str, Any]:
    base64_image = result.get("image")
    if not isinstance(base64_image, str) or not base64_image:
        return dict(result)

    image_bytes = base64.b64decode(base64_image)
    response = dict(result)
    response["imageBytes"] = len(image_bytes)

    if not include_image:
        response.pop("image", None)
        response["imageOmitted"] = True
        return response

    normalized_format = format.lower()
    if normalized_format == "jpg":
        normalized_format = "jpeg"
    if normalized_format not in {"png", "jpeg", "webp"}:
        raise ValueError("format must be one of: png, jpeg, jpg, webp")

    resize_requested = max_width is not None or max_height is not None
    transcode_requested = normalized_format != str(result.get("format", "png")).lower()
    if not resize_requested and not transcode_requested:
        return response

    with Image.open(BytesIO(image_bytes)) as image:
        transformed = image.copy()
        if resize_requested:
            target_width = max_width if max_width is not None and max_width > 0 else image.width
            target_height = (
                max_height if max_height is not None and max_height > 0 else image.height
            )
            transformed.thumbnail((target_width, target_height), Image.Resampling.LANCZOS)

        buffer = BytesIO()
        if normalized_format == "jpeg":
            if transformed.mode not in {"RGB", "L"}:
                flattened = Image.new("RGB", transformed.size, "white")
                alpha_source = transformed.convert("RGBA")
                flattened.paste(alpha_source, mask=alpha_source.getchannel("A"))
                transformed = flattened
            transformed.save(buffer, format="JPEG", quality=max(1, min(quality, 100)))
        elif normalized_format == "webp":
            transformed.save(buffer, format="WEBP", quality=max(1, min(quality, 100)))
        else:
            transformed.save(buffer, format="PNG")

        encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
        response["format"] = "jpg" if normalized_format == "jpeg" else normalized_format
        response["width"] = transformed.width
        response["height"] = transformed.height
        response["image"] = encoded
        response["imageBytes"] = len(buffer.getvalue())
        return response


DiagramIdArg = Annotated[
    str,
    Field(validation_alias=AliasChoices("diagram_id", "diagramId")),
]
ElementIdArg = Annotated[
    str,
    Field(validation_alias=AliasChoices("element_id", "elementId")),
]
ContainmentRootArg = Annotated[
    Optional[str],
    Field(
        validation_alias=AliasChoices(
            "root_id",
            "rootId",
            "parent_id",
            "parentId",
        )
    ),
]
QueryScopeArg = Annotated[
    Optional[str],
    Field(
        validation_alias=AliasChoices(
            "package_id",
            "packageId",
            "package_name",
            "packageName",
            "package",
            "owner_id",
            "ownerId",
            "root_id",
            "rootId",
        )
    ),
]
ContainerPresentationArg = Annotated[
    Optional[str],
    Field(
        validation_alias=AliasChoices(
            "container_presentation_id",
            "containerPresentationId",
        )
    ),
]
ParentPresentationArg = Annotated[
    Optional[str],
    Field(
        validation_alias=AliasChoices(
            "parent_presentation_id",
            "parentPresentationId",
        )
    ),
]


# -- Status / Project --------------------------------------------------------


@mcp.tool()
async def cameo_status() -> dict[str, Any]:
    """Check if CATIA Magic is running and the CameoMCPBridge plugin is responsive.

    Returns:
        JSON with plugin status, capability metadata, and client compatibility
        annotations. If `compatibility.clientCompatible` is false, rebuild and
        redeploy the plugin before attempting write operations.
    """
    result = await client.status()
    return _mcp_result(result)


@mcp.tool()
async def cameo_get_capabilities() -> dict[str, Any]:
    """Get machine-readable plugin capabilities and version-lockstep metadata.

    Use this to confirm which bridge contract the installed Java plugin
    exposes before relying on newer query or diagram semantics.

    Returns:
        JSON with endpoint groups, versions, and client compatibility fields.
    """
    result = await client.get_capabilities()
    return _mcp_result(result)


@mcp.tool()
async def cameo_probe_bridge() -> dict[str, Any]:
    """Probe common local bridge endpoints and report the preferred health paths.

    Use this when a caller is unsure whether the bridge is exposed at `/status`
    or `/api/v1/status`, or wants a concise machine-readable reachability check
    before attempting model work.
    """
    result = await client.probe_bridge()
    return _mcp_result(result)


@mcp.tool()
async def cameo_get_ui_state(summary_only: bool = False) -> dict[str, Any]:
    """Inspect live CATIA Magic UI context.

    Use this after a human opens a diagram or selects symbols. It returns the
    active project, active diagram, selected model elements, selected
    presentations, browser selection, counts, and best-effort warnings for UI
    APIs that are unavailable in the installed CATIA version.
    """
    result = await client.get_ui_state(summary_only=summary_only)
    return _mcp_result(result)


@mcp.tool()
async def cameo_get_active_diagram() -> dict[str, Any]:
    """Get the currently active CATIA Magic diagram as a small payload."""
    result = await client.get_active_diagram()
    return _mcp_result(result)


@mcp.tool()
async def cameo_get_ui_selection() -> dict[str, Any]:
    """Get selected browser elements and selected diagram presentation IDs.

    Use returned IDs as inputs to property dump tools.
    """
    result = await client.get_ui_selection()
    return _mcp_result(result)


@mcp.tool()
async def cameo_list_methodology_packs() -> dict[str, Any]:
    """List built-in methodology packs available in the Phase 2 copilot layer.

    Returns:
        JSON with each pack's phases, recipes, review sections, and evidence
        expectations.
    """
    return _mcp_result(list_methodology_packs())


@mcp.tool()
async def cameo_get_methodology_pack(pack_id: str) -> dict[str, Any]:
    """Get one methodology pack definition.

    Args:
        pack_id: Pack identifier such as `"oosem"`.

    Returns:
        JSON with the selected pack's recipes, phases, naming rules,
        mandatory relationships, and review/evidence structure.
    """
    return _mcp_result(get_methodology_pack(pack_id))


@mcp.tool()
async def cameo_get_methodology_guidance(
    pack_id: str,
    recipe_id: Optional[str] = None,
    recipe_parameters: Optional[dict] = None,
    completed_artifacts: Optional[list[dict]] = None,
) -> dict[str, Any]:
    """Explain what artifact work is missing next for a methodology pack.

    Args:
        pack_id: Pack identifier such as `"oosem"`.
        recipe_id: Optional specific recipe to assess. Omit to get the first
            pending recipe for the pack.
        recipe_parameters: Optional parameter values used to materialize
            recipe-specific names and artifacts.
        completed_artifacts: Optional normalized artifact snapshots already
            present, each shaped like `{"key","kind","name","element_id"}`.

    Returns:
        JSON with blockers, missing artifacts, and recommended next actions.
    """
    return _mcp_result(
        get_workflow_guidance(
            pack_id=pack_id,
            recipe_id=recipe_id,
            recipe_parameters=recipe_parameters,
            completed_artifacts=completed_artifacts,
        )
    )


@mcp.tool()
async def cameo_execute_methodology_recipe(
    pack_id: str,
    recipe_id: str,
    root_package_id: str,
    recipe_parameters: dict,
    completed_artifacts: Optional[list[dict]] = None,
    assumptions: Optional[list[str]] = None,
) -> dict[str, Any]:
    """Execute a bounded OOSEM methodology recipe through structured bridge calls.

    This Phase 2 layer orchestrates existing low-level bridge operations into
    named artifact workflows and returns validation plus a compact review
    packet by default.

    Args:
        pack_id: Pack identifier such as `"oosem"`.
        recipe_id: Recipe identifier from the selected pack.
        root_package_id: Parent package/model that will own the new artifact set.
        recipe_parameters: Parameter values for the recipe.
        completed_artifacts: Optional normalized artifact snapshots already
            present and available for trace/allocation linkage.
        assumptions: Optional assumptions to include in the evidence bundle.

    Returns:
        JSON with workflow guidance, execution plan, receipts, conformance, and
        review-packet markdown.
    """
    return _mcp_result(
        await execute_methodology_recipe(
            pack_id=pack_id,
            recipe_id=recipe_id,
            root_package_id=root_package_id,
            recipe_parameters=recipe_parameters,
            completed_artifacts=completed_artifacts,
            assumptions=assumptions,
        )
    )


@mcp.tool()
async def cameo_validate_methodology_recipe(
    pack_id: str,
    recipe_id: str,
    recipe_parameters: Optional[dict] = None,
    current_artifacts: Optional[list[dict]] = None,
) -> dict[str, Any]:
    """Run methodology conformance checks for an artifact recipe.

    Args:
        pack_id: Pack identifier such as `"oosem"`.
        recipe_id: Recipe identifier from the selected pack.
        recipe_parameters: Optional recipe parameter values used to resolve
            expected names and artifact structure.
        current_artifacts: Normalized artifact snapshots to validate.

    Returns:
        JSON with workflow guidance and conformance findings.
    """
    return _mcp_result(
        await validate_methodology_recipe(
            pack_id=pack_id,
            recipe_id=recipe_id,
            recipe_parameters=recipe_parameters,
            current_artifacts=current_artifacts,
        )
    )


@mcp.tool()
async def cameo_generate_review_packet(
    pack_id: str,
    recipe_id: str,
    recipe_parameters: Optional[dict] = None,
    current_artifacts: Optional[list[dict]] = None,
    assumptions: Optional[list[str]] = None,
    notes: Optional[list[str]] = None,
) -> dict[str, Any]:
    """Generate a compact methodology review packet without mutating the model.

    Args:
        pack_id: Pack identifier such as `"oosem"`.
        recipe_id: Recipe identifier from the selected pack.
        recipe_parameters: Optional recipe parameter values used to resolve
            expected names and artifact structure.
        current_artifacts: Normalized artifact snapshots to include.
        assumptions: Optional assumptions to include in the packet.
        notes: Optional freeform notes to include in the packet.

    Returns:
        JSON with a structured evidence bundle plus Markdown review packet text.
    """
    return _mcp_result(
        await generate_review_packet(
            pack_id=pack_id,
            recipe_id=recipe_id,
            recipe_parameters=recipe_parameters,
            current_artifacts=current_artifacts,
            assumptions=assumptions,
            notes=notes,
        )
    )


@mcp.tool()
async def cameo_get_project() -> dict[str, Any]:
    """Get current project info: name, file path, and primary model ID.

    Returns:
        JSON with project name, file location, and root model element ID.
    """
    result = await client.get_project()
    return _mcp_result(result)


@mcp.tool()
async def cameo_save_project() -> dict[str, Any]:
    """Save the current project to disk.

    Call this after making changes you want to persist.

    Returns:
        JSON confirmation of save operation.
    """
    result = await client.save_project()
    return _mcp_result(result)


# -- Session Management -------------------------------------------------------


@mcp.tool()
async def cameo_reset_session() -> dict[str, Any]:
    """Force-close any stuck model editing session in CATIA Magic.

    Use this tool when you encounter errors like:
    - "Session is already created" — another edit session was left open
    - Macro execution errors that leave the model in a locked state
    - Any operation that times out or fails mid-transaction

    This is a recovery tool. It discards any uncommitted changes from the
    stuck session and returns the model to a clean, unlocked state so that
    subsequent operations can proceed normally.

    You do NOT need to call this before normal operations — only when
    something has gone wrong and the bridge is reporting session conflicts.

    Returns:
        JSON confirmation that the session was reset.
    """
    result = await client.reset_session()
    return _mcp_result(result)

# -- Elements -----------------------------------------------------------------


@mcp.tool()
async def cameo_query_elements(
    type: Optional[str] = None,
    name: Optional[str] = None,
    package_id: QueryScopeArg = None,
    stereotype: Optional[str] = None,
    recursive: bool = True,
    limit: int = 200,
    offset: int = 0,
    view: str = "compact",
) -> dict[str, Any]:
    """Search for model elements matching filters.

    Use this to find existing elements before creating new ones or
    establishing relationships.

    Args:
        type: UML/SysML metaclass to filter by. Common values:
              Class, Package, Property, Port, Activity, StateMachine, State,
              Pseudostate, Block (SysML), Requirement (SysML),
              ConstraintBlock (SysML), FlowProperty (SysML),
              InterfaceBlock, ValueType.
        name: Exact or partial element name to match.
        package_id: Restrict search to an owning/root element ID. Despite the
                    legacy name in older builds, the underlying bridge scopes
                    by element ID, not package display name. CamelCase aliases
                    such as `packageId`, `ownerId`, and `rootId` are accepted.
        stereotype: Filter by applied stereotype name (e.g. "block",
                    "requirement", "interfaceBlock").
        recursive: Whether to search recursively into sub-packages.
                   Defaults to True.
        limit: Maximum number of matches to return. Defaults to 200.
        offset: Zero-based offset into the ordered result set. Defaults to 0.
        view: Response shape: "compact" (default) or "full".

    Returns:
        JSON object with paginated matches, applied filters, and cursor-like
        paging metadata.
    """
    result = await client.query_elements(
        type=type,
        name=name,
        package=package_id,
        stereotype=stereotype,
        recursive=recursive,
        limit=limit,
        offset=offset,
        view=view,
    )
    return _mcp_result(result)


@mcp.tool()
async def cameo_get_element(element_id: str) -> dict[str, Any]:
    """Get full details of a model element.

    Returns all properties including name, type, documentation,
    applied stereotypes, tagged values, and owned elements.

    Args:
        element_id: The unique ID of the element (UUID string from Cameo).

    Returns:
        JSON with complete element details.
    """
    result = await client.get_element(element_id)
    return _mcp_result(result)


@mcp.tool()
async def cameo_get_containment_tree(
    root_id: ContainmentRootArg = None,
    depth: int = 3,
    view: str = "compact",
) -> dict[str, Any]:
    """Browse the containment tree structure.

    Use this to understand the project hierarchy before creating or
    modifying elements. Start with no root_id to see top-level packages.

    Args:
        root_id: Element ID to use as root. Omit to start from the
                 project model root.
        depth: How many levels deep to traverse. Defaults to 3.
        view: Response shape: "compact" (default) or "full".

    For large models, prefer `cameo_list_containment_children`; this recursive
    endpoint can still produce very large payloads.

    Returns:
        JSON tree structure with element IDs, names, types, and children.
    """
    result = await client.get_containment_tree(
        root_id=root_id,
        depth=depth,
        view=view,
    )
    return _mcp_result(result)


@mcp.tool()
async def cameo_list_containment_children(
    root_id: ContainmentRootArg = None,
    limit: int = 50,
    offset: int = 0,
    type: Optional[str] = None,
    name: Optional[str] = None,
    stereotype: Optional[str] = None,
    view: str = "compact",
) -> dict[str, Any]:
    """List a compact, paginated slice of the containment tree.

    Use this for large models when a full recursive tree would be too large
    to inspect or pass around. It returns only the immediate children of the
    selected root, along with child counts and paging metadata.

    Args:
        root_id: Element ID to use as root. Omit to start from the project
                 primary model.
        limit: Maximum number of immediate children to return. Defaults to 50.
        offset: Zero-based offset into the child list. Defaults to 0.
        type: Optional type filter on immediate children.
        name: Optional case-insensitive substring filter on immediate children.
        stereotype: Optional applied stereotype filter on immediate children.
        view: Response shape: "compact" (default) or "full".

    Returns:
        JSON-compatible object with the selected root, compact children, and
        paging metadata.
    """
    result = await client.list_containment_children(
        root_id=root_id,
        limit=limit,
        offset=offset,
        type=type,
        name=name,
        stereotype=stereotype,
        view=view,
    )
    return _mcp_result(result)

@mcp.tool()
async def cameo_create_element(
    type: str,
    name: str,
    parent_id: str,
    stereotype: Optional[str] = None,
    documentation: Optional[str] = None,
    behavior_id: Optional[str] = None,
    represents_id: Optional[str] = None,
    type_id: Optional[str] = None,
    lower: Optional[int] = None,
    upper: Optional[int | str] = None,
    is_ordered: Optional[bool] = None,
    is_unique: Optional[bool] = None,
    aggregation: Optional[str] = None,
    is_behavior: Optional[bool] = None,
    is_conjugated: Optional[bool] = None,
    is_service: Optional[bool] = None,
    direction: Optional[str] = None,
    metaclasses: Optional[list[str]] = None,
) -> dict[str, Any]:
    """Create a new model element.

    Args:
        type: The UML/SysML element type alias. Structured creation currently
              supports:
              - Structural: Package, Profile, Class, Property, Port,
                FlowProperty, Interface, DataType, Enumeration, Signal,
                Component, Operation
              - Profiles: Stereotype (owned by a Profile; use metaclasses to bind)
              - SysML aliases: Block, ConstraintBlock, InterfaceBlock,
                Requirement, ValueType, FlowProperty
              - Behavioral: Activity, UseCase, Actor, StateMachine, State
              - State nodes: Pseudostate (initial kind), InitialState
              - Activity nodes: InitialNode, ActivityFinalNode,
                FlowFinalNode, DecisionNode, MergeNode, ForkNode, JoinNode
              - Actions: CallBehaviorAction, OpaqueAction
              - Partitions: ActivityPartition
              - Pins: InputPin, OutputPin
              - Other: Comment, Constraint
              SysML aliases rely on the SysML profile being available; if the
              bridge cannot resolve the required stereotype, creation fails
              instead of silently producing a plain UML element.
        name: Display name for the element.
        parent_id: ID of the parent element (usually a Package or Block).
        stereotype: Optional stereotype to apply on creation (e.g. "block",
                    "requirement", "valueType"). When omitted for a SysML alias
                    such as Block or Requirement, the bridge applies the
                    corresponding SysML stereotype automatically.
        documentation: Optional description/documentation string.
        behavior_id: For CallBehaviorAction type only -- links the action to
                     the Activity it invokes. The referenced element must be
                     an Activity or other Behavior.
        represents_id: For ActivityPartition (swimlane) type only -- links the
                       partition to the Block or Class it represents (the
                       performer).
        type_id: Optional type element ID for TypedElement creation such as
                 Property, Port, or FlowProperty.
        lower: Optional lower multiplicity bound for multiplicity-bearing
               elements such as Property and Port.
        upper: Optional upper multiplicity bound. Use -1 or "*" for unlimited.
        is_ordered: Optional multiplicity ordering flag.
        is_unique: Optional multiplicity uniqueness flag.
        aggregation: Optional Property aggregation value: "none", "shared",
                     or "composite".
        is_behavior: Optional Port behavior flag.
        is_conjugated: Optional Port conjugation flag.
        is_service: Optional Port service flag.
        direction: Optional FlowProperty direction tag value.
        metaclasses: For Stereotype type only -- list of UML metaclass names
                     to bind, such as ["Class"] or ["Property"].

    Returns:
        JSON with the created element ID and details.
    """
    result = await client.create_element(
        type=type,
        name=name,
        parent_id=parent_id,
        stereotype=stereotype,
        documentation=documentation,
        behavior_id=behavior_id,
        represents_id=represents_id,
        type_id=type_id,
        lower=lower,
        upper=upper,
        is_ordered=is_ordered,
        is_unique=is_unique,
        aggregation=aggregation,
        is_behavior=is_behavior,
        is_conjugated=is_conjugated,
        is_service=is_service,
        direction=direction,
        metaclasses=metaclasses,
    )
    return _mcp_result(result)


@mcp.tool()
async def cameo_modify_element(
    element_id: str,
    name: Optional[str] = None,
    documentation: Optional[str] = None,
) -> dict[str, Any]:
    """Modify an existing element name or documentation.

    Args:
        element_id: The unique ID of the element to modify.
        name: New name for the element. Omit to leave unchanged.
        documentation: New documentation string. Omit to leave unchanged.

    Returns:
        JSON with the updated element details.
    """
    result = await client.modify_element(
        element_id=element_id,
        name=name,
        documentation=documentation,
    )
    return _mcp_result(result)


@mcp.tool()
async def cameo_delete_element(element_id: str) -> dict[str, Any]:
    """Delete a model element.

    Warning: This permanently removes the element and all its owned
    sub-elements. Relationships connected to the element are also removed.

    Args:
        element_id: The unique ID of the element to delete.

    Returns:
        JSON confirmation of deletion.
    """
    result = await client.delete_element(element_id)
    return _mcp_result(result)

# -- Stereotypes / Tagged Values ----------------------------------------------


@mcp.tool()
async def cameo_apply_stereotype(
    element_id: str,
    stereotype: str,
    profile: Optional[str] = None,
) -> dict[str, Any]:
    """Apply a stereotype to an element.

    Args:
        element_id: The unique ID of the target element.
        stereotype: Name of the stereotype (e.g. "block", "requirement",
                    "valueType", "testCase", "rationale", "flowPort").
        profile: Optional profile name if the stereotype is ambiguous
                 (e.g. "SysML", "MARTE", "MD Customization for SysML").

    Returns:
        JSON confirmation with updated stereotype list.
    """
    result = await client.apply_stereotype(
        element_id=element_id,
        stereotype=stereotype,
        profile=profile,
    )
    return _mcp_result(result)


@mcp.tool()
async def cameo_set_tagged_values(
    element_id: str,
    stereotype: str,
    values: dict,
) -> dict[str, Any]:
    """Set tagged values on a stereotyped element.

    Tagged values are stereotype-specific properties. The element must
    already have the stereotype applied.

    Args:
        element_id: The unique ID of the element.
        stereotype: The stereotype whose tags to set (e.g. "requirement").
        values: Dictionary of tag-name to value mappings. Example:
                {"id": "REQ-001", "text": "The system shall...",
                 "priority": "high"}.

    Returns:
        JSON confirmation with updated tagged values.
    """
    result = await client.set_tagged_values(
        element_id=element_id,
        stereotype=stereotype,
        values=values,
    )
    return _mcp_result(result)


@mcp.tool()
async def cameo_set_stereotype_metaclasses(
    stereotype_id: str,
    metaclasses: list[str],
) -> Any:
    """Set the base metaclasses for a stereotype using Cameo's native API.

    Use this instead of Groovy macros when defining custom profiles. It avoids
    manual Extension wiring and keeps the model consistent.

    Common examples:
    - ["Class"] for stereotypes like logical or physical
    - ["Property"] for stereotypes like mop or store

    Args:
        stereotype_id: The element ID of the target stereotype.
        metaclasses: Non-empty list of UML metaclass names to bind.

    Returns:
        JSON confirmation with the stereotype and resolved base metaclasses.
    """
    result = await client.set_stereotype_metaclasses(
        stereotype_id=stereotype_id,
        metaclasses=metaclasses,
    )
    return _mcp_result(result)


@mcp.tool()
async def cameo_apply_profile(
    package_id: str,
    profile_id: Optional[str] = None,
    profile_name: Optional[str] = None,
) -> Any:
    """Apply a profile to a model/package so its stereotypes become usable.

    Use this after creating a custom profile or before applying custom
    stereotypes in a fresh model.

    Args:
        package_id: Package or model ID that should receive the profile.
        profile_id: Explicit profile element ID to apply.
        profile_name: Profile name to resolve when the ID is not known.

    Returns:
        JSON confirmation with the applied profile and package details.
    """
    result = await client.apply_profile(
        package_id=package_id,
        profile_id=profile_id,
        profile_name=profile_name,
    )
    return _mcp_result(result)

# -- Relationships ------------------------------------------------------------


@mcp.tool()
async def cameo_create_relationship(
    type: str,
    source_id: str,
    target_id: str,
    name: Optional[str] = None,
    guard: Optional[str] = None,
    owner_id: Optional[str] = None,
    source_part_with_port_id: Optional[str] = None,
    target_part_with_port_id: Optional[str] = None,
    realizing_connector_id: Optional[str] = None,
    conveyed_ids: Optional[list[str]] = None,
    item_property_id: Optional[str] = None,
) -> dict[str, Any]:
    """Create a relationship between two elements.

    Args:
        type: Structured relationship type. Supported values are:
              Association, DirectedAssociation, Composition,
              Generalization, Dependency, Include, Extend,
              ControlFlow, ObjectFlow, Allocate, Satisfy,
              Derive, Refine, Trace, Verify, Transition, Connector,
              InformationFlow, ItemFlow.
        source_id: ID of the source element.
        target_id: ID of the target element.
        name: Optional name for the relationship.
        guard: Optional guard condition for Transition, ControlFlow, or
               ObjectFlow.
        owner_id: Required for Connector. ID of the owning structured
                  classifier that should contain the connector. Required for
                  InformationFlow and ItemFlow too; use the owning package or
                  an element within the IBD context. The bridge resolves the
                  actual relationship containment to the nearest package.
        source_part_with_port_id: Optional for Connector. Property ID for the
                  source end's partWithPort when connecting a nested port.
        target_part_with_port_id: Optional for Connector. Property ID for the
                  target end's partWithPort when connecting a nested port.
        realizing_connector_id: Optional for InformationFlow or ItemFlow.
                  Connector ID that realizes the conveyed item flow on an IBD.
        conveyed_ids: Optional for InformationFlow or ItemFlow. Classifier IDs
                  representing the conveyed item/block types.
        item_property_id: Optional for ItemFlow. Property ID of the
                  FlowProperty that types the item flow payload/direction.

    Returns:
        JSON with the created relationship ID and details.
    """
    result = await client.create_relationship(
        type=type,
        source_id=source_id,
        target_id=target_id,
        name=name,
        guard=guard,
        owner_id=owner_id,
        source_part_with_port_id=source_part_with_port_id,
        target_part_with_port_id=target_part_with_port_id,
        realizing_connector_id=realizing_connector_id,
        conveyed_ids=conveyed_ids,
        item_property_id=item_property_id,
    )
    return _mcp_result(result)


@mcp.tool()
async def cameo_get_relationships(
    element_id: ElementIdArg,
    direction: str = "both",
) -> dict[str, Any]:
    """Get relationships for an element.

    Args:
        element_id: The unique ID of the element.
        direction: Filter by direction: "incoming", "outgoing", or "both".
                   Defaults to "both".

    Returns:
        JSON array of relationships with type, source, target, and metadata.
    """
    result = await client.get_relationships(
        element_id=element_id,
        direction=direction,
    )
    return _mcp_result(result)

# -- Matrices -----------------------------------------------------------------


@mcp.tool()
async def cameo_list_matrices(
    kind: Optional[str] = None,
    owner_id: Optional[str] = None,
) -> dict[str, Any]:
    """List supported native matrix artifacts in the current project.

    This matrix family is intentionally separate from the diagram shape/path API.
    It targets Cameo's native matrix artifacts, not arbitrary tables.

    Args:
        kind: Optional matrix kind filter. Supported values:
              - "refine" for native Refine Requirement Matrix artifacts
              - "derive" for native Derive Requirement Matrix artifacts
              - "satisfy" for native Satisfy Requirement Matrix artifacts
              - "allocation" for native SysML Allocation Matrix artifacts
        owner_id: Optional package/namespace ID that owns the matrix artifact.

    Returns:
        JSON with matching matrix IDs, names, native matrix types, and owners.
    """
    result = await client.list_matrices(
        kind=kind,
        owner_id=owner_id,
    )
    return _mcp_result(result)


@mcp.tool()
async def cameo_get_matrix(matrix_id: str) -> dict[str, Any]:
    """Read one supported native matrix with populated cell data.

    Supported matrix artifacts currently include:
    - Refine Requirement Matrix
    - Derive Requirement Matrix
    - Satisfy Requirement Matrix
    - SysML Allocation Matrix

    The response includes row and column elements plus only the populated cells.
    Empty cells are omitted from `populatedCells`; infer gaps from the row/column
    cross-product.

    Args:
        matrix_id: Diagram ID of the matrix artifact.

    Returns:
        JSON with matrix metadata, scope/type settings, rows, columns, and
        populated cells with their underlying relationship causes.
    """
    result = await client.get_matrix(matrix_id)
    return _mcp_result(result)


@mcp.tool()
async def cameo_verify_matrix_consistency(
    matrix_id: str,
    expected_row_ids: Optional[list[str]] = None,
    expected_column_ids: Optional[list[str]] = None,
    expected_dependency_names: Optional[list[str]] = None,
    min_populated_cell_count: int = 0,
    min_density: float = 0.0,
) -> dict[str, Any]:
    """Run quantitative consistency checks against one native requirement matrix.

    This wraps cameo_get_matrix with reusable checks for expected row/column
    membership, dependency names, populated-cell count, and matrix density.

    Args:
        matrix_id: Diagram ID of the matrix artifact to validate.
        expected_row_ids: Optional element IDs that must appear in the row domain.
        expected_column_ids: Optional element IDs that must appear in the
            column domain.
        expected_dependency_names: Optional relationship names that must appear
            in populated matrix cells.
        min_populated_cell_count: Minimum populated-cell count required.
        min_density: Minimum required populated-cell density over the full
            row/column cross-product.

    Returns:
        JSON with pass/fail status, detailed checks, and computed metrics.
    """
    matrix = await client.get_matrix(matrix_id)
    result = verification.verify_matrix_consistency(
        matrix,
        expected_row_ids=expected_row_ids,
        expected_column_ids=expected_column_ids,
        expected_dependency_names=expected_dependency_names,
        min_populated_cell_count=min_populated_cell_count,
        min_density=min_density,
    )
    result["matrix"] = matrix
    return _mcp_result(result)


@mcp.tool()
async def cameo_verify_activity_flow_semantics(
    diagram_id: str,
    max_partition_depth: int = 1,
    allow_stereotype_partition_labels: bool = False,
) -> dict[str, Any]:
    """Validate whether one activity diagram behaves like a coherent workflow.

    Discovery
    ---------
    - Use `cameo_list_diagrams` to find the activity diagram ID.
    - Use `cameo_list_diagram_shapes` if you want to inspect the diagram canvas
      before running this validator.

    When to use
    -----------
    - Activity diagrams that look like the right nouns/actions but may be
      missing a real executable control/object flow.
    - Swimlane layouts that may contain extra container layers or isolated
      action islands.

    Args:
        diagram_id: Activity diagram ID.
        max_partition_depth: Maximum allowed nested activity-partition depth.
        allow_stereotype_partition_labels: When false, flags partition labels
            that look like stereotype notation such as `«allocate»`.

    Returns:
        JSON with semantic checks, diagram readback, and the flattened flow
        graph used for validation.
    """
    result = await verify_activity_flow_semantics_for_diagram(
        diagram_id,
        max_partition_depth=max_partition_depth,
        allow_stereotype_partition_labels=allow_stereotype_partition_labels,
    )
    return _mcp_result(result)


@mcp.tool()
async def cameo_verify_port_boundary_consistency(
    interface_block_ids: list[str],
    allow_shared_flow_property_names: Optional[list[str]] = None,
) -> dict[str, Any]:
    """Validate interface-block flow-property ownership and duplication.

    Discovery
    ---------
    - Use `cameo_query_elements(type="Class", stereotype="InterfaceBlock")`
      or `cameo_query_elements(stereotype="InterfaceBlock")` to find the
      interface blocks from the relevant port BDD.

    When to use
    -----------
    - Port/interface reviews where the same artifact may have been copied onto
      multiple interfaces without reasoning about boundary ownership.
    - Suspected directionality mistakes on flow properties.

    Args:
        interface_block_ids: Interface block IDs to inspect together as one
            boundary-validation set.
        allow_shared_flow_property_names: Optional names that are allowed to
            appear on more than one interface block.

    Returns:
        JSON with duplicate-flow, direction, and ownership checks plus the
        extracted interface-block and flow-property readback.
    """
    result = await verify_port_boundary_consistency_for_interfaces(
        interface_block_ids,
        allow_shared_flow_property_names=allow_shared_flow_property_names,
    )
    return _mcp_result(result)


@mcp.tool()
async def cameo_verify_requirement_quality(
    requirement_ids: list[str],
    require_id: bool = True,
    require_measurement: bool = True,
    min_text_length: int = 20,
) -> dict[str, Any]:
    """Validate whether SysML requirements contain real requirement content.

    Discovery
    ---------
    - Use `cameo_query_elements(stereotype="Requirement")` or your package
      query flow to collect requirement IDs before calling this tool.

    When to use
    -----------
    - Requirement diagrams that have names and IDs but may have blank or weak
      requirement statements.
    - Release gates for measurable, reviewable requirement content.

    Args:
        requirement_ids: Requirement element IDs to evaluate.
        require_id: When true, fail requirements that have no requirement ID.
        require_measurement: When true, fail requirements that do not look
            directive and measurable.
        min_text_length: Minimum text length for a requirement statement to
            count as non-trivial.

    Returns:
        JSON with per-requirement assessments and aggregate quality checks.
    """
    result = await verify_requirement_quality_for_ids(
        requirement_ids,
        require_id=require_id,
        require_measurement=require_measurement,
        min_text_length=min_text_length,
    )
    return _mcp_result(result)


@mcp.tool()
async def cameo_verify_cross_diagram_traceability(
    activity_diagram_id: Optional[str] = None,
    interface_block_ids: Optional[list[str]] = None,
    ibd_diagram_id: Optional[str] = None,
    requirement_ids: Optional[list[str]] = None,
    architecture_element_ids: Optional[list[str]] = None,
) -> dict[str, Any]:
    """Validate traceability across activity, port, IBD, and requirement views.

    Discovery
    ---------
    - Use `cameo_list_diagrams` to find activity/IBD diagram IDs.
    - Use `cameo_query_elements(stereotype="InterfaceBlock")` for interface
      blocks and `cameo_query_elements(stereotype="Requirement")` for
      requirements.

    When to use
    -----------
    - Cross-view reviews where labels appear plausible but the mapping between
      behavior, interfaces, structure, and requirements may be weak.
    - Review packets that need a compact traceability summary.

    Args:
        activity_diagram_id: Optional activity diagram to extract behavior-side
            terms from.
        interface_block_ids: Optional interface blocks to compare against the
            activity vocabulary.
        ibd_diagram_id: Optional IBD to compare against the activity
            vocabulary.
        requirement_ids: Optional requirements to trace into the architecture
            element set.
        architecture_element_ids: Optional architecture element IDs that count
            as valid requirement trace targets.

    Returns:
        JSON with whichever traceability checks are applicable to the supplied
        artifact set.
    """
    result = await run_cross_diagram_traceability(
        activity_diagram_id=activity_diagram_id,
        interface_block_ids=interface_block_ids,
        ibd_diagram_id=ibd_diagram_id,
        requirement_ids=requirement_ids,
        architecture_element_ids=architecture_element_ids,
    )
    return _mcp_result(result)


@mcp.tool()
async def cameo_detect_cross_diagram_inconsistencies(
    activity_diagram_id: Optional[str] = None,
    interface_block_ids: Optional[list[str]] = None,
    ibd_diagram_id: Optional[str] = None,
    requirement_ids: Optional[list[str]] = None,
    architecture_element_ids: Optional[list[str]] = None,
    allow_shared_flow_property_names: Optional[list[str]] = None,
    require_id: bool = True,
    require_measurement: bool = True,
    min_requirement_text_length: int = 20,
    max_partition_depth: int = 1,
    allow_stereotype_partition_labels: bool = False,
) -> dict[str, Any]:
    """Detect cross-diagram inconsistencies and return a previewable remediation plan.

    This is the non-mutating semantic auto-remediation entry point. It reuses
    the bridge-backed semantic validation helpers and then returns structured
    receipts plus a `patchPlan.steps` preview the caller can inspect before any
    future apply step.
    """
    result = await detect_cross_diagram_inconsistencies_for_artifacts(
        activity_diagram_id=activity_diagram_id,
        interface_block_ids=interface_block_ids,
        ibd_diagram_id=ibd_diagram_id,
        requirement_ids=requirement_ids,
        architecture_element_ids=architecture_element_ids,
        allow_shared_flow_property_names=allow_shared_flow_property_names,
        require_id=require_id,
        require_measurement=require_measurement,
        min_requirement_text_length=min_requirement_text_length,
        max_partition_depth=max_partition_depth,
        allow_stereotype_partition_labels=allow_stereotype_partition_labels,
    )
    return _mcp_result(result)


@mcp.tool()
async def cameo_build_cross_diagram_remediation_plan(
    activity_validation: Optional[dict[str, Any]] = None,
    port_validation: Optional[dict[str, Any]] = None,
    requirement_validation: Optional[dict[str, Any]] = None,
    trace_validation: Optional[dict[str, Any]] = None,
    architecture_elements: Optional[list[dict[str, Any]]] = None,
) -> dict[str, Any]:
    """Build a previewable remediation plan from existing validation payloads."""
    result = build_cross_diagram_remediation_plan(
        activity_validation=activity_validation,
        port_validation=port_validation,
        requirement_validation=requirement_validation,
        trace_validation=trace_validation,
        architecture_elements=architecture_elements,
    )
    return _mcp_result(result)


@mcp.tool()
async def cameo_proof_model_text(
    root_package_id: Optional[str] = None,
    requirement_ids: Optional[list[str]] = None,
    comment_ids: Optional[list[str]] = None,
    state_ids: Optional[list[str]] = None,
    transition_ids: Optional[list[str]] = None,
    diagram_ids: Optional[list[str]] = None,
    auto_apply: bool = False,
) -> dict[str, Any]:
    """Proof model text across requirements, comments, states, transitions, and diagram labels.

    Provide `root_package_id` for an opinionated package-wide sweep, or pass
    explicit element/diagram IDs for narrower analysis. When `auto_apply=true`,
    the tool applies safe rename/text edits through the bridge and returns
    apply receipts alongside the proofing report.
    """
    result = await proof_model_text(
        root_package_id=root_package_id,
        requirement_ids=requirement_ids,
        comment_ids=comment_ids,
        state_ids=state_ids,
        transition_ids=transition_ids,
        diagram_ids=diagram_ids,
        auto_apply=auto_apply,
    )
    return _mcp_result(result)


@mcp.tool()
async def cameo_apply_proofing_patch_plan(
    patch_plan: dict[str, Any],
) -> dict[str, Any]:
    """Apply a previously generated proofing patch plan to the live model."""
    result = await apply_proofing_patch_plan(patch_plan)
    return _mcp_result(result)


@mcp.tool()
async def cameo_compare_expected_artifact_list(
    expected_artifacts: list[dict[str, Any]],
    current_artifacts: Optional[list[dict[str, Any]]] = None,
) -> dict[str, Any]:
    """Compare discovered/current artifacts against an expected methodology artifact list."""
    result = compare_against_expected_artifact_list(
        expected_artifacts=expected_artifacts,
        current_artifacts=current_artifacts,
    )
    return _mcp_result(result)


@mcp.tool()
async def cameo_validate_methodology_package(
    pack_id: str,
    recipe_id: Optional[str] = None,
    root_package_id: Optional[str] = None,
    current_artifacts: Optional[list[dict[str, Any]]] = None,
    expected_artifacts: Optional[list[dict[str, Any]]] = None,
) -> dict[str, Any]:
    """Validate a package or recipe scope against the methodology definition."""
    result = await validate_methodology_package_live(
        pack_id,
        recipe_id=recipe_id,
        root_package_id=root_package_id,
        current_artifacts=current_artifacts,
        expected_artifacts=expected_artifacts,
    )
    return _mcp_result(result)


@mcp.tool()
async def cameo_export_required_diagrams(
    pack_id: str,
    recipe_id: Optional[str] = None,
    root_package_id: Optional[str] = None,
    current_artifacts: Optional[list[dict[str, Any]]] = None,
    expected_artifacts: Optional[list[dict[str, Any]]] = None,
    export_format: str = "png",
    output_dir: Optional[str] = None,
) -> dict[str, Any]:
    """Plan or execute export of methodology-required diagrams.

    Omit `output_dir` for a dry-run export queue. Provide it to write the
    diagram images to disk.
    """
    result = await export_required_diagrams_live(
        pack_id,
        recipe_id=recipe_id,
        root_package_id=root_package_id,
        current_artifacts=current_artifacts,
        expected_artifacts=expected_artifacts,
        export_format=export_format,
        output_dir=output_dir,
    )
    return _mcp_result(result)


@mcp.tool()
async def cameo_assemble_ppt_pdf(
    pack_id: str,
    recipe_id: Optional[str] = None,
    root_package_id: Optional[str] = None,
    current_artifacts: Optional[list[dict[str, Any]]] = None,
    expected_artifacts: Optional[list[dict[str, Any]]] = None,
    output_dir: Optional[str] = None,
    title: Optional[str] = None,
    pptx_name: Optional[str] = None,
    pdf_name: Optional[str] = None,
    export_format: str = "png",
) -> dict[str, Any]:
    """Plan or assemble a PPT/PDF package from methodology-required diagrams."""
    result = await assemble_ppt_pdf_live(
        pack_id,
        recipe_id=recipe_id,
        root_package_id=root_package_id,
        current_artifacts=current_artifacts,
        expected_artifacts=expected_artifacts,
        output_dir=output_dir,
        title=title,
        pptx_name=pptx_name,
        pdf_name=pdf_name,
        export_format=export_format,
    )
    return _mcp_result(result)


@mcp.tool()
async def cameo_list_matrix_kinds() -> dict[str, Any]:
    """List the validated native matrix kinds and example type domains."""
    return {
        "count": len(client.VALIDATED_MATRIX_KINDS),
        "matrixKinds": client.VALIDATED_MATRIX_KINDS,
    }


@mcp.tool()
async def cameo_create_matrix(
    kind: str,
    parent_id: str,
    name: Optional[str] = None,
    scope_id: Optional[str] = None,
    row_scope_id: Optional[str] = None,
    column_scope_id: Optional[str] = None,
    row_types: Optional[list[str]] = None,
    column_types: Optional[list[str]] = None,
) -> dict[str, Any]:
    """Create a supported native matrix artifact.

    This creates Cameo's native matrix types:
    - "refine" -> Refine Requirement Matrix
    - "derive" -> Derive Requirement Matrix
    - "satisfy" -> Satisfy Requirement Matrix
    - "allocation" -> SysML Allocation Matrix
    - "dependency" -> Dependency Matrix

    The bridge configures the matrix to show all relevant rows/columns inside the
    selected scope so missing traceability remains visible.

    Args:
        kind: Matrix kind: "refine", "derive", "satisfy", "allocation", or
              "dependency".
              Aliases such as "Refine Requirement Matrix",
              "Satisfy Requirement Matrix", and "System Allocation Matrix"
              are normalized automatically.
        parent_id: Namespace/package ID that will own the matrix artifact.
        name: Optional display name. Defaults to Cameo's native matrix type name.
        scope_id: Optional shared scope root for both rows and columns. Defaults
                  to parent_id when row_scope_id/column_scope_id are omitted.
        row_scope_id: Optional explicit row scope root.
        column_scope_id: Optional explicit column scope root.
        row_types: Optional row-domain type tokens. Each token may be a UML
                  metaclass such as "Activity" or "Property", or a stereotype
                  such as "Block", "Requirement", or "valueProperty". When
                  omitted, the bridge uses the native matrix defaults.
        column_types: Optional column-domain type tokens using the same
                  resolution rules as row_types.

    Returns:
        JSON confirmation with the created matrix artifact and its initial
        populated row/column/cell data.
    """
    result = await client.create_matrix(
        kind=kind,
        parent_id=parent_id,
        name=name,
        scope_id=scope_id,
        row_scope_id=row_scope_id,
        column_scope_id=column_scope_id,
        row_types=row_types,
        column_types=column_types,
    )
    return _mcp_result(result)

# -- Generic Tables -----------------------------------------------------------


@mcp.tool()
async def cameo_list_generic_tables() -> dict[str, Any]:
    """List native Generic Table artifacts in the current project."""
    result = await client.list_generic_tables()
    return _mcp_result(result)


@mcp.tool()
async def cameo_get_generic_table(table_id: str) -> dict[str, Any]:
    """Get one native Generic Table with row, column, and cell data."""
    result = await client.get_generic_table(table_id)
    return _mcp_result(result)


@mcp.tool()
async def cameo_list_generic_table_columns(
    element_id: Optional[str] = None,
    element_type: Optional[str] = None,
) -> dict[str, Any]:
    """List possible native Generic Table column ids for an element or type.

    Args:
        element_id: Optional basis element id, such as an existing Block.
        element_type: Optional element type token, such as "Block".
                     Provide element_id or element_type.
    """
    result = await client.list_generic_table_columns(
        element_id=element_id,
        element_type=element_type,
    )
    return _mcp_result(result)


@mcp.tool()
async def cameo_create_generic_table(
    parent_id: str,
    name: Optional[str] = None,
    element_types: Optional[list[str]] = None,
    scope_ids: Optional[list[str]] = None,
    row_element_ids: Optional[list[str]] = None,
    column_ids: Optional[list[str]] = None,
) -> dict[str, Any]:
    """Create and configure a native Generic Table artifact.

    Args:
        parent_id: Namespace/package ID that will own the table.
        name: Optional display name.
        element_types: Optional native table element types, such as ["Block"].
        scope_ids: Optional table scope element IDs.
        row_element_ids: Optional explicit row element IDs.
        column_ids: Optional Generic Table column IDs to display.
    """
    result = await client.create_generic_table(
        parent_id=parent_id,
        name=name,
        element_types=element_types,
        scope_ids=scope_ids,
        row_element_ids=row_element_ids,
        column_ids=column_ids,
    )
    return _mcp_result(result)

# -- Relation Maps ------------------------------------------------------------


@mcp.tool()
async def cameo_list_relation_maps() -> dict[str, Any]:
    """List native Relation Map artifacts in the current project."""
    result = await client.list_relation_maps()
    return _mcp_result(result)


@mcp.tool()
async def cameo_get_relation_map(relation_map_id: str) -> dict[str, Any]:
    """Get one native Relation Map with persisted graph settings.

    Args:
        relation_map_id: ID of the Relation Map diagram element.
    """
    result = await client.get_relation_map(relation_map_id)
    return _mcp_result(result)


@mcp.tool()
async def cameo_create_relation_map(
    parent_id: str,
    name: Optional[str] = None,
    context_element_id: Optional[str] = None,
    scope_ids: Optional[list[str]] = None,
    element_type_ids: Optional[list[str]] = None,
    dependency_criteria: Optional[list[str]] = None,
    depth: Optional[int] = None,
    layout: Optional[str] = None,
    legend_enabled: Optional[bool] = None,
    show_full_types: Optional[bool] = None,
    show_stereotypes: Optional[bool] = None,
    show_parameters: Optional[bool] = None,
    show_element_numbers: Optional[bool] = None,
    single_node_per_element: Optional[bool] = None,
    short_node_names: Optional[bool] = None,
    types_include_subtypes: Optional[bool] = None,
    types_include_custom_types: Optional[bool] = None,
    make_element_as_context: Optional[bool] = None,
) -> dict[str, Any]:
    """Create and configure a native Relation Map artifact.

    Prefer this over `cameo_create_diagram(type="RelationMap")` when the map
    must render relationships. It writes Cameo's native graph settings:
    context element, scope roots, optional element-type filters, dependency
    criteria, depth, layout, and display flags.

    Args:
        parent_id: Namespace/package ID that will own the Relation Map.
        name: Optional display name.
        context_element_id: Optional root/context model element ID.
        scope_ids: Optional scope root element IDs.
        element_type_ids: Optional element/metaclass/stereotype IDs used as
            relation-map type filters.
        dependency_criteria: Optional raw Cameo relation-map criterion IDs.
        depth: Optional traversal depth. Use Cameo's native value semantics.
        layout: Optional native relation-map layout token.
        legend_enabled: Whether to show the legend.
        show_full_types: Whether to show fully qualified type names.
        show_stereotypes: Whether to show stereotypes.
        show_parameters: Whether to show parameters.
        show_element_numbers: Whether to show element numbers.
        single_node_per_element: Whether repeated appearances collapse to one
            node per element.
        short_node_names: Whether to shorten displayed node names.
        types_include_subtypes: Whether type filters include subtypes.
        types_include_custom_types: Whether type filters include custom types.
        make_element_as_context: Whether the context element is also shown as
            the map context node.
    """
    result = await client.create_relation_map(
        parent_id=parent_id,
        name=name,
        context_element_id=context_element_id,
        scope_ids=scope_ids,
        element_type_ids=element_type_ids,
        dependency_criteria=dependency_criteria,
        depth=depth,
        layout=layout,
        legend_enabled=legend_enabled,
        show_full_types=show_full_types,
        show_stereotypes=show_stereotypes,
        show_parameters=show_parameters,
        show_element_numbers=show_element_numbers,
        single_node_per_element=single_node_per_element,
        short_node_names=short_node_names,
        types_include_subtypes=types_include_subtypes,
        types_include_custom_types=types_include_custom_types,
        make_element_as_context=make_element_as_context,
    )
    return _mcp_result(result)


@mcp.tool()
async def cameo_configure_relation_map(
    relation_map_id: str,
    context_element_id: Optional[str] = None,
    scope_ids: Optional[list[str]] = None,
    element_type_ids: Optional[list[str]] = None,
    dependency_criteria: Optional[list[str]] = None,
    depth: Optional[int] = None,
    layout: Optional[str] = None,
    legend_enabled: Optional[bool] = None,
    show_full_types: Optional[bool] = None,
    show_stereotypes: Optional[bool] = None,
    show_parameters: Optional[bool] = None,
    show_element_numbers: Optional[bool] = None,
    single_node_per_element: Optional[bool] = None,
    short_node_names: Optional[bool] = None,
    types_include_subtypes: Optional[bool] = None,
    types_include_custom_types: Optional[bool] = None,
    make_element_as_context: Optional[bool] = None,
) -> dict[str, Any]:
    """Update native graph settings for an existing Relation Map."""
    result = await client.configure_relation_map(
        relation_map_id=relation_map_id,
        context_element_id=context_element_id,
        scope_ids=scope_ids,
        element_type_ids=element_type_ids,
        dependency_criteria=dependency_criteria,
        depth=depth,
        layout=layout,
        legend_enabled=legend_enabled,
        show_full_types=show_full_types,
        show_stereotypes=show_stereotypes,
        show_parameters=show_parameters,
        show_element_numbers=show_element_numbers,
        single_node_per_element=single_node_per_element,
        short_node_names=short_node_names,
        types_include_subtypes=types_include_subtypes,
        types_include_custom_types=types_include_custom_types,
        make_element_as_context=make_element_as_context,
    )
    return _mcp_result(result)


@mcp.tool()
async def cameo_refresh_relation_map(relation_map_id: str, timeout: float = 120.0) -> dict[str, Any]:
    """Refresh a native Relation Map after model or settings changes.

    Args:
        relation_map_id: ID of the Relation Map diagram element.
        timeout: HTTP and bridge-side timeout in seconds.
    """
    result = await client.refresh_relation_map(relation_map_id, timeout=timeout)
    return _mcp_result(result)


@mcp.tool()
async def cameo_dump_relation_map_raw_settings(
    relation_map_id: str,
    include_raw: bool = False,
    summary_only: bool = False,
) -> dict[str, Any]:
    """Dump native Relation Map settings for UI-diff investigation.

    Use before and after a human changes a Relation Map in CATIA Magic. The
    result includes sanitized settings plus reflected GraphSettings getters.
    Set include_raw only when class names/string values are needed.
    """
    result = await client.get_relation_map_raw_settings(
        relation_map_id=relation_map_id,
        include_raw=include_raw,
        summary_only=summary_only,
    )
    return _mcp_result(result)


@mcp.tool()
async def cameo_list_relation_map_presentations(
    relation_map_id: str,
    include_properties: bool = False,
    include_raw: bool = False,
    summary_only: bool = True,
    limit: int = 250,
    offset: int = 0,
) -> dict[str, Any]:
    """List loaded Relation Map presentation nodes, paths, and legend elements.

    Use this to distinguish graph traversal success from rendered relation-map
    expansion/export failure. Large property dumps are paged and default to
    summaries.
    """
    result = await client.get_relation_map_presentations(
        relation_map_id=relation_map_id,
        include_properties=include_properties,
        include_raw=include_raw,
        summary_only=summary_only,
        limit=limit,
        offset=offset,
    )
    return _mcp_result(result)


@mcp.tool()
async def cameo_list_relation_map_criteria_templates() -> dict[str, Any]:
    """List built-in Relation Map criteria templates.

    Templates marked verifiedWithUiDiff=false are placeholders until a snapshot
    diff from CATIA Magic's UI confirms the exact native expression.
    """
    result = await client.list_relation_map_criteria_templates()
    return _mcp_result(result)


@mcp.tool()
async def cameo_set_relation_map_criteria(
    relation_map_id: str,
    mode: str = "replace",
    criteria: Optional[list[dict[str, Any] | str]] = None,
    refresh: bool = False,
) -> dict[str, Any]:
    """Apply Relation Map criteria using templates or raw UI-derived expressions."""
    result = await client.set_relation_map_criteria(
        relation_map_id=relation_map_id,
        mode=mode,
        criteria=criteria,
        refresh=refresh,
    )
    return _mcp_result(result)


@mcp.tool()
async def cameo_expand_relation_map(
    relation_map_id: str,
    mode: str = "all",
    element_ids: Optional[list[str]] = None,
    depth: Optional[int] = None,
    refresh: bool = False,
    layout: Optional[str] = None,
    timeout: float = 120.0,
) -> dict[str, Any]:
    """Try to expand native Relation Map nodes and report before/after counts."""
    result = await client.expand_relation_map(
        relation_map_id=relation_map_id,
        mode=mode,
        element_ids=element_ids,
        depth=depth,
        refresh=refresh,
        layout=layout,
        timeout=timeout,
    )
    return _mcp_result(result)


@mcp.tool()
async def cameo_collapse_relation_map(
    relation_map_id: str,
    mode: str = "all",
    element_ids: Optional[list[str]] = None,
    refresh: bool = False,
    timeout: float = 120.0,
) -> dict[str, Any]:
    """Try to collapse native Relation Map nodes and report before/after counts."""
    result = await client.collapse_relation_map(
        relation_map_id=relation_map_id,
        mode=mode,
        element_ids=element_ids,
        refresh=refresh,
        timeout=timeout,
    )
    return _mcp_result(result)


@mcp.tool()
async def cameo_render_relation_map(
    relation_map_id: str,
    refresh: bool = False,
    expand: str = "none",
    depth: Optional[int] = None,
    layout: Optional[str] = None,
    scale_percentage: int = 200,
    include_image: bool = True,
    include_presentation_summary: bool = True,
) -> dict[str, Any]:
    """Render/export a Relation Map image; native refresh is opt-in because it can block CATIA."""
    result = await client.render_relation_map(
        relation_map_id=relation_map_id,
        refresh=refresh,
        expand=expand,
        depth=depth,
        layout=layout,
        scale_percentage=scale_percentage,
        include_image=include_image,
        include_presentation_summary=include_presentation_summary,
    )
    return _mcp_result(result)


@mcp.tool()
async def cameo_verify_relation_map(
    relation_map_id: str,
    expected_min_nodes: int = 0,
    expected_min_edges: int = 0,
    expected_rendered_nodes: int = 0,
    relationship_types: Optional[list[str]] = None,
    max_depth: int = 3,
) -> dict[str, Any]:
    """Verify graph traversal, native settings validity, and rendered count separately."""
    result = await client.verify_relation_map(
        relation_map_id=relation_map_id,
        expected_min_nodes=expected_min_nodes,
        expected_min_edges=expected_min_edges,
        expected_rendered_nodes=expected_rendered_nodes,
        relationship_types=relationship_types,
        max_depth=max_depth,
    )
    return _mcp_result(result)


@mcp.tool()
async def cameo_compare_relation_maps(
    left_relation_map_id: str,
    right_relation_map_id: str,
    include_presentations: bool = True,
    include_raw: bool = False,
) -> dict[str, Any]:
    """Compare two Relation Maps, usually a UI-created map and a bridge-created map."""
    result = await client.compare_relation_maps(
        left_relation_map_id=left_relation_map_id,
        right_relation_map_id=right_relation_map_id,
        include_presentations=include_presentations,
        include_raw=include_raw,
    )
    return _mcp_result(result)


@mcp.tool()
async def cameo_create_snapshot(
    target_type: str,
    target_id: Optional[str] = None,
    name: Optional[str] = None,
    include_raw: bool = False,
    include_presentations: Optional[bool] = None,
    include_properties: Optional[bool] = None,
) -> dict[str, Any]:
    """Capture an in-memory inspection snapshot for before/after UI diffs.

    target_type may be project, element, diagram, relationMap, or ui. For
    diagram/relationMap snapshots, presentation summaries are included by
    default so UI expansion changes can be diffed.
    """
    result = await client.create_snapshot(
        target_type=target_type,
        target_id=target_id,
        name=name,
        include_raw=include_raw,
        include_presentations=include_presentations,
        include_properties=include_properties,
    )
    return _mcp_result(result)


@mcp.tool()
async def cameo_list_snapshots() -> dict[str, Any]:
    """List in-memory bridge snapshots available for diffing."""
    result = await client.list_snapshots()
    return _mcp_result(result)


@mcp.tool()
async def cameo_get_snapshot(snapshot_id: str) -> dict[str, Any]:
    """Get one in-memory bridge snapshot payload."""
    result = await client.get_snapshot(snapshot_id)
    return _mcp_result(result)


@mcp.tool()
async def cameo_delete_snapshot(snapshot_id: str) -> dict[str, Any]:
    """Delete an in-memory snapshot without changing the CATIA model."""
    result = await client.delete_snapshot(snapshot_id)
    return _mcp_result(result)


@mcp.tool()
async def cameo_diff_snapshots(
    before_snapshot_id: str,
    after_snapshot_id: str,
    ignore_paths: Optional[list[str]] = None,
    include_details: bool = True,
    max_changes: int = 500,
) -> dict[str, Any]:
    """Diff two snapshots to reveal what CATIA Magic UI actions changed."""
    result = await client.diff_snapshots(
        before_snapshot_id=before_snapshot_id,
        after_snapshot_id=after_snapshot_id,
        ignore_paths=ignore_paths,
        include_details=include_details,
        max_changes=max_changes,
    )
    return _mcp_result(result)


@mcp.tool()
async def cameo_get_validation_capabilities() -> dict[str, Any]:
    """Probe whether CATIA native validation APIs are available through the bridge."""
    result = await client.get_validation_capabilities()
    return _mcp_result(result)


@mcp.tool()
async def cameo_list_validation_suites() -> dict[str, Any]:
    """List candidate native validation suites and constraints in the open project."""
    result = await client.list_validation_suites()
    return _mcp_result(result)


@mcp.tool()
async def cameo_run_native_validation(
    suite_id: Optional[str] = None,
    constraint_ids: Optional[list[str]] = None,
    scope_element_ids: Optional[list[str]] = None,
    whole_project: Optional[bool] = None,
    recursive: bool = True,
    exclude_read_only: bool = True,
    minimum_severity: Optional[str] = None,
    open_native_window: bool = False,
    name: Optional[str] = None,
) -> dict[str, Any]:
    """Run CATIA native validation for a suite or explicit constraint IDs.

    Provide either suite_id or constraint_ids. Use scope_element_ids with
    whole_project=false for bounded validation runs.
    """
    result = await client.run_native_validation(
        suite_id=suite_id,
        constraint_ids=constraint_ids,
        scope_element_ids=scope_element_ids,
        whole_project=whole_project,
        recursive=recursive,
        exclude_read_only=exclude_read_only,
        minimum_severity=minimum_severity,
        open_native_window=open_native_window,
        name=name,
    )
    return _mcp_result(result)


@mcp.tool()
async def cameo_get_validation_result(run_id: str) -> dict[str, Any]:
    """Fetch a cached CATIA native validation run result by run ID."""
    result = await client.get_validation_result(run_id)
    return _mcp_result(result)


@mcp.tool()
async def cameo_list_probe_templates() -> dict[str, Any]:
    """List safe built-in CATIA API discovery probes."""
    result = await client.list_probe_templates()
    return _mcp_result(result)


@mcp.tool()
async def cameo_execute_probe(
    template: Optional[str] = None,
    mode: str = "read",
    script: Optional[str] = None,
    language: str = "javaReflection",
    timeout_ms: int = 5000,
    requires_project: bool = True,
    description: Optional[str] = None,
    operation: Optional[str] = None,
    class_name: Optional[str] = None,
    method_name: Optional[str] = None,
    relation_map_id: Optional[str] = None,
) -> dict[str, Any]:
    """Execute a controlled discovery probe.

    Built-in templates are supported. Arbitrary scripts are intentionally
    refused by the Java bridge unless a safer execution engine is added later.
    """
    result = await client.execute_probe(
        template=template,
        mode=mode,
        script=script,
        language=language,
        timeout_ms=timeout_ms,
        requires_project=requires_project,
        description=description,
        operation=operation,
        class_name=class_name,
        method_name=method_name,
        relation_map_id=relation_map_id,
    )
    return _mcp_result(result)


@mcp.tool()
async def cameo_run_validation(
    suite_id: Optional[str] = None,
    constraint_ids: Optional[list[str]] = None,
    scope_mode: str = "project",
    scope_element_ids: Optional[list[str]] = None,
    min_severity: Optional[str] = None,
    timeout_ms: int = 30000,
) -> dict[str, Any]:
    """Run or preview bounded native Cameo validation."""
    return _mcp_result(await client.run_validation(
        suite_id=suite_id,
        constraint_ids=constraint_ids,
        scope_mode=scope_mode,
        scope_element_ids=scope_element_ids,
        min_severity=min_severity,
        timeout_ms=timeout_ms,
    ))


@mcp.tool()
async def cameo_get_report_capabilities() -> dict[str, Any]:
    """Probe Report Wizard API availability and plugin evidence."""
    return _mcp_result(await client.get_report_capabilities())


@mcp.tool()
async def cameo_list_report_templates() -> dict[str, Any]:
    """List Report Wizard templates when native readback is promoted."""
    return _mcp_result(await client.list_report_templates())


@mcp.tool()
async def cameo_generate_report_preview(
    template_id: Optional[str] = None,
    template_name: Optional[str] = None,
    report_name: Optional[str] = None,
    output_path: Optional[str] = None,
    output_format: Optional[str] = None,
    scope_element_ids: Optional[list[str]] = None,
    recursive: Optional[bool] = None,
    parameters: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Preview a guarded Report Wizard generation request."""
    return _mcp_result(await client.generate_report_preview(
        template_id=template_id,
        template_name=template_name,
        report_name=report_name,
        output_path=output_path,
        output_format=output_format,
        scope_element_ids=scope_element_ids,
        recursive=recursive,
        parameters=parameters,
    ))


@mcp.tool()
async def cameo_generate_report(
    template_id: Optional[str] = None,
    template_name: Optional[str] = None,
    report_name: Optional[str] = None,
    output_path: Optional[str] = None,
    output_format: Optional[str] = None,
    scope_element_ids: Optional[list[str]] = None,
    recursive: Optional[bool] = None,
    display_in_viewer: Optional[bool] = None,
    parameters: Optional[dict[str, Any]] = None,
    allow_write: bool = False,
) -> dict[str, Any]:
    """Generate a Report Wizard artifact from a real native template."""
    return _mcp_result(await client.generate_report(
        template_id=template_id,
        template_name=template_name,
        report_name=report_name,
        output_path=output_path,
        output_format=output_format,
        scope_element_ids=scope_element_ids,
        recursive=recursive,
        display_in_viewer=display_in_viewer,
        parameters=parameters,
        allow_write=allow_write,
    ))


@mcp.tool()
async def cameo_get_report_job(job_id: str) -> dict[str, Any]:
    """Fetch a Report Wizard generation job status."""
    return _mcp_result(await client.get_report_job(job_id))


@mcp.tool()
async def cameo_get_requirements_capabilities() -> dict[str, Any]:
    """Probe Requirements/ReqIF API availability and plugin evidence."""
    return _mcp_result(await client.get_requirements_capabilities())


@mcp.tool()
async def cameo_get_import_export_capabilities() -> dict[str, Any]:
    """Probe bridge-owned CSV/JSON and native ReqIF import/export support."""
    return _mcp_result(await client.get_import_export_capabilities())


@mcp.tool()
async def cameo_export_requirements(
    scope_ids: Optional[list[str]] = None,
    root_id: Optional[str] = None,
    package_id: Optional[str] = None,
    format: str = "json",
    output_path: Optional[str] = None,
    limit: int = 1000,
) -> dict[str, Any]:
    """Export requirement-like elements through the import/export route."""
    return _mcp_result(await client.export_requirements(
        scope_ids=scope_ids,
        root_id=root_id,
        package_id=package_id,
        format=format,
        output_path=output_path,
        limit=limit,
    ))


@mcp.tool()
async def cameo_preview_requirements_import(
    source_path: Optional[str] = None,
    source_rows: Optional[list[dict[str, Any]]] = None,
    requirements: Optional[list[dict[str, Any]]] = None,
    csv_text: Optional[str] = None,
    target_package_id: Optional[str] = None,
) -> dict[str, Any]:
    """Preview requirements import through the import/export route."""
    return _mcp_result(await client.preview_requirements_import(
        source_path=source_path,
        source_rows=source_rows,
        requirements=requirements,
        csv_text=csv_text,
        target_package_id=target_package_id,
    ))


@mcp.tool()
async def cameo_apply_requirements_import(
    patch_plan: Optional[dict[str, Any]] = None,
    target_package_id: Optional[str] = None,
    requirements: Optional[list[dict[str, Any]]] = None,
    rows: Optional[list[dict[str, Any]]] = None,
    csv_text: Optional[str] = None,
    format: str = "json",
    dry_run: bool = True,
    allow_write: bool = False,
) -> dict[str, Any]:
    """Apply or dry-run a reviewed requirements import request."""
    return _mcp_result(await client.apply_requirements_import(
        patch_plan=patch_plan,
        target_package_id=target_package_id,
        requirements=requirements,
        rows=rows,
        csv_text=csv_text,
        format=format,
        dry_run=dry_run,
        allow_write=allow_write,
    ))


@mcp.tool()
async def cameo_export_requirements_preview(
    scope_ids: Optional[list[str]] = None,
    format: str = "csv",
    output_path: Optional[str] = None,
) -> dict[str, Any]:
    """Preview requirement export without mutating the model."""
    return _mcp_result(await client.export_requirements_preview(
        scope_ids=scope_ids,
        format=format,
        output_path=output_path,
    ))


@mcp.tool()
async def cameo_import_requirements_preview(
    source_path: Optional[str] = None,
    source_rows: Optional[list[dict[str, Any]]] = None,
    target_package_id: Optional[str] = None,
) -> dict[str, Any]:
    """Preview requirement import/diff without writes."""
    return _mcp_result(await client.import_requirements_preview(
        source_path=source_path,
        source_rows=source_rows,
        target_package_id=target_package_id,
    ))


@mcp.tool()
async def cameo_get_simulation_capabilities() -> dict[str, Any]:
    """Probe Simulation Toolkit availability."""
    return _mcp_result(await client.get_simulation_capabilities())


@mcp.tool()
async def cameo_list_simulation_configurations() -> dict[str, Any]:
    """List simulation configurations when native readback is promoted."""
    return _mcp_result(await client.list_simulation_configurations())


@mcp.tool()
async def cameo_run_simulation_preview(
    configuration_id: Optional[str] = None,
    timeout_ms: int = 30000,
) -> dict[str, Any]:
    """Preview a bounded simulation run request."""
    return _mcp_result(await client.run_simulation_preview(
        configuration_id=configuration_id,
        timeout_ms=timeout_ms,
    ))


@mcp.tool()
async def cameo_run_simulation(
    configuration_id: Optional[str] = None,
    target_id: Optional[str] = None,
    timeout_ms: int = 30000,
    allow_execute: bool = False,
    async_run: bool = False,
) -> dict[str, Any]:
    """Call the guarded simulation run endpoint."""
    return _mcp_result(await client.run_simulation(
        configuration_id=configuration_id,
        target_id=target_id,
        timeout_ms=timeout_ms,
        allow_execute=allow_execute,
        async_run=async_run,
    ))


@mcp.tool()
async def cameo_get_simulation_result(run_id: str) -> dict[str, Any]:
    """Fetch simulation result status."""
    return _mcp_result(await client.get_simulation_result(run_id))


@mcp.tool()
async def cameo_terminate_simulation(run_id: str) -> dict[str, Any]:
    """Terminate an active simulation job when execution support is enabled."""
    return _mcp_result(await client.terminate_simulation(run_id))


@mcp.tool()
async def cameo_get_teamwork_capabilities() -> dict[str, Any]:
    """Probe Teamwork/Magic Collaboration Studio API availability."""
    return _mcp_result(await client.get_teamwork_capabilities())


@mcp.tool()
async def cameo_get_teamwork_project() -> dict[str, Any]:
    """Read Teamwork project metadata when native readback is promoted."""
    return _mcp_result(await client.get_teamwork_project())


@mcp.tool()
async def cameo_preview_teamwork_commit(message: Optional[str] = None) -> dict[str, Any]:
    """Preview a Teamwork commit without changing the server project."""
    return _mcp_result(await client.preview_teamwork_commit(message=message))


@mcp.tool()
async def cameo_preview_teamwork_update(message: Optional[str] = None) -> dict[str, Any]:
    """Preview a Teamwork update without changing the server project."""
    return _mcp_result(await client.preview_teamwork_update(message=message))


@mcp.tool()
async def cameo_list_teamwork_descriptors() -> dict[str, Any]:
    """List Teamwork descriptors when the native client is authenticated."""
    return _mcp_result(await client.list_teamwork_descriptors())


@mcp.tool()
async def cameo_list_teamwork_branches() -> dict[str, Any]:
    """List Teamwork branches when available."""
    return _mcp_result(await client.list_teamwork_branches())


@mcp.tool()
async def cameo_get_teamwork_history() -> dict[str, Any]:
    """Read Teamwork history diagnostics when available."""
    return _mcp_result(await client.get_teamwork_history())


@mcp.tool()
async def cameo_get_teamwork_locks() -> dict[str, Any]:
    """Read Teamwork lock diagnostics when available."""
    return _mcp_result(await client.get_teamwork_locks())


@mcp.tool()
async def cameo_get_datahub_capabilities() -> dict[str, Any]:
    """Probe DataHub/DOORS integration availability."""
    return _mcp_result(await client.get_datahub_capabilities())


@mcp.tool()
async def cameo_list_datahub_sources() -> dict[str, Any]:
    """List DataHub sources when native readback is promoted."""
    return _mcp_result(await client.list_datahub_sources())


@mcp.tool()
async def cameo_preview_datahub_sync(
    source_id: Optional[str] = None,
    scope_id: Optional[str] = None,
) -> dict[str, Any]:
    """Preview DataHub sync without writing to CATIA or external systems."""
    return _mcp_result(await client.preview_datahub_sync(source_id=source_id, scope_id=scope_id))


@mcp.tool()
async def cameo_get_criteria_capabilities() -> dict[str, Any]:
    """Probe generic criteria expression support."""
    return _mcp_result(await client.get_criteria_capabilities())


@mcp.tool()
async def cameo_list_criteria_templates(target: Optional[str] = None) -> dict[str, Any]:
    """List criteria templates for relation maps, matrices, tables, or legends."""
    return _mcp_result(await client.list_criteria_templates(target=target))


@mcp.tool()
async def cameo_build_criteria_expression(
    relationship_kind: Optional[str] = None,
    direction: str = "both",
    target: Optional[str] = None,
) -> dict[str, Any]:
    """Build a bridge-owned criteria expression preview."""
    return _mcp_result(await client.build_criteria_expression(
        relationship_kind=relationship_kind,
        direction=direction,
        target=target,
    ))


@mcp.tool()
async def cameo_parse_criteria_expression(expression: dict[str, Any] | str) -> dict[str, Any]:
    """Parse a criteria expression into a diagnostic payload."""
    return _mcp_result(await client.parse_criteria_expression(expression))


@mcp.tool()
async def cameo_apply_criteria_template(
    target_id: str,
    template_id: Optional[str] = None,
    expression: Optional[dict[str, Any]] = None,
    refresh: bool = False,
) -> dict[str, Any]:
    """Apply a criteria template after UI-diff verification."""
    return _mcp_result(await client.apply_criteria_template(
        target_id=target_id,
        template_id=template_id,
        expression=expression,
        refresh=refresh,
    ))


@mcp.tool()
async def cameo_capture_criteria_template_from_diff(
    before_snapshot_id: str,
    after_snapshot_id: str,
    target_kind: Optional[str] = None,
) -> dict[str, Any]:
    """Capture a native criteria template from before/after snapshot evidence."""
    return _mcp_result(await client.capture_criteria_template_from_diff(
        before_snapshot_id=before_snapshot_id,
        after_snapshot_id=after_snapshot_id,
        target_kind=target_kind,
    ))


@mcp.tool()
async def cameo_get_profile_capabilities() -> dict[str, Any]:
    """Probe profile/DSL authoring support."""
    return _mcp_result(await client.get_profile_capabilities())


@mcp.tool()
async def cameo_export_profile_summary() -> dict[str, Any]:
    """Export a summary of profile and stereotype elements in the open project."""
    return _mcp_result(await client.export_profile_summary())


@mcp.tool()
async def cameo_preview_profile_operation(
    operation: str,
    payload: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Preview a profile operation such as create-profile, create-stereotype, create-tag, apply-profile, or set-tags."""
    return _mcp_result(await client.preview_profile_operation(operation=operation, payload=payload))


@mcp.tool()
async def cameo_get_variant_capabilities() -> dict[str, Any]:
    """Probe native or bridge-owned variant support."""
    return _mcp_result(await client.get_variant_capabilities())


@mcp.tool()
async def cameo_analyze_variants_preview(
    configuration_ids: Optional[list[str]] = None,
    scope_ids: Optional[list[str]] = None,
) -> dict[str, Any]:
    """Preview variant/product-line analysis without writes."""
    return _mcp_result(await client.analyze_variants_preview(
        configuration_ids=configuration_ids,
        scope_ids=scope_ids,
    ))


@mcp.tool()
async def cameo_install_variant_pattern_preview(payload: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    """Preview installing bridge-owned variant stereotypes."""
    return _mcp_result(await client.install_variant_pattern_preview(payload=payload))


@mcp.tool()
async def cameo_export_variant_configuration(payload: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    """Preview exporting a bridge-owned variant configuration evidence payload."""
    return _mcp_result(await client.export_variant_configuration(payload=payload))


@mcp.tool()
async def cameo_get_extension_capabilities() -> dict[str, Any]:
    """Probe safety/cyber extension availability."""
    return _mcp_result(await client.get_extension_capabilities())


@mcp.tool()
async def cameo_scan_extensions(
    targets: Optional[list[str]] = None,
    scope_id: Optional[str] = None,
) -> dict[str, Any]:
    """Preview a read-only safety/cyber extension model scan."""
    return _mcp_result(await client.scan_extensions(targets=targets, scope_id=scope_id))


@mcp.tool()
async def cameo_list_extension_profiles() -> dict[str, Any]:
    """List extension-related profiles and stereotypes."""
    return _mcp_result(await client.list_extension_profiles())


@mcp.tool()
async def cameo_install_extension_pattern_preview(payload: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    """Preview installing bridge-owned safety/cyber extension patterns."""
    return _mcp_result(await client.install_extension_pattern_preview(payload=payload))


@mcp.tool()
async def cameo_get_typed_diagram_capabilities() -> dict[str, Any]:
    """Probe typed diagram inspection and write-preview support."""
    return _mcp_result(await client.get_typed_diagram_capabilities())


@mcp.tool()
async def cameo_list_typed_diagrams() -> dict[str, Any]:
    """List diagrams with type metadata for typed handlers."""
    return _mcp_result(await client.list_typed_diagrams())


@mcp.tool()
async def cameo_inspect_typed_diagram(diagram_id: str) -> dict[str, Any]:
    """Inspect a diagram through the typed diagram route."""
    return _mcp_result(await client.inspect_typed_diagram(diagram_id))


@mcp.tool()
async def cameo_preview_typed_diagram_operation(operation: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Preview a typed diagram operation such as sequence-message, state-transition, parametric-binding, or legend-apply."""
    return _mcp_result(await client.preview_typed_diagram_operation(operation=operation, payload=payload))


@mcp.tool()
async def cameo_refuse_compliance_claim(
    claim_type: str,
    evidence_ids: Optional[list[str]] = None,
) -> dict[str, Any]:
    """Return the bridge refusal contract for unsupported compliance claims."""
    return _mcp_result(await client.refuse_compliance_claim(
        claim_type=claim_type,
        evidence_ids=evidence_ids,
    ))


@mcp.tool()
async def cameo_get_traceability_graph(
    root_element_ids: Optional[list[str]] = None,
    context_element_id: Optional[str] = None,
    relation_map_id: Optional[str] = None,
    relationship_types: Optional[list[str]] = None,
    direction: str = "both",
    max_depth: int = 3,
    max_nodes: int = 250,
) -> dict[str, Any]:
    """Build a read-only relationship graph for traceability analysis.

    This is independent of Cameo's native Relation Map criteria UI. Use it when
    a map must reveal actual linked elements across Refine, DeriveReqt, Satisfy,
    Allocate, Dependency, activity-flow, connector, or information-flow links.

    Args:
        root_element_ids: One or more model element IDs to start from.
        context_element_id: Single root element ID; convenient alternative to
            root_element_ids.
        relation_map_id: Optional Relation Map ID. When supplied without roots,
            the map's persisted context element is used.
        relationship_types: Optional names/stereotypes to include, such as
            ["Refine", "DeriveReqt", "Satisfy", "Allocate", "Dependency"].
        direction: "incoming", "outgoing", or "both". Defaults to "both".
        max_depth: Breadth-first traversal depth. Defaults to 3.
        max_nodes: Safety cap on returned nodes. Defaults to 250.
    """
    result = await client.get_traceability_graph(
        root_element_ids=root_element_ids,
        context_element_id=context_element_id,
        relation_map_id=relation_map_id,
        relationship_types=relationship_types,
        direction=direction,
        max_depth=max_depth,
        max_nodes=max_nodes,
    )
    return _mcp_result(result)


@mcp.tool()
async def cameo_dump_diagram_properties(
    diagram_id: str,
    include_raw: bool = False,
    include_presentation_properties: bool = False,
    summary_only: bool = True,
    limit: int = 100,
    offset: int = 0,
) -> dict[str, Any]:
    """Dump diagram settings and paged presentation property summaries.

    Use this for before/after UI snapshots of diagrams, matrices, generic
    tables, and Relation Maps. Defaults avoid returning every symbol property
    unless include_presentation_properties is true.
    """
    result = await client.get_diagram_properties(
        diagram_id=diagram_id,
        include_raw=include_raw,
        include_presentation_properties=include_presentation_properties,
        summary_only=summary_only,
        limit=limit,
        offset=offset,
    )
    return _mcp_result(result)


@mcp.tool()
async def cameo_dump_presentation_properties(
    diagram_id: str,
    presentation_id: str,
    include_raw: bool = False,
    summary_only: bool = False,
) -> dict[str, Any]:
    """Dump full properties for one selected diagram presentation element."""
    result = await client.get_presentation_properties(
        diagram_id=diagram_id,
        presentation_id=presentation_id,
        include_raw=include_raw,
        summary_only=summary_only,
    )
    return _mcp_result(result)

# -- Diagrams -----------------------------------------------------------------


@mcp.tool()
async def cameo_list_diagram_types() -> dict[str, Any]:
    """List the validated diagram request tokens accepted by the MCP bridge.

    Returns the canonical request token to use, the native Cameo diagram type
    it resolves to, and the common aliases that are normalized to that token.
    """
    return {
        "count": len(client.VALIDATED_DIAGRAM_TYPES),
        "diagramTypes": client.VALIDATED_DIAGRAM_TYPES,
    }


@mcp.tool()
async def cameo_list_diagrams() -> dict[str, Any]:
    """List all diagrams in the current project.

    Returns:
        JSON array of diagrams with their IDs, names, types, and
        parent element IDs.
    """
    result = await client.list_diagrams()
    return _mcp_result(result)


@mcp.tool()
async def cameo_create_diagram(
    type: str,
    name: str,
    parent_id: str,
    relation_map_context_id: Optional[str] = None,
    relation_map_scope_ids: Optional[list[str]] = None,
    relation_map_element_types: Optional[list[str]] = None,
    relation_map_dependency_criteria: Optional[list[str]] = None,
    relation_map_depth: Optional[int] = None,
) -> dict[str, Any]:
    """Create a new SysML or UML diagram.

    Args:
        type: Diagram type. Valid values include:
              - SysML: "BDD", "IBD", "Requirement Diagram",
                "Parametric Diagram"
              - UML: "Class", "Package", "UseCase", "Activity",
                "Sequence", "StateMachine", "Component", "Deployment",
                "CompositeStructure", "Object", "Communication",
                "InteractionOverview", "Timing", "Profile"
              - Analysis/navigation: "RelationMap", "Content Diagram"
              Common aliases such as "InternalBlockDiagram",
              "SysML IBD", "ClassDiagram", or "StateMachineDiagram"
              are normalized to this validated token set automatically.
        name: Display name for the diagram.
        parent_id: ID of the parent element that owns this diagram
                   (typically a Package or Block).
        relation_map_context_id: Optional context/root element ID for
            RelationMap diagrams.
        relation_map_scope_ids: Optional scope root element IDs for RelationMap
            diagrams.
        relation_map_element_types: Optional metaclass or stereotype names to
            include in RelationMap diagrams, such as ["Block", "Requirement"].
        relation_map_dependency_criteria: Optional native structured-expression
            XML criteria strings for RelationMap relationship filters.
        relation_map_depth: Optional RelationMap traversal depth. Use -1 for
            indefinite depth.

    Returns:
        JSON with the created diagram ID and details.
    """
    result = await client.create_diagram(
        type=type,
        name=name,
        parent_id=parent_id,
        relation_map_context_id=relation_map_context_id,
        relation_map_scope_ids=relation_map_scope_ids,
        relation_map_element_types=relation_map_element_types,
        relation_map_dependency_criteria=relation_map_dependency_criteria,
        relation_map_depth=relation_map_depth,
    )
    return _mcp_result(result)


@mcp.tool()
async def cameo_add_to_diagram(
    diagram_id: DiagramIdArg,
    element_id: ElementIdArg,
    x: int = 100,
    y: int = 100,
    width: int = -1,
    height: int = -1,
    container_presentation_id: ContainerPresentationArg = None,
) -> dict[str, Any]:
    """Add a model element to a diagram canvas.

    Place an existing model element onto a diagram at the specified
    coordinates. Use width/height below zero to keep Cameo's auto-size.

    Args:
        diagram_id: The unique ID of the target diagram.
        element_id: The unique ID of the element to add.
        x: Horizontal position in pixels from the left. Defaults to 100.
        y: Vertical position in pixels from the top. Defaults to 100.
        width: Shape width in pixels. Use a negative value to omit the resize
               request and keep Cameo's auto-size. Defaults to -1.
        height: Shape height in pixels. Use a negative value to omit the
                resize request and keep Cameo's auto-size. Defaults to -1.
                If you set one explicitly, you must set both explicitly.
        container_presentation_id: Optional presentationId of a container
            shape (e.g., a swimlane or system boundary) to place this element
            inside. If omitted, the element is placed directly on the diagram
            canvas. Get this ID from cameo_list_diagram_shapes.

    Returns:
        JSON confirmation with the created shape info.
    """
    result = await client.add_to_diagram(
        diagram_id=diagram_id,
        element_id=element_id,
        x=x,
        y=y,
        width=width,
        height=height,
        container_presentation_id=container_presentation_id,
    )
    return _mcp_result(result)

@mcp.tool()
async def cameo_get_diagram_image(
    diagram_id: DiagramIdArg,
    include_image: bool = True,
    format: str = "png",
    max_width: Optional[int] = None,
    max_height: Optional[int] = None,
    quality: int = 85,
    scale_percentage: Optional[int] = None,
) -> dict[str, Any]:
    """Export a diagram as a base64-encoded PNG image.

    By default this returns the full base64 payload. To keep large diagrams
    below MCP token limits, set `include_image=False` for metadata only and/or
    use `max_width` / `max_height` plus `format="jpeg"` to shrink the payload.
    Use `scale_percentage` to request a higher-resolution native Cameo export
    before any optional client-side resizing/transcoding.

    Args:
        diagram_id: The unique ID of the diagram to export.
        include_image: When false, omit the base64 payload and return only
                       image metadata.
        format: Output encoding for the MCP response: `png` (default), `jpeg`,
                `jpg`, or `webp`.
        max_width: Optional maximum width in pixels for returned image data.
        max_height: Optional maximum height in pixels for returned image data.
        quality: Lossy encoder quality for `jpeg`/`webp` outputs.
        scale_percentage: Optional native Cameo export scale from 25 to 1000.

    Returns:
        JSON with base64-encoded image data and metadata (width, height).
    """
    if scale_percentage is None:
        result = await client.get_diagram_image(diagram_id)
    else:
        result = await client.get_diagram_image(
            diagram_id,
            scale_percentage=scale_percentage,
        )
    return _mcp_result(
        _transform_diagram_image(
            result,
            include_image=include_image,
            format=format,
            max_width=max_width,
            max_height=max_height,
            quality=quality,
        )
    )


@mcp.tool()
async def cameo_verify_diagram_visual(
    diagram_id: DiagramIdArg,
    expected_element_ids: Optional[list[str]] = None,
    expected_relationship_ids: Optional[list[str]] = None,
    min_shape_count: int = 0,
    min_relationship_shape_count: int = 0,
    min_width: int = 1,
    min_height: int = 1,
    min_image_bytes: int = 1,
    min_content_coverage_ratio: float = 0.0,
    max_overlap_ratio: float = 1.0,
) -> dict[str, Any]:
    """Run reusable visual verification checks against one diagram.

    This combines cameo_get_diagram_image and cameo_list_diagram_shapes into a
    stable visual verification result that checks image payload validity,
    rendered size, expected element/path presence, and coarse overlap risk.

    Args:
        diagram_id: The unique ID of the diagram to validate.
        expected_element_ids: Optional model element IDs that must appear on
            the diagram canvas.
        expected_relationship_ids: Optional relationship element IDs that must
            appear specifically as relationship paths.
        min_shape_count: Minimum number of presentation elements expected.
        min_relationship_shape_count: Minimum number of relationship paths
            expected on the diagram.
        min_width: Minimum rendered image width in pixels.
        min_height: Minimum rendered image height in pixels.
        min_image_bytes: Minimum PNG payload size in bytes.
        min_content_coverage_ratio: Minimum non-background pixel coverage ratio
            over the rendered image area.
        max_overlap_ratio: Maximum allowed sibling-shape overlap ratio.

    Returns:
        JSON with pass/fail status, check details, and both image/shape metrics.
    """
    diagram_image = await client.get_diagram_image(diagram_id)
    diagram_shapes = await client.list_diagram_shapes(diagram_id)
    result = verification.verify_diagram_visual(
        diagram_image,
        diagram_shapes,
        expected_element_ids=expected_element_ids,
        expected_relationship_ids=expected_relationship_ids,
        min_shape_count=min_shape_count,
        min_relationship_shape_count=min_relationship_shape_count,
        min_width=min_width,
        min_height=min_height,
        min_image_bytes=min_image_bytes,
        min_content_coverage_ratio=min_content_coverage_ratio,
        max_overlap_ratio=max_overlap_ratio,
    )
    result["diagramImage"] = diagram_image
    result["diagramShapes"] = diagram_shapes
    return _mcp_result(result)


@mcp.tool()
async def cameo_auto_layout(diagram_id: DiagramIdArg) -> dict[str, Any]:
    """Apply automatic layout to a diagram.

    Rearranges all shapes on the diagram using CATIA Magic's built-in
    layout algorithms for a clean, readable layout.

    Args:
        diagram_id: The unique ID of the diagram to lay out.

    Returns:
        JSON confirmation of the layout operation.
    """
    result = await client.auto_layout(diagram_id)
    return _mcp_result(result)


# -- Diagram Shape Management -------------------------------------------------


@mcp.tool()
async def cameo_list_diagram_shapes(
    diagram_id: DiagramIdArg,
    limit: int = 200,
    offset: int = 0,
    shape_type: Optional[str] = None,
    element_type: Optional[str] = None,
    parent_presentation_id: ParentPresentationArg = None,
    include_bounds: bool = True,
    include_child_count: bool = True,
    summary_only: bool = False,
) -> dict[str, Any]:
    """List all shapes and relationship paths currently on a diagram.

    Returns every presentation element (shape, path, label) on the diagram
    canvas, including each element's presentationId, bounding box (x, y,
    width, height), and the underlying model element reference.

    You MUST call this before using cameo_move_shapes, cameo_delete_shapes,
    cameo_add_diagram_paths, or cameo_set_shape_properties, because those
    tools require the presentationId values that this tool returns.

    The presentationId is NOT the same as the model element ID — it
    identifies the visual representation of an element on a specific
    diagram. The same model element can appear on multiple diagrams with
    different presentationIds.

    Args:
        diagram_id: The unique ID of the diagram to inspect.
        limit: Maximum number of filtered shapes to return. Defaults to 200.
        offset: Zero-based offset into the filtered shape list.
        shape_type: Optional presentation-class filter such as
                    `ControlFlowView` or `SwimlaneHeaderView`.
        element_type: Optional model-element filter such as `OpaqueAction`,
                      `ActivityPartition`, or `ControlFlow`.
        parent_presentation_id: Optional parent presentation filter for nested
                                diagram content.
        include_bounds: Include per-shape bounds in the returned page.
        include_child_count: Include per-shape child counts in the returned
                             page.
        summary_only: When true, omit `shapes` and return counts/groupings
                      instead of the shape page.

    Returns:
        JSON with arrays of shapes and paths, each containing
        presentationId, bounds (x, y, width, height), and element
        reference info (elementId, name, type).
    """
    result = await client.list_diagram_shapes(diagram_id)
    return _mcp_result(
        _filter_diagram_shapes(
            result,
            limit=limit,
            offset=offset,
            shape_type=shape_type,
            element_type=element_type,
            parent_presentation_id=parent_presentation_id,
            include_bounds=include_bounds,
            include_child_count=include_child_count,
            summary_only=summary_only,
        )
    )


@mcp.tool()
async def cameo_get_shape_properties(
    diagram_id: str,
    presentation_id: str,
) -> dict[str, Any]:
    """Read the current property state for a specific diagram shape."""
    result = await client.get_shape_properties(
        diagram_id=diagram_id,
        presentation_id=presentation_id,
    )
    return _mcp_result(result)


@mcp.tool()
async def cameo_move_shapes(
    diagram_id: str,
    shapes: list[dict],
) -> dict[str, Any]:
    """Move and/or resize shapes on a diagram canvas.

    Repositions one or more shapes to new coordinates and/or dimensions.
    The coordinate system uses pixels measured from the top-left corner
    of the diagram canvas: x increases rightward, y increases downward.

    Call cameo_list_diagram_shapes first to get the current presentationId
    and bounds for each shape you want to move.

    Args:
        diagram_id: The unique ID of the diagram containing the shapes.
        shapes: List of shape position updates. Each dict must contain:
                - presentationId (str): The presentation element ID from
                  cameo_list_diagram_shapes.
                - x (int): New horizontal position in pixels from the left
                  edge of the diagram canvas.
                - y (int): New vertical position in pixels from the top
                  edge of the diagram canvas.
                - width (int): New width in pixels. Use the current value
                  from list_diagram_shapes to keep the size unchanged.
                - height (int): New height in pixels. Use the current value
                  from list_diagram_shapes to keep the size unchanged.

                Example:
                [{"presentationId": "abc-123", "x": 200, "y": 50,
                  "width": 150, "height": 80}]

    Returns:
        JSON confirmation with the updated shape positions.
    """
    result = await client.move_shapes(
        diagram_id=diagram_id,
        shapes=shapes,
    )
    return _mcp_result(result)


@mcp.tool()
async def cameo_delete_shapes(
    diagram_id: str,
    presentation_ids: list[str],
) -> dict[str, Any]:
    """Delete presentation elements (shapes/paths) from a diagram canvas.

    This removes the visual representation of elements from the diagram
    ONLY — it does NOT delete the underlying model elements. The model
    elements remain in the containment tree and can be re-added to this
    or other diagrams later.

    Use cameo_delete_element instead if you want to remove the element
    from the model entirely.

    Call cameo_list_diagram_shapes first to get the presentationId values
    for the shapes you want to remove.

    Args:
        diagram_id: The unique ID of the diagram to modify.
        presentation_ids: List of presentationId strings identifying the
                          shapes or paths to remove from the diagram.
                          These IDs come from cameo_list_diagram_shapes.

    Returns:
        JSON confirmation with count of deleted presentation elements.
    """
    result = await client.delete_shapes(
        diagram_id=diagram_id,
        presentation_ids=presentation_ids,
    )
    return _mcp_result(result)


@mcp.tool()
async def cameo_add_diagram_paths(
    diagram_id: str,
    paths: list[dict],
) -> dict[str, Any]:
    """Add relationship lines (paths) to a diagram.

    Draws visual paths on the diagram for existing model relationships.
    The relationship must already exist in the model (created via
    cameo_create_relationship), and both the source and target elements
    must already be present on the diagram as shapes.

    You MUST call cameo_list_diagram_shapes first to get the
    presentationId of the source and target shapes (NOT their model
    element IDs). The path connects two shapes that are already on the
    diagram canvas.

    Args:
        diagram_id: The unique ID of the diagram to add paths to.
        paths: List of path definitions. Each dict must contain:
               - relationshipId (str): The model element ID of the
                 relationship (from cameo_create_relationship or
                 cameo_get_relationships).
               - sourceShapeId (str): The presentationId of the source
                 shape on this diagram (from cameo_list_diagram_shapes).
               - targetShapeId (str): The presentationId of the target
                 shape on this diagram (from cameo_list_diagram_shapes).

               Example:
               [{"relationshipId": "rel-456",
                 "sourceShapeId": "shape-abc",
                 "targetShapeId": "shape-def"}]

    Returns:
        JSON confirmation with the created path presentation elements.
    """
    result = await client.add_diagram_paths(
        diagram_id=diagram_id,
        paths=paths,
    )
    return _mcp_result(result)


@mcp.tool()
async def cameo_set_shape_properties(
    diagram_id: str,
    presentation_id: str,
    properties: dict,
) -> dict[str, Any]:
    """Set display properties on a specific diagram shape.

    Controls how a shape is visually rendered on the diagram — what
    compartments are shown, what labels are visible, etc. These are
    presentation-level properties (NOT model properties).

    Call cameo_list_diagram_shapes first to get the presentationId of
    the shape you want to modify.

    Common properties and their expected types:
    - "Show Constraints" (bool): Show/hide constraint compartment.
    - "Show Tagged Values" (bool): Show/hide tagged values compartment.
    - "Show Properties" (bool): Show/hide properties compartment.
    - "Show Operations" (bool): Show/hide operations compartment.
    - "Show Ports" (bool): Show/hide port shapes on the border.
    - "Show Full Path" (bool): Show fully-qualified name.
    - "Show Name" (bool): Show/hide the element name label.
    - "Show Type" (bool): Show/hide element type.
    - "Show Stereotype" (bool): Show/hide stereotype label.
    - "Suppress Attributes" (bool): Hide the attributes compartment.
    - "Suppress Operations" (bool): Hide the operations compartment.
    - "Autosize" (bool): Auto-fit shape to content.
    - "Fill Color" (str): Background color (e.g. "#RRGGBB").
    - "Font Color" (str): Text color (e.g. "#RRGGBB").
    - "Line Color" (str): Border/line color (e.g. "#RRGGBB").

    Args:
        diagram_id: The unique ID of the diagram containing the shape.
        presentation_id: The presentationId of the shape to modify
                         (from cameo_list_diagram_shapes).
        properties: Dictionary of property-name to value mappings.
                    Example: {"Show Constraints": true,
                              "Show Tagged Values": true,
                              "Fill Color": "#E0F0FF"}.

    Returns:
        JSON confirmation with count of properties set.
    """
    result = await client.set_shape_properties(
        diagram_id=diagram_id,
        presentation_id=presentation_id,
        properties=properties,
    )
    return _mcp_result(result)


@mcp.tool()
async def cameo_set_shape_compartments(
    diagram_id: str,
    presentation_id: str,
    compartments: dict,
) -> dict[str, Any]:
    """Apply normalized compartment visibility controls to one diagram shape.

    Common keys include `showAttributes`, `showOperations`, `showPorts`,
    `showParts`, `showContent`, `showReferences`, `showFullPorts`,
    `showFlowProperties`, `showProxyPorts`, and `showValues`.
    """
    result = await client.set_shape_compartments(
        diagram_id=diagram_id,
        presentation_id=presentation_id,
        compartments=compartments,
    )
    return _mcp_result(result)


@mcp.tool()
async def cameo_set_transition_label_presentation(
    diagram_id: DiagramIdArg,
    presentation_ids: Optional[list[str]] = None,
    show_name: bool = True,
    show_triggers: bool = True,
    show_guard: bool = False,
    show_effect: bool = False,
    reset_labels: bool = True,
) -> dict[str, Any]:
    """Apply a high-level transition-label display preset on one diagram.

    This is safer than guessing raw Cameo property names when you want
    transition names/triggers to render cleanly on state-machine diagrams.
    """
    result = await client.set_transition_label_presentation(
        diagram_id,
        presentation_ids=presentation_ids,
        show_name=show_name,
        show_triggers=show_triggers,
        show_guard=show_guard,
        show_effect=show_effect,
        reset_labels=reset_labels,
    )
    return _mcp_result(result)


@mcp.tool()
async def cameo_set_item_flow_label_presentation(
    diagram_id: DiagramIdArg,
    presentation_ids: Optional[list[str]] = None,
    show_name: bool = False,
    show_conveyed: bool = True,
    show_item_property: bool = True,
    show_direction: bool = True,
    show_stereotype: bool = False,
    reset_labels: bool = True,
) -> dict[str, Any]:
    """Apply a high-level item-flow/information-flow label preset on one diagram."""
    result = await client.set_item_flow_label_presentation(
        diagram_id,
        presentation_ids=presentation_ids,
        show_name=show_name,
        show_conveyed=show_conveyed,
        show_item_property=show_item_property,
        show_direction=show_direction,
        show_stereotype=show_stereotype,
        reset_labels=reset_labels,
    )
    return _mcp_result(result)


@mcp.tool()
async def cameo_set_allocation_compartment_presentation(
    diagram_id: DiagramIdArg,
    presentation_ids: Optional[list[str]] = None,
    show_allocated_elements: bool = True,
    show_element_properties: bool = True,
    show_ports: bool = True,
    show_full_ports: bool = True,
    apply_allocation_naming: bool = True,
) -> dict[str, Any]:
    """Apply a high-level allocation/full-port display preset on one diagram."""
    result = await client.set_allocation_compartment_presentation(
        diagram_id,
        presentation_ids=presentation_ids,
        show_allocated_elements=show_allocated_elements,
        show_element_properties=show_element_properties,
        show_ports=show_ports,
        show_full_ports=show_full_ports,
        apply_allocation_naming=apply_allocation_naming,
    )
    return _mcp_result(result)


@mcp.tool()
async def cameo_repair_hidden_labels(
    diagram_id: DiagramIdArg,
    presentation_ids: Optional[list[str]] = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Auto-show hidden labels using diagram-type-aware native repair defaults."""
    result = await client.repair_hidden_labels(
        diagram_id,
        presentation_ids=presentation_ids,
        dry_run=dry_run,
    )
    return _mcp_result(result)


@mcp.tool()
async def cameo_repair_label_positions(
    diagram_id: DiagramIdArg,
    presentation_ids: Optional[list[str]] = None,
    dry_run: bool = False,
    only_overlapping: bool = True,
    overlap_padding: int = 40,
) -> dict[str, Any]:
    """Reset likely-overlapping path labels to readable default positions."""
    result = await client.repair_label_positions(
        diagram_id,
        presentation_ids=presentation_ids,
        dry_run=dry_run,
        only_overlapping=only_overlapping,
        overlap_padding=overlap_padding,
    )
    return _mcp_result(result)


@mcp.tool()
async def cameo_repair_conveyed_item_labels(
    diagram_id: DiagramIdArg,
    presentation_ids: Optional[list[str]] = None,
    dry_run: bool = False,
    reset_labels: bool = True,
) -> dict[str, Any]:
    """Force conveyed-item labels and optional label resets on eligible paths."""
    result = await client.repair_conveyed_item_labels(
        diagram_id,
        presentation_ids=presentation_ids,
        dry_run=dry_run,
        reset_labels=reset_labels,
    )
    return _mcp_result(result)


@mcp.tool()
async def cameo_normalize_compartment_presets(
    diagram_id: DiagramIdArg,
    presentation_ids: Optional[list[str]] = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Normalize compartment presets based on the diagram type."""
    result = await client.normalize_compartment_presets(
        diagram_id,
        presentation_ids=presentation_ids,
        dry_run=dry_run,
    )
    return _mcp_result(result)


@mcp.tool()
async def cameo_prune_diagram_presentations(
    diagram_id: DiagramIdArg,
    keep_element_ids: Optional[list[str]] = None,
    drop_element_types: Optional[list[str]] = None,
    drop_shape_types: Optional[list[str]] = None,
    exclude_element_ids: Optional[list[str]] = None,
    exclude_presentation_ids: Optional[list[str]] = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Delete unwanted diagram presentations using keep/drop rules.

    Use this when Cameo auto-displays extra relationship symbols or other
    unwanted presentations after adding elements to a diagram. The most useful
    pattern is usually `keep_element_ids=[...]` to retain only the model
    elements you explicitly want visible before you add controlled paths or
    labels.
    """
    result = await client.prune_diagram_presentations(
        diagram_id,
        keep_element_ids=keep_element_ids,
        drop_element_types=drop_element_types,
        drop_shape_types=drop_shape_types,
        exclude_element_ids=exclude_element_ids,
        exclude_presentation_ids=exclude_presentation_ids,
        dry_run=dry_run,
    )
    return _mcp_result(result)


@mcp.tool()
async def cameo_prune_path_decorations(
    diagram_id: DiagramIdArg,
    presentation_ids: Optional[list[str]] = None,
    drop_child_shape_types: Optional[list[str]] = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Prune child path decorations such as association end-role labels.

    Use this when the path itself should stay visible but its auto-displayed
    role/end decorations are cluttering the diagram.
    """
    result = await client.prune_path_decorations(
        diagram_id,
        presentation_ids=presentation_ids,
        drop_child_shape_types=drop_child_shape_types,
        dry_run=dry_run,
    )
    return _mcp_result(result)


@mcp.tool()
async def cameo_reparent_shapes(
    diagram_id: str,
    reparentings: list[dict],
) -> dict[str, Any]:
    """Move existing presentation elements under new container shapes."""
    result = await client.reparent_shapes(
        diagram_id=diagram_id,
        reparentings=reparentings,
    )
    return _mcp_result(result)


@mcp.tool()
async def cameo_route_paths(
    diagram_id: str,
    routes: list[dict],
) -> dict[str, Any]:
    """Update routing and label reset behavior for existing diagram paths."""
    result = await client.route_paths(
        diagram_id=diagram_id,
        routes=routes,
    )
    return _mcp_result(result)


# -- Specification -----------------------------------------------------------


@mcp.tool()
async def cameo_get_specification(element_id: str) -> dict[str, Any]:
    """Get the full specification of a model element — all UML properties, stereotype tagged values, and constraint fields.

    This is the programmatic equivalent of opening the Specification window
    in CATIA Magic. Returns every readable property on the element plus all
    tagged values from applied stereotypes, plus any owned constraint fields
    (e.g. Pre Condition, Post Condition, Goal, Assumption for Use Cases).

    Use this to inspect an element's full state before modifying it.

    Args:
        element_id: The unique ID of the element.

    Returns:
        JSON with "properties" (UML/MOF properties like name, visibility,
        isAbstract), "appliedStereotypes" (with tagged values grouped by
        stereotype), and "constraints" (named constraint fields like
        Pre Condition, Post Condition, Goal, Assumption).
    """
    result = await client.get_specification(element_id)
    return _mcp_result(result)


@mcp.tool()
async def cameo_set_specification(
    element_id: str,
    properties: Optional[dict] = None,
    constraints: Optional[dict] = None,
) -> dict[str, Any]:
    """Set properties and/or constraint fields on a model element's specification.

    This is the programmatic equivalent of editing fields in the
    Specification window in CATIA Magic. Supports standard UML properties,
    stereotype tagged values, and named constraint fields.

    The handler auto-resolves each property name: it first checks
    tagged values across all applied stereotypes, then falls back
    to standard UML properties (via JMI reflection).

    Common properties you can set:
    - name, visibility (public/private/protected/package)
    - isAbstract, isFinalSpecialization (boolean)
    - documentation (element documentation text)
    - type (for TypedElements such as Property, Port, and Pins) using an
      element ID string or {"id": "<element-id>"} to point at an existing type
    - Any tagged value from an applied stereotype

    Common constraint fields (for Use Cases):
    - Pre Condition, Post Condition, Goal, Assumption

    Args:
        element_id: The unique ID of the element to modify.
        properties: Dictionary of property-name to value mappings.
                    Example: {"name": "NewName", "visibility": "public"}.
                    Type example: {"type": "01234567-89ab-cdef-0123-456789abcdef"}.
        constraints: Dictionary of constraint-name to text mappings.
                     These create or update named Constraint elements
                     owned by the target element.
                     Example: {"Pre Condition": "Customer has valid ATM card",
                               "Post Condition": "Cash dispensed",
                               "Goal": "Allow withdrawal",
                               "Assumption": "ATM is operational"}.

    Returns:
        JSON confirmation with count of properties/constraints set.
    """
    result = await client.set_specification(
        element_id, properties=properties, constraints=constraints
    )
    return _mcp_result(result)


@mcp.tool()
async def cameo_set_usecase_subject(
    element_id: str,
    subject_ids: list[str],
    append: bool = False,
) -> dict[str, Any]:
    """Set or append subject classifiers on a UseCase."""
    result = await client.set_usecase_subject(
        element_id=element_id,
        subject_ids=subject_ids,
        append=append,
    )
    return _mcp_result(result)


# -- State Machine Semantics --------------------------------------------------


@mcp.tool()
async def cameo_get_transition_triggers(
    transition_id: str,
) -> dict[str, Any]:
    """Read the structured trigger/event state for a transition.

    Use this when you need to inspect whether a transition is currently driven
    by change-event logic, signal-event logic, or has no trigger at all.

    Args:
        transition_id: Element ID of a UML/SysML transition.

    Returns:
        JSON with trigger count plus each trigger's event type, signal link,
        and change-expression text when present.
    """
    result = await get_transition_triggers(transition_id)
    return _mcp_result(result)


@mcp.tool()
async def cameo_set_transition_trigger(
    transition_id: str,
    trigger_kind: str,
    expression: Optional[str] = None,
    signal_id: Optional[str] = None,
    name: Optional[str] = None,
    replace: bool = True,
) -> dict[str, Any]:
    """Create or replace one transition trigger with explicit semantics.

    Args:
        transition_id: Element ID of a UML/SysML transition.
        trigger_kind: Either `"change"` or `"signal"`.
        expression: Required when `trigger_kind="change"`. Stored as the
            transition's Change Event expression text.
        signal_id: Required when `trigger_kind="signal"`. References an
            existing `Signal` element.
        name: Optional trigger display name.
        replace: When true (default), existing triggers are removed before the
            new trigger is created.

    Returns:
        JSON readback of the transition's current triggers after mutation.
    """
    result = await set_transition_trigger(
        transition_id,
        trigger_kind=trigger_kind,
        expression=expression,
        signal_id=signal_id,
        name=name,
        replace=replace,
    )
    return _mcp_result(result)


@mcp.tool()
async def cameo_get_state_behaviors(
    state_id: str,
) -> dict[str, Any]:
    """Read the structured entry/do/exit behavior payloads for a state.

    Args:
        state_id: Element ID of a UML/SysML state.

    Returns:
        JSON with `entry`, `doActivity`, and `exit` payloads, including body
        and language when those behaviors exist.
    """
    result = await get_state_behaviors(state_id)
    return _mcp_result(result)


@mcp.tool()
async def cameo_set_state_behaviors(
    state_id: str,
    entry: Optional[str] = None,
    do_activity: Optional[str] = None,
    exit_behavior: Optional[str] = None,
    language: str = "Opaque",
    clear_unspecified: bool = False,
) -> dict[str, Any]:
    """Set structured entry/do/exit opaque behaviors for a state.

    Notes:
    - Pass an empty string for a specific field to clear that behavior.
    - Omitted fields stay unchanged unless `clear_unspecified=True`.

    Args:
        state_id: Element ID of a UML/SysML state.
        entry: Optional entry-behavior body text.
        do_activity: Optional do-activity body text.
        exit_behavior: Optional exit-behavior body text.
        language: OpaqueBehavior language label stored alongside the body.
        clear_unspecified: When true, omitted behavior slots are cleared.

    Returns:
        JSON readback of the state's current entry/do/exit behaviors after
        mutation.
    """
    result = await set_state_behaviors(
        state_id,
        entry=entry,
        do_activity=do_activity,
        exit_behavior=exit_behavior,
        language=language,
        clear_unspecified=clear_unspecified,
    )
    return _mcp_result(result)


# -- Macros -------------------------------------------------------------------


@mcp.tool()
async def cameo_execute_macro(script: str) -> dict[str, Any]:
    """Execute a Groovy script inside CATIA Magic's JVM.

    This is an escape hatch for operations not covered by other tools.
    The script runs in the context of the open project and has full
    access to the Cameo/MagicDraw OpenAPI.

    Common patterns:
    - Access the project: def project = Application.getInstance().getProject()
    - Access element factory: def ef = project.getElementsFactory()
    - Access the model: def model = project.getPrimaryModel()

    Args:
        script: Groovy script source code to execute.

    Returns:
        JSON with script output, return value, and any errors.
    """
    result = await client.execute_macro(script)
    return _mcp_result(result)


# -- Entry Point --------------------------------------------------------------


def main():
    """Run the Cameo MCP Bridge server over stdio."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
