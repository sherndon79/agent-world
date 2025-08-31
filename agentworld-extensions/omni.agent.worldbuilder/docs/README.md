# Agent WorldBuilder Extension

Comprehensive USD scene management with spatial intelligence for Isaac Sim.

## Overview

Agent WorldBuilder provides advanced scene construction capabilities with spatial queries, batch operations, and intelligent object management through a thread-safe HTTP API on port 8899.

## Features

- **Object Creation** - Primitives (cube, sphere, cylinder, cone) and USD assets
- **Batch Operations** - Efficient multi-object creation and management
- **Spatial Intelligence** - Semantic queries and proximity detection
- **USD Asset Management** - Reference-based asset placement and transformation
- **Thread-Safe Operations** - Queue-based architecture for USD safety
- **Spatial Calculations** - Ground detection, bounds calculation, object alignment

## API Endpoints

### Object Creation
- `POST /add_element` - Create primitive objects
- `POST /create_batch` - Create object batches
- `POST /place_asset` - Place USD assets via reference
- `POST /transform_asset` - Transform existing assets

### Scene Management
- `GET /scene_status` - Scene health and statistics
- `GET /get_scene` - Complete scene structure (recursive)
- `GET /list_elements` - Flat element listing
- `POST /remove_element` - Remove scene elements
- `POST /clear_batch` - Clear object batches

### Spatial Queries
- `GET /query/objects_by_type` - Query by semantic type
- `GET /query/objects_in_bounds` - Query within spatial bounds
- `GET /query/objects_near_point` - Proximity-based queries

### Transform Operations
- `GET /transform/calculate_bounds` - Calculate bounding boxes
- `GET /transform/find_ground_level` - Ground level detection
- `GET /transform/align_objects` - Object alignment

### System
- `GET /health` - Extension health check
- `GET /request_status` - Check operation status
- `GET /metrics.prom` - Prometheus metrics

## Usage Examples

### Create Object Batch
```bash
curl -X POST http://localhost:8899/create_batch \
  -H "Content-Type: application/json" \
  -d '{
    "batch_name": "furniture_set",
    "elements": [
      {
        "element_type": "cube",
        "name": "table",
        "position": [0, 1, 0],
        "scale": [2, 0.1, 1]
      }
    ]
  }'
```

### Spatial Query
```bash
curl "http://localhost:8899/query/objects_near_point?point=[0,0,0]&radius=5.0"
```

### Place USD Asset
```bash
curl -X POST http://localhost:8899/place_asset \
  -H "Content-Type: application/json" \
  -d '{
    "name": "my_asset",
    "asset_path": "/path/to/asset.usd",
    "position": [0, 0, 0],
    "scale": [1, 1, 1]
  }'
```

## MCP Integration

This extension provides MCP (Model Context Protocol) integration through:
- `mcp__worldbuilder-server__isaac_add_element`
- `mcp__worldbuilder-server__isaac_create_batch`
- `mcp__worldbuilder-server__isaac_query_objects_by_type`
- And all other API endpoints as MCP tools

## Architecture

- **Queue-Based Processing** - Thread-safe USD operations
- **Spatial Intelligence Engine** - Advanced object queries
- **Batch Management System** - Efficient multi-object operations
- **USD Reference System** - Asset placement and management

## Installation

1. Enable extension in Isaac Sim Extension Manager
2. Extension starts HTTP API automatically on port 8899
3. Verify with: `curl http://localhost:8899/health`

## Requirements

- Isaac Sim 5.0+
- omni.usd
- omni.ui

## Thread Safety

All USD operations are queued and executed on the main thread to prevent threading issues, following the Agent World architecture patterns.