# Agent WorldViewer Extension

Camera control and viewport management extension for Isaac Sim with HTTP API for AI-powered camera positioning.

## Overview

Agent WorldViewer provides thread-safe camera control capabilities for Isaac Sim, enabling AI agents and external applications to position and control the viewport camera through a simple HTTP API.

## Features

- **Thread-Safe Camera Control** - Queue-based operations prevent USD threading issues
- **HTTP API** - RESTful endpoints for external integration (port 8900)
- **Smooth Cinematic Movement** - Smooth camera transitions with easing
- **Orbital Positioning** - Position camera in spherical coordinates around objects
- **Object Framing** - Automatically frame objects in the viewport
- **Asset Transform Queries** - Get position/rotation/scale information for scene objects

## API Endpoints

### Camera Control

- `POST /camera/set_position` - Set camera position and target
- `POST /camera/frame_object` - Frame an object in viewport
- `POST /camera/orbit` - Position camera in orbital coordinates
- `GET /camera/status` - Get current camera status

### Cinematic Movement

- `POST /camera/smooth_move` - Smooth camera movement between positions
- `POST /camera/stop_movement` - Stop active cinematic movement
- `GET /camera/movement_status` - Check movement status

### Asset Information

- `GET /asset/transform` - Get transform info for scene objects

### System

- `GET /health` - Extension health check
- `GET /metrics.prom` - Prometheus metrics

## Usage Examples

### Set Camera Position
```bash
curl -X POST http://localhost:8900/camera/set_position \
  -H "Content-Type: application/json" \
  -d '{
    "position": [10, 5, 10],
    "target": [0, 0, 0]
  }'
```

### Frame Object
```bash
curl -X POST http://localhost:8900/camera/frame_object \
  -H "Content-Type: application/json" \
  -d '{
    "object_path": "/World/my_cube",
    "distance": 5.0
  }'
```

### Orbital Camera Position
```bash
curl -X POST http://localhost:8900/camera/orbit \
  -H "Content-Type: application/json" \
  -d '{
    "center": [0, 0, 0],
    "distance": 10,
    "elevation": 30,
    "azimuth": 45
  }'
```

### Smooth Camera Movement
```bash
curl -X POST http://localhost:8900/camera/smooth_move \
  -H "Content-Type: application/json" \
  -d '{
    "start_position": [0, 5, 10],
    "end_position": [10, 8, 5],
    "duration": 3.0,
    "easing_type": "ease_in_out"
  }'
```

### Get Asset Transform
```bash
curl -X GET "http://localhost:8900/asset/transform?usd_path=/World/my_cube"
```

## Installation

1. Copy the extension to Isaac Sim's extensions directory
2. Enable the extension in Isaac Sim Extension Manager
3. The HTTP API will start automatically on port 8900

## MCP Integration

This extension provides MCP (Model Context Protocol) integration through:
- `mcp__worldviewer-server__worldviewer_set_camera_position`
- `mcp__worldviewer-server__worldviewer_frame_object`  
- `mcp__worldviewer-server__worldviewer_orbit_camera`
- `mcp__worldviewer-server__worldviewer_smooth_move`
- And all other API endpoints as MCP tools

## Architecture

- **HTTP API Server** - RESTful endpoints on port 8900
- **Camera Control System** - Direct viewport camera manipulation
- **Cinematic Movement Engine** - Smooth transitions with easing functions
- **Asset Query System** - Transform information retrieval
- **Thread-Safe Operations** - Main thread processing for USD safety

## Thread Safety

All camera operations are queued and processed on the main thread to prevent USD threading issues, similar to the Agent WorldBuilder extension architecture.

## Requirements

- Isaac Sim 5.0+
- omni.usd
- omni.ui  
- omni.kit.viewport.utility

## Relationship to WorldSurveyor

WorldViewer handles camera movement and viewport control, while WorldSurveyor waypoints serve as camera presets and spatial planning. Use WorldSurveyor to create and manage camera position waypoints, then use WorldViewer to smoothly animate between them.