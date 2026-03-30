"""MCP server exposing CATIA Magic / Cameo Systems Modeler tools to Claude Code."""

from __future__ import annotations

import json
import os
from typing import Any, Optional

from mcp.server.fastmcp import FastMCP

from cameo_mcp import client

mcp = FastMCP(
    "CameoMCPBridge",
    instructions=(
        "Bridge to CATIA Magic (Cameo Systems Modeler) for SysML/UML model "
        "creation, querying, and manipulation via the CameoMCPBridge plugin."
    ),
)


def _mcp_result(result: dict[str, Any]) -> Any:
    """Preserve legacy JSON-string responses unless explicitly disabled."""
    structured = os.environ.get("CAMEO_MCP_STRUCTURED_RESPONSES", "").lower()
    if structured in {"1", "true", "yes", "on"}:
        return result
    return json.dumps(result, separators=(",", ":"), ensure_ascii=False)


# -- Status / Project --------------------------------------------------------


@mcp.tool()
async def cameo_status() -> dict[str, Any]:
    """Check if CATIA Magic is running and the CameoMCPBridge plugin is responsive.

    Returns:
        JSON with plugin status, CATIA Magic version, and connection info.
    """
    result = await client.status()
    return _mcp_result(result)


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
    package_name: Optional[str] = None,
    stereotype: Optional[str] = None,
    recursive: bool = True,
) -> dict[str, Any]:
    """Search for model elements matching filters.

    Use this to find existing elements before creating new ones or
    establishing relationships.

    Args:
        type: UML/SysML metaclass to filter by. Common values:
              Class, Package, Property, Port, Activity, State,
              Block (SysML), Requirement (SysML), ConstraintBlock (SysML),
              FlowPort, InterfaceBlock, ValueType.
        name: Exact or partial element name to match.
        package_name: Restrict search to a specific package by name.
        stereotype: Filter by applied stereotype name (e.g. "block",
                    "requirement", "interfaceBlock").
        recursive: Whether to search recursively into sub-packages.
                   Defaults to True.

    Returns:
        JSON array of matching elements with their IDs, names, types,
        and stereotypes.
    """
    result = await client.query_elements(
        type=type,
        name=name,
        package=package_name,
        stereotype=stereotype,
        recursive=recursive,
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
    root_id: Optional[str] = None,
    depth: int = 3,
) -> dict[str, Any]:
    """Browse the containment tree structure.

    Use this to understand the project hierarchy before creating or
    modifying elements. Start with no root_id to see top-level packages.

    Args:
        root_id: Element ID to use as root. Omit to start from the
                 project model root.
        depth: How many levels deep to traverse. Defaults to 3.

    For large models, prefer `cameo_list_containment_children`; this recursive
    endpoint can still produce very large payloads.

    Returns:
        JSON tree structure with element IDs, names, types, and children.
    """
    result = await client.get_containment_tree(root_id=root_id, depth=depth)
    return _mcp_result(result)


@mcp.tool()
async def cameo_list_containment_children(
    root_id: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
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

    Returns:
        JSON-compatible object with the selected root, compact children, and
        paging metadata.
    """
    result = await client.list_containment_children(
        root_id=root_id,
        limit=limit,
        offset=offset,
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
    metaclasses: Optional[list[str]] = None,
) -> dict[str, Any]:
    """Create a new model element.

    Args:
        type: The UML/SysML metaclass. Valid values include:
              - Structural: Class, Package, Profile, Property, Port, Interface,
                DataType, Enumeration, Signal, Component, Node
              - Profiles: Stereotype (owned by a Profile; use metaclasses to bind)
              - SysML: Block, ConstraintBlock, InterfaceBlock, ValueType,
                FlowSpecification, Requirement
              - Behavioral: Activity, StateMachine, Interaction,
                OpaqueBehavior, UseCase, Actor
              - Activity nodes: InitialNode, ActivityFinalNode,
                FlowFinalNode, DecisionNode, MergeNode, ForkNode, JoinNode
              - Actions: CallBehaviorAction, OpaqueAction
              - Partitions: ActivityPartition
              - Pins: InputPin, OutputPin
              - Other: Comment, Constraint, InstanceSpecification
        name: Display name for the element.
        parent_id: ID of the parent element (usually a Package or Block).
        stereotype: Optional stereotype to apply on creation (e.g. "block",
                    "requirement", "valueType", "flowPort").
        documentation: Optional description/documentation string.
        behavior_id: For CallBehaviorAction type only -- links the action to
                     the Activity it invokes. The referenced element must be
                     an Activity or other Behavior.
        represents_id: For ActivityPartition (swimlane) type only -- links the
                       partition to the Block or Class it represents (the
                       performer).
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
) -> dict[str, Any]:
    """Create a relationship between two elements.

    Args:
        type: Relationship metaclass. Valid values include:
              - Structural: Association, Composition, Aggregation,
                Generalization, Realization, InterfaceRealization,
                Dependency, Usage, Abstraction
              - SysML: Allocate, Copy, DeriveReqt, Satisfy, Verify,
                Refine, Trace, FlowPort (connector)
              - Behavioral: Transition, ControlFlow, ObjectFlow,
                InformationFlow, Connector
              - Other: PackageImport, ElementImport
        source_id: ID of the source element.
        target_id: ID of the target element.
        name: Optional name for the relationship.
        guard: Optional guard condition (for transitions/flows).

    Returns:
        JSON with the created relationship ID and details.
    """
    result = await client.create_relationship(
        type=type,
        source_id=source_id,
        target_id=target_id,
        name=name,
        guard=guard,
    )
    return _mcp_result(result)


@mcp.tool()
async def cameo_get_relationships(
    element_id: str,
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

# -- Diagrams -----------------------------------------------------------------


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
) -> dict[str, Any]:
    """Create a new SysML or UML diagram.

    Args:
        type: Diagram type. Valid values include:
              - SysML: BlockDefinitionDiagram (BDD),
                InternalBlockDiagram (IBD), RequirementDiagram,
                ParametricDiagram, ActivityDiagram, SequenceDiagram,
                StateMachineDiagram, UseCaseDiagram, PackageDiagram
              - UML: ClassDiagram, ComponentDiagram, DeploymentDiagram,
                ObjectDiagram, ProfileDiagram, CommunicationDiagram,
                TimingDiagram, InteractionOverviewDiagram
        name: Display name for the diagram.
        parent_id: ID of the parent element that owns this diagram
                   (typically a Package or Block).

    Returns:
        JSON with the created diagram ID and details.
    """
    result = await client.create_diagram(
        type=type,
        name=name,
        parent_id=parent_id,
    )
    return _mcp_result(result)


@mcp.tool()
async def cameo_add_to_diagram(
    diagram_id: str,
    element_id: str,
    x: int = 100,
    y: int = 100,
    width: int = -1,
    height: int = -1,
    container_presentation_id: Optional[str] = None,
) -> dict[str, Any]:
    """Add a model element to a diagram canvas.

    Place an existing model element onto a diagram at the specified
    coordinates. Use width/height of -1 to auto-size.

    Args:
        diagram_id: The unique ID of the target diagram.
        element_id: The unique ID of the element to add.
        x: Horizontal position in pixels from the left. Defaults to 100.
        y: Vertical position in pixels from the top. Defaults to 100.
        width: Shape width in pixels. Use -1 for auto-size. Defaults to -1.
        height: Shape height in pixels. Use -1 for auto-size. Defaults to -1.
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
async def cameo_get_diagram_image(diagram_id: str) -> dict[str, Any]:
    """Export a diagram as a base64-encoded PNG image.

    Returns a base64-encoded PNG. For large diagrams that exceed token limits,
    use cameo_execute_macro with ImageExporter.export(dpe, ImageExporter.PNG, file)
    to save directly to disk instead.

    Args:
        diagram_id: The unique ID of the diagram to export.

    Returns:
        JSON with base64-encoded image data and metadata (width, height).
    """
    result = await client.get_diagram_image(diagram_id)
    return _mcp_result(result)


@mcp.tool()
async def cameo_auto_layout(diagram_id: str) -> dict[str, Any]:
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
async def cameo_list_diagram_shapes(diagram_id: str) -> dict[str, Any]:
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

    Returns:
        JSON with arrays of shapes and paths, each containing
        presentationId, bounds (x, y, width, height), and element
        reference info (elementId, name, type).
    """
    result = await client.list_diagram_shapes(diagram_id)
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
    - isAbstract, isFinalSpecialization (boolean as string)
    - documentation (element documentation text)
    - Any tagged value from an applied stereotype

    Common constraint fields (for Use Cases):
    - Pre Condition, Post Condition, Goal, Assumption

    Args:
        element_id: The unique ID of the element to modify.
        properties: Dictionary of property-name to value mappings.
                    Example: {"name": "NewName", "visibility": "public"}.
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
