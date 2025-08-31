# Screenshot MCP Server

Cross-platform desktop screenshot capture MCP server for AI agents. Provides system-wide screenshot capabilities independent of Isaac Sim, useful for documenting workflows, capturing external applications, or integrating desktop automation with 3D scene work.

## Features

### Desktop Capture
- **Full Desktop**: Capture entire desktop/screen
- **Specific Windows**: Target individual application windows
- **Rectangular Areas**: Capture custom screen regions
- **Multi-Monitor**: Support for multiple display setups

### Window Management
- **Window Detection**: List all open windows with titles
- **Window Targeting**: Capture specific windows by title/name
- **Isaac Sim Integration**: Specialized Isaac Sim window capture

### File Management
- **Automatic Naming**: Timestamp-based filenames
- **Custom Paths**: Specify output locations
- **Format Support**: PNG, JPEG, and other formats
- **Cleanup Tools**: Purge old screenshots by age

## Installation

### Prerequisites

#### Quick Setup (Recommended)
Use the Agent World installer to automatically set up MCP server virtual environments:

```bash
# Linux/macOS
./scripts/install_agent_world.sh
# Answer "yes" when prompted: "Create Python virtual environments for MCP servers?"

# Windows
./scripts/install_agent_world.ps1
# Answer "yes" when prompted: "Create Python virtual environments for MCP servers?"
```

#### Manual Setup
If setting up manually, create a virtual environment for the desktop-screenshot MCP server:

```bash
# Create virtual environment for desktop-screenshot MCP server
cd mcp-servers/desktop-screenshot
python -m venv venv
source venv/bin/activate  # Linux/macOS
# or: venv\Scripts\activate  # Windows
pip install -e .
```

**Note:** The MCP server uses modern Python packaging (`pyproject.toml`) and must be installed in development mode (`pip install -e .`) to work properly.

### Platform-Specific Requirements

**Linux (Ubuntu/Debian):**
```bash
sudo apt-get install python3-tk python3-dev
pip install pynput python-xlib
```

**macOS:**
```bash
pip install pyobjc-framework-Quartz pyobjc-framework-ApplicationServices
```

**Windows:**
```bash
pip install pywin32 pillow
```

### MCP Client Configuration

Add to your MCP client configuration:

```json
{
  "mcpServers": {
    "screenshot": {
      "command": "python",
      "args": ["/path/to/mcp-servers/desktop-screenshot/src/mcp_screenshot_server.py"],
      "env": {
        "SCREENSHOT_OUTPUT_DIR": "/tmp/screenshots"
      }
    }
  }
}
```

## Available MCP Tools

### Desktop Capture
- `screenshot_desktop` - Capture full desktop
- `screenshot_area` - Capture rectangular screen region  
- `screenshot_window` - Capture specific window by title
- `screenshot_isaac_sim` - Specialized Isaac Sim window capture

### Window Management
- `list_windows` - List all open windows with details

### File Management  
- `screenshot_purge` - Clean up old screenshots by age

## Usage Examples

### Basic Desktop Capture

```python
import mcp

# Connect to screenshot MCP server
ss = mcp.Client("screenshot")

# Capture full desktop
result = await ss.call_tool("screenshot_desktop", {
    "purpose": "documenting current desktop state",
    "tags": ["documentation", "desktop"]
})

print(f"Screenshot saved: {result['output_path']}")
```

### Window-Specific Capture

```python
# List available windows
windows = await ss.call_tool("list_windows")
print("Available windows:")
for window in windows["windows"]:
    print(f"- {window['title']} (PID: {window['pid']})")

# Capture specific application
result = await ss.call_tool("screenshot_window", {
    "window_title": "Isaac Sim",
    "purpose": "capturing Isaac Sim viewport",
    "tags": ["isaac-sim", "3d-scene"]
})
```

### Area Capture

```python
# Capture specific screen region
result = await ss.call_tool("screenshot_area", {
    "x": 100,
    "y": 100, 
    "width": 800,
    "height": 600,
    "purpose": "capturing UI panel",
    "notes": "Extension control panel screenshot"
})
```

### Isaac Sim Integration

```python
# Specialized Isaac Sim capture
result = await ss.call_tool("screenshot_isaac_sim", {
    "purpose": "documenting 3D scene setup",
    "tags": ["isaac-sim", "scene-documentation"]
})
```

## Integration with Agent World Extensions

### Scene Documentation Workflow

```python
async def document_scene_creation():
    """Document the complete scene creation process."""
    
    # 1. Capture desktop before starting
    await ss.call_tool("screenshot_desktop", {
        "purpose": "initial desktop state",
        "tags": ["workflow-start"]
    })
    
    # 2. Create scene with WorldBuilder
    await wb.call_tool("worldbuilder_add_element", {
        "element_type": "cube",
        "name": "demo_cube",
        "position": [0, 0, 1]
    })
    
    # 3. Capture Isaac Sim after scene creation
    await ss.call_tool("screenshot_isaac_sim", {
        "purpose": "scene after adding cube",
        "tags": ["scene-building", "cube-creation"]
    })
    
    # 4. Position camera with WorldViewer
    await wv.call_tool("worldviewer_set_camera_position", {
        "position": [5, 5, 5],
        "target": [0, 0, 1]
    })
    
    # 5. Capture final view
    await ss.call_tool("screenshot_isaac_sim", {
        "purpose": "final camera positioned view",
        "tags": ["camera-positioning", "final-result"]
    })
```

### Multi-Application Workflows

```python
async def multi_app_documentation():
    """Document workflow spanning multiple applications."""
    
    applications = [
        "Isaac Sim", 
        "Blender",
        "Visual Studio Code",
        "Terminal"
    ]
    
    for app in applications:
        try:
            result = await ss.call_tool("screenshot_window", {
                "window_title": app,
                "purpose": f"documenting {app} state",
                "tags": ["multi-app-workflow", app.lower().replace(" ", "-")]
            })
            print(f"Captured {app}: {result['output_path']}")
        except Exception as e:
            print(f"Could not capture {app}: {e}")
```

### Comparative Analysis

```python
async def before_after_comparison():
    """Create before/after comparison screenshots."""
    
    # Capture before state
    before = await ss.call_tool("screenshot_isaac_sim", {
        "purpose": "scene before modifications",
        "tags": ["before", "comparison"]
    })
    
    # Make scene modifications with WorldBuilder
    await wb.call_tool("worldbuilder_create_batch", {
        "batch_name": "comparison_elements",
        "elements": [
            {"element_type": "sphere", "name": "sphere1", "position": [2, 0, 1]},
            {"element_type": "cylinder", "name": "cyl1", "position": [-2, 0, 1]}
        ]
    })
    
    # Capture after state
    after = await ss.call_tool("screenshot_isaac_sim", {
        "purpose": "scene after modifications", 
        "tags": ["after", "comparison"]
    })
    
    print(f"Before: {before['output_path']}")
    print(f"After: {after['output_path']}")
```

## Advanced Features

### Custom Output Paths

```python
# Organized screenshot storage
result = await ss.call_tool("screenshot_desktop", {
    "output_path": "/project/documentation/desktop_capture_001.png",
    "purpose": "project milestone documentation",
    "tags": ["milestone", "project-docs"]
})
```

### Screenshot Management

```python
# Clean up old screenshots  
cleanup = await ss.call_tool("screenshot_purge", {
    "age": "7d",  # Remove files older than 7 days
    "pattern": "isaac_sim_*",  # Only Isaac Sim screenshots
    "dry_run": false  # Actually delete files
})

print(f"Removed {cleanup['files_removed']} old screenshots")
```

### Automated Screenshot Series

```python
async def automated_screenshot_series():
    """Take screenshots at regular intervals."""
    
    import asyncio
    
    viewpoints = [
        {"pos": [10, 0, 5], "name": "front"},
        {"pos": [0, 10, 5], "name": "side"}, 
        {"pos": [-10, 0, 5], "name": "back"},
        {"pos": [0, -10, 5], "name": "rear"}
    ]
    
    for i, viewpoint in enumerate(viewpoints):
        # Position camera
        await wv.call_tool("worldviewer_set_camera_position", {
            "position": viewpoint["pos"],
            "target": [0, 0, 0]
        })
        
        # Wait for camera to settle
        await asyncio.sleep(1)
        
        # Capture screenshot
        await ss.call_tool("screenshot_isaac_sim", {
            "purpose": f"viewpoint {viewpoint['name']}",
            "tags": ["series", f"viewpoint-{i+1}"]
        })
```

## Tool Parameters

### screenshot_desktop
```json
{
  "purpose": "Why this screenshot is being taken",
  "tags": ["categorization", "tags"],
  "notes": "Additional context",
  "output_path": "/custom/path.png"
}
```

### screenshot_window
```json
{
  "window_title": "Application Title",
  "purpose": "Screenshot purpose", 
  "tags": ["tags"],
  "notes": "Context notes",
  "output_path": "/custom/path.png"
}
```

### screenshot_area
```json
{
  "x": 100,
  "y": 100,
  "width": 800,
  "height": 600,
  "purpose": "Area capture purpose",
  "tags": ["area-capture"],
  "output_path": "/custom/path.png"
}
```

### screenshot_purge
```json
{
  "age": "7d",
  "pattern": "screenshot_*.png",
  "dry_run": true
}
```

## Error Handling

### Window Not Found
```python
try:
    result = await ss.call_tool("screenshot_window", {
        "window_title": "NonExistentApp"
    })
except Exception as e:
    print(f"Window capture failed: {e}")
    
    # Fallback to desktop capture
    result = await ss.call_tool("screenshot_desktop", {
        "purpose": "fallback desktop capture"
    })
```

### Permission Issues
```python
# Check available windows first
windows = await ss.call_tool("list_windows")
available_titles = [w["title"] for w in windows["windows"]]

if "Isaac Sim" in available_titles:
    result = await ss.call_tool("screenshot_isaac_sim")
else:
    print("Isaac Sim not found in available windows")
```

## Performance Notes

- **Desktop Capture**: Fast, captures entire screen
- **Window Capture**: Moderate speed, requires window detection
- **Area Capture**: Fastest, captures only specified region
- **Multi-Monitor**: Performance depends on total pixel count

## Platform Differences

### Linux
- Requires X11 display server
- May need additional permissions for screen access
- Window titles may vary by window manager

### macOS  
- Requires accessibility permissions
- System may prompt for screen recording permissions
- Retina displays capture at high DPI

### Windows
- Works with multiple monitor setups
- Window titles include application names
- May require running as administrator for some applications

## Troubleshooting

### Common Issues

1. **No Screenshots Generated**
   - Check output directory permissions
   - Verify display/screen access permissions
   - Test with desktop capture first

2. **Window Not Found**
   - Use `list_windows` to verify window titles
   - Window titles may change based on document/state
   - Try partial title matching

3. **Permission Errors**
   - Grant screen recording permissions (macOS)
   - Check accessibility settings
   - Run with appropriate privileges

### Debug Information

Enable debug logging:
```bash
export DEBUG=true
python mcp_screenshot_server.py
```

The screenshot MCP server provides a valuable complement to the Isaac Sim extensions, enabling comprehensive documentation workflows that span both 3D scenes and desktop applications.