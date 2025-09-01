# WorldSurveyor Extension

Mark and organize spatial locations in Isaac Sim with waypoints and groups. WorldSurveyor enables AI agents to create persistent spatial references for navigation, annotation, and scene organization.

## Features

### Waypoint Management
- **3D Markers**: Create waypoints at any coordinate in space
- **Multiple Types**: Point of interest, camera positions, lighting, audio sources
- **Visual Indicators**: Customizable markers with show/hide controls
- **Persistent Storage**: Waypoints persist across Isaac Sim sessions

### Hierarchical Organization
- **Group System**: Organize waypoints into logical collections  
- **Nested Groups**: Support for hierarchical group structures
- **Bulk Operations**: Apply actions to entire groups
- **Flexible Membership**: Waypoints can belong to multiple groups

### Spatial Intelligence
- **Navigation Aid**: Mark important locations for pathfinding
- **Scene Annotation**: Add contextual information to 3D coordinates
- **Measurement References**: Create reference points for spatial analysis

### Data Persistence  
- **SQLite Database**: Reliable local storage
- **Import/Export**: Backup and transfer waypoint collections
- **Session Continuity**: Waypoints automatically restored on extension load

## In-Sim Status Panel

- Status: Shows server running state and URL.
- Activity: Displays API requests and errors counters.
- Open Manager: One-click button opens the Waypoint Manager web UI.

Open the manager from Isaac Sim or directly via http://localhost:8891/waypoint_manager.html

## API Endpoints

Note: Modern structured endpoints are preferred (e.g., `/waypoints/create`). Backward-compatible flat endpoints may also exist.

### Waypoint Operations

**POST** `/waypoints/create`
```json
{
  "position": [10, 5, 2],
  "waypoint_type": "point_of_interest",
  "name": "observation_deck",
  "target": [0, 0, 0]
}
```

**GET** `/waypoints/list` - Get all waypoints
**GET** `/list_waypoints?waypoint_type=camera_position` - Filter by type

**POST** `/waypoints/update`
```json
{
  "waypoint_id": "wp_12345",
  "name": "updated_name",
  "notes": "Additional information",
  "metadata": {"priority": "high"}
}
```

**POST** `/waypoints/remove`
```json
{
  "waypoint_id": "wp_12345"
}
```

### Group Management

**POST** `/groups/create`
```json
{
  "name": "camera_positions",
  "description": "Key camera viewpoints for the scene",
  "color": "#4A90E2",
  "parent_group_id": "group_456"
}
```

**GET** `/groups/list` - Get all groups
**GET** `/groups/get` - Get specific group details
**GET** `/groups/hierarchy` - Get complete group structure

**POST** `/groups/add_waypoint`
```json
{
  "waypoint_id": "wp_12345", 
  "group_ids": ["group_456", "group_789"]
}
```

### Visibility Control

**POST** `/markers/visible`
```json
{
  "visible": true
}
```

**POST** `/markers/individual`
```json
{
  "waypoint_id": "wp_12345",
  "visible": false
}
```

**POST** `/markers/selective`
```json
{
  "visible_waypoint_ids": ["wp_123", "wp_456", "wp_789"]
}
```

### Navigation

**POST** `/waypoints/goto`
```json
{
  "waypoint_id": "wp_12345"
}
```

### Data Management

**GET** `/waypoints/export` - Export all waypoints and groups
**POST** `/waypoints/import` - Import waypoint collections
**POST** `/waypoints/clear` - Remove all waypoints (requires confirmation)

## Configuration

### Basic Settings
```json
{
  "server_port": 8891,
  "debug_mode": false,
  "enable_waypoint_persistence": true,
  "auto_save_waypoints": true
}
```

### Display Options
```json
{
  "waypoint_marker_scale": 1.0,
  "waypoint_visibility_default": true,
  "marker_cleanup_on_shutdown": true
}
```

### Limits
```json
{
  "max_waypoints_per_group": 1000,
  "max_group_nesting_depth": 5
}
```

## Authentication & UI

- No‑auth by default: WorldSurveyor is a collaborative, local tool. The extension runs with auth disabled by default (see launcher flags).
- Exposure: Protect via network boundary (reverse proxy/VPN) if accessed remotely.
- UI access: static/docs endpoints (`/`, `/index.html`, `/static/*`, `/docs`, `/openapi.json`) are public so the portal loads in the browser.

## Waypoint Types

WorldSurveyor supports multiple waypoint types for different use cases:

- **point_of_interest**: General purpose markers
- **camera_position**: Saved camera viewpoints  
- **lighting_position**: Lighting setup references
- **object_anchor**: Object placement references
- **selection_mark**: Interactive selection points
- **audio_source**: 3D audio positioning
- **spawn_point**: Entity spawn locations
- **directional_lighting**: Directional light references

## Usage Examples

### Basic Waypoint Creation
```python
import requests

# Create a point of interest
waypoint = requests.post('http://localhost:8891/waypoints/create', json={
    'position': [0, 0, 5],
    'waypoint_type': 'point_of_interest',
    'name': 'overview_point'
})

waypoint_id = waypoint.json()['waypoint_id']
print(f"Created waypoint: {waypoint_id}")
```

### Organized Waypoint System
```python
# Create groups for organization
camera_group = requests.post('http://localhost:8891/groups/create', json={
    'name': 'camera_positions',
    'description': 'Saved camera viewpoints',
    'color': '#FF6B35'
})

lighting_group = requests.post('http://localhost:8891/groups/create', json={
    'name': 'lighting_setup', 
    'description': 'Key lighting positions',
    'color': '#F7931E'
})

# Create waypoints
viewpoints = [
    {'pos': [10, 0, 5], 'name': 'front_view'},
    {'pos': [-10, 0, 5], 'name': 'back_view'},
    {'pos': [0, 10, 5], 'name': 'side_view'}
]

camera_group_id = camera_group.json()['group_id']

for viewpoint in viewpoints:
    wp = requests.post('http://localhost:8891/waypoints/create', json={
        'position': viewpoint['pos'],
        'waypoint_type': 'camera_position',
        'name': viewpoint['name'],
        'target': [0, 0, 0]  # Look at origin
    })
    
    # Add to camera group
    requests.post('http://localhost:8891/groups/add_waypoint', json={
        'waypoint_id': wp.json()['waypoint_id'],
        'group_ids': [camera_group_id]
    })
```

### Navigation and Visualization
```python
# Get all camera waypoints
camera_waypoints = requests.get('http://localhost:8891/waypoints/list', 
                               params={'waypoint_type': 'camera_position'})

# Navigate through each viewpoint
for wp in camera_waypoints.json()['waypoints']:
    print(f"Moving to {wp['name']}")
    
    # Navigate to waypoint (positions WorldViewer camera)
    requests.post('http://localhost:8891/waypoints/goto', json={
        'waypoint_id': wp['id']
    })
    
    # Capture view
    requests.post('http://localhost:8892/capture_frame', json={
        'output_path': f'/tmp/{wp["name"]}.png'
    })
```

### Selective Visibility
```python
# Hide all markers initially
requests.post('http://localhost:8891/markers/visible', json={'visible': False})

# Show only lighting waypoints
lighting_waypoints = requests.get('http://localhost:8891/waypoints/list',
                                 params={'waypoint_type': 'lighting_position'})

visible_ids = [wp['id'] for wp in lighting_waypoints.json()['waypoints']]
requests.post('http://localhost:8891/markers/selective', json={
    'visible_waypoint_ids': visible_ids
})
```

### Data Management
```python
# Export waypoints for backup
export_data = requests.get('http://localhost:8891/waypoints/export')

# Save to file
with open('scene_waypoints.json', 'w') as f:
    json.dump(export_data.json(), f)

# Later, import waypoints
with open('scene_waypoints.json', 'r') as f:
    import_data = json.load(f)

requests.post('http://localhost:8891/waypoints/import', json={
    'import_data': import_data,
    'merge_mode': 'append'  # or 'replace'
})
```

## MCP Integration

WorldSurveyor provides comprehensive MCP tools:

- `worldsurveyor_create_waypoint` - Create waypoints
- `worldsurveyor_list_waypoints` - Query waypoints  
- `worldsurveyor_create_group` - Group management
- `worldsurveyor_goto_waypoint` - Navigation
- `worldsurveyor_set_markers_visible` - Visibility control
- `worldsurveyor_export_waypoints` - Data export
 
### Monitoring

- `GET /metrics` and `GET /metrics.prom` – Performance metrics (Prometheus support)
- MCP tools: `worldsurveyor_get_metrics`, `worldsurveyor_metrics_prometheus`

## Advanced Features

### Waypoint Metadata
```python
# Create waypoint with rich metadata
waypoint = requests.post('http://localhost:8891/waypoints/create', json={
    'position': [5, 5, 2],
    'waypoint_type': 'point_of_interest',
    'name': 'analysis_point',
    'metadata': {
        'analysis_type': 'thermal',
        'sensor_height': 2.0,
        'coverage_radius': 10.0,
        'priority': 'high'
    }
})

# Update with additional notes
requests.post('http://localhost:8891/waypoints/update', json={
    'waypoint_id': waypoint.json()['waypoint_id'],
    'notes': 'Primary thermal analysis point for southern quadrant'
})
```

### Group Hierarchies
```python
# Create nested group structure
main_group = requests.post('http://localhost:8891/groups/create', json={
    'name': 'site_survey',
    'description': 'Complete site survey waypoints'
})

sub_groups = ['building_a', 'building_b', 'outdoor_areas']
main_id = main_group.json()['group_id']

for sub_name in sub_groups:
    requests.post('http://localhost:8891/groups/create', json={
        'name': sub_name,
        'parent_group_id': main_id
    })

# Get complete hierarchy  
hierarchy = requests.get('http://localhost:8891/groups/hierarchy')
```

## Error Handling

WorldSurveyor provides clear error messaging:

```json
{
  "success": false,
  "error": "Waypoint position is outside scene bounds",
  "position": [200, 200, 200],
  "scene_bounds": {
    "min": [-100, -100, -10],
    "max": [100, 100, 50]
  }
}
```

## Performance Notes

- **Database Operations**: Waypoints are persisted to SQLite for reliability
- **Marker Rendering**: Large numbers of visible markers may impact performance
- **Group Queries**: Hierarchical queries are optimized for reasonable group sizes
- **Memory Usage**: Waypoint data is loaded into memory for fast access

## Troubleshooting

### Common Issues

1. **Waypoints Not Visible**: Check marker visibility settings
2. **Database Errors**: Verify write permissions for database file
3. **Performance Issues**: Reduce number of visible markers
4. **Navigation Not Working**: Ensure WorldViewer extension is running

### Debug Information

Access debug information via the `/debug_status` endpoint for marker system diagnostics and database connection status.
