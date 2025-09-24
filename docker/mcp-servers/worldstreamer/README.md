# WorldStreamer MCP Server

Model Context Protocol (MCP) server for Isaac Sim WorldStreamer extension.

Provides AI agents with tools to control WebRTC streaming sessions in Isaac Sim through the WorldStreamer extension's HTTP API.

## Features

- **Start/Stop Streaming**: Control WebRTC streaming sessions
- **Status Monitoring**: Get real-time streaming status and URLs
- **Environment Validation**: Check Isaac Sim streaming environment
- **Health Checks**: Monitor extension connectivity and functionality
- **URL Management**: Generate streaming URLs for different network configurations

## Tools Available

| Tool | Description |
|------|-------------|
| `worldstreamer_start_streaming` | Start Isaac Sim WebRTC streaming session |
| `worldstreamer_stop_streaming` | Stop active WebRTC streaming session |
| `worldstreamer_get_status` | Get current streaming status and information |
| `worldstreamer_get_streaming_urls` | Get WebRTC streaming client URLs |
| `worldstreamer_validate_environment` | Validate Isaac Sim environment for streaming |
| `worldstreamer_health_check` | Check extension health and connectivity |

## Installation

```bash
cd mcp-servers/worldstreamer-server
pip install -e .
```

## Usage

### Standalone

```bash
python -m worldstreamer_server.server
```

### With MCP Client

```python
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters

server_params = StdioServerParameters(
    command="python", 
    args=["-m", "worldstreamer_server.server"]
)

async with ClientSession(server_params) as session:
    # List available tools
    tools = await session.list_tools()
    
    # Start streaming
    result = await session.call_tool(
        "worldstreamer_start_streaming", 
        {"server_ip": "192.168.1.100"}
    )
```

## Configuration

Set the WorldStreamer API base URL via environment variable:

```bash
export WORLDSTREAMER_BASE_URL=http://localhost:8905
```

Default: `http://localhost:8905`

## API Integration

This MCP server communicates with the WorldStreamer extension's HTTP API:

- **Base URL**: Configurable (default: http://localhost:8905)
- **Authentication**: Uses WorldStreamer's unified auth system if enabled
- **Timeout**: 30 seconds per request
- **Format**: JSON request/response

## Error Handling

The server provides comprehensive error handling:

- HTTP connection errors
- API authentication failures  
- Invalid streaming states
- Environment validation issues
- Detailed error messages with context

## Development

```bash
# Install development dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Format code
black .
isort .

# Type checking
mypy .
```

## Dependencies

- **mcp**: Model Context Protocol framework
- **httpx**: Async HTTP client for API communication
- **Python**: 3.8+ required

## Related

- [WorldStreamer Extension](../../agentworld-extensions/omni.agent.worldstreamer/)
- [Isaac Sim WebRTC Documentation](https://docs.omniverse.nvidia.com/extensions/latest/ext_livestream.html)
- [Agent World Extensions](../../agentworld-extensions/)

## License

MIT License - see project root for details.