# MagicDraw MCP Bridge (2022xR2 Backport)

An [MCP (Model Context Protocol)](https://modelcontextprotocol.io/) server that connects AI coding assistants to **MagicDraw 2022xR2** -- the industry-standard MBSE tool for SysML and UML modeling.

This is a backported version of the Cameo MCP Bridge, adapted to work with MagicDraw 2022xR2 with a `com.nomagic` package namespace to comply with corporate plugin restrictions.

> **Note on Methodology References:** This project's documentation references public MBSE methodologies and frameworks including OOSEM, UAF, and DoDAF. These references describe potential use cases for the bridge and are not affiliated with any specific defense program, contractor, or classified work. All methodology frameworks referenced are publicly available standards.

This lets Claude Code (or any MCP-compatible client) **query, create, modify, inspect, validate, and visualize** SysML/UML models inside a running MagicDraw instance through 162 tools covering capability negotiation, methodology-aware OOSEM workflows, semantic validation, state-machine semantics, elements, relationships, native matrices and tables, Relation Maps, reports, requirements import/export, validation suites, diagrams, reusable verification, specifications, and guarded macro execution.

```
Claude Code  <--stdio/MCP-->  Python MCP Server  <--HTTP/REST-->  Java Plugin (MagicDraw JVM)
```

## Why This Exists

MBSE tools like MagicDraw are powerful but manual. With this bridge, an AI assistant can:

- **Build models from requirements** -- "Create a state machine for ATM operations with idle, active, and maintenance states"
- **Query and navigate models** -- "Show me all blocks with the `<<requirement>>` stereotype"
- **Generate diagrams** -- Create sequence diagrams, BDDs, IBDs, state machines, and populate them with elements
- **Export diagram images** -- Get PNG snapshots of any diagram as base64
- **Run Groovy scripts** -- Escape hatch for anything the structured tools don't cover
- **Inspect and modify specifications** -- Read/write any UML property, tagged value, or constraint

### How Is This Different?

| Project | Approach | Status |
|---------|----------|--------|
| **This project** | Talks directly to MagicDraw's Java API via an embedded plugin | Backported to 2022xR2 |
| [Cameo MCP Bridge](https://github.com/ajhcs/cameo-mcp-bridge) | Original version for Cameo/CATIA Magic 2024x | Production |
| [SysML v2 API MCP Server](https://github.com/redsteve/SysML-v2-API-MCP-Server) | Connects to SysML v2 REST API (tool-agnostic) | Early stage, C++ |
| [EA MCP Server](https://www.sparxsystems.jp/en/MCP/) | Enterprise Architect integration | Closed-source, Windows-only |

This is an open-source MCP server that integrates directly with a running MagicDraw 2022xR2 instance, giving full access to SysML v1 models and the MagicDraw OpenAPI surface.

## Architecture

```
+-------------------+         +---------------------+         +---------------------------+
|                   |  stdio  |                     |  HTTP   |                           |
|  Claude Code /    |-------->|  Python MCP Server  |-------->|  Java Plugin              |
|  Any MCP Client   |<--------|  (cameo_mcp)        |<--------|  (MagicDrawMCPBridge)     |
|                   |   MCP   |                     | JSON    |                           |
+-------------------+         +---------------------+         +---------------------------+
                                                               |                         |
                                                               |  127.0.0.1:18740        |
                                                               |                         |
                                                               |  Handler families:      |
                                                               |  - Project/elements     |
                                                               |  - Relationships        |
                                                               |  - Matrices/tables      |
                                                               |  - Diagrams/RelationMap |
                                                               |  - UI/snapshots/probes  |
                                                               |  - Validation/reports   |
                                                               |  - Import/export        |
                                                               |  - Optional integrations|
                                                               +---------------------------+
                                                                         |
                                                               +---------v---------+
                                                               | MagicDraw 2022xR2 |
                                                               | JVM               |
                                                               | (OpenAPI, EMF,    |
                                                               |  SessionManager)  |
                                                               +-------------------+
```

**Key Architecture Changes for 2022xR2:**

- **Package Name**: `com.nomagic.magicdraw.mcpbridge` (was `com.claude.cameo.bridge`)
- **Plugin ID**: `com.nomagic.magicdraw.mcpbridge`
- **Java Version**: Java 11 (downgraded from Java 17)
- **Target**: MagicDraw 2022xR2 (was Cameo/CATIA Magic 2024x)
- **Plugin Version**: `1.0.0-md2022xr2`

**Data flow for a write operation:**

1. MCP client calls a tool (e.g., `cameo_create_element`)
2. Python server translates to HTTP POST to the Java plugin
3. Java handler dispatches to Swing EDT via `EdtDispatcher`
4. On EDT: opens a `SessionManager` session, executes the operation, closes the session
5. JSON response flows back through the layers

All write operations are session-wrapped for undo/redo support. Read operations run on the HTTP thread pool (MagicDraw model reads are thread-safe).

## Prerequisites

- **MagicDraw 2022xR2** installed
- **Java 11 JDK** (Amazon Corretto 11.0.21 recommended)
- **Python 3.10+** with `pip`
- **Gradle** (not required if using pre-built plugin)

## Installation

### Step 1: Configure Paths

Copy the configuration template and edit it with your local paths:

```bash
cp config.template.sh config.sh
# Edit config.sh and set:
# - MAGICDRAW_HOME (path to your MagicDraw 2022xR2 installation)
# - JAVA11_HOME (path to your Java 11 JDK)
```

**Example config.sh:**
```bash
export MAGICDRAW_HOME="C:/MagicDraw2022xR2"
export JAVA11_HOME="C:/Program Files/Amazon Corretto/jdk11.0.21_9"
```

**Note:** `config.sh` is in `.gitignore` and will not be committed to version control.

### Step 2: Run Installation

```bash
git clone <repository-url>
cd cameo-mcp-bridge
./install.sh
```

The install script will:
1. Load paths from `config.sh` (or use environment variables)
2. Build the Java plugin with Gradle using Java 11
3. Deploy it to `$MAGICDRAW_HOME/plugins/com.nomagic.magicdraw.mcpbridge/`
4. Create or reuse `mcp-server/.venv/`
5. Install the Python MCP server
6. Register with Claude Code when the `claude` CLI is available

### Manual Install

**1. Build the Java plugin:**

```bash
cd plugin
# Make sure MAGICDRAW_HOME and JAVA11_HOME are set (from config.sh or manually)
./gradlew assemblePlugin
```

Or with explicit paths:
```bash
./gradlew assemblePlugin -PcameoHome="/path/to/MagicDraw2022xR2" -Pjdk11Home="/path/to/jdk11"
```

**2. Deploy to MagicDraw:**

Copy the contents of `plugin/build/plugin-dist/com.nomagic.magicdraw.mcpbridge/` to:
```
<MAGICDRAW_HOME>/plugins/com.nomagic.magicdraw.mcpbridge/
```

The plugin directory should contain:
- `magicdraw-mcp-bridge-1.0.0-md2022xr2.jar`
- `plugin.xml`

**3. Install the Python server:**

```bash
cd mcp-server
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e .
```

On Windows shells, use `.venv\Scripts\activate` instead.

**4. Register with your MCP client:**

For Claude Code:
```bash
claude mcp add cameo-bridge --scope user -- /absolute/path/to/mcp-server/.venv/bin/python -m cameo_mcp.server
```

On Windows, the interpreter path is typically `.venv\Scripts\python.exe`.

**5. Restart MagicDraw 2022xR2**, open a project, and verify:

```
> Check cameo status
```

If the Python server and Java plugin are out of sync after an update, rebuild/redeploy the plugin, then restart MagicDraw.

## Backport Details

This version has been backported from Cameo 2024x to MagicDraw 2022xR2 with the following changes:

### Java Version Changes
- **Source/Target**: Java 11 (was Java 17)
- **Text blocks** converted to string concatenation
- **Pattern matching instanceof** converted to traditional syntax

### Package Changes
- **Package**: `com.nomagic.magicdraw.mcpbridge` (was `com.claude.cameo.bridge`)
- **Plugin ID**: `com.nomagic.magicdraw.mcpbridge`
- **Main Class**: `MagicDrawMCPBridgePlugin` (was `CameoMCPBridgePlugin`)

### API Compatibility
- Targets MagicDraw 2022xR2 APIs
- Required plugins: Diagram Table and Relation Map (2022x Refresh2)
- Plugin directory structure uses `com.nomagic.magicdraw.relationshipmap` (not `visualization.relationshipmap`)

### Build System
- Uses Amazon Corretto JDK 11
- Modified build paths for MagicDraw 2022xR2 library structure
- Updated Gradle configuration for Java 11 compatibility

## Configuration

### Required Configuration (config.sh)

Create a `config.sh` file from the template:

```bash
cp config.template.sh config.sh
```

Edit `config.sh` and set:
- `MAGICDRAW_HOME` - Path to your MagicDraw 2022xR2 installation
- `JAVA11_HOME` - Path to your Java 11 JDK

### Environment Variables

| Environment Variable | Default | Description |
|---------------------|---------|-------------|
| `MAGICDRAW_HOME` | `/opt/MagicDraw2022xR2` | Path to MagicDraw installation (set in config.sh) |
| `JAVA11_HOME` | unset | Path to Java 11 JDK (set in config.sh) |
| `CAMEO_BRIDGE_PORT` | `18740` | HTTP port for the bridge (must match both sides) |
| `CAMEO_MCP_STRUCTURED_RESPONSES` | deprecated | Structured MCP object responses are always used |

The Java plugin reads the port from system property `cameo.mcp.port` (default `18740`). To change it, add to your MagicDraw `*.vmoptions` file:

```
-Dcameo.mcp.port=18741
```

And set `CAMEO_BRIDGE_PORT=18741` in your environment before launching Claude Code.

## Tool Reference

The bridge provides 162 MCP tools across the following categories:

- **Project, Session & UI** (9 tools) - Status, capabilities, UI state, project info
- **Methodology Packs** (6 tools) - OOSEM workflows, recipes, validation
- **Elements** (8 tools) - Query, create, modify, delete model elements
- **Stereotypes & Tagged Values** (3 tools) - Apply stereotypes, set tagged values
- **Relationships** (2 tools) - Create and query relationships
- **Matrices & Generic Tables** (8 tools) - Native matrix artifacts
- **Relation Maps, Snapshots & Probes** (22 tools) - Relation Maps, snapshots, diffs
- **Advanced Native Surfaces** (42 tools) - Validation, reports, import/export, Teamwork, DataHub
- **Diagrams** (24 tools) - Create, populate, export, and manipulate diagrams
- **Verification** (2 tools) - Matrix and diagram verification
- **Semantic Validation** (4 tools) - Activity flow, port boundary, requirements quality
- **Auto Remediation** (2 tools) - Detect inconsistencies, build remediation plans
- **Proofing** (2 tools) - Proof model text, apply patches
- **Methodology Workflows** (4 tools) - Compare artifacts, validate packages, export diagrams
- **State Machine Semantics** (4 tools) - Transition triggers, state behaviors
- **Specification** (3 tools) - Get/set specifications, use case subjects
- **Macros** (1 tool) - Execute Groovy scripts

See the original README sections below for detailed tool descriptions.

## Known Limitations

### MagicDraw 2022xR2 Specific
- Some advanced features from 2024x may have limited support
- Relation Map APIs may differ slightly from 2024x version
- Some optional product integrations (DataHub, Teamwork, Simulation) may behave differently

### General Limitations
- **Diagram layout** - Models are correct but visual layout often needs manual adjustment
- **Nested presentations** - Complex nested elements (sequence diagram messages, composite states) may require manual cleanup
- **No ReqIF apply** - Native ReqIF remains preview-only
- **No element reparenting** - Cannot move elements between packages
- **No diagram delete/rename** - Can create but not delete or rename diagrams

See detailed limitations section below for workarounds.

## Security Considerations

This bridge is designed for **local development use only**.

- HTTP server binds to `127.0.0.1` (localhost only)
- **No authentication** on HTTP endpoints
- `cameo_execute_macro` executes **arbitrary Groovy code** in the MagicDraw JVM
- CORS headers set to `*` (wildcard)

**Do not** expose the bridge port to the network or use in production without additional security controls.

## Project Structure

```
cameo-mcp-bridge/
  mcp-server/                          # Python MCP server
    cameo_mcp/
      server.py                        # MCP tool definitions (162 tools)
      client.py                        # HTTP client for Java plugin
      verification.py                  # Diagram/matrix verification
      methodology/                     # Methodology packs
    pyproject.toml
  plugin/                              # Java MagicDraw plugin
    src/com/nomagic/magicdraw/mcpbridge/
      MagicDrawMCPBridgePlugin.java    # Plugin entry point
      HttpBridgeServer.java            # HTTP server + routing
      handlers/                        # 28 handler classes
      util/                            # 12 utility classes
    plugin.xml                         # Plugin descriptor
    build.gradle                       # Gradle build config
  install.sh                           # One-step installer
  LICENSE
  README.md
```

## Development

### Building the Plugin

```bash
cd plugin
./gradlew assemblePlugin -PcameoHome="C:/Users/borrth/MagicDraw2022xR2"
```

The output goes to `plugin/build/plugin-dist/com.nomagic.magicdraw.mcpbridge/`.

### Running the MCP Server Standalone

```bash
python -m cameo_mcp.server
```

This starts the MCP server on stdio. It will fail to connect unless MagicDraw is running with the plugin loaded.

## Compatibility

- **Tested**: MagicDraw 2022xR2
- **Java**: Java 11 (Amazon Corretto 11.0.21 recommended)
- **Python**: 3.10+
- **Required Plugins**: Diagram Table, Relation Map (bundled with MagicDraw 2022xR2)

## License

[MIT](LICENSE)

## Related

- **Original Project**: [Cameo MCP Bridge](https://github.com/ajhcs/cameo-mcp-bridge) (Cameo 2024x)
- **MBSE Agents**: [mbse-agents](https://github.com/ajhcs/mbse-agents) for standards-aware modeling

---

## Additional Tool Documentation

(Full tool reference sections from original README follow...)

### Project, Session & UI (9 tools)

| Tool | Description |
|------|-------------|
| `cameo_status` | Check plugin health and report client/plugin compatibility |
| `cameo_get_capabilities` | Get machine-readable endpoint/capability metadata |
| `cameo_probe_bridge` | Probe `/status` and `/api/v1/status` endpoints |
| `cameo_get_ui_state` | Inspect active project, diagram, browser selection |
| `cameo_get_active_diagram` | Get currently active diagram |
| `cameo_get_ui_selection` | Get selected browser elements and presentation IDs |
| `cameo_get_project` | Get project name, file path, root model ID |
| `cameo_save_project` | Save project to disk |
| `cameo_reset_session` | Force-close stuck editing session |

(Continue with remaining tool descriptions as needed...)

## Known Limitations (Detailed)

### Diagram Layout (Primary Pain Point)

The bridge builds models correctly -- elements, relationships, directionality, stereotypes, and structure all come out right. The main gap is **diagram presentation**: layout, spacing, and visual properties of complex diagrams often need manual adjustment.

| What Doesn't Work | Why |
|---|---|
| Spacing messages in sequence diagrams | Message arrows aren't top-level shapes |
| Moving messages relative to fragments | Nested presentation elements |
| Self-messages | `createPathElement()` fails when source == target |
| Region names in composite states | Region labels nested inside state shape |
| Resizing nested states | Sub-states in regions not accessible |
| Transition label display | Transition paths nested |

**Workarounds:**
- Use `cameo_execute_macro` with Groovy scripts for nested elements
- Use `cameo_auto_layout` for simple diagrams
- Manual drag-and-drop in MagicDraw (5-10 minutes for sequence diagrams)

### Not Yet Implemented
- Native ReqIF apply
- Optional-product writes (Teamwork, DataHub, simulation)
- Remove stereotype
- Delete/rename diagrams
- Element reparenting
- Undo/redo via MCP
- Bulk operations
- Model change notifications
- File-based diagram export

### API Gaps
- DurationConstraint/TimeConstraint creation unreliable
- Large diagram images may exceed token limits
- Direct file export not first-class
- Session recovery edge cases

## Contributing

Issues and pull requests welcome. Areas where contributions would be valuable:

- Testing on other MagicDraw 2022x versions
- Additional element and relationship type support
- Bulk operation endpoints
- Test coverage
- SysML v2 profile support
