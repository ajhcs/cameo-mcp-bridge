# Autopilot Surface And Relation Map Evidence Release

Date: 2026-05-05
Release: `2.3.5`

## Summary

This release expands the bridge from core model editing into a broader, evidence-first CATIA Magic automation surface. Version `2.3.5` adds native Relation Map inspection and rendering workflows, UI-state introspection, snapshot/diff evidence capture, native validation wrappers, Report Wizard generation, and guarded optional-product probes for Teamwork, DataHub, simulation, variants, profiles, typed diagrams, and safety/cyber extensions.

The main design choice is fail-closed automation: advanced routes report capability gaps, previews, refusals, and live evidence instead of pretending optional CATIA plugins are always installed or safe to write through.

## Shipped

### 1. Relation Map evidence workflow

- Added native Relation Map create/configure/read endpoints and MCP tools
- Added criteria templates, criteria application, graph readback, presentation listing, render, verify, compare, expand, collapse, and explicit refresh routes
- Added raw `GraphSettings` and presentation-property dumps for before/after UI investigation
- Kept native refresh opt-in after live validation showed it can block CATIA's EDT on large maps

### 2. UI introspection and snapshots

- Added active diagram, browser selection, selected model element, and selected presentation readback
- Added in-memory snapshots and bounded JSON diffs for comparing UI-created and bridge-created state
- Added controlled probe templates and restricted Java-reflection reads without enabling arbitrary probe scripts

### 3. Advanced CATIA route families

- Added native validation capabilities, suite listing, bounded validation runs, and cached result readback
- Added Report Wizard template discovery and native generation through `GenerateTask`
- Added JSON/CSV requirements import/export with dry-run defaults and explicit `allowWrite=true` apply gates
- Added probe-first handlers for simulation, Teamwork, DataHub, criteria, profiles, variants, safety/cyber extensions, and typed diagrams

### 4. Safety and release hygiene

- Added request timeout support on the Python client for long-running CATIA operations
- Serialized Java-side model writes so overlapping write sessions fail clearly
- Gated Report Wizard file generation behind `allowWrite=true`
- Ignored raw `mcp-server/validation-output/` artifacts so local model evidence is not accidentally committed
- Updated README and changelog to document the 162-tool surface and current limitations

## Compatibility

- Python MCP server version: `2.3.5`
- Plugin version: `2.3.5`
- API version: `v1`
- Handshake version: `1`

Plugin/server version lockstep is still required.

## Verification

- `python3 -m pytest` from `mcp-server` passed with `181 passed`
- `bash ./gradlew test -PcameoHome=/mnt/d/DevTools/CatiaMagic` from `plugin` passed
- Public-source hygiene scan passed for source-context and model-specific release references
- Initial Gradle run with the Windows JDK path failed from the Linux shell because the Windows `java.exe` could not be probed; rerunning with system Java 17 succeeded

## Follow-on Work

- Add disposable-model regression scripts for JSON/CSV requirements roundtrip and Report Wizard output assertions
- Promote optional-product write paths only after disposable live validation exists
- Tighten the capability manifest so multi-route preview families and MCP tool names stay aligned
