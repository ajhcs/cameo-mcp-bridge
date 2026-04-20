# Cameo MCP Bridge

An [MCP (Model Context Protocol)](https://modelcontextprotocol.io/) server that connects AI coding assistants to **CATIA Magic / Cameo Systems Modeler** -- the industry-standard MBSE tool for SysML and UML modeling.

This lets Claude Code (or any MCP-compatible client) **query, create, modify, and visualize** SysML/UML models inside a running Cameo instance through 46 tools covering capability negotiation, methodology-aware OOSEM workflows, semantic validation, state-machine semantics, elements, relationships, native requirement matrices, diagrams, reusable verification, specifications, and Groovy macro execution.

```
Claude Code  <--stdio/MCP-->  Python MCP Server  <--HTTP/REST-->  Java Plugin (Cameo JVM)
```

## Why This Exists

MBSE tools like Cameo are powerful but manual. With this bridge, an AI assistant can:

- **Build models from requirements** -- "Create a state machine for ATM operations with idle, active, and maintenance states"
- **Query and navigate models** -- "Show me all blocks with the `<<requirement>>` stereotype"
- **Generate diagrams** -- Create sequence diagrams, BDDs, IBDs, state machines, and populate them with elements
- **Export diagram images** -- Get PNG snapshots of any diagram as base64
- **Run Groovy scripts** -- Escape hatch for anything the structured tools don't cover
- **Inspect and modify specifications** -- Read/write any UML property, tagged value, or constraint

### How Is This Different?

| Project | Approach | Status |
|---------|----------|--------|
| **This project** | Talks directly to Cameo's Java API via an embedded plugin | Production-tested |
| [SysML v2 API MCP Server](https://github.com/redsteve/SysML-v2-API-MCP-Server) | Connects to SysML v2 REST API (tool-agnostic) | Early stage, C++ |
| [EA MCP Server](https://www.sparxsystems.jp/en/MCP/) | Enterprise Architect integration | Closed-source, Windows-only |
| Dassault's prototype | SysML v2 + MCP demo | Promotional, not shipped |

This is the only open-source MCP server that integrates directly with a running Cameo instance, giving full access to SysML v1 models and the complete Cameo API surface.

## Architecture

```
+-------------------+         +---------------------+         +---------------------------+
|                   |  stdio  |                     |  HTTP   |                           |
|  Claude Code /    |-------->|  Python MCP Server  |-------->|  Java Plugin              |
|  Any MCP Client   |<--------|  (cameo_mcp)        |<--------|  (CameoMCPBridgePlugin)   |
|                   |   MCP   |                     | JSON    |                           |
+-------------------+         +---------------------+         +---------------------------+
                                                               |                         |
                                                               |  127.0.0.1:18740        |
                                                               |                         |
                                                               |  Handlers:              |
                                                               |  - ProjectHandler       |
                                                               |  - ElementQueryHandler  |
                                                               |  - ElementMutationHandler|
                                                               |  - RelationshipHandler  |
                                                               |  - MatrixHandler        |
                                                               |  - DiagramHandler       |
                                                               |  - ContainmentTreeHandler|
                                                               |  - SpecificationHandler |
                                                               |  - MacroHandler         |
                                                               +---------------------------+
                                                                         |
                                                               +---------v---------+
                                                               | CATIA Magic /     |
                                                               | Cameo JVM         |
                                                               | (OpenAPI, EMF,    |
                                                               |  SessionManager)  |
                                                               +-------------------+
```

**Data flow for a write operation:**

1. MCP client calls a tool (e.g., `cameo_create_element`)
2. Python server translates to HTTP POST to the Java plugin
3. Java handler dispatches to Swing EDT via `EdtDispatcher`
4. On EDT: opens a `SessionManager` session, executes the operation, closes the session
5. JSON response flows back through the layers

All write operations are session-wrapped for undo/redo support. Read operations run on the HTTP thread pool (Cameo model reads are thread-safe).

## Prerequisites

- **CATIA Magic / Cameo Systems Modeler** 2024x or newer (any bundle: Systems of Systems Architect, Cyber Systems Engineer, etc.)
- **Java 17 JDK** available to Gradle
- **Python 3.10+** with `pip`
- **Gradle 8.x** (wrapper included)

## Installation

### Quick Install

```bash
git clone https://github.com/ajhcs/cameo-mcp-bridge.git
cd cameo-mcp-bridge

# Set your Cameo install path (default: D:/DevTools/CatiaMagic)
export CAMEO_HOME="/path/to/your/CatiaMagic"

# Optional: point the installer/Gradle at a Java 17 JDK explicitly
export JDK17_HOME="/path/to/jdk-17"

./install.sh
```

The install script:
1. Builds the Java plugin with Gradle and passes `CAMEO_HOME` through automatically
2. Deploys it to `$CAMEO_HOME/plugins/com.claude.cameo.bridge/`
3. Creates or reuses `mcp-server/.venv/` when not already inside a virtualenv
4. Installs the Python MCP server into that environment
5. Registers the MCP server with Claude Code when the `claude` CLI is available

### Manual Install

**1. Build the Java plugin:**

```bash
cd plugin
./gradlew assemblePlugin -PcameoHome="/path/to/CatiaMagic" -Pjdk17Home="/path/to/jdk-17"
```

Gradle must run on a Java 17 JDK. You can also set `JDK17_HOME` or `JAVA17_HOME` instead of passing `-Pjdk17Home=...`.

**2. Deploy to Cameo:**

Copy the contents of `plugin/build/plugin-dist/com.claude.cameo.bridge/` to:
```
<CAMEO_HOME>/plugins/com.claude.cameo.bridge/
```

**3. Install the Python server:**

```bash
cd mcp-server
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e .
```

On Windows shells, use `.venv\\Scripts\\activate` instead.

**4. Register with your MCP client:**

For Claude Code:
```bash
claude mcp add cameo-bridge --scope user -- /absolute/path/to/mcp-server/.venv/bin/python -m cameo_mcp.server
```

On Windows, the interpreter path is typically `.venv\\Scripts\\python.exe`.

For other MCP clients, configure stdio transport with the venv interpreter and command `-m cameo_mcp.server`.

**5. Restart CATIA Magic**, open a project, and verify:

```
> Check cameo status
```

If a newly added MCP tool returns HTTP 404 after an update, the Python server
and Java plugin are out of sync. Rebuild/redeploy the plugin, then restart
CATIA Magic so the new HTTP handlers are loaded.

The Python side now performs a capability handshake against the plugin before
non-status operations. If `cameo_status` or `cameo_get_capabilities` reports
`compatibility.clientCompatible = false`, stop and redeploy the matching plugin
before proceeding.

The Python MCP layer also ships a Phase 2 methodology surface for bounded
OOSEM workflows. These tools build named artifact recipes, workflow guidance,
conformance checks, semantic validation, and compact review packets on top of
the low-level bridge.

## What's New In 2.0

- Structured state-machine semantics for transition triggers plus `entry` / `do` / `exit` behaviors
- Python-side semantic validators for activity flow coherence, port/interface ownership, requirement quality, and cross-diagram traceability
- New OOSEM recipe starters for logical activity flows, logical port BDDs, and logical IBD traceability views
- Review packets that surface semantic findings alongside structural conformance and diagram evidence

## Configuration

| Environment Variable | Default | Description |
|---------------------|---------|-------------|
| `CAMEO_BRIDGE_PORT` | `18740` | HTTP port for the bridge (must match both sides) |
| `JDK17_HOME` | unset | Optional Java 17 home used by `install.sh` and Gradle |
| `JAVA17_HOME` | unset | Alternate Java 17 home override |
| `CAMEO_MCP_STRUCTURED_RESPONSES` | deprecated | Structured MCP object responses are now always used; this flag is kept only for backward compatibility with older docs |

The Java plugin reads the port from system property `cameo.mcp.port` (default `18740`). To change it, add to your Cameo `*.vmoptions` file:

```
-Dcameo.mcp.port=18741
```

And set `CAMEO_BRIDGE_PORT=18741` in your environment before launching Claude Code.

For local health checks, the plugin now responds on both `/api/v1/status` and the legacy `/status` alias. The same applies to `/api/v1/capabilities` and `/capabilities`.

## Tool Reference

### Project & Session (6 tools)

| Tool | Description |
|------|-------------|
| `cameo_status` | Check plugin health and report client/plugin compatibility |
| `cameo_get_capabilities` | Get machine-readable endpoint/capability metadata |
| `cameo_probe_bridge` | Probe `/status` and `/api/v1/status` style endpoints and report the preferred local health paths |
| `cameo_get_project` | Get project name, file path, and root model ID |
| `cameo_save_project` | Save the project to disk |
| `cameo_reset_session` | Force-close a stuck editing session (recovery tool) |

### Methodology Packs (6 tools)

| Tool | Description |
|------|-------------|
| `cameo_list_methodology_packs` | List built-in methodology packs such as `oosem` |
| `cameo_get_methodology_pack` | Get one pack's phases, recipes, naming rules, and evidence structure |
| `cameo_get_methodology_guidance` | Explain which artifact is missing next and why |
| `cameo_execute_methodology_recipe` | Execute a bounded recipe and return receipts, conformance, and review packet output |
| `cameo_validate_methodology_recipe` | Validate normalized artifact snapshots against recipe expectations |
| `cameo_generate_review_packet` | Generate a compact evidence bundle and Markdown review packet without mutating the model |

### Elements (8 tools)

| Tool | Description |
|------|-------------|
| `cameo_query_elements` | Search by type, name, package, stereotype, with paging and compact/full views |
| `cameo_get_element` | Get full details of a single element |
| `cameo_create_element` | Create a new model element |
| `cameo_modify_element` | Change name or documentation |
| `cameo_delete_element` | Remove an element and its children |
| `cameo_get_containment_tree` | Browse the project hierarchy |
| `cameo_list_containment_children` | Page/filter immediate children for large models with compact/full views |
| `cameo_apply_profile` | Apply a profile to a model/package so custom stereotypes become usable |

**Supported element types:** Package, Profile, Stereotype, Class, Block, Property, FlowProperty, Port, Interface, Activity, UseCase, Actor, StateMachine, State, Pseudostate, InitialState, Requirement, InterfaceBlock, ConstraintBlock, ValueType, DataType, Signal, Enumeration, Component, Comment, Constraint, CallBehaviorAction, OpaqueAction, ActivityPartition, InitialNode, ActivityFinalNode, FlowFinalNode, DecisionNode, MergeNode, ForkNode, JoinNode, InputPin, OutputPin, Operation

SysML aliases such as `Block`, `Requirement`, `ConstraintBlock`, `InterfaceBlock`, `ValueType`, and `FlowProperty` rely on the SysML profile being available. The bridge now treats missing required stereotypes as an error instead of silently producing plain UML elements.
`Pseudostate` currently maps to an initial pseudostate in the MVP.

For large projects, prefer `cameo_list_containment_children` over `cameo_get_containment_tree`. The recursive tree endpoint is still available for compatibility, but it can produce very large responses on real models.

### Stereotypes & Tagged Values (3 tools)

| Tool | Description |
|------|-------------|
| `cameo_apply_stereotype` | Apply a stereotype (e.g., `<<block>>`, `<<requirement>>`) |
| `cameo_set_tagged_values` | Set tagged values on a stereotyped element |
| `cameo_set_stereotype_metaclasses` | Bind a stereotype to UML metaclasses using Cameo's supported API |

If you create a custom profile through MCP, the typical sequence is:
1. Create the `Profile`
2. Create `Stereotype` elements inside it, optionally with `metaclasses=[...]`
3. Call `cameo_apply_profile` on the target model/package
4. Apply the new stereotypes to model elements

### Relationships (2 tools)

| Tool | Description |
|------|-------------|
| `cameo_create_relationship` | Create a relationship between two elements |
| `cameo_get_relationships` | Query relationships for an element |

**Supported relationship types:** Association, DirectedAssociation, Composition, Generalization, Dependency, ControlFlow, ObjectFlow, Transition, Connector, InformationFlow, ItemFlow, Allocate, Satisfy, Derive, Refine, Trace, Verify, Include, Extend

`Connector` supports nested-port `partWithPort` ownership. `InformationFlow` and `ItemFlow` support structured `realizingConnector`, `conveyed`, and SysML `itemProperty` payload data for IBD item-flow workflows. When you pass an IBD context element as `ownerId`, the bridge resolves the actual `InformationFlow`/`ItemFlow` containment to the nearest package because Cameo does not allow those relationships to be owned directly by a block.

### Matrices (4 tools)

| Tool | Description |
|------|-------------|
| `cameo_list_matrix_kinds` | List validated native matrix kinds, aliases, and example type domains |
| `cameo_list_matrices` | List supported native matrix artifacts in the project |
| `cameo_get_matrix` | Read one supported native matrix with rows, columns, and populated cells |
| `cameo_create_matrix` | Create a supported native matrix artifact |

**Supported matrix kinds:** `refine`, `derive`, `satisfy`, `allocation`

These tools target Cameo's native matrix artifacts:
- `refine` -> `Refine Requirement Matrix`
- `derive` -> `Derive Requirement Matrix`
- `satisfy` -> `Satisfy Requirement Matrix`
- `allocation` -> `SysML Allocation Matrix`

This matrix family is separate from the diagram shape/path API. It manages native matrix artifacts and returns row/column/cell data directly.

`cameo_create_matrix` also accepts optional `row_types` and `column_types` lists so native matrix artifacts can be constrained to specific domains when the underlying matrix kind supports it. Use `cameo_list_matrix_kinds` to see the validated kind aliases and live-proven example type domains.

### Diagrams (22 tools)

| Tool | Description |
|------|-------------|
| `cameo_list_diagram_types` | List validated diagram request tokens, aliases, and native Cameo types |
| `cameo_list_diagrams` | List all diagrams in the project |
| `cameo_create_diagram` | Create a new diagram (18 types supported) |
| `cameo_add_to_diagram` | Place a model element on a diagram canvas and return its `presentationId` |
| `cameo_get_diagram_image` | Export a diagram image with optional metadata-only, resize, and transcode controls |
| `cameo_auto_layout` | Apply Cameo's built-in auto-layout |
| `cameo_list_diagram_shapes` | List diagram shapes with paging, filtering, summary counts, and presentation IDs |
| `cameo_get_shape_properties` | Read the current display properties of one diagram shape |
| `cameo_move_shapes` | Reposition/resize shapes on a diagram with per-item results |
| `cameo_delete_shapes` | Remove shapes from a diagram (model elements preserved) |
| `cameo_add_diagram_paths` | Draw relationship paths between shapes on a diagram |
| `cameo_set_shape_properties` | Set display properties (colors, compartment visibility, etc.) with receipts |
| `cameo_set_shape_compartments` | Apply normalized compartment visibility controls to one shape |
| `cameo_set_transition_label_presentation` | Apply a high-level state-transition label preset instead of guessing raw Cameo property names |
| `cameo_set_item_flow_label_presentation` | Apply a high-level item-flow/information-flow label preset for IBD cleanup |
| `cameo_set_allocation_compartment_presentation` | Apply a high-level allocation/full-port presentation preset for SysML BDD cleanup |
| `cameo_repair_hidden_labels` | Auto-show hidden labels using diagram-type-aware native repair defaults |
| `cameo_repair_label_positions` | Reset likely-overlapping path labels with dry-run receipts |
| `cameo_repair_conveyed_item_labels` | Force conveyed-item/item-flow labels on eligible paths |
| `cameo_normalize_compartment_presets` | Normalize compartment/full-port visibility by diagram type |
| `cameo_reparent_shapes` | Move existing presentation elements under new container shapes |
| `cameo_route_paths` | Update path breakpoints, endpoints, and label reset behavior |

**Validated diagram request tokens:** `Class`, `Package`, `UseCase`, `Activity`, `Sequence`, `StateMachine`, `Component`, `Deployment`, `CompositeStructure`, `Object`, `Communication`, `InteractionOverview`, `Timing`, `Profile`, `BDD`, `IBD`, `Requirement Diagram`, `Parametric Diagram`

Use `cameo_list_diagram_types` if you want the accepted aliases too. Common forms such as `InternalBlockDiagram`, `SysML IBD`, `ClassDiagram`, and `StateMachineDiagram` are normalized to the validated token set automatically.

### Verification (2 tools)

| Tool | Description |
|------|-------------|
| `cameo_verify_matrix_consistency` | Check matrix row/column membership, populated-cell count, dependency names, and density |
| `cameo_verify_diagram_visual` | Check rendered PNG validity, diagram/path presence, content coverage, and coarse overlap risk |

These verification tools are Python-side wrappers over the bridge's native diagram and matrix readback. They are intended for repeatable regression checks, visual sanity validation, and lightweight quantitative validation without dropping to raw macros.

### Semantic Validation (4 tools)

| Tool | Description |
|------|-------------|
| `cameo_verify_activity_flow_semantics` | Check connected behavior flow, initial/final reachability, and swimlane sanity on an activity diagram |
| `cameo_verify_port_boundary_consistency` | Check interface-block flow-property ownership, duplicate vocabulary, and direction conflicts |
| `cameo_verify_requirement_quality` | Check requirement IDs, non-blank text, and basic measurability/readiness |
| `cameo_verify_cross_diagram_traceability` | Compare activity, interface, IBD, and requirements-to-architecture vocabulary/trace coverage |

These tools are the semantics-first layer for MBSE review. They use bridge readback plus lightweight Python heuristics to catch the common failure mode where a diagram looks plausible but does not hold together as a reviewable model.

### Auto Remediation (2 tools)

| Tool | Description |
|------|-------------|
| `cameo_detect_cross_diagram_inconsistencies` | Run semantic checks and return previewable remediation receipts plus a `patchPlan` |
| `cameo_build_cross_diagram_remediation_plan` | Turn existing validation payloads into a non-mutating remediation plan |

These tools do not mutate the model. They exist to bridge the gap between validation and safe repair by returning structured preview steps that later apply flows can consume.

### Proofing (2 tools)

| Tool | Description |
|------|-------------|
| `cameo_proof_model_text` | Collect and proof requirements, comments, state/transition names, and diagram labels, with optional safe auto-apply |
| `cameo_apply_proofing_patch_plan` | Apply a previously generated proofing patch plan to the live model |

Proofing is intentionally scoped to high-confidence name/text fixes. The proof report includes findings, metrics, sections, and a preview patch plan even when `auto_apply` is off.

### Methodology Workflows (4 tools)

| Tool | Description |
|------|-------------|
| `cameo_compare_expected_artifact_list` | Diff current artifacts against an expected methodology artifact list and return preview actions |
| `cameo_validate_methodology_package` | Validate a pack/recipe/package scope against the methodology definition |
| `cameo_export_required_diagrams` | Plan or execute export of the methodology-required diagram set |
| `cameo_assemble_ppt_pdf` | Plan or assemble PPT/PDF review packages from the exported diagram set |

For PPTX assembly, install the Python dependencies from `mcp-server/pyproject.toml` so `python-pptx` is available in the MCP runtime environment.

### State Machine Semantics (4 tools)

| Tool | Description |
|------|-------------|
| `cameo_get_transition_triggers` | Read explicit trigger semantics for one transition |
| `cameo_set_transition_trigger` | Create or replace one change-event or signal-event trigger |
| `cameo_get_state_behaviors` | Read `entry`, `do`, and `exit` state behaviors |
| `cameo_set_state_behaviors` | Create or replace structured `entry`, `do`, and `exit` behavior payloads |

These tools give the MCP layer first-class state semantics instead of forcing agents to approximate them through generic specification writes or raw macro fallback.

### Specification (3 tools)

| Tool | Description |
|------|-------------|
| `cameo_get_specification` | Read all UML properties, tagged values, and constraints |
| `cameo_set_specification` | Write properties, tagged values, or constraint fields |
| `cameo_set_usecase_subject` | Set or clear the UML subject classifier for a use case |

### Macros (1 tool)

| Tool | Description |
|------|-------------|
| `cameo_execute_macro` | Execute arbitrary Groovy scripts inside the Cameo JVM |

The macro tool is an escape hatch for operations not covered by the structured tools. Scripts have full access to the Cameo OpenAPI, with `project`, `application`, `primaryModel`, and `ef` (ElementsFactory) pre-injected into the script context.

**Important:** Scripts that modify the model must manage their own sessions:

```groovy
import com.nomagic.magicdraw.openapi.uml.SessionManager

SessionManager.getInstance().createSession(project, "My operation")
try {
    // ... modify model ...
    SessionManager.getInstance().closeSession(project)
} catch (Exception e) {
    SessionManager.getInstance().cancelSession(project)
    throw e
}
```

If a macro fails mid-session, use `cameo_reset_session` to recover.

## Usage Examples

### Create a SysML Block

```
Create a block called "Sensor" in the root model package
```

The AI will:
1. Call `cameo_get_project` to find the root model ID
2. Call `cameo_create_element` with type "Block", name "Sensor", and the root model ID as parent

### Build A State Machine

```
Create a state machine for an ATM with states OFF, IDLE, ACTIVE, and MAINTENANCE.
Add an initial pseudostate and transitions: initial -> OFF, OFF -> IDLE on startup,
IDLE -> ACTIVE on card insert, ACTIVE -> IDLE on transaction complete, and any state
-> MAINTENANCE on service request.
```

### Query and Modify

```
Find all requirements in the project and show me their IDs and text
```

### Export Diagrams

```
Export the "System Overview" diagram as a PNG and save it to my desktop
```

### Run a Groovy Script

```
Run a macro that lists all profiles loaded in the current project
```

## Known Limitations

### Diagram Layout (Primary Pain Point)

The bridge builds models correctly -- elements, relationships, directionality, stereotypes, and structure all come out right. The main gap is **diagram presentation**: layout, spacing, and visual properties of complex diagrams often need manual adjustment in Cameo's GUI.

`cameo_list_diagram_shapes` now discovers nested presentation elements recursively, but complex nested editing is still incomplete. Sequence diagrams, composite states, and other deeply nested presentations can still require manual cleanup or Groovy fallbacks. This means:

| What Doesn't Work | Why |
|---|---|
| Spacing messages vertically in sequence diagrams | Message arrows aren't top-level shapes; no Y-position control during creation |
| Moving messages relative to combined fragments (ref boxes) | Same -- messages and fragments are nested presentation elements |
| Self-messages (lifeline to itself) | `PresentationElementsManager.createPathElement()` fails when source == target |
| Showing region names in composite states | Region labels are nested inside the state shape; can't be found or configured |
| Resizing nested states to show full entry/exit behaviors | Sub-states in regions aren't accessible through the flat shape listing |
| Controlling transition label text display | Transition paths inside composite states are nested |

**Workarounds:**
- Use `cameo_execute_macro` with Groovy scripts that access nested presentation elements directly
- Use `cameo_auto_layout` (works well for simple diagrams, less so for complex state machines)
- For sequence diagrams: the model is correct, so manual drag-and-drop in Cameo takes 5-10 minutes
- For state machines: widen shapes and toggle region name visibility manually

**Current direction:** Keep expanding structured editing for nested presentation elements so fewer workflows require macros.

### Not Yet Implemented
- **Generic matrix/table artifact handler** -- native matrix support currently covers refine, derive, satisfy, and allocation matrices only
- **Remove stereotype** -- can apply but not remove
- **Delete/rename diagrams** -- diagrams can be created and populated but not deleted or renamed through the bridge
- **Element reparenting** -- cannot move elements between packages
- **Undo/redo** -- sessions support undo in Cameo's UI, but no MCP tool to trigger it
- **Bulk operations** -- creating N elements requires N sequential API calls
- **Model change notifications** -- purely request/response; no event subscription
- **File-based diagram export** -- `cameo_get_diagram_image` returns base64 over the wire; no option to save directly to a file path (use `cameo_execute_macro` with `ImageExporter.export(dpe, ImageExporter.PNG, file)` as a workaround)

### API Gaps
- **DurationConstraint / TimeConstraint** creation through macros is unreliable due to complex ownership chains in the Cameo API (`DurationInterval.setMin/setMax` requires `Duration` instances with specific ownership that the API rejects); add these manually in Cameo's UI
- **Large diagram images** can still exceed MCP client token limits at full resolution; prefer `cameo_get_diagram_image(include_image=false)` for metadata-only reads or use `max_width` / `max_height` with `format="jpeg"` before dropping to a macro-based file export
- **Direct file export** is still not first-class; if you need the bridge to save a diagram straight to disk, use `cameo_execute_macro` with `ImageExporter.export(...)`
- **Session recovery edge case** -- if a macro crashes mid-transaction, `cameo_reset_session` may itself throw `TransactionAlreadyCommitedException`; in this case, saving and reopening the project is the most reliable recovery

### Compatibility
- Tested with CATIA Magic Systems of Systems Architect 2024x
- Should work with any Cameo Systems Modeler 2024x bundle (2024x+)
- Requires Groovy script engine (bundled with Cameo) for macro execution
- The Gradle build requires access to Cameo's `lib/` directory for compile-time dependencies

## Security Considerations

This bridge is designed for **local development use only**.

- The HTTP server binds to `127.0.0.1` (localhost only) -- not accessible from the network
- There is **no authentication** on the HTTP endpoints
- The `cameo_execute_macro` tool executes **arbitrary Groovy code** inside the Cameo JVM with full access to the filesystem, network, and classloader
- CORS headers are set to `*` (wildcard) -- any webpage in a local browser could theoretically make requests to the bridge

**Do not** expose the bridge port to the network, run it on shared/multi-user machines without additional access controls, or use it in production environments without adding authentication.

## Project Structure

```
cameo-mcp-bridge/
  mcp-server/                          # Python MCP server
    cameo_mcp/
      __init__.py
      client.py                        # HTTP client for the Java plugin
server.py                        # MCP tool definitions (46 tools)
      verification.py                  # reusable diagram/matrix verification helpers
      methodology/                     # Phase 2 pack registry + recipe runtime
        registry.py
        runtime.py
        service.py
    pyproject.toml
  plugin/                              # Java Cameo plugin
    src/com/claude/cameo/bridge/
      CameoMCPBridgePlugin.java        # Plugin entry point
      HttpBridgeServer.java            # Embedded HTTP server + routing
      handlers/
        ProjectHandler.java            # Project info, save
        ElementQueryHandler.java       # Element search, get, relationships
        ElementMutationHandler.java    # Create, modify, delete elements
        RelationshipHandler.java       # Create relationships
        MatrixHandler.java             # Native matrix artifacts
        DiagramHandler.java            # Full diagram lifecycle
        ContainmentTreeHandler.java    # Containment tree browsing
        SpecificationHandler.java      # Specification read/write
        MacroHandler.java              # Groovy script execution
      util/
        EdtDispatcher.java             # EDT dispatch with session management
        ElementSerializer.java         # Element to JSON serialization
        JsonHelper.java                # JSON parsing utilities
    plugin.xml                         # Cameo plugin descriptor
    build.gradle                       # Gradle build config
  install.sh                           # One-step installer
  LICENSE
  README.md
```

## Development

### Building the Plugin

```bash
cd plugin
./gradlew assemblePlugin -PcameoHome="/path/to/CatiaMagic"
```

The output goes to `plugin/build/plugin-dist/com.claude.cameo.bridge/`.

### Running the MCP Server Standalone

```bash
python -m cameo_mcp.server
```

This starts the MCP server on stdio. It will fail to connect to the Java plugin unless Cameo is running with the plugin loaded.

### Adding a New Tool

1. Add the HTTP handler method in the appropriate Java handler class
2. Register the route in `HttpBridgeServer.registerHandlers()`
3. Add the async client function in `client.py`
4. Add the MCP tool function with docstring in `server.py`

The MCP tool docstrings are critical -- they are the AI's instruction manual. Include valid values, examples, common mistakes, and cross-references to related tools.

## Contributing

Issues and pull requests welcome. If you're building something similar for other MBSE tools, let's talk.

Areas where contributions would be especially valuable:
- Additional element and relationship type support
- Bulk operation endpoints
- Test coverage
- Support for Cameo Teamwork Cloud projects
- SysML v2 profile support

## License

[MIT](LICENSE)

## Related: MBSE Agents

Use with [mbse-agents](https://github.com/ajhcs/mbse-agents) for standards-aware modeling across aerospace, defense, automotive, and medical device domains. The agents provide practitioner-level domain knowledge (ARP4754A, DoDAF, ISO 26262, IEC 62304). This bridge provides direct tool access. Together: an AI that knows the standards at the clause level AND can modify your Cameo model.
