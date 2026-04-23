# Plan: Cameo Bridge Stabilization

**Generated**: 2026-04-12
**Estimated Complexity**: High

## Overview
This plan hardens the post-`2.0.0` bridge and methodology stack after the live smoke uncovered several abstraction mismatches between the MCP surface and Cameo's actual APIs. The immediate stabilization tranche is now complete for activity partitions, activity edges, diagram path bindings, and live relationship reads. The remaining work is to reduce macro reliance, make operation results explicit instead of heuristic, align the generated OOSEM recipes with the MBSE demo expectations, and add a regression harness that catches these issues before release.

The roadmap is grounded in an external MBSE reference corpus retained outside this repository, especially:
- OOSEM setup and model structure expectations
- stakeholder-needs and workflow expectations
- logical activity, logical port BDD, logical IBD, and requirements traceability flows

## Prerequisites
- Local Cameo / CATIA Magic install with plugin deploy access
- JDK 17 at `D:\DevTools\jdk17\jdk-17.0.18+8`
- Working plugin deploy target at `D:\DevTools\CatiaMagic`
- Live Cameo model available for smoke validation
- Python test environment for `mcp-server`

## Sprint 1: Remove High-Risk Abstraction Gaps
**Goal**: Eliminate the remaining special-case bridge behavior that currently hides behind generic operations or macros.
**Demo/Validation**:
- Rebuild and deploy the plugin
- Run the live smoke against activity, port, and IBD recipes
- Verify no runtime fallbacks are needed for the covered cases

### Task 1.1: Inventory Macro-Backed MCP Surfaces
- **Location**: `mcp-server/cameo_mcp/client.py`, `mcp-server/cameo_mcp/semantic_validation.py`, `mcp-server/cameo_mcp/state_machine_semantics.py`, `plugin/src/com/claude/cameo/bridge/handlers`
- **Description**: Produce a concrete inventory of all user-facing behaviors that still depend on `cameo_execute_macro`, classify them by risk, and identify which should become Java handlers first.
- **Dependencies**: None
- **Acceptance Criteria**:
  - All macro-backed surfaces are listed with owning files
  - Each surface is tagged as read-path, write-path, or mixed
  - Each surface has a migration recommendation
- **Validation**:
  - Manual review of inventory against code search for `execute_macro`

### Task 1.2: Promote Activity Partition Operations to a Java-Native Endpoint
- **Location**: `plugin/src/com/claude/cameo/bridge/handlers/DiagramHandler.java`, `plugin/src/com/claude/cameo/bridge/util/BridgeCapabilities.java`, `mcp-server/cameo_mcp/client.py`, `mcp-server/cameo_mcp/server.py`
- **Description**: Replace the current Python macro fallback for `ActivityPartition` add-to-diagram behavior with a dedicated bridge operation that creates or updates swimlanes explicitly.
- **Dependencies**: Task 1.1
- **Acceptance Criteria**:
  - Swimlane creation/update has a Java-owned bridge path
  - `client.py` no longer needs the `ActivityPartition` macro fallback for the covered use case
  - Activity recipe live smoke passes without macro intervention
- **Validation**:
  - Plugin Gradle test/build
  - Live recipe smoke for `logical_activity_flow`

### Task 1.3: Promote State-Machine Semantic Reads/Writes to Java-Native Endpoints
- **Location**: `plugin/src/com/claude/cameo/bridge/handlers`, `mcp-server/cameo_mcp/state_machine_semantics.py`, `mcp-server/cameo_mcp/server.py`
- **Description**: Replace the macro-backed trigger and state-behavior operations with typed Java handlers so these tools do not depend on Groovy runtime details.
- **Dependencies**: Task 1.1
- **Acceptance Criteria**:
  - Trigger and state-behavior MCP tools call Java handlers directly
  - Macro serialization code for these operations is removed or deprecated
  - Existing tests continue to pass
- **Validation**:
  - Python unit tests for state-machine semantics
  - Live read/write smoke on a test state machine

## Sprint 2: Make Runtime Semantics Explicit
**Goal**: Remove heuristic binding and ambiguous operation outputs so downstream recipe execution is deterministic.
**Demo/Validation**:
- Execute all three OOSEM logical recipes in a clean model
- Inspect receipts and artifact bindings for exact shape/path/model ids

### Task 2.1: Introduce Typed Operation Result Contracts
- **Location**: `mcp-server/cameo_mcp/methodology/runtime.py`, `mcp-server/cameo_mcp/server.py`, `plugin/src/com/claude/cameo/bridge/handlers`
- **Description**: Replace “guess the primary id” behavior with typed result shapes by operation family, especially for `create_diagram`, `add_to_diagram`, `add_diagram_paths`, and relationship creation.
- **Dependencies**: None
- **Acceptance Criteria**:
  - Runtime no longer infers primary ids by field ordering
  - Shape/path-producing operations expose explicit ids for binding
  - Tests cover both diagram and path cases
- **Validation**:
  - Runtime unit tests
  - Live recipe smoke confirms correct downstream bindings

### Task 2.2: Separate Semantic Smoke from Operational Smoke
- **Location**: `mcp-server/cameo_mcp/methodology/service.py`, `mcp-server/cameo_mcp/methodology/registry.py`, `docs/releases/*`, `README.md`
- **Description**: Distinguish “recipe executes successfully” from “generated model is semantically clean” so release validation is not ambiguous.
- **Dependencies**: Task 2.1
- **Acceptance Criteria**:
  - Operational smoke criteria are documented
  - Semantic validation output is reported separately from transport/runtime success
  - Release notes and review packet language reflect the distinction
- **Validation**:
  - Review packet output inspection
  - Release-doc review

### Task 2.3: Add Explicit Relationship Family Reads
- **Location**: `plugin/src/com/claude/cameo/bridge/handlers/ElementQueryHandler.java`, `mcp-server/cameo_mcp/client.py`, `mcp-server/cameo_mcp/semantic_validation.py`
- **Description**: Formalize the bridge read model for activity edges, connectors, directed relationships, and information flows so semantic validators do not depend on incidental serialization behavior.
- **Dependencies**: None
- **Acceptance Criteria**:
  - Relationship responses are complete for the families used by validators
  - Activity edges, connectors, and information flows are all covered by explicit tests
  - Semantic validators no longer need model-specific read workarounds
- **Validation**:
  - Plugin build/test
  - Live relationship read probes

## Sprint 3: Align Recipes with MBSE Demo Expectations
**Goal**: Make the generated OOSEM artifacts closer to the reference modeling intent so semantic findings reflect real gaps, not generator shortcuts.
**Demo/Validation**:
- Generate activity, logical port BDD, and logical IBD examples that resemble the reference workflow flows
- Compare recipe outputs to expected traceability and flow structure

### Task 3.1: Refine Logical Activity Recipe Semantics
- **Location**: `mcp-server/cameo_mcp/methodology/service.py`, `mcp-server/cameo_mcp/verification.py`
- **Description**: Ensure the generated lower-level activity diagrams better match the intended decomposition style from the external reference material, including performer allocation and data/control flow structure.
- **Dependencies**: Sprint 1 complete
- **Acceptance Criteria**:
  - Generated activity recipes pass operational smoke
  - Semantic findings, if any, reflect genuine modeling gaps rather than generator omissions
- **Validation**:
  - Live activity smoke
  - Review packet inspection against the logical activity reference

### Task 3.2: Refine Logical Port BDD Generation
- **Location**: `mcp-server/cameo_mcp/methodology/service.py`, `mcp-server/cameo_mcp/verification.py`
- **Description**: Revisit interface-block and port generation so the default scratch outputs more closely match the logical port BDD demo semantics, especially around duplicated flow-property naming and direction modeling.
- **Dependencies**: Sprint 2 complete
- **Acceptance Criteria**:
  - Default recipe output can be configured to avoid trivial semantic conflicts
  - Validation guidance explains when same-name opposite-direction flows are acceptable vs problematic
- **Validation**:
  - Live `logical_port_bdd` smoke
  - Comparison against the logical port BDD reference

### Task 3.3: Refine IBD Traceability Generation
- **Location**: `mcp-server/cameo_mcp/methodology/service.py`, `mcp-server/cameo_mcp/verification.py`, `mcp-server/cameo_mcp/semantic_validation.py`
- **Description**: Improve connector/item-flow generation and traceability expectations so the IBD recipe better aligns with the demo flow from activity to port BDD to IBD.
- **Dependencies**: Tasks 3.1 and 3.2
- **Acceptance Criteria**:
  - Cross-diagram traceability checks align with the generated artifact set
  - Default recipe output demonstrates the intended coverage chain
- **Validation**:
  - Live `logical_ibd_traceability` smoke
  - Comparison against the logical IBD and requirements traceability references

## Sprint 4: Add Release-Grade Regression Harness
**Goal**: Catch bridge/modeling regressions before release by combining unit, integration, and live smoke validation.
**Demo/Validation**:
- One command or documented short sequence runs the regression harness and reports pass/fail by layer

### Task 4.1: Build a Live Smoke Harness for the Core Demo Paths
- **Location**: `mcp-server/scripts`, `docs/plans`, `README.md`
- **Description**: Consolidate the ad hoc live validation scripts into a stable harness that exercises activity, logical port BDD, logical IBD, state-machine semantics, and semantic validators.
- **Dependencies**: Sprints 1-3
- **Acceptance Criteria**:
  - Harness is checked in and documented
  - It reports both operational status and semantic status
  - It cleans up scratch artifacts on success and failure
- **Validation**:
  - Manual run against a live Cameo instance

### Task 4.2: Add Java-Side Integration Tests for Bridge Edge Cases
- **Location**: `plugin/src/test/java`
- **Description**: Expand beyond capability tests to cover relationship reads/writes, diagram path routing, and compartment visibility behaviors that have already regressed once.
- **Dependencies**: Sprint 1 and Sprint 2 complete
- **Acceptance Criteria**:
  - At least one integration-style test covers each of: activity edges, path routing, relationship reads, and compartment updates
  - Failing behavior can be reproduced without manual live-model spelunking
- **Validation**:
  - `gradlew.bat test`

## Testing Strategy
- Keep fast Python unit tests for runtime binding, recipe generation, and semantic normalization.
- Add Java-side handler tests for bridge-specific type/serialization behavior.
- Maintain a live smoke harness for Cameo-only behavior that cannot be trusted from mocks.
- For each sprint, separate:
  - operational success checks
  - semantic/model-quality checks
  - release compatibility checks

## Potential Risks & Gotchas
- Cameo concepts that look generic in UML are not always generic in the API; each new abstraction should be verified against a live model.
- Macro removal may expose hidden assumptions in the current methodology recipes.
- Semantic validators may encode domain-specific modeling expectations that need configurability rather than one fixed rule set.
- The plugin rebuild/deploy/restart loop remains expensive, so Java-side changes should be batched carefully.

## Rollback Plan
- Revert plugin handler changes if a Java-side stabilization patch regresses the live bridge.
- Keep the current macro-backed fallbacks available until their Java replacements are validated live.
- If typed result contracts cause downstream breakage, gate them behind a compatibility layer in `runtime.py` until all callers are migrated.
