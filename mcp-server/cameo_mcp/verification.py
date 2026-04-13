"""Reusable visual and matrix verification helpers for the MCP layer."""

from __future__ import annotations

import base64
import binascii
import io
import re
from collections import defaultdict, deque
from itertools import combinations
from typing import Any, Mapping, Sequence

from PIL import Image, ImageChops, UnidentifiedImageError


_RELATIONSHIP_TYPE_HINTS = {
    "association",
    "dependency",
    "connector",
    "transition",
    "item flow",
    "information flow",
    "control flow",
    "object flow",
    "generalization",
    "include",
    "extend",
    "allocate",
    "satisfy",
    "verify",
    "derive",
    "refine",
    "trace",
}

_TERM_STOPWORDS = {
    "a",
    "an",
    "and",
    "display",
    "for",
    "from",
    "get",
    "of",
    "process",
    "provide",
    "query",
    "receive",
    "record",
    "select",
    "selection",
    "send",
    "show",
    "submit",
    "the",
    "to",
    "update",
    "with",
}

_DIRECTIVE_PATTERN = re.compile(r"\b(shall|must|will)\b", re.IGNORECASE)
_MEASUREMENT_PATTERN = re.compile(
    r"\b("
    r"\d+"
    r"|ms|millisecond|milliseconds|second|seconds|minute|minutes|hour|hours"
    r"|day|days|percent|%|availability|uptime|latency|response time|recover"
    r"|recovery|concurrent|throughput|capacity|max(?:imum)?|minimum|min(?:imum)?"
    r"|less than|greater than|at least|no more than|within"
    r")\b",
    re.IGNORECASE,
)


def _check(name: str, ok: bool, details: Any) -> dict[str, Any]:
    return {"name": name, "ok": ok, "details": details}


def _safe_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _normalized_text(value: Any) -> str:
    return " ".join(str(value or "").split())


def _normalized_key(value: Any) -> str:
    return _normalized_text(value).casefold()


def _element_id(payload: Mapping[str, Any]) -> str | None:
    value = payload.get("id") or payload.get("elementId") or payload.get("relationshipId")
    if value is None:
        return None
    return str(value)


def _relationship_id(payload: Mapping[str, Any]) -> str | None:
    value = payload.get("relationshipId") or payload.get("id")
    if value is None:
        return None
    return str(value)


def _element_type_name(payload: Mapping[str, Any]) -> str:
    return _normalized_key(payload.get("type") or payload.get("humanType") or payload.get("elementType"))


def _relationship_type_name(payload: Mapping[str, Any]) -> str:
    return _normalized_key(payload.get("type") or payload.get("relationshipType") or payload.get("humanType"))


def _reference_id(payload: Any) -> str | None:
    if isinstance(payload, Mapping):
        value = payload.get("id") or payload.get("elementId")
        if value is None:
            return None
        return str(value)
    if payload is None:
        return None
    return str(payload)


def _reference_name(payload: Any) -> str:
    if isinstance(payload, Mapping):
        return _normalized_text(payload.get("name") or payload.get("elementName") or "")
    return _normalized_text(payload)


def _iter_nested_tagged_values(payload: Mapping[str, Any]) -> dict[str, Any]:
    tagged: dict[str, Any] = {}
    direct_tags = payload.get("taggedValues")
    if isinstance(direct_tags, Mapping):
        for key, value in direct_tags.items():
            tagged[str(key)] = value

    for stereo in payload.get("appliedStereotypes") or ():
        if not isinstance(stereo, Mapping):
            continue
        stereo_tags = stereo.get("taggedValues")
        if not isinstance(stereo_tags, Mapping):
            continue
        for key, value in stereo_tags.items():
            tagged[str(key)] = value
    return tagged


def _extract_flow_property_direction(payload: Mapping[str, Any]) -> str | None:
    for key in ("direction",):
        value = payload.get(key)
        if value is not None:
            text = _normalized_key(value)
            if text:
                return text

    properties = payload.get("properties")
    if isinstance(properties, Mapping):
        value = properties.get("direction")
        if value is not None:
            text = _normalized_key(value)
            if text:
                return text

    tags = _iter_nested_tagged_values(payload)
    value = tags.get("direction")
    if value is None:
        return None
    text = _normalized_key(value)
    return text or None


def _flow_property_scope_key(payload: Mapping[str, Any]) -> str:
    for key in (
        "scopeId",
        "interfaceScopeId",
        "interfaceBlockId",
        "ownerId",
    ):
        value = payload.get(key)
        if value is None:
            continue
        text = _normalized_key(value)
        if text:
            return text

    for key in (
        "scopeName",
        "interfaceScopeName",
        "interfaceBlockName",
        "ownerName",
    ):
        value = payload.get(key)
        if value is None:
            continue
        text = _normalized_text(value)
        if text:
            return text.casefold()

    return ""


def _extract_requirement_id(payload: Mapping[str, Any]) -> str:
    value = payload.get("requirementId")
    if isinstance(value, str) and value.strip():
        return value.strip()

    properties = payload.get("properties")
    if isinstance(properties, Mapping):
        value = properties.get("id")
        if isinstance(value, str) and value.strip():
            return value.strip()

    tags = _iter_nested_tagged_values(payload)
    value = tags.get("id")
    if isinstance(value, str) and value.strip():
        return value.strip()

    return ""


def _extract_requirement_text(payload: Mapping[str, Any]) -> str:
    for key in ("text", "documentation"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return _normalized_text(value)

    properties = payload.get("properties")
    if isinstance(properties, Mapping):
        for key in ("text", "documentation"):
            value = properties.get(key)
            if isinstance(value, str) and value.strip():
                return _normalized_text(value)

    constraints = payload.get("constraints")
    if isinstance(constraints, Mapping):
        value = constraints.get("text")
        if isinstance(value, str) and value.strip():
            return _normalized_text(value)

    tags = _iter_nested_tagged_values(payload)
    value = tags.get("text")
    if isinstance(value, str) and value.strip():
        return _normalized_text(value)

    return ""


def _term_signature(value: Any) -> frozenset[str]:
    tokens = [
        token for token in re.findall(r"[a-z0-9]+", _normalized_key(value))
        if token and token not in _TERM_STOPWORDS
    ]
    return frozenset(tokens)


def _terms_match(left: str, right: str) -> bool:
    left_key = _normalized_key(left)
    right_key = _normalized_key(right)
    if not left_key or not right_key:
        return False
    if left_key == right_key:
        return True

    left_sig = _term_signature(left)
    right_sig = _term_signature(right)
    if not left_sig or not right_sig:
        return False
    smaller, larger = sorted((left_sig, right_sig), key=len)
    if len(smaller) == 1:
        # A singleton token subset is too broad for traceability matching and
        # creates false positives for generic nouns like "system" or "port".
        return False
    return smaller.issubset(larger)


def _build_term_matches(
    expected_terms: Sequence[str],
    actual_terms: Sequence[str],
) -> tuple[list[str], dict[str, list[str]]]:
    actual_list = [_normalized_text(term) for term in actual_terms if _normalized_text(term)]
    missing: list[str] = []
    matches: dict[str, list[str]] = {}
    for term in (_normalized_text(item) for item in expected_terms):
        if not term:
            continue
        matched = [candidate for candidate in actual_list if _terms_match(term, candidate)]
        if matched:
            matches[term] = matched
        else:
            missing.append(term)
    return missing, matches


def _dedupe_relationships(
    relationships: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    deduped: dict[str, dict[str, Any]] = {}
    anonymous: list[dict[str, Any]] = []
    for relationship in relationships:
        rel = dict(relationship)
        rel_id = _relationship_id(rel)
        if rel_id is None:
            anonymous.append(rel)
            continue
        deduped.setdefault(rel_id, rel)
    return list(deduped.values()) + anonymous


def _endpoint_ids(relationship: Mapping[str, Any], key: str) -> list[str]:
    values = relationship.get(key) or ()
    result: list[str] = []
    for value in values:
        ref_id = _reference_id(value)
        if ref_id is not None:
            result.append(ref_id)
    return result


def _shape_bounds(shape: Mapping[str, Any]) -> tuple[int, int, int, int] | None:
    bounds = shape.get("bounds")
    if not isinstance(bounds, Mapping):
        return None
    x = _safe_int(bounds.get("x"))
    y = _safe_int(bounds.get("y"))
    width = _safe_int(bounds.get("width"))
    height = _safe_int(bounds.get("height"))
    if None in {x, y, width, height} or width is None or height is None:
        return None
    if width <= 0 or height <= 0:
        return None
    return (x, y, width, height)


def _is_relationship_shape(shape: Mapping[str, Any]) -> bool:
    shape_type = str(shape.get("shapeType", "")).lower()
    if shape_type.endswith("pathelement"):
        return True
    element_type = str(shape.get("elementType", "")).lower()
    return any(token in element_type for token in _RELATIONSHIP_TYPE_HINTS)


def _is_layout_shape(shape: Mapping[str, Any]) -> bool:
    shape_type = str(shape.get("shapeType", "")).lower()
    if "label" in shape_type or "pathelement" in shape_type:
        return False
    bounds = _shape_bounds(shape)
    if bounds is None:
        return False
    return bounds[2] * bounds[3] >= 200


def analyze_diagram_image(diagram_image: Mapping[str, Any]) -> dict[str, Any]:
    image_b64 = str(diagram_image.get("image") or "")
    try:
        payload = base64.b64decode(image_b64) if image_b64 else b""
    except (ValueError, binascii.Error):
        payload = b""

    result: dict[str, Any] = {
        "byteCount": len(payload),
        "pngSignatureOk": payload.startswith(b"\x89PNG\r\n\x1a\n"),
        "reportedWidth": _safe_int(diagram_image.get("width")) or 0,
        "reportedHeight": _safe_int(diagram_image.get("height")) or 0,
        "imageWidth": 0,
        "imageHeight": 0,
        "contentBoundingBox": None,
        "contentCoverageRatio": 0.0,
    }
    if not payload:
        return result

    try:
        image = Image.open(io.BytesIO(payload)).convert("RGBA")
    except (OSError, UnidentifiedImageError):
        return result

    result["imageWidth"], result["imageHeight"] = image.size

    image_rgb = image.convert("RGB")
    background = Image.new("RGB", image_rgb.size, image_rgb.getpixel((0, 0)))
    diff = ImageChops.difference(image_rgb, background)
    diff_mask = diff.convert("L").point(lambda value: 255 if value > 0 else 0)
    bbox = diff.getbbox()
    if bbox is not None:
        left, top, right, bottom = bbox
        width = max(right - left, 0)
        height = max(bottom - top, 0)
        result["contentBoundingBox"] = {
            "x": left,
            "y": top,
            "width": width,
            "height": height,
        }
        histogram = diff_mask.histogram()
        pixel_count = histogram[255] if len(histogram) > 255 else 0
        total_pixels = max(image.size[0] * image.size[1], 1)
        result["contentCoverageRatio"] = pixel_count / total_pixels

    return result


def analyze_shape_layout(shapes: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    shape_count = len(shapes)
    relationship_shapes = [
        shape for shape in shapes
        if _is_relationship_shape(shape) and shape.get("elementId")
    ]
    bounded_shapes = [shape for shape in shapes if _shape_bounds(shape) is not None]
    layout_shapes = [shape for shape in shapes if _is_layout_shape(shape)]

    overlap_pairs = 0
    compared_pairs = 0
    max_overlap_ratio = 0.0

    grouped: dict[str | None, list[Mapping[str, Any]]] = {}
    for shape in layout_shapes:
        grouped.setdefault(shape.get("parentPresentationId"), []).append(shape)

    for siblings in grouped.values():
        for left, right in combinations(siblings, 2):
            left_bounds = _shape_bounds(left)
            right_bounds = _shape_bounds(right)
            if left_bounds is None or right_bounds is None:
                continue
            compared_pairs += 1
            lx, ly, lw, lh = left_bounds
            rx, ry, rw, rh = right_bounds
            x_overlap = max(0, min(lx + lw, rx + rw) - max(lx, rx))
            y_overlap = max(0, min(ly + lh, ry + rh) - max(ly, ry))
            intersection = x_overlap * y_overlap
            if intersection <= 0:
                continue
            min_area = min(lw * lh, rw * rh)
            if min_area <= 0:
                continue
            ratio = intersection / min_area
            overlap_pairs += 1
            max_overlap_ratio = max(max_overlap_ratio, ratio)

    return {
        "shapeCount": shape_count,
        "boundedShapeCount": len(bounded_shapes),
        "relationshipShapeCount": len(relationship_shapes),
        "relationshipElementIds": sorted(
            {
                str(shape["elementId"])
                for shape in relationship_shapes
                if shape.get("elementId")
            }
        ),
        "overlapPairs": overlap_pairs,
        "comparedPairs": compared_pairs,
        "maxOverlapRatio": max_overlap_ratio,
    }


def verify_diagram_visual(
    diagram_image: Mapping[str, Any],
    diagram_shapes: Mapping[str, Any],
    *,
    expected_element_ids: Sequence[str] | None = None,
    expected_relationship_ids: Sequence[str] | None = None,
    min_shape_count: int = 0,
    min_relationship_shape_count: int = 0,
    min_width: int = 1,
    min_height: int = 1,
    min_image_bytes: int = 1,
    min_content_coverage_ratio: float = 0.0,
    max_overlap_ratio: float = 1.0,
) -> dict[str, Any]:
    shapes = [
        shape for shape in (diagram_shapes.get("shapes") or [])
        if isinstance(shape, Mapping)
    ]
    image_metrics = analyze_diagram_image(diagram_image)
    shape_metrics = analyze_shape_layout(shapes)
    listed_element_ids = {
        str(shape.get("elementId"))
        for shape in shapes
        if shape.get("elementId")
    }
    relationship_element_ids = set(shape_metrics["relationshipElementIds"])

    expected_element_ids = [str(item) for item in (expected_element_ids or [])]
    expected_relationship_ids = [str(item) for item in (expected_relationship_ids or [])]
    missing_elements = [
        element_id for element_id in expected_element_ids
        if element_id not in listed_element_ids
    ]
    missing_relationships = [
        relationship_id for relationship_id in expected_relationship_ids
        if relationship_id not in relationship_element_ids
    ]

    checks = [
        _check("png-signature", image_metrics["pngSignatureOk"], image_metrics),
        _check(
            "image-dimensions",
            image_metrics["imageWidth"] >= min_width and image_metrics["imageHeight"] >= min_height,
            image_metrics,
        ),
        _check(
            "image-size",
            image_metrics["byteCount"] >= min_image_bytes,
            image_metrics,
        ),
        _check(
            "reported-image-dimensions",
            image_metrics["reportedWidth"] == image_metrics["imageWidth"]
            and image_metrics["reportedHeight"] == image_metrics["imageHeight"],
            image_metrics,
        ),
        _check(
            "content-coverage",
            image_metrics["contentCoverageRatio"] >= min_content_coverage_ratio,
            image_metrics,
        ),
        _check(
            "shape-count",
            shape_metrics["shapeCount"] >= min_shape_count,
            shape_metrics,
        ),
        _check(
            "relationship-shape-count",
            shape_metrics["relationshipShapeCount"] >= min_relationship_shape_count,
            shape_metrics,
        ),
        _check(
            "expected-elements-present",
            not missing_elements,
            {"missing": missing_elements, "expected": expected_element_ids},
        ),
        _check(
            "expected-relationships-present",
            not missing_relationships,
            {"missing": missing_relationships, "expected": expected_relationship_ids},
        ),
        _check(
            "shape-overlap",
            shape_metrics["maxOverlapRatio"] <= max_overlap_ratio,
            shape_metrics,
        ),
    ]

    return {
        "ok": all(check["ok"] for check in checks),
        "checks": checks,
        "image": image_metrics,
        "shapes": shape_metrics,
    }


def verify_matrix_consistency(
    matrix: Mapping[str, Any],
    *,
    expected_row_ids: Sequence[str] | None = None,
    expected_column_ids: Sequence[str] | None = None,
    expected_dependency_names: Sequence[str] | None = None,
    min_populated_cell_count: int = 0,
    min_density: float = 0.0,
) -> dict[str, Any]:
    rows = [row for row in (matrix.get("rows") or []) if isinstance(row, Mapping)]
    columns = [column for column in (matrix.get("columns") or []) if isinstance(column, Mapping)]
    populated_cells = [
        cell for cell in (matrix.get("populatedCells") or [])
        if isinstance(cell, Mapping)
    ]

    row_ids = {str(row.get("id")) for row in rows if row.get("id")}
    column_ids = {str(column.get("id")) for column in columns if column.get("id")}
    dependency_names = {
        str(dependency.get("name") or dependency.get("dependencyName"))
        for cell in populated_cells
        for dependency in (cell.get("dependencies") or [])
        if isinstance(dependency, Mapping) and (dependency.get("name") or dependency.get("dependencyName"))
    }

    row_count = _safe_int(matrix.get("rowCount")) or len(rows)
    column_count = _safe_int(matrix.get("columnCount")) or len(columns)
    populated_cell_count = _safe_int(matrix.get("populatedCellCount")) or len(populated_cells)
    total_cells = row_count * column_count
    density = populated_cell_count / total_cells if total_cells > 0 else 0.0

    expected_row_ids = [str(item) for item in (expected_row_ids or [])]
    expected_column_ids = [str(item) for item in (expected_column_ids or [])]
    expected_dependency_names = [str(item) for item in (expected_dependency_names or [])]

    missing_rows = [row_id for row_id in expected_row_ids if row_id not in row_ids]
    missing_columns = [column_id for column_id in expected_column_ids if column_id not in column_ids]
    missing_dependencies = [
        dependency for dependency in expected_dependency_names
        if dependency not in dependency_names
    ]

    metrics = {
        "rowCount": row_count,
        "columnCount": column_count,
        "populatedCellCount": populated_cell_count,
        "actualRowCount": len(rows),
        "actualColumnCount": len(columns),
        "actualPopulatedCellCount": len(populated_cells),
        "density": density,
        "dependencyNames": sorted(dependency_names),
    }
    checks = [
        _check(
            "payload-counts-consistent",
            row_count == len(rows)
            and column_count == len(columns)
            and populated_cell_count == len(populated_cells),
            metrics,
        ),
        _check(
            "populated-cell-count",
            populated_cell_count >= min_populated_cell_count,
            metrics,
        ),
        _check(
            "density",
            density >= min_density,
            metrics,
        ),
        _check(
            "expected-rows-present",
            not missing_rows,
            {"missing": missing_rows, "expected": expected_row_ids},
        ),
        _check(
            "expected-columns-present",
            not missing_columns,
            {"missing": missing_columns, "expected": expected_column_ids},
        ),
        _check(
            "expected-dependencies-present",
            not missing_dependencies,
            {"missing": missing_dependencies, "expected": expected_dependency_names},
        ),
    ]

    return {
        "ok": all(check["ok"] for check in checks),
        "checks": checks,
        "metrics": metrics,
    }


def extract_activity_trace_terms(
    elements: Sequence[Mapping[str, Any]],
    relationships: Sequence[Mapping[str, Any]],
) -> list[str]:
    terms: list[str] = []
    for element in elements:
        element_type = _element_type_name(element)
        if any(token in element_type for token in ("action", "objectnode", "pin", "parameter")):
            name = _normalized_text(element.get("name") or element.get("elementName") or "")
            if name:
                terms.append(name)

    for relationship in relationships:
        relationship_type = _relationship_type_name(relationship)
        if "objectflow" in relationship_type or "informationflow" in relationship_type:
            name = _normalized_text(relationship.get("name") or "")
            if name:
                terms.append(name)
            item_property = relationship.get("itemProperty")
            item_name = _reference_name(item_property)
            if item_name:
                terms.append(item_name)
            for conveyed in relationship.get("conveyed") or ():
                conveyed_name = _reference_name(conveyed)
                if conveyed_name:
                    terms.append(conveyed_name)
    return sorted({term for term in terms if term})


def extract_ibd_trace_terms(
    elements: Sequence[Mapping[str, Any]],
    relationships: Sequence[Mapping[str, Any]],
) -> list[str]:
    terms: list[str] = []
    for element in elements:
        element_type = _element_type_name(element)
        if any(token in element_type for token in ("port", "property", "interfaceblock", "interface block")):
            name = _normalized_text(element.get("name") or element.get("elementName") or "")
            if name:
                terms.append(name)

    for relationship in relationships:
        relationship_type = _relationship_type_name(relationship)
        if any(token in relationship_type for token in ("connector", "informationflow", "itemflow")):
            name = _normalized_text(relationship.get("name") or "")
            if name:
                terms.append(name)
            item_name = _reference_name(relationship.get("itemProperty"))
            if item_name:
                terms.append(item_name)
            for conveyed in relationship.get("conveyed") or ():
                conveyed_name = _reference_name(conveyed)
                if conveyed_name:
                    terms.append(conveyed_name)
    return sorted({term for term in terms if term})


def verify_activity_flow_semantics(
    elements: Sequence[Mapping[str, Any]],
    relationships: Sequence[Mapping[str, Any]],
    *,
    shapes: Sequence[Mapping[str, Any]] | None = None,
    max_partition_depth: int = 1,
    allow_stereotype_partition_labels: bool = False,
) -> dict[str, Any]:
    elements_by_id = {
        element_id: dict(element)
        for element in elements
        if (element_id := _element_id(element)) is not None
    }
    flow_relationships = [
        rel for rel in _dedupe_relationships(relationships)
        if any(token in _relationship_type_name(rel) for token in ("controlflow", "objectflow"))
    ]

    initial_ids = {
        element_id for element_id, element in elements_by_id.items()
        if "initial" in _element_type_name(element)
    }
    final_ids = {
        element_id for element_id, element in elements_by_id.items()
        if "final" in _element_type_name(element)
    }
    action_ids = {
        element_id for element_id, element in elements_by_id.items()
        if "action" in _element_type_name(element)
    }

    adjacency: dict[str, set[str]] = defaultdict(set)
    reverse_adjacency: dict[str, set[str]] = defaultdict(set)
    touched_node_ids: set[str] = set()
    for relationship in flow_relationships:
        sources = _endpoint_ids(relationship, "sources")
        targets = _endpoint_ids(relationship, "targets")
        if not sources or not targets:
            continue
        for source_id in sources:
            for target_id in targets:
                adjacency[source_id].add(target_id)
                reverse_adjacency[target_id].add(source_id)
                touched_node_ids.add(source_id)
                touched_node_ids.add(target_id)

    isolated_actions = sorted(
        action_id for action_id in action_ids
        if not adjacency.get(action_id) and not reverse_adjacency.get(action_id)
    )

    reachable_from_initial: set[str] = set()
    if initial_ids:
        queue = deque(sorted(initial_ids))
        reachable_from_initial.update(initial_ids)
        while queue:
            current = queue.popleft()
            for neighbor in adjacency.get(current, ()):
                if neighbor in reachable_from_initial:
                    continue
                reachable_from_initial.add(neighbor)
                queue.append(neighbor)

    unreachable_actions = sorted(action_ids - reachable_from_initial) if initial_ids else sorted(action_ids)
    reachable_finals = sorted(final_ids & reachable_from_initial)

    component_nodes = touched_node_ids | initial_ids | final_ids | action_ids
    undirected: dict[str, set[str]] = defaultdict(set)
    for source_id, targets in adjacency.items():
        for target_id in targets:
            undirected[source_id].add(target_id)
            undirected[target_id].add(source_id)

    component_sizes: list[int] = []
    remaining = set(component_nodes)
    while remaining:
        seed = remaining.pop()
        queue = deque([seed])
        size = 1
        while queue:
            current = queue.popleft()
            for neighbor in undirected.get(current, ()):
                if neighbor not in remaining:
                    continue
                remaining.remove(neighbor)
                size += 1
                queue.append(neighbor)
        component_sizes.append(size)

    partition_details: dict[str, Any] = {
        "count": 0,
        "maxDepth": 0,
        "stereotypeStyleNames": [],
        "containerOnlyPartitions": [],
    }
    partition_ok = True
    if shapes:
        partition_shapes = [
            shape for shape in shapes
            if "activitypartition" in _element_type_name(shape)
        ]
        partition_details["count"] = len(partition_shapes)
        by_presentation = {
            str(shape.get("presentationId")): shape
            for shape in partition_shapes
            if shape.get("presentationId")
        }
        shape_by_parent: dict[str | None, list[Mapping[str, Any]]] = defaultdict(list)
        for shape in shapes:
            parent_key = shape.get("parentPresentationId")
            if isinstance(parent_key, str):
                shape_by_parent[parent_key].append(shape)
            else:
                shape_by_parent[None].append(shape)

        for partition in partition_shapes:
            depth = 0
            parent_presentation = partition.get("parentPresentationId")
            while isinstance(parent_presentation, str) and parent_presentation in by_presentation:
                depth += 1
                parent_presentation = by_presentation[parent_presentation].get("parentPresentationId")
            partition_details["maxDepth"] = max(partition_details["maxDepth"], depth)

            label = _normalized_text(
                partition.get("elementName")
                or elements_by_id.get(str(partition.get("elementId")), {}).get("name")
                or ""
            )
            if not allow_stereotype_partition_labels and label.startswith("«") and label.endswith("»"):
                partition_details["stereotypeStyleNames"].append(label)

            children = shape_by_parent.get(partition.get("presentationId"), [])
            if children:
                child_partition_count = sum(
                    1 for child in children if "activitypartition" in _element_type_name(child)
                )
                child_behavior_count = sum(
                    1 for child in children
                    if "activitypartition" not in _element_type_name(child)
                )
                if child_partition_count > 0 and child_behavior_count == 0:
                    partition_details["containerOnlyPartitions"].append(
                        _normalized_text(label or str(partition.get("elementId") or ""))
                    )

        partition_ok = (
            partition_details["maxDepth"] <= max_partition_depth
            and not partition_details["stereotypeStyleNames"]
            and not partition_details["containerOnlyPartitions"]
        )

    metrics = {
        "elementCount": len(elements_by_id),
        "flowRelationshipCount": len(flow_relationships),
        "initialNodeIds": sorted(initial_ids),
        "finalNodeIds": sorted(final_ids),
        "actionIds": sorted(action_ids),
        "isolatedActionIds": isolated_actions,
        "unreachableActionIds": unreachable_actions,
        "reachableFinalIds": reachable_finals,
        "flowComponentCount": len(component_sizes),
        "flowComponentSizes": sorted(component_sizes, reverse=True),
        "partitionDetails": partition_details,
    }
    checks = [
        _check("initial-node-present", bool(initial_ids), metrics),
        _check("final-node-present", bool(final_ids), metrics),
        _check("actions-connected", not isolated_actions, metrics),
        _check(
            "actions-reachable-from-initial",
            bool(initial_ids) and not unreachable_actions,
            metrics,
        ),
        _check("final-reachable", bool(reachable_finals), metrics),
        _check("single-flow-component", len(component_sizes) <= 1, metrics),
        _check("partition-sanity", partition_ok, metrics),
    ]

    return {
        "ok": all(check["ok"] for check in checks),
        "checks": checks,
        "metrics": metrics,
    }


def verify_port_boundary_consistency(
    interface_blocks: Sequence[Mapping[str, Any]],
    flow_properties: Sequence[Mapping[str, Any]],
    *,
    allow_shared_flow_property_names: Sequence[str] | None = None,
) -> dict[str, Any]:
    interface_names = {
        str(interface.get("id") or ""): _normalized_text(interface.get("name") or "")
        for interface in interface_blocks
        if interface.get("id")
    }
    interface_scope_labels = {
        _normalized_key(interface_id): interface_name
        for interface_id, interface_name in interface_names.items()
        if _normalized_key(interface_id)
    }
    allowed = {_normalized_key(name) for name in (allow_shared_flow_property_names or ()) if _normalized_key(name)}

    duplicate_map: dict[str, list[str]] = defaultdict(list)
    direction_map: dict[tuple[str, str], set[str]] = defaultdict(set)
    unnamed_property_ids: list[str] = []
    orphan_property_ids: list[str] = []
    missing_direction_ids: list[str] = []

    for flow_property in flow_properties:
        flow_property_id = _element_id(flow_property) or ""
        owner_id = str(flow_property.get("ownerId") or "")
        if owner_id not in interface_names:
            orphan_property_ids.append(flow_property_id)

        name = _normalized_text(flow_property.get("name") or "")
        if not name:
            unnamed_property_ids.append(flow_property_id)
            continue

        normalized_name = _normalized_key(name)
        duplicate_map[normalized_name].append(owner_id)

        direction = _extract_flow_property_direction(flow_property)
        if direction:
            scope_key = _flow_property_scope_key(flow_property)
            direction_map[(scope_key, normalized_name)].add(direction)
        else:
            missing_direction_ids.append(flow_property_id)

    duplicate_details = {
        name: sorted(
            {
                interface_names.get(owner_id) or owner_id
                for owner_id in owners
                if owner_id
            }
        )
        for name, owners in duplicate_map.items()
        if len(set(owners)) > 1 and name not in allowed
    }
    direction_conflicts: dict[str, dict[str, list[str]]] = defaultdict(dict)
    for (scope_key, name), directions in direction_map.items():
        if len(directions) <= 1:
            continue
        scope_name = interface_scope_labels.get(scope_key, "") or scope_key
        direction_conflicts[scope_name][name] = sorted(directions)

    metrics = {
        "interfaceCount": len(interface_blocks),
        "flowPropertyCount": len(flow_properties),
        "duplicateFlowProperties": duplicate_details,
        "directionConflicts": dict(direction_conflicts),
        "unnamedPropertyIds": sorted(item for item in unnamed_property_ids if item),
        "orphanPropertyIds": sorted(item for item in orphan_property_ids if item),
        "missingDirectionIds": sorted(item for item in missing_direction_ids if item),
    }
    checks = [
        _check("interfaces-present", bool(interface_blocks), metrics),
        _check("flow-properties-present", bool(flow_properties), metrics),
        _check("owner-consistency", not metrics["orphanPropertyIds"], metrics),
        _check("duplicate-flow-properties", not duplicate_details, metrics),
        _check("direction-conflicts", not direction_conflicts, metrics),
        _check("named-flow-properties", not metrics["unnamedPropertyIds"], metrics),
        _check("flow-property-directions-present", not metrics["missingDirectionIds"], metrics),
    ]
    return {
        "ok": all(check["ok"] for check in checks),
        "checks": checks,
        "metrics": metrics,
    }


def verify_requirement_quality(
    requirements: Sequence[Mapping[str, Any]],
    *,
    require_id: bool = True,
    require_measurement: bool = True,
    min_text_length: int = 20,
) -> dict[str, Any]:
    missing_id_ids: list[str] = []
    blank_text_ids: list[str] = []
    weak_text_ids: list[str] = []
    evaluated: list[dict[str, Any]] = []

    for requirement in requirements:
        element_id = _element_id(requirement) or ""
        requirement_id = _extract_requirement_id(requirement)
        text = _extract_requirement_text(requirement)
        measurable = bool(_DIRECTIVE_PATTERN.search(text)) and bool(_MEASUREMENT_PATTERN.search(text))
        long_enough = len(text) >= min_text_length

        if require_id and not requirement_id:
            missing_id_ids.append(element_id)
        if not text:
            blank_text_ids.append(element_id)
        elif require_measurement and not (measurable and long_enough):
            weak_text_ids.append(element_id)

        evaluated.append(
            {
                "elementId": element_id,
                "name": _normalized_text(requirement.get("name") or ""),
                "requirementId": requirement_id,
                "text": text,
                "hasId": bool(requirement_id),
                "hasText": bool(text),
                "isMeasurable": measurable and long_enough,
            }
        )

    metrics = {
        "requirementCount": len(requirements),
        "missingIdIds": sorted(item for item in missing_id_ids if item),
        "blankTextIds": sorted(item for item in blank_text_ids if item),
        "weakTextIds": sorted(item for item in weak_text_ids if item),
        "evaluatedRequirements": evaluated,
    }
    checks = [
        _check("requirements-present", bool(requirements), metrics),
        _check("requirement-ids-present", not metrics["missingIdIds"], metrics),
        _check("requirement-text-present", not metrics["blankTextIds"], metrics),
        _check("requirement-text-measurable", not metrics["weakTextIds"], metrics),
    ]
    return {
        "ok": all(check["ok"] for check in checks),
        "checks": checks,
        "metrics": metrics,
    }


def verify_cross_diagram_traceability(
    *,
    activity_terms: Sequence[str] | None = None,
    port_terms: Sequence[str] | None = None,
    ibd_terms: Sequence[str] | None = None,
    requirement_links: Mapping[str, Sequence[str]] | None = None,
    requirement_ids: Sequence[str] | None = None,
    architecture_element_ids: Sequence[str] | None = None,
) -> dict[str, Any]:
    activity_terms = [_normalized_text(term) for term in (activity_terms or ()) if _normalized_text(term)]
    port_terms = [_normalized_text(term) for term in (port_terms or ()) if _normalized_text(term)]
    ibd_terms = [_normalized_text(term) for term in (ibd_terms or ()) if _normalized_text(term)]
    requirement_ids = [str(item) for item in (requirement_ids or ())]
    architecture_ids = {str(item) for item in (architecture_element_ids or ())}
    requirement_links = {
        str(key): [str(value) for value in values]
        for key, values in (requirement_links or {}).items()
    }

    missing_port_terms, matched_port_terms = _build_term_matches(port_terms, activity_terms)
    missing_ibd_terms, matched_ibd_terms = _build_term_matches(ibd_terms, activity_terms)
    missing_requirement_traces = sorted(
        requirement_id
        for requirement_id in requirement_ids
        if architecture_ids and not (architecture_ids & set(requirement_links.get(requirement_id, ())))
    )

    metrics = {
        "activityTermCount": len(activity_terms),
        "portTermCount": len(port_terms),
        "ibdTermCount": len(ibd_terms),
        "matchedPortTerms": matched_port_terms,
        "matchedIbdTerms": matched_ibd_terms,
        "missingPortTerms": missing_port_terms,
        "missingIbdTerms": missing_ibd_terms,
        "missingRequirementTraceIds": missing_requirement_traces,
    }

    checks = []
    if port_terms:
        checks.append(
            _check("activity-to-port-coverage", not missing_port_terms, metrics)
        )
    if ibd_terms:
        checks.append(
            _check("activity-to-ibd-coverage", not missing_ibd_terms, metrics)
        )
    if requirement_ids and architecture_ids:
        checks.append(
            _check(
                "requirements-to-architecture-trace",
                not missing_requirement_traces,
                metrics,
            )
        )
    if not checks:
        checks.append(
            _check(
                "traceability-inputs-present",
                False,
                {"message": "Provide at least one artifact pairing to validate."},
            )
        )

    return {
        "ok": all(check["ok"] for check in checks),
        "checks": checks,
        "metrics": metrics,
    }
