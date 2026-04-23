---
name: cameo-live-validation
description: Probe the local Cameo bridge, keep reads compact, and verify live model claims before proposing or making changes.
---

# Cameo Live Validation

Use this skill when working against the local Cameo bridge in Codex.

## Operating rules

1. Start every live session with:
   - `cameo_probe_bridge`
   - `cameo_status`
   - `cameo_get_capabilities`
   - `cameo_get_project`
2. Treat bridge health and open-project readiness as separate checks.
3. Prefer compact reads first:
   - `view="compact"`
   - filtered queries
   - paged containment reads
   - metadata-only image access before full image payloads
4. Before claiming success, use verification tools when available:
   - `cameo_verify_diagram_visual`
   - `cameo_verify_matrix_consistency`
   - semantic validation helpers
5. Escalate to live scripts only for real smoke or regression work, not every small read.

## Compact defaults

- Do not dump full containment trees unless the task truly needs them.
- Prefer narrow package scopes and exact type filters.
- For diagrams, read the artifact metadata before requesting rendered images.
- For matrix work, inspect row and column counts plus populated cell summaries before pulling full details.
- Summaries in Codex should separate `done`, `failed`, and `blocked` instead of pasting raw payloads.

## Regression boundary

Use the repo's live scripts only when validating an end-to-end capability claim:

- `mcp-server/scripts/live_validate_bridge_surface.py`
- `mcp-server/scripts/live_validate_flow_properties.py`
- `mcp-server/scripts/live_validate_matrices.py`

See the reference notes in `references/preflight.md`, `references/compact-read-patterns.md`, and `references/live-regression.md`.
