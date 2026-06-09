#!/bin/bash
# Configuration template for MagicDraw MCP Bridge
# Copy this file to config.sh and update the paths for your environment
# DO NOT commit config.sh to version control (it's in .gitignore)

# Path to your MagicDraw 2022xR2 installation
# Windows example: MAGICDRAW_HOME="C:/MagicDraw2022xR2"
# Unix example: MAGICDRAW_HOME="/opt/MagicDraw2022xR2"
export MAGICDRAW_HOME="/path/to/MagicDraw2022xR2"

# Path to Java 11 JDK (Amazon Corretto 11 recommended)
# Windows example: JAVA11_HOME="C:/Program Files/Amazon Corretto/jdk11.0.21_9"
# Unix example: JAVA11_HOME="/usr/lib/jvm/java-11-openjdk"
export JAVA11_HOME="/path/to/jdk11"

# Optional: Override the bridge HTTP port (default: 18740)
# export CAMEO_BRIDGE_PORT="18740"
