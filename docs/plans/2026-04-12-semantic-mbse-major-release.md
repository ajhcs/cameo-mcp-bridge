---
status: active
created: 2026-04-12
owner: codex
deepened: 2026-04-12
---

# Semantic MBSE Major Release Plan

Date: 2026-04-12  
Repo: `cameo-mcp-bridge`  
Origin: External MBSE reference transcript corpus retained outside this repository plus [DoD-Grade Advanced Capability Roadmap](../ideation/2026-03-30-dod-advanced-capabilities-roadmap.md)

## Problem Frame

The bridge is already strong at low-level Cameo manipulation, but the recent MBSE review surfaced a gap between notation support and semantic correctness. It can create the right nouns, shapes, and relationships, yet it still allows:

- activity diagrams with the right actions but no executable end-to-end flow
- port and interface definitions with the right artifacts but the wrong boundary ownership
- IBDs that are structurally correct but hard to trace back to behavior
- state machines that look advanced while hiding blank `entry / do / exit` semantics
- requirements diagrams with IDs and taxonomy but no meaningful requirement statements

This release should turn the product from a strong generic bridge into a semantic MBSE copilot for Cameo-based logical architecture work.

## Release Goal

Ship a major release centered on:

1. Structured state-machine semantics
2. Semantic validation for common MBSE artifact failures
3. Methodology and layout recipes for activity/BDD/IBD/requirements workflows
4. Benchmark-driven hardening and release packaging

## Scope

### In Scope

- New structured APIs for transition triggers/events and state internal behaviors
- New semantic validators for activity flow, port ownership, requirements completeness, and cross-diagram traceability
- Recipe and layout-profile support for the MBSE logical architecture workflows represented in the transcript corpus
- End-to-end tests and live validation scripts grounded in the benchmark scenario
- Docs, capability manifest, version bump, and release notes for a major version

### Out of Scope

- Multi-tool / cross-vendor integrations for Capella, Rhapsody, Sparx, DOORS, ReqIF, or Simulink
- Generic matrix/table support beyond the existing refine/derive matrix family
- Remote auth / hosted service packaging
- Full bulk-operation redesign
- Broad UAF or DoD breadth beyond what is needed to support the new semantic layer

## Key Decisions

### 1. Add explicit state-machine semantics tools instead of overloading generic specification writes

Rationale:
- `SpecificationHandler` only exposes a narrow standard-property surface today.
- Transition triggers, signal events, change events, and `entry` / `do` / `exit` behaviors are typed semantics, not generic string properties.
- Explicit tools will be easier for MCP clients to use correctly and easier to validate in tests.

### 2. Keep semantic validators primarily Python-side unless missing data forces new read endpoints

Rationale:
- The repo already has a Python verification layer.
- Most of the new checks can compose existing reads from `query_elements`, `get_relationships`, `get_specification`, `list_diagram_shapes`, and diagram images.
- This keeps the Java surface smaller and lets the release ship faster.

### 3. Reuse the methodology/runtime stack instead of inventing a parallel planner

Rationale:
- The existing methodology pack machinery already produces guidance, conformance, and review packets.
- This release should deepen that layer with MBSE-semantic recipes rather than fork it.

### 4. Keep the major-release wedge Cameo-first and semantics-first

Rationale:
- The immediate pain is incorrect artifacts, not insufficient vendor breadth.
- Shipping a strong Cameo semantic copilot is a better major release than shipping a thin cross-tool story.

## Implementation Units

## 1. Structured State-Machine Semantics

### Outcome

Add first-class MCP support for:

- transition triggers
- change events
- signal events
- state `entry`, `do`, and `exit` behaviors

### Files

- `plugin/src/com/claude/cameo/bridge/HttpBridgeServer.java`
- `plugin/src/com/claude/cameo/bridge/util/BridgeCapabilities.java`
- `plugin/src/com/claude/cameo/bridge/handlers/StateMachineHandler.java` (new)
- `mcp-server/cameo_mcp/client.py`
- `mcp-server/cameo_mcp/server.py`

### Tests

- `mcp-server/tests/test_client.py`
- `mcp-server/tests/test_server.py`
- `mcp-server/tests/test_state_machine_semantics.py` (new)
- `plugin/src/test/java/com/claude/cameo/bridge/handlers/StateMachineHandlerTest.java` (new if practical in current Java test setup)

### Tasks

- Define explicit tool contracts:
  - `cameo_set_transition_trigger(...)`
  - `cameo_set_state_behaviors(...)`
- Add Java endpoints for structured trigger/event and state-behavior mutation.
- Add readback support sufficient to verify the values just written.
- Expose the new capabilities through the Python client and MCP tool layer.
- Extend the capability manifest so version skew is caught before these tools are used.

### Acceptance Criteria

- A client can assign a Change Event trigger to a transition without using macros.
- A client can assign a Signal Event trigger backed by a `Signal` element without using macros.
- A client can set and read back `entry`, `do`, and `exit` behavior payloads for a `State`.
- The resulting state machine no longer requires blank internal behavior compartments as placeholders.

## 2. Semantic Validation Layer

### Outcome

Add validators that catch the exact failure modes seen in the MBSE review.

### Files

- `mcp-server/cameo_mcp/verification.py`
- `mcp-server/cameo_mcp/server.py`
- `mcp-server/cameo_mcp/methodology/runtime.py`
- `mcp-server/cameo_mcp/methodology/service.py`
- `plugin/src/com/claude/cameo/bridge/handlers/ElementQueryHandler.java` (only if extra read data is needed)

### Tests

- `mcp-server/tests/test_verification.py`
- `mcp-server/tests/test_semantic_validation.py` (new)
- `mcp-server/tests/test_methodology_runtime.py`

### Tasks

- Add `verify_activity_flow_semantics`:
  - initial and final node presence
  - action reachability
  - disconnected islands
  - control-flow / object-flow continuity
  - swimlane sanity checks
- Add `verify_port_boundary_consistency`:
  - misplaced flow properties
  - duplicated artifacts on the wrong port/interface boundary
  - interface ownership mismatches
- Add `verify_requirement_quality`:
  - blank requirement bodies
  - missing measurable text
  - missing IDs where required
- Add `verify_cross_diagram_traceability`:
  - activity-to-port-BDD consistency
  - activity-to-IBD item-flow mapping
  - requirements-to-architecture trace presence
- Expose MCP tools for these checks where it improves usability.

### Acceptance Criteria

- The validator flags the activity-diagram “right nouns, wrong flow” failure before release.
- The validator flags “Available Slots on the wrong interface/port” before release.
- The validator flags blank requirements bodies before release.
- The validator can produce a review-ready summary consumable by methodology review packets.

## 3. Methodology Recipes and Semantic Layout Profiles

### Outcome

Turn the bridge from primitive operations into repeatable MBSE workflows for the logical-architecture workflow class of work.

### Files

- `mcp-server/cameo_mcp/methodology/registry.py`
- `mcp-server/cameo_mcp/methodology/runtime.py`
- `mcp-server/cameo_mcp/methodology/service.py`
- `mcp-server/cameo_mcp/server.py`
- `mcp-server/cameo_mcp/client.py`
- `plugin/src/com/claude/cameo/bridge/handlers/DiagramHandler.java`
- `plugin/src/com/claude/cameo/bridge/util/BridgeCapabilities.java`

### Tests

- `mcp-server/tests/test_methodology_registry.py`
- `mcp-server/tests/test_methodology_runtime.py`
- `mcp-server/tests/test_methodology_service.py`
- `mcp-server/tests/test_layout_profiles.py` (new)

### Tasks

- Add recipes for the workflow slice represented in the transcript corpus:
  - logical activity flow
  - logical port BDD
  - logical IBD traceability
  - logical part requirements diagram
  - logical state machine starter
- Add semantic layout profiles:
  - `swimlane`
  - `traceability-ladder`
  - `subject-with-usecases` if still only implicit/test-only
- Add an MCP entry point such as `cameo_apply_layout_profile(...)`.
- Extend review packets so they include semantic-validator findings, not just existence and visual checks.
- Ensure recipe output includes explicit assumptions when a diagram cannot be made semantically complete automatically.

### Acceptance Criteria

- A recipe can create a coherent activity starter that passes semantic validation.
- A layout profile can reorganize an activity or IBD diagram into a more reviewable structure than raw `auto_layout`.
- Review packets highlight missing semantic traceability, not just missing artifacts.

## 4. Benchmark-Driven Hardening

### Outcome

Lock the release against the MBSE transcript corpus and the specific failure modes that motivated this work.

### Files

- `mcp-server/scripts/live_validate_mbse_methodology.py` (new)
- `mcp-server/scripts/live_validate_flow_properties.py`
- `mcp-server/tests/fixtures/mbse/` (new fixture directory)
- `mcp-server/tests/test_verification.py`
- `mcp-server/tests/test_server.py`

### Tests

- `mcp-server/tests/test_verification.py`
- `mcp-server/tests/test_server.py`
- `mcp-server/tests/test_mbse_methodology_release.py` (new)

### Tasks

- Add fixture material derived from the reviewed transcript corpus.
- Add a live validation script that exercises the workflow end to end against a running Cameo project.
- Add regression cases for:
  - disconnected activity flow
  - wrong port ownership
  - unreadable IBD trace mapping
  - blank state behaviors
  - blank requirement text
- Add release-gate checks so the major version cannot ship without these passing.

### Acceptance Criteria

- The release has a repeatable benchmark run tied to the corpus that motivated the work.
- Regressions in any of the five known failure modes fail CI or the documented release checklist.

## 5. Release Packaging and Docs

### Outcome

Ship this as a major version with a clear product story: semantic MBSE copilot for Cameo.

### Files

- `README.md`
- `mcp-server/pyproject.toml`
- `plugin/src/com/claude/cameo/bridge/util/BridgeCapabilities.java`
- `docs/ideation/2026-03-30-dod-advanced-capabilities-roadmap.md` (if outcome notes are added)
- `docs/plans/2026-04-12-semantic-mbse-major-release.md`

### Tests

- No new test-only files beyond the release-gate checks above.

### Tasks

- Bump major version across Python and plugin metadata.
- Update README tool reference and limitations sections.
- Document the new semantic tools and the new review/validation workflow.
- Write concise release notes anchored in the five concrete failure modes now addressed.

### Acceptance Criteria

- The README explains the new semantic capabilities clearly.
- The capability manifest reflects the shipped tool surface.
- The release can be announced as a major improvement without overselling cross-tool or hosted capabilities.

## Sequencing

### Milestone 1: API and Validation Foundation

- Finalize tool design for state-machine semantics.
- Finalize semantic-validator contracts and output shapes.
- Add or confirm any missing read support needed by the validators.

Dependency:
- Everything else depends on the API contracts from this milestone.

### Milestone 2: Structured State-Machine Semantics

- Implement Java endpoints and Python MCP tools.
- Add unit tests and readback verification.

Dependency:
- Should land before recipe work so recipes can rely on structured state semantics.

### Milestone 3: Semantic Validators

- Implement activity, port, requirement, and cross-diagram validators.
- Integrate them into review packets.

Dependency:
- Can proceed in parallel with recipe drafting once the result schemas are stable.

### Milestone 4: Recipes and Layout Profiles

- Add major workflow recipes.
- Add semantic layout profiles.
- Wire validators into recipe output and review packets.

Dependency:
- Benefits from Milestones 2 and 3 being substantially complete.

### Milestone 5: Benchmarking, Docs, and Release

- Add benchmark fixtures and live validation.
- Update docs.
- Bump versions and prepare release notes.

## Risks

- Scope creep into generic MBSE platform work rather than the semantic Cameo wedge
- Overloading the spec layer instead of adding explicit typed semantics
- Building validators that only check presence instead of meaningful correctness
- Letting layout work dominate the release before the semantic checks are stable
- Shipping a major version without a benchmark tied to the motivating failures

## Release Readiness Checklist

- [ ] Structured state-machine semantics are available without macros
- [ ] Semantic validators exist for all five motivating failure classes
- [ ] At least one logical-architecture recipe can produce a reviewable artifact bundle
- [ ] Layout profiles improve readability beyond raw auto-layout for the target workflows
- [ ] Benchmark-driven regression coverage exists
- [ ] README and capability manifest are updated
- [ ] Major version numbers are aligned across Python and plugin surfaces

## Deferred Backlog

- Capella / Rhapsody / Sparx / DOORS / Simulink interoperability
- Generic matrix/table artifact support
- Bulk operation protocol redesign
- Hosted/multi-user/authenticated deployment mode
- Model change notification or subscription APIs

## Suggested Execution Order

1. Finalize the explicit state-machine API design.
2. Land the state-machine handler and MCP tools.
3. Land semantic validators in Python.
4. Add one recipe plus one layout profile and prove they use the validators.
5. Add benchmark-driven live validation.
6. Update docs and cut the major release.
