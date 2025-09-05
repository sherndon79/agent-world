# WorldViewer Extension

Control camera positioning and create cinematic movements in Isaac Sim. WorldViewer enables AI agents to navigate 3D scenes with smooth camera transitions, orbital controls, and automated framing.

![WorldViewer Isaac Menu](../resources/images/Agent_WorldViewer_Isaac_Menu.png)
*WorldViewer extension interface in Isaac Sim showing camera control tools and cinematic movement options.*

## For New Users

**WorldViewer lets AI agents control the Isaac Sim camera programmatically.** Instead of manually navigating with mouse controls, you can:

- **Ask Claude Code**: "Move the camera to show the scene from above" or "Create a smooth flythrough"
- **Position precisely**: Set exact camera positions and targets through natural language  
- **Create cinematics**: Generate smooth camera movements for presentations or analysis
- **🎬 Build shot sequences**: Create complex cinematography with mixed auto/manual execution modes
- **Professional workflows**: Use media player controls (play/pause/stop) for sophisticated camera sequences

**You don't need to use the HTTP API directly** - the MCP integration handles all the technical details automatically.

## Features

### Camera Positioning
- **Precise Control**: Set exact camera position and target
- **Look-at Targeting**: Point camera at specific coordinates
- **Up Vector Control**: Define camera orientation
- **Bounds Checking**: Safe camera positioning within scene limits

### Cinematic Movements
- **Smooth Transitions**: Animated camera movements with easing
- **Multiple Easing Types**: Linear, ease-in-out, bounce, elastic
- **Configurable Duration**: Control movement timing
- **Movement Interruption**: Stop movements in progress

### Object Framing
- **Auto-framing**: Automatically position camera to frame objects
- **Distance Calculation**: Optimal viewing distance based on object size  
- **Multi-object Framing**: Frame multiple objects simultaneously

### Orbital Controls
- **Spherical Coordinates**: Position camera using azimuth and elevation
- **Center Point Orbiting**: Orbit around any 3D coordinate
- **Distance Control**: Maintain specific distance from center

### 🎬 **Queue Control System** *(Production Ready)*
- **Sequential Cinematography**: Chain multiple camera movements in perfect sequence
- **Mixed Execution Modes**: Combine automatic and manual-triggered movements
- **Media Player Controls**: Play, pause, stop, and resume complex shot sequences
- **Speed-Based Timing**: Intelligent duration calculation based on movement speed
- **Advanced State Management**: Sophisticated queue states (idle, running, paused, pending)
- **Target Preservation**: Smooth camera target interpolation during pause/resume
- **Complex Workflows**: Support for intricate patterns (Manual→Auto→Manual→Auto)
- **Real-time Status**: Live queue monitoring with progress tracking and timing
- **Camera Target Display**: Visual debugging in Isaac Sim interface

**Perfect for:**
- **AI-Generated Cinematography**: Let Claude Code create and control complex shot sequences
- **Automated Presentations**: Script sophisticated camera movements for demos
- **Multi-Shot Planning**: Pre-plan entire camera sequences with mixed timing control
- **Production Workflows**: Professional-grade cinematography for Isaac Sim scenes

## API Endpoints (canonical)

Note: canonical paths include the `/camera/` prefix. Backward‑compatible aliases may exist.

### Camera Control

**POST** `/camera/set_position`
```json
{
  "position": [5, 5, 5],
  "target": [0, 0, 0],
  "up_vector": [0, 0, 1]
}
```

**POST** `/camera/orbit`
```json
{
  "center": [0, 0, 1],
  "distance": 10,
  "elevation": 30,
  "azimuth": 45
}
```

### Object Framing

**POST** `/camera/frame_object`
```json
{
  "object_path": "/World/my_cube",
  "distance": 5.0
}
```

### Cinematic Movements

**POST** `/camera/smooth_move`
```json
{
  "start_position": [0, 0, 5],
  "end_position": [10, 0, 5],
  "start_target": [0, 0, 0],
  "end_target": [10, 0, 0],
  "speed": 10.0,
  "duration": 3.0,
  "execution_mode": "auto",
  "easing_type": "ease_in_out"
}
```

**New Parameters:**
- `speed` - Movement speed in units/second (auto-calculates duration)
- `execution_mode` - `"auto"` (immediate) or `"manual"` (wait for play command) 
- `duration` - Manual override (optional when using speed)

**POST** `/camera/stop_movement` (alias: `/movement/stop`)
```json
{
  "movement_id": "movement_12345"
}
```

### Status and Control

**GET** `/camera/status` - Current camera position and orientation
**GET** `/camera/movement_status?movement_id=...` - Check movement progress
**GET** `/health` - Extension health status  
**GET** `/metrics` - Performance metrics

## Configuration

### Basic Settings
```json
{
  "server_port": 8900,
  "debug_mode": false,
  "enable_cinematic_mode": true,
  "smooth_movement_enabled": true
}
```

### Movement Controls  
```json
{
  "default_movement_duration": 3.0,
  "max_movement_duration": 60.0,
  "camera_bounds_checking": true
}
```

### 🎬 **Queue Control** *(New)*

**GET** `/camera/queue/status`
```json
{
  "success": true,
  "queue_state": "pending",
  "active_count": 0,
  "queued_count": 3,
  "total_duration": 15.0,
  "estimated_remaining": 15.0,
  "queued_shots": [
    {
      "movement_id": "smooth_move_123",
      "operation": "smooth_move", 
      "execution_mode": "manual",
      "duration": 5.0
    }
  ]
}
```

**POST** `/camera/queue/play`
```json
{
  "success": true,
  "message": "Queue resumed/started",
  "queue_state": "running"
}
```

**POST** `/camera/queue/pause`  
```json
{
  "success": true,
  "message": "Queue paused. Camera movement stopped.",
  "queue_state": "paused"
}
```

**POST** `/camera/queue/stop`
```json
{
  "success": true,
  "message": "Queue stopped and cleared",
  "stopped_movements": 2
}
```

### Camera Bounds
```json
{
  "camera_min_bounds": [-50, -50, -10],
  "camera_max_bounds": [50, 50, 20],
  "min_target_distance": 0.1,
  "max_target_distance": 100.0
}
```

## Usage Examples

### Basic Camera Positioning
```python
import requests

# Position camera to look at origin
requests.post('http://localhost:8900/camera/set_position', json={
    'position': [10, 10, 10],
    'target': [0, 0, 0]
})

# Get current camera status
status = requests.get('http://localhost:8900/get_camera_status')
print(f"Camera at: {status.json()['position']}")
```

### Orbital Camera Movement
```python
# Orbit around an object at different angles
for angle in [0, 90, 180, 270]:
    requests.post('http://localhost:8900/camera/orbit', json={
        'center': [0, 0, 1],
        'distance': 8,
        'elevation': 20,
        'azimuth': angle
    })
    
    # Take screenshot at each position
    requests.post('http://localhost:8892/capture_frame', 
                  json={'output_path': f'/tmp/view_{angle}.png'})
```

### Cinematic Movements
```python
# Create smooth camera movement
movement = requests.post('http://localhost:8900/camera/smooth_move', json={
    'start_position': [0, -10, 5],
    'end_position': [0, 10, 5],
    'start_target': [0, 0, 0],
    'end_target': [0, 0, 0],
    'duration': 5.0,
    'easing_type': 'ease_in_out'
})

movement_id = movement.json()['movement_id']

# Monitor movement progress
import time
while True:
status = requests.get('http://localhost:8900/camera/movement_status', params={'movement_id': movement_id})
    if status.json()['completed']:
        break
    print(f"Progress: {status.json()['progress']}%")
    time.sleep(0.5)
```

### 🎬 **Queue Control Cinematography** *(New)*
```python
# Create sophisticated shot sequences with mixed execution modes
import requests

# Shot 1: Manual trigger - establisher
requests.post('http://localhost:8900/camera/smooth_move', json={
    'start_position': [50, 50, 30],
    'end_position': [0, -40, 15], 
    'start_target': [0, 0, 5],
    'end_target': [0, 0, 5],
    'speed': 8.0,
    'execution_mode': 'manual'  # Wait for play command
})

# Shot 2: Auto execution - detail shot
requests.post('http://localhost:8900/camera/smooth_move', json={
    'start_position': [0, -40, 15],
    'end_position': [15, -25, 8],
    'start_target': [0, 0, 5], 
    'end_target': [10, -15, 5],
    'speed': 12.0,
    'execution_mode': 'auto'  # Automatic execution
})

# Shot 3: Manual trigger - final reveal
requests.post('http://localhost:8900/camera/smooth_move', json={
    'start_position': [15, -25, 8],
    'end_position': [25, 25, 20],
    'start_target': [10, -15, 5],
    'end_target': [0, 0, 5],
    'speed': 6.0,
    'execution_mode': 'manual'  # Wait for play command
})

# Check queue status
status = requests.get('http://localhost:8900/camera/queue/status')
print(f"Queue state: {status.json()['queue_state']}")
print(f"Total shots: {status.json()['queued_count']}")

# Start the sequence (triggers first manual shot)
requests.post('http://localhost:8900/camera/queue/play')

# Auto shot will execute automatically after shot 1 completes
# Final shot will wait for another play command

# Later: trigger final shot
requests.post('http://localhost:8900/camera/queue/play')

# Advanced: Pause and resume with target preservation
requests.post('http://localhost:8900/camera/queue/pause')  # Preserves camera targets
requests.post('http://localhost:8900/camera/queue/play')   # Resumes smoothly
```

### Object Framing
```python
# Automatically frame different objects
objects = ['/World/cube1', '/World/sphere1', '/World/cylinder1']

for obj in objects:
    # Frame the object
    requests.post('http://localhost:8900/camera/frame_object', json={
        'object_path': obj,
        'distance': 3.0
    })
    
    # Capture the framed view
    requests.post('http://localhost:8892/capture_frame',
                  json={'output_path': f'/tmp/{obj.split("/")[-1]}.png'})
```

## Easing Types

WorldViewer supports multiple easing functions for smooth movements:

- **linear**: Constant speed movement
- **ease_in**: Slow start, fast finish  
- **ease_out**: Fast start, slow finish
- **ease_in_out**: Slow start and finish, fast middle
- **bounce**: Bouncing effect at the end
- **elastic**: Elastic spring effect

## MCP Integration

WorldViewer provides MCP tools for AI agents:

- `worldviewer_set_camera_position` - Direct camera positioning
- `worldviewer_orbit_camera` - Orbital positioning  
- `worldviewer_frame_object` - Automatic object framing
- `worldviewer_smooth_move` - Cinematic movements
- `worldviewer_get_camera_status` - Status monitoring

## Advanced Features

### Camera Path Recording
```python
# Record a series of camera positions
positions = []
for i in range(0, 360, 30):
    pos = requests.post('http://localhost:8900/camera/orbit', json={
        'center': [0, 0, 1],
        'distance': 5,
        'elevation': 0, 
        'azimuth': i
    })
    positions.append(pos.json()['position'])

# Use positions for smooth interpolated movement
```

### Multi-object Framing
```python
# Get transforms of multiple objects
objects = ['/World/obj1', '/World/obj2', '/World/obj3']
transforms = []

for obj in objects:
    # Get object transform (requires WorldBuilder API)
    transform = requests.get(f'http://localhost:8899/get_asset_transform', 
                           json={'usd_path': obj})
    transforms.append(transform.json())

# Calculate center point and frame all objects
center = calculate_center(transforms)  # Custom function
requests.post('http://localhost:8900/camera/set_position', json={
    'position': [center[0] + 10, center[1] + 10, center[2] + 5],
    'target': center
})
```

## Error Handling

WorldViewer provides detailed error responses:

```json
{
  "success": false,
  "error": "Camera position out of bounds",
  "bounds": {
    "min": [-50, -50, -10],
    "max": [50, 50, 20]
  },
  "requested": [100, 0, 0]
}
```

## Performance Notes

- **Smooth Movements**: Limited to one active movement at a time
- **Bounds Checking**: Validation prevents invalid camera positions
- **Thread Safety**: Camera operations are properly synchronized with Isaac Sim
- **Real-time Updates**: Camera changes immediately update the viewport

## Troubleshooting

### Common Issues

1. **Camera Not Moving**: Check if another movement is in progress
2. **Out of Bounds**: Verify camera position is within configured bounds
3. **Object Not Found**: Ensure object exists in scene before framing
4. **Jerky Movement**: Use appropriate easing types for smooth motion

### Debug Mode

Enable debug logging with `debug_mode: true` for detailed movement tracking and camera state information.
