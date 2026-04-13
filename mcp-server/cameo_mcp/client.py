"""HTTP client for the CameoMCPBridge Java plugin REST API."""

from __future__ import annotations

import json
import os
import re
from typing import Any, Optional

import httpx

BRIDGE_PLUGIN_VERSION = "2.1.0"
BRIDGE_API_VERSION = "v1"
BRIDGE_HANDSHAKE_VERSION = "1"


VALIDATED_DIAGRAM_TYPES: list[dict[str, Any]] = [
    {"canonical": "Class", "nativeType": "Class Diagram", "family": "uml", "aliases": ["class", "ClassDiagram", "Class Diagram"]},
    {"canonical": "Package", "nativeType": "Package Diagram", "family": "uml", "aliases": ["package", "PackageDiagram", "Package Diagram"]},
    {"canonical": "UseCase", "nativeType": "Use Case Diagram", "family": "uml", "aliases": ["usecase", "use case", "UseCaseDiagram", "Use Case Diagram"]},
    {"canonical": "Activity", "nativeType": "Activity Diagram", "family": "uml", "aliases": ["activity", "ActivityDiagram", "Activity Diagram"]},
    {"canonical": "Sequence", "nativeType": "Sequence Diagram", "family": "uml", "aliases": ["sequence", "SequenceDiagram", "Sequence Diagram"]},
    {"canonical": "StateMachine", "nativeType": "State Machine Diagram", "family": "uml", "aliases": ["statemachine", "state machine", "StateMachineDiagram", "State Machine Diagram"]},
    {"canonical": "Component", "nativeType": "Component Diagram", "family": "uml", "aliases": ["component", "ComponentDiagram", "Component Diagram"]},
    {"canonical": "Deployment", "nativeType": "Deployment Diagram", "family": "uml", "aliases": ["deployment", "DeploymentDiagram", "Deployment Diagram"]},
    {"canonical": "CompositeStructure", "nativeType": "Composite Structure Diagram", "family": "uml", "aliases": ["compositestructure", "composite structure", "CompositeStructureDiagram", "Composite Structure Diagram"]},
    {"canonical": "Object", "nativeType": "Object Diagram", "family": "uml", "aliases": ["object", "ObjectDiagram", "Object Diagram"]},
    {"canonical": "Communication", "nativeType": "Communication Diagram", "family": "uml", "aliases": ["communication", "CommunicationDiagram", "Communication Diagram"]},
    {"canonical": "InteractionOverview", "nativeType": "Interaction Overview Diagram", "family": "uml", "aliases": ["interactionoverview", "interaction overview", "InteractionOverviewDiagram", "Interaction Overview Diagram"]},
    {"canonical": "Timing", "nativeType": "Timing Diagram", "family": "uml", "aliases": ["timing", "TimingDiagram", "Timing Diagram"]},
    {"canonical": "Profile", "nativeType": "Profile Diagram", "family": "uml", "aliases": ["profile", "ProfileDiagram", "Profile Diagram"]},
    {"canonical": "BDD", "nativeType": "SysML Block Definition Diagram", "family": "sysml", "aliases": ["bdd", "BlockDefinitionDiagram", "Block Definition Diagram", "SysML BDD", "SysML Block Definition Diagram"]},
    {"canonical": "IBD", "nativeType": "SysML Internal Block Diagram", "family": "sysml", "aliases": ["ibd", "InternalBlockDiagram", "Internal Block Diagram", "SysML IBD", "SysML Internal Block Diagram"]},
    {"canonical": "Requirement Diagram", "nativeType": "SysML Requirement Diagram", "family": "sysml", "aliases": ["requirement", "requirements", "RequirementDiagram", "Requirement Diagram", "SysML Requirement Diagram"]},
    {"canonical": "Parametric Diagram", "nativeType": "SysML Parametric Diagram", "family": "sysml", "aliases": ["parametric", "ParametricDiagram", "Parametric Diagram", "SysML Parametric Diagram"]},
]

VALIDATED_MATRIX_KINDS: list[dict[str, Any]] = [
    {
        "kind": "refine",
        "nativeType": "Refine Requirement Matrix",
        "aliases": ["refine", "refine matrix", "refine requirement matrix"],
        "validatedRowTypeExamples": ["Block", "UseCase", "Property"],
        "validatedColumnTypeExamples": ["Requirement"],
    },
    {
        "kind": "derive",
        "nativeType": "Derive Requirement Matrix",
        "aliases": ["derive", "derive matrix", "derive requirement matrix"],
        "validatedRowTypeExamples": ["Requirement"],
        "validatedColumnTypeExamples": ["Requirement"],
    },
]


def _normalize_lookup_key(value: str) -> str:
    spaced = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", value.strip())
    spaced = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1 \2", spaced)
    normalized = spaced.lower().replace("-", " ").replace("_", " ")
    return " ".join(normalized.split())


_DIAGRAM_TYPE_ALIASES: dict[str, str] = {}
for _spec in VALIDATED_DIAGRAM_TYPES:
    _DIAGRAM_TYPE_ALIASES[_normalize_lookup_key(_spec["canonical"])] = _spec["canonical"]
    _DIAGRAM_TYPE_ALIASES[_normalize_lookup_key(_spec["nativeType"])] = _spec["canonical"]
    for _alias in _spec["aliases"]:
        _DIAGRAM_TYPE_ALIASES[_normalize_lookup_key(_alias)] = _spec["canonical"]


_MATRIX_KIND_ALIASES: dict[str, str] = {}
for _spec in VALIDATED_MATRIX_KINDS:
    _MATRIX_KIND_ALIASES[_normalize_lookup_key(_spec["kind"])] = _spec["kind"]
    _MATRIX_KIND_ALIASES[_normalize_lookup_key(_spec["nativeType"])] = _spec["kind"]
    for _alias in _spec["aliases"]:
        _MATRIX_KIND_ALIASES[_normalize_lookup_key(_alias)] = _spec["kind"]


def normalize_diagram_type(diagram_type: str) -> str:
    """Map user-facing aliases to the validated diagram token set."""
    return _DIAGRAM_TYPE_ALIASES.get(_normalize_lookup_key(diagram_type), diagram_type.strip())


def normalize_matrix_kind(kind: str) -> str:
    """Map user-facing matrix aliases to the validated native kind set."""
    return _MATRIX_KIND_ALIASES.get(_normalize_lookup_key(kind), kind.strip())


def _base_url() -> str:
    port = os.environ.get("CAMEO_BRIDGE_PORT", "18740")
    return f"http://127.0.0.1:{port}/api/v1"


def _json_literal(value: Any) -> str:
    return json.dumps(value)


def _is_activity_partition_element(metadata: dict[str, Any]) -> bool:
    candidate_values = (
        metadata.get("type"),
        metadata.get("humanType"),
    )
    normalized = {
        str(value).strip().lower().replace(" ", "")
        for value in candidate_values
        if value is not None
    }
    return "activitypartition" in normalized


def _format_macro_failure(result: dict[str, Any]) -> str:
    detail = str(result.get("error") or "macro execution failed")
    output = str(result.get("output") or "")
    if output:
        detail += f"; output={output}"
    return detail


def _parse_macro_json_result(
    result: dict[str, Any],
    *,
    context: str,
) -> dict[str, Any]:
    if not result.get("success"):
        raise RuntimeError(f"{context}: {_format_macro_failure(result)}")

    payload = result.get("result")
    if not isinstance(payload, str):
        raise RuntimeError(
            f"{context}: macro returned a non-string result payload: {payload!r}"
        )

    try:
        parsed = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"{context}: macro returned invalid JSON: {payload!r}"
        ) from exc

    if not isinstance(parsed, dict):
        raise RuntimeError(
            f"{context}: macro returned a non-object JSON payload: {parsed!r}"
        )
    return parsed


def _activity_partition_add_script(
    diagram_id: str,
    element_id: str,
    *,
    x: Optional[int],
    y: Optional[int],
    width: Optional[int],
    height: Optional[int],
) -> str:
    return f"""
import com.google.gson.GsonBuilder
import com.nomagic.magicdraw.openapi.uml.PresentationElementsManager
import com.nomagic.magicdraw.openapi.uml.SessionManager
import java.awt.Rectangle

def gson = new GsonBuilder().disableHtmlEscaping().create()
def diagramId = {_json_literal(diagram_id)}
def partitionId = {_json_literal(element_id)}
def requestedX = {_json_literal(x)}
def requestedY = {_json_literal(y)}
def requestedWidth = {_json_literal(width)}
def requestedHeight = {_json_literal(height)}

def diagram = project.getElementByID(diagramId)
if (diagram == null) {{
    throw new IllegalArgumentException("Diagram not found: " + diagramId)
}}
def dpe = project.getDiagram(diagram)
if (dpe == null) {{
    throw new IllegalArgumentException("Diagram presentation not found: " + diagramId)
}}
dpe.ensureLoaded()

def partition = project.getElementByID(partitionId)
if (partition == null) {{
    throw new IllegalArgumentException("Activity partition not found: " + partitionId)
}}

def findPartitionPresentation
findPartitionPresentation = {{ elements, targetId ->
    def fallback = null
    for (pe in (elements ?: [])) {{
        def peElement = null
        try {{
            peElement = pe?.element
        }} catch (ignored) {{}}
        if (peElement != null && targetId == peElement.ID) {{
            def className = pe.getClass().getSimpleName()
            if (className == "SwimlaneHeaderView") {{
                return pe
            }}
            if (fallback == null
                    && (className.contains("Swimlane") || className.contains("Partition"))) {{
                fallback = pe
            }}
        }}
        def nested = findPartitionPresentation(pe?.presentationElements, targetId)
        if (nested != null) {{
            return nested
        }}
    }}
    return fallback
}}

def findFirstSwimlane
findFirstSwimlane = {{ elements ->
    for (pe in (elements ?: [])) {{
        if (pe.getClass().getSimpleName() == "SwimlaneView") {{
            return pe
        }}
        def nested = findFirstSwimlane(pe?.presentationElements)
        if (nested != null) {{
            return nested
        }}
    }}
    return null
}}

def existingPartitionPresentation = findPartitionPresentation(dpe.getPresentationElements(), partitionId)
if (existingPartitionPresentation != null) {{
    def bounds = existingPartitionPresentation.getBounds()
    return gson.toJson([
        diagramId: diagramId,
        elementId: partitionId,
        x: bounds?.x,
        y: bounds?.y,
        width: bounds?.width,
        height: bounds?.height,
        added: true,
        presentationId: existingPartitionPresentation.ID,
        receipt: [
            operation: "addShape",
            diagramId: diagramId,
            elementId: partitionId,
            presentationId: existingPartitionPresentation.ID,
            status: "existing",
            activityPartitionFallback: true,
        ],
    ])
}}

def siblingPartitions = []
for (owned in (partition.owner?.ownedElement ?: [])) {{
    if (owned?.getClass()?.getSimpleName() == "ActivityPartition") {{
        siblingPartitions << owned
    }}
}}
if (siblingPartitions.isEmpty()) {{
    siblingPartitions << partition
}}

def existingSwimlane = findFirstSwimlane(dpe.getPresentationElements())
def existingBounds = existingSwimlane?.getBounds()
int laneCount = Math.max(siblingPartitions.size(), 1)
int laneWidth = requestedWidth != null ? requestedWidth.intValue()
    : (existingBounds != null ? Math.max((int) (existingBounds.width / laneCount), 1) : 220)
int totalWidth = requestedWidth != null ? laneWidth * laneCount
    : (existingBounds != null ? existingBounds.width : laneWidth * laneCount)
int totalHeight = requestedHeight != null ? requestedHeight.intValue()
    : (existingBounds != null ? existingBounds.height : 280)
int targetX = requestedX != null ? requestedX.intValue() : (existingBounds != null ? existingBounds.x : 100)
int targetY = requestedY != null ? requestedY.intValue() : (existingBounds != null ? existingBounds.y : 100)

if (existingSwimlane != null) {{
    throw new IllegalStateException(
        "Activity partition diagram fallback found an existing swimlane but could not "
        + "locate a presentation for partition " + partitionId + ". Refusing to rebuild "
        + "the entire swimlane container automatically."
    )
}}

def pem = PresentationElementsManager.getInstance()
def sm = SessionManager.getInstance()
sm.createSession(project, "MCP Add Activity Partition Swimlane")
try {{
    def swimlane = pem.createSwimlane([], siblingPartitions, dpe)
    if (swimlane == null) {{
        throw new IllegalStateException("Failed to create swimlane for activity partition: " + partitionId)
    }}
    pem.reshapeShapeElement(swimlane, new Rectangle(targetX, targetY, totalWidth, totalHeight))
    sm.closeSession(project)
}} catch (Exception e) {{
    sm.cancelSession(project)
    throw e
}}

def createdPartitionPresentation = findPartitionPresentation(dpe.getPresentationElements(), partitionId)
if (createdPartitionPresentation == null) {{
    throw new IllegalStateException(
        "Failed to locate the created swimlane presentation for activity partition: " + partitionId
    )
}}
def createdBounds = createdPartitionPresentation.getBounds()
return gson.toJson([
    diagramId: diagramId,
    elementId: partitionId,
    x: createdBounds?.x,
    y: createdBounds?.y,
    width: createdBounds?.width,
    height: createdBounds?.height,
    added: true,
    presentationId: createdPartitionPresentation.ID,
    receipt: [
        operation: "addShape",
        diagramId: diagramId,
        elementId: partitionId,
        presentationId: createdPartitionPresentation.ID,
        status: "created",
        activityPartitionFallback: true,
    ],
])
""".strip()


async def _add_activity_partition_to_diagram_via_macro(
    diagram_id: str,
    element_id: str,
    *,
    x: Optional[int],
    y: Optional[int],
    width: Optional[int],
    height: Optional[int],
) -> dict[str, Any]:
    script = _activity_partition_add_script(
        diagram_id,
        element_id,
        x=x,
        y=y,
        width=width,
        height=height,
    )
    result = await execute_macro(script)
    return _parse_macro_json_result(
        result,
        context="Activity partition diagram fallback",
    )


# Module-level singleton client for connection pooling and keepalive
_shared_client: Optional[httpx.AsyncClient] = None
_shared_client_base_url: Optional[str] = None
_capabilities_cache: Optional[dict[str, Any]] = None
_capabilities_cache_base_url: Optional[str] = None


def _get_client() -> httpx.AsyncClient:
    global _shared_client, _shared_client_base_url
    base_url = _base_url()
    if (
        _shared_client is None
        or _shared_client.is_closed
        or _shared_client_base_url != base_url
    ):
        _shared_client = httpx.AsyncClient(base_url=base_url, timeout=30.0)
        _shared_client_base_url = base_url
    return _shared_client


def _annotate_bridge_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    annotated = dict(metadata)
    compatibility = dict(annotated.get("compatibility") or {})
    errors: list[str] = []

    plugin_version = annotated.get("pluginVersion") or annotated.get("version")
    if plugin_version != BRIDGE_PLUGIN_VERSION:
        errors.append(
            "plugin version mismatch "
            f"(expected {BRIDGE_PLUGIN_VERSION}, got {plugin_version or 'unknown'})"
        )

    handshake_version = annotated.get("handshakeVersion")
    if handshake_version != BRIDGE_HANDSHAKE_VERSION:
        errors.append(
            "handshake version mismatch "
            f"(expected {BRIDGE_HANDSHAKE_VERSION}, got {handshake_version or 'unknown'})"
        )

    api_version = annotated.get("apiVersion")
    if api_version != BRIDGE_API_VERSION:
        errors.append(
            f"API version mismatch (expected {BRIDGE_API_VERSION}, got {api_version or 'unknown'})"
        )

    compatibility["clientExpectedPluginVersion"] = BRIDGE_PLUGIN_VERSION
    compatibility["clientExpectedHandshakeVersion"] = BRIDGE_HANDSHAKE_VERSION
    compatibility["clientExpectedApiVersion"] = BRIDGE_API_VERSION
    compatibility["clientCompatible"] = not errors
    compatibility["clientCompatibilityErrors"] = errors
    annotated["compatibility"] = compatibility
    return annotated


def _require_compatible_bridge(metadata: dict[str, Any]) -> dict[str, Any]:
    annotated = _annotate_bridge_metadata(metadata)
    compatibility = annotated["compatibility"]
    if not compatibility.get("clientCompatible", False):
        errors = compatibility.get("clientCompatibilityErrors") or ["unknown incompatibility"]
        raise RuntimeError(
            "Incompatible CameoMCPBridge plugin: "
            + "; ".join(str(error) for error in errors)
            + ". Rebuild/redeploy the plugin and restart Cameo."
        )
    return annotated


async def _request_raw(
    method: str,
    path: str,
    *,
    params: Optional[dict[str, Any]] = None,
    json_body: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Send an HTTP request to the Java plugin and return the JSON response.

    Raises a clear error when the plugin is unreachable.
    """
    try:
        http_client = _get_client()
        response = await http_client.request(
            method,
            path,
            params=params,
            json=json_body,
        )
        response.raise_for_status()
        if response.status_code == 204 or not response.content:
            return {"status": "ok"}
        return response.json()
    except httpx.ConnectError:
        raise ConnectionError(
            "Cannot connect to CameoMCPBridge plugin at "
            f"{_base_url()}. "
            "Ensure CATIA Magic (Cameo Systems Modeler) is running "
            "and the CameoMCPBridge plugin is loaded."
        ) from None
    except httpx.HTTPStatusError as exc:
        try:
            detail = exc.response.json()
        except Exception:
            detail = exc.response.text
        raise RuntimeError(
            f"CameoMCPBridge returned HTTP {exc.response.status_code}: {detail}"
        ) from None


async def _ensure_compatible_bridge(force_refresh: bool = False) -> dict[str, Any]:
    global _capabilities_cache, _capabilities_cache_base_url
    base_url = _base_url()
    if (
        not force_refresh
        and _capabilities_cache is not None
        and _capabilities_cache_base_url == base_url
    ):
        return _require_compatible_bridge(_capabilities_cache)

    metadata = await _request_raw("GET", "/capabilities")
    annotated = _require_compatible_bridge(metadata)
    _capabilities_cache = annotated
    _capabilities_cache_base_url = base_url
    return annotated


async def _request(
    method: str,
    path: str,
    *,
    params: Optional[dict[str, Any]] = None,
    json_body: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    if path not in {"/status", "/capabilities"}:
        await _ensure_compatible_bridge()
    return await _request_raw(method, path, params=params, json_body=json_body)

# -- Status / Project --------------------------------------------------------


async def status() -> dict[str, Any]:
    """Check plugin health."""
    return _annotate_bridge_metadata(await _request_raw("GET", "/status"))


async def get_capabilities() -> dict[str, Any]:
    """Get plugin capability and compatibility metadata."""
    return _annotate_bridge_metadata(await _request_raw("GET", "/capabilities"))


async def get_project() -> dict[str, Any]:
    """Get current project info."""
    return await _request("GET", "/project")


async def save_project() -> dict[str, Any]:
    """Save the current project to disk."""
    return await _request("POST", "/project/save")


# -- Elements -----------------------------------------------------------------


async def query_elements(
    type: Optional[str] = None,
    name: Optional[str] = None,
    package: Optional[str] = None,
    stereotype: Optional[str] = None,
    recursive: Optional[bool] = None,
    limit: Optional[int] = None,
    offset: Optional[int] = None,
    view: Optional[str] = None,
) -> dict[str, Any]:
    """Search for model elements matching filters."""
    params: dict[str, Any] = {}
    if type is not None:
        params["type"] = type
    if name is not None:
        params["name"] = name
    if package is not None:
        params["package"] = package
    if stereotype is not None:
        params["stereotype"] = stereotype
    if recursive is not None:
        params["recursive"] = str(recursive).lower()
    if limit is not None:
        params["limit"] = str(limit)
    if offset is not None:
        params["offset"] = str(offset)
    if view is not None:
        params["view"] = view
    return await _request("GET", "/elements", params=params)


async def get_element(element_id: str) -> dict[str, Any]:
    """Get full details of a single element."""
    return await _request("GET", f"/elements/{element_id}")


async def create_element(
    type: str,
    name: str,
    parent_id: str,
    stereotype: Optional[str] = None,
    documentation: Optional[str] = None,
    behavior_id: Optional[str] = None,
    represents_id: Optional[str] = None,
    metaclasses: Optional[list[str]] = None,
) -> dict[str, Any]:
    """Create a new model element."""
    body: dict[str, Any] = {
        "type": type,
        "name": name,
        "parentId": parent_id,
    }
    if stereotype is not None:
        body["stereotype"] = stereotype
    if documentation is not None:
        body["documentation"] = documentation
    if behavior_id is not None:
        body["behaviorId"] = behavior_id
    if represents_id is not None:
        body["representsId"] = represents_id
    if metaclasses is not None:
        body["metaclasses"] = metaclasses
    return await _request("POST", "/elements", json_body=body)


async def modify_element(
    element_id: str,
    name: Optional[str] = None,
    documentation: Optional[str] = None,
) -> dict[str, Any]:
    """Modify an existing element's name or documentation."""
    body: dict[str, Any] = {}
    if name is not None:
        body["name"] = name
    if documentation is not None:
        body["documentation"] = documentation
    return await _request("PUT", f"/elements/{element_id}", json_body=body)


async def delete_element(element_id: str) -> dict[str, Any]:
    """Delete a model element."""
    return await _request("DELETE", f"/elements/{element_id}")

# -- Stereotypes / Tagged Values ----------------------------------------------


async def apply_stereotype(
    element_id: str,
    stereotype: str,
    profile: Optional[str] = None,
) -> dict[str, Any]:
    """Apply a stereotype to an element."""
    body: dict[str, Any] = {"stereotype": stereotype}
    if profile is not None:
        body["profile"] = profile
    return await _request("POST", f"/elements/{element_id}/stereotypes", json_body=body)


async def set_tagged_values(
    element_id: str,
    stereotype: str,
    values: dict[str, Any],
) -> dict[str, Any]:
    """Set tagged values on a stereotyped element."""
    body: dict[str, Any] = {
        "stereotype": stereotype,
        "values": values,
    }
    return await _request("PUT", f"/elements/{element_id}/tagged-values", json_body=body)


async def set_stereotype_metaclasses(
    stereotype_id: str,
    metaclasses: list[str],
) -> dict[str, Any]:
    """Set the base metaclasses for a stereotype using Cameo's supported API."""
    body: dict[str, Any] = {"metaclasses": metaclasses}
    return await _request("PUT", f"/elements/{stereotype_id}/metaclasses", json_body=body)


async def apply_profile(
    package_id: str,
    profile_id: Optional[str] = None,
    profile_name: Optional[str] = None,
) -> dict[str, Any]:
    """Apply a profile to a model/package."""
    body: dict[str, Any] = {}
    if profile_id is not None:
        body["profileId"] = profile_id
    if profile_name is not None:
        body["profileName"] = profile_name
    return await _request("POST", f"/elements/{package_id}/apply-profile", json_body=body)

# -- Relationships ------------------------------------------------------------


async def get_relationships(
    element_id: str,
    direction: Optional[str] = None,
) -> dict[str, Any]:
    """Get relationships for an element."""
    params: dict[str, Any] = {}
    if direction is not None:
        params["direction"] = direction
    return await _request("GET", f"/elements/{element_id}/relationships", params=params)


async def get_interface_flow_properties(
    interface_block_ids: list[str],
) -> dict[str, Any]:
    """Read interface blocks and their owned flow properties in one native bridge call."""
    return await _request(
        "POST",
        "/elements/interface-flow-properties",
        json_body={"interfaceIds": interface_block_ids},
    )


async def create_relationship(
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
    """Create a relationship between two elements."""
    body: dict[str, Any] = {
        "type": type,
        "sourceId": source_id,
        "targetId": target_id,
    }
    if name is not None:
        body["name"] = name
    if guard is not None:
        body["guard"] = guard
    if owner_id is not None:
        body["ownerId"] = owner_id
    if source_part_with_port_id is not None:
        body["sourcePartWithPortId"] = source_part_with_port_id
    if target_part_with_port_id is not None:
        body["targetPartWithPortId"] = target_part_with_port_id
    if realizing_connector_id is not None:
        body["realizingConnectorId"] = realizing_connector_id
    if conveyed_ids is not None:
        body["conveyedIds"] = conveyed_ids
    if item_property_id is not None:
        body["itemPropertyId"] = item_property_id
    return await _request("POST", "/relationships", json_body=body)

# -- Matrices -----------------------------------------------------------------


async def list_matrices(
    kind: Optional[str] = None,
    owner_id: Optional[str] = None,
) -> dict[str, Any]:
    """List supported native requirement matrices in the current project."""
    params: dict[str, Any] = {}
    if kind is not None:
        params["kind"] = kind
    if owner_id is not None:
        params["ownerId"] = owner_id
    return await _request("GET", "/matrices", params=params)


async def get_matrix(matrix_id: str) -> dict[str, Any]:
    """Get one supported native requirement matrix with populated cell data."""
    return await _request("GET", f"/matrices/{matrix_id}")


async def create_matrix(
    kind: str,
    parent_id: str,
    name: Optional[str] = None,
    scope_id: Optional[str] = None,
    row_scope_id: Optional[str] = None,
    column_scope_id: Optional[str] = None,
    row_types: Optional[list[str]] = None,
    column_types: Optional[list[str]] = None,
) -> dict[str, Any]:
    """Create a native refine/derive requirement matrix."""
    body: dict[str, Any] = {
        "kind": normalize_matrix_kind(kind),
        "parentId": parent_id,
    }
    if name is not None:
        body["name"] = name
    if scope_id is not None:
        body["scopeId"] = scope_id
    if row_scope_id is not None:
        body["rowScopeId"] = row_scope_id
    if column_scope_id is not None:
        body["columnScopeId"] = column_scope_id
    if row_types is not None:
        body["rowTypes"] = row_types
    if column_types is not None:
        body["columnTypes"] = column_types
    return await _request("POST", "/matrices", json_body=body)

# -- Diagrams -----------------------------------------------------------------


async def list_diagrams() -> dict[str, Any]:
    """List all diagrams in the current project."""
    return await _request("GET", "/diagrams")


async def create_diagram(
    type: str,
    name: str,
    parent_id: str,
) -> dict[str, Any]:
    """Create a new diagram."""
    body: dict[str, Any] = {
        "type": normalize_diagram_type(type),
        "name": name,
        "parentId": parent_id,
    }
    return await _request("POST", "/diagrams", json_body=body)


async def add_to_diagram(
    diagram_id: str,
    element_id: str,
    x: Optional[int] = None,
    y: Optional[int] = None,
    width: Optional[int] = None,
    height: Optional[int] = None,
    container_presentation_id: Optional[str] = None,
) -> dict[str, Any]:
    """Add a model element to a diagram canvas."""
    has_explicit_width = width is not None and width >= 0
    has_explicit_height = height is not None and height >= 0
    if has_explicit_width != has_explicit_height:
        raise ValueError(
            "width and height must both be non-negative, or both be omitted/negative"
        )

    if container_presentation_id is None:
        element = await get_element(element_id)
        if _is_activity_partition_element(element):
            return await _add_activity_partition_to_diagram_via_macro(
                diagram_id,
                element_id,
                x=x,
                y=y,
                width=width if has_explicit_width else None,
                height=height if has_explicit_height else None,
            )

    body: dict[str, Any] = {"elementId": element_id}
    if x is not None:
        body["x"] = x
    if y is not None:
        body["y"] = y
    if has_explicit_width:
        body["width"] = width
    if has_explicit_height:
        body["height"] = height
    if container_presentation_id is not None:
        body["containerPresentationId"] = container_presentation_id
    return await _request("POST", f"/diagrams/{diagram_id}/elements", json_body=body)


async def get_diagram_image(diagram_id: str) -> dict[str, Any]:
    """Export a diagram as a base64-encoded image."""
    return await _request("GET", f"/diagrams/{diagram_id}/image")


async def auto_layout(diagram_id: str) -> dict[str, Any]:
    """Apply automatic layout to a diagram."""
    return await _request("POST", f"/diagrams/{diagram_id}/layout")

# -- Diagram Shape Management -------------------------------------------------


async def list_diagram_shapes(diagram_id: str) -> dict[str, Any]:
    """List all shapes and paths on a diagram with bounds and element info."""
    return await _request("GET", f"/diagrams/{diagram_id}/shapes")


async def get_shape_properties(
    diagram_id: str,
    presentation_id: str,
) -> dict[str, Any]:
    """Read the current display properties exposed by a diagram shape."""
    return await _request("GET", f"/diagrams/{diagram_id}/shapes/{presentation_id}/properties")


async def move_shapes(
    diagram_id: str,
    shapes: list[dict[str, Any]],
) -> dict[str, Any]:
    """Move/resize shapes on a diagram."""
    return await _request("PUT", f"/diagrams/{diagram_id}/shapes", json_body={"shapes": shapes})


async def delete_shapes(
    diagram_id: str,
    presentation_ids: list[str],
) -> dict[str, Any]:
    """Delete presentation elements from a diagram."""
    return await _request("DELETE", f"/diagrams/{diagram_id}/shapes", json_body={"presentationIds": presentation_ids})


async def add_diagram_paths(
    diagram_id: str,
    paths: list[dict[str, Any]],
) -> dict[str, Any]:
    """Add relationship paths to a diagram."""
    return await _request("POST", f"/diagrams/{diagram_id}/paths", json_body={"paths": paths})


async def set_shape_properties(
    diagram_id: str,
    presentation_id: str,
    properties: dict[str, Any],
) -> dict[str, Any]:
    """Set display properties on a diagram shape."""
    return await _request("PUT", f"/diagrams/{diagram_id}/shapes/{presentation_id}/properties", json_body={"properties": properties})


async def set_shape_compartments(
    diagram_id: str,
    presentation_id: str,
    compartments: dict[str, Any],
) -> dict[str, Any]:
    """Set compartment-focused presentation controls on a diagram shape."""
    return await _request(
        "PUT",
        f"/diagrams/{diagram_id}/shapes/{presentation_id}/compartments",
        json_body={"compartments": compartments},
    )


async def reparent_shapes(
    diagram_id: str,
    reparentings: list[dict[str, Any]],
) -> dict[str, Any]:
    """Move existing presentation elements under new container shapes."""
    return await _request(
        "PUT",
        f"/diagrams/{diagram_id}/shapes/reparent",
        json_body={"reparentings": reparentings},
    )


async def route_paths(
    diagram_id: str,
    routes: list[dict[str, Any]],
) -> dict[str, Any]:
    """Update path breakpoints and endpoints for existing relationship paths."""
    return await _request(
        "PUT",
        f"/diagrams/{diagram_id}/paths/route",
        json_body={"routes": routes},
    )

# -- Containment Tree ---------------------------------------------------------


async def get_containment_tree(
    root_id: Optional[str] = None,
    depth: Optional[int] = None,
    view: Optional[str] = None,
) -> dict[str, Any]:
    """Browse the containment tree structure."""
    params: dict[str, Any] = {}
    if root_id is not None:
        params["rootId"] = root_id
    if depth is not None:
        params["depth"] = str(depth)
    if view is not None:
        params["view"] = view
    return await _request("GET", "/containment-tree", params=params)


async def list_containment_children(
    root_id: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    type: Optional[str] = None,
    name: Optional[str] = None,
    stereotype: Optional[str] = None,
    view: Optional[str] = None,
) -> dict[str, Any]:
    """List a compact, paginated slice of the containment tree."""
    params: dict[str, Any] = {
        "limit": str(limit),
        "offset": str(offset),
    }
    if root_id is not None:
        params["rootId"] = root_id
    if type is not None:
        params["type"] = type
    if name is not None:
        params["name"] = name
    if stereotype is not None:
        params["stereotype"] = stereotype
    if view is not None:
        params["view"] = view
    return await _request("GET", "/containment-tree/children", params=params)


# -- Specification -----------------------------------------------------------


async def get_specification(element_id: str) -> dict[str, Any]:
    """Get the full specification (all properties + tagged values) of an element."""
    return await _request("GET", f"/elements/{element_id}/specification")


async def set_specification(
    element_id: str,
    properties: Optional[dict[str, Any]] = None,
    constraints: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Set properties and/or constraints on an element's specification."""
    body: dict[str, Any] = {}
    if properties is not None:
        body["properties"] = properties
    if constraints is not None:
        body["constraints"] = constraints
    return await _request("PUT", f"/elements/{element_id}/specification", json_body=body)


async def set_usecase_subject(
    element_id: str,
    subject_ids: list[str],
    append: bool = False,
) -> dict[str, Any]:
    """Set or append subject classifiers on a UseCase."""
    body: dict[str, Any] = {"subjectIds": subject_ids, "append": append}
    return await _request("PUT", f"/elements/{element_id}/usecase-subject", json_body=body)


# -- Session Management -------------------------------------------------------


async def reset_session() -> dict[str, Any]:
    """Force-close any stuck model session."""
    return await _request("POST", "/session/reset")

# -- Macros -------------------------------------------------------------------


async def execute_macro(script: str) -> dict[str, Any]:
    """Execute a Groovy script inside CATIA Magic's JVM."""
    body: dict[str, Any] = {"script": script}
    return await _request("POST", "/macros/execute", json_body=body)
