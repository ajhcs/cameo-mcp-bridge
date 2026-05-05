# Plan: Relation Map UI Introspection and Native Settings Control

**Generated**: 2026-05-04
**Estimated Complexity**: High
**Primary repo**: `Z:\cameo-mcp-bridge`
**Primary live target**: CATIA Magic / Cameo Systems Modeler with `CameoMCPBridge` loaded on `http://127.0.0.1:18740/api/v1`

## Overview

## 2026-05-04 Live Refinement Note

Live CATIA validation found that native Relation Map refresh is the unstable
operation, not graph traversal or PNG export. `RelationshipMapUtilities`
exposes only `refreshMap(Diagram)` on this install, and that call can block the
Swing EDT for large maps. The bridge design therefore needs to treat refresh as
an explicit, risky operation with timeout evidence, not as a hidden default in
render, criteria, expand, collapse, create, or configure flows.

Implementation direction:

- serialize CATIA write sessions bridge-wide
- report write-in-progress instead of allowing overlapping sessions
- keep render/export as EDT read/no-session when no mutation is requested
- make native refresh opt-in and document it as a potentially blocking CATIA UI
  rebuild
- validate Relation Maps primarily through graph/verify/render evidence without
  implicit refresh

The current bridge can create and inspect many model elements, diagrams, matrices, tables, and relation maps, but it does not yet expose enough of CATIA Magic's UI-created diagram state to reproduce advanced Relation Map behavior. The immediate motivating failure is this:

- The underlying model traceability exists and is traversable through the bridge graph endpoint.
- The Relation Map Diagram exists and its settings validate.
- CATIA Magic's rendered relation map still shows only the root context node and legend.

This strongly suggests the bridge is missing one or more CATIA-native UI details: exact relationship criteria objects, expansion state, active diagram state, selection state, graph node expansion state, presentation properties, or some internal diagram refresh/layout behavior that the UI performs but our bridge does not.

The goal of this work is to stop guessing. Build a set of native UI/settings inspection tools, a before/after snapshot and diff workflow, and controlled mutation endpoints that let an agent observe what CATIA Magic actually changes when a human configures a relation map through the UI. Then convert those observed deltas into stable MCP tools.

## Guiding Principles

- Prefer evidence from live CATIA Magic over assumptions from Java source names.
- Every new write endpoint must have a corresponding readback endpoint.
- Every new UI/settings operation must produce a machine-readable receipt.
- Avoid broad, generic "dump everything forever" responses by default. Provide `summaryOnly`, `includeRaw`, `limit`, and `offset` controls where response size can grow.
- Keep macro/script execution as an escape hatch, not the primary API.
- Version-lock the Python MCP client and Java plugin together after adding endpoints.
- Live validation must prove actual CATIA behavior, not just HTTP `200`.

## Current Relevant Code

Java plugin:

- `plugin/src/com/claude/cameo/bridge/HttpBridgeServer.java`
- `plugin/src/com/claude/cameo/bridge/handlers/DiagramHandler.java`
- `plugin/src/com/claude/cameo/bridge/handlers/RelationMapHandler.java`
- `plugin/src/com/claude/cameo/bridge/handlers/SpecificationHandler.java`
- `plugin/src/com/claude/cameo/bridge/handlers/MacroHandler.java`
- `plugin/src/com/claude/cameo/bridge/util/BridgeCapabilities.java`
- `plugin/plugin.xml`
- `plugin/build.gradle`

Python MCP server/client:

- `mcp-server/cameo_mcp/client.py`
- `mcp-server/cameo_mcp/server.py`
- `mcp-server/tests/test_client.py`

Likely new Java handlers/utilities:

- `plugin/src/com/claude/cameo/bridge/handlers/UiStateHandler.java`
- `plugin/src/com/claude/cameo/bridge/handlers/PropertyDumpHandler.java`
- `plugin/src/com/claude/cameo/bridge/handlers/SnapshotHandler.java`
- `plugin/src/com/claude/cameo/bridge/handlers/ScriptProbeHandler.java`
- `plugin/src/com/claude/cameo/bridge/util/PropertySerializer.java`
- `plugin/src/com/claude/cameo/bridge/util/PresentationSerializer.java`
- `plugin/src/com/claude/cameo/bridge/util/SnapshotStore.java`
- `plugin/src/com/claude/cameo/bridge/util/JsonDiff.java`

## Non-Goals

- Do not replace CATIA Magic's Relation Map engine with an external renderer in this phase.
- Do not make unrestricted remote code execution available outside localhost.
- Do not build a GUI for the bridge.
- Do not remove the existing macro endpoint unless a safer replacement is complete and validated.
- Do not hard-code any validation model into the bridge. Live validation may use an approved model, but tools must be general.

## Prerequisites

- CATIA Magic/Cameo Systems Modeler available on the target machine.
- A model open for live validation. Use a disposable or explicitly approved model for any write validation.
- Bridge reachable at `http://127.0.0.1:18740/api/v1/status`.
- Java build uses JDK 17 on this machine, previously at `D:/DevTools/jdk17/jdk-17.0.18+8`.
- Gradle build should be run from the plugin project, using the repo's existing workflow.
- Python tests should run from `mcp-server`.

## Sprint 1: UI State Inspector

**Goal**: Expose the live CATIA UI context so an agent can know what diagram, element, symbol, or relation-map node the user is looking at or has selected.

**Demo/Validation**:

- Open a diagram in CATIA Magic.
- Select a shape and a path.
- Call the new UI state endpoint.
- Confirm the response includes active diagram, selected model element IDs, selected presentation IDs, diagram type, and selection counts.

### Task 1.1: Add Java UI State Handler

- **Location**:
  - `plugin/src/com/claude/cameo/bridge/handlers/UiStateHandler.java`
  - `plugin/src/com/claude/cameo/bridge/HttpBridgeServer.java`
  - `plugin/src/com/claude/cameo/bridge/util/BridgeCapabilities.java`
- **Description**:
  - Add `GET /api/v1/ui/state`.
  - Return current application/project/UI context.
  - Use CATIA/MagicDraw APIs for:
    - active project
    - active diagram presentation element
    - selected browser node, if available
    - selected presentation elements, if available
    - selected model elements, if available
  - Run UI reads on the Swing EDT if required.
- **Response shape**:
  - `project`: name, filePath, primaryModelId, isDirty
  - `activeDiagram`: id, name, type, owner
  - `selection`: selectedElementCount, selectedPresentationCount
  - `selectedElements`: compact element references
  - `selectedPresentations`: presentationId, shapeType, backing element reference, bounds when available
  - `browserSelection`: element reference if available
  - `warnings`: array of APIs that were unavailable or returned null
- **Acceptance Criteria**:
  - Returns `200` with no selection.
  - Returns active diagram info when a diagram is open.
  - Returns selected symbol and backing element IDs when a shape/path is selected.
  - Does not mutate the model.
- **Validation**:
  - Add Java-side smoke script or manual live validation.
  - Add Python client wrapper and MCP tool in Sprint 5.

### Task 1.2: Add Active Diagram Convenience Endpoints

- **Location**:
  - `UiStateHandler.java`
  - `HttpBridgeServer.java`
  - `BridgeCapabilities.java`
- **Description**:
  - Add `GET /api/v1/ui/active-diagram`.
  - Add `GET /api/v1/ui/selection`.
  - These can delegate to `GET /ui/state` internally but return smaller payloads.
- **Acceptance Criteria**:
  - `active-diagram` response is small enough to use frequently.
  - `selection` response gives enough IDs to feed into property dump endpoints.
- **Validation**:
  - Select different diagrams and symbols in CATIA and verify readback changes.

### Task 1.3: Add UI State Capability Metadata

- **Location**:
  - `BridgeCapabilities.java`
  - `mcp-server/cameo_mcp/client.py`
  - `mcp-server/cameo_mcp/server.py`
- **Description**:
  - Register capabilities:
    - `cameo_get_ui_state`
    - `cameo_get_active_diagram`
    - `cameo_get_ui_selection`
- **Acceptance Criteria**:
  - `/api/v1/status` and `/api/v1/capabilities` expose the new tools.
  - Python MCP server exposes matching tools with docstrings.
- **Validation**:
  - Unit tests for client paths.
  - Live call against CATIA.

## Sprint 2: Raw Settings and Property Dumps

**Goal**: Make CATIA's internal settings inspectable. This is the core unblocker for reverse engineering Relation Map behavior.

**Demo/Validation**:

- Create a relation map manually through the UI.
- Dump its raw diagram settings and presentation properties.
- Change one setting in the UI.
- Dump again and observe a machine-readable difference.

### Task 2.1: Add Generic Property Serializer

- **Location**:
  - `plugin/src/com/claude/cameo/bridge/util/PropertySerializer.java`
- **Description**:
  - Serialize CATIA `PropertyManager` and `Property` objects in a safe, structured format.
  - Preserve:
    - property name
    - property ID
    - class type
    - value type
    - value string
    - raw class name
    - enum/list/map values where possible
  - Avoid throwing when a property cannot be serialized; include a warning entry instead.
- **Acceptance Criteria**:
  - Handles null values.
  - Handles primitive values.
  - Handles lists/collections.
  - Handles CATIA-specific objects by returning class name plus string representation.
- **Validation**:
  - Unit test serializer against mock/simple properties if practical.
  - Live test against a class shape, dependency path, diagram frame, relation map.

### Task 2.2: Add Diagram Property Dump Endpoint

- **Location**:
  - `plugin/src/com/claude/cameo/bridge/handlers/PropertyDumpHandler.java`
  - `HttpBridgeServer.java`
  - `BridgeCapabilities.java`
- **Endpoint**:
  - `GET /api/v1/inspect/diagrams/{diagramId}/properties`
- **Query params**:
  - `includeRaw=true|false`
  - `includePresentationProperties=true|false`
  - `limit`
  - `offset`
  - `summaryOnly=true|false`
- **Response shape**:
  - diagram reference
  - diagram property manager dump, if available
  - diagram presentation property manager dump, if available
  - counts by presentation type
  - optional paged presentation property dumps
- **Acceptance Criteria**:
  - Works on BDD, activity diagram, matrix, generic table, and relation map.
  - Does not require a diagram to be open, unless CATIA requires load; if loading is required, call `ensureLoaded`.
  - Does not mutate diagram except any unavoidable `ensureLoaded` side effect, which must be documented in `warnings`.
- **Validation**:
  - Live dump for `13A Stakeholder-to-Physical Traceability Map`.
  - Live dump for a known BDD with shapes and paths.

### Task 2.3: Add Presentation Property Dump Endpoint

- **Endpoint**:
  - `GET /api/v1/inspect/diagrams/{diagramId}/presentations/{presentationId}/properties`
- **Description**:
  - Return full property dump for one symbol/path/label.
  - Include parent presentation ID and children summary.
- **Acceptance Criteria**:
  - Works for `ClassView`, `DependencyView`, `TextBoxView`, `DiagramFrameView`, `SwimlaneView`, and relation-map node presentations if they appear.
- **Validation**:
  - Select a shape in UI, get its presentation ID through Sprint 1, dump properties.

### Task 2.4: Add Relation Map Raw Settings Dump

- **Location**:
  - `RelationMapHandler.java` or new `RelationMapInspectHandler.java`
- **Endpoint**:
  - `GET /api/v1/relation-maps/{relationMapId}/settings/raw`
- **Description**:
  - Dump more than the current sanitized `GraphSettings`.
  - Include:
    - context element
    - scope roots
    - element types
    - dependency criteria list as strings
    - criteria count
    - layout
    - depth
    - legend
    - all discoverable `GraphSettings` getter values via reflection
    - all public no-arg getter names and values where safe
    - raw settings object class name
    - validity check result
- **Acceptance Criteria**:
  - Reflection failures are warnings, not endpoint failures.
  - Response shows enough data to compare UI-created vs bridge-created maps.
- **Validation**:
  - Dump relation map before and after manual UI edits.
  - Confirm criteria strings are not lost or normalized beyond recognition.

### Task 2.5: Add Relation Map Presentation Dump

- **Endpoint**:
  - `GET /api/v1/relation-maps/{relationMapId}/presentations`
- **Description**:
  - Ensure relation map is loaded.
  - Return relation-map presentation elements, including any node/path/legend presentations.
  - Include bounds, backing element, presentation class names, child counts.
- **Acceptance Criteria**:
  - For the current failing relation map, response should confirm whether CATIA has created only one node presentation or whether export is hiding/cropping expanded nodes.
- **Validation**:
  - Compare presentation count with rendered PNG dimensions.

## Sprint 3: Snapshot and Diff Workflow

**Goal**: Let CATIA Magic create the correct state through the UI, then capture exactly what changed.

**Demo/Validation**:

1. Agent calls `POST /api/v1/snapshots` for a relation map.
2. User manually adds relationship criteria or expands nodes in CATIA UI.
3. Agent calls `POST /api/v1/snapshots` again.
4. Agent calls diff endpoint.
5. Diff clearly shows changed settings/properties/presentations.

### Task 3.1: Add Snapshot Store

- **Location**:
  - `plugin/src/com/claude/cameo/bridge/util/SnapshotStore.java`
  - `plugin/src/com/claude/cameo/bridge/handlers/SnapshotHandler.java`
- **Endpoint**:
  - `POST /api/v1/snapshots`
- **Request body**:
  - `targetType`: `project|diagram|relationMap|element|presentation|ui`
  - `targetId`: optional for UI/project
  - `name`: optional human label
  - `includeRaw`: default false
  - `includePresentations`: default true for diagrams/relation maps
  - `includeProperties`: default true
- **Response**:
  - `snapshotId`
  - `target`
  - `createdAt`
  - `summary`
  - `warnings`
- **Storage**:
  - In-memory store is acceptable for Sprint 3.
  - Add optional export endpoint later if needed.
- **Acceptance Criteria**:
  - Can snapshot a relation map before and after UI change.
  - Snapshot payload uses the same serializers as Sprint 2.

### Task 3.2: Add Snapshot View and Delete

- **Endpoints**:
  - `GET /api/v1/snapshots`
  - `GET /api/v1/snapshots/{snapshotId}`
  - `DELETE /api/v1/snapshots/{snapshotId}`
- **Acceptance Criteria**:
  - Snapshot list gives enough metadata to pick before/after.
  - Delete works and does not touch the model.

### Task 3.3: Add JSON Diff Utility

- **Location**:
  - `plugin/src/com/claude/cameo/bridge/util/JsonDiff.java`
- **Description**:
  - Implement deterministic JSON diff:
    - added paths
    - removed paths
    - changed scalar paths
    - changed array lengths
  - Include path filtering options:
    - ignore timestamps
    - ignore volatile IDs if necessary
    - ignore bounds if requested
- **Acceptance Criteria**:
  - Diff output is stable across runs.
  - Large arrays are summarized unless `includeDetails=true`.

### Task 3.4: Add Snapshot Diff Endpoint

- **Endpoint**:
  - `POST /api/v1/snapshots/diff`
- **Request body**:
  - `beforeSnapshotId`
  - `afterSnapshotId`
  - `ignorePaths`: optional array
  - `includeDetails`: default true
  - `maxChanges`: default 500
- **Acceptance Criteria**:
  - Can diff relation map before/after manual criteria addition.
  - Can diff relation map before/after manual expansion of plus nodes.
  - Output points directly to the changed settings/property paths.

### Task 3.5: Add High-Level Compare Helper for Relation Maps

- **Endpoint**:
  - `POST /api/v1/relation-maps/compare`
- **Request body**:
  - `leftRelationMapId`
  - `rightRelationMapId`
  - `includePresentations`
  - `includeRaw`
- **Description**:
  - Useful when a user creates a working relation map manually next to a bridge-created one.
- **Acceptance Criteria**:
  - Diff clearly distinguishes GraphSettings criteria, context, scope, expansion/presentation differences.

## Sprint 4: Relation Map Native Control Endpoints

**Goal**: Convert observed UI deltas into stable bridge operations for relation map criteria, expansion, refresh, layout, and export.

**Demo/Validation**:

- Create a relation map through the bridge.
- Apply criteria using the new native criteria endpoint.
- Expand nodes using the new expansion endpoint.
- Export image.
- Confirm exported image includes expected relationship graph, not only root node.

### Task 4.1: Add Criteria Template Discovery

- **Endpoint**:
  - `GET /api/v1/relation-maps/criteria/templates`
- **Description**:
  - Return known criteria templates discovered from UI diffs.
  - Initial templates should be data-driven constants, not scattered strings:
    - `dependency.direct`
    - `abstraction.direct`
    - `refine.sourceToTarget`
    - `refine.targetToSource`
    - `deriveReqt.sourceToTarget`
    - `deriveReqt.targetToSource`
    - `satisfy.sourceToTarget`
    - `satisfy.targetToSource`
    - `allocate.sourceToTarget`
    - `allocatedTo`
  - Include a `verifiedWithUiDiff` boolean per template.
- **Acceptance Criteria**:
  - Templates can be listed without a project open if implemented as static metadata.
  - Templates generated from actual CATIA UI deltas are marked verified.

### Task 4.2: Add Criteria Apply Endpoint

- **Endpoint**:
  - `PUT /api/v1/relation-maps/{relationMapId}/criteria`
- **Request body**:
  - `mode`: `replace|append|remove`
  - `criteria`: array of objects:
    - `template`: optional template key
    - `rawExpression`: optional raw CATIA expression string
    - `relationshipType`: optional normalized name
    - `direction`: optional
    - `color`: optional, only if CATIA settings support it
    - `label`: optional
  - `refresh`: default true
- **Description**:
  - Use exact UI-derived criteria XML/object strings where known.
  - Do not assume metaclass-only criteria are enough.
- **Acceptance Criteria**:
  - Readback through raw settings shows criteria applied exactly.
  - Invalid criteria returns `400` with an actionable error.
  - Endpoint receipt includes before/after criteria count.

### Task 4.3: Add Relation Map Expansion Endpoint

- **Endpoint**:
  - `POST /api/v1/relation-maps/{relationMapId}/expand`
- **Request body**:
  - `mode`: `all|selected|byElement|byDepth`
  - `elementIds`: optional
  - `depth`: optional
  - `refresh`: default true
  - `layout`: optional
- **Description**:
  - Investigate CATIA APIs for relation-map node expansion.
  - If no public API exists, use a macro-backed implementation internally but expose it as a normal bridge endpoint with validation and receipts.
- **Acceptance Criteria**:
  - For a manually configured relation map, expanding all increases presentation node/path count.
  - For the failing validation map, expansion either works or returns a clear unsupported reason with evidence.

### Task 4.4: Add Relation Map Collapse Endpoint

- **Endpoint**:
  - `POST /api/v1/relation-maps/{relationMapId}/collapse`
- **Request body**:
  - `mode`: `all|selected|byElement`
  - `elementIds`: optional
- **Acceptance Criteria**:
  - Collapse operation visibly reduces presentation count or reports unsupported.
  - Does not destroy settings criteria.

### Task 4.5: Add Relation Map Refresh/Layout/Export Pipeline Endpoint

- **Endpoint**:
  - `POST /api/v1/relation-maps/{relationMapId}/render`
- **Request body**:
  - `refresh`: default true
  - `expand`: `none|all|depth`
  - `depth`: optional
  - `layout`: optional
  - `scalePercentage`: default 200
  - `includeImage`: default true
  - `includePresentationSummary`: default true
- **Response**:
  - image metadata
  - presentation count before/after refresh
  - graph node/edge count if requested
  - warnings
- **Acceptance Criteria**:
  - One endpoint can perform the full "make the relation map visible" workflow.
  - If image is still root-only, response shows whether the problem is criteria, expansion, or export.

### Task 4.6: Add Criteria/Graph Consistency Verifier

- **Endpoint**:
  - `POST /api/v1/relation-maps/{relationMapId}/verify`
- **Request body**:
  - `expectedMinNodes`
  - `expectedMinEdges`
  - `expectedRenderedNodes`
  - `relationshipTypes`
  - `maxDepth`
- **Acceptance Criteria**:
  - For the current failure, verifier should say:
    - graph traversal passes
    - settings validity passes
    - rendered node count fails
  - This becomes the regression test for the relation-map bug.

## Sprint 5: MCP Client and Server Tool Surface

**Goal**: Make all new Java endpoints available to coding agents through the Python MCP server with clear, typed tool docs.

**Demo/Validation**:

- Agent can call MCP tools rather than raw HTTP.
- Tool results are native dicts.
- Unit tests pass.

### Task 5.1: Add Python Client Methods

- **Location**:
  - `mcp-server/cameo_mcp/client.py`
- **Methods**:
  - `get_ui_state()`
  - `get_active_diagram()`
  - `get_ui_selection()`
  - `get_diagram_properties(diagram_id, ...)`
  - `get_presentation_properties(diagram_id, presentation_id, ...)`
  - `get_relation_map_raw_settings(relation_map_id, ...)`
  - `get_relation_map_presentations(relation_map_id, ...)`
  - `create_snapshot(...)`
  - `list_snapshots()`
  - `get_snapshot(snapshot_id)`
  - `delete_snapshot(snapshot_id)`
  - `diff_snapshots(...)`
  - `list_relation_map_criteria_templates()`
  - `set_relation_map_criteria(...)`
  - `expand_relation_map(...)`
  - `collapse_relation_map(...)`
  - `render_relation_map(...)`
  - `verify_relation_map(...)`
- **Acceptance Criteria**:
  - All methods use `_request`.
  - All methods have clear parameter names matching existing style.
  - Tests mock exact paths and methods.

### Task 5.2: Add MCP Tools

- **Location**:
  - `mcp-server/cameo_mcp/server.py`
- **Tool names**:
  - `cameo_get_ui_state`
  - `cameo_get_active_diagram`
  - `cameo_get_ui_selection`
  - `cameo_dump_diagram_properties`
  - `cameo_dump_presentation_properties`
  - `cameo_dump_relation_map_raw_settings`
  - `cameo_list_relation_map_presentations`
  - `cameo_create_snapshot`
  - `cameo_list_snapshots`
  - `cameo_get_snapshot`
  - `cameo_delete_snapshot`
  - `cameo_diff_snapshots`
  - `cameo_list_relation_map_criteria_templates`
  - `cameo_set_relation_map_criteria`
  - `cameo_expand_relation_map`
  - `cameo_collapse_relation_map`
  - `cameo_render_relation_map`
  - `cameo_verify_relation_map`
- **Acceptance Criteria**:
  - Tool docstrings say when to use each tool.
  - Tools return `_mcp_result(result)`.
  - Parameters include aliases for snake_case and camelCase where useful.
  - Potentially large dumps default to summary mode.

### Task 5.3: Update Client/Plugin Version Lockstep

- **Location**:
  - `client.py`
  - `plugin/plugin.xml`
  - `plugin/build.gradle`
  - `BridgeCapabilities.java`
  - `CHANGELOG.md`
  - `docs/releases/` if current release process uses it
- **Description**:
  - Bump bridge version after endpoints are complete.
  - Ensure status compatibility metadata requires exact match.
- **Acceptance Criteria**:
  - `/status` reports the new version.
  - Python client expected plugin version matches Java plugin.

## Sprint 6: Controlled Script Probe Escape Hatch

**Goal**: Provide a safer, auditable way to run tiny discovery probes against CATIA APIs when normal endpoint coverage is insufficient.

**Demo/Validation**:

- Agent runs a read-only probe that introspects relation-map classes/methods.
- Response includes stdout/result/warnings.
- Write probes require explicit `mode=write` and are blocked by default if not enabled.

### Task 6.1: Harden Existing Macro Capabilities or Add ScriptProbeHandler

- **Location**:
  - Existing `MacroHandler.java` or new `ScriptProbeHandler.java`
- **Endpoint**:
  - `POST /api/v1/probes/execute`
- **Request body**:
  - `language`: `groovy|javascript|javaReflection` depending on supported CATIA environment
  - `mode`: `read|write`
  - `script`
  - `timeoutMs`
  - `requiresProject`: default true
  - `description`
- **Safety controls**:
  - Bind to localhost only.
  - Optional environment/system property gate for write probes.
  - Default timeout.
  - Return clear refusal if write probes are disabled.
  - Log probe description and mode.
- **Acceptance Criteria**:
  - Read-only probes work without opening a model session.
  - Write probes are disabled unless explicitly enabled.
  - Errors return useful stack traces but do not crash the bridge.

### Task 6.2: Add Built-In Probe Templates

- **Endpoint**:
  - `GET /api/v1/probes/templates`
- **Templates**:
  - `relationMap.listGraphSettingsMethods`
  - `relationMap.dumpCriteriaClasses`
  - `relationMap.dumpPresentationClasses`
  - `diagram.dumpSelectedPresentationMethods`
  - `ui.dumpSelectionApi`
- **Acceptance Criteria**:
  - Agents can run known probes without hand-writing scripts.
  - Template outputs help discover private/public CATIA APIs faster.

## Sprint 7: Live Validation Harness

**Goal**: Make validation repeatable so this does not become a one-off manual session.

**Demo/Validation**:

- With CATIA Magic open and a project loaded, run one script that validates:
  - bridge health
  - UI state endpoints
  - property dumps
  - snapshots and diffs
  - relation-map criteria/expansion/render pipeline

### Task 7.1: Add Live Validation Script

- **Location**:
  - `mcp-server/scripts/live_validate_ui_introspection.py`
  - or `mcp-server/tests/live_validate_ui_introspection.py` depending on repo pattern
- **Description**:
  - Use raw HTTP or Python client.
  - Do not require destructive model changes by default.
  - Include optional `--relation-map-id`.
  - Include optional `--diagram-id`.
  - Include optional `--allow-write` for criteria/expansion tests.
- **Acceptance Criteria**:
  - Script clearly reports pass/fail by endpoint.
  - Script exits non-zero on failed required checks.
  - Script writes an evidence JSON file under a temp or validation output folder.

### Task 7.2: Add Relation Map Regression Script

- **Location**:
  - `mcp-server/scripts/live_validate_relation_map_rendering.py`
- **Description**:
  - Specifically targets the current failure mode.
  - Inputs:
    - relation map ID
    - root element ID
    - expected min graph nodes
    - expected min graph edges
    - expected min rendered presentations
  - Exports:
    - raw settings JSON
    - presentation dump JSON
    - graph JSON
    - rendered PNG
    - verifier summary JSON
- **Acceptance Criteria**:
  - Can reproduce "graph passes, render fails" before fix.
  - Can prove "graph passes, render passes" after fix.

### Task 7.3: Add Unit Tests

- **Location**:
  - `mcp-server/tests/test_client.py`
  - new Java tests if existing test setup supports them
- **Acceptance Criteria**:
  - Python client path/method/body tests for every new endpoint.
  - Serializer tests for common value types if Java test framework is available.

## Sprint 8: Documentation and Agent Runbook

**Goal**: Give future agents exact instructions for using the new bridge surface.

### Task 8.1: Add User-Facing Docs

- **Location**:
  - `docs/strategy/relation-map-ui-introspection.md`
  - or `docs/ideation/relation-map-ui-introspection.md`
- **Contents**:
  - Why the tools exist.
  - How to snapshot before/after UI changes.
  - How to inspect selected symbols.
  - How to apply relation-map criteria.
  - How to verify graph vs rendered relation map.
- **Acceptance Criteria**:
  - A new agent can follow the doc without reading this plan.

### Task 8.2: Add Server Agent Instructions

- **Location**:
  - `docs/plans/relation-map-ui-introspection-plan.md` or companion runbook
- **Instructions**:
  - Start with `git status --short`.
  - Do not revert unrelated dirty files.
  - Check `http://127.0.0.1:18740/api/v1/status`.
  - Check `/api/v1/project`.
  - Confirm plugin version.
  - Run unit tests before live validation.
  - Rebuild and deploy plugin.
  - Restart CATIA Magic after plugin deployment.
  - Run live validation after restart.
- **Acceptance Criteria**:
  - Documentation includes exact commands and expected evidence.

## Suggested Endpoint Summary

Read-only:

- `GET /api/v1/ui/state`
- `GET /api/v1/ui/active-diagram`
- `GET /api/v1/ui/selection`
- `GET /api/v1/inspect/diagrams/{diagramId}/properties`
- `GET /api/v1/inspect/diagrams/{diagramId}/presentations/{presentationId}/properties`
- `GET /api/v1/relation-maps/{relationMapId}/settings/raw`
- `GET /api/v1/relation-maps/{relationMapId}/presentations`
- `GET /api/v1/snapshots`
- `GET /api/v1/snapshots/{snapshotId}`
- `GET /api/v1/relation-maps/criteria/templates`
- `GET /api/v1/probes/templates`

Write or stateful:

- `POST /api/v1/snapshots`
- `DELETE /api/v1/snapshots/{snapshotId}`
- `POST /api/v1/snapshots/diff`
- `POST /api/v1/relation-maps/compare`
- `PUT /api/v1/relation-maps/{relationMapId}/criteria`
- `POST /api/v1/relation-maps/{relationMapId}/expand`
- `POST /api/v1/relation-maps/{relationMapId}/collapse`
- `POST /api/v1/relation-maps/{relationMapId}/render`
- `POST /api/v1/relation-maps/{relationMapId}/verify`
- `POST /api/v1/probes/execute`

## Recommended Server Agent Work Order

1. Create the read-only UI state and property dump endpoints first.
2. Add Python client/server wrappers for those read-only endpoints.
3. Rebuild/deploy/restart CATIA and live-test read-only inspection.
4. Manually create or edit a relation map in CATIA UI.
5. Use snapshot/diff tooling to capture exact UI-created criteria and expansion deltas.
6. Only then implement relation-map mutation endpoints.
7. Add render/verify endpoint after criteria and expansion are observable.
8. Add script probe escape hatch last, with safety controls.

This order matters because implementing write endpoints before we can read exact CATIA-native state will recreate the current guessing problem.

## Build and Validation Commands

From repo root:

```powershell
git status --short
```

Bridge health with CATIA running:

```powershell
Invoke-RestMethod -Uri 'http://127.0.0.1:18740/api/v1/status' | ConvertTo-Json -Depth 8
Invoke-RestMethod -Uri 'http://127.0.0.1:18740/api/v1/project' | ConvertTo-Json -Depth 8
Invoke-RestMethod -Uri 'http://127.0.0.1:18740/api/v1/capabilities' | ConvertTo-Json -Depth 8
```

Python tests:

```powershell
cd Z:\cameo-mcp-bridge\mcp-server
python -m pytest
```

Java build pattern to confirm with existing repo workflow:

```powershell
cd Z:\cameo-mcp-bridge\plugin
$env:JAVA_HOME='D:\DevTools\jdk17\jdk-17.0.18+8'
cmd.exe /c gradlew.bat clean build
```

Live validation after deploy/restart:

```powershell
python mcp-server\scripts\live_validate_ui_introspection.py --base-url http://127.0.0.1:18740/api/v1
python mcp-server\scripts\live_validate_relation_map_rendering.py --base-url http://127.0.0.1:18740/api/v1 --relation-map-id <id> --root-element-id <id>
```

## Acceptance Criteria for the Whole Project

Minimum:

- New UI state endpoints expose active diagram and selections.
- New property dump endpoints expose raw diagram, presentation, and relation-map settings.
- Snapshot/diff workflow can capture manual CATIA UI changes.
- MCP tools expose the new read and diff workflows.
- Existing tests pass.
- Live validation can prove the current relation-map failure mode.

Target:

- A manually working UI-created relation map can be diffed against a bridge-created relation map.
- The exact UI-created relationship criteria can be reapplied by bridge endpoint.
- Relation-map expansion/render pipeline can produce a rendered image with more than the root node.
- `cameo_verify_relation_map` clearly distinguishes:
  - model graph exists
  - settings are valid
  - rendered relation map expanded successfully

## Potential Risks and Gotchas

- CATIA may not expose active UI selection through a stable public API. Mitigation: add best-effort warnings and use reflection/probe templates.
- Relation-map expansion may be UI-only or hidden behind non-public APIs. Mitigation: implement read-only detection first; use controlled script probes to discover methods.
- `GraphSettings.setDependencyCriterion(...)` accepting strings does not prove the criteria are semantically equivalent to UI-created criteria. Mitigation: snapshot/diff UI-created maps before adding more criteria templates.
- Exported relation-map image may crop or omit content even when presentations exist. Mitigation: compare presentation count, graph count, and image dimensions in verifier.
- Saving may leave `isDirty: true` after refresh/export. Mitigation: verifier should report dirty state separately and avoid treating save success as cleanliness unless immediate readback confirms it.
- Response sizes can explode when dumping raw properties. Mitigation: default to summaries and add pagination.
- Macro/probe execution has security risk. Mitigation: localhost only, read mode default, write mode gate, timeout, logging.
- Network-share Gradle builds can be brittle. Mitigation: if `Z:` build fails, copy the plugin folder to local temp for build and deploy artifact back intentionally.

## Rollback Plan

- Keep new endpoints additive.
- Do not change existing endpoint behavior except capability metadata and versioning.
- If new handlers cause plugin startup failure:
  - revert handler registration in `HttpBridgeServer.java`
  - revert capability additions in `BridgeCapabilities.java`
  - rebuild previous plugin artifact
  - restart CATIA Magic
- If Python MCP tool additions fail validation:
  - keep Java plugin deployed
  - revert only Python server/client additions
  - use raw HTTP endpoints for live investigation until MCP wrappers are fixed

## Handoff Notes for the Coding Agent

- Start by reading the current tree. Do not trust this plan over the actual checkout.
- Do not revert unrelated dirty files. The repo currently has ongoing changes around relation maps, matrices, generic tables, and version `2.3.5`.
- Keep commits small by sprint or endpoint group.
- After implementing any Java endpoint, add it to `BridgeCapabilities.java` and Python client/server wrappers before calling it complete.
- After deploying the plugin, restart CATIA Magic before live validation.
- The most important proof is not that an endpoint returns `200`; it is that live CATIA state changes or readback match the intended behavior.
