# Configuration Guide

agenTW∞rld Extensions use a unified configuration system that supports hierarchical configuration loading with environment variable overrides.

## For New Users

**Most users don't need to modify any configuration!** The extensions work out of the box with sensible defaults.

**Only customize if you need to:**
- Change server ports (default: WorldBuilder=8899, WorldViewer=8900, WorldSurveyor=8891, WorldRecorder=8892)
- Enable debug logging for troubleshooting
- Adjust performance limits for your hardware

The installer automatically handles authentication setup via `.env` file generation.

## Configuration Hierarchy

Settings are loaded in order of precedence (highest to lowest):

1. **Environment Variables** (highest priority)
2. **Isaac Sim Settings** (carb.settings)
3. **JSON Configuration Files**
4. **Code Defaults** (lowest priority)

## Configuration Files

### Monolithic Configuration

The primary configuration file is `agent-world-config.json` in the `agentworld-extensions/` directory:

```json
{
  "_comment": "agenTW∞rld Extensions Configuration", 
  "_usage": "Hierarchical config loading: Environment > Isaac Sim Settings > JSON > Defaults",
  
  "worldbuilder": {
    "server_port": 8899,
    "server_host": "localhost",
    "debug_mode": false,
    "verbose_logging": false,
    "auth_enabled": true,
    "startup_delay": 0.1,
    "shutdown_timeout": 5.0,
    
    "max_scene_elements": 1000,
    "max_batch_size": 100,
    "enable_batch_operations": true,
    "scene_validation_enabled": true
  },
  
  "worldviewer": {
    "server_port": 8900,
    "server_host": "localhost", 
    "debug_mode": false,
    "verbose_logging": false,
    "auth_enabled": true,
    
    "enable_cinematic_mode": true,
    "default_movement_duration": 3.0,
    "max_movement_duration": 60.0,
    "smooth_movement_enabled": true,
    "camera_bounds_checking": true
  },
  
  "worldsurveyor": {
    "server_port": 8891,
    "server_host": "localhost",
    "debug_mode": false,
    "verbose_logging": false,
    
    "enable_waypoint_persistence": true,
    "waypoint_marker_scale": 1.0,
    "auto_save_waypoints": true,
    "waypoint_visibility_default": true,
    "max_waypoints_per_group": 1000
  },
  
  "worldrecorder": {
    "server_port": 8892,
    "server_host": "localhost",
    "debug_mode": false,
    "verbose_logging": false,
    
    "default_fps": 24,
    "max_recording_duration": 300,
    "output_directory": "/tmp/recordings",
    "hardware_encoding_preferred": true,
    "max_queue_size": 100
  }
}
```

### Extension-Specific Files

The monolithic `agent-world-config.json` is authoritative and should be used for all extensions. Per-extension JSON files are deprecated and removed for WorldSurveyor. Other per-extension files, if present, are considered legacy and ignored when the monolithic config exists.

## Environment Variables

Override any configuration value using environment variables with the pattern:
`<EXTENSION>_<SETTING_NAME>=<value>`

### Examples

```bash
# Server configuration
export WORLDBUILDER_SERVER_PORT=8999
export WORLDBUILDER_DEBUG_MODE=true
export WORLDBUILDER_AUTH_ENABLED=false

# WorldViewer settings  
export WORLDVIEWER_ENABLE_CINEMATIC_MODE=false
export WORLDVIEWER_MAX_MOVEMENT_DURATION=30

# WorldSurveyor settings
export WORLDSURVEYOR_AUTO_SAVE_WAYPOINTS=false
export WORLDSURVEYOR_WAYPOINT_VISIBILITY_DEFAULT=false

# WorldRecorder settings
export WORLDRECORDER_DEFAULT_FPS=60
export WORLDRECORDER_OUTPUT_DIRECTORY=/custom/recordings
```


### Authentication & Secrets

Authentication is enabled by default. Use these environment variables to configure tokens/secrets:

```bash
# Global (preferred)
export AGENT_EXT_AUTH_ENABLED=true
export AGENT_EXT_AUTH_TOKEN=your-bearer-token
export AGENT_EXT_HMAC_SECRET=your-hmac-secret

# Optional per-service overrides
export AGENT_WORLDBUILDER_AUTH_TOKEN=...
export AGENT_WORLDBUILDER_HMAC_SECRET=...
export AGENT_WORLDVIEWER_AUTH_TOKEN=...
export AGENT_WORLDVIEWER_HMAC_SECRET=...
export AGENT_WORLDSURVEYOR_AUTH_TOKEN=...
export AGENT_WORLDSURVEYOR_HMAC_SECRET=...
export AGENT_WORLDRECORDER_AUTH_TOKEN=...
export AGENT_WORLDRECORDER_HMAC_SECRET=...
```

The installer writes a `.env` file at the repo root with generated secrets and the launcher sources it automatically.

MCP servers automatically negotiate authentication using a 401-challenge: the initial unauthenticated request receives a 401, then the client retries with HMAC (X-Timestamp/X-Signature) and optional Authorization: Bearer <token> derived from the variables above (global AGENT_EXT_* or per‑service AGENT_<SERVICE>_* overrides).


### Boolean Values
Environment variables support flexible boolean parsing:
- **True**: `true`, `1`, `yes`, `on`
- **False**: `false`, `0`, `no`, `off`

## Isaac Sim Settings Integration

Extensions integrate with Isaac Sim's native carb.settings system:

### Setting Paths
- WorldBuilder: `/exts/omni.agent.worldbuilder/`
- WorldViewer: `/exts/omni.agent.worldviewer/`
- WorldSurveyor: `/exts/omni.agent.worldsurveyor/`
- WorldRecorder: `/exts/omni.agent.worldrecorder/`

### Common Settings
- `debug_mode` - Enable debug logging
- `auth_enabled` - Require authentication
- `verbose_logging` - Detailed operation logs
- `server_port` - HTTP server port


### Security Configuration File

Central security settings are read from `agent-world-security.json` in the `agentworld-extensions/` directory if present (loaded automatically by each extension):

- `authentication.bearer_token_header` – customize the header used for the Bearer token (default `Authorization`)
- `authentication.token_prefix` – customize token prefix (default `Bearer `)
- `rate_limiting.requests_per_minute` – configure per-IP request budget (default 60)

Cross‑cutting HTTP settings like CORS and JSON formatting are managed in `agent-world-http.json` in the `agentworld-extensions/` directory and applied by the unified HTTP handler.

### WorldSurveyor UI Authentication

- Static/UI endpoints (`/`, `/index.html`, `/static/*`, `/docs`, `/openapi.json`) are always accessible to load the portal.
- The portal requests `GET /auth_info` and, if a token is configured (global `AGENT_EXT_AUTH_TOKEN` or service‑specific), it auto‑applies `Authorization: Bearer <token>` to API requests.
- To disable auth for local browser testing, set `AGENT_EXT_AUTH_ENABLED=0` or toggle `/exts/omni.agent.worldsurveyor/auth_enabled=false` in carb.settings.
## Configuration Categories

### Server Settings
```json
{
  "server_host": "localhost",
  "server_port": 8899,
  "server_timeout": 1.0,
  "server_ready_timeout": 5.0,
  "startup_delay": 0.1,
  "shutdown_timeout": 5.0
}
```

### Authentication & Security
```json
{
  "auth_enabled": true,
  "cors_enabled": true,
  "cors_origin": "*"
}
```

### Logging & Debug
```json
{
  "debug_mode": false,
  "verbose_logging": false,
  "log_request_details": false,
  "log_thread_info": false
}
```

## Extension-Specific Configuration

### WorldBuilder

#### Scene Management
```json
{
  "max_scene_elements": 1000,
  "max_element_name_length": 100,
  "enable_scene_persistence": false,
  "scene_validation_enabled": true,
  "auto_save_scene": false
}
```

#### Batch Operations  
```json
{
  "enable_batch_operations": true,
  "max_batch_size": 100,
  "batch_processing_delay": 0.05,
  "max_operations_per_cycle": 5
}
```

#### Asset Management
```json
{
  "max_asset_file_size": 104857600,
  "asset_loading_timeout": 30.0,
  "asset_cache_size": 50,
  "texture_quality": "medium"
}
```

#### Spatial Bounds
```json
{
  "world_bounds_min": [-100.0, -100.0, -100.0],
  "world_bounds_max": [100.0, 100.0, 100.0],
  "default_element_scale": [1.0, 1.0, 1.0],
  "default_element_color": [0.5, 0.5, 0.5]
}
```

### WorldViewer

#### Camera Control
```json
{
  "camera_bounds_checking": true,
  "camera_min_bounds": [-50, -50, -10],
  "camera_max_bounds": [50, 50, 20],
  "min_target_distance": 0.1,
  "max_target_distance": 100.0
}
```

#### Cinematic Features
```json
{
  "enable_cinematic_mode": true,
  "smooth_movement_enabled": true,
  "default_movement_duration": 3.0,
  "max_movement_duration": 60.0,
  "movement_easing_default": "ease_in_out"
}
```

### WorldSurveyor

#### Waypoint Management
```json
{
  "enable_waypoint_persistence": true,
  "auto_save_waypoints": true,
  "waypoint_visibility_default": true,
  "waypoint_marker_scale": 1.0,
  "max_waypoints_per_group": 1000
}
```

#### Display Options
```json
{
  "marker_cleanup_on_shutdown": true,
  "default_marker_color": "#4A90E2",
  "marker_transparency": 0.8
}
```

### WorldRecorder

#### Recording Settings
```json
{
  "default_fps": 24,
  "max_fps": 60,
  "default_crf": 20,
  "recommended_max_duration": 30,
  "max_recording_duration": 300
}
```

#### Output Management  
```json
{
  "output_directory": "/tmp/recordings",
  "auto_cleanup_recordings": false,
  "min_file_size_bytes": 500,
  "temp_file_prefix": "viewport_capture_"
}
```

#### Performance Settings
```json
{
  "max_queue_size": 100,
  "hardware_encoding_preferred": true,
  "encoder_timeout_sec": 120.0,
  "default_timeout_sec": 30.0
}
```

## Dynamic Configuration

### Runtime Configuration Updates

Some settings can be updated at runtime through extension UIs or API calls. However, server settings (ports, hosts) require extension restart.

### Configuration Validation

Extensions validate configuration values on startup:
- Port ranges (1024-65535)
- Positive numeric values
- File path accessibility
- Memory and performance limits

## Development Configuration

### Debug Configuration
```json
{
  "debug_mode": true,
  "verbose_logging": true,
  "log_request_details": true,
  "log_thread_info": true,
  "enable_debug_visualization": true
}
```

### Performance Monitoring
```json
{
  "enable_performance_monitoring": true,
  "scene_update_interval": 0.1,
  "metrics_collection_enabled": true
}
```

### Testing Configuration
```json
{
  "enable_test_endpoints": true,
  "mock_hardware_encoding": false,
  "test_data_directory": "/tmp/test_data"
}
```

## Configuration Best Practices

### Production Settings
- Keep `debug_mode: false` for performance
- Set reasonable limits for `max_*` values  
- Use environment variables for deployment-specific settings
- Enable `auth_enabled` for security

### Development Settings
- Enable `debug_mode` and `verbose_logging` for troubleshooting
- Lower timeout values for faster iteration
- Use test directories for output

### Performance Optimization
- Adjust `max_queue_size` based on available memory
- Enable `hardware_encoding_preferred` for WorldRecorder
- Set appropriate `batch_processing_delay` for WorldBuilder

### Security Considerations
- Change default ports in production
- Enable authentication (`auth_enabled: true`)
- Restrict CORS origins from wildcard (`*`)
- Use HTTPS with reverse proxy for external access

## Troubleshooting Configuration

### Configuration Loading Issues
```bash
# Check configuration file syntax
python -m json.tool agent-world-config.json

# Verify environment variables
env | grep WORLD

# Test configuration loading
curl http://localhost:8899/health
```

### Common Configuration Errors

1. **Invalid JSON Syntax**: Use JSON validators
2. **Port Conflicts**: Ensure unique ports across extensions  
3. **Permission Issues**: Verify write access to output directories
4. **Resource Limits**: Adjust limits based on system capabilities

### Debug Configuration Loading

Enable debug mode to see detailed configuration loading:

```bash
export WORLDBUILDER_DEBUG_MODE=true
```

This will log:
- Configuration file loading
- Environment variable overrides  
- Isaac Sim settings integration
- Final configuration values
