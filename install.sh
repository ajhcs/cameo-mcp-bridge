#!/bin/bash
# install.sh - Install the Cameo MCP Bridge
set -euo pipefail

CAMEO_HOME="${CAMEO_HOME:-D:/DevTools/CatiaMagic}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

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

find_java17_home() {
    for candidate in "${JDK17_HOME:-}" "${JAVA17_HOME:-}" "${JAVA_HOME:-}"; do
        if [ -n "${candidate:-}" ] && [ -x "$candidate/bin/java" ]; then
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

echo "=== Cameo MCP Bridge Installer ==="
echo "CAMEO_HOME: $CAMEO_HOME"
echo ""

# Build the Java plugin
echo "Building Java plugin..."
cd "$SCRIPT_DIR/plugin"
if GRADLE_JAVA_HOME="$(find_java17_home)"; then
    echo "Using Java from: $GRADLE_JAVA_HOME"
    JAVA_HOME="$GRADLE_JAVA_HOME" PATH="$GRADLE_JAVA_HOME/bin:$PATH" \
        ./gradlew -Dorg.gradle.java.home="$GRADLE_JAVA_HOME" assemblePlugin -PcameoHome="$CAMEO_HOME"
else
    echo "Warning: no explicit Java 17 home detected via JDK17_HOME/JAVA17_HOME/JAVA_HOME."
    echo "Gradle will use the current PATH/JAVA_HOME. If the build fails, set JDK17_HOME."
    ./gradlew assemblePlugin -PcameoHome="$CAMEO_HOME"
fi
echo "Build complete."
echo ""

# Deploy to Cameo
echo "Deploying plugin to Cameo..."
mkdir -p "$CAMEO_HOME/plugins/com.claude.cameo.bridge"
cp -r build/plugin-dist/com.claude.cameo.bridge/* "$CAMEO_HOME/plugins/com.claude.cameo.bridge/"
echo "Plugin deployed to: $CAMEO_HOME/plugins/com.claude.cameo.bridge/"
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
echo "  1. Restart CATIA Magic"
echo "  2. Open a project"
echo "  3. Start a new Claude Code session"
echo "  4. Say: 'Check cameo status'"
