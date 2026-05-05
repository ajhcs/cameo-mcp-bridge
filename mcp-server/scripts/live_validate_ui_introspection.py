from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from urllib.parse import urlparse
from pathlib import Path
from typing import Any, Awaitable, Callable

HERE = Path(__file__).resolve()
MCP_SERVER_DIR = HERE.parents[1]
if str(MCP_SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(MCP_SERVER_DIR))

from cameo_mcp import client  # noqa: E402


def _check(report: dict[str, Any], name: str, ok: bool, details: Any) -> None:
    report.setdefault("checks", []).append({"name": name, "ok": ok, "details": details})


async def _run(
    report: dict[str, Any],
    name: str,
    operation: Callable[[], Awaitable[dict[str, Any]]],
    required: bool = True,
) -> dict[str, Any] | None:
    try:
        result = await operation()
    except Exception as exc:
        _check(report, name, not required, {"type": type(exc).__name__, "message": str(exc)})
        return None
    _check(report, name, True, result)
    return result


async def main_async(args: argparse.Namespace) -> int:
    parsed = urlparse(args.base_url)
    if parsed.port:
        os.environ["CAMEO_BRIDGE_PORT"] = str(parsed.port)
    report: dict[str, Any] = {
        "startedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "baseUrl": args.base_url,
    }

    await _run(report, "status", client.status)
    await _run(report, "project", client.get_project)
    await _run(report, "capabilities", client.get_capabilities)
    ui_state = await _run(report, "ui.state", client.get_ui_state)
    await _run(report, "ui.activeDiagram", client.get_active_diagram, required=False)
    await _run(report, "ui.selection", client.get_ui_selection, required=False)
    await _run(report, "probe.templates", client.list_probe_templates, required=False)
    await _run(report, "relationMap.criteriaTemplates", client.list_relation_map_criteria_templates, required=False)
    await _run(
        report,
        "probe.graphSettingsMethods",
        lambda: client.execute_probe(template="relationMap.listGraphSettingsMethods"),
        required=False,
    )

    diagram_id = args.diagram_id
    if diagram_id is None and ui_state:
        active = ui_state.get("activeDiagram") or {}
        diagram_id = active.get("id")
    if diagram_id:
        await _run(
            report,
            "diagram.properties",
            lambda: client.get_diagram_properties(diagram_id, summary_only=True, limit=25),
            required=False,
        )

    if args.relation_map_id:
        await _run(
            report,
            "relationMap.rawSettings",
            lambda: client.get_relation_map_raw_settings(args.relation_map_id, summary_only=True),
        )
        await _run(
            report,
            "relationMap.presentations",
            lambda: client.get_relation_map_presentations(args.relation_map_id, limit=50),
        )
        await _run(
            report,
            "relationMap.verify.readOnly",
            lambda: client.verify_relation_map(args.relation_map_id),
            required=False,
        )
        await _run(
            report,
            "probe.graphSettingsCriteriaGetter",
            lambda: client.execute_probe(
                operation="invokeGraphSettingsGetter",
                relation_map_id=args.relation_map_id,
                method_name="getDependencyCriterion",
            ),
            required=False,
        )
        before = await _run(
            report,
            "snapshot.before",
            lambda: client.create_snapshot(
                target_type="relationMap",
                target_id=args.relation_map_id,
                name="live-validate-before",
            ),
        )
        after = await _run(
            report,
            "snapshot.after",
            lambda: client.create_snapshot(
                target_type="relationMap",
                target_id=args.relation_map_id,
                name="live-validate-after",
            ),
        )
        if before and after:
            await _run(
                report,
                "snapshot.diff",
                lambda: client.diff_snapshots(before["snapshotId"], after["snapshotId"], include_details=False),
            )
        if args.allow_write:
            criteria: list[dict[str, Any] | str] = []
            if args.criteria_raw:
                criteria.append({"rawExpression": args.criteria_raw})
            if args.criteria_template:
                criteria.append({"template": args.criteria_template})
            if criteria:
                await _run(
                    report,
                    "relationMap.criteria.write",
                    lambda: client.set_relation_map_criteria(
                        args.relation_map_id,
                        mode=args.criteria_mode,
                        criteria=criteria,
                        refresh=True,
                    ),
                )
            await _run(
                report,
                "relationMap.expand.write",
                lambda: client.expand_relation_map(args.relation_map_id, mode="all", refresh=True),
                required=False,
            )
            await _run(
                report,
                "relationMap.render.write",
                lambda: client.render_relation_map(args.relation_map_id, expand="all", include_image=False),
                required=False,
            )

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    failed = [check for check in report.get("checks", []) if not check["ok"]]
    print(json.dumps({"output": str(output), "failed": len(failed), "checks": len(report.get("checks", []))}, indent=2))
    return 1 if failed else 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:18740/api/v1")
    parser.add_argument("--diagram-id")
    parser.add_argument("--relation-map-id")
    parser.add_argument("--allow-write", action="store_true")
    parser.add_argument("--criteria-template")
    parser.add_argument("--criteria-raw")
    parser.add_argument("--criteria-mode", default="append", choices=["replace", "append", "remove"])
    parser.add_argument("--output", default="validation-output/ui-introspection.json")
    return asyncio.run(main_async(parser.parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
