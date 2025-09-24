#!/usr/bin/env bash
set -euo pipefail

: "${MCP_SERVER:?MCP_SERVER must be set}"
VENV_PY="/app/venv/bin/python"

case "$MCP_SERVER" in
  worldbuilder|worldviewer|worldsurveyor|worldrecorder|worldstreamer)
    TARGET="/app/${MCP_SERVER}/src/main.py"
    exec "$VENV_PY" "$TARGET"
    ;;
  *)
    TARGET="/app/${MCP_SERVER}/src/mcp_agent_${MCP_SERVER}.py"
    exec "$VENV_PY" "$TARGET"
    ;;
esac
