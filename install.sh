#!/bin/bash
# install.sh - Install the MagicDraw MCP Bridge
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Load configuration from config.sh if it exists
if [ -f "$SCRIPT_DIR/config.sh" ]; then
    echo "Loading configuration from config.sh..."
    source "$SCRIPT_DIR/config.sh"
else
    echo "Warning: config.sh not found. Using environment variables or defaults."
    echo "To configure, copy config.template.sh to config.sh and edit the paths."
fi

# Use MAGICDRAW_HOME from config, environment, or fall back to default
CAMEO_HOME="${MAGICDRAW_HOME:-${CAMEO_HOME:-/opt/MagicDraw2022xR2}}"

find_python() {
    if command -v python3 >/dev/null 2>&1; then
        echo "python3"
        return 0
    fi

    if command -v python >/dev/null 2>&1; then
        echo "python"
        return 0
    fi

    return 1
}

find_java11_home() {
    for candidate in "${JDK11_HOME:-}" "${JAVA11_HOME:-}" "${JAVA_HOME:-}"; do
        if [ -n "${candidate:-}" ] && [ -x "$candidate/bin/java" ]; then
            echo "$candidate"
            return 0
        fi
        # Also check for .exe on Windows paths
        if [ -n "${candidate:-}" ] && [ -x "$candidate/bin/java.exe" ]; then
            echo "$candidate"
            return 0
        fi
    done

    return 1
}

resolve_venv_python() {
    local venv_dir="$1"

    if [ -x "$venv_dir/bin/python" ]; then
        echo "$venv_dir/bin/python"
        return 0
    fi

    if [ -x "$venv_dir/Scripts/python.exe" ]; then
        echo "$venv_dir/Scripts/python.exe"
        return 0
    fi

    return 1
}

if ! PYTHON_BIN="$(find_python)"; then
    echo "Error: neither python3 nor python was found on PATH."
    exit 1
fi

echo "=== MagicDraw MCP Bridge Installer ==="
echo "CAMEO_HOME: $CAMEO_HOME"
echo ""

# Build the Java plugin
echo "Building Java plugin..."
cd "$SCRIPT_DIR/plugin"
if GRADLE_JAVA_HOME="$(find_java11_home)"; then
    echo "Using Java from: $GRADLE_JAVA_HOME"
    JAVA_HOME="$GRADLE_JAVA_HOME" PATH="$GRADLE_JAVA_HOME/bin:$PATH" \
        ./gradlew -Dorg.gradle.java.home="$GRADLE_JAVA_HOME" assemblePlugin -PcameoHome="$CAMEO_HOME"
else
    echo "Warning: no explicit Java 11 home detected via JDK11_HOME/JAVA11_HOME/JAVA_HOME."
    echo "Gradle will use the current PATH/JAVA_HOME. If the build fails, set JDK11_HOME."
    ./gradlew assemblePlugin -PcameoHome="$CAMEO_HOME"
fi
echo "Build complete."
echo ""

# Deploy to MagicDraw
echo "Deploying plugin to MagicDraw..."
mkdir -p "$CAMEO_HOME/plugins/com.nomagic.mcpbridge"
cp -r build/plugin-dist/com.nomagic.mcpbridge/* "$CAMEO_HOME/plugins/com.nomagic.mcpbridge/"
echo "Plugin deployed to: $CAMEO_HOME/plugins/com.nomagic.mcpbridge/"
echo ""

# Install Python MCP server
echo "Installing Python MCP server..."
cd "$SCRIPT_DIR/mcp-server"
if [ -n "${VIRTUAL_ENV:-}" ]; then
    MCP_PYTHON="$PYTHON_BIN"
else
    VENV_DIR="$SCRIPT_DIR/mcp-server/.venv"
    if [ ! -d "$VENV_DIR" ]; then
        "$PYTHON_BIN" -m venv "$VENV_DIR"
    fi
    if ! MCP_PYTHON="$(resolve_venv_python "$VENV_DIR")"; then
        echo "Error: could not locate Python inside $VENV_DIR"
        exit 1
    fi
fi
"$MCP_PYTHON" -m pip install -e . --quiet
echo "Python server installed."
echo ""

# Register with Claude Code
echo "Registering MCP server with Claude Code..."
if command -v claude >/dev/null 2>&1; then
    claude mcp add cameo-bridge --scope user -- "$MCP_PYTHON" -m cameo_mcp.server
else
    echo "Claude CLI not found. Register manually with:"
    echo "  claude mcp add cameo-bridge --scope user -- \"$MCP_PYTHON\" -m cameo_mcp.server"
fi
echo ""
echo "=== Installation complete ==="
echo ""
echo "Next steps:"
echo "  1. Restart MagicDraw 2022xR2"
echo "  2. Open a project"
echo "  3. Start a new Claude Code session"
echo "  4. Say: 'Check cameo status'"
