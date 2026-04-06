"""HTTP client for the CameoMCPBridge Java plugin REST API."""

from __future__ import annotations

import os
from typing import Any, Optional

import httpx

BRIDGE_PLUGIN_VERSION = "1.0.0"
BRIDGE_API_VERSION = "v1"
BRIDGE_HANDSHAKE_VERSION = "1"


def _base_url() -> str:
    port = os.environ.get("CAMEO_BRIDGE_PORT", "18740")
    return f"http://127.0.0.1:{port}/api/v1"


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


async def create_relationship(
    type: str,
    source_id: str,
    target_id: str,
    name: Optional[str] = None,
    guard: Optional[str] = None,
    owner_id: Optional[str] = None,
    source_part_with_port_id: Optional[str] = None,
    target_part_with_port_id: Optional[str] = None,
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
) -> dict[str, Any]:
    """Create a native refine/derive requirement matrix."""
    body: dict[str, Any] = {
        "kind": kind,
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
        "type": type,
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
    body: dict[str, Any] = {"elementId": element_id}
    has_explicit_width = width is not None and width >= 0
    has_explicit_height = height is not None and height >= 0
    if has_explicit_width != has_explicit_height:
        raise ValueError(
            "width and height must both be non-negative, or both be omitted/negative"
        )
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
