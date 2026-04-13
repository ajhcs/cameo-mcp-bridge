# Semantic MBSE Major Release

Date: 2026-04-12
Release: `2.0.0`

## Summary

This release is the first semantics-first major version of the Cameo MCP Bridge. The bridge already handled low-level model CRUD, diagrams, and requirement matrices well. What it lacked was a reliable layer for MBSE correctness: connected activity logic, clean port/interface boundaries, non-empty requirements, cross-diagram traceability, and explicit state-machine semantics.

Version `2.0.0` closes that gap enough to position the product as a practical OOSEM copilot for bounded Cameo workflows.

## Shipped

### 1. Structured state-machine semantics

- Added explicit tools for reading and writing transition triggers
- Added explicit tools for reading and writing state `entry`, `do`, and `exit` behaviors
- Kept the implementation Cameo-first by using the existing macro bridge behind a typed MCP surface

### 2. Semantic validators

- Activity-flow validator for connected behavior, reachability, and swimlane sanity
- Port-boundary validator for duplicate flow-property ownership and direction conflicts
- Requirement-quality validator for IDs, text presence, and measurable content
- Cross-diagram traceability validator for activity, interface, IBD, and requirements-to-architecture coverage

### 3. Methodology integration

- Semantic validators now run as part of methodology recipe validation and execution
- Conformance reports now merge structural and semantic findings
- Evidence bundles and review packets now include semantic validation results

### 4. New OOSEM starter recipes

- `logical_activity_flow`
- `logical_port_bdd`
- `logical_ibd_traceability`

These recipes are intentionally bounded. They generate reviewable starters that can be judged against semantic checks, rather than pretending to fully solve every modeling decision automatically.

### 5. Pre-cut stabilization

- Replaced the interface-flow-property macro read path with a native plugin endpoint so port-boundary and cross-diagram validation run on a typed Java bridge path
- Fixed activity-edge creation and relationship reads so `logical_activity_flow` works cleanly on a live Cameo model instead of only under mocked tests
- Added a guarded swimlane fallback for `ActivityPartition` placement while a first-class Java swimlane endpoint remains on the broader migration roadmap
- Tightened traceability matching and port-direction conflict checks to better align with the Module 11 logical activity / logical port / logical IBD demo flow
- Completed a clean live smoke against a real Cameo session for:
  - `logical_activity_flow`
  - `logical_port_bdd`
  - `logical_ibd_traceability`

## Why This Is A Major Release

The core product promise changed:

- Before: strong generic bridge into Cameo
- Now: semantic MBSE copilot for bounded OOSEM work in Cameo

The new release adds a layer of typed semantic operations, semantic validators, recipe-level conformance, and reviewable evidence. That is a material capability boundary, not just incremental tool count growth.

## Compatibility

- Python MCP server version: `2.0.0`
- Plugin version: `2.0.0`
- API version: `v1`
- Handshake version: `1`

Plugin/server version lockstep is still required.

## Recommended First Workflow

1. Start with an OOSEM methodology recipe instead of raw element creation.
2. Generate the starter artifact.
3. Inspect the review packet and semantic validation section.
4. Fix the reported semantic gaps before treating the artifact as review-ready.

## Follow-on Migration

The major release is stable enough to cut, but the broader cleanup still remains:

- promote the remaining macro-backed state-machine semantics to Java-native handlers
- replace the temporary `ActivityPartition` fallback with a dedicated swimlane endpoint
- make runtime result binding fully typed instead of heuristic
- add a repeatable live regression harness for the core OOSEM demo flows
