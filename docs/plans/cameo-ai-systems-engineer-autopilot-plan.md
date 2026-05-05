# Plan: Cameo AI Systems Engineer Autopilot

**Generated**: 2026-05-04
**Estimated Complexity**: Very High
**Primary repo**: `Z:\cameo-mcp-bridge`
**Primary live target**: CATIA Magic / Cameo Systems Modeler with `CameoMCPBridge` on `http://127.0.0.1:18740/api/v1`
**Planning input**: `docs/strategy/catia-magic-feature-access-ranking.md` plus the 35 selected "Cameo AI Systems Engineer Autopilot" capabilities.

## Overview

Build a Cameo AI Systems Engineer Autopilot: a typed, evidence-first bridge that lets an AI agent inspect, reason about, edit, validate, repair, document, and synchronize CATIA Magic / Cameo models with enough fidelity that routine MBSE work can be delegated safely.

The product thesis is simple:

- CATIA Magic already contains the engineering truth.
- The human-visible UI, native reports, validation results, simulations, Teamwork history, tables, matrices, and diagrams contain information that generic REST or model-element reads do not expose cleanly.
- The bridge must therefore become a high-fidelity automation layer, not just a CRUD wrapper.
- Every AI write must be inspectable, reversible, validated, and accompanied by evidence.

The plan below is organized as engineering work packages. Each package must land as a demonstrable increment with Java plugin changes, Python MCP wrappers, tests, live validation scripts, documentation, and release notes.

## Success Criteria

The full program is successful when an engineer can ask an AI agent to:

1. Inspect any relevant part of a Cameo model and explain what it found with element IDs, stereotypes, tags, relationships, diagrams, and source evidence.
2. Propose model changes as a structured patch plan before writing.
3. Apply approved changes through typed endpoints, not ad hoc macros.
4. Produce traceability, matrices, diagrams, validation results, reports, and evidence bundles.
5. Detect missing or stale model content before a review or delivery.
6. Run selected native Cameo validation, simulation, report, Teamwork, and integration workflows where the installed license/API surface allows it.
7. Fail closed with clear diagnostics when CATIA/Cameo plugins, licenses, UI state, Teamwork credentials, or API capabilities are missing.

## Non-Goals

- Do not embed an LLM inside the Java plugin.
- Do not expose unrestricted remote code execution beyond the current local-only diagnostic macro/probe surface.
- Do not rely on Groovy macros as the stable implementation for high-value capabilities.
- Do not hard-code any validation model into any bridge feature.
- Do not make write operations fire-and-forget. Every write needs receipts, validation hooks, and rollback/evidence strategy.
- Do not implement broad Teamwork/DataHub/Simulation behavior without first detecting whether the relevant product/plugin is installed and licensed.

## Engineering Principles

1. **Typed endpoint first**: Java handlers should expose stable, explicit operations. Macro/probe paths are only for discovery.
2. **Readback before mutation**: every write feature must have equivalent or stronger inspection support.
3. **Receipts over assumptions**: responses must include IDs created/modified, warnings, skipped actions, validation summaries, and unsupported capabilities.
4. **Evidence-driven discovery**: when a UI-created setting is unclear, use snapshot/diff and property dumps to learn it before implementing mutation.
5. **Live CATIA validation required**: unit tests are necessary but insufficient.
6. **One CATIA write at a time**: all write endpoints must use the existing serialized write/session infrastructure.
7. **No hidden native refresh**: operations known to block the Swing EDT, especially Relation Map native refresh, must be explicit and timeout-controlled.
8. **AI planner outside, deterministic tools inside**: natural-language reasoning belongs to the MCP client/agent layer; the plugin should provide deterministic primitives.

## Current Baseline

Live baseline as of this plan:

- Bridge version: `2.3.5`
- Live status: healthy
- Advertised REST capabilities: `79`
- Java handlers currently include:
  - `ProjectHandler`
  - `UiStateHandler`
  - `ElementQueryHandler`
  - `ElementMutationHandler`
  - `RelationshipHandler`
  - `DiagramHandler`
  - `MatrixHandler`
  - `GenericTableHandler`
  - `RelationMapHandler`
  - `PropertyDumpHandler`
  - `SnapshotHandler`
  - `ScriptProbeHandler`
  - `SpecificationHandler`
  - `MacroHandler`
- Python MCP server currently exposes about 100 user-facing `cameo_*` tools, including higher-level methodology and verification helpers.

Important current files:

- `plugin/src/com/claude/cameo/bridge/HttpBridgeServer.java`
- `plugin/src/com/claude/cameo/bridge/util/BridgeCapabilities.java`
- `plugin/src/com/claude/cameo/bridge/util/EdtDispatcher.java`
- `plugin/src/com/claude/cameo/bridge/handlers/*.java`
- `mcp-server/cameo_mcp/client.py`
- `mcp-server/cameo_mcp/server.py`
- `mcp-server/tests/test_client.py`
- `mcp-server/tests/test_server.py`
- `mcp-server/scripts/live_validate_*.py`
- `docs/strategy/catia-magic-feature-access-ranking.md`

## External API Anchors To Investigate

Use these as API starting points, not as final design assumptions. Validate every class/method against the installed CATIA Magic version and plugin availability.

- Model CRUD and diagrams:
  - `com.nomagic.magicdraw.openapi.uml.ModelElementsManager`
  - `com.nomagic.magicdraw.openapi.uml.SessionManager`
  - `com.nomagic.magicdraw.openapi.uml.PresentationElementsManager`
  - `com.nomagic.magicdraw.uml.Finder`
  - `com.nomagic.magicdraw.uml.ClassifierFinder`
- Stereotypes and tags:
  - `com.nomagic.uml2.ext.jmi.helpers.StereotypesHelper`
  - `com.nomagic.uml2.ext.jmi.helpers.TagsHelper`
  - profile wrapper classes generated under `com.nomagic.profiles`
- Validation:
  - `com.nomagic.magicdraw.validation.ValidationHelper`
  - `com.nomagic.magicdraw.validation.ValidationRunData`
  - `com.nomagic.magicdraw.validation.RuleViolationResult`
  - `com.nomagic.magicdraw.validation.ValidationConstants`
- Simulation:
  - `com.nomagic.magicdraw.simulation.SimulationManager`
  - `SimulationManager.simulate(...)`
  - `SimulationManager.simulateAsync(...)`
  - `SimulationResult`
- Reports:
  - `com.nomagic.magicdraw.magicreport.*`
  - `com.nomagic.magicdraw.magicreport.helper.ReportHelper`
  - Report Wizard APIs may be sparse; expect probing.
- Teamwork / Magic Collaboration Studio:
  - Java client APIs and/or server REST APIs must be discovered per installed deployment.
  - Token/password/login mode differs by organization. Do not assume token auth.
- Criteria:
  - Structured expression classes used by dependency matrices, relation maps, smart packages, generic table derived properties, legends, and opaque behaviors.

## Resolved API Implementation Playbooks

These playbooks turn the highest-risk research targets into concrete implementation work. Treat every class name below as a candidate to verify against the installed CATIA Magic version before compiling against it. If a class is optional-product-specific, detect it reflectively first and return an unsupported capability response instead of failing plugin startup.

### Shared Native-API Probe Pattern

Use this sequence for every optional native integration:

1. Add read-only reflection support before typed behavior.
   - Extend `ScriptProbeHandler.safeProbeClass(...)` only for explicit package prefixes needed by the feature.
   - Preferred probe route: `POST /api/v1/probes/execute` with `language=javaReflection`, `operation=listMethods`, and the candidate `className`.
   - For optional products, use `Class.forName(className, false, Thread.currentThread().getContextClassLoader())` inside the new handler and catch `ClassNotFoundException`, `NoClassDefFoundError`, `LinkageError`, and security/licensing exceptions.
2. Add the handler only after the probe proves the class surface.
   - Register under one top-level context in `HttpBridgeServer.java`.
   - Add exact route rows to `BridgeCapabilities.java`.
   - Add Python client methods in `mcp-server/cameo_mcp/client.py`.
   - Add MCP wrappers in `mcp-server/cameo_mcp/server.py` or a feature module imported from it.
3. Every capability probe response must include:
   - `available`
   - `installed`
   - `licensed`
   - `mode`: `native`, `bridge-owned`, `external-rest`, or `unsupported`
   - `classesFound`
   - `classesMissing`
   - `pluginDirectoriesFound`
   - `warnings`
   - `nextProbe`
4. Every live script must capture:
   - `/api/v1/status`
   - `/api/v1/capabilities`
   - `/api/v1/project`
   - feature `/capabilities` route
   - request/response JSON for every route exercised
   - unsupported response evidence when the installed product is absent

Current local install signal from `D:\DevTools\CatiaMagic\plugins`: Report Wizard and Requirements plugins are present; obvious Simulation Toolkit, DataHub, Product Line/variant, safety, and cyber plugin directories were not present in the first directory scan. Re-check this before implementation because installed plugins can change.

### Resolved Local API Evidence

Use this as the current research baseline for the engineering team. These findings came from local CATIA Magic 2024x-era jars and OpenAPI examples, not from guesswork.

| Target | Local evidence | Implementation decision |
| --- | --- | --- |
| Native validation | `D:\DevTools\CatiaMagic\lib\md_api.jar` contains `ValidationHelper`, `ValidationRunData`, and `RuleViolationResult`; OpenAPI example `openapi\examples\validationhelper\ValidationHelperExample.java` demonstrates suite lookup and `ValidationHelper.validate(...)`. | Implement as a typed Java handler immediately. No optional plugin dependency is needed beyond the existing core API jars. |
| Report Wizard | `D:\DevTools\CatiaMagic\plugins\com.nomagic.magicdraw.reportwizard\reportwizard_api.jar` contains `ReportHelper`, `TemplateHelper`, `GenerateTask`, `ReportCommandLine`, `ReportBean`, and `TemplateBean`. `TemplateHelper` exposes template listing/loading, and `GenerateTask` exposes `execute()` plus report display helpers. | Add an optional `compileOnly` dependency and implement template discovery first, then gated generation. Do not mark generation complete until a live report file is produced and read back. |
| Teamwork / Magic Collaboration Studio | `md_api.jar` contains `com.nomagic.magicdraw.esi.EsiUtils`; local OpenAPI example `openapi\examples\teamworkcloud\TeamworkCloudSample.java` demonstrates login, remote descriptor discovery, project creation, descriptor lookup, and ESI service access. | Implement read-only collaboration introspection and preview routes first. Mutating commit/update routes require disposable Teamwork project evidence and explicit preview approval. |
| ReqIF / Requirements | `D:\DevTools\CatiaMagic\plugins\com.nomagic.requirements\requirements_api.jar` contains `ReqIFUtils`, `ReqIFMappingManager`, import/export command actions, mapping classes, and ReqIF constants. `ReqIFUtils` exposes import/export helpers for specifications/elements. | Add an optional `compileOnly` dependency and implement capability probe plus export first. Import stays preview-only until sample ReqIF roundtrip evidence exists. |
| Generic tables and matrices | Existing bridge code already uses native generic table, matrix, relation map, snapshot, property dump, and presentation serialization surfaces. OpenAPI examples exist for generic table and dependency matrix customization. | Keep building these as typed handlers, not macros. Add criteria-expression capture and replay through snapshot/diff evidence. |
| Sequence and interaction diagrams | OpenAPI example `openapi\examples\sequencecreation\CreateSequenceAction.java` shows `PresentationElementsManager.createSequenceMessage(...)`, `InteractionHelper`, duration intervals, and time intervals. | Implement read/list first, then typed create-message/edit endpoints with diagram-type gating. |
| Simulation | Local javadocs mention Simulation Toolkit APIs, but the first runtime class scan did not find runtime simulation classes in the installed plugin directories. | Probe-only until runtime jars are present. Do not add hard compile dependencies or production run routes that fail bridge startup. |
| DataHub, product-line variants, safety, cyber | No obvious plugin directories were found in the first scan. | Implement extension/profile detection and bridge-owned fallback patterns only. Native routes stay in diagnostic/probing mode until installed products are proven. |

Exact class probes engineers should run before coding a target:

```powershell
$java = 'D:\DevTools\jdk17\jdk-17.0.18+8\bin\javap.exe'
& $java -classpath 'D:\DevTools\CatiaMagic\lib\md_api.jar' com.nomagic.magicdraw.validation.ValidationHelper
& $java -classpath 'D:\DevTools\CatiaMagic\lib\md_api.jar' com.nomagic.magicdraw.validation.ValidationRunData
& $java -classpath 'D:\DevTools\CatiaMagic\lib\md_api.jar' com.nomagic.magicdraw.validation.RuleViolationResult
& $java -classpath 'D:\DevTools\CatiaMagic\plugins\com.nomagic.magicdraw.reportwizard\reportwizard_api.jar' com.nomagic.magicdraw.magicreport.helper.TemplateHelper
& $java -classpath 'D:\DevTools\CatiaMagic\plugins\com.nomagic.magicdraw.reportwizard\reportwizard_api.jar' com.nomagic.magicdraw.magicreport.GenerateTask
& $java -classpath 'D:\DevTools\CatiaMagic\lib\md_api.jar' com.nomagic.magicdraw.esi.EsiUtils
& $java -classpath 'D:\DevTools\CatiaMagic\plugins\com.nomagic.requirements\requirements_api.jar;D:\DevTools\CatiaMagic\lib\md_api.jar' com.nomagic.requirements.reqif.ReqIFUtils
```

Build dependency rule:

- Keep core `md.jar`, `md_api.jar`, diagram, relationship map, dependency matrix, and generic table jars exactly as normal `compileOnly` dependencies.
- Add Report Wizard and Requirements jars with optional `compileOnly` helper logic that only adds the file when it exists under `cameoHome`.
- Do not add Report Wizard, Requirements, Simulation, DataHub, safety, cyber, or variant/product-line plugins to `plugin.xml` as `required-plugin` unless the bridge is intentionally being split into product-specific distributions.
- If a handler is optional, its `/capabilities` route must succeed even when the optional jar/plugin is absent.

### Advanced Handler Implementation Map

Use this map when turning any advanced playbook into code. Each row identifies the first route family to build, the Java ownership boundary, the Python wrapper location, and the required live evidence gate. Do not skip the capability route; it is what keeps optional CATIA products from breaking bridge startup.

| Target | Java owner | Python/MCP owner | First implementation increment | Hard dependency policy | Live evidence gate |
| --- | --- | --- | --- | --- | --- |
| Validation | `ValidationHandler.java`; shared `ValidationFinding` serializer if useful | `cameo_mcp/validation.py`, imported by `server.py` | `GET /api/v1/validation/capabilities`, then suite inventory, then one bounded run | Core `md_api.jar` classes can be compiled against after local `javap` proof | Native run completes or unsupported response proves no open project/suite/license/class |
| Report Wizard | `ReportHandler.java`; in-memory job store under handler | `cameo_mcp/reports.py` | Template discovery from native helper and filesystem; generation only after dry run | Optional `compileOnly` only if `reportwizard_api.jar` exists; no required plugin declaration | Generated non-empty file or structured template/generation unsupported artifact |
| Teamwork/MCS | `TeamworkHandler.java` for current CATIA project/session only | `cameo_mcp/teamwork.py`; server REST clients stay MCP-side | Local/server project detection, descriptor metadata, history/locks read-only | Core API classes only; avoid server client hard dependencies until environment known | Local project proves unsupported cleanly; server project returns descriptor/version or precise auth limitation |
| ReqIF/Requirements | `ImportExportHandler.java` or `RequirementsHandler.java` for native ReqIF; Python for CSV/XLSX | `cameo_mcp/import_export.py`, `excel_roundtrip.py` | Bridge-owned CSV export/import preview, then native ReqIF capability probe/export | Optional `compileOnly` only if `requirements_api.jar` exists | CSV IDs roundtrip; native ReqIF remains probing until sample file import/export evidence exists |
| DataHub/DOORS/ENOVIA | `DataHubHandler.java` diagnostics only | `cameo_mcp/datahub.py` or `import_export.py` | Installed plugin/source inventory and sync preview only | Reflection only until DataHub jars and connector config are present | Probe proves absent cleanly or lists sources without secrets; no sync write |
| Simulation | `SimulationHandler.java`; bounded job/result store | `cameo_mcp/simulation.py`, `trade_studies.py` | Runtime class/plugin probe and executable configuration inventory | Reflection only unless Simulation Toolkit jar is present in local install | Unsupported cleanly when absent; if present, sample run produces outputs |
| Variants/Product line | `VariantHandler.java` | `cameo_mcp/variants.py` | Native plugin probe plus bridge-owned stereotype pattern preview | Reflection only for native plugins; bridge-owned pattern uses core profile/tag APIs | Stereotype pattern evaluates configurations, or native plugin read-only inventory works |
| Safety/Cyber | `ExtensionProbeHandler.java` or diagnostics extension | `cameo_mcp/extensions.py` | Installed plugin/profile/stereotype inventory and read-only model scan | Reflection/profile introspection only | Probe records installed/absent state and never claims compliance |

For each row, add the route context in `HttpBridgeServer.java`, advertise every route in `BridgeCapabilities.java`, add client methods in `client.py`, expose only stable user-facing MCP tools in `server.py`, and add both unit tests and a live `scripts/live_probe_*` or `scripts/live_validate_*` script before marking the task implemented.

### Native Validation Suite Runner

Research status: strong OpenAPI anchor. Public javadocs show `ValidationHelper.validate(ValidationRunData, String, ProgressStatus)` returns `Collection<RuleViolationResult>`, and `ValidationRunData` supports suite, constraint, scope, selected-elements, whole-project, severity, and read-only exclusion constructors.

Likely Java classes/packages:

- `com.nomagic.magicdraw.validation.ValidationHelper`
- `com.nomagic.magicdraw.validation.ValidationRunData`
- `com.nomagic.magicdraw.validation.RuleViolationResult`
- `com.nomagic.magicdraw.validation.ValidationConstants`
- `com.nomagic.magicdraw.validation.Scope`
- `com.nomagic.uml2.ext.magicdraw.classes.mdkernel.Constraint`
- `com.nomagic.uml2.ext.magicdraw.classes.mdkernel.Package`
- `com.nomagic.uml2.ext.magicdraw.classes.mdkernel.Element`

Probe commands:

```powershell
Invoke-RestMethod http://127.0.0.1:18740/api/v1/probes/execute -Method Post -ContentType 'application/json' -Body '{"language":"javaReflection","operation":"listMethods","className":"com.nomagic.magicdraw.validation.ValidationHelper"}'
Invoke-RestMethod http://127.0.0.1:18740/api/v1/probes/execute -Method Post -ContentType 'application/json' -Body '{"language":"javaReflection","operation":"listMethods","className":"com.nomagic.magicdraw.validation.ValidationRunData"}'
```

Implementation route design:

- `GET /api/v1/validation/capabilities`: verifies classes and reports supported modes.
- `GET /api/v1/validation/suites`: finds validation suites as packages/constraints with validation stereotypes; first pass may return discovered package candidates plus `listingConfidence`.
- `POST /api/v1/validation/run`: accepts `suiteId`, `constraintIds`, `scopeMode`, `scopeElementIds`, `wholeProject`, `minimumSeverity`, `excludeReadOnly`, `recursive`, `openNativeWindow`, `timeoutMillis`.
- `GET /api/v1/validation/results/{runId}`: returns cached serialized findings for async or long-running runs.

Java implementation notes:

- Put native calls in `ValidationHandler.java`.
- Start with synchronous execution inside `EdtDispatcher.read(...)`; if live evidence shows validation blocks the EDT for large models, move to a bounded background job while ensuring all model access obeys CATIA threading rules.
- Use `ValidationRunData(Collection<Constraint>, name, wholeProject, elements, severity, excludeReadOnly)` for constraint-specific runs when suite discovery is uncertain.
- Use `ValidationRunData(Package suite, boolean wholeProject, Collection<? extends Element> elements, EnumerationLiteral severity, boolean excludeReadOnly)` for suite runs when suite packages are confirmed.
- Serialize each `RuleViolationResult` into `ValidationFinding`: rule id/name, severity, message, violating element ref, annotation text if available, and available corrective actions as names only.
- Do not execute native fix actions in v1. Expose them as `suggestedFixes` with `autoFixable=false` until each action is typed and validated.

Failure modes:

- no open project: `409 NO_PROJECT`
- suite not found: `404 VALIDATION_SUITE_NOT_FOUND`
- validation classes missing: `501 VALIDATION_UNAVAILABLE`
- selected element ID stale: `404 ELEMENT_NOT_FOUND`
- validation timeout: `504 VALIDATION_TIMEOUT` plus partial run metadata if any
- native validation throws because a plugin/profile is not mounted: `424 VALIDATION_DEPENDENCY_MISSING`

Acceptance gate:

- `mcp-server/scripts/live_validate_native_validation.py --suite <suite-id-or-name> --scope selected --element <id>` writes `validation-output/native-validation/run.json`, `findings.json`, `summary.md`, and `capability-probe.json`.
- The script passes when at least one native validation run completes or, in an environment without suites, unsupported/discovery failure is proven with class and project-state evidence.

### Simulation And Parametric Execution

Research status: strong OpenAPI anchor, but optional product dependency. Public javadocs show `SimulationManager.execute(...)`, `executeWithConfig(...)`, `simulateAsync(...)`, `terminate(...)`, and `SimulationResult.getOutputValues()`. The installed plugin scan must prove Simulation Toolkit availability before compiling or enabling routes.

Likely Java classes/packages:

- `com.nomagic.magicdraw.simulation.SimulationManager`
- `com.nomagic.magicdraw.simulation.execution.SimulationResult`
- `com.nomagic.magicdraw.simulation.execution.SimulationSession`
- `com.nomagic.magicdraw.simulation.execution.SimulationExecution`
- `com.nomagic.magicdraw.simulation.listeners.SimulationExecutionListener`
- `com.nomagic.magicdraw.simulation.exceptions.SimulationInputValuesException`

Probe commands:

```powershell
Invoke-RestMethod http://127.0.0.1:18740/api/v1/probes/execute -Method Post -ContentType 'application/json' -Body '{"language":"javaReflection","operation":"listMethods","className":"com.nomagic.magicdraw.simulation.SimulationManager"}'
Invoke-RestMethod http://127.0.0.1:18740/api/v1/probes/execute -Method Post -ContentType 'application/json' -Body '{"language":"javaReflection","operation":"listMethods","className":"com.nomagic.magicdraw.simulation.execution.SimulationResult"}'
```

Implementation route design:

- `GET /api/v1/simulation/capabilities`: class/plugin/license probe.
- `GET /api/v1/simulation/configurations`: locate elements stereotyped as simulation configs; include target compatibility if discoverable.
- `POST /api/v1/simulation/run`: synchronous bounded run for a known config/target.
- `POST /api/v1/simulation/run-async`: starts a job and returns `runId`.
- `GET /api/v1/simulation/results/{runId}`: status, output values, exceptions, duration.
- `POST /api/v1/simulation/results/{runId}/terminate`: calls `SimulationManager.terminate(...)` or `terminateSession(...)` when available.

Java implementation notes:

- Put native calls in `SimulationHandler.java`.
- Add compile dependencies only after confirming local jar locations. Prefer `compileOnly fileTree(dir: "${cameoHome}/plugins", include: ["**/*simulation*.jar"])` only if the jars exist; otherwise keep the first handler version reflective.
- Never call `SimulationResult.getOutputValues()` without a timeout wrapper because it can block until execution terminates.
- Store active results in a bounded in-memory `ConcurrentHashMap<String, SimulationJob>` with timestamps and terminal cleanup.
- Inputs must be structured: `configId`, `targetId`, `outputs`, `inputs`, `timeoutMillis`, `silent`, `dryRun`.

Failure modes:

- Simulation Toolkit absent: `501 SIMULATION_UNAVAILABLE`
- no compatible target/config: `422 SIMULATION_CONFIG_INCOMPATIBLE`
- blocking output timeout: `504 SIMULATION_TIMEOUT`
- invalid input value: `400 SIMULATION_INPUT_INVALID`
- native exception: `500 SIMULATION_EXECUTION_ERROR` with exception class/message, not a stack dump

Acceptance gate:

- `mcp-server/scripts/live_probe_simulation.py` must pass in unsupported mode on installs without Simulation Toolkit.
- `mcp-server/scripts/live_validate_simulation.py --config <id> --target <id> --allow-execute` is required before claiming execution support.
- Output artifacts: `validation-output/simulation/capabilities.json`, `configurations.json`, `run.json`, `outputs.json`, `summary.md`.

### Report Wizard Automation

Research status: strong local API anchor for discovery and likely generation. Local `reportwizard_api.jar` exposes `ReportHelper`, `TemplateHelper`, `GenerateTask`, `ReportCommandLine`, `ReportBean`, and `TemplateBean`. Treat generation as evidence-gated because template context and output behavior still need live proof in CATIA.

Likely Java classes/packages:

- `com.nomagic.magicdraw.magicreport.helper.ReportHelper`
- `com.nomagic.magicdraw.magicreport.helper.TemplateHelper`
- `com.nomagic.magicreport.engine.*`
- classes under jars in `D:\DevTools\CatiaMagic\plugins\com.nomagic.magicdraw.reportwizard`

Probe commands:

```powershell
Get-ChildItem 'D:\DevTools\CatiaMagic\plugins\com.nomagic.magicdraw.reportwizard' -Recurse -Filter *.jar | Select-Object FullName
Invoke-RestMethod http://127.0.0.1:18740/api/v1/probes/execute -Method Post -ContentType 'application/json' -Body '{"language":"javaReflection","operation":"listMethods","className":"com.nomagic.magicdraw.magicreport.helper.ReportHelper"}'
Invoke-RestMethod http://127.0.0.1:18740/api/v1/probes/execute -Method Post -ContentType 'application/json' -Body '{"language":"javaReflection","operation":"listMethods","className":"com.nomagic.magicdraw.magicreport.helper.TemplateHelper"}'
```

Implementation route design:

- `GET /api/v1/reports/capabilities`: plugin directories, jars, candidate classes, supported output formats.
- `GET /api/v1/reports/templates`: scan known template folders and optionally native template registry.
- `POST /api/v1/reports/generate-preview`: validates template, output path, scope, and format without writing.
- `POST /api/v1/reports/generate`: guarded write to an allowed output directory.
- `GET /api/v1/reports/jobs/{jobId}`: report generation status.

Java implementation notes:

- First implementation may be template discovery only using filesystem scan under `${cameoHome}/data` and Report Wizard plugin directories.
- Native generation must be behind `allowWrite=true` and an output directory allowlist rooted under `mcp-server/validation-output/reports/` unless the user supplies an explicit local path.
- If native generation APIs are inaccessible, mark `mode=template-discovery-only` and use MCP-side document assembly as a separate partial capability; do not label it Report Wizard generation.

Failure modes:

- Report Wizard plugin absent: `501 REPORT_WIZARD_UNAVAILABLE`
- template file not found: `404 REPORT_TEMPLATE_NOT_FOUND`
- output format unsupported: `422 REPORT_FORMAT_UNSUPPORTED`
- output path blocked: `403 REPORT_OUTPUT_PATH_BLOCKED`
- native generation job failed: `500 REPORT_GENERATION_FAILED`

Acceptance gate:

- `mcp-server/scripts/live_validate_report_wizard.py --template <template-id> --format docx --allow-write` generates a report or records an unsupported result with template discovery evidence.
- Output artifacts: `validation-output/report-wizard/templates.json`, `generate-request.json`, generated report file, `summary.md`.

### Teamwork Cloud / Magic Collaboration Studio

Research status: strong local OpenAPI anchor for read/probe behavior through `EsiUtils`, with optional external REST as a later expansion. Local auth, server profile, and project mode still vary. Do not implement write operations until a disposable Teamwork project exists.

Likely integration surfaces:

- Local Cameo project APIs for detecting whether the current project is local or server-backed.
- `com.nomagic.magicdraw.esi.EsiUtils` in `md_api.jar`.
- Teamwork/Magic Collaboration client jars under `D:\DevTools\CatiaMagic\lib` with names including `esi`, `ci`, or Dassault DS client names when present.
- Teamwork Cloud REST API at an organization-specific server URL.

Probe commands:

```powershell
Get-ChildItem 'D:\DevTools\CatiaMagic\lib' -Filter '*.jar' | Where-Object { $_.Name -match 'esi|ci|dsclient' } | Select-Object Name
Invoke-RestMethod http://127.0.0.1:18740/api/v1/project
```

Implementation route design:

- `GET /api/v1/teamwork/capabilities`: local/server mode, local client jars, configured server hints, auth mode unknown/known.
- `GET /api/v1/teamwork/project`: current project collaboration metadata if server-backed.
- `GET /api/v1/teamwork/history`: read-only history where available.
- `GET /api/v1/teamwork/locks`: read-only lock state where available.
- `POST /api/v1/teamwork/commit-preview`: validation and changed-element preview only.
- `POST /api/v1/teamwork/commit`: disabled until explicit server validation and user confirmation workflow are implemented.
- `GET /api/v1/teamwork/branches`: read-only branches where available.

Java/Python implementation notes:

- Keep server REST credentials out of the Java plugin. If REST is used, prefer Python MCP with env vars or an explicit credentials profile supplied by the user.
- Java handler should expose current Cameo-side project/session metadata only.
- Do not assume token auth; support discovery fields for SSO/password/token/server-managed session.
- Commit route must require `validationGate=pass`, `expectedProjectId`, `expectedVersion`, and an approval token generated by a preview call.

Failure modes:

- local project: `200 available=false reason=LOCAL_PROJECT`
- server not configured: `424 TEAMWORK_SERVER_NOT_CONFIGURED`
- auth unavailable: `401 TEAMWORK_AUTH_REQUIRED`
- read-only or locked project: `423 TEAMWORK_LOCKED_OR_READ_ONLY`
- version changed since preview: `409 TEAMWORK_VERSION_CHANGED`

Acceptance gate:

- `mcp-server/scripts/live_probe_teamwork.py` must prove local unsupported mode on a local project.
- `mcp-server/scripts/live_validate_teamwork_readonly.py --server-profile <name>` is required before claiming history/locks.
- No commit support can be marked done without a disposable Teamwork project and recorded preview/commit/readback evidence.

### DataHub, ReqIF, CSV, DOORS, And Requirements Integrations

Research status: Requirements and native ReqIF are locally anchored through `requirements_api.jar`; DataHub remains optional and was not visible in the current plugin directory scan. Therefore the implementation order is bridge-owned CSV/XLSX, native ReqIF export/import probe, Requirements-plugin readback, then DataHub probes if the plugin is later installed.

Likely integration surfaces:

- `D:\DevTools\CatiaMagic\plugins\com.nomagic.requirements`
- `com.nomagic.requirements.reqif.ReqIFUtils`
- `com.nomagic.requirements.reqif.mapping.ReqIFMappingManager`
- `D:\DevTools\CatiaMagic\plugins\com.nomagic.magicdraw.importexport`
- Optional DataHub plugin directory if installed later.
- Requirement stereotypes/tags via `StereotypesHelper` and `TagsHelper`.

Probe commands:

```powershell
Get-ChildItem 'D:\DevTools\CatiaMagic\plugins\com.nomagic.requirements' -Recurse -Filter *.jar | Select-Object FullName
Get-ChildItem 'D:\DevTools\CatiaMagic\plugins' -Directory | Where-Object { $_.Name -match 'datahub|reqif|requirements|importexport' } | Select-Object Name
```

Implementation route design:

- `GET /api/v1/import-export/capabilities`: CSV/XLSX/native ReqIF/DataHub availability.
- `POST /api/v1/import-export/requirements/export`: bridge-owned CSV/JSON first.
- `POST /api/v1/import-export/requirements/import-preview`: diff only, no writes.
- `POST /api/v1/import-export/requirements/apply`: approved patch-plan application.
- `GET /api/v1/datahub/capabilities`: optional plugin/class/config probe.
- `GET /api/v1/datahub/sources`: configured sources if native APIs expose them.
- `POST /api/v1/datahub/sync-preview`: preview only; no native sync writes until proven.

Implementation notes:

- Keep CSV/XLSX logic in Python first because it can reuse existing typed element and relationship endpoints and is easy to unit-test.
- Native ReqIF/DataHub paths must not bypass patch-plan preview unless the native API itself provides a preview/diff that can be serialized.
- Every imported row must carry stable Cameo element ID or an unambiguous external key mapping.
- Store external mapping evidence as a table in `validation-output/import-export/` before adding model-side mapping stereotypes/tags.

Failure modes:

- DataHub absent: `200 available=false reason=DATAHUB_PLUGIN_NOT_INSTALLED`
- ambiguous external key: `422 IMPORT_AMBIGUOUS_EXTERNAL_KEY`
- row missing ID/key: `422 IMPORT_ROW_UNADDRESSABLE`
- native sync would write without preview: `403 DATAHUB_SYNC_PREVIEW_REQUIRED`

Acceptance gate:

- `mcp-server/scripts/live_validate_excel_roundtrip.py --allow-write` proves bridge-owned import/export on a disposable package.
- `mcp-server/scripts/live_probe_datahub.py` proves installed/uninstalled state with plugin directory and class evidence.
- Native ReqIF/DataHub support remains `probing` until a sample ReqIF/DataHub source roundtrip is recorded.

### Profile/DSL Authoring

Research status: strong OpenAPI primitives exist through UML/profile model elements plus `StereotypesHelper` and `TagsHelper`; generated `com.nomagic.profiles` wrappers can help for built-in profiles but should not be required for custom profiles.

Likely Java classes/packages:

- `com.nomagic.magicdraw.openapi.uml.ModelElementsManager`
- `com.nomagic.magicdraw.openapi.uml.SessionManager`
- `com.nomagic.uml2.ext.magicdraw.mdprofiles.Profile`
- `com.nomagic.uml2.ext.magicdraw.mdprofiles.Stereotype`
- `com.nomagic.uml2.ext.magicdraw.mdprofiles.Extension`
- `com.nomagic.uml2.ext.magicdraw.classes.mdkernel.Property`
- `com.nomagic.uml2.ext.jmi.helpers.StereotypesHelper`
- `com.nomagic.uml2.ext.jmi.helpers.TagsHelper`

Implementation route design:

- `GET /api/v1/profiles/capabilities`
- `POST /api/v1/profiles/create`
- `POST /api/v1/profiles/stereotypes/create`
- `POST /api/v1/profiles/tags/create`
- `POST /api/v1/profiles/apply`
- `PUT /api/v1/profiles/tags`
- `POST /api/v1/profiles/export-summary`

Implementation notes:

- Implement model semantics first: profile, stereotype, tag definitions, metaclass extension, apply stereotype, set tag.
- Defer icon, toolbar, palette, customization, and diagram style integration until UI diff identifies stable properties.
- Use `OperationReceipt` and snapshot before/after for every create/apply operation.
- Do not create global reusable profiles in production packages during validation; use a disposable profile package/project.

Failure modes:

- metaclass not found: `404 PROFILE_METACLASS_NOT_FOUND`
- stereotype duplicate: `409 STEREOTYPE_ALREADY_EXISTS`
- tag type unsupported: `422 PROFILE_TAG_TYPE_UNSUPPORTED`
- profile read-only: `423 PROFILE_READ_ONLY`

Acceptance gate:

- `mcp-server/scripts/live_validate_profile_dsl.py --allow-write` creates a disposable profile with one stereotype extending `Class` or SysML `Block`, creates two tags, applies it to a disposable element, sets values, reads them back, and writes before/after snapshots.

### Variant/Product-Line Support

Research status: optional-product-specific. No obvious local product-line or variant plugin directory appeared in the first plugin scan. Start with probe and a bridge-owned stereotype pattern, then add native integration only if a product-line plugin is installed.

Probe commands:

```powershell
Get-ChildItem 'D:\DevTools\CatiaMagic\plugins' -Directory | Where-Object { $_.Name -match 'variant|variability|product|line|ple|pure' } | Select-Object Name
```

Implementation route design:

- `GET /api/v1/variants/capabilities`: native plugin probe plus bridge-owned pattern support.
- `POST /api/v1/variants/pattern/install-preview`: creates a patch plan for stereotypes like `Variant`, `VariationPoint`, `VariantOption`.
- `POST /api/v1/variants/configurations/evaluate`: evaluates included/excluded elements from tag values and dependency rules.
- `POST /api/v1/variants/configurations/export`: JSON/CSV evidence of a selected configuration.

Implementation notes:

- Bridge-owned variant support should be explicit in responses as `mode=bridge-owned`, not native product-line support.
- Do not mutate model visibility/suppression globally. Generate configuration views/evidence first.
- If native plugin appears later, add read-only native introspection before creating or applying native configurations.

Failure modes:

- native plugin absent: `200 nativeAvailable=false bridgeOwnedAvailable=true`
- configuration expression ambiguous: `422 VARIANT_RULE_AMBIGUOUS`
- variant would hide/delete model content: `403 VARIANT_DESTRUCTIVE_OPERATION_REFUSED`

Acceptance gate:

- `mcp-server/scripts/live_validate_variants.py --mode bridge-owned --allow-write` installs the disposable stereotype pattern, tags three elements, evaluates two configurations, and exports evidence.

### Safety/Cyber Extension Hooks

Research status: optional-product-specific. Public product listings identify safety/reliability and cybersecurity-related add-ons, but route support must begin as profile/stereotype introspection unless installed native APIs are detected.

Probe commands:

```powershell
Get-ChildItem 'D:\DevTools\CatiaMagic\plugins' -Directory | Where-Object { $_.Name -match 'safety|reliability|cyber|security|iso|hazard|fmea|fmeca|risk' } | Select-Object Name
```

Implementation route design:

- `GET /api/v1/extensions/capabilities`: installed plugin/profile probe.
- `GET /api/v1/extensions/profiles`: list profile roots and stereotypes matching safety/cyber/risk/hazard/failure/classification terms.
- `POST /api/v1/extensions/model-scan`: read-only scan for hazards, risks, mitigations, threats, controls, classifications, and trace links.
- `POST /api/v1/extensions/pattern/install-preview`: bridge-owned profile/stereotype pattern only, via patch plan.

Implementation notes:

- Treat safety/cyber as read-only until domain-specific stereotypes and validation rules are proven.
- Do not claim compliance. Return evidence and traceability gaps only.
- Keep safety/cyber checks as configurable rule packs in MCP first; native rule authoring can follow the validation-rule playbook.

Failure modes:

- extension absent: `200 available=false reason=EXTENSION_NOT_INSTALLED`
- compliance claim requested: `403 COMPLIANCE_CLAIM_REFUSED`
- profile found but unknown semantics: `206 PARTIAL_EXTENSION_INTROSPECTION`

Acceptance gate:

- `mcp-server/scripts/live_probe_extensions.py --targets safety,cyber` records plugin directories, profile roots, stereotype names, and unsupported evidence when absent.

## Implementation Instructions By Resolved Research Target

This section is the handoff checklist for engineering agents. Complete each target as a vertical slice: Java route, capability metadata, Python client, MCP wrapper, tests, live script, docs, and changelog. Do not implement all Java first and leave the MCP surface untested.

### Target 1: Native Validation

Goal: let AI run the same native validation checks a human can run from CATIA Magic, then serialize the findings into reviewable evidence.

Files to add or change:

- `plugin/src/com/claude/cameo/bridge/handlers/ValidationHandler.java` - new Java route family.
- `plugin/src/com/claude/cameo/bridge/util/ValidationSerializer.java` - new serializer for suites, constraints, and `RuleViolationResult`.
- `plugin/src/com/claude/cameo/bridge/HttpBridgeServer.java` - register `/api/v1/validation`.
- `plugin/src/com/claude/cameo/bridge/util/BridgeCapabilities.java` - add route rows and capability flags.
- `mcp-server/cameo_mcp/client.py` - add `get_validation_capabilities`, `list_validation_suites`, `run_validation`, `get_validation_result`.
- `mcp-server/cameo_mcp/server.py` - expose `cameo_get_validation_capabilities`, `cameo_list_validation_suites`, `cameo_run_native_validation`, `cameo_get_native_validation_result`, `cameo_run_precommit_review_gate`.
- `mcp-server/tests/test_client.py` and `mcp-server/tests/test_server.py` - add mocked response coverage for all validation methods/tools.
- `mcp-server/scripts/live_validate_native_validation.py` - write live evidence.

Endpoint contract:

- `GET /api/v1/validation/capabilities` returns class availability, supported run modes, known suite roots, and whether the current project is open.
- `GET /api/v1/validation/suites?includeConstraints=true` returns candidate suite packages, constraints, severity literals, and discovery confidence.
- `POST /api/v1/validation/run` accepts:

```json
{
  "suiteId": "optional element id",
  "suiteQualifiedName": "optional qualified name",
  "constraintIds": ["optional constraint ids"],
  "scopeMode": "wholeProject|selected|elements|activeDiagram",
  "scopeElementIds": ["element ids"],
  "minimumSeverity": "error|warning|debug|any",
  "excludeReadOnly": true,
  "recursive": true,
  "openNativeWindow": false,
  "timeoutMillis": 120000
}
```

Implementation notes:

- Use `Finder.byQualifiedName()` for known suites, but fall back to scanning validation profile/packages so this works across SysML and custom profiles.
- Cache each run result under a `runId` in memory; include `startedAt`, `completedAt`, `durationMillis`, `scopeSummary`, and `resultCount`.
- Serialize all element references with the existing `ElementSerializer` shape so downstream MCP tools can navigate directly from findings to model elements.
- Do not add auto-fix execution in this slice. Return fix action names only if discoverable.

Live gate:

- PASS when a native validation run completes against an open project and the script writes `capabilities.json`, `suites.json`, `run-request.json`, `run-response.json`, `findings.json`, and `summary.md`.
- UNSUPPORTED when validation classes or suites cannot be found, with `capabilities.json` proving the exact missing part.

### Target 2: Report Wizard

Goal: make CATIA Magic report templates discoverable and allow gated generation of DOCX/PDF/HTML output from known templates.

Files to add or change:

- `plugin/build.gradle` - add optional `compileOnly` for `plugins/com.nomagic.magicdraw.reportwizard/reportwizard_api.jar`.
- `plugin/src/com/claude/cameo/bridge/handlers/ReportWizardHandler.java`.
- `plugin/src/com/claude/cameo/bridge/util/ReportTemplateSerializer.java`.
- `plugin/src/com/claude/cameo/bridge/util/ReportJobStore.java`.
- `plugin/src/com/claude/cameo/bridge/HttpBridgeServer.java`.
- `plugin/src/com/claude/cameo/bridge/util/BridgeCapabilities.java`.
- `mcp-server/cameo_mcp/client.py`.
- `mcp-server/cameo_mcp/server.py`.
- `mcp-server/scripts/live_validate_report_wizard.py`.

Endpoint contract:

- `GET /api/v1/reports/capabilities` returns plugin directory, jar path, `TemplateHelper` availability, `GenerateTask` availability, output formats, and output allowlist.
- `GET /api/v1/reports/templates?includeNative=true` returns template id, name, category, file path, required plugins, output format hints, and source.
- `POST /api/v1/reports/generate-preview` validates template, scope, output file, overwrite behavior, and required plugins without writing.
- `POST /api/v1/reports/generate` starts a bounded generation job and returns `jobId`, `outputPath`, and status.
- `GET /api/v1/reports/jobs/{jobId}` returns status, timings, output file metadata, and error details.

Generation request:

```json
{
  "templateId": "template bean id or file path",
  "templateName": "optional name lookup",
  "scopeElementIds": ["optional element ids"],
  "outputPath": "Z:/cameo-mcp-bridge/mcp-server/validation-output/report-wizard/report.docx",
  "format": "docx|pdf|html|xlsx|unknown",
  "overwrite": false,
  "allowWrite": true,
  "customContext": {},
  "timeoutMillis": 180000
}
```

Implementation notes:

- Use `TemplateHelper.listTemplates()` and `TemplateHelper.getTemplateBeanByName(...)` when available.
- Use `GenerateTask(TemplateBean)` only after a preview succeeds and `allowWrite=true`.
- If generation needs `ReportCommandLine.generate(Project)` instead of `GenerateTask`, keep that path behind the same preview and job store.
- Output must be restricted to `mcp-server/validation-output/report-wizard/` by default. Broader paths require explicit request fields and path normalization.
- Do not show native report UI from automated routes unless the request explicitly sets `showNativeWindow=true`.

Live gate:

- PASS when template listing works and a small report is generated, exists on disk, is non-empty, and is referenced in `summary.md`.
- UNSUPPORTED when Report Wizard is absent, with class and plugin path evidence.

### Target 3: Teamwork / Magic Collaboration Studio

Goal: expose collaboration state and guarded workflow previews without risking accidental commits to a shared server.

Files to add or change:

- `plugin/src/com/claude/cameo/bridge/handlers/TeamworkHandler.java`.
- `plugin/src/com/claude/cameo/bridge/util/TeamworkSerializer.java`.
- `plugin/src/com/claude/cameo/bridge/util/PreviewApprovalStore.java` if commit/update preview tokens are implemented.
- `plugin/src/com/claude/cameo/bridge/HttpBridgeServer.java`.
- `plugin/src/com/claude/cameo/bridge/util/BridgeCapabilities.java`.
- Python client/server methods and `mcp-server/scripts/live_probe_teamwork.py`.

Endpoint contract:

- `GET /api/v1/teamwork/capabilities` reports `EsiUtils` availability, current project mode, lock/update/commit method availability, and whether writes are enabled.
- `GET /api/v1/teamwork/project` serializes local versus remote descriptor metadata for the current project.
- `GET /api/v1/teamwork/descriptors` lists remote descriptors only when already authenticated or safely configured.
- `GET /api/v1/teamwork/branches?projectId=...` and `GET /api/v1/teamwork/history?projectId=...` are read-only.
- `GET /api/v1/teamwork/locks` returns current lock state if available.
- `POST /api/v1/teamwork/update-preview` and `POST /api/v1/teamwork/commit-preview` compute a plan and approval token.
- `POST /api/v1/teamwork/commit` remains disabled until the preview token, expected project id, expected version, and validation gate all match.

Implementation notes:

- Use `EsiUtils.getTeamworkService()`, `getLockService(Project)`, `getRemoteProjectDescriptors()`, `getBranches(...)`, `getVersions(...)`, `isProjectChanged(...)`, `getLoggedUserName(...)`, and descriptor helpers as the typed starting point.
- Do not collect or store credentials in the Java plugin. If credentialed REST is later needed, implement it in Python with explicit env-var configuration and redacted logging.
- Treat local projects as a valid result, not an error: `available=true`, `projectMode=local`, `writeSupported=false`.
- All write routes must default to disabled in `BridgeCapabilities` until a disposable Teamwork project has live evidence.

Live gate:

- PASS for read-only support when the script proves local/server project mode and serializes descriptors or an explicit local-project unsupported result.
- PASS for write support only after preview, commit/update, and readback run against a disposable server project with recorded version before/after.

### Target 4: ReqIF And Requirements Import/Export

Goal: give AI a reliable requirements interchange path for ReqIF, CSV, JSON, and eventually DOORS/DataHub-linked workflows.

Files to add or change:

- `plugin/build.gradle` - optional `compileOnly` for `plugins/com.nomagic.requirements/requirements_api.jar`.
- `plugin/src/com/claude/cameo/bridge/handlers/ImportExportHandler.java`.
- `plugin/src/com/claude/cameo/bridge/util/ReqIFSerializer.java`.
- `plugin/src/com/claude/cameo/bridge/util/PatchPlanSerializer.java` if one does not already exist in reusable form.
- Python client/server methods for `cameo_get_import_export_capabilities`, `cameo_export_requirements`, `cameo_preview_requirements_import`, `cameo_apply_requirements_import`.
- `mcp-server/scripts/live_validate_reqif.py` and `mcp-server/scripts/live_validate_excel_roundtrip.py`.

Endpoint contract:

- `GET /api/v1/import-export/capabilities` returns CSV/JSON/XLSX bridge support plus native ReqIF class availability.
- `POST /api/v1/import-export/requirements/export` exports selected requirement elements to JSON/CSV and optionally native ReqIF.
- `POST /api/v1/import-export/requirements/import-preview` parses source input and returns a patch plan.
- `POST /api/v1/import-export/requirements/apply` applies a previously reviewed patch plan.
- `GET /api/v1/datahub/capabilities` remains a diagnostic probe until DataHub is installed.

Implementation notes:

- Use `ReqIFUtils.exportReqIFSpecifications(...)`, `exportReqIFElements(...)`, and `importReqIF(...)` only behind the native capability probe.
- Native import must not write directly in the first slice. First capture the native API's behavior on a disposable project, then decide whether it can produce a preview. If no preview is possible, require a scratch project and explicit `allowNativeWrite=true`.
- The bridge-owned CSV/XLSX path should resolve rows by stable Cameo element id first, then by external key tag, then by exact qualified name. Ambiguous matches are hard failures.

Live gate:

- PASS for bridge-owned Excel/CSV when export -> edited input -> preview -> apply -> readback works on a disposable requirements package.
- PASS for native ReqIF only after sample ReqIF export/import roundtrip evidence exists.

### Target 5: Simulation And Parametric Execution

Goal: detect Simulation Toolkit availability and, if installed, run bounded simulations with captured outputs. In the current local install this is a probe-first target.

Files to add or change:

- `plugin/src/com/claude/cameo/bridge/handlers/SimulationHandler.java`.
- `plugin/src/com/claude/cameo/bridge/util/SimulationSerializer.java`.
- `plugin/src/com/claude/cameo/bridge/util/SimulationJobStore.java`.
- Python client/server methods for `cameo_get_simulation_capabilities`, `cameo_list_simulation_configurations`, `cameo_run_simulation`, `cameo_get_simulation_result`, `cameo_terminate_simulation`.
- `mcp-server/scripts/live_probe_simulation.py`.
- `mcp-server/scripts/live_validate_simulation.py` only after runtime classes are present.

Endpoint contract:

- `GET /api/v1/simulation/capabilities` must return a useful `available=false` diagnostic when Simulation Toolkit is absent.
- `GET /api/v1/simulation/configurations` is enabled only when runtime classes and profile stereotypes are visible.
- `POST /api/v1/simulation/run-preview` checks target/config compatibility without executing.
- `POST /api/v1/simulation/run` and `POST /api/v1/simulation/run-async` require `allowExecute=true`, timeout, and dry-run evidence.

Implementation notes:

- Do not add simulation jars to `build.gradle` until the actual installed jar path is found. Use reflection for the first route.
- Never let simulation execution run on an unbounded thread. Store jobs, enforce timeout, and expose termination.
- If simulation changes model state, the route must create before/after snapshots and mark the project dirtiness result.

Live gate:

- PASS in the current environment can be an unsupported diagnostic if it includes plugin directory scan, class lookup results, and project state.
- Execution support requires a separate PASS with a disposable executable model and output readback.

### Target 6: Criteria, Relation Map, Matrix, And Query Templates

Goal: replace hand-written placeholder expressions with UI-proven native criteria and make those templates reusable across relation maps, matrices, tables, legends, and smart packages.

Files to add or change:

- `plugin/src/com/claude/cameo/bridge/handlers/CriteriaHandler.java`.
- `plugin/src/com/claude/cameo/bridge/util/StructuredExpressionSerializer.java`.
- Extend `RelationMapHandler`, `MatrixHandler`, and `GenericTableHandler` only where they need typed apply hooks.
- Python tools: `cameo_get_criteria_capabilities`, `cameo_list_criteria_templates`, `cameo_build_criteria_expression`, `cameo_parse_criteria_expression`, `cameo_apply_criteria_template`, `cameo_capture_criteria_template_from_diff`.
- `mcp-server/scripts/live_validate_criteria_templates.py`.

Endpoint contract:

- `GET /api/v1/criteria/capabilities`
- `GET /api/v1/criteria/templates?target=relationMap|matrix|table|legend|smartPackage`
- `POST /api/v1/criteria/build`
- `POST /api/v1/criteria/parse`
- `POST /api/v1/criteria/apply`
- `POST /api/v1/criteria/capture-template-from-diff`

Implementation notes:

- UI-created settings are the source of truth. The script sequence is: snapshot -> user creates UI expression -> snapshot -> diff -> serialize native expression -> replay against disposable target -> verify.
- Each template must carry `verifiedWithUiDiff`, `verifiedInCatiaVersion`, `sourceSnapshotId`, `targetKinds`, `nativeExpressionShape`, and `failureModes`.
- Relation Map refresh remains opt-in. Criteria application must not silently trigger a heavy refresh unless `refresh=true`.

Live gate:

- PASS when a template captured from UI diff can be replayed into a new disposable relation map/matrix/table and the native property dump matches expected expression fields.

### Target 7: Deep Diagram Handlers

Goal: move high-value diagram work from generic element/presentation manipulation to typed handlers that understand sequence, state, activity, parametric, internal block, legend, and table semantics.

Files to add or change:

- `plugin/src/com/claude/cameo/bridge/handlers/TypedDiagramHandler.java` or specialized handlers such as `SequenceDiagramHandler.java` when the route family grows.
- `plugin/src/com/claude/cameo/bridge/util/DiagramSemanticSerializer.java`.
- Extend existing `DiagramHandler` only for common plumbing.
- Python tools: `cameo_get_typed_diagram_capabilities`, `cameo_inspect_typed_diagram`, `cameo_create_sequence_message`, `cameo_create_state_transition`, `cameo_create_parametric_binding`, `cameo_apply_diagram_legend`.
- `mcp-server/scripts/live_validate_typed_diagrams.py`.

Implementation notes:

- Gate every write by diagram type. A sequence-message route must reject non-sequence diagrams with `422 DIAGRAM_TYPE_UNSUPPORTED`.
- Use the OpenAPI sequence example as the typed path for messages and execution specifications.
- For state/parametric handlers, implement read-only inspection and class probes before mutation.
- Preserve layout evidence with render/verify screenshots after writes.

Live gate:

- PASS when each typed route creates one minimal disposable element/presentation pair, renders the diagram, and verifies nonblank output plus semantic readback.

### Target 8: Profile, DSL, Variant, Safety, And Cyber Extension Patterns

Goal: make AI able to inspect and install modeling extensions without pretending optional commercial add-ons are installed.

Files to add or change:

- `plugin/src/com/claude/cameo/bridge/handlers/ProfileHandler.java`.
- `plugin/src/com/claude/cameo/bridge/handlers/ExtensionProbeHandler.java`.
- `plugin/src/com/claude/cameo/bridge/util/ProfileSerializer.java`.
- `plugin/src/com/claude/cameo/bridge/util/ExtensionScanSerializer.java`.
- Python tools for profile create/apply/tagging and extension scans.
- `mcp-server/scripts/live_validate_profile_dsl.py`, `live_validate_variants.py`, `live_probe_extensions.py`.

Implementation notes:

- Reuse existing `ElementMutationHandler` stereotype/tag logic where possible; move only reusable serialization and route families into new handlers.
- Bridge-owned variant/safety/cyber patterns must be labeled as `mode=bridge-owned`.
- Native product-line, safety, cyber, and data-marking routes stay disabled until plugin directories, classes, and profile semantics are proven.
- Do not emit compliance claims. Emit evidence, trace gaps, and rule findings.

Live gate:

- PASS when a disposable profile with stereotype/tag definitions is created, applied to elements, read back, and cleaned up or explicitly marked dirty.
- Native extension support requires separate PASS evidence from an installed plugin/profile.

### Target 9: Build, Capability, And Plugin Startup Hardening

Goal: prevent optional integrations from making the bridge fragile.

Files to add or change:

- `plugin/build.gradle` - add an `optionalCompileOnly` helper.
- `plugin/plugin.xml` - do not add new optional products as required plugins.
- `plugin/src/com/claude/cameo/bridge/util/BridgeCapabilities.java` - add `available`, `mode`, `status`, and `warnings` fields per optional family.
- `mcp-server/tests/test_server.py` - verify unsupported capability responses are user-facing and structured.

Recommended Gradle helper:

```groovy
def optionalCompileOnly = { String jarPath ->
    def jar = file(jarPath)
    if (jar.exists()) {
        dependencies.add("compileOnly", files(jar))
    }
}

optionalCompileOnly("${cameoHome}/plugins/com.nomagic.magicdraw.reportwizard/reportwizard_api.jar")
optionalCompileOnly("${cameoHome}/plugins/com.nomagic.requirements/requirements_api.jar")
```

Startup acceptance:

- CATIA starts with only the core plugin set.
- `/api/v1/capabilities` still returns every optional family with `available=false` where absent.
- Missing optional classes never throw during plugin activation.

### Target 10: MCP Tool Quality Bar

Goal: every new capability is usable by an AI agent without reading Java code.

For each tool:

- Name it after the user-facing action, not the Java class.
- Include `projectState`, `capabilityStatus`, and `evidencePath` in outputs where relevant.
- Validate required IDs and mode flags in Python before sending the HTTP request when possible.
- Return actionable unsupported messages, for example: `Simulation Toolkit classes were not found in the installed CATIA Magic plugin directories; run live_probe_simulation.py after installing the toolkit.`
- Add one happy-path mocked test and at least one unsupported/error-path test.

## Research Resolution Protocol

Several Autopilot capabilities depend on CATIA Magic plugins whose public API varies by installed version, license, and plugin set. Do not leave those items as open-ended research. Resolve each target with the same four-step playbook before implementing a write endpoint:

1. **Classpath proof**: add a read-only probe route or `ScriptProbeHandler` template that checks whether the expected classes can be loaded with `Class.forName(...)`, records the loaded code source where available, and returns `available=false` instead of throwing.
2. **Read-only inventory**: expose a capability route that lists the native objects the user can already see in the UI, such as validation suites, report templates, simulation configurations, teamwork metadata, DataHub sources, profiles, or diagram presentations.
3. **Disposable live proof**: run the smallest possible native operation against a throwaway package/project and write before/after evidence under `mcp-server/validation-output/<feature>/<timestamp>/`.
4. **Typed production route**: only after steps 1-3 pass, add write/generation routes, MCP wrappers, tests, docs, and changelog entries. If any step fails, ship the unsupported diagnostic response and keep the capability in `probing` or `blocked`.

Each probe response must include:

- `available`: boolean
- `status`: `available`, `missing-class`, `missing-plugin`, `missing-license`, `not-open-project`, `local-project-only`, `unsupported-version`, `timeout`, or `error`
- `detectedClasses`
- `detectedPlugins`
- `projectMode`: `none`, `local`, `teamwork`, or `unknown`
- `licenseSignals`
- `nextAction`
- `warnings`

Use these public documentation anchors only as starting evidence, then confirm against the installed local jars and live CATIA session:

- Validation: `com.nomagic.magicdraw.validation` package, especially `ValidationHelper`, `ValidationRunData`, and `RuleViolationResult`.
- Simulation: Cameo Simulation Toolkit documents state that Java API classes live in `plugins/com.nomagic.magicdraw.simulation/simulation_api.jar` and local JavaDoc is available under `<MagicDraw installation directory>/openapi/docs/simulation/SimulationJavaDoc.zip`.
- Report Wizard: `com.nomagic.magicdraw.magicreport.helper.ReportHelper` is documented as an OpenAPI helper for templates; generation APIs still need local probing.
- Teamwork: OpenAPI project descriptors distinguish local and remote descriptors, and save/load can map to commit/update for Teamwork projects; do not assume that current Magic Collaboration Studio auth exposes the same operations.
- DataHub/ReqIF/DOORS, Product Line, Safety, Cyber, and Data Markings: treat as optional extension plugins and prove installation before route registration claims more than diagnostics.

## Standard Live Evidence Layout

All new `mcp-server/scripts/live_*.py` scripts must accept this common CLI surface unless a capability cannot support writes:

```powershell
python scripts\<script>.py --base-url http://127.0.0.1:18740/api/v1 --out validation-output\<feature> --timestamped --require-open-project
```

Mutation-capable scripts must additionally support:

```powershell
--allow-write --cleanup --scratch-prefix AutopilotScratch --timeout-seconds 120
```

Use this artifact layout:

```text
validation-output/<feature>/<YYYYMMDD-HHMMSS>/
  manifest.json
  status.json
  capabilities.json
  project.json
  request.json
  response.json
  before-snapshot.json
  after-snapshot.json
  diff.json
  findings.json
  summary.md
  logs/
```

Pass/fail rules:

- `PASS`: route works, evidence is written, expected readback IDs match, and cleanup either succeeds or is explicitly marked unnecessary.
- `UNSUPPORTED`: probe proves the CATIA plugin, license, project mode, or native class is unavailable and returns a structured unsupported response.
- `FAIL`: bridge crashes, CATIA hangs, route returns unstructured errors, output artifacts are missing, write readback does not match, or cleanup leaves unexpected model content.

Disposable model strategy:

- Prefer a dedicated scratch package named `AutopilotScratch_<timestamp>` in the open test model.
- For profile/DSL, simulation, and Teamwork work, prefer a separate disposable `.mdzip` or server test project because cleanup can be incomplete or commit history can persist.
- Never use private course models as the only proof. If a course model is used for convenience, also create a minimal non-sensitive sample or document why the capability could not be proven generically.
- End every write script with `/api/v1/project` readback and model dirtiness reporting. Do not assume deleting a scratch package makes the model clean.

## Standard Delivery Checklist For Every Capability

Every capability below must include the following before it is considered done:

1. Java route in an appropriate handler or a new handler.
2. Route registration in `HttpBridgeServer.java`.
3. Capability metadata in `BridgeCapabilities.java`.
4. Python async client method in `mcp-server/cameo_mcp/client.py`.
5. MCP tool wrapper in `mcp-server/cameo_mcp/server.py`.
6. Unit tests in `mcp-server/tests/test_client.py` and/or `mcp-server/tests/test_server.py`.
7. Java tests where logic can be isolated without CATIA UI.
8. Live validation script in `mcp-server/scripts/`.
9. Output artifacts under `mcp-server/validation-output/<feature-name>/`.
10. Docs and examples under `docs/`.
11. `CHANGELOG.md` update.
12. Failure-mode tests for missing project, wrong diagram type, unsupported plugin, missing license, timeout, and write-in-progress.

## Capability Status Ledger

Create and maintain `docs/strategy/autopilot-capability-status.md` before implementation starts. This file is the source of truth for parallel work; do not infer status from branch names, chat notes, or partial code.

Required table columns:

- `id`: capability number from the portfolio map.
- `capability`: short name.
- `owner`: person or agent currently responsible; `unassigned` is allowed.
- `phase`: `foundation`, `core-mbse`, `advanced-integration`, or `extension-pattern`.
- `status`: `not-started`, `probing`, `implemented`, `unit-tested`, `live-verified`, `blocked`, or `deferred`.
- `java_routes`: exact route family or `none`.
- `mcp_tools`: exact MCP tool names or `none`.
- `optional_dependency`: jar/plugin/license dependency, if any.
- `evidence_path`: latest `mcp-server/validation-output/<feature>/<timestamp>/` path.
- `blocking_risk`: one sentence describing the highest current risk.
- `next_gate`: the next concrete validation gate.

Rules:

- Update the ledger in the same PR/commit as any route, MCP tool, or live script change.
- Mark a capability `implemented` only after Java route registration, capability metadata, Python client, and MCP tool wrapper exist.
- Mark `unit-tested` only after both mocked client/server tests pass or the ledger records why one side is not applicable.
- Mark `live-verified` only when the evidence directory contains status, capabilities, project state, request, response, and summary artifacts.
- Mark optional-product capabilities `blocked` or `deferred`, not failed, when the local CATIA installation lacks the required plugin or license.
- Never mark advanced write routes `live-verified` from a private course model alone; add disposable model evidence or record why generic proof is unavailable.

## Execution Order And Dependency Gates

Use this order to keep the program efficient. Later tracks may do read-only probing in parallel, but write routes must not bypass their gates.

| Gate | Work unlocked | Must pass first | Blocks if missing |
|---|---|---|---|
| G0 Baseline | Any implementation | `live_capture_capabilities.py`, repo status, current `/status`, `/capabilities`, `/project` | Unknown bridge version, no open project for live write proof |
| G1 Shared contracts | New write endpoints | `ElementRef`, `PresentationRef`, `OperationReceipt`, `PatchPlan`, `ValidationFinding` response shapes documented and adopted by one slice | Inconsistent MCP outputs and hard-to-audit AI writes |
| G2 Snapshot/diff | Criteria, repair, import/apply, variant/profile install | snapshot create/list/get/diff routes verified live | No reliable proof of what changed |
| G3 Universal inspection | Natural-language edit, traceability, completeness, dashboards | deep inspection can read elements, relationships, stereotypes/tags, presentations, specifications | AI cannot explain or validate proposed changes |
| G4 Native validation | pre-commit review, validation-rule authoring, release/demo gates | validation classes probed and at least one native run or structured unsupported result recorded | Review gates become bridge-owned heuristics only |
| G5 UI-derived criteria | relation maps, matrices, smart packages, legends, advanced queries | UI diff capture and replay of one criteria template | Hand-written expressions drift from CATIA semantics |
| G6 Diagram proof | diagram compiler, repair, typed diagram handlers | semantic readback plus PNG/render verification for one disposable diagram | Created diagrams may be invisible or semantically empty |
| G7 Optional product probe | Report Wizard, ReqIF, Simulation, Teamwork, DataHub, variants, safety/cyber | classpath/plugin/license probe and read-only inventory | Optional jars break startup or routes overclaim support |
| G8 Disposable write proof | optional product write/generate/sync routes | preview route plus disposable live proof with before/after evidence | Risk of accidental shared-server writes or irreversible imports |

Hard sequencing requirements:

- Implement Sprint 1 inspection and receipt contracts before broad natural-language edit tools.
- Implement snapshot/diff evidence before criteria replay, import/apply, extension installation, or large diagram repair work.
- Implement native validation before the pre-commit review gate claims to run CATIA validation.
- Implement Report Wizard template listing before report generation.
- Implement Teamwork read-only project/history/lock inspection before any commit/update preview.
- Implement ReqIF export and bridge-owned CSV/JSON preview before native ReqIF import.
- Keep Simulation, DataHub, product-line, safety, and cyber routes probe-only until local plugin directories, classes, and licensing are proven.

Parallelizable work after G0:

- Team A can build shared Java serializers and inspection handlers.
- Team B can build MCP patch-plan and methodology wrapper logic against mocked client responses.
- Team C can build live evidence harnesses and artifact writers.
- Team D can run optional dependency probes and document unsupported states.
- Team E can prepare docs, examples, and status ledger templates.

## Roadblock Playbooks

Use these responses when a feature stalls. The goal is to preserve forward motion while avoiding misleading capability claims.

### CATIA Or Bridge Not Reachable

- Check `http://127.0.0.1:18740/api/v1/status` first, then `/api/v1/capabilities`, then `/api/v1/project`.
- If a Cameo process exists but `/status` fails, treat the bridge as down; restart CATIA after redeploying the plugin.
- If `/project` returns no open project, allow read-only capability probes but block live write validation.
- Record the blocker in the capability ledger with `next_gate=Open project and rerun baseline capture`.

### Optional Jar Missing At Build Time

- Do not add the jar as a required dependency.
- Add an optional `compileOnly` entry only when the file exists under `cameoHome`.
- Keep handler startup independent of optional classes by using reflection or isolating hard references behind classes that only load when the jar exists.
- `/capabilities` for that family must return `available=false`, `status=missing-plugin` or `missing-class`, and `nextAction`.

### Native API Surface Differs From Documentation

- Preserve the probe output under `validation-output/<feature>/`.
- Narrow the first implementation to inventory/list routes.
- Add a compatibility note to the status ledger, including CATIA version and code source path for loaded classes.
- Do not implement write routes from public docs alone; require local `javap`, reflection, or OpenAPI example evidence.

### Native Operation Hangs Or Blocks The UI

- Move the operation behind an explicit route with `timeoutMillis` and `allowExecute` or `allowWrite`.
- Store job status in a feature-specific job store and expose polling.
- Return `504 <FEATURE>_TIMEOUT` with partial diagnostics when possible.
- Add a live script timeout shorter than the user's normal CATIA tolerance so validation fails before the desktop becomes unusable.

### Write Readback Does Not Match

- Mark the capability `implemented` or `unit-tested`, not `live-verified`.
- Persist before/after snapshots and a diff even for failed runs.
- Add a failing semantic acceptance note to `summary.md`.
- Fix the typed handler before adding MCP-level workarounds.

### Course Model Is The Only Available Proof

- Run the live proof only with explicit user approval for that model.
- Write evidence under a path that names the model and marks sensitivity.
- Create a follow-up task for a disposable sample model before release notes claim general support.

## Repo Integration Playbook

Use this section as the mechanical implementation checklist for every new endpoint and MCP tool.

### Java Handler Pattern

- Put route families under `plugin/src/com/claude/cameo/bridge/handlers/<Feature>Handler.java`.
- Implement `HttpHandler` directly, following the routing style in `MatrixHandler`, `RelationMapHandler`, `GenericTableHandler`, and `SnapshotHandler`.
- Parse request bodies and query parameters with `JsonHelper` helpers instead of manual string parsing.
- Resolve elements by ID inside the handler and return `BAD_REQUEST` for invalid IDs, `CONFLICT` for no open project or unavailable native state, and `NOT_FOUND` for unknown subroutes.
- Use `EdtDispatcher.read(...)` for inspection and computation that touches CATIA model/UI state.
- Use `EdtDispatcher.write("MCP Bridge: <operation>", ...)` for any mutation.
- Do not call potentially blocking native refresh/generation APIs implicitly. If a native refresh, report generation, simulation, Teamwork call, or DataHub sync can block, make it an explicit route with request timeout fields and response timing.
- Serialize model elements with `ElementSerializer`, presentation elements with `PresentationSerializer`, presentation/model properties with `PropertySerializer`, and snapshot/diff payloads with `SnapshotStore` and `JsonDiff`.
- Return the shared contracts in this plan. If an older route shape must remain stable, nest the new payload under `receipt`, `finding`, `evidence`, or `diagnostics` rather than replacing legacy top-level fields.

### Route Registration Pattern

- Add each new handler import and `server.createContext(...)` entry in `plugin/src/com/claude/cameo/bridge/HttpBridgeServer.java`.
- Prefer one context per route family, for example `/api/v1/validation`, `/api/v1/simulation`, `/api/v1/teamwork`, `/api/v1/datahub`.
- Keep legacy `/status` and `/capabilities` behavior untouched.
- Add every new route to `plugin/src/com/claude/cameo/bridge/util/BridgeCapabilities.java` with the correct group, MCP tool name, method, path, and `read` or `write` mode.
- Update `BridgeCapabilitiesTest` when capability count or required endpoints change.

### Python MCP Pattern

- Add low-level async HTTP wrappers to `mcp-server/cameo_mcp/client.py` near the related existing family. Follow existing `_request(...)` usage and normalize user-facing aliases in the client layer.
- Add user-facing tools to `mcp-server/cameo_mcp/server.py` with explicit docstrings, typed arguments, and `_mcp_result(result)`.
- If a feature has substantial MCP-side logic, add a focused module such as `criteria.py`, `traceability_autopilot.py`, `simulation.py`, or `excel_roundtrip.py`, then keep `server.py` as the tool boundary.
- Add tests in `mcp-server/tests/test_client.py` for request method/path/body/query construction.
- Add tests in `mcp-server/tests/test_server.py` for MCP argument mapping, alias handling, and error passthrough.
- If a tool produces deterministic analysis without CATIA, unit-test the analysis module directly.

### Live Validation Pattern

- Each live script goes under `mcp-server/scripts/live_validate_<feature>.py` or `live_probe_<feature>.py`.
- Every script starts by capturing `/api/v1/status`, `/api/v1/capabilities`, and `/api/v1/project`.
- If no project is open, fail with a clear message before any write attempt.
- Write artifacts under `mcp-server/validation-output/<feature-name>/<timestamp>/`.
- Persist at minimum: request JSON, raw response JSON, normalized summary JSON, and a Markdown run summary.
- For any write validation, create a disposable package named `MCP Autopilot Validation - <feature> - <timestamp>`, write only under it, and include snapshot IDs before and after.
- Default scripts to read-only. Require `--allow-write` for mutation, generation, sync, simulation execution, report generation, or profile creation.
- End by reporting project dirtiness and whether cleanup was attempted.

## SysML Semantic Acceptance Baseline

All Autopilot features that create or repair SysML content must satisfy these semantic checks in addition to endpoint-level tests:

- Requirements: every created or modified requirement has stable `id` and `text`, requirement stereotypes/tags survive readback, and derived/refined/satisfied/verified links use the correct SysML relationship type.
- Blocks and decomposition: part properties are typed by blocks, ownership and package placement are explicit, and decomposition does not create duplicate or orphan part structures.
- Ports and interfaces: proxy/full ports have type IDs, interface blocks own flow properties, directions are preserved, connectors bind compatible ports, and item flows expose conveyed classifiers plus realizing connectors.
- Activities: control flows connect control-compatible nodes, object flows carry typed object tokens, activity parameters line up with external entering/exiting flows, and swimlanes/partitions map to responsible blocks or parts.
- Allocation: allocations must be readable in both relationship lists and native allocation matrix cells, with direction and owner context clear enough to explain source and target.
- Parametrics: constraint blocks own constraint parameters, constraint properties are typed by constraint blocks, binding connectors connect compatible value/constraint parameters, and value properties have type/unit/default where known.
- Matrices and Relation Maps: generated artifacts must prove row/column or node/edge membership against expected element IDs, not just prove that an artifact was created.
- Diagrams: every diagram write must be followed by presentation readback and visual verification when a PNG/image endpoint exists.
- Evidence: every semantic validator must return element IDs and model locations, not only human-readable names.

## Shared Response Contracts

Implement these common response shapes early and reuse them.

### ElementRef

Fields:

- `id`
- `name`
- `type`
- `humanType`
- `ownerId`
- `ownerName`
- `ownerType`
- `qualifiedName`
- `stereotypes`
- `isReadOnly`
- `isProxy`

### PresentationRef

Fields:

- `presentationId`
- `presentationType`
- `diagramId`
- `diagramName`
- `element`
- `bounds`
- `pathPoints`
- `propertiesSummary`
- `warnings`

### OperationReceipt

Fields:

- `operation`
- `requestId`
- `startedAt`
- `completedAt`
- `durationMillis`
- `dryRun`
- `changed`
- `created`
- `modified`
- `deleted`
- `skipped`
- `warnings`
- `errors`
- `snapshotBeforeId`
- `snapshotAfterId`
- `diffSummary`
- `validationSummary`

### PatchPlan

Fields:

- `planId`
- `intent`
- `scope`
- `operations`
- `expectedChanges`
- `preconditions`
- `rollbackPlan`
- `riskLevel`
- `requiresApproval`

### ValidationFinding

Fields:

- `findingId`
- `severity`
- `ruleId`
- `ruleName`
- `message`
- `element`
- `presentation`
- `source`
- `suggestedFixes`
- `autoFixable`

## Team Structure

Recommended parallel ownership:

- **Team A, Core Java Bridge**: handlers, session safety, serialization, CATIA API adapters.
- **Team B, Python MCP Surface**: client wrappers, MCP tools, schemas, tests.
- **Team C, Live Validation and Evidence**: scripts, validation-output snapshots, demo models.
- **Team D, Advanced Integrations**: Simulation, Teamwork, Report Wizard, DataHub, Excel.
- **Team E, Product/Docs**: examples, workflow recipes, release notes, community demo scripts.

Coordination rule: no team should revert another team's work. If a shared file must be edited, reserve a section or coordinate through small patches.

## Capability Portfolio Map

| # | Capability | Primary Sprint | Lead Team | Implementation Class |
|---:|---|---|---|---|
| 1 | Universal model inspector | 1 | A/B/C | Foundation |
| 2 | Human UI diff recorder | 2 | A/B/C | Foundation |
| 3 | Generic criteria expression builder | 5 | A/B/C | Core MBSE |
| 4 | Native validation suite runner | 7 | A/B/C | Core MBSE |
| 5 | Pre-commit review gate | 7 | B/C | Core MBSE |
| 6 | Requirements automation suite | 4 | A/B/C | Core MBSE |
| 7 | Traceability autopilot | 5 | B/C | Core MBSE |
| 8 | Relation Map mastery | 5 | A/B/C | Core MBSE |
| 9 | Matrix mastery | 5 | A/B/C | Core MBSE |
| 10 | Diagram intent compiler | 6 | B/C | Core MBSE |
| 11 | Diagram repair engine | 6 | A/B/C | Core MBSE |
| 12 | ICD automation | 6 | A/B/C | Core MBSE |
| 13 | Simulation/parametric execution bridge | 9 | A/D/C | Advanced |
| 14 | Trade study engine | 9 | B/D/C | Advanced |
| 15 | Report Wizard automation | 8 | A/D/C | Advanced |
| 16 | Cameo Collaborator publishing | 8 | D/C | Advanced |
| 17 | Teamwork Cloud / Magic Collaboration bridge | 10 | D/A/C | Advanced |
| 18 | Change impact analyzer | 10 | B/C | Advanced |
| 19 | Model completeness dashboard | 4, 7 | B/C | Core MBSE |
| 20 | Natural-language model query | 3 | B/C | Foundation |
| 21 | Natural-language model edit with proof | 3 | B/C | Foundation |
| 22 | Model recipe library | 3 | B/E | Foundation |
| 23 | Methodology wizard replacement | 3 | B/E/C | Foundation |
| 24 | Profile/DSL authoring assistant | 12 | A/B/C | Advanced |
| 25 | SysML pattern library | 3, 12 | B/E/C | Foundation |
| 26 | DataHub/ReqIF/CSV/DOORS bridge | 11 | D/C | Advanced |
| 27 | Excel roundtrip | 11 | B/D/C | Advanced |
| 28 | Model-to-document proofing | 8 | B/C/E | Core MBSE |
| 29 | AI-generated validation rules | 7, 12 | A/B/C | Advanced |
| 30 | Evidence bundle generator | 2, 8 | B/C/E | Foundation |
| 31 | Server/API diagnostics tool | 2 | A/B/C | Foundation |
| 32 | Undo-safe transaction layer | 1 | A/B/C | Foundation |
| 33 | Diagram-specific deep handlers | 6, 12 | A/C | Core MBSE |
| 34 | Variant/product-line support | 12 | A/B/C | Advanced |
| 35 | Safety/cyber extension hooks | 12 | A/B/C | Advanced |

## Sprint 0: Program Setup And Safety Rail

**Goal**: Make the work executable by multiple coding agents without corrupting the model, repo, or CATIA session.

**Demo/Validation**:

- Bridge is reachable.
- Repo status is captured.
- Baseline Python and Java builds pass or known failures are documented.
- Live validation output directory exists.

### Task 0.1: Create Program Tracking Files

- **Location**:
  - `docs/plans/cameo-ai-systems-engineer-autopilot-plan.md`
  - `docs/strategy/catia-magic-feature-access-ranking.md`
  - `docs/strategy/autopilot-capability-status.md` new
- **Description**:
  - Add a status table with all 35 capabilities.
  - Track fields: `owner`, `status`, `branch`, `javaRoutes`, `mcpTools`, `unitTests`, `liveValidation`, `knownRisks`.
- **Dependencies**: none
- **Acceptance Criteria**:
  - Each capability has one current owner or is explicitly unassigned.
  - Status values are limited to `not-started`, `probing`, `implemented`, `unit-tested`, `live-verified`, `blocked`, `deferred`.
- **Validation**:
  - Manual review.

### Task 0.2: Establish Build And Deploy Commands

- **Location**:
  - `docs/development/build-and-live-validation.md` new or existing docs update
- **Description**:
  - Document reliable local-temp Gradle build workflow for Windows/network share.
  - Document Python test command.
  - Document plugin deployment target and restart requirement.
- **Acceptance Criteria**:
  - Any engineer can rebuild and deploy without relying on chat history.
- **Validation**:
  - Run:
    - `python -m pytest tests\test_client.py tests\test_server.py`
    - Gradle plugin build from local temp copy with JDK 17.

### Task 0.3: Freeze Baseline Capability Manifest

- **Location**:
  - `mcp-server/scripts/live_capture_capabilities.py` new
  - `mcp-server/validation-output/autopilot-baseline/`
- **Description**:
  - Add script to capture `/status`, `/capabilities`, `/project`, `/ui/state`, active diagram, and repo version info.
- **Acceptance Criteria**:
  - Script writes one JSON bundle with timestamp and bridge version.
- **Validation**:
  - Run against live CATIA and inspect output.

### Task 0.4: Define Versioning Policy

- **Location**:
  - `CHANGELOG.md`
  - `plugin/plugin.xml`
  - `mcp-server/pyproject.toml`
- **Description**:
  - Decide whether this program is `2.4.x`, `2.5.x`, or `3.0.0`.
  - Recommendation: use `2.4.x` for foundation/core MBSE, reserve `3.0.0` for advanced integrations.
- **Acceptance Criteria**:
  - Version bump policy documented before implementation starts.
- **Validation**:
  - Manual review.

## Sprint 1: Core Inspection And Transaction Foundation

**Goal**: Build the foundation needed for safe AI delegation: universal readback, typed receipts, dry-run support, rollback-friendly snapshots, and serialized write safety.

**Capabilities covered**: 1, 20, 21, 31, 32.

**Demo/Validation**:

- Ask for any package/diagram/element and receive a complete model-inspection packet.
- Create a dry-run edit plan and see predicted changes without modifying the model.
- Apply a small approved edit and receive before/after snapshots, diff, and rollback instructions.

### Task 1.1: Universal Model Inspector Endpoint

- **Capability**: 1, Universal model inspector
- **Location**:
  - `plugin/src/com/claude/cameo/bridge/handlers/InspectionHandler.java` new
  - `plugin/src/com/claude/cameo/bridge/util/ElementSerializer.java` if existing, otherwise create or extend
  - `plugin/src/com/claude/cameo/bridge/util/PropertySerializer.java`
  - `plugin/src/com/claude/cameo/bridge/util/PresentationSerializer.java`
  - `HttpBridgeServer.java`
  - `BridgeCapabilities.java`
- **Routes**:
  - `GET /api/v1/inspect/elements/{elementId}`
  - `POST /api/v1/inspect/elements`
  - `GET /api/v1/inspect/packages/{packageId}/summary`
  - `GET /api/v1/inspect/diagrams/{diagramId}/deep`
- **Request fields**:
  - `includeOwnedElements`
  - `includeRelationships`
  - `includeStereotypes`
  - `includeTaggedValues`
  - `includePresentations`
  - `includeSpecifications`
  - `maxDepth`
  - `maxElements`
  - `summaryOnly`
- **Implementation instructions**:
  - Reuse existing query and property dump logic where possible.
  - Use stable `ElementRef` and `PresentationRef` response contracts.
  - Include warnings when a field is unavailable rather than failing the whole request.
  - Limit recursive traversal by `maxDepth` and `maxElements`.
  - Never mutate model state in inspector routes.
- **Acceptance Criteria**:
  - Can inspect a requirement and see id/text/specification/stereotypes/tags/relationships.
  - Can inspect a block and see ports/properties/connectors.
  - Can inspect a diagram and see presentation elements, backing model elements, bounds, paths, and properties.
  - Handles missing element ID with `404`.
  - Handles no open project with clear `409`.
- **Validation**:
  - Unit tests for client wrapper body/query parameters.
  - Live script: `scripts/live_validate_universal_inspector.py`.
  - Output: `validation-output/universal-inspector/summary.json`.

### Task 1.2: Typed Operation Receipt Utility

- **Capability**: 32, Undo-safe transaction layer
- **Location**:
  - `plugin/src/com/claude/cameo/bridge/util/OperationReceipt.java` new
  - `plugin/src/com/claude/cameo/bridge/util/ReceiptBuilder.java` new
  - Existing write handlers incrementally adopt it.
- **Description**:
  - Create a shared Java utility for receipts across write operations.
  - Include request ID, timestamps, changed IDs, warnings, snapshot IDs, validation summaries.
- **Dependencies**: existing snapshot store
- **Acceptance Criteria**:
  - New write endpoints return consistent receipt fields.
  - Existing endpoints can adopt this without breaking old clients by nesting under `receipt`.
- **Validation**:
  - Unit tests for JSON shape if practical.
  - Python tests asserting receipt parsing.

### Task 1.3: Dry-Run And Patch Plan Contract

- **Capabilities**: 21, Natural-language model edit with proof; 32, Undo-safe transaction layer
- **Location**:
  - `mcp-server/cameo_mcp/patch_plan.py` new
  - `mcp-server/cameo_mcp/server.py`
  - `mcp-server/cameo_mcp/client.py`
- **MCP tools**:
  - `cameo_prepare_patch_plan`
  - `cameo_apply_patch_plan`
  - `cameo_validate_patch_plan`
- **Implementation instructions**:
  - The Java plugin should not parse natural language.
  - The MCP layer converts agent-proposed operations into explicit endpoint calls.
  - `prepare` returns a plan only.
  - `apply` requires structured operations and optionally `requireApprovalToken`.
  - Every apply call creates snapshot before and after.
- **Acceptance Criteria**:
  - A patch plan can create one element, modify a field, create one relationship, and add to diagram.
  - The plan can be validated without applying.
  - The plan records rollback instructions.
- **Validation**:
  - Unit tests for plan schema and invalid operations.
  - Live validation on a disposable package.

### Task 1.4: Transaction Guard And Rollback Markers

- **Capability**: 32, Undo-safe transaction layer
- **Location**:
  - `EdtDispatcher.java`
  - `SnapshotStore.java`
  - `ProjectHandler.java`
  - `mcp-server/cameo_mcp/client.py`
- **Description**:
  - Extend serialized write guard with operation IDs and explicit in-progress readback.
  - Add `GET /api/v1/session/write-state`.
  - Add optional `snapshotBefore=true` and `snapshotAfter=true` for write endpoints.
- **Acceptance Criteria**:
  - Concurrent writes fail clearly with active write name and age.
  - Timed-out write state can be queried.
  - Snapshot IDs are included when requested.
- **Validation**:
  - Unit test route behavior where possible.
  - Manual stress smoke with two overlapping harmless writes.

### Task 1.5: Server/API Diagnostics Tool

- **Capability**: 31, Server/API diagnostics tool
- **Location**:
  - `plugin/src/com/claude/cameo/bridge/handlers/DiagnosticsHandler.java` new
  - `mcp-server/scripts/live_diagnose_bridge.py` new
  - `mcp-server/cameo_mcp/server.py`
- **Routes/tools**:
  - `GET /api/v1/diagnostics`
  - `POST /api/v1/diagnostics/resolve-element`
  - MCP `cameo_diagnose_bridge`
  - MCP `cameo_resolve_model_reference`
- **Implementation instructions**:
  - Diagnose project open status, dirty state, active write, plugin version, installed capabilities, missing handlers, active diagram.
  - Resolve ambiguous references by ID, name, qualified name, stereotype, owner path.
  - Include "why not found" hints.
- **Acceptance Criteria**:
  - Explains no project, wrong project, stale element ID, duplicate names, missing stereotype, unsupported endpoint.
- **Validation**:
  - Live script with valid and invalid IDs.

## Sprint 2: Evidence, UI Diff, And Community-Grade Troubleshooting

**Goal**: Make hidden CATIA UI behavior observable and reusable.

**Capabilities covered**: 2, 30, 31, supports 3, 8, 9, 11, 15, 17.

**Demo/Validation**:

- User changes a setting in the UI.
- Agent captures before/after snapshots and produces a structured diff.
- Agent converts the diff into a candidate endpoint/template update.

### Task 2.1: Human UI Diff Recorder Workflow

- **Capability**: 2, Human UI diff recorder
- **Location**:
  - `SnapshotHandler.java`
  - `JsonDiff.java`
  - `mcp-server/cameo_mcp/ui_diff.py` new
  - `mcp-server/scripts/live_record_ui_diff.py` new
- **MCP tools**:
  - `cameo_start_ui_diff_capture`
  - `cameo_finish_ui_diff_capture`
  - `cameo_explain_ui_diff`
- **Implementation instructions**:
  - Use snapshots with scopes: `project`, `diagram`, `relationMap`, `matrix`, `table`, `selection`.
  - Store capture metadata: active diagram, selected elements, operation label, user notes.
  - Diff must classify changes into model elements, presentation properties, tagged values, diagram settings, relation criteria, matrix criteria, table columns.
- **Acceptance Criteria**:
  - Captures a human-created Relation Map criteria change.
  - Captures a diagram presentation property change.
  - Produces a minimized diff excluding timestamps/noise.
- **Validation**:
  - Live manual script with prompts.
  - Save artifacts under `validation-output/ui-diff-recorder/`.

### Task 2.2: Evidence Bundle Generator

- **Capability**: 30, Evidence bundle generator
- **Location**:
  - `mcp-server/cameo_mcp/evidence.py` new
  - `mcp-server/scripts/live_generate_evidence_bundle.py` new
  - `mcp-server/cameo_mcp/server.py`
- **MCP tool**:
  - `cameo_generate_evidence_bundle`
- **Bundle contents**:
  - Project status and capabilities
  - Active diagram and selection
  - Selected element inspections
  - Traceability graph
  - Matrix summaries
  - Relation Map summaries
  - Validation results
  - Diagrams/images
  - Snapshot diff
  - Markdown executive summary
- **Acceptance Criteria**:
  - One command produces a directory with JSON, images, and `summary.md`.
  - Bundle is deterministic enough to compare across runs.
- **Validation**:
  - Run on an approved validation model and a small synthetic model.

### Task 2.3: UI Evidence To Implementation Template

- **Capabilities**: 2, 3, 8, 9, 11
- **Location**:
  - `docs/templates/ui-diff-to-endpoint.md` new
  - `mcp-server/cameo_mcp/ui_diff.py`
- **Description**:
  - Add a generator that turns a diff into an implementation note:
    - observed setting
    - owning element/presentation
    - native property/tag/criteria path
    - proposed Java class/method
    - proposed endpoint request/response
    - live validation scenario
- **Acceptance Criteria**:
  - Running on a Relation Map UI diff produces a developer-ready note.
- **Validation**:
  - Manual review.

## Sprint 3: Natural-Language Query, Recipes, And Methodology Autopilot

**Goal**: Give the AI agent reliable model-query and workflow primitives while keeping deterministic execution in the MCP layer.

**Capabilities covered**: 20, 21, 22, 23, 25.

**Demo/Validation**:

- Ask "which requirements lack satisfy links?" and receive exact elements.
- Ask "build a stakeholder-to-physical traceability packet" and receive a patch plan with artifacts.
- Execute a recipe in a disposable package and validate it.

### Task 3.1: Model Query DSL

- **Capability**: 20, Natural-language model query
- **Location**:
  - `mcp-server/cameo_mcp/query_dsl.py` new
  - `mcp-server/cameo_mcp/server.py`
  - Java inspector endpoints from Sprint 1
- **MCP tools**:
  - `cameo_query_model_dsl`
  - `cameo_explain_query_result`
- **Implementation instructions**:
  - Do not send natural language into Java.
  - Define a JSON DSL: element type, stereotype, owner path, relationship predicates, missing relationship predicates, tag filters, text filters.
  - Natural-language mapping is done by the AI client using this schema.
- **Acceptance Criteria**:
  - Query for unsatisfied requirements.
  - Query for blocks with ports but no interface block.
  - Query for diagrams owned by a package.
  - Query for elements changed in a snapshot diff.
- **Validation**:
  - Unit tests for DSL normalization.
  - Live validation using known model content.

### Task 3.2: Natural-Language Edit With Proof

- **Capability**: 21, Natural-language model edit with proof
- **Location**:
  - `patch_plan.py`
  - `query_dsl.py`
  - `mcp-server/cameo_mcp/server.py`
- **Description**:
  - Add a documented workflow:
    1. Query context.
    2. Prepare patch plan.
    3. Present diff prediction.
    4. Apply only approved structured operations.
    5. Validate and generate evidence.
- **Acceptance Criteria**:
  - The tool rejects natural-language free text in `apply`.
  - Applying a plan returns receipt plus validation result.
- **Validation**:
  - Unit tests for unsafe direct apply rejection.
  - Live test on disposable package.

### Task 3.3: Model Recipe Library

- **Capability**: 22, Model recipe library
- **Location**:
  - `mcp-server/cameo_mcp/methodology/`
  - `mcp-server/cameo_mcp/recipes/` new if useful
  - `docs/recipes/` new
- **Recipe families**:
  - Requirement set creation
  - BDD creation
  - IBD creation
  - Activity decomposition
  - State machine creation
  - Traceability pack
  - Interface/ICD pack
  - Review bundle
- **Acceptance Criteria**:
  - Each recipe declares inputs, outputs, required MCP tools, validation checks, rollback plan.
  - At least five recipes run live.
- **Validation**:
  - `scripts/live_validate_recipes.py`.

### Task 3.4: Methodology Wizard Replacement

- **Capability**: 23, Methodology wizard replacement
- **Location**:
  - `mcp-server/cameo_mcp/methodology/registry.py`
  - `mcp-server/cameo_mcp/methodology/service.py`
- **Description**:
  - Extend methodology packs into executable guidance.
  - Each step can be `inspect`, `plan`, `apply`, `verify`, or `export`.
  - Add progress state so an agent can resume.
- **Acceptance Criteria**:
  - A methodology run can be paused after planning and resumed for apply.
  - Review packet shows completed/missing artifacts.
- **Validation**:
  - Unit tests for recipe state machine.
  - Live run on a disposable package.

### Task 3.5: SysML Pattern Library

- **Capability**: 25, SysML pattern library
- **Location**:
  - `docs/patterns/` new
  - `mcp-server/cameo_mcp/patterns.py` new
- **Patterns**:
  - Requirement pattern
  - Logical block/interface pattern
  - Physical allocation pattern
  - Activity flow pattern
  - State transition pattern
  - Verification case pattern
  - ICD pattern
- **Acceptance Criteria**:
  - Patterns are declarative JSON/YAML or Python dictionaries.
  - Pattern application yields a patch plan, not immediate mutation.
- **Validation**:
  - Unit tests for pattern expansion.

## Sprint 4: Requirements Automation And Completeness

**Goal**: Make requirements work nearly fully automatable and reviewable.

**Capabilities covered**: 6, 19, supports 5, 7, 28.

**Demo/Validation**:

- Generate requirement table, quality report, numbering report, missing trace report, and suggested fixes.

### Task 4.1: Requirements Package Inspector

- **Capability**: 6, Requirements automation suite
- **Location**:
  - `plugin/src/com/claude/cameo/bridge/handlers/RequirementsHandler.java` new
  - `mcp-server/cameo_mcp/requirements.py` new
- **Routes**:
  - `GET /api/v1/requirements`
  - `GET /api/v1/requirements/{id}`
  - `GET /api/v1/requirements/packages/{packageId}/analysis`
- **Response includes**:
  - Requirement ID/text/name
  - owner
  - derived/refined/satisfied/verified-by relationships
  - orphan status
  - duplicate ID status
  - quality findings
- **Acceptance Criteria**:
  - Can analyze a package of requirements without mutation.
- **Validation**:
  - Live package analysis.

### Task 4.2: Requirement Numbering And Uniqueness

- **Capability**: 6
- **Routes**:
  - `POST /api/v1/requirements/numbering/preview`
  - `POST /api/v1/requirements/numbering/apply`
  - `POST /api/v1/requirements/numbering/check`
- **Implementation instructions**:
  - First implement a bridge-owned numbering convention.
  - Then investigate native AutoID/ProfileApplicationNumbering APIs.
  - Keep native integration optional until live-proven.
- **Acceptance Criteria**:
  - Preview shows proposed numbering changes.
  - Apply creates snapshots and validates uniqueness.
- **Validation**:
  - Unit tests for numbering formats.
  - Live test on disposable requirements.

### Task 4.3: Requirement Table Parity

- **Capability**: 6
- **Location**:
  - `GenericTableHandler.java`
  - `RequirementsHandler.java`
- **Description**:
  - Create native or generic requirement tables with columns for id, text, owner, satisfy, verify, derive, refine, risk, status.
  - Use UI diff recorder to learn native Requirement Table settings.
- **Acceptance Criteria**:
  - A requirement table can be created and read back.
  - Table scope and columns are inspectable.
- **Validation**:
  - Live table creation in disposable package.

### Task 4.4: Model Completeness Dashboard

- **Capability**: 19, Model completeness dashboard
- **Location**:
  - `mcp-server/cameo_mcp/completeness.py` new
  - `mcp-server/cameo_mcp/server.py`
- **MCP tool**:
  - `cameo_generate_model_completeness_dashboard`
- **Checks**:
  - Requirements without satisfy
  - Requirements without verify
  - Blocks without ports/interfaces
  - Activities without allocations
  - Interfaces without item flows
  - Diagrams missing for key packages
  - Matrices missing for key relationships
  - Reports/evidence missing
- **Acceptance Criteria**:
  - Produces JSON and Markdown dashboard.
- **Validation**:
  - Run on course model and disposable model.

## Sprint 5: Traceability, Criteria, Relation Maps, And Matrices

**Goal**: Make traceability generation and proof the standout feature.

**Capabilities covered**: 3, 7, 8, 9.

**Demo/Validation**:

- Given a requirement package, create suggested satisfy/derive/refine/verify/allocate links, generate matrices and Relation Maps, then verify coverage.

### Task 5.1: Generic Criteria Expression Builder

- **Capability**: 3, Generic criteria expression builder
- **Location**:
  - `plugin/src/com/claude/cameo/bridge/handlers/CriteriaHandler.java` new
  - `plugin/src/com/claude/cameo/bridge/util/StructuredExpressionSerializer.java` new
  - `mcp-server/cameo_mcp/criteria.py` new
- **Routes**:
  - `GET /api/v1/criteria/templates`
  - `POST /api/v1/criteria/build`
  - `POST /api/v1/criteria/parse`
  - `POST /api/v1/criteria/apply`
- **Supported targets**:
  - Relation Map
  - Dependency Matrix
  - Generic Table derived property
  - Smart Package query
  - Legend condition
- **Implementation instructions**:
  - Start with proven DSL relation expressions.
  - Add templates for satisfy, verify, derive, refine, allocate, trace, dependency, connector, item flow.
  - Each template must include `verifiedWithUiDiff`.
  - First add `GET /api/v1/criteria/capabilities` to report which native expression targets are proven: `relationMap`, `matrix`, `genericTable`, `smartPackage`, `legend`, `opaqueBehavior`.
  - Store bridge-owned criteria as a neutral JSON AST with nodes such as `relationshipType`, `direction`, `sourceType`, `targetType`, `stereotype`, `tagEquals`, `ownerScope`, `depth`, and `includeDerived`.
  - Implement adapters one target at a time. The first production adapter should use the existing `RelationMapHandler` criteria path; matrix criteria follows only after a UI-created matrix criteria diff has been captured.
  - Add a developer probe named `criteria_expression_introspection` to `ScriptProbeHandler` that dumps the Java class names, property keys, and serialized values for a manually configured Relation Map, matrix, smart package, generic table column, and legend condition.
  - Refuse `POST /api/v1/criteria/apply` unless the target adapter has `verifiedWithUiDiff=true`, the target element type matches the adapter, and the request includes `dryRun=false`.
- **Acceptance Criteria**:
  - Build and apply criteria to a Relation Map and Dependency Matrix.
  - Parse existing criteria into structured summary.
  - Unsupported targets return `UNSUPPORTED` with the captured class/property evidence needed for the next implementation pass.
- **Validation**:
  - `scripts/live_validate_criteria_builder.py --targets relation-map,matrix --allow-write --cleanup`.
  - Output: `validation-output/criteria-builder/<timestamp>/criteria-templates.json`, `ui-diff-before.json`, `ui-diff-after.json`, `adapter-readback.json`, `summary.md`.
  - Pass gate: at least five criteria templates roundtrip through build, apply, readback, and parse without losing relationship direction or scope.

### Task 5.2: Traceability Autopilot

- **Capability**: 7, Traceability autopilot
- **Location**:
  - `mcp-server/cameo_mcp/traceability_autopilot.py` new
- **MCP tools**:
  - `cameo_analyze_traceability_gaps`
  - `cameo_propose_traceability_links`
  - `cameo_apply_traceability_links`
- **Implementation instructions**:
  - Never auto-link without returning a patch plan first.
  - Rank suggestions by evidence: name similarity, owner package, existing path, diagram co-occurrence, stereotype compatibility.
- **Acceptance Criteria**:
  - Suggests links with confidence and rationale.
  - Applies selected links and verifies matrix/graph coverage.
- **Validation**:
  - Synthetic model with known expected links.

### Task 5.3: Relation Map Mastery

- **Capability**: 8, Relation Map mastery
- **Location**:
  - `RelationMapHandler.java`
  - `mcp-server/cameo_mcp/relation_maps.py` if split is useful
- **Work items**:
  - Finish criteria templates.
  - Add native preset catalog inspection.
  - Improve render/export behavior without hidden refresh.
  - Implement refresh diagnostics.
  - Expand/collapse if stable native method is found.
  - Compare maps by graph and settings.
- **Acceptance Criteria**:
  - Can create a Relation Map from context element and criteria.
  - Can prove graph has expected nodes/edges.
  - Can export evidence bundle even when native presentations are unavailable.
- **Validation**:
  - Extend `live_validate_relation_map_rendering.py`.

### Task 5.4: Matrix Mastery

- **Capability**: 9, Matrix mastery
- **Location**:
  - `MatrixHandler.java`
  - `mcp-server/cameo_mcp/matrices.py` new if useful
- **Routes**:
  - `GET /api/v1/matrices/kinds`
  - `POST /api/v1/matrices/{id}/criteria`
  - `POST /api/v1/matrices/{id}/verify`
  - `POST /api/v1/matrices/{id}/export`
- **Supported kinds**:
  - satisfy
  - verify
  - derive
  - refine
  - allocation
  - dependency
  - custom
- **Acceptance Criteria**:
  - Can create/read/verify/export all supported matrix kinds.
  - Unsupported native matrix kind reports a clear capability gap.
- **Validation**:
  - `scripts/live_validate_matrices_full.py`.

## Sprint 6: Diagram Intent, Repair, ICD, And Deep Presentations

**Goal**: Let the AI create and fix the diagrams engineers actually submit.

**Capabilities covered**: 10, 11, 12, 33.

**Demo/Validation**:

- Agent creates a BDD/IBD/activity/state/requirement traceability pack from intent.
- Agent repairs labels, compartments, paths, swimlanes, nested state presentations, and ICD tables.

### Task 6.1: Diagram Intent Compiler

- **Capability**: 10, Diagram intent compiler
- **Location**:
  - `mcp-server/cameo_mcp/diagram_intent.py` new
  - Existing diagram endpoints
- **MCP tools**:
  - `cameo_compile_diagram_intent`
  - `cameo_apply_diagram_intent`
- **Intent schema**:
  - diagram type
  - owner package
  - purpose
  - required elements
  - relationships
  - layout policy
  - validation expectations
- **Acceptance Criteria**:
  - Compiles intent into patch plan.
  - Applies to create a runnable/testable diagram.
- **Validation**:
  - Live create BDD, IBD, activity, requirement diagram.

### Task 6.2: Diagram Repair Engine

- **Capability**: 11, Diagram repair engine
- **Location**:
  - `DiagramHandler.java`
  - `mcp-server/cameo_mcp/diagram_repair.py` new
- **Repair families**:
  - hidden labels
  - label positions
  - conveyed item labels
  - allocation compartments
  - path decorations
  - compartment presets
  - overlapping shapes
  - route paths
  - prune orphan presentations
- **Acceptance Criteria**:
  - Each repair returns before/after presentation summary.
  - Dry-run mode reports what would be changed.
- **Validation**:
  - Existing diagram visual verification plus screenshot/image checks.

### Task 6.3: ICD Automation

- **Capability**: 12, ICD automation
- **Location**:
  - `plugin/src/com/claude/cameo/bridge/handlers/IcdHandler.java` new
  - `mcp-server/cameo_mcp/icd.py` new
- **Routes/tools**:
  - `POST /api/v1/icd/analyze`
  - `POST /api/v1/icd/create-table`
  - `POST /api/v1/icd/verify`
- **Inputs**:
  - system/block
  - interface blocks
  - ports
  - connectors
  - item flows
  - allocation context
- **Acceptance Criteria**:
  - Produces blackbox and whitebox ICD tables where model data exists.
  - Flags missing ports, missing item flows, untyped connectors.
- **Validation**:
  - Live test on model with known interfaces.

### Task 6.4: Diagram-Specific Deep Handlers

- **Capability**: 33, Diagram-specific deep handlers
- **Location**:
  - `DiagramHandler.java`
  - new helpers under `plugin/src/com/claude/cameo/bridge/diagram/`
- **Initial targets**:
  - Sequence diagrams: lifelines, messages, activation bars.
  - Composite states: nested state bounds and transitions.
  - Parametric diagrams: constraint properties and binding connectors.
  - View/viewpoint diagrams.
  - Legends and legend conditions.
- **Acceptance Criteria**:
  - Each target has a read endpoint first.
  - Write endpoint follows only after live UI diff proves required properties.
- **Validation**:
  - One live validation script per diagram type:
    - `scripts/live_validate_sequence_diagram_deep_handler.py`
    - `scripts/live_validate_state_diagram_deep_handler.py`
    - `scripts/live_validate_parametric_diagram_deep_handler.py`
    - `scripts/live_validate_viewpoint_diagram_deep_handler.py`
    - `scripts/live_validate_legend_deep_handler.py`
  - Each script must run read-only by default and write under `validation-output/diagram-deep-handlers/<diagram-type>/<timestamp>/`.
  - Required artifacts: `diagram.json`, `presentations.json`, `property-dump.json`, `image.png` when export is supported, `readback-summary.md`.
  - Pass gate for read endpoints: every returned presentation has `presentationId`, `presentationType`, backing element reference when applicable, bounds/path data when applicable, and warnings instead of dropped unsupported symbols.
  - Pass gate for write/repair endpoints: before/after presentation readback proves the intended symbol changed and no unrelated presentations changed outside the requested scope.

## Sprint 7: Validation, Pre-Commit Gate, And AI-Generated Rules

**Goal**: Make the bridge a model quality authority.

**Capabilities covered**: 4, 5, 29, supports 19 and 28.

**Demo/Validation**:

- Run native validation plus bridge semantic validation.
- Generate a pre-commit report.
- Generate a new validation rule from a structured rule request.

### Task 7.1: Native Validation Suite Runner

- **Capability**: 4, Native validation suite runner
- **Resolved playbook**: follow `Native Validation Suite Runner` in `Resolved API Implementation Playbooks`.
- **Location**:
  - `plugin/src/com/claude/cameo/bridge/handlers/ValidationHandler.java` new
  - `mcp-server/cameo_mcp/validation.py` new
- **Routes**:
  - `GET /api/v1/validation/suites`
  - `POST /api/v1/validation/run`
  - `GET /api/v1/validation/results/{runId}`
- **Implementation instructions**:
  - Use `ValidationHelper.validate(...)` and `ValidationRunData` if available.
  - Return `RuleViolationResult` data as `ValidationFinding`.
  - Support selected scope, package scope, diagram scope, whole project.
  - Add `GET /api/v1/validation/capabilities` before `GET /api/v1/validation/suites`. It must probe `ValidationHelper`, `ValidationRunData`, `RuleViolationResult`, and any suite/catalog APIs found in the local OpenAPI jars.
  - Implement listing in tiers:
    - Tier 1: report validation package availability and active project validation profile roots.
    - Tier 2: list suites/rules with IDs, names, severities, owner profiles, and enabled state.
    - Tier 3: list rule parameters and scope compatibility if the API exposes them.
  - `POST /api/v1/validation/run` request fields: `suiteIds`, `ruleIds`, `scopeElementIds`, `scopeMode`, `includeInfo`, `includeWarnings`, `timeoutSeconds`, `dryRun`, `saveResults`, `maxFindings`.
  - Run on the serialized operation path with explicit timeout. If native validation cannot be cancelled safely, mark cancellation as unsupported and keep the timeout at the bridge client layer.
  - Normalize each native result into `ValidationFinding`; include raw class names and raw severity fields under `native` for audit.
  - Never create or modify validation rules in this task; rule authoring remains Task 7.3.
- **Acceptance Criteria**:
  - Can list available suites or report why listing is unsupported.
  - Can run at least one suite live.
  - Results map to element IDs.
  - No open project returns `409`.
  - Missing validation classes return `UNSUPPORTED`, not `500`.
  - Native findings include enough element IDs for MCP pre-commit tooling to fetch context.
- **Validation**:
  - `scripts/live_probe_native_validation.py --base-url http://127.0.0.1:18740/api/v1 --out validation-output/native-validation --timestamped`.
  - `scripts/live_validate_native_validation.py --scope project --max-findings 200 --timeout-seconds 120`.
  - Optional mutation fixture: `scripts/live_validate_native_validation.py --create-known-violation --allow-write --cleanup`.
  - Required artifacts: `suites.json`, `run-request.json`, `run-response.json`, `findings.json`, `element-readback.json`, `summary.md`.
  - Pass gate: either a native suite runs and returns structured findings, or the unsupported response identifies the missing class/plugin/license/project condition with classpath proof.

### Task 7.2: Pre-Commit Review Gate

- **Capability**: 5, Pre-commit review gate
- **Location**:
  - `mcp-server/cameo_mcp/precommit.py` new
  - `mcp-server/cameo_mcp/server.py`
- **MCP tool**:
  - `cameo_run_precommit_review_gate`
- **Checks**:
  - Native validation results.
  - Requirement quality.
  - Trace coverage.
  - Matrix consistency.
  - Diagram visual checks.
  - Dirty project status.
  - Relation Map graph health.
  - Missing evidence bundle.
- **Acceptance Criteria**:
  - Returns `pass`, `warn`, or `fail`.
  - Includes fix plan for failures.
- **Validation**:
  - Run against known clean and known broken models.

### Task 7.3: AI-Generated Validation Rules

- **Capability**: 29, AI-generated validation rules
- **Location**:
  - `mcp-server/cameo_mcp/rule_authoring.py` new
  - optional Java `ValidationRuleAuthoringHandler.java`
- **Implementation instructions**:
  - Phase 1: generate MCP-side semantic checks from a constrained rule DSL.
  - Phase 2: investigate native validation rule element creation.
  - Phase 3: support exporting/importing rule suites if native API allows.
- **Acceptance Criteria**:
  - User can define "all requirements in package X must have satisfy links" as DSL.
  - Tool runs rule and returns findings.
- **Validation**:
  - Unit tests for DSL.
  - Live checks on model packages.

## Sprint 8: Reports, Publishing, Proofing, And Deliverables

**Goal**: Convert model state into review-ready outputs.

**Capabilities covered**: 15, 16, 28, 30.

**Demo/Validation**:

- Generate report/doc artifacts and a proofing report from the live model.

### Task 8.1: Report Wizard Automation

- **Capability**: 15, Report Wizard automation
- **Resolved playbook**: follow `Report Wizard Automation` in `Resolved API Implementation Playbooks`.
- **Location**:
  - `plugin/src/com/claude/cameo/bridge/handlers/ReportHandler.java` new
  - `mcp-server/cameo_mcp/reports.py` new
- **Routes**:
  - `GET /api/v1/reports/templates`
  - `POST /api/v1/reports/generate`
  - `GET /api/v1/reports/jobs/{jobId}`
- **Implementation instructions**:
  - Discover available Report Wizard APIs and template folders.
  - Start with read-only template discovery.
  - Add generation only after a local proof.
  - Support output formats based on installed Report Wizard support: docx, xlsx, pptx, html, rtf, txt, xml.
  - Add `GET /api/v1/reports/capabilities` to probe Report Wizard plugin classes, template directories, supported output formats, and writeable output locations.
  - `GET /api/v1/reports/templates` must return template ID/path, display name, template type, supported formats, required variables if discoverable, and whether the file exists/readable.
  - `POST /api/v1/reports/generate` request fields: `templateId`, `scopeElementIds`, `outputFormat`, `outputDirectory`, `fileName`, `variables`, `overwrite`, `timeoutSeconds`, `dryRun`.
  - Generation must be job-backed even if the first implementation runs synchronously. Save job metadata in memory and return `jobId`, output paths, warnings, and native logs.
  - If native generation APIs are not reachable, do not silently assemble an external report and call it Report Wizard. Return `UNSUPPORTED` and optionally point to Task 8.3 for bridge-owned proofing.
- **Acceptance Criteria**:
  - Can list templates.
  - Can generate at least one report to a chosen output directory.
  - Reports include requested diagrams/tables when template supports them.
  - Generated artifact exists on disk, has non-zero size, and is recorded in the evidence bundle manifest.
- **Validation**:
  - `scripts/live_probe_report_wizard.py --out validation-output/report-wizard --timestamped`.
  - `scripts/live_validate_report_wizard.py --template sample --format html --output-dir validation-output/report-wizard/generated --timeout-seconds 180`.
  - Required artifacts: `capabilities.json`, `templates.json`, `generate-request.json`, `job.json`, `generated-files.json`, `summary.md`.
  - Pass gate: template discovery works and one safe template either generates a readable artifact or returns a structured unsupported/missing-template result.

### Task 8.2: Cameo Collaborator Publishing

- **Capability**: 16, Cameo Collaborator publishing
- **Location**:
  - `mcp-server/cameo_mcp/collaborator.py` new
  - Java or external CLI/REST integration depending on installed product
- **Description**:
  - Detect whether Cameo Collaborator/Magic Collaboration Studio is available.
  - Add publishing plan and status readback.
- **Acceptance Criteria**:
  - If unavailable, returns clear unsupported result.
  - If available, publishes a small view or produces a validated dry-run package.
- **Validation**:
  - Environment-dependent live validation.

### Task 8.3: Model-To-Document Proofing

- **Capability**: 28, Model-to-document proofing
- **Location**:
  - `mcp-server/cameo_mcp/document_proofing.py` new
- **Inputs**:
  - model scope
  - report/document path or generated report artifact
  - expected artifact list
- **Checks**:
  - stale element names
  - weak requirement statements
  - missing traceability
  - inconsistent terminology
  - missing diagrams/tables
- **Acceptance Criteria**:
  - Produces Markdown findings with model references.
- **Validation**:
  - Run on generated evidence/report bundle.

## Sprint 9: Simulation, Parametrics, And Trade Studies

**Goal**: Expose the high-prestige Simulation Toolkit and parametric workflows.

**Capabilities covered**: 13, 14.

**Demo/Validation**:

- Detect simulation capability.
- Run a simple simulation or return actionable unsupported evidence.
- Run a simple parametric/trade study on a test model.

### Task 9.1: Simulation Capability Probe

- **Capability**: 13, Simulation/parametric execution bridge
- **Resolved playbook**: follow `Simulation And Parametric Execution` in `Resolved API Implementation Playbooks`.
- **Location**:
  - `plugin/src/com/claude/cameo/bridge/handlers/SimulationHandler.java` new
  - `mcp-server/cameo_mcp/simulation.py` new
- **Routes**:
  - `GET /api/v1/simulation/capabilities`
  - `GET /api/v1/simulation/configurations`
- **Implementation instructions**:
  - Detect classes for `SimulationManager`.
  - Detect plugin/license availability.
  - List simulation configurations and executable targets if possible.
  - Probe the local installation for `plugins/com.nomagic.magicdraw.simulation/simulation_api.jar` and record whether `SimulationManager` loads from that jar or another plugin jar.
  - Add `GET /api/v1/simulation/capabilities` fields: `apiJarFound`, `simulationManagerClass`, `simulationPluginDetected`, `licenseSignal`, `supportedModes`, `canRunSync`, `canRunAsync`, `canCancel`, `requiresUiThread`.
  - `GET /api/v1/simulation/configurations` should list Simulation Config elements, executable behaviors, parametric diagrams, constraint blocks, value properties, and any native configuration IDs that can be safely read.
  - Avoid adding `simulation_api.jar` to Gradle in a way that breaks plugin startup. Prefer compileOnly/local-provided dependency documentation and classpath probing in the running CATIA process.
- **Acceptance Criteria**:
  - Safely reports available/unavailable without crashing when Simulation Toolkit is absent.
- **Validation**:
  - `scripts/live_probe_simulation.py --out validation-output/simulation --timestamped`.
  - Required artifacts: `classpath.json`, `capabilities.json`, `configurations.json`, `summary.md`.
  - Pass gate: absence of Simulation Toolkit is a clean `UNSUPPORTED`; presence returns at least one configuration/executable target or explains why the open project has none.

### Task 9.2: Simulation Execution Endpoint

- **Capability**: 13
- **Resolved playbook**: follow `Simulation And Parametric Execution` in `Resolved API Implementation Playbooks`.
- **Routes**:
  - `POST /api/v1/simulation/run`
  - `POST /api/v1/simulation/run-async`
  - `GET /api/v1/simulation/results/{runId}`
- **Implementation instructions**:
  - Use `SimulationManager.simulate(...)` for sync proof.
  - Use `simulateAsync(...)` only after job lifecycle is understood.
  - Include timeout and cancellation strategy if API allows.
  - `POST /api/v1/simulation/run` request fields: `configurationId`, `targetElementId`, `inputValues`, `captureSignals`, `captureConsole`, `timeoutSeconds`, `dryRun`.
  - Result fields: `runId`, `status`, `startedAt`, `completedAt`, `durationMillis`, `outputs`, `events`, `console`, `resultArtifacts`, `warnings`, `native`.
  - Async execution is blocked until `GET /api/v1/simulation/results/{runId}` can prove stable lifecycle states: `queued`, `running`, `completed`, `failed`, `cancelled`, `timeout`.
- **Acceptance Criteria**:
  - Runs one known executable simulation and returns outputs.
  - Handles invalid inputs with structured errors.
- **Validation**:
  - `scripts/live_validate_simulation_execution.py --sample-model examples/autopilot-demo/simulation-smoke.mdzip --timeout-seconds 180`.
  - Required artifacts: `run-request.json`, `run-result.json`, `outputs.csv`, `events.json`, `summary.md`.
  - Pass gate: either a sample simulation completes with captured outputs or the environment is marked `UNSUPPORTED` with class/plugin/license evidence.

### Task 9.3: Trade Study Engine

- **Capability**: 14, Trade study engine
- **Location**:
  - `mcp-server/cameo_mcp/trade_studies.py` new
- **Description**:
  - Wrap simulation/parametric runs into alternatives.
  - Inputs: alternatives, parameter values, target outputs, scoring function.
  - Outputs: ranking, sensitivity notes, evidence.
- **Acceptance Criteria**:
  - Runs at least one synthetic trade study from parameter sets.
  - Produces CSV/JSON/Markdown results.
- **Validation**:
  - Unit tests for scoring.
  - Live test if simulation endpoint works.

## Sprint 10: Teamwork Cloud, Change Impact, And Version Intelligence

**Goal**: Make model collaboration and change history accessible.

**Capabilities covered**: 17, 18.

**Demo/Validation**:

- Diagnose Teamwork availability.
- Read version/change information where accessible.
- Produce change impact from snapshots and/or Teamwork version diffs.

### Task 10.1: Teamwork Capability Probe

- **Capability**: 17, Teamwork Cloud / Magic Collaboration bridge
- **Resolved playbook**: follow `Teamwork Cloud / Magic Collaboration Studio` in `Resolved API Implementation Playbooks`.
- **Location**:
  - `plugin/src/com/claude/cameo/bridge/handlers/TeamworkHandler.java` new
  - `mcp-server/cameo_mcp/teamwork.py` new
- **Routes**:
  - `GET /api/v1/teamwork/capabilities`
  - `GET /api/v1/teamwork/project`
- **Implementation instructions**:
  - Detect whether current project is local or server project.
  - Detect available authentication/session context.
  - Do not assume token login.
  - Add `GET /api/v1/teamwork/capabilities` as read-only. Probe project descriptor remote/local state, available Teamwork/Magic Collaboration classes, active login/session hints, and whether the project is editable/read-only.
  - `GET /api/v1/teamwork/project` must return `projectMode`, local descriptor URI, remote descriptor URI if present, branch/name/version fields if discoverable, and warnings when values are UI-only.
  - Do not prompt for credentials or store passwords in the bridge. If credentials are needed, return `authRequired=true` and document the required existing CATIA login state.
- **Acceptance Criteria**:
  - Local project returns `available=false` with reason.
  - Server project returns repository/project/version metadata if available.
- **Validation**:
  - `scripts/live_probe_teamwork.py --out validation-output/teamwork --timestamped`.
  - Required artifacts: `capabilities.json`, `project.json`, `descriptor.json`, `summary.md`.
  - Pass gate: local projects are identified without error; server projects return at least descriptor/version metadata or a precise auth/plugin limitation.

### Task 10.2: Teamwork Version, Commit, Lock, Branch Operations

- **Capability**: 17
- **Resolved playbook**: follow `Teamwork Cloud / Magic Collaboration Studio` in `Resolved API Implementation Playbooks`.
- **Routes**:
  - `GET /api/v1/teamwork/history`
  - `GET /api/v1/teamwork/locks`
  - `POST /api/v1/teamwork/commit-preview`
  - `POST /api/v1/teamwork/commit`
  - `GET /api/v1/teamwork/branches`
- **Implementation instructions**:
  - Begin read-only.
  - Implement commit only after live server test and explicit user confirmation workflow.
  - Commit route must include validation gate option.
  - `POST /api/v1/teamwork/commit` must require `confirm=true`, `commitMessage`, `validationGate`, and a clean pre-commit result unless `overrideValidationFailure=true` is explicitly supplied.
  - Commit preview must include dirty elements, locked/unlocked status if available, native warnings, and validation gate summary. It must not create a server version.
  - Locks and branches remain read-only until proven against a disposable server project.
- **Acceptance Criteria**:
  - Read-only version/lock data works in server project.
  - Commit operation is guarded and auditable.
- **Validation**:
  - `scripts/live_validate_teamwork_readonly.py --require-teamwork-project`.
  - `scripts/live_validate_teamwork_commit_preview.py --require-teamwork-project --no-commit`.
  - Commit smoke only against a disposable server project: `scripts/live_validate_teamwork_commit.py --require-teamwork-project --allow-commit --project-name AutopilotScratch`.

### Task 10.3: Change Impact Analyzer

- **Capability**: 18, Change impact analyzer
- **Location**:
  - `mcp-server/cameo_mcp/change_impact.py` new
- **Inputs**:
  - element IDs
  - snapshot diff
  - Teamwork version diff if available
  - relationship traversal config
- **Outputs**:
  - directly changed elements
  - upstream/downstream requirements
  - affected blocks/interfaces/activities/tests
  - affected diagrams/tables/matrices/reports
  - suggested validation/export tasks
- **Acceptance Criteria**:
  - Works from local snapshots even without Teamwork.
  - Uses Teamwork history when available.
- **Validation**:
  - Synthetic before/after change.

## Sprint 11: Integrations, DataHub, ReqIF, CSV, DOORS, And Excel

**Goal**: Address one of the biggest community pain points: Cameo data synchronization with the rest of the engineering toolchain.

**Capabilities covered**: 26, 27.

**Demo/Validation**:

- Export requirements/table/matrix data to CSV/XLSX.
- Import controlled CSV/XLSX changes through patch plan.
- Probe DataHub/ReqIF/DOORS availability.

### Task 11.1: Excel Roundtrip Foundation

- **Capability**: 27, Excel roundtrip
- **Location**:
  - `mcp-server/cameo_mcp/excel_roundtrip.py` new
  - optional no Java changes initially
- **Description**:
  - Export requirements, elements, relationships, matrices to `.xlsx` and `.csv`.
  - Re-import with diff preview.
  - Apply only approved changes through normal typed endpoints.
- **Acceptance Criteria**:
  - Roundtrip a requirement table without losing IDs.
  - Detect deleted/renamed/changed rows.
  - Refuse ambiguous rows without IDs.
- **Validation**:
  - Unit tests with sample workbooks.
  - Live export/import on disposable package.

### Task 11.2: ReqIF/CSV Import Export

- **Capability**: 26, DataHub/ReqIF/CSV/DOORS bridge
- **Resolved playbook**: follow `DataHub, ReqIF, CSV, DOORS, And Requirements Integrations` in `Resolved API Implementation Playbooks`.
- **Location**:
  - `mcp-server/cameo_mcp/import_export.py` new
  - `RequirementsHandler.java` if native support exists
- **Implementation instructions**:
  - Phase 1: bridge-owned CSV import/export.
  - Phase 2: probe native ReqIF/Cameo Requirements Modeler APIs.
  - Phase 3: expose native ReqIF only after UI diff/live proof.
  - CSV export schema must include immutable `elementId`, `qualifiedName`, `humanType`, `ownerId`, `stereotypes`, `requirementId`, `text`, and selected tags.
  - Import must run in three stages: parse, diff, patch-plan. Applying the patch plan is separate and uses normal element/specification/tag endpoints.
  - Native ReqIF probing should use a dedicated `GET /api/v1/import-export/capabilities` route before any import/export route is advertised.
  - Do not attempt DOORS writes through CSV. DOORS/DataHub belongs to Task 11.3 and must start with source inventory and sync preview only.
- **Acceptance Criteria**:
  - CSV import/export works.
  - Native ReqIF support is either implemented or documented as unavailable.
- **Validation**:
  - `scripts/live_validate_csv_reqif_roundtrip.py --format csv --allow-write --cleanup`.
  - Optional: `scripts/live_probe_reqif.py --sample-file examples/autopilot-demo/requirements.reqif`.
  - Pass gate: CSV row IDs roundtrip exactly and ambiguous/missing IDs are refused before mutation.

### Task 11.3: DataHub/DOORS/ENOVIA Probe

- **Capability**: 26
- **Resolved playbook**: follow `DataHub, ReqIF, CSV, DOORS, And Requirements Integrations` in `Resolved API Implementation Playbooks`.
- **Location**:
  - `plugin/src/com/claude/cameo/bridge/handlers/DataHubHandler.java` new
- **Routes**:
  - `GET /api/v1/datahub/capabilities`
  - `GET /api/v1/datahub/sources`
  - `POST /api/v1/datahub/sync-preview`
- **Implementation instructions**:
  - Treat DataHub as optional.
  - Detect installed plugin/classes.
  - Do not perform sync writes until preview/readback is reliable.
  - Add classpath probes for likely DataHub plugin packages and record installed plugin descriptors from CATIA's plugin manager if available.
  - `GET /api/v1/datahub/sources` must be read-only and return configured source names/types without credentials or secret values.
  - `POST /api/v1/datahub/sync-preview` request fields: `sourceId`, `scopeElementIds`, `direction`, `maxChanges`, `includeDeletes`. It must return proposed creates/updates/deletes and never execute sync.
  - Native DOORS/ENOVIA support must remain `UNSUPPORTED` until a disposable connector/source is available for live proof.
- **Acceptance Criteria**:
  - Clear availability report.
  - If installed, list configured sources or explain missing configuration.
- **Validation**:
  - `scripts/live_probe_datahub.py --out validation-output/datahub --timestamped`.
  - If a disposable source exists: `scripts/live_validate_datahub_sync_preview.py --source <id> --max-changes 25`.
  - Pass gate: no secrets are emitted, unavailable plugins return structured `UNSUPPORTED`, and sync preview performs no writes.

## Sprint 12: Customization, Profiles, Variants, Safety, And Cyber

**Goal**: Expose the high-leverage extension points that make the tool valuable in real organizations.

**Capabilities covered**: 24, 25, 29, 34, 35.

**Demo/Validation**:

- Create a profile/stereotype/tag pattern.
- Apply it to elements.
- Generate validation rules and a pattern pack.
- Probe product-line/safety/cyber plugins.

### Task 12.1: Profile/DSL Authoring Assistant

- **Capability**: 24, Profile/DSL authoring assistant
- **Resolved playbook**: follow `Profile/DSL Authoring` in `Resolved API Implementation Playbooks`.
- **Location**:
  - `plugin/src/com/claude/cameo/bridge/handlers/ProfileDslHandler.java` new
  - `mcp-server/cameo_mcp/profile_dsl.py` new
- **Routes**:
  - `POST /api/v1/profiles/create`
  - `POST /api/v1/profiles/stereotypes/create`
  - `POST /api/v1/profiles/tags/create`
  - `POST /api/v1/profiles/apply-customization`
- **Implementation instructions**:
  - Start with simple profile/stereotype/tag creation.
  - Use snapshot/diff for UI customization details.
  - Defer icon/palette/menu customizations until readback is reliable.
  - Use `StereotypesHelper` and `TagsHelper` for application/readback, and the existing element creation path for Profile, Stereotype, and Property/TagDefinition where possible.
  - Add `GET /api/v1/profiles/capabilities` to report whether profile creation, stereotype metaclass assignment, tag creation, tag setting, and customization application are supported.
  - Route request fields:
    - profile create: `ownerId`, `name`, `uri`, `applyToOwner`
    - stereotype create: `profileId`, `name`, `metaclasses`, `baseStereotypeIds`
    - tag create: `stereotypeId`, `name`, `valueType`, `multiplicity`, `defaultValue`
    - customization: `profileId`, `stereotypeId`, `iconPath`, `toolbar`, `palette`, `diagramTypes`
  - Customization must remain read/probe-only until snapshot/diff can prove which model elements/properties the UI creates.
- **Acceptance Criteria**:
  - Can create a profile with one stereotype and two tags.
  - Can apply to element and set tags.
  - Readback proves the stereotype metaclasses and tag values without relying on UI labels alone.
- **Validation**:
  - `scripts/live_validate_profile_dsl.py --allow-write --cleanup --scratch-prefix AutopilotProfileScratch`.
  - Required artifacts: `profile-request.json`, `create-response.json`, `apply-response.json`, `tag-readback.json`, `snapshot-diff.json`, `summary.md`.
  - Pass gate: profile, stereotype, tags, application, and tag values all read back by ID; cleanup removes scratch content or reports remaining IDs.

### Task 12.2: Variant/Product-Line Support

- **Capability**: 34, Variant/product-line support
- **Resolved playbook**: follow `Variant/Product-Line Support` in `Resolved API Implementation Playbooks`.
- **Location**:
  - `plugin/src/com/claude/cameo/bridge/handlers/VariantHandler.java` new
  - `mcp-server/cameo_mcp/variants.py` new
- **Routes**:
  - `GET /api/v1/variants/capabilities`
  - `GET /api/v1/variants/native-model`
  - `POST /api/v1/variants/pattern/install-preview`
  - `POST /api/v1/variants/pattern/apply`
  - `POST /api/v1/variants/configurations/evaluate`
  - `POST /api/v1/variants/configurations/export`
- **Implementation instructions**:
  - Probe Product Line Engineering / Variability Core / Pure Variants plugins by installed plugin directory, plugin descriptor, and reflectively loaded candidate classes. Do not advertise native support from names alone.
  - Native mode is read-only first: list variability elements, variation points, options, configurations, and rule expressions only when the installed API exposes them.
  - Bridge-owned mode is always explicit as `mode=bridge-owned`. It installs a disposable profile pattern with stereotypes such as `Variant`, `VariationPoint`, `VariantOption`, and `VariantConfiguration`.
  - `pattern/install-preview` returns a patch plan and never writes.
  - `pattern/apply` requires `allowWrite=true`, `profileOwnerId`, `scratchPrefix`, `snapshotBefore=true`, and `snapshotAfter=true`.
  - `configurations/evaluate` must not hide, suppress, delete, or move model content. It returns included/excluded element IDs, rule explanations, ambiguous rules, and traceability gaps.
  - Native product-line writes stay blocked until a real installed plugin, sample model, and reversible configuration evidence exist.
- **Acceptance Criteria**:
  - Reports plugin availability.
  - If unavailable, supports lightweight stereotype-based variants as bridge-owned pattern.
  - Evaluates at least two configurations against three or more tagged elements.
  - Refuses destructive configuration operations with `403 VARIANT_DESTRUCTIVE_OPERATION_REFUSED`.
- **Validation**:
  - `scripts/live_probe_variants.py --out validation-output/variants --timestamped`.
  - `scripts/live_validate_variants.py --mode bridge-owned --allow-write --cleanup --scratch-prefix AutopilotVariantScratch`.
  - Required artifacts: `capabilities.json`, `pattern-preview.json`, `apply-response.json`, `configuration-a.json`, `configuration-b.json`, `export.json`, `snapshot-diff.json`, `summary.md`.
  - Pass gate: native absence is structured and bridge-owned pattern install/evaluate/export works without modifying content outside the scratch scope.

### Task 12.3: Safety/Cyber Extension Hooks

- **Capability**: 35, Safety/cyber extension hooks
- **Resolved playbook**: follow `Safety/Cyber Extension Hooks` in `Resolved API Implementation Playbooks`.
- **Location**:
  - `plugin/src/com/claude/cameo/bridge/handlers/ExtensionProbeHandler.java` new or extend diagnostics
  - `mcp-server/cameo_mcp/extensions.py` new
- **Targets**:
  - Cameo Safety and Reliability Analyzer
  - Systems Safety Engineer
  - Systems Cybersecurity Designer
  - Data markings/classification
- **Routes**:
  - `GET /api/v1/extensions/capabilities`
  - `GET /api/v1/extensions/profiles`
  - `POST /api/v1/extensions/model-scan`
  - `POST /api/v1/extensions/pattern/install-preview`
- **Implementation instructions**:
  - Start as diagnostics and profile introspection only. Detect plugin directories, plugin descriptors, loaded classes, mounted profiles, stereotypes, tag definitions, and validation suites that match safety/cyber/risk/hazard/failure/classification terms.
  - `model-scan` is read-only and returns candidate hazards, risks, mitigations, threats, controls, classifications, linked requirements, linked design elements, and evidence gaps.
  - Do not claim regulatory compliance, certification readiness, risk closure, cybersecurity posture, or safety assurance. Return evidence and missing traceability only.
  - Bridge-owned safety/cyber patterns must be preview-only until a domain-specific profile owner and review workflow are approved.
  - Native extension writes remain blocked until the installed extension API, license, sample model, and domain semantics are proven by a live validation run.
- **Acceptance Criteria**:
  - Probe reports installed/available extensions.
  - If installed, list stereotype/profile roots and key element types.
  - Read-only scan returns element IDs, stereotype names, owner paths, and traceability gaps.
  - Compliance/certification requests are refused with `403 COMPLIANCE_CLAIM_REFUSED`.
- **Validation**:
  - `scripts/live_probe_extensions.py --targets safety,cyber --out validation-output/extensions --timestamped`.
  - Optional when a sample model/profile exists: `scripts/live_validate_extension_model_scan.py --targets safety,cyber --scope <package-id>`.
  - Required artifacts: `capabilities.json`, `profiles.json`, `model-scan-request.json`, `model-scan-response.json`, `summary.md`.
  - Pass gate: absent extensions return structured unsupported diagnostics; installed profiles are listed without secrets or unsupported compliance claims.

## Sprint 13: Public Demo, Documentation, And Community Impact

**Goal**: Package the system so it can become known in the Cameo community.

**Demo/Validation**:

- Public-style demo script shows AI model inspection, gap analysis, patch plan, apply, validation, diagram export, report/evidence bundle.

### Task 13.1: Autopilot Demo Model

- **Location**:
  - `examples/autopilot-demo/` new
  - `docs/demos/autopilot-demo.md` new
- **Description**:
  - Create or document a small non-sensitive demo model.
  - Include requirements, BDD, IBD, activity, state, traceability gaps, matrices.
- **Acceptance Criteria**:
  - Demo can run without course/private data.
- **Validation**:
  - Fresh CATIA install smoke where possible.

### Task 13.2: Community-Facing README Section

- **Location**:
  - `README.md`
  - `docs/strategy/catia-magic-feature-access-ranking.md`
- **Description**:
  - Add "What this bridge can automate" section.
  - Add "safe AI write workflow" section.
  - Add "live validation philosophy" section.
- **Acceptance Criteria**:
  - A Cameo user can understand why this is not just another macro bridge.
- **Validation**:
  - Manual review.

### Task 13.3: Release Checklist

- **Location**:
  - `docs/releases/`
  - `CHANGELOG.md`
- **Description**:
  - Release notes by capability cluster.
  - Known limitations.
  - Validation evidence links.
- **Acceptance Criteria**:
  - Release cannot be marked complete without live evidence for claimed capabilities.
- **Validation**:
  - Release dry run.

## Cross-Capability Acceptance Matrix

| Capability | Minimum Done | Full Done |
|---|---|---|
| Universal inspector | Inspect elements/diagrams/tags/relationships | Deep project/package/diagram summary with stable pagination |
| UI diff recorder | Snapshot before/after and noise-reduced diff | Diff-to-endpoint developer template |
| Criteria builder | Relation Map and matrix criteria | All criteria targets including smart package/table/legend |
| Validation runner | Native suite run with findings | Validation result solver/fix integration |
| Pre-commit gate | Read-only gate report | Optional guarded commit integration |
| Requirements suite | Analyze/number/check/export | Native requirement table and ReqIF parity |
| Traceability autopilot | Suggest links | Apply selected links and prove coverage |
| Relation Map mastery | Criteria/graph/verify/export | Stable native presentation expansion/render where possible |
| Matrix mastery | Core matrices | Custom criteria and export parity |
| Diagram intent compiler | Build common diagrams from plan | Multi-diagram artifact packs |
| Diagram repair | Existing repair endpoints unified | Deep handlers for sequence/state/parametric/viewpoint |
| ICD automation | Analyze ports/connectors | Native blackbox/whitebox ICD tables |
| Simulation bridge | Capability probe | Sync/async run with outputs |
| Trade study | Offline scoring from parameter sets | Native parametric execution alternatives |
| Report Wizard | Template discovery | Report generation and job status |
| Collaborator publishing | Availability probe | Publish/update/review workflow |
| Teamwork bridge | Project/version readback | Commit/lock/branch/merge support |
| Change impact | Snapshot-based impact | Teamwork version impact |
| Completeness dashboard | JSON/Markdown checks | Project-level dashboard with trend history |
| NL query | Deterministic query DSL | Agent-ready query examples and explanations |
| NL edit | Patch plan/apply workflow | Validation and rollback automation |
| Recipe library | Five executable recipes | Broad methodology catalog |
| Methodology wizard | resumable recipe state | wizard replacement with review packets |
| Profile/DSL assistant | Create profile/stereotype/tags | UI customization support |
| SysML patterns | Pattern to patch plan | Pattern marketplace/examples |
| DataHub/ReqIF/CSV/DOORS | CSV export/import | Native DataHub/ReqIF/DOORS sync where installed |
| Excel roundtrip | XLSX/CSV diff/apply | Matrix/table Excel parity |
| Document proofing | Markdown findings | Auto-linked report correction plan |
| AI rules | MCP-side rule DSL | Native validation rule authoring |
| Evidence bundle | JSON/images/summary | Full review-ready packet |
| Diagnostics | Status and reference resolution | Teamwork/API/dependency diagnostics |
| Transaction layer | receipts/snapshots/write state | rollback/undo integration |
| Deep handlers | read-first per diagram type | write/repair per diagram type |
| Variants | plugin probe or stereotype pattern | native product-line integration |
| Safety/cyber hooks | extension probe | native safety/cyber workflows |

## Per-Capability Validation Matrix

Use this matrix to decide what evidence is required before a capability can move from `planned` to `done`. A capability may be shipped as `unsupported` only when the probe evidence proves why the installed CATIA Magic/Cameo environment cannot support it.

| # | Capability | Unit / Contract Tests | Java-Side Test Target | Live Evidence Gate |
|---:|---|---|---|---|
| 1 | Universal model inspector | client query params, pagination, depth limits, element serialization shape | serializer/ref resolver helpers where CATIA-free | `live_validate_universal_inspector.py` captures model/package/diagram summaries and proves stable IDs |
| 2 | Human UI diff recorder | snapshot manifest, diff normalization, noise filtering | `JsonDiff`, `SnapshotStore` | `live_record_ui_diff.py` writes before/after snapshots, diff, and property dumps for a known UI change |
| 3 | Criteria builder | criteria DSL parsing, aliases, invalid criteria errors | criteria template mapping if isolated | relation map/matrix criteria live script proves generated settings survive raw readback |
| 4 | Native validation suite runner | request body, severity/scope mapping, unsupported response | reflection/probe result serializer | `live_validate_native_validation.py` completes a run or proves suite/plugin unavailability |
| 5 | Pre-commit validation gate | gate result aggregation, fail/pass/override logic | none unless Teamwork helper is isolated | pre-commit script captures project state, validation summary, and refuses commit when gate fails |
| 6 | Requirements engineering suite | requirement ID/text rules, numbering, export shape | requirement stereotype/tag helper if isolated | disposable requirements package readback plus table/export evidence |
| 7 | Traceability autopilot | gap detection, link suggestions, patch plan validation | relationship-type mapping | live trace script creates or suggests satisfy/derive/refine/verify links and proves matrix/relationship readback |
| 8 | Relation Map mastery | graph normalization, criteria aliases, compare payloads | relation-map settings serializers where possible | relation-map rendering script captures settings, graph, PNG, verify output, and snapshot diff |
| 9 | Matrix mastery | row/column/cell consistency, supported kinds, density checks | matrix kind mapping | live matrix script creates/reads refine/derive/satisfy/allocation/dependency where supported |
| 10 | Diagram intent compiler | plan-to-operation expansion, layout request bodies | diagram type alias mapping | creates at least BDD/IBD/activity/state-style examples and verifies shapes plus PNG nonblank content |
| 11 | Diagram repair | hidden label/path/compartment repair request contracts | compartment alias resolver and repair option mapping | repair script captures broken-before/fixed-after presentations, image, and verification summary |
| 12 | ICD automation | port/interface/connectivity analysis, table export schema | port/interface serializer helpers | live ICD script proves ports, flow properties, connectors, item flows, and table/export readback |
| 13 | Simulation bridge | config/run request validation, timeout paths, result normalization | optional reflection probe serializer | `live_probe_simulation.py` unsupported pass, plus execution script only with installed Simulation Toolkit and `--allow-execute` |
| 14 | Trade study assistant | scoring/ranking math, CSV/XLSX inputs, decision report | none unless parameter serializer isolated | offline deterministic trade study plus optional simulation-backed run evidence |
| 15 | Report Wizard automation | template list/generate request validation, path allowlist | report probe serializer | `live_validate_report_wizard.py` discovers templates and generates output or proves native generation unavailable |
| 16 | Collaborator publishing | payload contracts, guarded write confirmation | optional availability serializer | read-only availability probe first; publish smoke only against disposable project/site |
| 17 | Teamwork operations | commit preview contract, lock/branch/history normalization | Teamwork probe serializer | read-only server-project script; commit script requires disposable server project and explicit `--allow-commit` |
| 18 | Change impact analyzer | traversal, snapshot diff impact, report sorting | none | synthetic before/after snapshots plus optional Teamwork version diff if available |
| 19 | Model completeness dashboard | checks, severities, trend manifest | none | dashboard script scans a real model and writes JSON/Markdown findings with element IDs |
| 20 | Natural-language model query | query DSL parser, deterministic filters, explanation output | none | live query examples prove returned IDs match direct bridge reads |
| 21 | Natural-language model edit | patch plan validation, approval gates, dry-run/apply split | operation receipt helper | live edit script performs dry-run then approved disposable write with before/after diff |
| 22 | Recipe library | recipe schema, step ordering, resumability | none | five recipes execute in dry-run and at least one disposable live write recipe passes |
| 23 | Methodology wizard replacement | workflow state, resume/fail/retry logic | none | methodology script produces review packet and can resume from saved state |
| 24 | Profile/DSL authoring | profile/stereotype/tag request validation | stereotype/tag mapping if isolated | profile live script creates profile/stereotype/tags, applies them, and reads values by ID |
| 25 | SysML pattern generator | pattern-to-patch plan expansion, duplicate detection | none | disposable pattern instance readback for requirement/block/interface/activity pattern |
| 26 | DataHub/ReqIF/CSV/DOORS bridge | CSV/ReqIF parse/export, diff preview, missing-ID refusal | optional DataHub probe serializer | CSV roundtrip passes; native DataHub/ReqIF probe proves available or structured unsupported |
| 27 | Excel roundtrip | workbook schema, row identity, diff/apply plans | none | XLSX export/import on disposable requirements/table/matrix data with ID-preserving readback |
| 28 | Document proofing | findings schema, source linking, correction plan | none | proofing script emits element-linked findings and report/evidence bundle references |
| 29 | AI-generated validation rules | rule DSL validation, sandboxed rule evaluation | optional constraint/profile helper | MCP-side rule pack runs first; native rule authoring only after live profile/constraint proof |
| 30 | Evidence bundle generator | manifest completeness, file checksums, missing artifact errors | none | bundle script packages JSON, PNGs, diffs, summaries, and validates manifest paths/checksums |
| 31 | API/Teamwork diagnostics | status/capability/project diagnostics, auth redaction | capabilities serializer tests | diagnostics script captures status, capabilities, project mode, plugin probes, and no secrets |
| 32 | Undo-safe transaction layer | receipt schema, write-state, rollback metadata | receipt utility tests | disposable write script proves receipt, snapshots, diff, cleanup, and final dirty-state reporting |
| 33 | Deep handlers per diagram type | route contracts for sequence/state/parametric/viewpoint | type alias/property mapping | read-first scripts per diagram family; write support only after presentation readback and render verify |
| 34 | Variant/product-line support | variant model schema, stereotype fallback rules | optional probe serializer | plugin probe or stereotype-based variant demo with configuration analysis evidence |
| 35 | Safety/cyber extension hooks | extension inventory schema, rule pack checks | optional probe serializer | extension probe lists installed profiles/plugins or returns structured unsupported; no writes in v1 |

Minimum pass criteria for every row:

- Python unit tests prove request/response contracts and error propagation.
- Java tests cover all CATIA-independent mapping, serialization, capability metadata, and guard logic.
- Live scripts capture `status.json`, `capabilities.json`, and `project.json` before feature calls.
- Write-capable scripts require `--allow-write`, create disposable content, capture before/after snapshots, and report cleanup plus `isDirty`.
- Rendered artifacts use the existing verification helpers where possible; diagram/image claims require nonblank PNG and expected element/presentation evidence.
- Optional CATIA product features must pass either native execution evidence or a structured `UNSUPPORTED` probe with missing classes/plugins/license/project-mode details.

## Testing Strategy

### Unit Tests

Run from `mcp-server`:

```powershell
python -m pytest tests\test_client.py tests\test_server.py
```

Add focused tests for:

- request body construction
- timeout fields
- unsupported capability responses
- patch plan validation
- query DSL normalization
- CSV/XLSX import diff logic
- evidence bundle manifest generation

### Java Build

Use the known reliable local-temp copy workflow for Gradle/JDK 17. Document exact commands in `docs/development/build-and-live-validation.md`.

Current local command pattern:

```powershell
cd Z:\cameo-mcp-bridge\plugin
$env:JDK17_HOME = "D:\DevTools\jdk17\jdk-17.0.18+8"
.\gradlew.bat test -PcameoHome=D:/DevTools/CatiaMagic -Pjdk17Home=D:/DevTools/jdk17/jdk-17.0.18+8
.\gradlew.bat assemblePlugin -PcameoHome=D:/DevTools/CatiaMagic -Pjdk17Home=D:/DevTools/jdk17/jdk-17.0.18+8
```

Deployment validation command pattern:

```powershell
cd Z:\cameo-mcp-bridge\plugin
.\gradlew.bat deploy -PcameoHome=D:/DevTools/CatiaMagic -Pjdk17Home=D:/DevTools/jdk17/jdk-17.0.18+8
```

After deployment, restart CATIA Magic/Cameo completely, then verify:

```powershell
Invoke-RestMethod http://127.0.0.1:18740/api/v1/status
Invoke-RestMethod http://127.0.0.1:18740/api/v1/capabilities
Invoke-RestMethod http://127.0.0.1:18740/api/v1/project
```

### Live Tests

Every major capability gets a script:

- `live_validate_universal_inspector.py`
- `live_record_ui_diff.py`
- `live_validate_requirements_automation.py`
- `live_validate_traceability_autopilot.py`
- `live_validate_relation_map_mastery.py`
- `live_validate_matrix_mastery.py`
- `live_validate_diagram_intent.py`
- `live_validate_icd.py`
- `live_validate_native_validation.py`
- `live_validate_report_wizard.py`
- `live_probe_simulation.py`
- `live_probe_teamwork.py`
- `live_probe_datahub.py`
- `live_validate_excel_roundtrip.py`
- `live_validate_profile_dsl.py`

Each script must:

- capture status/capabilities first
- fail clearly if no project is open
- write artifacts under `validation-output/<feature>/`
- avoid destructive writes unless `--allow-write`
- create disposable packages for write tests
- save before/after snapshots for mutation tests

## Risk Register

| Risk | Impact | Mitigation |
|---|---|---|
| CATIA native API hangs the Swing EDT | Bridge appears frozen | Use explicit timeouts, no hidden refresh, write-state diagnostics |
| Plugin/license missing | Advanced features fail | Add capability probes before implementation |
| Teamwork auth varies by organization | Teamwork endpoints unreliable | Start read-only, support multiple auth discovery paths |
| Report Wizard APIs are sparse | Generation difficult | Start template discovery, use UI diff/probes, fall back to external assembly only as partial |
| DataHub/DOORS not installed | Integration cannot be live-proven | Implement CSV/Excel bridge-owned flow first |
| Macro escape hatch becomes permanent | Security and reliability risk | Require migration ticket for every useful macro |
| Dirty model state hides write side effects | Validation ambiguity | Use snapshots and disposable packages |
| Large model traversal explodes response size | Timeouts/memory pressure | Pagination, max depth, max elements, summaryOnly |
| Multiple agents edit shared files | Merge conflicts | Assign ownership and keep patches small |
| Natural language writes become unsafe | Model corruption | Apply only structured patch plans, require approval for writes |

## Rollback Plan

For code:

- Keep each capability on a small branch or commit series.
- Do not mix unrelated handler changes in one patch.
- Revert capability files only, not shared session fixes, unless explicitly approved.

For model writes:

- Use `snapshotBefore` and `snapshotAfter`.
- Use disposable packages for validation.
- Add rollback instructions in every `OperationReceipt`.
- If CATIA session is stuck, use `POST /api/v1/session/reset`, then re-check project state.

For deployment:

- Keep previous plugin jar available in install directory until new version is live-verified.
- After deploying, restart CATIA fully.
- Verify `/api/v1/status` version and `/api/v1/capabilities` before running live tests.

## Recommended Implementation Order Summary

1. Universal inspection, transaction receipts, patch plans, diagnostics.
2. UI diff recorder and evidence bundles.
3. Query DSL, recipe library, methodology workflow.
4. Requirements automation and completeness dashboard.
5. Criteria builder, traceability autopilot, Relation Map mastery, matrix mastery.
6. Diagram intent, diagram repair, ICD automation, deep handlers.
7. Native validation runner, pre-commit gate, AI-generated rule DSL.
8. Report Wizard, Collaborator, proofing, evidence outputs.
9. Simulation and trade studies.
10. Teamwork, change impact, version intelligence.
11. DataHub/ReqIF/CSV/DOORS and Excel roundtrip.
12. Profile/DSL, patterns, variants, safety/cyber.
13. Public demo, docs, release packaging.

This order maximizes near-term practical autonomy while reducing the risk of building advanced features on weak inspection and evidence foundations.
