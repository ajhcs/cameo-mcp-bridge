# Changelog

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
