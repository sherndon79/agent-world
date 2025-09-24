# MCP Transport Implementation Guide

## Overview
This document provides a complete guide for implementing Model Context Protocol (MCP) servers in Python, covering the evolution from deprecated transports to the current Streamable HTTP approach.

## Key Findings

### 1. Transport Evolution (Critical Update)
- **SSE Transport**: **DEPRECATED as of protocol version 2024-11-05** - No longer supported
- **Streamable HTTP Transport**: **Current standard** using single HTTP endpoint with optional SSE streaming
- **FastMCP**: Official Python SDK implementation supporting Streamable HTTP transport
- Claude Code and other modern MCP clients expect Streamable HTTP, not legacy SSE

### 2. Common Implementation Mistakes

#### ❌ Incorrect Approach (What We Initially Tried)
```python
# This doesn't exist in the MCP SDK
from mcp.server.sse import sse_server  # WRONG - This function doesn't exist

# This is also incorrect usage
async with SseServerTransport("/sse") as (read_stream, write_stream):
    # This pattern doesn't work for SSE
```

#### ✅ Correct Modern Implementation with Streamable HTTP Transport

```python
import uvicorn
import os
from mcp.server.fastmcp import FastMCP

# Create FastMCP server instance
mcp = FastMCP("YourServerName")

# Define tools using decorators
@mcp.tool()
def your_tool_function(param: str) -> str:
    """Description of your tool"""
    return f"Result: {param}"

@mcp.resource("resource://pattern/{id}")
def your_resource(id: str) -> str:
    """Description of your resource"""
    return f"Resource content for {id}"

# Get the ASGI application
app = mcp.create_app()

if __name__ == "__main__":
    port = int(os.getenv("MCP_SERVER_PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
```

#### ❌ Deprecated SSE Transport (DO NOT USE)

```python
# This entire approach is DEPRECATED and will not work with modern MCP clients
from mcp.server.sse import SseServerTransport  # DEPRECATED
async with SseServerTransport("/sse") as (read_stream, write_stream):  # DEPRECATED
```

### 3. FastMCP Implementation (Higher-Level API)

```python
from mcp.server.fastmcp import FastMCP
from starlette.applications import Starlette
from starlette.routing import Mount, Route
from mcp.server.sse import SseServerTransport
import uvicorn

def create_sse_server(mcp: FastMCP):
    """Create a Starlette app for SSE connections"""
    transport = SseServerTransport("/messages/")

    async def handle_sse(request):
        async with transport.connect_sse(
            request.scope, request.receive, request._send
        ) as streams:
            await mcp._mcp_server.run(
                streams[0], streams[1],
                mcp._mcp_server.create_initialization_options()
            )

    routes = [
        Route("/sse/", endpoint=handle_sse),
        Mount("/messages/", app=transport.handle_post_message),
    ]

    return Starlette(routes=routes)

# Usage
mcp = FastMCP("YourServerName")
app = create_sse_server(mcp)

@mcp.tool()
def your_tool(param: str) -> str:
    return f"Result: {param}"

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

## Required Dependencies

### Core MCP Dependencies (Modern)
```
mcp>=1.13.1         # Official MCP SDK with FastMCP
uvicorn>=0.24.0     # ASGI server
```

### Legacy Dependencies (Remove These)
```
starlette>=0.27.0   # No longer needed with FastMCP
aiohttp>=3.8.0      # No longer needed with FastMCP
aiohttp-cors>=0.7.0 # No longer needed with FastMCP
```

## Container Configuration

### Docker Requirements
- Ensure uvicorn is installed in the container
- Expose the correct ports (8700-8704 for our setup)
- Set proper environment variables for port configuration

### Environment Variables
```bash
MCP_SERVER_PORT=8702        # Port for the server
AGENT_EXT_AUTH_ENABLED=1    # Authentication settings
AGENT_EXT_AUTH_TOKEN=...    # Auth token
AGENT_EXT_HMAC_SECRET=...   # HMAC secret
```

## Claude Code Configuration

### Correct Client Configuration (Streamable HTTP)
```json
{
  "mcpServers": {
    "worldbuilder-server": {
      "type": "http",
      "url": "http://localhost:8700",
      "env": {}
    }
  }
}
```

### Legacy Configuration (REMOVE)
```json
{
  "mcpServers": {
    "worldbuilder-server": {
      "type": "sse",                    // DEPRECATED - Change to "http"
      "url": "http://localhost:8700/sse", // DEPRECATED - Remove /sse path
      "env": {}
    }
  }
}
```

## Troubleshooting

### Common Issues

1. **ImportError: cannot import name 'sse_server'**
   - Solution: Use `SseServerTransport` with proper Starlette routing

2. **Containers Restarting Continuously**
   - Usually caused by servers exiting immediately
   - Check for proper async/await patterns
   - Ensure uvicorn is running the ASGI app correctly

3. **SSE Connection Not Established**
   - Verify routes are set up correctly
   - Check that both `/sse` (GET) and `/sse/messages` (POST) endpoints exist
   - Ensure CORS is configured if accessing from browser

### Debug Commands
```bash
# Check container logs
docker-compose logs -f service-name

# Check if ports are exposed
docker-compose ps

# Test SSE endpoint
curl -H "Accept: text/event-stream" http://localhost:8702/sse

# Test health/basic connectivity
curl http://localhost:8702/health
```

### Known Issues and Solutions

#### RuntimeError: asyncio.run() cannot be called from a running event loop
**Problem**: When the main() function is already async, calling `uvicorn.run()` creates a nested event loop.

**Solution**: Use uvicorn programmatically within the existing async context:
```python
# Instead of:
uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")

# Use:
config = uvicorn.Config(app, host="0.0.0.0", port=port, log_level="info")
server = uvicorn.Server(config)
await server.serve()
```

#### TypeError: 'NoneType' object is not callable
**Problem**: SSE endpoint functions return None instead of proper HTTP responses.

**Cause**: Incorrect SSE transport routing - using individual Route handlers instead of Mount for message endpoints.

**Wrong approach:**
```python
async def post_handler(request):
    sse_transport = SseServerTransport("/sse/messages")
    return await sse_transport.handle_post_message(request)

routes = [
    Route("/sse", sse_endpoint, methods=["GET"]),
    Route("/sse/messages", post_handler, methods=["POST", "OPTIONS"])  # WRONG
]
```

**Correct approach:**
```python
# Create single SSE transport instance
sse_transport = SseServerTransport("/sse/messages")

# Use Mount for message endpoint handling
routes = [
    Route("/sse", sse_endpoint, methods=["GET"]),
    Mount("/sse/messages", app=sse_transport.handle_post_message)  # CORRECT
]
```

#### SSE Connection Hangs (HTTP 200 but no data)
**Problem**: SSE endpoint connects but doesn't properly handle MCP protocol handshake.

**Cause**: Incorrect usage of `connect_sse()` method parameters.

**Solution**: Use proper ASGI parameters with `request._send`:
```python
async def sse_endpoint(request):
    """Handle SSE connections"""
    sse_transport = SseServerTransport("/sse/messages")

    async with sse_transport.connect_sse(
        request.scope, request.receive, request._send  # Use request._send
    ) as streams:
        await mcp_server.server.run(
            streams[0], streams[1],
            InitializationOptions(
                server_name="your-server",
                server_version="1.0.0",
                capabilities=mcp_server.server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={}
                )
            )
        )
```

## Architecture Comparison

### SSE Transport Architecture
```
Client ←→ [GET /sse] ←→ SSE Connection (persistent)
Client ←→ [POST /sse/messages] ←→ Message Handler
```

### Streamable HTTP Transport (Future)
```
Client ←→ [Single HTTP Endpoint] ←→ Bidirectional Communication
```

## Migration Notes

### From stdio_server to SSE
1. Remove `stdio_server` imports
2. Add Starlette/uvicorn dependencies
3. Implement SSE routing as shown above
4. Update container configuration

### Container Volume Considerations
- Ensure local file mounts (not external repo dependencies)
- Use relative paths in docker-compose.yml: `./worldstreamer:/app/worldstreamer:ro`
- Remove virtual environment directories from version control

## References
- [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)
- [MCP SSE Server Examples](https://www.ragie.ai/blog/building-a-server-sent-events-sse-mcp-server-with-fastapi)
- [Starlette Documentation](https://www.starlette.io/)
- [Uvicorn Documentation](https://www.uvicorn.org/)

## Troubleshooting Journey Summary

### Initial Problem
MCP containers were stuck in continuous restart loops with exit code 0.

### Root Cause Analysis
1. **CRITICAL: Using Deprecated Transport**: SSE transport was deprecated in protocol version 2024-11-05
2. **Wrong SDK Usage**: Used low-level `Server` class instead of `FastMCP`
3. **Incorrect Client Configuration**: Claude Code was configured for legacy `sse` transport
4. **Outdated Dependencies**: Using starlette, aiohttp instead of pure FastMCP approach

### Resolution Steps
1. **Research**: Analyzed MCP SDK source and examples to understand proper SSE implementation
2. **Transport Fix**: Implemented correct SSE transport with Starlette routing
3. **Asyncio Fix**: Switched to programmatic uvicorn server within async context
4. **Routing Fix**: Used Mount pattern for `/sse/messages` endpoints instead of individual Route handlers
5. **Dependencies**: Added starlette>=0.27.0 and uvicorn>=0.24.0 to requirements
6. **Volume Fix**: Updated docker-compose to use local volumes instead of external repo dependencies

### Key Learnings
- MCP SSE transport requires specific ASGI setup with Mount routing
- SSE servers need both GET `/sse` and POST/OPTIONS `/sse/messages` endpoints
- AsyncIO context matters when running uvicorn programmatically
- MCP SDK documentation examples can be incomplete - source code analysis is essential

---
*Generated during agent-adventures MCP server containerization - September 2025*