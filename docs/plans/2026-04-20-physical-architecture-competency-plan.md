# Plan: Physical Architecture Competency + Codex Plugin Execution

**Generated**: 2026-04-20
**Estimated Complexity**: High

## Overview
Make `cameo-mcp-bridge` operationally capable of:

- creating and validating the full physical-architecture artifact family end to end
- reproducing the relevant engineer workflows from the external reference corpus without baking course naming into the product
- proving correctness with live Cameo validation instead of static claims
- staying token-efficient inside the Codex app through compact reads, review packets, and plugin-local guidance
- shipping as a repo-local Codex plugin that can start the MCP server and steer agents into verification-first behavior

This plan supersedes the narrower physical-architecture-only scope. It treats capability coverage, live verifiability, token compression, and Codex productization as one backlog.

## Current Baseline
- Live bridge probing is established: health, capabilities, and open-project checks are already part of the working loop.
- Native matrix support is live for `derive`, `satisfy`, and `allocation`.
- `Refine Requirement Matrix` still needs live repair so matrix coverage is not yet uniformly healthy.
- The repo already has reusable verification, semantic validation, methodology helpers, and a repo-local Codex plugin scaffold.

## Mandatory Outcomes
- A live Cameo run can create or validate the physical-architecture artifact set expected by the reference corpus.
- The same system can follow the reference workflow shapes, not just approximate their outputs.
- Every readiness claim is backed by machine-readable receipts, targeted live probes, or exported evidence.
- Codex app usage stays compact by default: probe first, read narrowly, escalate to heavy payloads only when needed.
- The workspace exposes a first-class Codex plugin with local MCP startup and a thin skill layer.

## Prerequisites
- CATIA Magic / Cameo Systems Modeler 2024x with the repo plugin deployed
- Java 17 available for plugin rebuild/deploy
- Python environment for `mcp-server`
- A live Cameo project open during validation
- The external reference corpus remains available outside the repo as the competency contract

## Sprint 1: Productize Codex Entry Points
**Goal**: Turn the repo into a usable Codex plugin and encode compact, verification-first usage patterns.
**Demo/Validation**:
- Codex can see the plugin in the workspace marketplace
- The plugin starts the local MCP server successfully
- A Codex session can run `cameo_probe_bridge`, `cameo_status`, and `cameo_get_project` through the plugin path

### Task 1.1: Finalize Repo-Local Plugin Manifest
- **Location**: `plugins/cameo-mcp-bridge/.codex-plugin/plugin.json`, `.agents/plugins/marketplace.json`
- **Description**: Replace scaffold placeholders with the real repo metadata, Codex-facing descriptions, and marketplace entry.
- **Dependencies**: None
- **Acceptance Criteria**:
  - Manifest uses the real plugin name and current version line
  - Marketplace entry resolves to `./plugins/cameo-mcp-bridge`
  - No dead `hooks` or `apps` placeholders remain
- **Validation**:
  - Open manifests and confirm paths and metadata are internally consistent

### Task 1.2: Add a Local MCP Launcher
- **Location**: `plugins/cameo-mcp-bridge/.mcp.json`, `plugins/cameo-mcp-bridge/scripts/run-cameo-mcp-server.ps1`
- **Description**: Start `cameo_mcp.server` from the repo with a predictable local launcher that prefers the repo venv and fails loudly if the install is broken.
- **Dependencies**: Task 1.1
- **Acceptance Criteria**:
  - `.mcp.json` points to the launcher
  - The launcher resolves the repo root and `mcp-server` relative to itself
  - Missing venv/package state produces a clear failure message
- **Validation**:
  - Run the launcher directly in PowerShell
  - Verify the process starts `cameo_mcp.server`

### Task 1.3: Add a Token-Efficient Live Validation Skill
- **Location**: `plugins/cameo-mcp-bridge/skills/cameo-live-validation/`
- **Description**: Add one thin skill that encodes probe-first, compact-read, verification-first operating behavior for Codex sessions.
- **Dependencies**: Task 1.2
- **Acceptance Criteria**:
  - Skill tells agents to separate bridge health from open-project readiness
  - Skill biases toward compact views, filtered reads, and verification tools before heavy payloads
  - Skill points at the existing live scripts only for true smoke/regression work
- **Validation**:
  - Review the skill text and ensure it matches the repo’s actual tools and scripts

### Task 1.4: Smoke the Plugin End-to-End in Codex
- **Location**: Codex app, live workspace
- **Description**: Confirm the plugin installs cleanly, starts the MCP server, and exposes the expected bridge behavior in-app.
- **Dependencies**: Tasks 1.1-1.3
- **Acceptance Criteria**:
  - Plugin appears in the workspace marketplace
  - MCP startup succeeds from the plugin launcher
  - Probe/status/project checks work from the plugin path
- **Validation**:
  - Live Codex plugin smoke in this workspace

## Sprint 2: Convert the Reference Corpus into a Regression Contract
**Goal**: Turn the external captions, slides, and examples into explicit machine-checkable expectations without carrying their course naming into the repo.
**Demo/Validation**:
- Repo contains a checklist or fixture mapping each reference workflow to concrete artifacts, operations, and validators

### Task 2.1: Build a Reference-Workflow Capability Matrix
- **Location**: `docs/plans/`, `mcp-server/scripts/` or `mcp-server/tests/fixtures/`
- **Description**: Encode the relevant workflow slices into a normalized checklist of required packages, diagrams, matrices, structural fields, and semantic expectations.
- **Dependencies**: Sprint 1 complete
- **Acceptance Criteria**:
  - Every external workflow maps to explicit bridge capabilities and expected model evidence
  - Package-structure expectations are captured, not just artifact outputs
- **Validation**:
  - Manual review against the external reference corpus

### Task 2.2: Add a Non-Mutating Capability Inventory Script
- **Location**: `mcp-server/scripts`
- **Description**: Add a live script that inventories whether the open project already contains the packages, artifacts, and readback richness required by the physical-architecture reference workflows.
- **Dependencies**: Task 2.1
- **Acceptance Criteria**:
  - Script reports supported, partial, missing, and blocked states
  - Output includes exact artifact IDs/names and missing semantic fields
- **Validation**:
  - Live run against the ATM model

### Task 2.3: Repair the Refine Matrix Regression
- **Location**: `mcp-server/scripts/live_validate_matrices.py`, `plugin/src/com/claude/cameo/bridge/handlers/MatrixHandler.java`, related relationship/readback paths as needed
- **Description**: Keep matrix assertions split by kind so working paths stay green while the `Refine Requirement Matrix` path is repaired and revalidated.
- **Dependencies**: None
- **Acceptance Criteria**:
  - Live matrix validation reports per-kind pass/fail instead of one collapsed result
  - `derive`, `satisfy`, and `allocation` remain live-positive
  - `refine` returns the expected populated cells in a live run
- **Validation**:
  - Live run of `live_validate_matrices.py` against the ATM model

### Task 2.4: Add Package-Structure Validation
- **Location**: `mcp-server/cameo_mcp/rubric_workflows.py`, `verification.py`
- **Description**: Validate physical-architecture definition and traceability container structure so missing or misplaced packages are reported explicitly.
- **Dependencies**: Task 2.1
- **Acceptance Criteria**:
  - Missing or misplaced packages are reported explicitly
  - Results can feed later package-level readiness gates
- **Validation**:
  - Unit tests plus live package validation

## Sprint 3: Close the Remaining Bridge Semantics Gaps
**Goal**: Expose the missing physical-architecture data needed to model and validate what the reference workflows expect.
**Demo/Validation**:
- Rebuild and redeploy the plugin
- Exercise each new or extended endpoint against a scratch package in a live Cameo project

### Task 3.1: Add First-Class Typed Part and Port Mutation/Readback
- **Location**: `plugin/src/com/claude/cameo/bridge/handlers/ElementMutationHandler.java`, `plugin/src/com/claude/cameo/bridge/handlers/ElementQueryHandler.java`, `mcp-server/cameo_mcp/client.py`, `mcp-server/cameo_mcp/server.py`
- **Description**: Extend the bridge so `Property`, `Port`, and `FlowProperty` can be fully defined and read back with `typeId`, direction, multiplicity where needed, `represents`, and conjugation semantics.
- **Dependencies**: Sprint 2 complete
- **Acceptance Criteria**:
  - Typed parts, ports, and flow properties can be created and then queried without fallback macros
  - Readback exposes the same fields needed for physical port BDD and physical IBD validation
- **Validation**:
  - Unit tests
  - Live creation/readback of representative port and flow-property patterns

### Task 3.2: Strengthen Connector and Item-Flow Readback
- **Location**: `plugin/src/com/claude/cameo/bridge/handlers/RelationshipHandler.java`, `plugin/src/com/claude/cameo/bridge/handlers/ElementQueryHandler.java`
- **Description**: Expand connector, information-flow, and item-flow serialization so validators can see connector ends, `partWithPort`, conveyed items, and directionality.
- **Dependencies**: Task 3.1
- **Acceptance Criteria**:
  - Connector responses are rich enough to validate the physical IBD chain end to end
  - Item-flow responses expose the typed items and direction used by the reference workflows
- **Validation**:
  - Targeted tests
  - Live readback of a representative end-to-end flow chain

### Task 3.3: Normalize Physical Diagram Creation Patterns
- **Location**: `mcp-server/cameo_mcp/client.py`, `server.py`, diagram helpers as needed
- **Description**: Make sure the bridge surface can drive the common creation patterns used in the reference corpus for physical BDDs, IBDs, activity diagrams, and state machines without excessive macro fallback.
- **Dependencies**: Tasks 3.1-3.2
- **Acceptance Criteria**:
  - Physical artifact creation can be expressed with stable MCP calls
  - Remaining macro-only gaps are isolated and documented as explicit exceptions
- **Validation**:
  - Live scratch creation of representative physical diagrams

## Sprint 4: Add a Physical Architecture Product Layer
**Goal**: Turn the low-level bridge into a first-class physical-architecture workflow surface with recipes, validators, and compact review output.
**Demo/Validation**:
- Run the physical workflow against a package and get a reviewable status for every required artifact

### Task 4.1: Add a Physical Methodology Pack
- **Location**: `mcp-server/cameo_mcp/methodology/registry.py`, `methodology/service.py`, `server.py`
- **Description**: Extend the current methodology layer with a physical tranche covering physical architecture BDD, physical activity, physical I/O definition, physical port definition, physical IBD, physical state machine, physical specification BDD, physical requirements, allocation matrix, satisfy matrix, and derive matrix.
- **Dependencies**: Sprint 3 complete
- **Acceptance Criteria**:
  - The physical workflow is discoverable through methodology tools
  - Each required artifact has an explicit recipe or expected-artifact definition
  - Guidance can explain what is missing next
- **Validation**:
  - `cameo_list_methodology_packs`
  - `cameo_get_methodology_pack`
  - `cameo_get_methodology_guidance`

### Task 4.2: Add Physical-Specific Validators
- **Location**: `mcp-server/cameo_mcp/verification.py`, `semantic_validation.py`, `server.py`
- **Description**: Add validators for physical decomposition completeness, port-definition consistency, IBD connector/item-flow coherence, allocation completeness, satisfy coverage, derive coverage, and activity/port/IBD agreement.
- **Dependencies**: Sprint 3 complete
- **Acceptance Criteria**:
  - Failures identify the artifact and mismatch, not just a generic invalid state
  - Requirement headers versus leaf requirements are handled explicitly
  - Validators use bridge readback, not screenshots alone
- **Validation**:
  - Python unit tests
  - Live runs against the reference sample project

### Task 4.3: Add Compact Review and Export Gates
- **Location**: `mcp-server/cameo_mcp/rubric_workflows.py`, `proofing.py`, `README.md`
- **Description**: Gate package validation and evidence export on semantic readiness, and keep the review payload compact enough for Codex app usage.
- **Dependencies**: Tasks 4.1-4.2
- **Acceptance Criteria**:
  - Package validation can report semantic readiness instead of artifact presence only
  - Review packets summarize high-signal findings without dumping large raw payloads
  - Export flows can include validation receipts
- **Validation**:
  - Dry-run and live package-validation runs

## Sprint 5: Build the Full Physical-Architecture Regression Harness
**Goal**: Prove the system can satisfy the external competency requirements against a live Cameo model and replay the reference workflows as evidence.
**Demo/Validation**:
- One live run covers physical-architecture readiness, traceability matrices, and Codex plugin smoke

### Task 5.1: Add a Physical-Architecture Live Validation Runner
- **Location**: `mcp-server/scripts`
- **Description**: Create a dedicated live regression entry point that checks the required artifact family plus the broader reference workflow expectations.
- **Dependencies**: Sprint 4 complete
- **Acceptance Criteria**:
  - Report covers the full physical-architecture artifact set
  - Output distinguishes supported, partial, missing, semantically inconsistent, and blocked states
- **Validation**:
  - Live run in Cameo with the user-provided project

### Task 5.2: Build a Repeatable Evidence Bundle
- **Location**: `mcp-server/cameo_mcp/rubric_workflows.py`, `docs/releases`, `README.md`
- **Description**: Package exported diagrams, matrices, and validation receipts into a repeatable proof point for release readiness.
- **Dependencies**: Task 5.1
- **Acceptance Criteria**:
  - Evidence bundle includes diagram exports, matrix readback, semantic receipts, and plugin smoke receipts
  - README explains how to rerun the proof from a clean session
- **Validation**:
  - Clean rerun from the documentation

### Task 5.3: Release and Drift Control
- **Location**: `CHANGELOG.md`, `docs/releases/`, test suites, plugin manifests
- **Description**: Cut the next release line only after live regression and Codex plugin smoke pass together.
- **Dependencies**: Tasks 5.1-5.2
- **Acceptance Criteria**:
  - Release notes match the actual live-validated behavior
  - No feature is called complete without a matching live or unit validation path
- **Validation**:
  - Final pre-release checklist and live rerun

## Parallel Workstreams
- **Workstream A: Codex productization**
  - Owns plugin packaging, launcher, marketplace metadata, and compact skill guidance
- **Workstream B: Java bridge semantics**
  - Owns typed part/port support, connector/item-flow readback, and deploy/restart validation
- **Workstream C: Python methodology and verification**
  - Owns physical methodology packs, validators, review packets, and package gates
- **Workstream D: Live regression**
  - Owns reference-workflow mapping, capability inventories, end-to-end runners, and evidence bundles

## Dependency Summary
- Sprint 1 can run immediately and in parallel with the mapping work.
- Sprint 2 depends on the external corpus and current repo readback, not on new Java code.
- Sprint 3 depends on Sprint 2 because the workflow contract needs to define the semantic readback gaps precisely.
- Sprint 4 depends on Sprint 3 because physical validators and guidance need the richer bridge payloads.
- Sprint 5 depends on Sprint 4 because end-to-end proof requires both capabilities and validation receipts.

## Testing Strategy
- Keep fast unit tests around matrix-kind parsing, payload validation, launcher behavior, and semantic-check logic.
- Add live validation for artifact families that depend on actual Cameo behavior: physical activity partitions, full ports, item flows, allocation matrices, satisfy matrices, derive matrices, and state-machine triggers.
- Treat the external reference corpus as a private competency contract rather than a product-surface naming source.

## Potential Risks and Gotchas
- Typed port and flow-property semantics may still expose Cameo API edge cases that need native Java handling instead of macro fallback.
- Live deploys are not trustworthy until the plugin is rebuilt, redeployed, and Cameo is fully restarted.
- Workflow parity can fail even when artifact coverage looks good if package structure, row/column direction, or conjugation semantics are wrong.
- Codex plugin packaging is low risk, but it will be noisy if the launcher does not fail clearly on missing local setup.

## Rollback Plan
- Keep plugin packaging isolated under `plugins/` and `.agents/plugins/` so it can be removed without touching the Java bridge.
- Land bridge and Python capability work in small slices that can be reverted independently.
- Treat live smoke scripts as non-destructive by default; scratch-creation tests must clean up created artifacts before completion.
