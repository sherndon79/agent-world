# Agent WorldRecorder Extension

Kit-native video recording and screenshot capture HTTP API for Isaac Sim.

## Overview

The Agent WorldRecorder Extension provides a reliable, dependency-free solution for capturing videos and screenshots from Isaac Sim. This extension replaces the previous PyAV-based implementation with a streamlined approach using Isaac Sim's built-in `omni.kit.capture.viewport` API.

## Key Features

### ✅ **Kit-Native Implementation**
- Uses `omni.kit.capture.viewport` for all capture operations
- No external dependencies (PyAV, FFmpeg, codecs)
- Guaranteed compatibility with Isaac Sim versions

### 🎬 **Video Recording**
- MP4 video recording with configurable settings
- Duration-based recording (seconds) or frame-based recording
- Adjustable resolution, FPS, and quality settings
- Session tracking and output management

### 📸 **Screenshot Capture**  
- Single-frame PNG/JPG screenshot capture
- Configurable resolution and output paths
- Immediate capture with polling for completion

### 🔗 **HTTP API**
- RESTful endpoints compatible with existing MCP tools
- Unified authentication and CORS support
- Real-time status monitoring and session management
- Thread-safe operation with Kit's main thread

## API Endpoints

### Video Recording
- `POST /recording/start` - Start video recording
- `POST /recording/stop` - Stop active recording  
- `GET /recording/status` - Get recording status and outputs

### Screenshot Capture
- `POST /viewport/capture_frame` - Capture single frame screenshot

### Legacy Compatibility
- `POST /video/start` - Alias for `/recording/start`
- `POST /video/stop` - Alias for `/recording/stop`  
- `GET /video/status` - Alias for `/recording/status`

## Usage Examples

### Start Video Recording
```bash
curl -X POST http://localhost:8892/recording/start \
  -H "Content-Type: application/json" \
  -d '{
    "output_path": "/tmp/recording.mp4",
    "fps": 30,
    "width": 1920,
    "height": 1080,
    "duration_sec": 10
  }'
```

### Capture Screenshot
```bash
curl -X POST http://localhost:8892/viewport/capture_frame \
  -H "Content-Type: application/json" \
  -d '{
    "output_path": "/tmp/screenshot.png",
    "width": 1920,
    "height": 1080
  }'
```

### Check Recording Status
```bash
curl http://localhost:8892/recording/status
```

## Configuration

The extension uses the unified Agent World configuration system:

- **Port**: Configurable via `WorldRecorderConfig` (default: 8892)
- **Authentication**: HMAC-based authentication support
- **Rate Limiting**: Built-in security and rate limiting
- **Metrics**: Integration with Agent World metrics system

## Architecture

```
┌─────────────────────────────────────┐
│     MCP WorldRecorder Server        │ 
│   (HTTP API Client Interface)       │
└─────────────────┬───────────────────┘
                  │ HTTP Requests
                  ▼
┌─────────────────────────────────────┐
│   Agent WorldRecorder Extension     │
│                                     │
│  ┌─────────────┐ ┌─────────────────┐│
│  │HTTP Handler │ │  API Interface  ││
│  └─────────────┘ └─────────────────┘│
└─────────────────┬───────────────────┘
                  │ Kit API Calls  
                  ▼
┌─────────────────────────────────────┐
│     omni.kit.capture.viewport       │
│        (Isaac Sim Built-in)         │
└─────────────────────────────────────┘
```

## Advantages over PyAV Implementation

| **Aspect** | **New (Kit-native)** | **Old (PyAV-based)** |
|------------|---------------------|----------------------|
| **Dependencies** | ✅ None (built-in) | ❌ PyAV + FFmpeg + codecs |
| **Reliability** | ✅ Always available | ❌ Installation issues common |
| **Maintenance** | ✅ Updates with Kit | ❌ External dependency tracking |
| **Performance** | ✅ Optimized for Kit | ⚠️ Additional encoding overhead |
| **File Size** | ✅ Minimal | ❌ Large PyAV binary |

## Security

- HMAC-SHA256 authentication support
- Rate limiting and IP-based throttling  
- CORS configuration for cross-origin requests
- Input validation and sanitization

## Development

### Dependencies
```toml
[dependencies]
"omni.kit.capture.viewport" = {}
```

### File Structure
```
omni.agent.worldrecorder/
├── config/
│   └── extension.toml
├── docs/
│   ├── README.md
│   └── CHANGELOG.md  
└── omni/agent/worldrecorder/
    ├── __init__.py
    ├── extension.py
    ├── api_interface.py
    ├── http_handler.py
    ├── config.py
    ├── security.py
    └── openapi_spec.py
```

## Troubleshooting

### Common Issues

1. **Recording Not Starting**
   - Check Isaac Sim viewport is active
   - Verify output directory exists and is writable
   - Ensure no other capture operations are running

2. **Authentication Errors**  
   - Verify HMAC credentials are configured
   - Check `WWW-Authenticate` headers in 401 responses
   - Ensure MCP client is using proper auth negotiation

3. **Output Files Missing**
   - Allow time for processing completion
   - Check `/recording/status` for output paths
   - Verify disk space and permissions

### Debug Information
```bash
# Check extension health
curl http://localhost:8892/health

# View capture capabilities  
curl http://localhost:8892/metrics

# Monitor session status
curl http://localhost:8892/recording/status
```

## Migration from PyAV Implementation

The new WorldRecorder is a drop-in replacement with the same API endpoints. Simply:

1. Archive old `omni.agent.worldrecorder` 
2. Install new Kit-native version
3. Update MCP server configurations  
4. Test recording functionality

No changes needed to existing MCP client code or automation scripts.