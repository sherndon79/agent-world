# mcpctl — Simple CLI for agenTW∞rld Extension APIs

mcpctl is a tiny convenience CLI to call the Isaac Sim extension HTTP APIs
(WorldBuilder, WorldViewer, WorldSurveyor, WorldRecorder) using the same
HMAC/Bearer auth as the MCP servers (via the shared MCPBaseClient).

It’s useful for quick, authenticated checks without writing curl commands.

## Quick Start

- Defaults to localhost ports: WorldBuilder 8899, WorldViewer 8900,
  WorldSurveyor 8891, WorldRecorder 8892.
- Reads tokens/secrets from your `.env` at the repo root (same as MCP servers):
  - Global: `AGENT_EXT_AUTH_TOKEN`, `AGENT_EXT_HMAC_SECRET`
  - Per-service overrides also supported (e.g. `AGENT_WORLDBUILDER_HMAC_SECRET`).

Examples:

```bash
# WorldBuilder scene status
python mcpctl.py worldbuilder scene_status

# WorldBuilder near-point query
python mcpctl.py worldbuilder query_objects_near_point --point 5,0,2 --radius 10

# WorldViewer get asset transform
python mcpctl.py worldviewer get_asset_transform --usd-path /World/test_sphere_for_debug --calculation-mode auto

# Generic GET
python mcpctl.py worldbuilder GET /metrics.prom

# Generic POST with JSON body
python mcpctl.py worldbuilder POST /add_element --json '{"element_type":"cube","name":"box","position":[0,0,1]}'
```

## Optional venv

Create a local venv (only if needed):

```bash
cd mcp-servers/tools/mcpctl
python3 -m venv venv
./venv/bin/pip install -e .
```

## Notes

- This tool does not depend on MCP servers; it talks directly to the
  extension HTTP APIs using the same auth client as the MCP servers.
- Output is plain text or pretty-printed JSON where helpful.
