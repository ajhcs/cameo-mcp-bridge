"""HTTP client for the CameoMCPBridge Java plugin REST API."""

from __future__ import annotations

import os
from typing import Any, Optional

import httpx


def _base_url() -> str:
    port = os.environ.get("CAMEO_BRIDGE_PORT", "18740")
    return f"http://127.0.0.1:{port}/api/v1"


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(base_url=_base_url(), timeout=30.0)


async def _request(
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
        async with _client() as client:
            response = await client.request(
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

# -- Status / Project --------------------------------------------------------


async def status() -> dict[str, Any]:
    """Check plugin health."""
    return await _request("GET", "/status")


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
    return await _request("POST", "/relationships", json_body=body)

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
) -> dict[str, Any]:
    """Add a model element to a diagram canvas."""
    body: dict[str, Any] = {"elementId": element_id}
    if x is not None:
        body["x"] = x
    if y is not None:
        body["y"] = y
    if width is not None:
        body["width"] = width
    if height is not None:
        body["height"] = height
    return await _request("POST", f"/diagrams/{diagram_id}/elements", json_body=body)


async def get_diagram_image(diagram_id: str) -> dict[str, Any]:
    """Export a diagram as a base64-encoded image."""
    return await _request("GET", f"/diagrams/{diagram_id}/image")


async def auto_layout(diagram_id: str) -> dict[str, Any]:
    """Apply automatic layout to a diagram."""
    return await _request("POST", f"/diagrams/{diagram_id}/layout")

# -- Containment Tree ---------------------------------------------------------


async def get_containment_tree(
    root_id: Optional[str] = None,
    depth: Optional[int] = None,
) -> dict[str, Any]:
    """Browse the containment tree structure."""
    params: dict[str, Any] = {}
    if root_id is not None:
        params["rootId"] = root_id
    if depth is not None:
        params["depth"] = str(depth)
    return await _request("GET", "/containment-tree", params=params)


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
    if properties:
        body["properties"] = properties
    if constraints:
        body["constraints"] = constraints
    return await _request("PUT", f"/elements/{element_id}/specification", json_body=body)


# -- Macros -------------------------------------------------------------------


async def execute_macro(script: str) -> dict[str, Any]:
    """Execute a Groovy script inside CATIA Magic's JVM."""
    body: dict[str, Any] = {"script": script}
    return await _request("POST", "/macros/execute", json_body=body)
