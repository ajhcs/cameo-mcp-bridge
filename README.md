# Cameo MCP Bridge

An [MCP (Model Context Protocol)](https://modelcontextprotocol.io/) server that connects AI coding assistants to **CATIA Magic / Cameo Systems Modeler** -- the industry-standard MBSE tool for SysML and UML modeling.

This lets Claude Code (or any MCP-compatible client) **query, create, modify, and visualize** SysML/UML models inside a running Cameo instance through 26 tools covering elements, relationships, diagrams, specifications, and Groovy macro execution.

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
- **Java 17** (ships with CATIA Magic, or provide your own)
- **Python 3.10+** with pip
- **Gradle 8.x** (wrapper included)

## Installation

### Quick Install

```bash
git clone https://github.com/ajhcs/cameo-mcp-bridge.git
cd cameo-mcp-bridge

# Set your Cameo install path (default: D:/DevTools/CatiaMagic)
export CAMEO_HOME="/path/to/your/CatiaMagic"

./install.sh
```

The install script:
1. Builds the Java plugin with Gradle
2. Deploys it to `$CAMEO_HOME/plugins/com.claude.cameo.bridge/`
3. Installs the Python MCP server (`pip install -e ./mcp-server`)
4. Registers the MCP server with Claude Code

### Manual Install

**1. Build the Java plugin:**

```bash
cd plugin
./gradlew assemblePlugin -PcameoHome="/path/to/CatiaMagic"
```

**2. Deploy to Cameo:**

Copy the contents of `plugin/build/plugin-dist/com.claude.cameo.bridge/` to:
```
<CAMEO_HOME>/plugins/com.claude.cameo.bridge/
```

**3. Install the Python server:**

```bash
cd mcp-server
pip install -e .
```

**4. Register with your MCP client:**

For Claude Code:
```bash
claude mcp add cameo-bridge --scope user -- python -m cameo_mcp.server
```

For other MCP clients, configure stdio transport with command `python -m cameo_mcp.server`.

**5. Restart CATIA Magic**, open a project, and verify:

```
> Check cameo status
```

## Configuration

| Environment Variable | Default | Description |
|---------------------|---------|-------------|
| `CAMEO_BRIDGE_PORT` | `18740` | HTTP port for the bridge (must match both sides) |

The Java plugin reads the port from system property `cameo.mcp.port` (default `18740`). To change it, add to your Cameo `*.vmoptions` file:

```
-Dcameo.mcp.port=18741
```

And set `CAMEO_BRIDGE_PORT=18741` in your environment before launching Claude Code.

## Tool Reference

### Project & Session (3 tools)

| Tool | Description |
|------|-------------|
| `cameo_status` | Check if Cameo is running and the plugin is responsive |
| `cameo_get_project` | Get project name, file path, and root model ID |
| `cameo_save_project` | Save the project to disk |
| `cameo_reset_session` | Force-close a stuck editing session (recovery tool) |

### Elements (6 tools)

| Tool | Description |
|------|-------------|
| `cameo_query_elements` | Search by type, name, package, stereotype |
| `cameo_get_element` | Get full details of a single element |
| `cameo_create_element` | Create a new model element (30+ types supported) |
| `cameo_modify_element` | Change name or documentation |
| `cameo_delete_element` | Remove an element and its children |
| `cameo_get_containment_tree` | Browse the project hierarchy |

**Supported element types:** Package, Class, Block, Property, Port, Activity, StateMachine, Interaction, UseCase, Actor, Requirement, InterfaceBlock, ConstraintBlock, ValueType, DataType, Signal, Enumeration, Component, Comment, Constraint, CallBehaviorAction, OpaqueAction, ActivityPartition, InitialNode, ActivityFinalNode, FlowFinalNode, DecisionNode, MergeNode, ForkNode, JoinNode, InputPin, OutputPin, Operation

### Stereotypes & Tagged Values (2 tools)

| Tool | Description |
|------|-------------|
| `cameo_apply_stereotype` | Apply a stereotype (e.g., `<<block>>`, `<<requirement>>`) |
| `cameo_set_tagged_values` | Set tagged values on a stereotyped element |

### Relationships (2 tools)

| Tool | Description |
|------|-------------|
| `cameo_create_relationship` | Create a relationship between two elements |
| `cameo_get_relationships` | Query relationships for an element |

**Supported relationship types:** Association, DirectedAssociation, Composition, Generalization, Dependency, ControlFlow, ObjectFlow, Allocate, Satisfy, Derive, Refine, Trace, Include, Extend

### Diagrams (9 tools)

| Tool | Description |
|------|-------------|
| `cameo_list_diagrams` | List all diagrams in the project |
| `cameo_create_diagram` | Create a new diagram (18 types supported) |
| `cameo_add_to_diagram` | Place a model element on a diagram canvas |
| `cameo_get_diagram_image` | Export a diagram as base64-encoded PNG |
| `cameo_auto_layout` | Apply Cameo's built-in auto-layout |
| `cameo_list_diagram_shapes` | List all shapes/paths with presentation IDs and bounds |
| `cameo_move_shapes` | Reposition/resize shapes on a diagram |
| `cameo_delete_shapes` | Remove shapes from a diagram (model elements preserved) |
| `cameo_add_diagram_paths` | Draw relationship paths between shapes on a diagram |
| `cameo_set_shape_properties` | Set display properties (colors, compartment visibility, etc.) |

**Supported diagram types:** Class, Package, UseCase, Activity, Sequence, StateMachine, Component, Deployment, CompositeStructure, Object, Communication, InteractionOverview, Timing, Profile, SysML BDD, SysML IBD, SysML Requirement, SysML Parametric

### Specification (2 tools)

| Tool | Description |
|------|-------------|
| `cameo_get_specification` | Read all UML properties, tagged values, and constraints |
| `cameo_set_specification` | Write properties, tagged values, or constraint fields |

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

### Build a State Machine

```
Create a state machine for an ATM with states: OFF, IDLE, ACTIVE, MAINTENANCE.
Add transitions: OFF->IDLE on startup, IDLE->ACTIVE on card insert,
ACTIVE->IDLE when transaction complete, any state->MAINTENANCE on service request.
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

**Root cause:** `cameo_list_diagram_shapes` and `cameo_move_shapes` only operate on **top-level** presentation elements. Shapes nested inside composite states, swimlanes, combined fragments, or interaction uses are invisible to the bridge. This means:

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

**Planned fix:** Make shape listing and manipulation recursive so nested presentation elements are accessible.

### Not Yet Implemented
- **Remove stereotype** -- can apply but not remove
- **Delete/rename diagrams** -- diagrams can be created and populated but not deleted or renamed through the bridge
- **Element reparenting** -- cannot move elements between packages
- **Undo/redo** -- sessions support undo in Cameo's UI, but no MCP tool to trigger it
- **Bulk operations** -- creating N elements requires N sequential API calls
- **Model change notifications** -- purely request/response; no event subscription
- **Verify relationship** -- `allocate`, `satisfy`, `derive`, `refine`, `trace` are supported, but `verify` is missing
- **File-based diagram export** -- `cameo_get_diagram_image` returns base64 over the wire; no option to save directly to a file path (use `cameo_execute_macro` with `ImageExporter.export(dpe, ImageExporter.PNG, file)` as a workaround)

### API Gaps
- **DurationConstraint / TimeConstraint** creation through macros is unreliable due to complex ownership chains in the Cameo API (`DurationInterval.setMin/setMax` requires `Duration` instances with specific ownership that the API rejects); add these manually in Cameo's UI
- **Large diagram images** may exceed MCP client token limits when returned as base64; use the macro workaround above to save directly to disk
- **`format` parameter** on `cameo_get_diagram_image` is accepted but ignored (always exports PNG)
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
      server.py                        # MCP tool definitions (26 tools)
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
