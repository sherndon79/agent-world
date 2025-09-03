# Claude Code Setup Guide

This guide shows how to configure agenTW∞rld extensions for use with Claude Code's MCP integration.

## Overview

agenTW∞rld provides MCP (Model Context Protocol) servers that allow Claude Code to interact with Isaac Sim extensions for 3D world building, camera control, waypoint management, and recording.

## Prerequisites

1. **Isaac Sim** - Version 2023.1.1 or later installed
2. **agenTW∞rld Extensions** - Installed and running in Isaac Sim
3. **Python Virtual Environments** - Created for each MCP server (see installation guide)

## Claude Code Configuration

### 1. Create .claude.json

Create a `.claude.json` file in your project directory with the agenTW∞rld MCP servers:

```json
{
  "mcpServers": {
    "worldbuilder-server": {
      "type": "stdio", 
      "command": "python",
      "args": ["path/to/agent-world/mcp-servers/worldbuilder/src/mcp_agent_worldbuilder.py"],
      "env": {}
    },
    "worldviewer-server": {
      "type": "stdio",
      "command": "python", 
      "args": ["path/to/agent-world/mcp-servers/worldviewer/src/mcp_agent_worldviewer.py"],
      "env": {}
    },
    "worldsurveyor-server": {
      "type": "stdio",
      "command": "python",
      "args": ["path/to/agent-world/mcp-servers/worldsurveyor/src/mcp_agent_worldsurveyor.py"], 
      "env": {}
    },
    "worldrecorder-server": {
      "type": "stdio",
      "command": "python",
      "args": ["path/to/agent-world/mcp-servers/worldrecorder/src/mcp_agent_worldrecorder.py"],
      "env": {}
    }
  }
}
```

### 2. Update Paths

Replace `path/to/agent-world` with your actual installation path:

- **Linux/Mac**: `/home/username/agent-world` or `/Users/username/agent-world`
- **Windows**: `C:\\Users\\username\\agent-world`

### 3. Python Command Setup

Choose the appropriate Python command for your setup:

**Option A: Use Unified Virtual Environment (Recommended)**
```json
"command": "/path/to/agent-world/mcp-servers/venv/bin/python"
```

**Option B: Use System Python**  
```json
"command": "python"
```

**Option C: Use Conda Environment**
```json  
"command": "/path/to/conda/envs/agent-world/bin/python"
```

Note: agenTW∞rld now uses a single unified virtual environment for all MCP servers, located at `mcp-servers/venv/`, which simplifies installation and reduces disk usage.

## Available MCP Tools

Once configured, Claude Code will have access to these tool categories:

### 🏗️ WorldBuilder Tools
- `mcp__worldbuilder-server__worldbuilder_add_element` - Add primitives (cubes, spheres, etc.)
- `mcp__worldbuilder-server__worldbuilder_place_asset` - Place USD assets
- `mcp__worldbuilder-server__worldbuilder_create_batch` - Create object groups
- `mcp__worldbuilder-server__worldbuilder_get_scene` - Query scene contents
- `mcp__worldbuilder-server__worldbuilder_clear_scene` - Clear scene elements

### 🎥 WorldViewer Tools  
- `mcp__worldviewer-server__worldviewer_set_camera_position` - Position camera
- `mcp__worldviewer-server__worldviewer_orbit_camera` - Orbital camera positioning
- `mcp__worldviewer-server__worldviewer_smooth_move` - Smooth camera transitions
- `mcp__worldviewer-server__worldviewer_frame_object` - Frame objects in view
- `mcp__worldviewer-server__worldviewer_get_camera_status` - Get camera info

### 🧭 WorldSurveyor Tools
- `mcp__worldsurveyor-server__worldsurveyor_create_waypoint` - Create spatial waypoints
- `mcp__worldsurveyor-server__worldsurveyor_list_waypoints` - List all waypoints  
- `mcp__worldsurveyor-server__worldsurveyor_goto_waypoint` - Navigate to waypoint
- `mcp__worldsurveyor-server__worldsurveyor_create_group` - Create waypoint groups
- `mcp__worldsurveyor-server__worldsurveyor_export_waypoints` - Export waypoint data

### 📹 WorldRecorder Tools
- `mcp__worldrecorder-server__worldrecorder_capture_frame` - Take screenshots
- `mcp__worldrecorder-server__worldrecorder_start_video` - Start video recording  
- `mcp__worldrecorder-server__worldrecorder_stop_video` - Stop video recording
- `mcp__worldrecorder-server__worldrecorder_get_status` - Get recording status

## Authentication Setup (Optional)

For secure deployments, you can add authentication:

```json
{
  "mcpServers": {
    "worldbuilder-server": {
      "type": "stdio",
      "command": "python",
      "args": ["path/to/mcp_agent_worldbuilder.py"],
      "env": {
        "AGENT_WORLDBUILDER_AUTH_TOKEN": "your-auth-token-here",
        "AGENT_WORLDBUILDER_HMAC_SECRET": "your-hmac-secret-here"
      }
    }
  }
}
```

## Troubleshooting

### Connection Issues

1. **Verify Isaac Sim is running** with extensions loaded
2. **Check extension status** - Look for green status indicators in Isaac Sim
3. **Confirm ports are available** (8899, 8900, 8891, 8892)
4. **Check Python paths** - Ensure MCP server scripts are accessible

### Health Checks

Test extension connectivity:
```bash
curl http://localhost:8899/health  # WorldBuilder
curl http://localhost:8900/health  # WorldViewer  
curl http://localhost:8891/health  # WorldSurveyor
curl http://localhost:8892/health  # WorldRecorder
```

All should return `{"success": true, "status": "healthy"}`.

### Common Issues

**"Command not found" errors**: Update Python paths in `.claude.json`
**"Connection refused"**: Ensure Isaac Sim extensions are running
**"Permission denied"**: Check file permissions on MCP server scripts
**"Module not found"**: Install dependencies in Python environment

## Example Usage

Once configured, you can ask Claude Code to:

```
"Create a red cube at position [0, 0, 1] and position the camera to view it"
"Take a screenshot of the current scene"
"Create a waypoint at the cube location called 'cube_location'"  
"Record a 10-second video while orbiting around the cube"
```

Claude Code will use the appropriate MCP tools to accomplish these tasks through Isaac Sim.

## Next Steps

- See [Installation Guide](installation.md) for initial setup
- Review [MCP Integration Guide](mcp-integration.md) for advanced configuration  
- Check individual [Extension Guides](extensions/) for detailed API references