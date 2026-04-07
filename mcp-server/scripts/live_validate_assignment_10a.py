from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve()
MCP_SERVER_DIR = HERE.parents[1]
if str(MCP_SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(MCP_SERVER_DIR))

from cameo_mcp import client, server as mcp_server  # noqa: E402


class ValidationError(RuntimeError):
    pass


def _append_check(report: dict[str, Any], name: str, ok: bool, details: Any) -> None:
    report.setdefault("checks", []).append(
        {
            "name": name,
            "ok": ok,
            "details": details,
        }
    )


def _expect(condition: bool, message: str) -> None:
    if not condition:
        raise ValidationError(message)


async def _create_element(
    element_type: str,
    name: str,
    parent_id: str,
    report: dict[str, Any],
    **kwargs: Any,
) -> dict[str, Any]:
    result = await client.create_element(
        type=element_type,
        name=name,
        parent_id=parent_id,
        **kwargs,
    )
    element = result["element"]
    report.setdefault("artifacts", {})[name] = element
    return element


async def _execute_macro(script: str) -> dict[str, Any]:
    result = await client.execute_macro(script)
    if not result.get("success"):
        raise ValidationError(
            "Macro failed: "
            + str(result.get("error") or "unknown error")
            + "; output="
            + str(result.get("output") or "")
        )
    return result


def _parse_probe_output(output: str) -> dict[str, Any]:
    parsed: dict[str, Any] = {}
    multi_keys = {"stereotype", "connector", "conveyed"}

    for raw_line in output.splitlines():
        line = raw_line.strip()
        if not line or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key in multi_keys:
            parsed.setdefault(key, []).append(value)
        else:
            parsed[key] = value
    return parsed


def _applied_stereotype_names(specification: dict[str, Any]) -> list[str]:
    applied = specification.get("appliedStereotypes") or []
    names: list[str] = []
    for entry in applied:
        name = entry.get("stereotype")
        if isinstance(name, str) and name:
            names.append(name)
    return names


def _stereotype_tag_value(
    specification: dict[str, Any],
    stereotype_name: str,
    tag_name: str,
) -> Any:
    for entry in specification.get("appliedStereotypes") or []:
        if str(entry.get("stereotype", "")).lower() != stereotype_name.lower():
            continue
        tagged_values = entry.get("taggedValues") or {}
        if isinstance(tagged_values, dict):
            return tagged_values.get(tag_name)
    return None


def _tag_name(value: Any) -> str:
    if isinstance(value, dict):
        name = value.get("name")
        return name if isinstance(name, str) else ""
    return value if isinstance(value, str) else ""


async def _resolve_sysml_profile_name(report: dict[str, Any]) -> str:
    profiles = await client.query_elements(type="Profile", recursive=True, limit=1000, view="compact")
    discovered = [
        element.get("name", "")
        for element in profiles.get("elements", [])
        if element.get("name")
    ]
    report["availableProfiles"] = discovered

    preferred = ["SysML", "SysML Profile", "sysml", "sysml profile"]
    candidates: list[str] = []
    seen: set[str] = set()

    for item in preferred + discovered:
        normalized = item.strip()
        if not normalized:
            continue
        key = normalized.lower()
        if key in seen or "sysml" not in key:
            continue
        seen.add(key)
        candidates.append(normalized)

    _expect(bool(candidates), "Could not discover a SysML profile in the open project")
    report["sysmlProfileCandidates"] = candidates
    return candidates[0]


def _flow_property_probe_macro(flow_property_id: str) -> str:
    flow_property_literal = json.dumps(flow_property_id)
    return f"""
import com.nomagic.uml2.ext.jmi.helpers.StereotypesHelper
def flowProperty = project.getElementByID({flow_property_literal})
println("elementId=" + (flowProperty?.getID() ?: ""))
println("typeId=" + (flowProperty?.getType()?.getID() ?: ""))
for (st in StereotypesHelper.getStereotypes(flowProperty) ?: []) {{
    println("stereotype=" + (st?.getName() ?: ""))
}}
def stereo = StereotypesHelper.getAppliedStereotypeByString(flowProperty, "FlowProperty")
def direction = stereo ? StereotypesHelper.getStereotypePropertyFirst(flowProperty, stereo, "direction") : null
println("direction=" + (direction?.getName() ?: ""))
return "ok"
""".strip()


def _item_flow_probe_macro(item_flow_id: str) -> str:
    item_flow_literal = json.dumps(item_flow_id)
    return f"""
import com.nomagic.uml2.ext.jmi.helpers.StereotypesHelper
def infoFlow = project.getElementByID({item_flow_literal})
println("elementId=" + (infoFlow?.getID() ?: ""))
println("ownerId=" + (infoFlow?.getOwner()?.getID() ?: ""))
println("humanType=" + (infoFlow?.getHumanType() ?: ""))
for (st in StereotypesHelper.getStereotypes(infoFlow) ?: []) {{
    println("stereotype=" + (st?.getName() ?: ""))
}}
for (item in infoFlow?.getConveyed() ?: []) {{
    println("conveyed=" + (item?.getID() ?: ""))
}}
for (connector in infoFlow?.getRealizingConnector() ?: []) {{
    println("connector=" + (connector?.getID() ?: ""))
}}
def itemFlow = StereotypesHelper.getAppliedStereotypeByString(infoFlow, "ItemFlow")
def itemProperty = itemFlow ? StereotypesHelper.getStereotypePropertyFirst(infoFlow, itemFlow, "itemProperty") : null
println("itemPropertyId=" + (itemProperty?.getID() ?: ""))
println("sourceIds=" + ((infoFlow?.getInformationSource() ?: []).collect {{ it.getID() }}.join(",") ?: ""))
println("targetIds=" + ((infoFlow?.getInformationTarget() ?: []).collect {{ it.getID() }}.join(",") ?: ""))
return "ok"
""".strip()


async def run_validation(keep_artifacts: bool) -> dict[str, Any]:
    report: dict[str, Any] = {
        "runId": f"live-assignment-10a-{int(time.time())}",
        "checks": [],
        "artifacts": {},
        "cleanup": {
            "attempted": False,
            "deleted": False,
        },
    }
    validation_package_id: str | None = None

    try:
        status = await client.status()
        capabilities = await client.get_capabilities()
        capability_names = {
            endpoint.get("name")
            for endpoint in capabilities.get("capabilities", {}).get("endpoints", [])
            if isinstance(endpoint, dict)
        }
        required_capabilities = {
            "cameo_create_relationship",
            "cameo_create_diagram",
            "cameo_add_to_diagram",
            "cameo_add_diagram_paths",
            "cameo_set_tagged_values",
            "cameo_set_specification",
        }
        _expect(status.get("healthy") is True, "Bridge status is not healthy")
        _expect(
            status.get("compatibility", {}).get("clientCompatible") is True,
            "Bridge compatibility handshake failed",
        )
        _expect(
            required_capabilities.issubset(capability_names),
            "Running bridge does not expose the assignment workflow endpoints",
        )
        _append_check(
            report,
            "status-and-capabilities",
            True,
            {
                "pluginVersion": status.get("pluginVersion"),
                "capabilityCount": capabilities.get("capabilities", {}).get("count"),
                "requiredCapabilities": sorted(required_capabilities),
            },
        )

        project = await client.get_project()
        root_id = project.get("primaryModelId")
        _expect(bool(root_id), "Project response did not include a primaryModelId")
        report["project"] = project
        _append_check(
            report,
            "project-open",
            True,
            {
                "name": project.get("name"),
                "isDirty": project.get("isDirty"),
                "primaryModelId": root_id,
            },
        )

        prefix = f"MCP Assignment 10A Validation {int(time.time())}"
        validation_package = await _create_element(
            "Package",
            prefix,
            root_id,
            report,
            documentation="Disposable package for Assignment 10A live validation.",
        )
        validation_package_id = validation_package["id"]
        _append_check(
            report,
            "validation-package-created",
            True,
            {
                "packageId": validation_package_id,
                "packageName": validation_package.get("name"),
            },
        )

        sysml_profile_name = await _resolve_sysml_profile_name(report)
        apply_result = await client.apply_profile(
            package_id=validation_package_id,
            profile_name=sysml_profile_name,
        )
        _append_check(
            report,
            "sysml-profile-applied",
            True,
            {
                "profileName": apply_result.get("profileName"),
                "alreadyApplied": apply_result.get("alreadyApplied"),
                "applied": apply_result.get("applied"),
            },
        )

        system_block = await _create_element("Block", "ValidationContextSystem", validation_package_id, report)
        source_block = await _create_element("Block", "ValidationSourceBlock", validation_package_id, report)
        target_block = await _create_element("Block", "ValidationTargetBlock", validation_package_id, report)
        interface_block = await _create_element("InterfaceBlock", "ValidationInterfaceBlock", validation_package_id, report)
        payload_block = await _create_element("Block", "ValidationPayloadBlock", validation_package_id, report)

        flow_property = await _create_element("FlowProperty", "payloadOut", interface_block["id"], report)
        await client.set_specification(
            flow_property["id"],
            properties={"type": {"id": payload_block["id"]}},
        )
        await client.set_tagged_values(
            flow_property["id"],
            stereotype="flowProperty",
            values={"direction": "out"},
        )
        flow_property_spec = await client.get_specification(flow_property["id"])
        flow_property_element = await client.get_element(flow_property["id"])
        _expect(
            any(name.lower() == "flowproperty" for name in _applied_stereotype_names(flow_property_spec)),
            "FlowProperty alias did not apply <<flowProperty>>",
        )
        _expect(
            flow_property_spec.get("properties", {}).get("type", {}).get("id") == payload_block["id"],
            "FlowProperty type did not persist to the payload block",
        )
        _expect(
            _tag_name(_stereotype_tag_value(flow_property_spec, "FlowProperty", "direction")).upper() == "OUT",
            "FlowProperty specification readback did not expose direction as OUT",
        )
        _expect(
            _tag_name((flow_property_element.get("taggedValues") or {}).get("direction")).upper() == "OUT",
            "FlowProperty element readback did not expose direction as OUT",
        )
        flow_property_probe = _parse_probe_output(
            (await _execute_macro(_flow_property_probe_macro(flow_property["id"]))).get("output", "")
        )
        _expect(
            any(name.lower() == "flowproperty" for name in flow_property_probe.get("stereotype", [])),
            "FlowProperty probe did not report the <<flowProperty>> stereotype",
        )
        _expect(
            flow_property_probe.get("typeId") == payload_block["id"],
            "FlowProperty probe reported the wrong payload type",
        )
        _expect(
            str(flow_property_probe.get("direction", "")).upper() == "OUT",
            "FlowProperty direction did not persist as OUT",
        )
        _append_check(
            report,
            "hw-10-3-flow-property-path",
            True,
            flow_property_probe,
        )

        source_port = await _create_element("Port", "sourcePort", source_block["id"], report)
        target_port = await _create_element("Port", "targetPort", target_block["id"], report)
        await client.set_specification(
            source_port["id"],
            properties={"type": {"id": interface_block["id"]}},
        )
        await client.set_specification(
            target_port["id"],
            properties={"type": {"id": interface_block["id"]}},
        )

        source_part = await _create_element("Property", "sourcePart", system_block["id"], report)
        target_part = await _create_element("Property", "targetPart", system_block["id"], report)
        await client.set_specification(
            source_part["id"],
            properties={"type": {"id": source_block["id"]}},
        )
        await client.set_specification(
            target_part["id"],
            properties={"type": {"id": target_block["id"]}},
        )

        connector = await client.create_relationship(
            type="Connector",
            source_id=source_port["id"],
            target_id=target_port["id"],
            owner_id=system_block["id"],
            source_part_with_port_id=source_part["id"],
            target_part_with_port_id=target_part["id"],
            name="validation_connector",
        )
        connector_id = connector["relationship"]["id"]

        item_flow = await client.create_relationship(
            type="ItemFlow",
            source_id=source_port["id"],
            target_id=target_port["id"],
            owner_id=system_block["id"],
            realizing_connector_id=connector_id,
            conveyed_ids=[payload_block["id"]],
            item_property_id=flow_property["id"],
            name="validation_item_flow",
        )
        item_flow_id = item_flow["relationship"]["id"]
        report["artifacts"]["connectorId"] = connector_id
        report["artifacts"]["itemFlowId"] = item_flow_id

        item_flow_element = await client.get_element(item_flow_id)
        _expect(
            item_flow_element.get("type") == "InformationFlow",
            "ItemFlow create path did not persist as an InformationFlow element",
        )
        stereotypes = [str(item).lower() for item in item_flow_element.get("stereotypes", [])]
        _expect(
            "itemflow" in stereotypes,
            "ItemFlow relationship did not receive the <<ItemFlow>> stereotype",
        )
        _expect(
            item_flow_element.get("itemProperty", {}).get("id") == flow_property["id"],
            "ItemFlow readback lost the structured itemProperty reference",
        )
        realizing_connector_ids = {
            entry.get("id")
            for entry in item_flow_element.get("realizingConnectors", [])
            if isinstance(entry, dict)
        }
        _expect(
            connector_id in realizing_connector_ids,
            "ItemFlow readback lost the realizing connector reference",
        )
        conveyed_ids = {
            entry.get("id")
            for entry in item_flow_element.get("conveyed", [])
            if isinstance(entry, dict)
        }
        _expect(
            payload_block["id"] in conveyed_ids,
            "ItemFlow readback lost the conveyed payload classifier",
        )

        item_flow_probe = _parse_probe_output(
            (await _execute_macro(_item_flow_probe_macro(item_flow_id))).get("output", "")
        )
        _expect(
            item_flow_element.get("ownerId") == validation_package_id,
            "ItemFlow readback did not resolve containment to the validation package",
        )
        _expect(
            item_flow_probe.get("ownerId") == validation_package_id,
            "ItemFlow probe did not resolve containment to the validation package",
        )
        _expect(connector_id in item_flow_probe.get("connector", []), "ItemFlow probe did not report the realizing connector")
        _expect(
            payload_block["id"] in item_flow_probe.get("conveyed", []),
            "ItemFlow probe did not report the conveyed payload block",
        )
        _expect(
            item_flow_probe.get("itemPropertyId") == flow_property["id"],
            "ItemFlow probe did not report the flow property tag",
        )
        _append_check(
            report,
            "hw-10-4-item-flow-model-path",
            True,
            {
                "elementReadback": item_flow_element,
                "probe": item_flow_probe,
            },
        )

        source_relationships = await client.get_relationships(source_port["id"])
        outgoing_item_flows = [
            relationship
            for relationship in source_relationships.get("outgoing", [])
            if relationship.get("relationshipId") == item_flow_id
        ]
        _expect(
            bool(outgoing_item_flows),
            "Port relationship query missed the outgoing ItemFlow",
        )
        outgoing_item_flow = outgoing_item_flows[0]
        _expect(
            outgoing_item_flow.get("itemProperty", {}).get("id") == flow_property["id"],
            "Relationship query lost the structured itemProperty reference",
        )
        _expect(
            payload_block["id"]
            in {
                entry.get("id")
                for entry in outgoing_item_flow.get("conveyed", [])
                if isinstance(entry, dict)
            },
            "Relationship query lost the conveyed payload classifier",
        )
        _append_check(
            report,
            "hw-10-4-item-flow-query-path",
            True,
            outgoing_item_flow,
        )

        ibd = await client.create_diagram(
            type="InternalBlockDiagram",
            name="Validation Context IBD",
            parent_id=system_block["id"],
        )
        diagram_id = ibd["id"]
        report["artifacts"]["ibdId"] = diagram_id
        source_part_shape = await client.add_to_diagram(
            diagram_id=diagram_id,
            element_id=source_part["id"],
            x=140,
            y=120,
        )
        target_part_shape = await client.add_to_diagram(
            diagram_id=diagram_id,
            element_id=target_part["id"],
            x=480,
            y=120,
        )
        source_port_shape = await client.add_to_diagram(
            diagram_id=diagram_id,
            element_id=source_port["id"],
            x=120,
            y=40,
            container_presentation_id=source_part_shape["presentationId"],
        )
        target_port_shape = await client.add_to_diagram(
            diagram_id=diagram_id,
            element_id=target_port["id"],
            x=20,
            y=40,
            container_presentation_id=target_part_shape["presentationId"],
        )
        path_result = await client.add_diagram_paths(
            diagram_id=diagram_id,
            paths=[
                {
                    "relationshipId": connector_id,
                    "sourceShapeId": source_port_shape["presentationId"],
                    "targetShapeId": target_port_shape["presentationId"],
                },
                {
                    "relationshipId": item_flow_id,
                    "sourceShapeId": source_port_shape["presentationId"],
                    "targetShapeId": target_port_shape["presentationId"],
                },
            ],
        )
        _expect(
            path_result.get("resultCount") == 2,
            "IBD path creation did not return both connector and item-flow results",
        )
        path_entries = path_result.get("results", [])
        _expect(
            all(isinstance(entry, dict) and entry.get("created") for entry in path_entries),
            "IBD path creation failed for at least one relationship",
        )
        _append_check(
            report,
            "hw-10-4-ibd-path-placement",
            True,
            {
                "diagram": ibd,
                "paths": path_entries,
            },
        )

        visual_verification = await mcp_server.cameo_verify_diagram_visual(
            diagram_id,
            expected_element_ids=[
                source_part["id"],
                target_part["id"],
                source_port["id"],
                target_port["id"],
            ],
            expected_relationship_ids=[connector_id, item_flow_id],
            min_shape_count=4,
            min_relationship_shape_count=2,
            min_width=1,
            min_height=1,
            min_image_bytes=1024,
            min_content_coverage_ratio=0.01,
        )
        failed_visual_checks = [
            check["name"]
            for check in visual_verification.get("checks", [])
            if not check.get("ok")
        ]
        _expect(
            visual_verification.get("ok") is True,
            "Diagram visual verification failed: " + ", ".join(failed_visual_checks),
        )
        _append_check(
            report,
            "hw-10-4-visual-verification",
            True,
            {
                "diagramId": diagram_id,
                "image": visual_verification.get("image"),
                "shapes": visual_verification.get("shapes"),
                "checks": visual_verification.get("checks"),
            },
        )

        report["success"] = True

        if not keep_artifacts and validation_package_id is not None:
            report["cleanup"]["attempted"] = True
            cleanup = await client.delete_element(validation_package_id)
            report["cleanup"]["deleted"] = bool(cleanup.get("deleted"))
            report["cleanup"]["response"] = cleanup
    except Exception as exc:
        report["success"] = False
        report["error"] = {
            "type": type(exc).__name__,
            "message": str(exc),
        }
        if validation_package_id is not None:
            report["artifacts"]["validationPackageId"] = validation_package_id
            if not keep_artifacts:
                try:
                    report["cleanup"]["attempted"] = True
                    cleanup = await client.delete_element(validation_package_id)
                    report["cleanup"]["deleted"] = bool(cleanup.get("deleted"))
                    report["cleanup"]["response"] = cleanup
                except Exception as cleanup_exc:
                    report["cleanup"]["error"] = str(cleanup_exc)

    return report


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run live validation for the remaining Assignment 10A bridge workflows.",
    )
    parser.add_argument(
        "--keep-artifacts",
        action="store_true",
        help="Do not delete the disposable validation package after a successful run.",
    )
    args = parser.parse_args()

    report = asyncio.run(run_validation(keep_artifacts=args.keep_artifacts))
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report.get("success") else 1


if __name__ == "__main__":
    raise SystemExit(main())
