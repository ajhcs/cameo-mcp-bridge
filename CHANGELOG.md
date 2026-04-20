# Changelog

## 2.3.3 - 2026-04-20

Patch release that consolidates internal naming on neutral methodology terminology and cleans residual mentions from the tracked docs surface.

### Changed

- Consolidated the internal workflow module on the `cameo_mcp.methodology_workflows` name; the public MCP tool surface is unchanged
- Updated README section heading and tool descriptions to use methodology-workflow wording
- Rewrote tracked release notes, plan docs, and changelog entries to use methodology/package terminology throughout
- Bumped the in-repo Python/plugin/methodology compatibility line to `2.3.3`

## 2.3.2 - 2026-04-20

Patch release focused on live-verifiable native matrix coverage, neutral methodology naming, and Codex workspace productization.

### Added

- A repo-local Codex plugin scaffold with marketplace metadata, MCP launcher wiring, and a verification-first live-validation skill
- A neutral physical-architecture competency execution plan under `docs/plans/2026-04-20-physical-architecture-competency-plan.md`

### Fixed

- Repaired native `Refine Requirement Matrix` population by binding `Refine` relationships to the requirements-profile stereotype that Cameo's matrix criteria actually consume
- Updated the live matrix regression harness to validate the live-proven activity-to-requirement refine shape instead of the earlier speculative row domains
- Corrected `Dependency` ownership so generic dependency creation resolves to a package owner instead of trying to attach to arbitrary source elements
- Corrected stale README tool-count claims so the documented MCP surface matches the actual bridge capability manifest

### Changed

- Bumped the in-repo Python/plugin/methodology compatibility line to `2.3.2`

## 2.3.1 - 2026-04-13

Patch release focused on hardening the new diagram-repair surface introduced in `2.3.0`.

### Fixed

- Restored the missing `RepairDefaults.hiddenLabelKeys` field so the plugin compiles cleanly after the `2.3.0` repair-endpoint additions
- Wrapped `setPresentationElementProperties(...)` and `resetLabelPositions(...)` on the affected repair/property paths so Cameo builds with checked exceptions compile correctly
- Changed diagram-repair batches to fail soft per target instead of aborting the entire request on the first unsupported presentation element
- Excluded comment/note presentations from allocation-compartment normalization candidates
- Improved transition/item-flow presentation receipts to report partial support explicitly when a Cameo build exposes only a subset of the requested properties
- Corrected `repairLabelPositions` receipts and `updatedCount` reporting for processed targets

### Changed

- Bumped the in-repo Python/plugin/methodology compatibility line to `2.3.1`

## 2.3.0 - 2026-04-13

Minor release focused on reducing end-to-end human intervention for review, cleanup, and methodology package workflows.

### Added

- Intent-level diagram presentation APIs for transition labels, item-flow labels, and allocation/full-port compartments
- A built-in bridge probe on the Python side so clients can discover whether local health lives at `/status` or `/api/v1/status`
- Legacy `/status` and `/capabilities` HTTP aliases alongside the versioned `/api/v1/...` endpoints
- Native diagram repair endpoints for hidden labels, label-position resets, conveyed-item labels, and diagram-type-aware compartment presets
- Python-side proofing helpers and MCP tools for requirements, comments, state/transition names, and diagram text, including preview patch plans and optional safe auto-apply
- Methodology workflow helpers and MCP tools for comparing expected artifacts, validating package scope, exporting required diagrams, and assembling PPT/PDF submission bundles
- Semantic auto-remediation planning that converts cross-diagram validation findings into previewable receipts and `patchPlan.steps`
- `python-pptx` as an MCP-server dependency so PPTX assembly can be automated instead of remaining a manual post-step

### Fixed

- Enum-valued stereotype tagged values now resolve actual `EnumerationLiteral` instances by ID or name instead of falling through the generic JSON coercion path
- `set_specification` now benefits from the same stereotype enum coercion path as `set_tagged_values`
- Direct Python client consumers can now omit, resize, transcode, page, filter, and summarize large diagram payloads instead of reimplementing the MCP-side shaping logic
- `ibd` / `bdd` artifact kinds now participate correctly in methodology export/assembly flows instead of being dropped as non-diagrams
- The bridge capability manifest now advertises the new diagram repair endpoints alongside the earlier presentation presets

### Changed

- Bumped the in-repo Python/plugin/methodology compatibility line to `2.3.0`
- Expanded the README tool reference to document repair, proofing, methodology workflow, and remediation surfaces

## 2.1.0 - 2026-04-13

Minor release focused on hardening the MCP contract around diagram inspection and activity swimlane editing.

### Added

- CamelCase compatibility aliases for common MCP arguments such as `diagramId`, `elementId`, `parentId`, `ownerId`, and `containerPresentationId` on the affected Python tools
- Token-safe diagram export controls on `cameo_get_diagram_image`, including metadata-only responses plus optional resize and JPEG/WEBP transcoding
- Paging, filtering, nested-parent filtering, and summary-only shape inventory support on `cameo_list_diagram_shapes`
- Regression coverage for MCP schema aliases, diagram response shaping, and the guarded activity-partition fallback path

### Fixed

- Stopped the `ActivityPartition` macro fallback from deleting and rebuilding an existing swimlane container when it cannot safely resolve the partition presentation
- Forced integer rectangle dimensions in the swimlane fallback so Groovy no longer produces `Rectangle(Integer, Integer, Double, Double)` constructor failures
- Corrected the effective scope contract for `cameo_query_elements` so owner/root/package ID aliases reach the underlying bridge as element IDs

### Changed

- Bumped the Python MCP server, plugin, and OOSEM methodology pack release line to `2.1.0`
- Updated the README and release notes to document the safer large-diagram workflow and the new argument/shape-handling behavior

## 2.0.0 - 2026-04-12

Major release focused on semantic MBSE support for Cameo-based OOSEM workflows.

### Added

- Structured state-machine semantics tools for transition triggers and state `entry` / `do` / `exit` behaviors
- Semantic validation tools for activity-flow coherence, port/interface boundary consistency, requirement quality, and cross-diagram traceability
- OOSEM methodology recipes for logical activity flows, logical port BDDs, and logical IBD traceability views
- Methodology runtime integration so semantic-validator failures appear in conformance results, evidence bundles, and review packets
- Release notes for the semantic MBSE major release in `docs/releases/2026-04-12-semantic-mbse-major-release.md`

### Changed

- Bumped the MCP server, plugin, and OOSEM pack release line to `2.0.0`
- Expanded the README to document the new semantic-validation and state-semantics tool surface
- Improved review packet output to summarize semantic validators and highlight the failing evidence behind each validator
- Hardened the live bridge for the `2.0.0` cut by fixing activity-edge ownership/query behavior, replacing the interface-flow-property macro read with a native plugin endpoint, and tightening port/IBD validator matching against live Cameo models

### Stabilized Before Cut

- Added a native plugin read path for interface blocks and owned flow properties so port-boundary and cross-diagram traceability validation no longer depend on Groovy macros
- Fixed live activity-flow execution by attaching `ControlFlow` / `ObjectFlow` to the owning `Activity` and exposing `ActivityEdge` reads through `cameo_get_relationships`
- Added a guarded `ActivityPartition` fallback path so swimlane placement works reliably until the swimlane path is promoted to a dedicated Java endpoint
- Verified the release end to end against a real Cameo session with clean live smoke for `logical_activity_flow`, `logical_port_bdd`, and `logical_ibd_traceability`

### Product Story

This release moves the project from a strong generic Cameo bridge toward a semantic MBSE copilot: one that can now help create, validate, and package reviewable OOSEM artifacts instead of only manipulating notation.
