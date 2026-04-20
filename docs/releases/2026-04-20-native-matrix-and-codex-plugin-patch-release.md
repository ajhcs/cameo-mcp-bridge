# Native Matrix and Codex Plugin Patch Release

Date: 2026-04-20
Release: `2.3.2`

## Summary

This patch release makes the native requirement-matrix surface trustworthy enough to use as a release gate and aligns product-facing naming with neutral methodology/package terminology. It also packages the local Codex plugin scaffold so the same workspace can run probe-first, compact, live-validation workflows directly in the Codex app.

Version `2.3.2` keeps the existing bridge contract shape intact while fixing the `refine` matrix regression, tightening dependency ownership, and unifying the user-facing methodology language across the bridge, MCP tools, and docs.

## Shipped

### 1. Live matrix hardening

- Repaired `Refine` relationship stereotype resolution so native `Refine Requirement Matrix` artifacts populate correctly in live Cameo runs
- Kept live matrix validation split by kind so `refine`, `derive`, `satisfy`, and `allocation` are measured independently
- Updated the live matrix harness to validate the live-proven activity-to-requirement refine shape

### 2. Neutral methodology naming

- Consolidated tracked code and docs on neutral methodology/package terminology
- Renamed the public MCP validation tool to `cameo_validate_methodology_package`
- Framed the physical-architecture execution plan as a competency/reference-corpus plan

### 3. Codex workspace productization

- Added a repo-local Codex plugin scaffold, launcher wiring, and live-validation skill guidance
- Corrected README capability-count drift so the documented MCP surface matches the actual bridge manifest

## Compatibility

- Python MCP server version: `2.3.2`
- Plugin version: `2.3.2`
- API version: `v1`
- Handshake version: `1`

Plugin/server version lockstep is still required.

## Verification

- `python -m pytest -q mcp-server/tests` passed with `142 passed`
- `gradlew.bat test assemblePlugin deploy -PcameoHome=D:/DevTools/CatiaMagic -Pjdk17Home=D:/DevTools/jdk17/jdk-17.0.18+8` passed
- `python mcp-server/scripts/live_validate_matrices.py` passed live against a restarted Cameo session with:
  - `refine` populated-cell count `2`
  - `derive` populated-cell count `1`
  - `satisfy` populated-cell count `1`
  - `allocation` populated-cell count `1`

## Follow-on Work

- Finish the remaining physical-architecture readback and validator tranche beyond matrices
- Smoke the repo-local Codex plugin install path in a clean workspace session
- Restore Git transport on this machine so release commits can be pushed without manual intervention
