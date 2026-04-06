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


def _cell_dependency_names(matrix: dict[str, Any]) -> set[str]:
    names: set[str] = set()
    for cell in matrix.get("populatedCells", []):
        for dependency in cell.get("dependencies", []):
            name = dependency.get("name")
            if isinstance(name, str) and name:
                names.add(name)
    return names


def _element_ids(items: list[dict[str, Any]]) -> set[str]:
    return {
        item.get("id")
        for item in items
        if isinstance(item, dict) and item.get("id")
    }


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
        requirement_a = await _create_element("Requirement", "Matrix Requirement A", validation_package_id, report)
        requirement_b = await _create_element("Requirement", "Matrix Requirement B", validation_package_id, report)

        refine_1 = await client.create_relationship(
            type="Refine",
            source_id=block_a["id"],
            target_id=requirement_a["id"],
            name="refine_block_a_req_a",
        )
        refine_2 = await client.create_relationship(
            type="Refine",
            source_id=block_b["id"],
            target_id=requirement_b["id"],
            name="refine_block_b_req_b",
        )
        derive = await client.create_relationship(
            type="Derive",
            source_id=requirement_b["id"],
            target_id=requirement_a["id"],
            name="derive_req_b_req_a",
        )
        report["artifacts"]["refineRelationshipIds"] = [
            refine_1["relationship"]["id"],
            refine_2["relationship"]["id"],
        ]
        report["artifacts"]["deriveRelationshipId"] = derive["relationship"]["id"]
        _append_check(
            report,
            "seed-relationships-created",
            True,
            {
                "refineIds": report["artifacts"]["refineRelationshipIds"],
                "deriveId": report["artifacts"]["deriveRelationshipId"],
            },
        )

        refine_matrix_result = await client.create_matrix(
            kind="refine",
            parent_id=validation_package_id,
            name="Validation Refine Matrix",
            scope_id=validation_package_id,
        )
        refine_matrix = refine_matrix_result["matrix"]
        refine_matrix_id = refine_matrix["id"]
        report["artifacts"]["refineMatrixId"] = refine_matrix_id
        _expect(refine_matrix["kind"] == "refine", "Refine matrix returned the wrong kind")
        _expect(refine_matrix["matrixType"] == "Refine Requirement Matrix", "Wrong native refine matrix type")
        _expect(refine_matrix["rowCount"] >= 2, "Refine matrix did not include expected block rows")
        _expect(refine_matrix["columnCount"] >= 2, "Refine matrix did not include expected requirement columns")
        _expect(refine_matrix["populatedCellCount"] >= 2, "Refine matrix did not populate expected cells")
        refine_row_ids = _element_ids(refine_matrix.get("rows", []))
        refine_column_ids = _element_ids(refine_matrix.get("columns", []))
        _expect(block_a["id"] in refine_row_ids and block_b["id"] in refine_row_ids, "Refine matrix rows missed blocks")
        _expect(
            requirement_a["id"] in refine_column_ids and requirement_b["id"] in refine_column_ids,
            "Refine matrix columns missed requirements",
        )
        _expect("Refine" in _cell_dependency_names(refine_matrix), "Refine matrix cells missed Refine causes")
        _append_check(
            report,
            "refine-matrix-create-readback",
            True,
            {
                "matrixId": refine_matrix_id,
                "rowCount": refine_matrix["rowCount"],
                "columnCount": refine_matrix["columnCount"],
                "populatedCellCount": refine_matrix["populatedCellCount"],
            },
        )

        derive_matrix_result = await client.create_matrix(
            kind="derive",
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
        _expect("DeriveReqt" in _cell_dependency_names(derive_matrix), "Derive matrix cells missed DeriveReqt causes")
        _append_check(
            report,
            "derive-matrix-create-readback",
            True,
            {
                "matrixId": derive_matrix_id,
                "rowCount": derive_matrix["rowCount"],
                "columnCount": derive_matrix["columnCount"],
                "populatedCellCount": derive_matrix["populatedCellCount"],
            },
        )

        listed_refine = await client.list_matrices(kind="refine", owner_id=validation_package_id)
        listed_derive = await client.list_matrices(kind="derive", owner_id=validation_package_id)
        listed_refine_ids = _element_ids(listed_refine.get("matrices", []))
        listed_derive_ids = _element_ids(listed_derive.get("matrices", []))
        _expect(refine_matrix_id in listed_refine_ids, "List refine matrices missed the created refine matrix")
        _expect(derive_matrix_id in listed_derive_ids, "List derive matrices missed the created derive matrix")

        fetched_refine = await client.get_matrix(refine_matrix_id)
        fetched_derive = await client.get_matrix(derive_matrix_id)
        _expect(fetched_refine["id"] == refine_matrix_id, "Get refine matrix returned the wrong artifact")
        _expect(fetched_derive["id"] == derive_matrix_id, "Get derive matrix returned the wrong artifact")
        _append_check(
            report,
            "matrix-list-and-get",
            True,
            {
                "listedRefineCount": listed_refine.get("count"),
                "listedDeriveCount": listed_derive.get("count"),
                "fetchedRefinePopulatedCellCount": fetched_refine.get("populatedCellCount"),
                "fetchedDerivePopulatedCellCount": fetched_derive.get("populatedCellCount"),
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
        description="Run a live validation pass for the native refine/derive matrix handler.",
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
