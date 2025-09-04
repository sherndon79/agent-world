# Installation Guide

This guide walks through installing and setting up agenTW∞rld Extensions in Isaac Sim.

## Prerequisites

### System Requirements
- **Isaac Sim 5.0.0** (recommended - developed and tested against this version)
- **Operating System**: Windows 10/11 or Ubuntu 20.04/22.04  
- **GPU**: NVIDIA GPU with graphics drivers 470+ 
- **Memory**: 16GB+ RAM recommended
- **Storage**: 5GB+ free space for extensions and recordings

### Isaac Sim Installation

The agenTW∞rld installer can handle Isaac Sim installation for you:

**Option 1: Automatic Download (Recommended)**
1. Run the installer script - it will automatically download Isaac Sim 5.0.0
2. No manual download needed

**Option 2: Pre-download (Faster Installation)**  
1. Download Isaac Sim 5.0.0 to your agenTW∞rld directory:
   - **Linux**: [isaac-sim-standalone-5.0.0-linux-x86_64.zip](https://download.isaacsim.omniverse.nvidia.com/isaac-sim-standalone-5.0.0-linux-x86_64.zip)
   - **Windows**: [isaac-sim-standalone-5.0.0-windows-x86_64.zip](https://download.isaacsim.omniverse.nvidia.com/isaac-sim-standalone-5.0.0-windows-x86_64.zip)
2. Run the installer script - it will auto-detect and extract the zip

**Option 3: Manual Installation**
1. Extract Isaac Sim manually to your preferred location
2. Run the installer and provide the path when prompted

*Note: Newer Isaac Sim versions may work but are not officially tested.*

## Extension Installation


### Method 0: Quick Install (Recommended)

Use the helper installer to wire everything up interactively:

```bash
bash scripts/install_agent_world.sh
```

What it does:
- Detects an existing Isaac Sim host or lets you download/unpack a host bundle
- Symlinks extensions into your chosen `extsUser` directory
- Offers to enable API authentication and generates secrets into `.env`
- Creates a launcher wrapper that sources `.env` and enables extensions with auth on

Launch Isaac Sim with the generated wrapper:

```bash
scripts/launch_agent_world.sh
```

Verify basic health for all services:

```bash
bash scripts/smoke_test.sh
```

Note: If auth is enabled, `smoke_test.sh` will pick up `AGENT_EXT_AUTH_TOKEN` from `.env` automatically.

#### Authentication Setup
The installer automatically generates authentication credentials if you choose to enable API security:

**Generated Files:**
- **`.env` file**: Contains generated Bearer token and HMAC secret
- **Launcher script**: Automatically sources `.env` for authentication

**Generated Credentials:**
```bash
# Example .env contents (values are auto-generated)
AGENT_EXT_AUTH_ENABLED=1
AGENT_EXT_AUTH_TOKEN=abc123...  # 64-character hex token
AGENT_EXT_HMAC_SECRET=def456...  # 96-character hex secret
```

**Per-Service Overrides:** You can optionally set individual tokens per extension by uncommenting the per-service variables in `.env`.



### Method 1: Manual Installation

1. **Copy Extensions**
   ```bash
   cp -r agentworld-extensions/* /path/to/isaac-sim/exts/
   ```

2. **Enable Extensions in Isaac Sim**
   - Launch Isaac Sim
   - Open `Window > Extensions`
   - Search for "agent" to find the extensions
   - Enable each extension:
     - `omni.agent.worldbuilder`
     - `omni.agent.worldviewer`  
     - `omni.agent.worldsurveyor`
     - `omni.agent.worldrecorder`

3. **Verify Installation**
   - Check extension manager shows all extensions as enabled
   - Look for extension UI panels in Isaac Sim menus
   - Verify HTTP servers start (check extension logs)

### Method 2: Development Installation

For development or customization:

1. **Symbolic Link Installation**
   ```bash
   ln -s /path/to/agentworld-extensions/omni.agent.worldbuilder \
         /path/to/isaac-sim/exts/omni.agent.worldbuilder
   ```

2. **Enable Developer Mode**
   - In Isaac Sim Extensions manager
   - Enable "Developer Bundle" 
   - Extensions will auto-reload on file changes

## Configuration

### Default Configuration
Extensions use the unified configuration system with sensible defaults:

- **WorldBuilder**: Port 8899
- **WorldViewer**: Port 8900  
- **WorldSurveyor**: Port 8891
- **WorldRecorder**: Port 8892

### Custom Configuration

Create or edit `agentworld-extensions/agent-world-config.json`:

```json
{
  "worldbuilder": {
    "server_port": 8899,
    "debug_mode": false,
    "max_scene_elements": 1000
  },
  "worldviewer": {
    "server_port": 8900,
    "enable_cinematic_mode": true,
    "max_movement_duration": 60.0
  },
  "worldsurveyor": {
    "server_port": 8891,
    "waypoint_visibility_default": true,
    "auto_save_waypoints": true
  },
  "worldrecorder": {
    "server_port": 8892,
    "default_fps": 30,
    "hardware_encoding_preferred": true
  }
}
```

### Environment Variables
Override any setting via environment variables:

```bash
export WORLDBUILDER_DEBUG_MODE=true
export WORLDVIEWER_SERVER_PORT=8901
export WORLDRECORDER_MAX_FPS=60
```

## Verification


### Authentication Headers (curl)

If authentication is enabled, include your Bearer token:

```bash
export AUTH="Authorization: Bearer $AGENT_EXT_AUTH_TOKEN"
curl -H "$AUTH" http://localhost:8900/health
```

For HMAC (advanced):

```bash
TS=$(date +%s)
SIG=$(python3 - <<PY
import hmac,hashlib,os
secret=os.environ['AGENT_EXT_HMAC_SECRET'].encode()
msg=f"GET|/health|{os.environ['TS']}".encode()
print(hmac.new(secret,msg,hashlib.sha256).hexdigest())
PY
)
curl -H "X-Timestamp: $TS" -H "X-Signature: $SIG" http://localhost:8900/health
```


### Extension Status
Check that extensions loaded successfully:

1. **Extension Manager**
   - All extensions show "Enabled" status
   - No error messages in extension logs

2. **HTTP Servers**
   ```bash
   # Check server availability
   curl http://localhost:8899/health  # WorldBuilder
   curl http://localhost:8900/health  # WorldViewer  
   curl http://localhost:8891/health  # WorldSurveyor
   curl http://localhost:8892/health  # WorldRecorder
   ```

3. **Extension Menus**
   - WorldBuilder: Scene creation UI panel
   - WorldViewer: Camera controls
   - WorldSurveyor: Waypoint management
   - WorldRecorder: Capture controls

### Quick Test
Use the provided smoke test script for verification:
```bash
bash scripts/smoke_test.sh
```

This script automatically tests all extension health endpoints and handles authentication if enabled.

## MCP Integration Setup

### Install MCP Servers

#### Quick Setup (Recommended)
The agenTW∞rld installer can automatically set up MCP server virtual environments:

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

**Note:** The installer now uses a unified virtual environment approach that installs all MCP servers from a single `pyproject.toml` file in the `mcp-servers` directory. This simplifies dependency management and reduces disk usage compared to individual virtual environments per server.

### Configure MCP Servers
Copy MCP server configurations to your MCP client:

```json
{
  "mcpServers": {
    "worldbuilder-server": {
      "command": "/path/to/mcp-servers/venv/bin/python",
      "args": ["-m", "mcp_agent_worldbuilder"],
      "env": {
        "WORLDBUILDER_API_URL": "http://localhost:8899"
      }
    },
    "worldviewer-server": {
      "command": "/path/to/mcp-servers/venv/bin/python",
      "args": ["-m", "mcp_agent_worldviewer"],
      "env": {
        "WORLDVIEWER_API_URL": "http://localhost:8900"
      }
    },
    "worldsurveyor-server": {
      "command": "/path/to/mcp-servers/venv/bin/python",
      "args": ["-m", "mcp_agent_worldsurveyor"],
      "env": {
        "WORLDSURVEYOR_API_URL": "http://localhost:8891"
      }
    },
    "worldrecorder-server": {
      "command": "/path/to/mcp-servers/venv/bin/python",
      "args": ["-m", "mcp_agent_worldrecorder"],
      "env": {
        "WORLDRECORDER_API_URL": "http://localhost:8892"
      }
    },
    "screenshot-server": {
      "command": "/path/to/mcp-servers/venv/bin/python",
      "args": ["-m", "mcp_desktop_screenshot"]
    }
  }
}
```

## Troubleshooting

### Common Issues

#### Extensions Not Loading
- **Symptom**: Extensions don't appear in Extension Manager
- **Solution**: Verify file permissions and paths
- **Check**: Extension `.toml` files are readable

#### Port Conflicts  
- **Symptom**: "Address already in use" errors
- **Solution**: Change ports in configuration or kill conflicting processes
- **Check**: `netstat -tlnp | grep <port>`

#### Permission Errors
- **Symptom**: Can't write recordings or waypoints
- **Solution**: Ensure Isaac Sim has write permissions to output directories
- **Check**: Create test file in output directory

#### Performance Issues
- **Symptom**: Slow response or UI lag
- **Solution**: Reduce concurrent operations, check system resources
- **Check**: Extension `/metrics` endpoints for bottlenecks

### Debug Mode
Enable debug logging for troubleshooting:

```json
{
  "worldbuilder": {
    "debug_mode": true,
    "verbose_logging": true
  }
}
```

### Log Locations
Extension logs are available in:
- Isaac Sim Console window
- Isaac Sim log files in user directory
- Extension-specific HTTP response messages

### Getting Help

1. **Check Extension Health**: Use `/health` endpoints
2. **Review Logs**: Enable debug mode for detailed logs  
3. **Verify Prerequisites**: Ensure Isaac Sim and system requirements
4. **Test Isolation**: Test extensions individually
5. **Configuration**: Verify JSON configuration syntax

For persistent issues, include:
- Isaac Sim version
- Extension versions  
- System information
- Configuration files
- Error logs and messages