"""HTTP client for the CameoMCPBridge Java plugin REST API."""

from __future__ import annotations

import base64
import os
import re
from collections import Counter
from io import BytesIO
from typing import Any, Optional

import httpx
from PIL import Image

BRIDGE_PLUGIN_VERSION = "2.3.5"
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
    {"canonical": "RelationMap", "nativeType": "Relation Map Diagram", "family": "analysis", "aliases": ["relation map", "relationship map", "RelationMap", "Relation Map", "Relation Map Diagram", "Relationship Map", "Relationship Map Diagram"]},
    {"canonical": "Content Diagram", "nativeType": "Content Diagram", "family": "analysis", "aliases": ["content", "content diagram", "ContentDiagram", "Content Diagram"]},
]

VALIDATED_MATRIX_KINDS: list[dict[str, Any]] = [
    {
        "kind": "refine",
        "nativeType": "Refine Requirement Matrix",
        "aliases": ["refine", "refine matrix", "refine requirement matrix"],
        "validatedRowTypeExamples": ["Activity"],
        "validatedColumnTypeExamples": ["Requirement"],
    },
    {
        "kind": "derive",
        "nativeType": "Derive Requirement Matrix",
        "aliases": ["derive", "derive matrix", "derive requirement matrix"],
        "validatedRowTypeExamples": ["Requirement"],
        "validatedColumnTypeExamples": ["Requirement"],
    },
    {
        "kind": "satisfy",
        "nativeType": "Satisfy Requirement Matrix",
        "aliases": ["satisfy", "satisfy matrix", "satisfy requirement matrix"],
        "validatedRowTypeExamples": ["Block", "Component", "Property"],
        "validatedColumnTypeExamples": ["Requirement"],
    },
    {
        "kind": "allocation",
        "nativeType": "SysML Allocation Matrix",
        "aliases": ["allocation", "allocation matrix", "system allocation matrix", "sysml allocation matrix"],
        "validatedRowTypeExamples": ["Block", "Property", "UseCase"],
        "validatedColumnTypeExamples": ["Block", "Property", "Component"],
    },
    {
        "kind": "dependency",
        "nativeType": "Dependency Matrix",
        "aliases": ["dependency", "dependency matrix"],
        "validatedRowTypeExamples": ["Activity", "OpaqueAction", "Block", "Requirement"],
        "validatedColumnTypeExamples": ["Activity", "OpaqueAction", "Block", "Requirement"],
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
            target_height = max_height if max_height is not None and max_height > 0 else image.height
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
    timeout: Optional[float] = None,
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
            timeout=timeout,
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
    except httpx.TimeoutException:
        timeout_label = f"{timeout:g}s" if timeout is not None else "the configured timeout"
        raise TimeoutError(
            f"CameoMCPBridge request timed out after {timeout_label}: {method} {path}. "
            "Long-running CATIA operations such as diagram image export may need a higher timeout "
            "or a no-image validation pass."
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
    timeout: Optional[float] = None,
) -> dict[str, Any]:
    if path not in {"/status", "/capabilities"}:
        await _ensure_compatible_bridge()
    return await _request_raw(method, path, params=params, json_body=json_body, timeout=timeout)

# -- Status / Project --------------------------------------------------------


async def status() -> dict[str, Any]:
    """Check plugin health."""
    return _annotate_bridge_metadata(await _request_raw("GET", "/status"))


async def get_capabilities() -> dict[str, Any]:
    """Get plugin capability and compatibility metadata."""
    return _annotate_bridge_metadata(await _request_raw("GET", "/capabilities"))


async def get_ui_state(summary_only: bool = False) -> dict[str, Any]:
    """Get active project, active diagram, browser selection, and symbol selection."""
    return await _request("GET", "/ui/state", params={"summaryOnly": summary_only})


async def get_active_diagram() -> dict[str, Any]:
    """Get the currently active diagram in the CATIA Magic UI."""
    return await _request("GET", "/ui/active-diagram")


async def get_ui_selection() -> dict[str, Any]:
    """Get current selected browser elements and diagram presentation elements."""
    return await _request("GET", "/ui/selection")


async def probe_bridge() -> dict[str, Any]:
    """Probe common bridge health/capability endpoints without assuming one path."""
    port = os.environ.get("CAMEO_BRIDGE_PORT", "18740")
    root_url = f"http://127.0.0.1:{port}"
    probes = [
        ("status", "/status"),
        ("status", "/api/v1/status"),
        ("capabilities", "/capabilities"),
        ("capabilities", "/api/v1/capabilities"),
    ]
    results: list[dict[str, Any]] = []

    try:
        async with httpx.AsyncClient(base_url=root_url, timeout=5.0) as probe_client:
            for kind, path in probes:
                entry: dict[str, Any] = {"kind": kind, "path": path}
                try:
                    response = await probe_client.get(path)
                    entry["statusCode"] = response.status_code
                    if response.status_code == 204 or not response.content:
                        entry["ok"] = True
                        entry["payload"] = {"status": "ok"}
                    else:
                        try:
                            payload = response.json()
                        except Exception:
                            payload = {"rawText": response.text}
                        entry["ok"] = 200 <= response.status_code < 300
                        entry["payload"] = payload
                        if isinstance(payload, dict) and (
                            payload.get("pluginVersion") or payload.get("version")
                        ):
                            entry["payload"] = _annotate_bridge_metadata(payload)
                except Exception as exc:
                    entry["ok"] = False
                    entry["error"] = str(exc)
                results.append(entry)
    except httpx.ConnectError:
        return {
            "reachable": False,
            "baseUrl": root_url,
            "preferredStatusPath": None,
            "preferredCapabilitiesPath": None,
            "results": results,
        }

    def _preferred(kind: str) -> Optional[str]:
        for entry in results:
            if entry.get("kind") == kind and entry.get("ok"):
                return str(entry["path"])
        return None

    return {
        "reachable": any(entry.get("ok") for entry in results),
        "baseUrl": root_url,
        "preferredStatusPath": _preferred("status"),
        "preferredCapabilitiesPath": _preferred("capabilities"),
        "results": results,
    }


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
    if type_id is not None:
        body["typeId"] = type_id
    if lower is not None:
        body["lower"] = lower
    if upper is not None:
        body["upper"] = upper
    if is_ordered is not None:
        body["isOrdered"] = is_ordered
    if is_unique is not None:
        body["isUnique"] = is_unique
    if aggregation is not None:
        body["aggregation"] = aggregation
    if is_behavior is not None:
        body["isBehavior"] = is_behavior
    if is_conjugated is not None:
        body["isConjugated"] = is_conjugated
    if is_service is not None:
        body["isService"] = is_service
    if direction is not None:
        body["direction"] = direction
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
    """List supported native matrix artifacts in the current project."""
    params: dict[str, Any] = {}
    if kind is not None:
        params["kind"] = normalize_matrix_kind(kind)
    if owner_id is not None:
        params["ownerId"] = owner_id
    return await _request("GET", "/matrices", params=params)


async def get_matrix(matrix_id: str) -> dict[str, Any]:
    """Get one supported native matrix with populated cell data."""
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
    """Create a supported native matrix artifact."""
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

# -- Generic Tables -----------------------------------------------------------


async def list_generic_tables() -> dict[str, Any]:
    """List native Generic Table artifacts in the current project."""
    return await _request("GET", "/generic-tables")


async def get_generic_table(table_id: str) -> dict[str, Any]:
    """Get one native Generic Table with row, column, and cell data."""
    return await _request("GET", f"/generic-tables/{table_id}")


async def list_generic_table_columns(
    element_id: Optional[str] = None,
    element_type: Optional[str] = None,
) -> dict[str, Any]:
    """List possible native Generic Table column ids for an element or type."""
    params: dict[str, Any] = {}
    if element_id is not None:
        params["elementId"] = element_id
    if element_type is not None:
        params["elementType"] = element_type
    return await _request("GET", "/generic-tables/columns", params=params)


async def create_generic_table(
    parent_id: str,
    name: Optional[str] = None,
    element_types: Optional[list[str]] = None,
    scope_ids: Optional[list[str]] = None,
    row_element_ids: Optional[list[str]] = None,
    column_ids: Optional[list[str]] = None,
) -> dict[str, Any]:
    """Create and configure a native Generic Table artifact."""
    body: dict[str, Any] = {"parentId": parent_id}
    if name is not None:
        body["name"] = name
    if element_types is not None:
        body["elementTypes"] = element_types
    if scope_ids is not None:
        body["scopeIds"] = scope_ids
    if row_element_ids is not None:
        body["rowElementIds"] = row_element_ids
    if column_ids is not None:
        body["columnIds"] = column_ids
    return await _request("POST", "/generic-tables", json_body=body)

# -- Relation Maps ------------------------------------------------------------


async def list_relation_maps() -> dict[str, Any]:
    """List native Relation Map artifacts in the current project."""
    return await _request("GET", "/relation-maps")


async def get_relation_map(relation_map_id: str) -> dict[str, Any]:
    """Get one native Relation Map with persisted graph settings."""
    return await _request("GET", f"/relation-maps/{relation_map_id}")


def _relation_map_settings_body(
    *,
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
    body: dict[str, Any] = {}
    if context_element_id is not None:
        body["contextElementId"] = context_element_id
    if scope_ids is not None:
        body["scopeIds"] = scope_ids
    if element_type_ids is not None:
        body["elementTypeIds"] = element_type_ids
    if dependency_criteria is not None:
        body["dependencyCriteria"] = dependency_criteria
    if depth is not None:
        body["depth"] = depth
    if layout is not None:
        body["layout"] = layout
    optional_flags = {
        "legendEnabled": legend_enabled,
        "showFullTypes": show_full_types,
        "showStereotypes": show_stereotypes,
        "showParameters": show_parameters,
        "showElementNumbers": show_element_numbers,
        "singleNodePerElement": single_node_per_element,
        "shortNodeNames": short_node_names,
        "typesIncludeSubtypes": types_include_subtypes,
        "typesIncludeCustomTypes": types_include_custom_types,
        "makeElementAsContext": make_element_as_context,
    }
    body.update({key: value for key, value in optional_flags.items() if value is not None})
    return body


async def create_relation_map(
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
    """Create and configure a native Relation Map artifact."""
    body = {"parentId": parent_id}
    if name is not None:
        body["name"] = name
    body.update(
        _relation_map_settings_body(
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
    )
    return await _request("POST", "/relation-maps", json_body=body)


async def configure_relation_map(
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
    """Update persisted settings for a native Relation Map artifact."""
    body = _relation_map_settings_body(
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
    return await _request(
        "PUT",
        f"/relation-maps/{relation_map_id}/settings",
        json_body=body,
    )


async def refresh_relation_map(relation_map_id: str, timeout: float = 120.0) -> dict[str, Any]:
    """Refresh a native Relation Map after model or settings changes.

    Native CATIA refresh can block for large maps, so callers should invoke it
    deliberately and expect a long-running write operation.
    """
    return await _request(
        "POST",
        f"/relation-maps/{relation_map_id}/refresh",
        json_body={"refreshTimeoutSeconds": max(1, int(timeout))},
        timeout=timeout,
    )


async def get_relation_map_raw_settings(
    relation_map_id: str,
    include_raw: bool = False,
    summary_only: bool = False,
) -> dict[str, Any]:
    """Dump native GraphSettings fields and reflected no-arg getter values."""
    return await _request(
        "GET",
        f"/relation-maps/{relation_map_id}/settings/raw",
        params={"includeRaw": include_raw, "summaryOnly": summary_only},
    )


async def get_relation_map_presentations(
    relation_map_id: str,
    include_properties: bool = False,
    include_raw: bool = False,
    summary_only: bool = True,
    limit: int = 250,
    offset: int = 0,
) -> dict[str, Any]:
    """List loaded Relation Map presentation elements, including nodes, paths, and legend symbols."""
    return await _request(
        "GET",
        f"/relation-maps/{relation_map_id}/presentations",
        params={
            "includeProperties": include_properties,
            "includeRaw": include_raw,
            "summaryOnly": summary_only,
            "limit": limit,
            "offset": offset,
        },
    )


async def list_relation_map_criteria_templates() -> dict[str, Any]:
    """List built-in Relation Map criteria templates."""
    return await _request("GET", "/relation-maps/criteria/templates")


async def set_relation_map_criteria(
    relation_map_id: str,
    mode: str = "replace",
    criteria: Optional[list[dict[str, Any] | str]] = None,
    refresh: bool = False,
) -> dict[str, Any]:
    """Apply native Relation Map dependency criteria."""
    return await _request(
        "PUT",
        f"/relation-maps/{relation_map_id}/criteria",
        json_body={"mode": mode, "criteria": criteria or [], "refresh": refresh},
    )


async def expand_relation_map(
    relation_map_id: str,
    mode: str = "all",
    element_ids: Optional[list[str]] = None,
    depth: Optional[int] = None,
    refresh: bool = False,
    layout: Optional[str] = None,
    timeout: float = 120.0,
) -> dict[str, Any]:
    """Try to expand native Relation Map graph nodes."""
    body: dict[str, Any] = {"mode": mode, "refresh": refresh}
    if element_ids is not None:
        body["elementIds"] = element_ids
    if depth is not None:
        body["depth"] = depth
    if layout is not None:
        body["layout"] = layout
    body["actionTimeoutSeconds"] = max(1, int(timeout))
    return await _request("POST", f"/relation-maps/{relation_map_id}/expand", json_body=body, timeout=timeout)


async def collapse_relation_map(
    relation_map_id: str,
    mode: str = "all",
    element_ids: Optional[list[str]] = None,
    refresh: bool = False,
    timeout: float = 120.0,
) -> dict[str, Any]:
    """Try to collapse native Relation Map graph nodes."""
    body: dict[str, Any] = {"mode": mode, "refresh": refresh}
    if element_ids is not None:
        body["elementIds"] = element_ids
    body["actionTimeoutSeconds"] = max(1, int(timeout))
    return await _request("POST", f"/relation-maps/{relation_map_id}/collapse", json_body=body, timeout=timeout)


async def render_relation_map(
    relation_map_id: str,
    refresh: bool = False,
    expand: str = "none",
    depth: Optional[int] = None,
    layout: Optional[str] = None,
    scale_percentage: int = 200,
    include_image: bool = True,
    include_presentation_summary: bool = True,
    export_image: Optional[bool] = None,
    timeout: float = 120.0,
) -> dict[str, Any]:
    """Run the Relation Map render/export pipeline.

    Native Relation Map refresh can block CATIA for large maps, so it is opt-in.
    """
    body: dict[str, Any] = {
        "refresh": refresh,
        "expand": expand,
        "scalePercentage": scale_percentage,
        "includeImage": include_image,
        "includePresentationSummary": include_presentation_summary,
    }
    if depth is not None:
        body["depth"] = depth
    if layout is not None:
        body["layout"] = layout
    if export_image is not None:
        body["exportImage"] = export_image
    body["renderTimeoutSeconds"] = max(1, int(timeout))
    return await _request("POST", f"/relation-maps/{relation_map_id}/render", json_body=body, timeout=timeout)


async def verify_relation_map(
    relation_map_id: str,
    expected_min_nodes: int = 0,
    expected_min_edges: int = 0,
    expected_rendered_nodes: int = 0,
    relationship_types: Optional[list[str]] = None,
    max_depth: int = 3,
) -> dict[str, Any]:
    """Verify graph traversal, native settings validity, and rendered presentation count."""
    body: dict[str, Any] = {
        "expectedMinNodes": expected_min_nodes,
        "expectedMinEdges": expected_min_edges,
        "expectedRenderedNodes": expected_rendered_nodes,
        "maxDepth": max_depth,
    }
    if relationship_types is not None:
        body["relationshipTypes"] = relationship_types
    return await _request("POST", f"/relation-maps/{relation_map_id}/verify", json_body=body)


async def compare_relation_maps(
    left_relation_map_id: str,
    right_relation_map_id: str,
    include_presentations: bool = True,
    include_raw: bool = False,
) -> dict[str, Any]:
    """Compare two Relation Maps using the native inspection serializers."""
    return await _request(
        "POST",
        "/relation-maps/compare",
        json_body={
            "leftRelationMapId": left_relation_map_id,
            "rightRelationMapId": right_relation_map_id,
            "includePresentations": include_presentations,
            "includeRaw": include_raw,
        },
    )


async def create_snapshot(
    target_type: str,
    target_id: Optional[str] = None,
    name: Optional[str] = None,
    include_raw: bool = False,
    include_presentations: Optional[bool] = None,
    include_properties: Optional[bool] = None,
) -> dict[str, Any]:
    """Create an in-memory before/after inspection snapshot."""
    body: dict[str, Any] = {
        "targetType": target_type,
        "includeRaw": include_raw,
    }
    if target_id is not None:
        body["targetId"] = target_id
    if name is not None:
        body["name"] = name
    if include_presentations is not None:
        body["includePresentations"] = include_presentations
    if include_properties is not None:
        body["includeProperties"] = include_properties
    return await _request("POST", "/snapshots", json_body=body)


async def list_snapshots() -> dict[str, Any]:
    """List in-memory snapshots held by the Java bridge."""
    return await _request("GET", "/snapshots")


async def get_snapshot(snapshot_id: str) -> dict[str, Any]:
    """Get one in-memory snapshot payload."""
    return await _request("GET", f"/snapshots/{snapshot_id}")


async def delete_snapshot(snapshot_id: str) -> dict[str, Any]:
    """Delete one in-memory snapshot without touching the model."""
    return await _request("DELETE", f"/snapshots/{snapshot_id}")


async def diff_snapshots(
    before_snapshot_id: str,
    after_snapshot_id: str,
    ignore_paths: Optional[list[str]] = None,
    include_details: bool = True,
    max_changes: int = 500,
) -> dict[str, Any]:
    """Diff two in-memory snapshots with stable JSON paths."""
    body: dict[str, Any] = {
        "beforeSnapshotId": before_snapshot_id,
        "afterSnapshotId": after_snapshot_id,
        "includeDetails": include_details,
        "maxChanges": max_changes,
    }
    if ignore_paths is not None:
        body["ignorePaths"] = ignore_paths
    return await _request("POST", "/snapshots/diff", json_body=body)


async def get_validation_capabilities() -> dict[str, Any]:
    """Probe native CATIA validation API availability."""
    return await _request("GET", "/validation/capabilities")


async def list_validation_suites() -> dict[str, Any]:
    """List native validation suite candidates and constraints."""
    return await _request("GET", "/validation/suites")


async def run_native_validation(
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
    """Run native CATIA validation against a suite or explicit constraints."""
    body: dict[str, Any] = {
        "recursive": recursive,
        "excludeReadOnly": exclude_read_only,
        "openNativeWindow": open_native_window,
    }
    if suite_id is not None:
        body["suiteId"] = suite_id
    if constraint_ids is not None:
        body["constraintIds"] = constraint_ids
    if scope_element_ids is not None:
        body["scopeElementIds"] = scope_element_ids
    if whole_project is not None:
        body["wholeProject"] = whole_project
    if minimum_severity is not None:
        body["minimumSeverity"] = minimum_severity
    if name is not None:
        body["name"] = name
    return await _request("POST", "/validation/run", json_body=body)


async def get_validation_result(run_id: str) -> dict[str, Any]:
    """Fetch a cached native validation run result."""
    return await _request("GET", f"/validation/results/{run_id}")


async def list_probe_templates() -> dict[str, Any]:
    """List safe built-in CATIA API discovery probes."""
    return await _request("GET", "/probes/templates")


async def execute_probe(
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
    """Execute a controlled built-in probe. Arbitrary scripts are refused by Java."""
    body: dict[str, Any] = {
        "mode": mode,
        "language": language,
        "timeoutMs": timeout_ms,
        "requiresProject": requires_project,
    }
    if template is not None:
        body["template"] = template
    if script is not None:
        body["script"] = script
    if description is not None:
        body["description"] = description
    if operation is not None:
        body["operation"] = operation
    if class_name is not None:
        body["className"] = class_name
    if method_name is not None:
        body["methodName"] = method_name
    if relation_map_id is not None:
        body["relationMapId"] = relation_map_id
    return await _request("POST", "/probes/execute", json_body=body)


async def get_advanced_capability(feature: str) -> dict[str, Any]:
    """Get a probe-first capability contract for an advanced route family."""
    return await _request("GET", f"/{feature}/capabilities")


async def run_validation(
    suite_id: Optional[str] = None,
    constraint_ids: Optional[list[str]] = None,
    scope_mode: str = "project",
    scope_element_ids: Optional[list[str]] = None,
    min_severity: Optional[str] = None,
    timeout_ms: int = 30000,
) -> dict[str, Any]:
    """Run or preview a bounded native validation request."""
    body: dict[str, Any] = {"scopeMode": scope_mode, "timeoutMs": timeout_ms}
    if suite_id is not None:
        body["suiteId"] = suite_id
    if constraint_ids is not None:
        body["constraintIds"] = constraint_ids
    if scope_element_ids is not None:
        body["scopeElementIds"] = scope_element_ids
    if min_severity is not None:
        body["minSeverity"] = min_severity
    return await _request("POST", "/validation/run", json_body=body)


async def get_report_capabilities() -> dict[str, Any]:
    """Probe Report Wizard API support."""
    return await get_advanced_capability("reports")


async def list_report_templates() -> dict[str, Any]:
    """List report templates when native readback is promoted."""
    return await _request("GET", "/reports/templates")


async def generate_report_preview(
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
    body: dict[str, Any] = {}
    if template_id is not None:
        body["templateId"] = template_id
    if template_name is not None:
        body["templateName"] = template_name
    if report_name is not None:
        body["reportName"] = report_name
    if output_path is not None:
        body["outputPath"] = output_path
    if output_format is not None:
        body["format"] = output_format
    if scope_element_ids is not None:
        body["scopeElementIds"] = scope_element_ids
    if recursive is not None:
        body["recursive"] = recursive
    if parameters is not None:
        body["parameters"] = parameters
    return await _request("POST", "/reports/generate-preview", json_body=body)


async def generate_report(
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
    """Generate a Report Wizard artifact through the native bridge endpoint."""
    body: dict[str, Any] = {"allowWrite": allow_write}
    if template_id is not None:
        body["templateId"] = template_id
    if template_name is not None:
        body["templateName"] = template_name
    if report_name is not None:
        body["reportName"] = report_name
    if output_path is not None:
        body["outputPath"] = output_path
    if output_format is not None:
        body["format"] = output_format
    if scope_element_ids is not None:
        body["scopeElementIds"] = scope_element_ids
    if recursive is not None:
        body["recursive"] = recursive
    if display_in_viewer is not None:
        body["displayInViewer"] = display_in_viewer
    if parameters is not None:
        body["parameters"] = parameters
    return await _request("POST", "/reports/generate", json_body=body)


async def get_report_job(job_id: str) -> dict[str, Any]:
    """Fetch a Report Wizard generation job status."""
    return await _request("GET", f"/reports/jobs/{job_id}")


async def get_requirements_capabilities() -> dict[str, Any]:
    """Probe Requirements/ReqIF API support."""
    return await get_advanced_capability("requirements")


async def get_import_export_capabilities() -> dict[str, Any]:
    """Probe bridge-owned and native import/export support."""
    return await _request("GET", "/import-export/capabilities")


async def export_requirements(
    scope_ids: Optional[list[str]] = None,
    root_id: Optional[str] = None,
    package_id: Optional[str] = None,
    format: str = "json",
    output_path: Optional[str] = None,
    limit: int = 1000,
) -> dict[str, Any]:
    """Export requirement-like elements through the import/export route."""
    body: dict[str, Any] = {"format": format, "limit": limit}
    if scope_ids is not None:
        body["scopeIds"] = scope_ids
    if root_id is not None:
        body["rootId"] = root_id
    if package_id is not None:
        body["packageId"] = package_id
    if output_path is not None:
        body["outputPath"] = output_path
    return await _request("POST", "/import-export/requirements/export", json_body=body)


async def preview_requirements_import(
    source_path: Optional[str] = None,
    source_rows: Optional[list[dict[str, Any]]] = None,
    requirements: Optional[list[dict[str, Any]]] = None,
    csv_text: Optional[str] = None,
    target_package_id: Optional[str] = None,
) -> dict[str, Any]:
    """Preview requirement import through the import/export route."""
    body: dict[str, Any] = {}
    if source_path is not None:
        body["sourcePath"] = source_path
    if source_rows is not None:
        body["sourceRows"] = source_rows
        body["rows"] = source_rows
    if requirements is not None:
        body["requirements"] = requirements
    if csv_text is not None:
        body["csvText"] = csv_text
    if target_package_id is not None:
        body["targetPackageId"] = target_package_id
    return await _request("POST", "/import-export/requirements/import-preview", json_body=body)


async def apply_requirements_import(
    patch_plan: Optional[dict[str, Any]] = None,
    *,
    target_package_id: Optional[str] = None,
    requirements: Optional[list[dict[str, Any]]] = None,
    rows: Optional[list[dict[str, Any]]] = None,
    csv_text: Optional[str] = None,
    format: str = "json",
    dry_run: bool = True,
    allow_write: bool = False,
) -> dict[str, Any]:
    """Apply or dry-run a reviewed requirements import request."""
    body: dict[str, Any] = {"format": format, "dryRun": dry_run, "allowWrite": allow_write}
    if patch_plan is not None:
        body["patchPlan"] = patch_plan
    if target_package_id is not None:
        body["targetPackageId"] = target_package_id
    if requirements is not None:
        body["requirements"] = requirements
    if rows is not None:
        body["rows"] = rows
    if csv_text is not None:
        body["csvText"] = csv_text
    return await _request("POST", "/import-export/requirements/apply", json_body=body)


async def export_requirements_preview(
    scope_ids: Optional[list[str]] = None,
    format: str = "csv",
    output_path: Optional[str] = None,
) -> dict[str, Any]:
    """Preview requirements export without mutating the model."""
    body: dict[str, Any] = {"format": format}
    if scope_ids is not None:
        body["scopeIds"] = scope_ids
    if output_path is not None:
        body["outputPath"] = output_path
    return await _request("POST", "/requirements/export", json_body=body)


async def import_requirements_preview(
    source_path: Optional[str] = None,
    source_rows: Optional[list[dict[str, Any]]] = None,
    target_package_id: Optional[str] = None,
) -> dict[str, Any]:
    """Preview requirements import/diff without writing."""
    body: dict[str, Any] = {}
    if source_path is not None:
        body["sourcePath"] = source_path
    if source_rows is not None:
        body["sourceRows"] = source_rows
    if target_package_id is not None:
        body["targetPackageId"] = target_package_id
    return await _request("POST", "/requirements/import/preview", json_body=body)


async def get_simulation_capabilities() -> dict[str, Any]:
    """Probe Simulation Toolkit support."""
    return await get_advanced_capability("simulation")


async def list_simulation_configurations() -> dict[str, Any]:
    """List executable simulation configurations when native readback is promoted."""
    return await _request("GET", "/simulation/configurations")


async def run_simulation_preview(
    configuration_id: Optional[str] = None,
    timeout_ms: int = 30000,
) -> dict[str, Any]:
    """Preview a bounded simulation run request."""
    body: dict[str, Any] = {"timeoutMs": timeout_ms}
    if configuration_id is not None:
        body["configurationId"] = configuration_id
    return await _request("POST", "/simulation/run-preview", json_body=body)


async def run_simulation(
    configuration_id: Optional[str] = None,
    target_id: Optional[str] = None,
    timeout_ms: int = 30000,
    allow_execute: bool = False,
    async_run: bool = False,
) -> dict[str, Any]:
    """Run the guarded simulation endpoint."""
    body: dict[str, Any] = {"timeoutMs": timeout_ms, "allowExecute": allow_execute}
    if configuration_id is not None:
        body["configurationId"] = configuration_id
    if target_id is not None:
        body["targetId"] = target_id
    return await _request("POST", "/simulation/run-async" if async_run else "/simulation/run", json_body=body)


async def get_simulation_result(run_id: str) -> dict[str, Any]:
    """Fetch simulation result status."""
    return await _request("GET", f"/simulation/results/{run_id}")


async def terminate_simulation(run_id: str) -> dict[str, Any]:
    """Terminate an active simulation run."""
    return await _request("POST", f"/simulation/results/{run_id}/terminate", json_body={})


async def get_teamwork_capabilities() -> dict[str, Any]:
    """Probe Teamwork/Magic Collaboration Studio support."""
    return await get_advanced_capability("teamwork")


async def get_teamwork_project() -> dict[str, Any]:
    """Read Teamwork project metadata when native readback is promoted."""
    return await _request("GET", "/teamwork/project")


async def preview_teamwork_commit(message: Optional[str] = None) -> dict[str, Any]:
    """Preview a Teamwork commit without changing the server project."""
    body: dict[str, Any] = {}
    if message is not None:
        body["message"] = message
    return await _request("POST", "/teamwork/commit-preview", json_body=body)


async def preview_teamwork_update(message: Optional[str] = None) -> dict[str, Any]:
    """Preview a Teamwork update without changing the server project."""
    body: dict[str, Any] = {}
    if message is not None:
        body["message"] = message
    return await _request("POST", "/teamwork/update-preview", json_body=body)


async def list_teamwork_descriptors() -> dict[str, Any]:
    return await _request("GET", "/teamwork/descriptors")


async def list_teamwork_branches() -> dict[str, Any]:
    return await _request("GET", "/teamwork/branches")


async def get_teamwork_history() -> dict[str, Any]:
    return await _request("GET", "/teamwork/history")


async def get_teamwork_locks() -> dict[str, Any]:
    return await _request("GET", "/teamwork/locks")


async def get_datahub_capabilities() -> dict[str, Any]:
    """Probe DataHub/DOORS integration support."""
    return await get_advanced_capability("datahub")


async def list_datahub_sources() -> dict[str, Any]:
    """List DataHub sources when native readback is promoted."""
    return await _request("GET", "/datahub/sources")


async def preview_datahub_sync(source_id: Optional[str] = None, scope_id: Optional[str] = None) -> dict[str, Any]:
    """Preview DataHub synchronization without writing."""
    body: dict[str, Any] = {}
    if source_id is not None:
        body["sourceId"] = source_id
    if scope_id is not None:
        body["scopeId"] = scope_id
    return await _request("POST", "/datahub/sync-preview", json_body=body)


async def get_criteria_capabilities() -> dict[str, Any]:
    return await _request("GET", "/criteria/capabilities")


async def list_criteria_templates(target: Optional[str] = None) -> dict[str, Any]:
    params = {"target": target} if target is not None else None
    return await _request("GET", "/criteria/templates", params=params)


async def build_criteria_expression(
    relationship_kind: Optional[str] = None,
    direction: str = "both",
    target: Optional[str] = None,
) -> dict[str, Any]:
    body: dict[str, Any] = {"direction": direction}
    if relationship_kind is not None:
        body["relationshipKind"] = relationship_kind
    if target is not None:
        body["target"] = target
    return await _request("POST", "/criteria/build", json_body=body)


async def parse_criteria_expression(expression: dict[str, Any] | str) -> dict[str, Any]:
    return await _request("POST", "/criteria/parse", json_body={"expression": expression})


async def apply_criteria_template(
    target_id: str,
    template_id: Optional[str] = None,
    expression: Optional[dict[str, Any]] = None,
    refresh: bool = False,
) -> dict[str, Any]:
    return await _request(
        "POST",
        "/criteria/apply",
        json_body={
            "targetId": target_id,
            "templateId": template_id,
            "expression": expression,
            "refresh": refresh,
        },
    )


async def capture_criteria_template_from_diff(
    before_snapshot_id: str,
    after_snapshot_id: str,
    target_kind: Optional[str] = None,
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "beforeSnapshotId": before_snapshot_id,
        "afterSnapshotId": after_snapshot_id,
    }
    if target_kind is not None:
        body["targetKind"] = target_kind
    return await _request("POST", "/criteria/capture-template-from-diff", json_body=body)


async def get_profile_capabilities() -> dict[str, Any]:
    return await _request("GET", "/profiles/capabilities")


async def export_profile_summary() -> dict[str, Any]:
    return await _request("POST", "/profiles/export-summary", json_body={})


async def preview_profile_operation(operation: str, payload: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    route_by_operation = {
        "create-profile": "/profiles/create",
        "create-stereotype": "/profiles/stereotypes/create",
        "create-tag": "/profiles/tags/create",
        "apply-profile": "/profiles/apply",
        "set-tags": "/profiles/tags",
    }
    route = route_by_operation.get(operation)
    if route is None:
        raise ValueError(f"Unsupported profile operation: {operation}")
    method = "PUT" if operation == "set-tags" else "POST"
    return await _request(method, route, json_body=payload or {})


async def get_variant_capabilities() -> dict[str, Any]:
    """Probe native or bridge-owned variant support."""
    return await get_advanced_capability("variants")


async def analyze_variants_preview(
    configuration_ids: Optional[list[str]] = None,
    scope_ids: Optional[list[str]] = None,
) -> dict[str, Any]:
    """Preview variant/product-line analysis without writes."""
    body: dict[str, Any] = {}
    if configuration_ids is not None:
        body["configurationIds"] = configuration_ids
    if scope_ids is not None:
        body["scopeIds"] = scope_ids
    return await _request("POST", "/variants/configurations/evaluate", json_body=body)


async def install_variant_pattern_preview(payload: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    return await _request("POST", "/variants/pattern/install-preview", json_body=payload or {})


async def export_variant_configuration(payload: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    return await _request("POST", "/variants/configurations/export", json_body=payload or {})


async def get_extension_capabilities() -> dict[str, Any]:
    """Probe safety/cyber extension support."""
    return await get_advanced_capability("extensions")


async def scan_extensions(
    targets: Optional[list[str]] = None,
    scope_id: Optional[str] = None,
) -> dict[str, Any]:
    """Preview a read-only safety/cyber extension model scan."""
    body: dict[str, Any] = {}
    if targets is not None:
        body["targets"] = targets
    if scope_id is not None:
        body["scopeId"] = scope_id
    return await _request("POST", "/extensions/model-scan", json_body=body)


async def list_extension_profiles() -> dict[str, Any]:
    return await _request("GET", "/extensions/profiles")


async def install_extension_pattern_preview(payload: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    return await _request("POST", "/extensions/pattern/install-preview", json_body=payload or {})


async def get_typed_diagram_capabilities() -> dict[str, Any]:
    return await _request("GET", "/typed-diagrams/capabilities")


async def list_typed_diagrams() -> dict[str, Any]:
    return await _request("GET", "/typed-diagrams")


async def inspect_typed_diagram(diagram_id: str) -> dict[str, Any]:
    return await _request("POST", "/typed-diagrams/inspect", json_body={"diagramId": diagram_id})


async def preview_typed_diagram_operation(operation: str, payload: dict[str, Any]) -> dict[str, Any]:
    route_by_operation = {
        "sequence-message": "/typed-diagrams/sequence/messages",
        "state-transition": "/typed-diagrams/state/transitions",
        "parametric-binding": "/typed-diagrams/parametric/bindings",
        "legend-apply": "/typed-diagrams/legends/apply",
    }
    route = route_by_operation.get(operation)
    if route is None:
        raise ValueError(f"Unsupported typed diagram operation: {operation}")
    return await _request("POST", route, json_body=payload)


async def refuse_compliance_claim(
    claim_type: str,
    evidence_ids: Optional[list[str]] = None,
) -> dict[str, Any]:
    """Return the bridge's explicit refusal contract for compliance claims."""
    body: dict[str, Any] = {"claimType": claim_type}
    if evidence_ids is not None:
        body["evidenceIds"] = evidence_ids
    return await _request("POST", "/extensions/compliance-claim", json_body=body)


async def get_traceability_graph(
    root_element_ids: Optional[list[str]] = None,
    context_element_id: Optional[str] = None,
    relation_map_id: Optional[str] = None,
    relationship_types: Optional[list[str]] = None,
    direction: str = "both",
    max_depth: int = 3,
    max_nodes: int = 250,
) -> dict[str, Any]:
    """Build a read-only relationship graph from one or more root elements."""
    body: dict[str, Any] = {
        "direction": direction,
        "maxDepth": max_depth,
        "maxNodes": max_nodes,
    }
    if root_element_ids is not None:
        body["rootElementIds"] = root_element_ids
    if context_element_id is not None:
        body["contextElementId"] = context_element_id
    if relationship_types is not None:
        body["relationshipTypes"] = relationship_types

    if relation_map_id is not None:
        return await _request(
            "POST",
            f"/relation-maps/{relation_map_id}/graph",
            json_body=body,
        )
    return await _request(
        "POST",
        "/relation-maps/traceability-graph",
        json_body=body,
    )


async def get_diagram_properties(
    diagram_id: str,
    include_raw: bool = False,
    include_presentation_properties: bool = False,
    summary_only: bool = True,
    limit: int = 100,
    offset: int = 0,
) -> dict[str, Any]:
    """Dump diagram settings and a paged summary of presentation properties."""
    return await _request(
        "GET",
        f"/inspect/diagrams/{diagram_id}/properties",
        params={
            "includeRaw": include_raw,
            "includePresentationProperties": include_presentation_properties,
            "summaryOnly": summary_only,
            "limit": limit,
            "offset": offset,
        },
    )


async def get_presentation_properties(
    diagram_id: str,
    presentation_id: str,
    include_raw: bool = False,
    summary_only: bool = False,
) -> dict[str, Any]:
    """Dump full properties for one diagram presentation element."""
    return await _request(
        "GET",
        f"/inspect/diagrams/{diagram_id}/presentations/{presentation_id}/properties",
        params={"includeRaw": include_raw, "summaryOnly": summary_only},
    )

# -- Diagrams -----------------------------------------------------------------


async def list_diagrams() -> dict[str, Any]:
    """List all diagrams in the current project."""
    return await _request("GET", "/diagrams")


async def create_diagram(
    type: str,
    name: str,
    parent_id: str,
    relation_map_context_id: Optional[str] = None,
    relation_map_scope_ids: Optional[list[str]] = None,
    relation_map_element_types: Optional[list[str]] = None,
    relation_map_dependency_criteria: Optional[list[str]] = None,
    relation_map_depth: Optional[int] = None,
) -> dict[str, Any]:
    """Create a new diagram."""
    body: dict[str, Any] = {
        "type": normalize_diagram_type(type),
        "name": name,
        "parentId": parent_id,
    }
    if relation_map_context_id is not None:
        body["relationMapContextId"] = relation_map_context_id
    if relation_map_scope_ids is not None:
        body["relationMapScopeIds"] = relation_map_scope_ids
    if relation_map_element_types is not None:
        body["relationMapElementTypes"] = relation_map_element_types
    if relation_map_dependency_criteria is not None:
        body["relationMapDependencyCriteria"] = relation_map_dependency_criteria
    if relation_map_depth is not None:
        if relation_map_depth < -1 or relation_map_depth > 100:
            raise ValueError(
                "relation_map_depth must be -1 for indefinite depth, or between 0 and 100"
            )
        body["relationMapDepth"] = relation_map_depth
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


async def get_diagram_image(
    diagram_id: str,
    *,
    include_image: bool = True,
    format: str = "png",
    max_width: Optional[int] = None,
    max_height: Optional[int] = None,
    quality: int = 85,
    scale_percentage: Optional[int] = None,
) -> dict[str, Any]:
    """Export a diagram image, optionally scaling natively or transforming client-side."""
    params: dict[str, Any] = {}
    if scale_percentage is not None:
        if scale_percentage < 25 or scale_percentage > 1000:
            raise ValueError("scale_percentage must be between 25 and 1000")
        params["scalePercentage"] = scale_percentage
    result = await _request(
        "GET",
        f"/diagrams/{diagram_id}/image",
        params=params or None,
    )
    return _transform_diagram_image(
        result,
        include_image=include_image,
        format=format,
        max_width=max_width,
        max_height=max_height,
        quality=quality,
    )


async def auto_layout(diagram_id: str) -> dict[str, Any]:
    """Apply automatic layout to a diagram."""
    return await _request("POST", f"/diagrams/{diagram_id}/layout")

# -- Diagram Shape Management -------------------------------------------------


async def list_diagram_shapes(
    diagram_id: str,
    *,
    limit: int = 200,
    offset: int = 0,
    shape_type: Optional[str] = None,
    element_type: Optional[str] = None,
    parent_presentation_id: Optional[str] = None,
    include_bounds: bool = True,
    include_child_count: bool = True,
    summary_only: bool = False,
) -> dict[str, Any]:
    """List diagram shapes, optionally filtered/paged client-side."""
    result = await _request("GET", f"/diagrams/{diagram_id}/shapes")
    return _filter_diagram_shapes(
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


async def set_transition_label_presentation(
    diagram_id: str,
    *,
    presentation_ids: Optional[list[str]] = None,
    show_name: bool = True,
    show_triggers: bool = True,
    show_guard: bool = False,
    show_effect: bool = False,
    reset_labels: bool = True,
) -> dict[str, Any]:
    """Apply an intent-level transition-label display preset."""
    body: dict[str, Any] = {
        "showName": show_name,
        "showTriggers": show_triggers,
        "showGuard": show_guard,
        "showEffect": show_effect,
        "resetLabels": reset_labels,
    }
    if presentation_ids is not None:
        body["presentationIds"] = presentation_ids
    return await _request(
        "PUT",
        f"/diagrams/{diagram_id}/presentation/transition-labels",
        json_body=body,
    )


async def set_item_flow_label_presentation(
    diagram_id: str,
    *,
    presentation_ids: Optional[list[str]] = None,
    show_name: bool = False,
    show_conveyed: bool = True,
    show_item_property: bool = True,
    show_direction: bool = True,
    show_stereotype: bool = False,
    reset_labels: bool = True,
) -> dict[str, Any]:
    """Apply an intent-level item-flow label display preset."""
    body: dict[str, Any] = {
        "showName": show_name,
        "showConveyed": show_conveyed,
        "showItemProperty": show_item_property,
        "showDirection": show_direction,
        "showStereotype": show_stereotype,
        "resetLabels": reset_labels,
    }
    if presentation_ids is not None:
        body["presentationIds"] = presentation_ids
    return await _request(
        "PUT",
        f"/diagrams/{diagram_id}/presentation/item-flow-labels",
        json_body=body,
    )


async def set_allocation_compartment_presentation(
    diagram_id: str,
    *,
    presentation_ids: Optional[list[str]] = None,
    show_allocated_elements: bool = True,
    show_element_properties: bool = True,
    show_ports: bool = True,
    show_full_ports: bool = True,
    apply_allocation_naming: bool = True,
) -> dict[str, Any]:
    """Apply an intent-level SysML allocation/full-port presentation preset."""
    body: dict[str, Any] = {
        "showAllocatedElements": show_allocated_elements,
        "showElementProperties": show_element_properties,
        "showPorts": show_ports,
        "showFullPorts": show_full_ports,
        "applyAllocationNaming": apply_allocation_naming,
    }
    if presentation_ids is not None:
        body["presentationIds"] = presentation_ids
    return await _request(
        "PUT",
        f"/diagrams/{diagram_id}/presentation/allocation-compartments",
        json_body=body,
    )


async def repair_hidden_labels(
    diagram_id: str,
    *,
    presentation_ids: Optional[list[str]] = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Auto-show hidden labels using diagram-type-aware defaults."""
    body: dict[str, Any] = {"dryRun": dry_run}
    if presentation_ids is not None:
        body["presentationIds"] = presentation_ids
    return await _request(
        "PUT",
        f"/diagrams/{diagram_id}/repair/hidden-labels",
        json_body=body,
    )


async def repair_label_positions(
    diagram_id: str,
    *,
    presentation_ids: Optional[list[str]] = None,
    dry_run: bool = False,
    only_overlapping: bool = True,
    overlap_padding: int = 40,
) -> dict[str, Any]:
    """Reset label positions, optionally only for likely-overlapping path labels."""
    body: dict[str, Any] = {
        "dryRun": dry_run,
        "onlyOverlapping": only_overlapping,
        "overlapPadding": overlap_padding,
    }
    if presentation_ids is not None:
        body["presentationIds"] = presentation_ids
    return await _request(
        "PUT",
        f"/diagrams/{diagram_id}/repair/label-positions",
        json_body=body,
    )


async def repair_conveyed_item_labels(
    diagram_id: str,
    *,
    presentation_ids: Optional[list[str]] = None,
    dry_run: bool = False,
    reset_labels: bool = True,
) -> dict[str, Any]:
    """Force conveyed-item labels on eligible path elements."""
    body: dict[str, Any] = {
        "dryRun": dry_run,
        "resetLabels": reset_labels,
    }
    if presentation_ids is not None:
        body["presentationIds"] = presentation_ids
    return await _request(
        "PUT",
        f"/diagrams/{diagram_id}/repair/conveyed-item-labels",
        json_body=body,
    )


async def normalize_compartment_presets(
    diagram_id: str,
    *,
    presentation_ids: Optional[list[str]] = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Normalize compartment presets based on diagram type defaults."""
    body: dict[str, Any] = {"dryRun": dry_run}
    if presentation_ids is not None:
        body["presentationIds"] = presentation_ids
    return await _request(
        "PUT",
        f"/diagrams/{diagram_id}/repair/compartment-presets",
        json_body=body,
    )


async def prune_diagram_presentations(
    diagram_id: str,
    *,
    keep_element_ids: Optional[list[str]] = None,
    drop_element_types: Optional[list[str]] = None,
    drop_shape_types: Optional[list[str]] = None,
    exclude_element_ids: Optional[list[str]] = None,
    exclude_presentation_ids: Optional[list[str]] = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Delete unwanted diagram presentations using keep/drop rules."""
    body: dict[str, Any] = {"dryRun": dry_run}
    if keep_element_ids is not None:
        body["keepElementIds"] = keep_element_ids
    if drop_element_types is not None:
        body["dropElementTypes"] = drop_element_types
    if drop_shape_types is not None:
        body["dropShapeTypes"] = drop_shape_types
    if exclude_element_ids is not None:
        body["excludeElementIds"] = exclude_element_ids
    if exclude_presentation_ids is not None:
        body["excludePresentationIds"] = exclude_presentation_ids
    return await _request(
        "PUT",
        f"/diagrams/{diagram_id}/repair/prune-presentations",
        json_body=body,
    )


async def prune_path_decorations(
    diagram_id: str,
    *,
    presentation_ids: Optional[list[str]] = None,
    drop_child_shape_types: Optional[list[str]] = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Delete child path decorations such as association end-role labels."""
    body: dict[str, Any] = {"dryRun": dry_run}
    if presentation_ids is not None:
        body["presentationIds"] = presentation_ids
    if drop_child_shape_types is not None:
        body["dropChildShapeTypes"] = drop_child_shape_types
    return await _request(
        "PUT",
        f"/diagrams/{diagram_id}/repair/path-decorations",
        json_body=body,
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
