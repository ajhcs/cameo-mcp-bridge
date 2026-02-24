"""MCP server exposing CATIA Magic / Cameo Systems Modeler tools to Claude Code."""

from __future__ import annotations

import json
from typing import Optional

from mcp.server.fastmcp import FastMCP

from cameo_mcp import client

mcp = FastMCP(
    "CameoMCPBridge",
    instructions=(
        "Bridge to CATIA Magic (Cameo Systems Modeler) for SysML/UML model "
        "creation, querying, and manipulation via the CameoMCPBridge plugin."
    ),
)


# -- Status / Project --------------------------------------------------------


@mcp.tool()
async def cameo_status() -> str:
    """Check if CATIA Magic is running and the CameoMCPBridge plugin is responsive.

    Returns:
        JSON with plugin status, CATIA Magic version, and connection info.
    """
    result = await client.status()
    return json.dumps(result, indent=2)


@mcp.tool()
async def cameo_get_project() -> str:
    """Get current project info: name, file path, and primary model ID.

    Returns:
        JSON with project name, file location, and root model element ID.
    """
    result = await client.get_project()
    return json.dumps(result, indent=2)


@mcp.tool()
async def cameo_save_project() -> str:
    """Save the current project to disk.

    Call this after making changes you want to persist.

    Returns:
        JSON confirmation of save operation.
    """
    result = await client.save_project()
    return json.dumps(result, indent=2)

# -- Elements -----------------------------------------------------------------


@mcp.tool()
async def cameo_query_elements(
    type: Optional[str] = None,
    name: Optional[str] = None,
    package_name: Optional[str] = None,
    stereotype: Optional[str] = None,
    recursive: bool = True,
) -> str:
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
    return json.dumps(result, indent=2)


@mcp.tool()
async def cameo_get_element(element_id: str) -> str:
    """Get full details of a model element.

    Returns all properties including name, type, documentation,
    applied stereotypes, tagged values, and owned elements.

    Args:
        element_id: The unique ID of the element (UUID string from Cameo).

    Returns:
        JSON with complete element details.
    """
    result = await client.get_element(element_id)
    return json.dumps(result, indent=2)


@mcp.tool()
async def cameo_get_containment_tree(
    root_id: Optional[str] = None,
    depth: int = 3,
) -> str:
    """Browse the containment tree structure.

    Use this to understand the project hierarchy before creating or
    modifying elements. Start with no root_id to see top-level packages.

    Args:
        root_id: Element ID to use as root. Omit to start from the
                 project model root.
        depth: How many levels deep to traverse. Defaults to 3.

    Returns:
        JSON tree structure with element IDs, names, types, and children.
    """
    result = await client.get_containment_tree(root_id=root_id, depth=depth)
    return json.dumps(result, indent=2)

@mcp.tool()
async def cameo_create_element(
    type: str,
    name: str,
    parent_id: str,
    stereotype: Optional[str] = None,
    documentation: Optional[str] = None,
) -> str:
    """Create a new model element.

    Args:
        type: The UML/SysML metaclass. Valid values include:
              - Structural: Class, Package, Property, Port, Interface,
                DataType, Enumeration, Signal, Component, Node
              - SysML: Block, ConstraintBlock, InterfaceBlock, ValueType,
                FlowSpecification, Requirement
              - Behavioral: Activity, StateMachine, Interaction,
                OpaqueBehavior, UseCase, Actor
              - Actions/Nodes: Action, CallBehaviorAction, OpaqueAction,
                InitialNode, FinalNode, DecisionNode, MergeNode,
                ForkNode, JoinNode, FlowFinalNode
              - Other: Comment, Constraint, InstanceSpecification
        name: Display name for the element.
        parent_id: ID of the parent element (usually a Package or Block).
        stereotype: Optional stereotype to apply on creation (e.g. "block",
                    "requirement", "valueType", "flowPort").
        documentation: Optional description/documentation string.

    Returns:
        JSON with the created element ID and details.
    """
    result = await client.create_element(
        type=type,
        name=name,
        parent_id=parent_id,
        stereotype=stereotype,
        documentation=documentation,
    )
    return json.dumps(result, indent=2)


@mcp.tool()
async def cameo_modify_element(
    element_id: str,
    name: Optional[str] = None,
    documentation: Optional[str] = None,
) -> str:
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
    return json.dumps(result, indent=2)


@mcp.tool()
async def cameo_delete_element(element_id: str) -> str:
    """Delete a model element.

    Warning: This permanently removes the element and all its owned
    sub-elements. Relationships connected to the element are also removed.

    Args:
        element_id: The unique ID of the element to delete.

    Returns:
        JSON confirmation of deletion.
    """
    result = await client.delete_element(element_id)
    return json.dumps(result, indent=2)

# -- Stereotypes / Tagged Values ----------------------------------------------


@mcp.tool()
async def cameo_apply_stereotype(
    element_id: str,
    stereotype: str,
    profile: Optional[str] = None,
) -> str:
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
    return json.dumps(result, indent=2)


@mcp.tool()
async def cameo_set_tagged_values(
    element_id: str,
    stereotype: str,
    values: dict,
) -> str:
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
    return json.dumps(result, indent=2)

# -- Relationships ------------------------------------------------------------


@mcp.tool()
async def cameo_create_relationship(
    type: str,
    source_id: str,
    target_id: str,
    name: Optional[str] = None,
    guard: Optional[str] = None,
) -> str:
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
    return json.dumps(result, indent=2)


@mcp.tool()
async def cameo_get_relationships(
    element_id: str,
    direction: str = "both",
) -> str:
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
    return json.dumps(result, indent=2)

# -- Diagrams -----------------------------------------------------------------


@mcp.tool()
async def cameo_list_diagrams() -> str:
    """List all diagrams in the current project.

    Returns:
        JSON array of diagrams with their IDs, names, types, and
        parent element IDs.
    """
    result = await client.list_diagrams()
    return json.dumps(result, indent=2)


@mcp.tool()
async def cameo_create_diagram(
    type: str,
    name: str,
    parent_id: str,
) -> str:
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
    return json.dumps(result, indent=2)


@mcp.tool()
async def cameo_add_to_diagram(
    diagram_id: str,
    element_id: str,
    x: int = 100,
    y: int = 100,
    width: int = -1,
    height: int = -1,
) -> str:
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
    )
    return json.dumps(result, indent=2)

@mcp.tool()
async def cameo_get_diagram_image(
    diagram_id: str,
    format: str = "png",
) -> str:
    """Export a diagram as a base64-encoded image.

    Args:
        diagram_id: The unique ID of the diagram to export.
        format: Image format, typically "png". Defaults to "png".

    Returns:
        JSON with base64-encoded image data and metadata.
    """
    result = await client.get_diagram_image(diagram_id)
    return json.dumps(result, indent=2)


@mcp.tool()
async def cameo_auto_layout(diagram_id: str) -> str:
    """Apply automatic layout to a diagram.

    Rearranges all shapes on the diagram using CATIA Magic's built-in
    layout algorithms for a clean, readable layout.

    Args:
        diagram_id: The unique ID of the diagram to lay out.

    Returns:
        JSON confirmation of the layout operation.
    """
    result = await client.auto_layout(diagram_id)
    return json.dumps(result, indent=2)


# -- Specification -----------------------------------------------------------


@mcp.tool()
async def cameo_get_specification(element_id: str) -> str:
    """Get the full specification of a model element — all UML properties and stereotype tagged values.

    This is the programmatic equivalent of opening the Specification window
    in CATIA Magic. Returns every readable property on the element plus all
    tagged values from applied stereotypes.

    Use this to inspect an element's full state before modifying it.

    Args:
        element_id: The unique ID of the element.

    Returns:
        JSON with "standardProperties" (UML/MOF properties like name,
        visibility, isAbstract) and "taggedValues" (grouped by stereotype).
    """
    result = await client.get_specification(element_id)
    return json.dumps(result, indent=2)


@mcp.tool()
async def cameo_set_specification(
    element_id: str,
    properties: dict,
) -> str:
    """Set properties on a model element's specification.

    This is the programmatic equivalent of editing fields in the
    Specification window in CATIA Magic. Supports both standard UML
    properties and stereotype tagged values.

    The handler auto-resolves each property name: it first checks
    tagged values across all applied stereotypes, then falls back
    to standard UML properties (via JMI reflection).

    Common properties you can set:
    - name, visibility (public/private/protected/package)
    - isAbstract, isFinalSpecialization (boolean as string)
    - documentation (element documentation text)
    - Any tagged value from an applied stereotype

    Args:
        element_id: The unique ID of the element to modify.
        properties: Dictionary of property-name to value mappings.
                    Example: {"name": "NewName", "visibility": "public",
                              "isAbstract": "true", "Text": "The system shall..."}.

    Returns:
        JSON confirmation with count of properties set.
    """
    result = await client.set_specification(element_id, properties)
    return json.dumps(result, indent=2)


# -- Macros -------------------------------------------------------------------


@mcp.tool()
async def cameo_execute_macro(script: str) -> str:
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
    return json.dumps(result, indent=2)


# -- Entry Point --------------------------------------------------------------


def main():
    """Run the Cameo MCP Bridge server over stdio."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
