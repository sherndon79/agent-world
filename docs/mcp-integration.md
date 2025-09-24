# MCP Integration Guide

agenTW∞rld Extensions provide comprehensive Model Context Protocol (MCP) integration, enabling AI agents to interact with Isaac Sim through standardized MCP tools and resources.

## For New Users

**MCP integration is automatically set up by the installer!** If you ran `install_agent_world.sh` and chose "yes" for MCP servers, you're ready to use AI tools like Claude Code.

**You only need this guide if you:**
- Want to configure MCP servers manually
- Are using a different MCP client  
- Need to troubleshoot MCP connectivity

## Overview

Each extension includes a dedicated MCP server that translates between MCP protocol and the extension's HTTP APIs, providing seamless AI agent integration.

**Key Orchestration Features:**
- **Independent MCP servers** enable parallel and sequential workflows
- **No inter-server dependencies** allow flexible AI-driven orchestration
- **Unified authentication** across all servers for seamless integration
- **Consistent error handling** enables robust multi-server workflows

## MCP Servers

### Available Servers

- **WorldBuilder MCP**: Scene creation and manipulation tools
- **WorldViewer MCP**: Camera control and navigation tools  
- **WorldSurveyor MCP**: Waypoint and spatial marking tools
- **WorldRecorder MCP**: Screenshot and video recording tools
- **Screenshot MCP**: Desktop and window screenshot capture
- **Asset Discovery MCP**: Asset search and generation tools (supplementary)

### Server Architecture

Each MCP server:
- Connects to corresponding Isaac Sim extension HTTP API
- Provides rich error handling and validation
- Supports both synchronous and asynchronous operations
- Includes comprehensive help text and examples

Authentication: MCP servers use a shared MCPBaseClient with automatic 401-challenge negotiation. When auth is enabled (.env AGENT_EXT_AUTH_ENABLED=1), the client retries with HMAC (X-Timestamp/X-Signature) and optional Authorization: Bearer <token> using AGENT_EXT_* or per-service AGENT_<SERVICE>_* variables.

## Installation

### Prerequisites

#### Quick Setup (Recommended)
Use the agenTW∞rld installer to automatically set up MCP server virtual environments:

```bash
# Linux/macOS
./scripts/install_agent_world.sh
# Answer "yes" when prompted: "Create Python virtual environments for MCP servers?"

# Windows
./scripts/install_agent_world.ps1
# Answer "yes" when prompted: "Create Python virtual environments for MCP servers?"
```

#### Manual Setup
If setting up manually, create a unified virtual environment for all MCP servers:

```bash
# Create unified virtual environment in mcp-servers directory
cd mcp-servers
python3 -m venv venv
source venv/bin/activate  # Linux/macOS
# or: venv\Scripts\activate  # Windows

# Upgrade pip and install build tools
pip install --upgrade pip setuptools wheel

# Install the unified MCP package with all dependencies
pip install -e .
```

**Note:** The installer uses a unified virtual environment approach that installs all MCP servers from a single `pyproject.toml` file in the `mcp-servers` directory. This simplifies dependency management and reduces disk usage. All MCP servers use the shared Python interpreter at `mcp-servers/venv/bin/python`.

### MCP Client Configuration

Add to your MCP client configuration (e.g., Claude Desktop):

```json
{
  "mcpServers": {
    "worldbuilder-server": {
      "type": "stdio",
      "command": "/path/to/agent-world/mcp-servers/venv/bin/python",
      "args": [
        "/path/to/agent-world/mcp-servers/worldbuilder/src/main.py"
      ],
      "env": {}
    },
    "worldviewer-server": {
      "type": "stdio",
      "command": "/path/to/agent-world/mcp-servers/venv/bin/python",
      "args": [
        "/path/to/agent-world/mcp-servers/worldviewer/src/main.py"
      ],
      "env": {}
    },
    "worldsurveyor-server": {
      "type": "stdio",
      "command": "/path/to/agent-world/mcp-servers/venv/bin/python",
      "args": [
        "/path/to/agent-world/mcp-servers/worldsurveyor/src/main.py"
      ],
      "env": {}
    },
    "worldrecorder-server": {
      "type": "stdio",
      "command": "/path/to/agent-world/mcp-servers/venv/bin/python",
      "args": [
        "/path/to/agent-world/mcp-servers/worldrecorder/src/main.py"
      ],
      "env": {}
    },
    "screenshot-server": {
      "type": "stdio",
      "command": "/path/to/agent-world/mcp-servers/venv/bin/python",
      "args": [
        "/path/to/agent-world/mcp-servers/desktop-screenshot/src/mcp_screenshot_server.py"
      ],
      "env": {
        "SCREENSHOT_OUTPUT_DIR": "/tmp/screenshots"
      }
    }
  }
}
```

## Available MCP Tools

### WorldBuilder Tools

#### Scene Creation
- `worldbuilder_add_element` - Create primitive shapes (cubes, spheres, etc.)
- `worldbuilder_create_batch` - Create multiple elements as a group
- `worldbuilder_place_asset` - Place USD assets in the scene

#### Scene Management  
- `worldbuilder_get_scene` - Retrieve complete scene structure
- `worldbuilder_list_elements` - Get flat list of all scene elements
- `worldbuilder_remove_element` - Remove specific elements
- `worldbuilder_clear_scene` - Clear entire scene (with confirmation)

#### Spatial Queries
- `worldbuilder_query_objects_by_type` - Find objects by semantic type
- `worldbuilder_query_objects_in_bounds` - Spatial bounding box queries
- `worldbuilder_query_objects_near_point` - Proximity-based searches
- `worldbuilder_calculate_bounds` - Get bounding boxes for object groups

#### Utilities
- `worldbuilder_scene_status` - Health and statistics
- `worldbuilder_get_metrics` - Performance metrics
- `worldbuilder_metrics_prometheus` - Prometheus metrics

Note: Metrics endpoints are available as HTTP GET `/metrics` and `/metrics.prom`.

### WorldViewer Tools

#### Camera Control
- `worldviewer_set_camera_position` - Position camera in 3D space
- `worldviewer_orbit_camera` - Orbital positioning around points
- `worldviewer_frame_object` - Automatically frame scene objects

#### Cinematic Features
- `worldviewer_smooth_move` - Animated camera movements with easing
- `worldviewer_stop_movement` - Interrupt active movements
- `worldviewer_movement_status` - Check movement progress

#### Status
- `worldviewer_get_camera_status` - Current camera position/orientation
- `worldviewer_extension_health` - Extension health status
- `worldviewer_get_metrics` - Performance metrics
- `worldviewer_metrics_prometheus` - Prometheus metrics

### WorldSurveyor Tools

#### Waypoint Management
- `worldsurveyor_create_waypoint` - Create spatial waypoints
- `worldsurveyor_list_waypoints` - Query waypoints with filtering
- `worldsurveyor_update_waypoint` - Modify waypoint properties
- `worldsurveyor_remove_waypoint` - Delete specific waypoints

#### Group Organization
- `worldsurveyor_create_group` - Create waypoint groups  
- `worldsurveyor_list_groups` - Query group structure
- `worldsurveyor_add_waypoint_to_groups` - Organize waypoints
- `worldsurveyor_get_group_hierarchy` - Complete group structure

#### Visibility Control
- `worldsurveyor_set_markers_visible` - Show/hide all markers
- `worldsurveyor_set_individual_marker_visible` - Control individual markers
- `worldsurveyor_set_selective_markers_visible` - Show only specific markers

#### Navigation & Data
- `worldsurveyor_goto_waypoint` - Navigate to waypoints
- `worldsurveyor_export_waypoints` - Backup waypoint data
- `worldsurveyor_import_waypoints` - Restore waypoint collections
 
#### Monitoring
- `worldsurveyor_get_metrics` - Performance metrics
- `worldsurveyor_metrics_prometheus` - Prometheus metrics

### WorldRecorder Tools

#### Capture Operations
- `worldrecorder_capture_frame` - Take screenshots
- `worldrecorder_start_recording` - Begin video recording (alias of /video/start)
- `worldrecorder_stop_recording` - End video recording (alias of /video/stop)
  (aliases also available as `worldrecorder_start_video` and `worldrecorder_stop_video`)

#### Status & Control  
- `worldrecorder_get_status` - Recording status and statistics
- `worldrecorder_health` - Extension health check
- `worldrecorder_get_metrics` - Performance metrics
- `worldrecorder_metrics_prometheus` - Prometheus metrics

## Usage Examples

### Scene Creation with WorldBuilder

```python
# AI agent using MCP tools to create a scene
import mcp

# Connect to WorldBuilder MCP server
wb = mcp.Client("worldbuilder")

# Create ground plane
await wb.call_tool("worldbuilder_add_element", {
    "element_type": "cube",
    "name": "ground",
    "position": [0, 0, -0.5],
    "scale": [20, 20, 1],
    "color": [0.5, 0.5, 0.5]
})

# Create building batch
building_elements = [
    {
        "element_type": "cube", 
        "name": "foundation",
        "position": [0, 0, 1],
        "scale": [10, 10, 2]
    },
    {
        "element_type": "cube",
        "name": "walls", 
        "position": [0, 0, 4],
        "scale": [10, 10, 6]
    },
    {
        "element_type": "cube",
        "name": "roof",
        "position": [0, 0, 8], 
        "scale": [12, 12, 1]
    }
]

await wb.call_tool("worldbuilder_create_batch", {
    "batch_name": "simple_building",
    "elements": building_elements
})
```

### Camera Control with WorldViewer

```python
# Position camera and create cinematic movement
wv = mcp.Client("worldviewer")

# Set initial camera position
await wv.call_tool("worldviewer_set_camera_position", {
    "position": [15, 15, 10],
    "target": [0, 0, 0]
})

# Create smooth orbital movement
await wv.call_tool("worldviewer_smooth_move", {
    "start_position": [15, 15, 10],
    "end_position": [-15, 15, 10],
    "start_target": [0, 0, 0],
    "end_target": [0, 0, 0],
    "duration": 5.0,
    "easing_type": "ease_in_out"
})
```

### Waypoint Navigation with WorldSurveyor

```python
# Create and organize waypoints
ws = mcp.Client("worldsurveyor")

# Create waypoint group
await ws.call_tool("worldsurveyor_create_group", {
    "name": "inspection_points",
    "description": "Building inspection waypoints"
})

# Create waypoints for building inspection
inspection_points = [
    {"name": "front_entrance", "position": [12, 0, 2]},
    {"name": "side_wall", "position": [0, 12, 2]}, 
    {"name": "roof_access", "position": [0, 0, 10]},
    {"name": "rear_exit", "position": [-12, 0, 2]}
]

for point in inspection_points:
    await ws.call_tool("worldsurveyor_create_waypoint", {
        "position": point["position"],
        "name": point["name"],
        "waypoint_type": "point_of_interest"
    })
```

### Recording with WorldRecorder

```python
# Document the scene with recordings
wr = mcp.Client("worldrecorder")

# Take high-quality screenshots from each waypoint
waypoints = await ws.call_tool("worldsurveyor_list_waypoints", {})

for waypoint in waypoints["waypoints"]:
    # Navigate to waypoint
    await ws.call_tool("worldsurveyor_goto_waypoint", {
        "waypoint_id": waypoint["id"]
    })
    
    # Capture screenshot
    await wr.call_tool("worldrecorder_capture_frame", {
        "output_path": f"/tmp/inspection_{waypoint['name']}.png",
        "width": 1920,
        "height": 1080
    })

# Record a complete walkthrough
await wr.call_tool("worldrecorder_start_recording", {
    "output": "/tmp/building_walkthrough.mp4",
    "fps": 30,
    "crf": 20,
    "max_duration_sec": 120
})

# Move through all waypoints during recording
for waypoint in waypoints["waypoints"]:
    await ws.call_tool("worldsurveyor_goto_waypoint", {
        "waypoint_id": waypoint["id"]
    })
    await asyncio.sleep(3)  # Pause at each location

await wr.call_tool("worldrecorder_stop_recording")
```

## AI Agent Integration Patterns

### Multi-Extension Workflows

```python
async def create_documented_scene():
    """AI agent workflow combining multiple extensions."""
    
    # 1. Create scene with WorldBuilder
    await wb.call_tool("worldbuilder_add_element", {
        "element_type": "sphere",
        "name": "target_object", 
        "position": [0, 0, 2],
        "color": [1, 0, 0]
    })
    
    # 2. Position camera with WorldViewer
    await wv.call_tool("worldviewer_frame_object", {
        "object_path": "/World/target_object",
        "distance": 5
    })
    
    # 3. Mark location with WorldSurveyor  
    await ws.call_tool("worldsurveyor_create_waypoint", {
        "position": [0, 0, 2],
        "name": "target_location",
        "waypoint_type": "object_anchor"
    })
    
    # 4. Document with WorldRecorder
    await wr.call_tool("worldrecorder_capture_frame", {
        "output_path": "/tmp/target_documentation.png"
    })
```

### Error Handling in MCP Tools

```python
async def safe_scene_creation():
    """Demonstrate error handling in MCP workflows."""
    
    try:
        # Attempt to create element
        result = await wb.call_tool("worldbuilder_add_element", {
            "element_type": "cube",
            "name": "test_cube",
            "position": [0, 0, 1]
        })
        
        if not result["success"]:
            print(f"Creation failed: {result['error']}")
            return
            
    except Exception as e:
        print(f"MCP call failed: {e}")
        return
    
    # Verify element was created
    scene = await wb.call_tool("worldbuilder_get_scene")
    elements = [elem["name"] for elem in scene["elements"]]
    
    if "test_cube" in elements:
        print("Element created successfully")
    else:
        print("Element creation verification failed")
```

## Advanced MCP Features

### Resource Access

Some MCP servers provide resources for AI agents:

```python
# Access WorldBuilder scene templates
resources = await wb.list_resources()
template_resource = await wb.read_resource("scene_templates/basic_room.json")

# Use template to create scene
template_data = json.loads(template_resource.text)
await wb.call_tool("worldbuilder_create_batch", template_data)
```

### Custom Tool Parameters

MCP tools support rich parameter validation:

```python
# WorldBuilder validates element types
await wb.call_tool("worldbuilder_add_element", {
    "element_type": "invalid_type",  # Will return validation error
    "name": "test",
    "position": [0, 0, 0]
})

# WorldViewer validates camera bounds
await wv.call_tool("worldviewer_set_camera_position", {
    "position": [1000, 1000, 1000]  # Outside configured bounds
})
```

### Batch Operations via MCP

```python
# Efficient batch scene creation
batch_request = {
    "batch_name": "procedural_city",
    "elements": []
}

# Generate 100 buildings procedurally
for i in range(10):
    for j in range(10):
        batch_request["elements"].append({
            "element_type": "cube",
            "name": f"building_{i}_{j}",
            "position": [i * 20, j * 20, 5],
            "scale": [8, 8, random.uniform(5, 15)],
            "color": [random.random(), random.random(), random.random()]
        })

# Create entire city in one MCP call
await wb.call_tool("worldbuilder_create_batch", batch_request)
```

## MCP Server Development

### Custom MCP Server Extension

```python
# Example custom MCP server for specialized workflows
import mcp.server
from mcp.server.models import Tool

@app.list_tools()
async def handle_list_tools() -> list[Tool]:
    return [
        Tool(
            name="custom_workflow_builder",
            description="Create custom AI workflow in Isaac Sim",
            inputSchema={
                "type": "object",
                "properties": {
                    "workflow_type": {"type": "string"},
                    "scene_complexity": {"type": "string", "enum": ["simple", "moderate", "complex"]},
                    "output_format": {"type": "string", "enum": ["images", "video", "data"]}
                },
                "required": ["workflow_type"]
            }
        )
    ]

@app.call_tool()
async def handle_call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    if name == "custom_workflow_builder":
        # Orchestrate multiple extensions for custom workflow
        return await build_custom_workflow(arguments)
```

## Troubleshooting MCP Integration

### Common Issues

1. **MCP Server Not Starting**
   - Check Python path and dependencies
   - Verify Isaac Sim extensions are running
   - Check base URL configuration

2. **Tool Calls Failing**
   - Verify extension HTTP APIs are responding
   - Check MCP server logs for detailed errors
   - Test direct HTTP API calls

3. **Authentication Issues**  
   - Ensure auth tokens are configured if auth_enabled=true
   - Check CORS settings for cross-origin requests

### Debug Mode

Enable debug logging in MCP servers:

```bash
export DEBUG=true
export WORLDBUILDER_BASE_URL=http://localhost:8899
python mcp_agent_worldbuilder.py
```

### Health Checks

```python
# Test MCP server connectivity
async def test_mcp_health():
    try:
        health = await wb.call_tool("worldbuilder_scene_status")
        print(f"WorldBuilder MCP: {'✓' if health['success'] else '✗'}")
    except Exception as e:
        print(f"WorldBuilder MCP: ✗ ({e})")
```
