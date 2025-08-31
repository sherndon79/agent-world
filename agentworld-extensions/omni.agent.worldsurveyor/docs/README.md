# Agent WorldSurveyor Extension

Spatial waypoint management with hierarchical organization for Isaac Sim.

## Overview

Agent WorldSurveyor provides comprehensive waypoint and spatial planning capabilities with visual markers, hierarchical groups, and import/export functionality for AI-powered scene navigation through HTTP API on port 8891.

## Web Portal

**User Waypoint Management** is available through the WorldSurveyor Waypoint Manager web portal at **http://localhost:8891** - providing an intuitive interface for creating, organizing, and managing spatial waypoints with visual feedback.

## Features

- **Web-Based Waypoint Manager** - Interactive portal for user-friendly waypoint management
- **Toolbar Widget** - Isaac Sim toolbar integration with scroll-based waypoint type selection
- **Smart Placement System** - Exact positioning and targeting-based placement depending on waypoint type
- **Waypoint Management** - Create, organize, and manage spatial waypoints
- **Hierarchical Groups** - Organize waypoints into nested group structures
- **Visual Markers** - 3D scene markers with individual visibility control
- **Import/Export** - Data persistence and transfer capabilities
- **Spatial Planning** - Navigation and scene planning support
- **Thread-Safe Operations** - Queue-based architecture for USD safety

## API Endpoints

### Waypoint Management
- `POST /create_waypoint` - Create spatial waypoints
- `GET /list_waypoints` - List all waypoints
- `POST /remove_waypoint` - Remove specific waypoint
- `POST /clear_all_waypoints` - Clear all waypoints

### Group Management
- `POST /create_group` - Create waypoint groups
- `GET /list_groups` - List all groups
- `GET /get_group` - Get specific group details
- `GET /get_group_hierarchy` - Get complete hierarchy
- `POST /remove_group` - Remove group

### Group Operations
- `POST /add_waypoint_to_groups` - Add waypoint to groups
- `POST /remove_waypoint_from_groups` - Remove from groups
- `GET /get_waypoint_groups` - Get waypoint's groups
- `GET /get_group_waypoints` - Get group's waypoints

### Visualization
- `POST /set_markers_visible` - Global marker visibility
- `POST /set_individual_marker_visible` - Individual marker control

### Data Management
- `POST /export_waypoints` - Export waypoint data
- `POST /import_waypoints` - Import waypoint data

### System
- `GET /health` - Extension health check
- `GET /metrics.prom` - Prometheus metrics

## Usage Examples

### Create Waypoint with Groups
```bash
curl -X POST http://localhost:8891/create_waypoint \
  -H "Content-Type: application/json" \
  -d '{
    "position": [5, 2, 3],
    "waypoint_type": "camera_position",
    "name": "Overview Shot",
    "target": [0, 0, 0]
  }'
```

### Create Hierarchical Groups
```bash
curl -X POST http://localhost:8891/create_group \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Camera Positions",
    "description": "All camera waypoints",
    "color": "#FF5733"
  }'
```

### Export All Waypoints
```bash
curl -X POST http://localhost:8891/export_waypoints \
  -H "Content-Type: application/json" \
  -d '{"include_groups": true}'
```

### Control Marker Visibility
```bash
curl -X POST http://localhost:8891/set_markers_visible \
  -H "Content-Type: application/json" \
  -d '{"visible": true}'
```

## Waypoint Types

- **point_of_interest** - General points of interest (targeting-based)
- **camera_position** - Camera viewpoint locations (exact placement with position and target)
- **object_anchor** - Object placement markers (targeting-based)
- **selection_mark** - Selection indicators (targeting-based)
- **lighting_position** - Lighting setup points (exact placement with position and direction)
- **audio_source** - Audio placement markers (targeting-based)
- **spawn_point** - Object spawn locations (targeting-based)

## UI Integration

### Toolbar Widget
- Integrated into Isaac Sim's main toolbar
- Click the camera icon to enable waypoint placement mode
- Hover over the camera icon and scroll to select waypoint type
- Click-to-place functionality in viewport
- Real-time visual feedback during placement

### Placement Modes
- **Exact Placement** - Uses exact camera position and target/direction (camera positions, directional lighting)
- **Targeting-Based** - Positioned at specified viewing distance using crosshairs (POI, anchors, markers, audio, spawn points)

## MCP Integration

This extension provides MCP (Model Context Protocol) integration through:
- `mcp__worldsurveyor-server__worldsurveyor_create_waypoint`
- `mcp__worldsurveyor-server__worldsurveyor_create_group`
- `mcp__worldsurveyor-server__worldsurveyor_list_waypoints`
- And all other API endpoints as MCP tools

## Architecture

- **Hierarchical Group System** - Nested waypoint organization
- **Visual Marker Engine** - Real-time 3D scene markers using debug draw
- **Data Persistence Layer** - SQLite database with import/export
- **Spatial Planning Support** - Navigation and scene planning capabilities
- **Thread-Safe Operations** - Main thread processing for USD safety

## Installation

1. Enable extension in Isaac Sim Extension Manager
2. Extension starts HTTP API automatically on port 8891
3. Verify with: `curl http://localhost:8891/health`

## Requirements

- Isaac Sim 5.0+
- omni.usd
- omni.ui
- omni.kit.viewport.utility
- omni.kit.widget.toolbar
- isaacsim.util.debug_draw

## Thread Safety

All operations are processed on the main thread to ensure USD and UI thread safety, following Agent World architecture patterns.