from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Awaitable, Callable
from urllib.parse import urlparse

HERE = Path(__file__).resolve()
MCP_SERVER_DIR = HERE.parents[1]
if str(MCP_SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(MCP_SERVER_DIR))

from cameo_mcp import client  # noqa: E402


def _record(report: dict[str, Any], name: str, ok: bool, details: Any) -> None:
    report.setdefault("checks", []).append(
        {
            "name": name,
            "ok": ok,
            "details": details,
        }
    )


async def _run(
    report: dict[str, Any],
    name: str,
    operation: Callable[[], Awaitable[dict[str, Any]]],
    *,
    required: bool = True,
) -> dict[str, Any] | None:
    try:
        result = await operation()
    except Exception as exc:  # noqa: BLE001 - live validation must preserve exact failure evidence
        _record(report, name, not required, {"type": type(exc).__name__, "message": str(exc)})
        return None
    _record(report, name, True, result)
    return result


async def main_async(args: argparse.Namespace) -> int:
    parsed = urlparse(args.base_url)
    if parsed.port:
        os.environ["CAMEO_BRIDGE_PORT"] = str(parsed.port)

    timestamp = time.strftime("%Y%m%d-%H%M%S", time.localtime())
    out_dir = Path(args.output_dir) / timestamp if args.timestamped else Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    report: dict[str, Any] = {
        "startedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "baseUrl": args.base_url,
        "writesAllowed": args.allow_write,
    }

    await _run(report, "status", client.status)
    await _run(report, "capabilities", client.get_capabilities)
    await _run(report, "project", client.get_project, required=args.require_open_project)

    await _run(report, "validation.capabilities", client.get_validation_capabilities)
    await _run(report, "validation.suites", client.list_validation_suites, required=False)

    await _run(report, "reports.capabilities", client.get_report_capabilities)
    await _run(report, "reports.templates", client.list_report_templates, required=False)
    await _run(
        report,
        "reports.generatePreview",
        lambda: client.generate_report_preview(template_id="__probe__", output_path=str(out_dir / "probe.docx")),
        required=False,
    )

    await _run(report, "importExport.capabilities", client.get_import_export_capabilities)
    await _run(
        report,
        "importExport.requirementsExport",
        lambda: client.export_requirements(format="json", limit=25),
        required=False,
    )
    await _run(
        report,
        "importExport.importPreview",
        lambda: client.preview_requirements_import(source_rows=[]),
        required=False,
    )

    await _run(report, "simulation.capabilities", client.get_simulation_capabilities)
    await _run(report, "simulation.configurations", client.list_simulation_configurations, required=False)
    await _run(report, "simulation.runPreview", client.run_simulation_preview, required=False)

    await _run(report, "teamwork.capabilities", client.get_teamwork_capabilities)
    await _run(report, "teamwork.project", client.get_teamwork_project, required=False)
    await _run(report, "teamwork.commitPreview", lambda: client.preview_teamwork_commit(message="MCP probe"), required=False)

    await _run(report, "datahub.capabilities", client.get_datahub_capabilities)
    await _run(report, "datahub.sources", client.list_datahub_sources, required=False)
    await _run(report, "datahub.syncPreview", client.preview_datahub_sync, required=False)

    await _run(report, "criteria.capabilities", client.get_criteria_capabilities)
    await _run(report, "criteria.templates", client.list_criteria_templates)
    await _run(report, "criteria.build", lambda: client.build_criteria_expression("satisfy"), required=False)

    await _run(report, "profiles.capabilities", client.get_profile_capabilities)
    await _run(report, "profiles.summary", client.export_profile_summary, required=False)

    await _run(report, "variants.capabilities", client.get_variant_capabilities)
    await _run(report, "variants.evaluate", client.analyze_variants_preview, required=False)

    await _run(report, "extensions.capabilities", client.get_extension_capabilities)
    await _run(report, "extensions.profiles", client.list_extension_profiles, required=False)
    await _run(report, "extensions.scan", client.scan_extensions, required=False)

    await _run(report, "typedDiagrams.capabilities", client.get_typed_diagram_capabilities)
    await _run(report, "typedDiagrams.list", client.list_typed_diagrams, required=False)

    manifest = {
        "baseUrl": args.base_url,
        "outputDir": str(out_dir),
        "checks": len(report.get("checks", [])),
        "failed": [check["name"] for check in report.get("checks", []) if not check["ok"]],
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    (out_dir / "route-surface.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    (out_dir / "summary.md").write_text(summary_markdown(manifest, report), encoding="utf-8")
    print(json.dumps(manifest, indent=2))
    return 1 if manifest["failed"] else 0


def summary_markdown(manifest: dict[str, Any], report: dict[str, Any]) -> str:
    lines = [
        "# Autopilot Route Surface Validation",
        "",
        f"- Base URL: `{manifest['baseUrl']}`",
        f"- Checks: {manifest['checks']}",
        f"- Failed: {len(manifest['failed'])}",
        "",
        "## Checks",
        "",
    ]
    for check in report.get("checks", []):
        status = "PASS" if check["ok"] else "FAIL"
        lines.append(f"- {status}: `{check['name']}`")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:18740/api/v1")
    parser.add_argument("--output-dir", default="validation-output/autopilot-route-surface")
    parser.add_argument("--timestamped", action="store_true")
    parser.add_argument("--require-open-project", action="store_true")
    parser.add_argument("--allow-write", action="store_true")
    return asyncio.run(main_async(parser.parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
