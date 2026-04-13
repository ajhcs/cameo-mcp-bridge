"""Async semantic validation helpers for the MCP layer.

This module keeps bridge read orchestration separate from the reusable
verification heuristics. It prefers existing REST reads and uses native bridge
helpers where the current REST surface does not expose enough structure, such
as owned flow properties on interface blocks.
"""

from __future__ import annotations

import asyncio
from typing import Any, Mapping, Sequence

from cameo_mcp import client as default_bridge_client
from cameo_mcp import verification


async def _read_interface_flow_properties(
    interface_block_ids: Sequence[str],
    bridge: Any,
) -> dict[str, Any]:
    reader = getattr(bridge, "get_interface_flow_properties", None)
    if reader is None:
        raise RuntimeError(
            "Bridge client does not implement get_interface_flow_properties(interface_block_ids)."
        )

    payload = await reader(interface_block_ids)
    if not isinstance(payload, Mapping):
        raise RuntimeError(
            "Bridge returned a non-object payload from get_interface_flow_properties: "
            f"{payload!r}"
        )
    return dict(payload)


def _relationship_signature(relationship: Mapping[str, Any]) -> tuple[Any, ...]:
    return (
        relationship.get("relationshipId"),
        relationship.get("type") or relationship.get("relationshipType"),
        tuple(
            str(item.get("id") or "")
            for item in relationship.get("sources") or ()
            if isinstance(item, Mapping)
        ),
        tuple(
            str(item.get("id") or "")
            for item in relationship.get("targets") or ()
            if isinstance(item, Mapping)
        ),
        tuple(
            str(item.get("id") or "")
            for item in relationship.get("relatedElements") or ()
            if isinstance(item, Mapping)
        ),
    )


def _flatten_relationship_responses(
    responses: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    deduped: dict[tuple[Any, ...], dict[str, Any]] = {}
    for response in responses:
        for bucket in ("outgoing", "incoming", "undirected"):
            for relationship in response.get(bucket) or ():
                if not isinstance(relationship, Mapping):
                    continue
                key = _relationship_signature(relationship)
                deduped.setdefault(key, dict(relationship))
    return list(deduped.values())


async def _gather_diagram_snapshot(diagram_id: str, bridge: Any) -> dict[str, Any]:
    diagram_shapes = await bridge.list_diagram_shapes(diagram_id)
    shapes = [
        shape for shape in (diagram_shapes.get("shapes") or ())
        if isinstance(shape, Mapping)
    ]
    element_ids = sorted(
        {
            str(shape.get("elementId"))
            for shape in shapes
            if shape.get("elementId")
        }
    )

    elements = await asyncio.gather(
        *(bridge.get_element(element_id) for element_id in element_ids)
    ) if element_ids else []
    relationship_responses = await asyncio.gather(
        *(bridge.get_relationships(element_id) for element_id in element_ids)
    ) if element_ids else []
    relationships = _flatten_relationship_responses(relationship_responses)

    return {
        "diagramId": diagram_id,
        "diagramShapes": diagram_shapes,
        "elements": list(elements),
        "relationships": relationships,
    }


def _merge_requirement_payload(
    element: Mapping[str, Any],
    specification: Mapping[str, Any],
) -> dict[str, Any]:
    merged = dict(element)
    merged["specification"] = dict(specification)
    for key in ("name", "type", "documentation", "properties", "appliedStereotypes", "constraints"):
        if key in specification:
            merged[key] = specification[key]
    return merged


def _related_requirement_architecture_ids(
    requirement_id: str,
    response: Mapping[str, Any],
) -> list[str]:
    related_ids: set[str] = set()
    for bucket in ("outgoing", "incoming"):
        for relationship in response.get(bucket) or ():
            if not isinstance(relationship, Mapping):
                continue
            for endpoint_key in ("sources", "targets"):
                for endpoint in relationship.get(endpoint_key) or ():
                    if not isinstance(endpoint, Mapping):
                        continue
                    endpoint_id = endpoint.get("id")
                    if endpoint_id and str(endpoint_id) != requirement_id:
                        related_ids.add(str(endpoint_id))
    for relationship in response.get("undirected") or ():
        if not isinstance(relationship, Mapping):
            continue
        for endpoint in relationship.get("relatedElements") or ():
            if not isinstance(endpoint, Mapping):
                continue
            endpoint_id = endpoint.get("id")
            if endpoint_id and str(endpoint_id) != requirement_id:
                related_ids.add(str(endpoint_id))
    return sorted(related_ids)


async def verify_activity_flow_semantics_for_diagram(
    diagram_id: str,
    *,
    max_partition_depth: int = 1,
    allow_stereotype_partition_labels: bool = False,
    bridge: Any = default_bridge_client,
) -> dict[str, Any]:
    snapshot = await _gather_diagram_snapshot(diagram_id, bridge)
    result = verification.verify_activity_flow_semantics(
        snapshot["elements"],
        snapshot["relationships"],
        shapes=snapshot["diagramShapes"].get("shapes") or (),
        max_partition_depth=max_partition_depth,
        allow_stereotype_partition_labels=allow_stereotype_partition_labels,
    )
    result["diagramId"] = diagram_id
    result["elements"] = snapshot["elements"]
    result["relationships"] = snapshot["relationships"]
    result["diagramShapes"] = snapshot["diagramShapes"]
    return result


async def verify_port_boundary_consistency_for_interfaces(
    interface_block_ids: Sequence[str],
    *,
    allow_shared_flow_property_names: Sequence[str] | None = None,
    bridge: Any = default_bridge_client,
) -> dict[str, Any]:
    payload = await _read_interface_flow_properties(interface_block_ids, bridge)
    interface_blocks = [
        item for item in (payload.get("interfaceBlocks") or ())
        if isinstance(item, Mapping)
    ]
    flow_properties = [
        item for item in (payload.get("flowProperties") or ())
        if isinstance(item, Mapping)
    ]
    result = verification.verify_port_boundary_consistency(
        interface_blocks,
        flow_properties,
        allow_shared_flow_property_names=allow_shared_flow_property_names,
    )
    result["interfaceBlocks"] = interface_blocks
    result["flowProperties"] = flow_properties
    return result


async def verify_requirement_quality_for_ids(
    requirement_ids: Sequence[str],
    *,
    require_id: bool = True,
    require_measurement: bool = True,
    min_text_length: int = 20,
    bridge: Any = default_bridge_client,
) -> dict[str, Any]:
    elements = await asyncio.gather(
        *(bridge.get_element(requirement_id) for requirement_id in requirement_ids)
    ) if requirement_ids else []
    specifications = await asyncio.gather(
        *(bridge.get_specification(requirement_id) for requirement_id in requirement_ids)
    ) if requirement_ids else []
    requirements = [
        _merge_requirement_payload(element, specification)
        for element, specification in zip(elements, specifications)
    ]
    result = verification.verify_requirement_quality(
        requirements,
        require_id=require_id,
        require_measurement=require_measurement,
        min_text_length=min_text_length,
    )
    result["requirements"] = requirements
    return result


async def verify_cross_diagram_traceability(
    *,
    activity_diagram_id: str | None = None,
    interface_block_ids: Sequence[str] | None = None,
    ibd_diagram_id: str | None = None,
    requirement_ids: Sequence[str] | None = None,
    architecture_element_ids: Sequence[str] | None = None,
    bridge: Any = default_bridge_client,
) -> dict[str, Any]:
    activity_terms: list[str] = []
    port_terms: list[str] = []
    ibd_terms: list[str] = []
    requirement_links: dict[str, list[str]] = {}

    if activity_diagram_id:
        activity_snapshot = await _gather_diagram_snapshot(activity_diagram_id, bridge)
        activity_terms = verification.extract_activity_trace_terms(
            activity_snapshot["elements"],
            activity_snapshot["relationships"],
        )
    if interface_block_ids:
        interface_payload = await _read_interface_flow_properties(interface_block_ids, bridge)
        port_terms = sorted(
            {
                str(flow_property.get("name")).strip()
                for flow_property in (interface_payload.get("flowProperties") or ())
                if isinstance(flow_property, Mapping) and str(flow_property.get("name") or "").strip()
            }
        )
    if ibd_diagram_id:
        ibd_snapshot = await _gather_diagram_snapshot(ibd_diagram_id, bridge)
        ibd_terms = verification.extract_ibd_trace_terms(
            ibd_snapshot["elements"],
            ibd_snapshot["relationships"],
        )
    if requirement_ids:
        relationship_responses = await asyncio.gather(
            *(bridge.get_relationships(requirement_id) for requirement_id in requirement_ids)
        )
        requirement_links = {
            str(requirement_id): _related_requirement_architecture_ids(
                str(requirement_id),
                response,
            )
            for requirement_id, response in zip(requirement_ids, relationship_responses)
        }

    result = verification.verify_cross_diagram_traceability(
        activity_terms=activity_terms,
        port_terms=port_terms,
        ibd_terms=ibd_terms,
        requirement_links=requirement_links,
        requirement_ids=requirement_ids,
        architecture_element_ids=architecture_element_ids,
    )
    result["activityTerms"] = activity_terms
    result["portTerms"] = port_terms
    result["ibdTerms"] = ibd_terms
    result["requirementLinks"] = requirement_links
    return result
