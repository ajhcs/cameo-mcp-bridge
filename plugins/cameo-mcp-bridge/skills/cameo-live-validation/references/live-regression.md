# Live Regression

- Use unit tests for payload parsing, contract normalization, and Python-side validation logic.
- Use live validation for anything dependent on actual Cameo behavior:
  - diagram rendering and placement
  - matrix readback
  - flow-property and port semantics
  - connector and item-flow behavior
  - project-level artifact discovery
- Treat these scripts as the current end-to-end smoke tools:
  - `mcp-server/scripts/live_validate_596def1.py`
  - `mcp-server/scripts/live_validate_flow_properties.py`
  - `mcp-server/scripts/live_validate_matrices.py`
- Operational proof means:
  - the bridge is live
  - a project is open
  - the target artifact can be created or read back
  - the result is validated by a purpose-built checker or a narrow live assertion
