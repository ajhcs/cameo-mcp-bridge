from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path
from typing import Any, Awaitable, Callable

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


def _error_details(exc: Exception) -> dict[str, Any]:
    return {
        "type": type(exc).__name__,
        "message": str(exc),
    }


async def _run_validation_check(
    report: dict[str, Any],
    name: str,
    operation: Callable[[], Awaitable[dict[str, Any]]],
) -> dict[str, Any] | None:
    try:
        details = await operation()
    except Exception as exc:
        _append_check(report, name, False, _error_details(exc))
        return None
    _append_check(report, name, True, details)
    return details


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


def _element_ids(items: list[dict[str, Any]]) -> set[str]:
    return {
        item.get("id")
        for item in items
        if isinstance(item, dict) and item.get("id")
    }


def _dependency_names(matrix: dict[str, Any]) -> list[str]:
    return sorted(
        {
            dependency.get("name")
            for cell in matrix.get("populatedCells", [])
            if isinstance(cell, dict)
            for dependency in cell.get("dependencies", [])
            if isinstance(dependency, dict) and dependency.get("name")
        }
    )


async def run_validation(keep_artifacts: bool) -> dict[str, Any]:
    report: dict[str, Any] = {
        "runId": f"live-matrix-{int(time.time())}",
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
            "cameo_list_matrices",
            "cameo_get_matrix",
            "cameo_create_matrix",
        }
        _expect(status.get("healthy") is True, "Bridge status is not healthy")
        _expect(
            status.get("compatibility", {}).get("clientCompatible") is True,
            "Bridge compatibility handshake failed",
        )
        _expect(
            required_capabilities.issubset(capability_names),
            "Running bridge does not expose the matrix endpoints; restart Cameo after deploy",
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

        prefix = f"MCP Matrix Validation {int(time.time())}"
        validation_package = await _create_element(
            "Package",
            prefix,
            root_id,
            report,
            documentation="Disposable package for live matrix validation.",
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

        block_a = await _create_element("Block", "MatrixBlockA", validation_package_id, report)
        block_b = await _create_element("Block", "MatrixBlockB", validation_package_id, report)
        activity_a = await _create_element("Activity", "Matrix Activity A", validation_package_id, report)
        activity_b = await _create_element("Activity", "Matrix Activity B", validation_package_id, report)
        requirement_a = await _create_element("Requirement", "Matrix Requirement A", validation_package_id, report)
        requirement_b = await _create_element("Requirement", "Matrix Requirement B", validation_package_id, report)

        refine_1 = await client.create_relationship(
            type="Refine",
            source_id=activity_a["id"],
            target_id=requirement_a["id"],
            name="refine_activity_a_req_a",
        )
        refine_2 = await client.create_relationship(
            type="Refine",
            source_id=activity_b["id"],
            target_id=requirement_b["id"],
            name="refine_activity_b_req_b",
        )
        derive = await client.create_relationship(
            type="Derive",
            source_id=requirement_b["id"],
            target_id=requirement_a["id"],
            name="derive_req_b_req_a",
        )
        allocate = await client.create_relationship(
            type="Allocate",
            source_id=block_a["id"],
            target_id=block_b["id"],
            name="allocate_block_a_block_b",
        )
        satisfy = await client.create_relationship(
            type="Satisfy",
            source_id=block_b["id"],
            target_id=requirement_a["id"],
            name="satisfy_block_b_req_a",
        )
        report["artifacts"]["refineRelationshipIds"] = [
            refine_1["relationship"]["id"],
            refine_2["relationship"]["id"],
        ]
        report["artifacts"]["deriveRelationshipId"] = derive["relationship"]["id"]
        report["artifacts"]["allocateRelationshipId"] = allocate["relationship"]["id"]
        report["artifacts"]["satisfyRelationshipId"] = satisfy["relationship"]["id"]
        _append_check(
            report,
            "seed-relationships-created",
            True,
            {
                "refineIds": report["artifacts"]["refineRelationshipIds"],
                "deriveId": report["artifacts"]["deriveRelationshipId"],
                "allocateId": report["artifacts"]["allocateRelationshipId"],
                "satisfyId": report["artifacts"]["satisfyRelationshipId"],
            },
        )

        async def validate_refine_matrix() -> dict[str, Any]:
            refine_matrix_result = await client.create_matrix(
                kind="Refine Requirement Matrix",
                parent_id=validation_package_id,
                name="Validation Refine Matrix",
                scope_id=validation_package_id,
                row_types=["Activity"],
                column_types=["Requirement"],
            )
            refine_matrix = refine_matrix_result["matrix"]
            refine_matrix_id = refine_matrix["id"]
            report["artifacts"]["refineMatrixId"] = refine_matrix_id
            _expect(refine_matrix["kind"] == "refine", "Refine matrix returned the wrong kind")
            _expect(refine_matrix["matrixType"] == "Refine Requirement Matrix", "Wrong native refine matrix type")
            _expect(refine_matrix["rowCount"] >= 2, "Refine matrix did not include expected activity rows")
            _expect(refine_matrix["columnCount"] >= 2, "Refine matrix did not include expected requirement columns")
            _expect(refine_matrix["populatedCellCount"] >= 2, "Refine matrix did not populate expected cells")
            refine_row_ids = _element_ids(refine_matrix.get("rows", []))
            refine_column_ids = _element_ids(refine_matrix.get("columns", []))
            _expect(
                activity_a["id"] in refine_row_ids and activity_b["id"] in refine_row_ids,
                "Refine matrix rows missed activities",
            )
            _expect(
                requirement_a["id"] in refine_column_ids and requirement_b["id"] in refine_column_ids,
                "Refine matrix columns missed requirements",
            )
            refine_verification = await mcp_server.cameo_verify_matrix_consistency(
                refine_matrix_id,
                expected_row_ids=[activity_a["id"], activity_b["id"]],
                expected_column_ids=[requirement_a["id"], requirement_b["id"]],
                min_populated_cell_count=2,
            )
            _expect(refine_verification.get("ok") is True, "Refine matrix consistency verification failed")
            return {
                "matrixId": refine_matrix_id,
                "rowCount": refine_matrix["rowCount"],
                "columnCount": refine_matrix["columnCount"],
                "populatedCellCount": refine_matrix["populatedCellCount"],
                "dependencyNames": _dependency_names(refine_matrix),
                "verification": refine_verification,
            }

        async def validate_derive_matrix() -> dict[str, Any]:
            derive_matrix_result = await client.create_matrix(
                kind="Derive Requirement Matrix",
                parent_id=validation_package_id,
                name="Validation Derive Matrix",
                scope_id=validation_package_id,
            )
            derive_matrix = derive_matrix_result["matrix"]
            derive_matrix_id = derive_matrix["id"]
            report["artifacts"]["deriveMatrixId"] = derive_matrix_id
            _expect(derive_matrix["kind"] == "derive", "Derive matrix returned the wrong kind")
            _expect(derive_matrix["matrixType"] == "Derive Requirement Matrix", "Wrong native derive matrix type")
            _expect(derive_matrix["rowCount"] >= 2, "Derive matrix did not include expected requirement rows")
            _expect(derive_matrix["columnCount"] >= 2, "Derive matrix did not include expected requirement columns")
            _expect(derive_matrix["populatedCellCount"] >= 1, "Derive matrix did not populate expected cells")
            derive_row_ids = _element_ids(derive_matrix.get("rows", []))
            derive_column_ids = _element_ids(derive_matrix.get("columns", []))
            _expect(
                requirement_a["id"] in derive_row_ids and requirement_b["id"] in derive_row_ids,
                "Derive matrix rows missed requirements",
            )
            _expect(
                requirement_a["id"] in derive_column_ids and requirement_b["id"] in derive_column_ids,
                "Derive matrix columns missed requirements",
            )
            derive_verification = await mcp_server.cameo_verify_matrix_consistency(
                derive_matrix_id,
                expected_row_ids=[requirement_a["id"], requirement_b["id"]],
                expected_column_ids=[requirement_a["id"], requirement_b["id"]],
                min_populated_cell_count=1,
            )
            _expect(derive_verification.get("ok") is True, "Derive matrix consistency verification failed")
            return {
                "matrixId": derive_matrix_id,
                "rowCount": derive_matrix["rowCount"],
                "columnCount": derive_matrix["columnCount"],
                "populatedCellCount": derive_matrix["populatedCellCount"],
                "dependencyNames": _dependency_names(derive_matrix),
                "verification": derive_verification,
            }

        async def validate_satisfy_matrix() -> dict[str, Any]:
            satisfy_matrix_result = await client.create_matrix(
                kind="Satisfy Requirement Matrix",
                parent_id=validation_package_id,
                name="Validation Satisfy Matrix",
                scope_id=validation_package_id,
            )
            satisfy_matrix = satisfy_matrix_result["matrix"]
            satisfy_matrix_id = satisfy_matrix["id"]
            report["artifacts"]["satisfyMatrixId"] = satisfy_matrix_id
            _expect(satisfy_matrix["kind"] == "satisfy", "Satisfy matrix returned the wrong kind")
            _expect(
                satisfy_matrix["matrixType"] == "Satisfy Requirement Matrix",
                "Wrong native satisfy matrix type",
            )
            _expect(satisfy_matrix["rowCount"] >= 2, "Satisfy matrix did not include expected block rows")
            _expect(satisfy_matrix["columnCount"] >= 2, "Satisfy matrix did not include expected requirement columns")
            _expect(satisfy_matrix["populatedCellCount"] >= 1, "Satisfy matrix did not populate expected cells")
            satisfy_row_ids = _element_ids(satisfy_matrix.get("rows", []))
            satisfy_column_ids = _element_ids(satisfy_matrix.get("columns", []))
            _expect(block_b["id"] in satisfy_row_ids, "Satisfy matrix rows missed the satisfying block")
            _expect(requirement_a["id"] in satisfy_column_ids, "Satisfy matrix columns missed the satisfied requirement")
            satisfy_verification = await mcp_server.cameo_verify_matrix_consistency(
                satisfy_matrix_id,
                expected_row_ids=[block_a["id"], block_b["id"]],
                expected_column_ids=[requirement_a["id"], requirement_b["id"]],
                min_populated_cell_count=1,
            )
            _expect(satisfy_verification.get("ok") is True, "Satisfy matrix consistency verification failed")
            return {
                "matrixId": satisfy_matrix_id,
                "rowCount": satisfy_matrix["rowCount"],
                "columnCount": satisfy_matrix["columnCount"],
                "populatedCellCount": satisfy_matrix["populatedCellCount"],
                "dependencyNames": _dependency_names(satisfy_matrix),
                "verification": satisfy_verification,
            }

        async def validate_allocation_matrix() -> dict[str, Any]:
            allocation_matrix_result = await client.create_matrix(
                kind="SysML Allocation Matrix",
                parent_id=validation_package_id,
                name="Validation Allocation Matrix",
                scope_id=validation_package_id,
            )
            allocation_matrix = allocation_matrix_result["matrix"]
            allocation_matrix_id = allocation_matrix["id"]
            report["artifacts"]["allocationMatrixId"] = allocation_matrix_id
            _expect(allocation_matrix["kind"] == "allocation", "Allocation matrix returned the wrong kind")
            _expect(
                allocation_matrix["matrixType"] == "SysML Allocation Matrix",
                "Wrong native allocation matrix type",
            )
            _expect(allocation_matrix["rowCount"] >= 2, "Allocation matrix did not include expected block rows")
            _expect(allocation_matrix["columnCount"] >= 2, "Allocation matrix did not include expected block columns")
            _expect(
                allocation_matrix["populatedCellCount"] >= 1,
                "Allocation matrix did not populate expected cells",
            )
            allocation_row_ids = _element_ids(allocation_matrix.get("rows", []))
            allocation_column_ids = _element_ids(allocation_matrix.get("columns", []))
            _expect(
                block_a["id"] in allocation_row_ids and block_b["id"] in allocation_row_ids,
                "Allocation matrix rows missed blocks",
            )
            _expect(
                block_a["id"] in allocation_column_ids and block_b["id"] in allocation_column_ids,
                "Allocation matrix columns missed blocks",
            )
            allocation_verification = await mcp_server.cameo_verify_matrix_consistency(
                allocation_matrix_id,
                expected_row_ids=[block_a["id"], block_b["id"]],
                expected_column_ids=[block_a["id"], block_b["id"]],
                min_populated_cell_count=1,
            )
            _expect(
                allocation_verification.get("ok") is True,
                "Allocation matrix consistency verification failed",
            )
            return {
                "matrixId": allocation_matrix_id,
                "rowCount": allocation_matrix["rowCount"],
                "columnCount": allocation_matrix["columnCount"],
                "populatedCellCount": allocation_matrix["populatedCellCount"],
                "dependencyNames": _dependency_names(allocation_matrix),
                "verification": allocation_verification,
            }

        await _run_validation_check(report, "refine-matrix-create-readback", validate_refine_matrix)
        await _run_validation_check(report, "derive-matrix-create-readback", validate_derive_matrix)
        await _run_validation_check(report, "satisfy-matrix-create-readback", validate_satisfy_matrix)
        await _run_validation_check(report, "allocation-matrix-create-readback", validate_allocation_matrix)

        async def validate_matrix_list_and_get() -> dict[str, Any]:
            kinds_to_artifacts = {
                "refine": report["artifacts"].get("refineMatrixId"),
                "derive": report["artifacts"].get("deriveMatrixId"),
                "satisfy": report["artifacts"].get("satisfyMatrixId"),
                "allocation": report["artifacts"].get("allocationMatrixId"),
            }
            details: dict[str, Any] = {}
            for kind, matrix_id in kinds_to_artifacts.items():
                _expect(matrix_id is not None, f"No matrix id recorded for kind: {kind}")
                listed = await client.list_matrices(kind=kind, owner_id=validation_package_id)
                listed_ids = _element_ids(listed.get("matrices", []))
                _expect(matrix_id in listed_ids, f"List {kind} matrices missed the created matrix")
                fetched = await client.get_matrix(str(matrix_id))
                _expect(fetched["id"] == matrix_id, f"Get {kind} matrix returned the wrong artifact")
                details[kind] = {
                    "matrixId": matrix_id,
                    "listedCount": listed.get("count"),
                    "fetchedPopulatedCellCount": fetched.get("populatedCellCount"),
                }
            return details

        await _run_validation_check(report, "matrix-list-and-get", validate_matrix_list_and_get)

        report["success"] = all(
            item.get("ok") is True
            for item in report.get("checks", [])
        )

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
        description="Run a live validation pass for the supported native matrix handlers.",
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
