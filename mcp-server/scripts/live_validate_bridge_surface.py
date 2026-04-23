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

from cameo_mcp import client  # noqa: E402


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


def _has_stereotype(element: dict[str, Any], expected: str) -> bool:
    stereotypes = element.get("stereotypes") or []
    return any(str(item).lower() == expected.lower() for item in stereotypes)


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


def _transition_probe_macro(transition_id: str) -> str:
    transition_literal = json.dumps(transition_id)
    return f"""
def transition = project.getElementByID({transition_literal})
def guard = transition?.getGuard()
def spec = guard?.getSpecification()
def guardValue = null
if (spec != null) {{
    try {{
        guardValue = spec.getValue()
    }} catch (Throwable ignored) {{
        try {{
            guardValue = spec.getBody()?.isEmpty() ? null : spec.getBody().get(0)
        }} catch (Throwable ignored2) {{
            guardValue = spec.toString()
        }}
    }}
}}
println("transitionId=" + (transition?.getID() ?: ""))
println("guardClass=" + (guard?.getClass()?.getSimpleName() ?: ""))
println("guardName=" + (guard?.getName() ?: ""))
println("guardValue=" + (guardValue ?: ""))
println("regionId=" + (transition?.getContainer()?.getID() ?: ""))
println("sourceContainerId=" + (transition?.getSource()?.getContainer()?.getID() ?: ""))
println("targetContainerId=" + (transition?.getTarget()?.getContainer()?.getID() ?: ""))
return "ok"
""".strip()


def _connector_probe_macro(connector_id: str) -> str:
    connector_literal = json.dumps(connector_id)
    return f"""
def connector = project.getElementByID({connector_literal})
println("connectorId=" + (connector?.getID() ?: ""))
println("ownerId=" + (connector?.get_structuredClassifierOfOwnedConnector()?.getID() ?: ""))
for (end in connector?.getEnd() ?: []) {{
    println("end=" + (end?.getRole()?.getID() ?: "") + "|" + (end?.getPartWithPort()?.getID() ?: ""))
}}
return "ok"
""".strip()


def _stereotype_probe_macro(element_id: str) -> str:
    element_literal = json.dumps(element_id)
    return f"""
import com.nomagic.uml2.ext.jmi.helpers.StereotypesHelper
def element = project.getElementByID({element_literal})
println("elementId=" + (element?.getID() ?: ""))
for (st in StereotypesHelper.getStereotypes(element) ?: []) {{
    println("stereotype=" + (st?.getName() ?: ""))
}}
return "ok"
""".strip()


def _parse_key_value_output(output: str) -> dict[str, Any]:
    parsed: dict[str, Any] = {}
    ends: list[dict[str, str]] = []
    stereotypes: list[str] = []

    for raw_line in output.splitlines():
        line = raw_line.strip()
        if not line or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key == "end":
            role_id, _, part_with_port_id = value.partition("|")
            ends.append(
                {
                    "roleId": role_id,
                    "partWithPortId": part_with_port_id,
                }
            )
            continue
        if key == "stereotype":
            stereotypes.append(value)
            continue
        parsed[key] = value

    if ends:
        parsed["ends"] = ends
    if stereotypes:
        parsed["stereotypes"] = stereotypes
    return parsed


def _applied_stereotype_names(specification: dict[str, Any]) -> list[str]:
    applied = specification.get("appliedStereotypes") or []
    names: list[str] = []
    for entry in applied:
        name = entry.get("stereotype")
        if isinstance(name, str) and name:
            names.append(name)
    return names


async def _resolve_sysml_profile_name(report: dict[str, Any]) -> str:
    profiles = await client.query_elements(type="Profile", recursive=True, limit=1000, view="compact")
    discovered = [
        element.get("name", "")
        for element in profiles.get("elements", [])
        if element.get("name")
    ]
    report["availableProfiles"] = discovered

    preferred = [
        "SysML",
        "SysML Profile",
        "sysml",
        "sysml profile",
    ]
    candidates: list[str] = []
    seen: set[str] = set()

    for item in preferred + discovered:
        normalized = item.strip()
        if not normalized:
            continue
        key = normalized.lower()
        if key in seen:
            continue
        if "sysml" not in key:
            continue
        seen.add(key)
        candidates.append(normalized)

    _expect(bool(candidates), "Could not discover a SysML profile in the open project")
    report["sysmlProfileCandidates"] = candidates
    return candidates[0]


async def run_validation(keep_artifacts: bool) -> dict[str, Any]:
    report: dict[str, Any] = {
        "runId": f"live-bridge-surface-{int(time.time())}",
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
        report["status"] = {
            "healthy": status.get("healthy"),
            "pluginVersion": status.get("pluginVersion"),
            "apiVersion": status.get("apiVersion"),
            "handshakeVersion": status.get("handshakeVersion"),
            "clientCompatible": status.get("compatibility", {}).get("clientCompatible"),
        }
        _expect(status.get("healthy") is True, "Bridge status is not healthy")
        _expect(
            status.get("compatibility", {}).get("clientCompatible") is True,
            "Bridge compatibility handshake failed",
        )
        _append_check(report, "status-handshake", True, report["status"])

        project = await client.get_project()
        report["project"] = project
        root_id = project.get("primaryModelId")
        _expect(bool(root_id), "Project response did not include a primaryModelId")
        _append_check(
            report,
            "project-open",
            True,
            {
                "name": project.get("name"),
                "primaryModelId": root_id,
            },
        )

        prefix = f"MCP Live Validation {int(time.time())}"
        validation_package = await _create_element(
            "Package",
            prefix,
            root_id,
            report,
            documentation="Disposable package for live bridge surface validation.",
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
        report["sysmlProfileApplication"] = apply_result
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

        block_a = await _create_element("Block", "ValidationBlockA", validation_package_id, report)
        block_a_spec = await client.get_specification(block_a["id"])
        _expect(
            any(name.lower() == "block" for name in _applied_stereotype_names(block_a_spec)),
            "Block alias did not apply <<Block>>",
        )
        block_b = await _create_element("Block", "ValidationBlockB", validation_package_id, report)
        block_b_spec = await client.get_specification(block_b["id"])
        _expect(
            any(name.lower() == "block" for name in _applied_stereotype_names(block_b_spec)),
            "Second Block alias did not apply <<Block>>",
        )
        system_block = await _create_element("Block", "ValidationSystem", validation_package_id, report)
        system_block_spec = await client.get_specification(system_block["id"])
        _expect(
            any(name.lower() == "block" for name in _applied_stereotype_names(system_block_spec)),
            "Owner block alias did not apply <<Block>>",
        )
        interface_block = await _create_element(
            "InterfaceBlock",
            "ValidationInterface",
            validation_package_id,
            report,
        )
        interface_block_spec = await client.get_specification(interface_block["id"])
        _expect(
            any(name.lower() == "interfaceblock" for name in _applied_stereotype_names(interface_block_spec)),
            "InterfaceBlock alias did not apply <<InterfaceBlock>>",
        )
        value_type = await _create_element("ValueType", "ValidationValueType", validation_package_id, report)
        value_type_spec = await client.get_specification(value_type["id"])
        _expect(
            any(name.lower() == "valuetype" for name in _applied_stereotype_names(value_type_spec)),
            "ValueType alias did not apply <<ValueType>>",
        )
        constraint_block = await _create_element(
            "ConstraintBlock",
            "ValidationConstraint",
            validation_package_id,
            report,
        )
        constraint_block_spec = await client.get_specification(constraint_block["id"])
        _expect(
            any(name.lower() == "constraintblock" for name in _applied_stereotype_names(constraint_block_spec)),
            "ConstraintBlock alias did not apply <<ConstraintBlock>>",
        )
        requirement_a = await _create_element(
            "Requirement",
            "Validation Requirement A",
            validation_package_id,
            report,
        )
        requirement_a_spec = await client.get_specification(requirement_a["id"])
        _expect(
            any(name.lower() == "requirement" for name in _applied_stereotype_names(requirement_a_spec)),
            "Requirement alias did not apply <<Requirement>>",
        )
        requirement_b = await _create_element(
            "Requirement",
            "Validation Requirement B",
            validation_package_id,
            report,
        )
        requirement_b_spec = await client.get_specification(requirement_b["id"])
        _expect(
            any(name.lower() == "requirement" for name in _applied_stereotype_names(requirement_b_spec)),
            "Second Requirement alias did not apply <<Requirement>>",
        )
        _append_check(
            report,
            "sysml-alias-creation",
            True,
            {
                "blockA": block_a["id"],
                "interfaceBlock": interface_block["id"],
                "valueType": value_type["id"],
                "constraintBlock": constraint_block["id"],
                "requirementA": requirement_a["id"],
            },
        )

        port_a = await _create_element("Port", "portA", block_a["id"], report)
        port_b = await _create_element("Port", "portB", block_b["id"], report)
        part_a = await _create_element("Property", "partA", system_block["id"], report)
        part_b = await _create_element("Property", "partB", system_block["id"], report)

        await client.set_specification(
            port_a["id"],
            properties={"type": {"id": interface_block["id"]}},
        )
        await client.set_specification(
            port_b["id"],
            properties={"type": {"id": interface_block["id"]}},
        )
        await client.set_specification(
            part_a["id"],
            properties={"type": {"id": block_a["id"]}},
        )
        await client.set_specification(
            part_b["id"],
            properties={"type": {"id": block_b["id"]}},
        )
        spec_port_a = await client.get_specification(port_a["id"])
        spec_port_b = await client.get_specification(port_b["id"])
        spec_part_a = await client.get_specification(part_a["id"])
        spec_part_b = await client.get_specification(part_b["id"])
        _expect(
            spec_port_a.get("properties", {}).get("type", {}).get("id") == interface_block["id"],
            "Typed specification write did not persist portA.type",
        )
        _expect(
            spec_port_b.get("properties", {}).get("type", {}).get("id") == interface_block["id"],
            "Typed specification write did not persist portB.type",
        )
        _expect(
            spec_part_a.get("properties", {}).get("type", {}).get("id") == block_a["id"],
            "Typed specification write did not persist partA.type",
        )
        _expect(
            spec_part_b.get("properties", {}).get("type", {}).get("id") == block_b["id"],
            "Typed specification write did not persist partB.type",
        )
        _append_check(
            report,
            "typed-specification-write",
            True,
            {
                "portAType": spec_port_a.get("properties", {}).get("type"),
                "portBType": spec_port_b.get("properties", {}).get("type"),
                "partAType": spec_part_a.get("properties", {}).get("type"),
                "partBType": spec_part_b.get("properties", {}).get("type"),
            },
        )

        state_machine = await _create_element("StateMachine", "ValidationStateMachine", validation_package_id, report)
        initial_state = await _create_element("InitialState", "Start", state_machine["id"], report)
        idle_state = await _create_element("State", "Idle", state_machine["id"], report)
        active_state = await _create_element("State", "Active", state_machine["id"], report)

        await client.create_relationship(
            type="Transition",
            source_id=initial_state["id"],
            target_id=idle_state["id"],
        )
        guarded_transition = await client.create_relationship(
            type="Transition",
            source_id=idle_state["id"],
            target_id=active_state["id"],
            guard="authorized",
        )
        guarded_transition_id = guarded_transition["relationship"]["id"]
        transition_probe = _parse_key_value_output(
            (await _execute_macro(_transition_probe_macro(guarded_transition_id))).get("output", "")
        )
        _expect(
            transition_probe.get("guardValue") == "authorized",
            "Transition guard did not persist as the expected literal",
        )
        _expect(
            transition_probe.get("regionId")
            and transition_probe.get("regionId") == transition_probe.get("sourceContainerId")
            and transition_probe.get("regionId") == transition_probe.get("targetContainerId"),
            "Transition endpoints were not resolved into a shared Region",
        )
        _append_check(
            report,
            "state-machine-and-guarded-transition",
            True,
            transition_probe,
        )

        connector = await client.create_relationship(
            type="Connector",
            source_id=port_a["id"],
            target_id=port_b["id"],
            owner_id=system_block["id"],
            source_part_with_port_id=part_a["id"],
            target_part_with_port_id=part_b["id"],
        )
        connector_id = connector["relationship"]["id"]
        port_a_relationships = await client.get_relationships(port_a["id"])
        connector_matches = [
            item
            for item in port_a_relationships.get("undirected", [])
            if item.get("relationshipId") == connector_id
        ]
        _expect(
            bool(connector_matches),
            "Connector was not returned from get_relationships(portA)",
        )
        connector_probe = _parse_key_value_output(
            (await _execute_macro(_connector_probe_macro(connector_id))).get("output", "")
        )
        _expect(
            connector_probe.get("ownerId") == system_block["id"],
            "Connector owner did not match the requested structured classifier",
        )
        _expect(
            len(connector_probe.get("ends", [])) == 2,
            "Connector did not resolve to exactly two ends",
        )
        populated_ends = [
            end
            for end in connector_probe.get("ends", [])
            if end.get("roleId")
        ]
        _expect(
            len(populated_ends) == 2,
            "Connector did not resolve to exactly two populated ends",
        )
        end_map = {
            end.get("roleId"): end.get("partWithPortId")
            for end in populated_ends
        }
        _expect(end_map.get(port_a["id"]) == part_a["id"], "Connector source end lost partWithPort")
        _expect(end_map.get(port_b["id"]) == part_b["id"], "Connector target end lost partWithPort")
        _append_check(
            report,
            "connector-with-partwithport",
            True,
            {
                "relationshipReadback": connector_matches[0],
                "probe": connector_probe,
            },
        )

        refine = await client.create_relationship(
            type="Refine",
            source_id=block_a["id"],
            target_id=requirement_a["id"],
        )
        derive = await client.create_relationship(
            type="Derive",
            source_id=requirement_b["id"],
            target_id=requirement_a["id"],
        )
        refine_probe = _parse_key_value_output(
            (await _execute_macro(_stereotype_probe_macro(refine["relationship"]["id"]))).get("output", "")
        )
        derive_probe = _parse_key_value_output(
            (await _execute_macro(_stereotype_probe_macro(derive["relationship"]["id"]))).get("output", "")
        )
        _expect(
            any(name.lower() == "refine" for name in refine_probe.get("stereotypes", [])),
            "Refine relationship did not receive the <<Refine>> stereotype",
        )
        _expect(
            any(name.lower() == "derivereqt" for name in derive_probe.get("stereotypes", [])),
            "Derive relationship did not receive the <<DeriveReqt>> stereotype",
        )
        _append_check(
            report,
            "refine-and-derive-relationships",
            True,
            {
                "refine": refine_probe,
                "derive": derive_probe,
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

    return report


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run a live Cameo validation pass for the core bridge surface.",
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
