from __future__ import annotations

import argparse
import asyncio
import base64
import json
import os
import sys
import time
from urllib.parse import urlparse
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve()
MCP_SERVER_DIR = HERE.parents[1]
if str(MCP_SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(MCP_SERVER_DIR))

from cameo_mcp import client  # noqa: E402


async def main_async(args: argparse.Namespace) -> int:
    parsed = urlparse(args.base_url)
    if parsed.port:
        os.environ["CAMEO_BRIDGE_PORT"] = str(parsed.port)
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    report: dict[str, Any] = {
        "startedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "baseUrl": args.base_url,
        "relationMapId": args.relation_map_id,
    }

    raw = await client.get_relation_map_raw_settings(args.relation_map_id, include_raw=args.include_raw)
    templates = await client.list_relation_map_criteria_templates()
    criteria_probe = await client.execute_probe(
        operation="invokeGraphSettingsGetter",
        relation_map_id=args.relation_map_id,
        method_name="getDependencyCriterion",
    )
    presentations = await client.get_relation_map_presentations(args.relation_map_id, limit=args.presentation_limit)
    before_snapshot = await client.create_snapshot(
        target_type="relationMap",
        target_id=args.relation_map_id,
        name="render-validation-before",
    )
    write_receipts: dict[str, Any] = {}
    if args.allow_write:
        criteria: list[dict[str, Any] | str] = []
        if args.criteria_template:
            criteria.append({"template": args.criteria_template})
        if args.criteria_raw:
            criteria.append({"rawExpression": args.criteria_raw})
        if criteria:
            write_receipts["criteria"] = await client.set_relation_map_criteria(
                args.relation_map_id,
                mode=args.criteria_mode,
                criteria=criteria,
                refresh=args.refresh,
            )
        write_receipts["expand"] = await client.expand_relation_map(
            args.relation_map_id,
            mode=args.expand_mode,
            depth=args.expand_depth,
            refresh=args.refresh,
            layout=args.layout,
            timeout=args.render_timeout,
        )
    graph = await client.get_traceability_graph(
        relation_map_id=args.relation_map_id,
        root_element_ids=[args.root_element_id] if args.root_element_id else None,
        relationship_types=args.relationship_type,
        max_depth=args.max_depth,
        max_nodes=args.max_nodes,
    )
    render = await client.render_relation_map(
        args.relation_map_id,
        refresh=args.refresh,
        expand=args.expand,
        layout=args.layout,
        scale_percentage=args.scale_percentage,
        include_image=not args.skip_image,
        export_image=not args.skip_image,
        timeout=args.render_timeout,
    )
    after_snapshot = await client.create_snapshot(
        target_type="relationMap",
        target_id=args.relation_map_id,
        name="render-validation-after",
    )
    snapshot_diff = await client.diff_snapshots(
        before_snapshot["snapshotId"],
        after_snapshot["snapshotId"],
        include_details=False,
    )
    verify = await client.verify_relation_map(
        args.relation_map_id,
        expected_min_nodes=args.expected_min_graph_nodes,
        expected_min_edges=args.expected_min_graph_edges,
        expected_rendered_nodes=args.expected_min_rendered_presentations,
        relationship_types=args.relationship_type,
        max_depth=args.max_depth,
    )

    artifacts = {
        "rawSettings": out_dir / "raw-settings.json",
        "criteriaTemplates": out_dir / "criteria-templates.json",
        "criteriaProbe": out_dir / "criteria-probe.json",
        "presentations": out_dir / "presentations.json",
        "graph": out_dir / "graph.json",
        "render": out_dir / "render.json",
        "verify": out_dir / "verify.json",
        "writeReceipts": out_dir / "write-receipts.json",
        "snapshotDiff": out_dir / "snapshot-diff.json",
    }
    artifacts["rawSettings"].write_text(json.dumps(raw, indent=2), encoding="utf-8")
    artifacts["criteriaTemplates"].write_text(json.dumps(templates, indent=2), encoding="utf-8")
    artifacts["criteriaProbe"].write_text(json.dumps(criteria_probe, indent=2), encoding="utf-8")
    artifacts["presentations"].write_text(json.dumps(presentations, indent=2), encoding="utf-8")
    artifacts["graph"].write_text(json.dumps(graph, indent=2), encoding="utf-8")
    artifacts["render"].write_text(json.dumps({k: v for k, v in render.items() if k != "image"}, indent=2), encoding="utf-8")
    artifacts["verify"].write_text(json.dumps(verify, indent=2), encoding="utf-8")
    artifacts["writeReceipts"].write_text(json.dumps(write_receipts, indent=2), encoding="utf-8")
    artifacts["snapshotDiff"].write_text(json.dumps(snapshot_diff, indent=2), encoding="utf-8")

    image = render.get("image") or {}
    if image.get("image"):
        png_path = out_dir / "rendered.png"
        png_path.write_bytes(base64.b64decode(image["image"]))
        artifacts["renderedPng"] = png_path

    report["artifacts"] = {key: str(path) for key, path in artifacts.items()}
    report["summary"] = {
        "graphNodeCount": graph.get("nodeCount"),
        "graphEdgeCount": graph.get("edgeCount"),
        "presentationCount": presentations.get("presentationCount"),
        "renderPresentationCountAfter": render.get("presentationCountAfter"),
        "verifyOk": verify.get("ok"),
        "checks": verify.get("checks"),
        "snapshotChangeCount": snapshot_diff.get("changeCount"),
        "writeReceiptKeys": sorted(write_receipts.keys()),
    }
    report_path = out_dir / "summary.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report["summary"] | {"summary": str(report_path)}, indent=2))
    return 0 if verify.get("ok") else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:18740/api/v1")
    parser.add_argument("--relation-map-id", required=True)
    parser.add_argument("--root-element-id")
    parser.add_argument("--relationship-type", action="append")
    parser.add_argument("--expected-min-graph-nodes", type=int, default=0)
    parser.add_argument("--expected-min-graph-edges", type=int, default=0)
    parser.add_argument("--expected-min-rendered-presentations", type=int, default=0)
    parser.add_argument("--max-depth", type=int, default=3)
    parser.add_argument("--max-nodes", type=int, default=250)
    parser.add_argument("--presentation-limit", type=int, default=500)
    parser.add_argument("--scale-percentage", type=int, default=200)
    parser.add_argument("--render-timeout", type=float, default=120.0)
    parser.add_argument("--skip-image", action="store_true")
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--expand", default="none")
    parser.add_argument("--allow-write", action="store_true")
    parser.add_argument("--criteria-template")
    parser.add_argument("--criteria-raw")
    parser.add_argument("--criteria-mode", default="append", choices=["replace", "append", "remove"])
    parser.add_argument("--expand-mode", default="all")
    parser.add_argument("--expand-depth", type=int)
    parser.add_argument("--layout")
    parser.add_argument("--include-raw", action="store_true")
    parser.add_argument("--output-dir", default="validation-output/relation-map-rendering")
    return asyncio.run(main_async(parser.parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
