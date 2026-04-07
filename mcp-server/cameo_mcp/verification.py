"""Reusable visual and matrix verification helpers for the MCP layer."""

from __future__ import annotations

import base64
import binascii
import io
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


def _check(name: str, ok: bool, details: Any) -> dict[str, Any]:
    return {"name": name, "ok": ok, "details": details}


def _safe_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


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
