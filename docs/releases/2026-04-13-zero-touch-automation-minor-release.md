# Zero-Touch Automation Minor Release

Date: 2026-04-13
Release: `2.3.0`

## Summary

This minor release pushes the bridge further from a low-level Cameo transport and closer to an end-to-end modeling copilot. The focus of `2.3.0` is reducing the amount of manual cleanup still required after the model semantics are already correct: diagram repair, proofing, artifact validation, export packaging, and previewable remediation planning.

Because `2.2.0` was never cut as a separate public release, the `2.3.0` release also includes the bridge hardening work that landed after `2.1.0`: enum-tag writing fixes, presentation-level APIs, and more reliable bridge discovery.

## Shipped

### 1. Diagram repair endpoints

- Added native repair operations for:
  - hidden labels
  - overlapping label positions
  - conveyed item-flow labels
  - diagram-type-aware compartment presets
- Exposed the repair surface through the Java plugin, Python client, and MCP server
- Added dry-run support so repair work can be previewed before it is applied

### 2. Proofing tools

- Added package-aware proofing for:
  - requirements text
  - comments
  - state and transition names
  - diagram text
- Added patch-plan generation so suggested wording changes can be reviewed before mutation
- Added optional safe auto-apply support for model-backed text where the bridge can write directly

### 3. Methodology-driven workflows

- Added artifact-list comparison against expected deliverables
- Added methodology/package validation helpers
- Added required-diagram export helpers
- Added automated PPT/PDF assembly support so submission bundles can be produced directly from the bridge workflow

### 4. Semantic auto-remediation

- Added cross-diagram inconsistency detection that returns structured findings
- Added previewable remediation plans with `patchPlan.steps` instead of only reporting failures
- Kept remediation planning non-destructive by default so the user can inspect a proposed fix set before applying it

### 5. Bridge hardening included in the release

- Fixed enum-valued stereotype tagged values by resolving actual `EnumerationLiteral` instances by ID or name
- Added intent-level presentation APIs for transition labels, item-flow labels, and allocation/full-port compartments
- Added bridge probing support so clients can discover whether local health lives at `/status` or `/api/v1/status`
- Added legacy `/status` and `/capabilities` aliases alongside the versioned API routes
- Mirrored large-diagram shaping controls into the Python client so direct client users do not need to reimplement paging/filtering/resizing logic

## Change Notes

- `2.3.0` is the first release that can both inspect and actively clean up common presentation-layer issues in a bounded, typed way
- Submission packaging is now much closer to a one-command flow: validate, export, assemble, and review
- The bridge now has a clearer split between:
  - semantic validation
  - proofing and presentation cleanup
  - previewable remediation planning

## Compatibility

- Python MCP server version: `2.3.0`
- Plugin version: `2.3.0`
- API version: `v1`
- Handshake version: `1`

Plugin/server version lockstep is still required.

## Verification

- `python3 -m pytest mcp-server/tests -q` passed with `140 passed`
- A live PPT/PDF assembly smoke test succeeded through the Python workflow surface

## Follow-on Work

- Add a one-shot `cameo_repair_diagram` orchestration tool that runs the repair passes with diagram-type defaults
- Add an apply-side cross-diagram remediation endpoint so preview plans can become controlled edits
- Expand proofing coverage to more presentation-only text where the model element is not the display source of truth
- Add workflow-specific export templates and richer evidence bundle assembly
