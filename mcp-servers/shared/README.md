# MCP World Extensions - Unified Authentication System

## Overview

This directory contains shared authentication components for all World* MCP extensions (WorldBuilder, WorldViewer, WorldRecorder, WorldSurveyor). The unified auth system provides automatic HMAC authentication with 401 challenge/retry logic.

## Quick Start

### Basic Usage Pattern

```python
import sys
import os

# Add shared modules to path
shared_path = os.path.join(os.path.dirname(__file__), '..', '..', 'shared')
if shared_path not in sys.path:
    sys.path.insert(0, shared_path)

from mcp_base_client import MCPBaseClient

class MyExtension:
    def __init__(self, base_url: str):
        # Initialize unified auth client
        self.client = MCPBaseClient("SERVICE_NAME", base_url)
    
    async def _initialize_client(self):
        """Initialize the unified auth client"""
        if not self.client._initialized:
            await self.client.initialize()
    
    async def some_api_call(self):
        await self._initialize_client()
        
        # Automatic auth negotiation and 401 retry
        result = await self.client.get("/endpoint")
        return result

    async def __aenter__(self):
        """Async context manager entry"""
        await self._initialize_client()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.client.close()
```

### Error Handling

```python
try:
    result = await self.client.post("/create_element", json=data)
except aiohttp.ClientError as e:
    # Handle connection/network errors
    return {"error": f"Connection error: {str(e)}"}
except Exception as e:
    # Handle unexpected errors
    return {"error": f"Unexpected error: {str(e)}"}
```

## Service Configuration

### Available Services

| Service | Port | Service Name | Base URL |
|---------|------|--------------|----------|
| WorldBuilder | 8899 | `WORLDBUILDER` | `http://localhost:8899` |
| WorldViewer | 8900 | `WORLDVIEWER` | `http://localhost:8900` |
| WorldRecorder | 8892 | `WORLDRECORDER` | `http://localhost:8892` |
| WorldSurveyor | 8891 | `WORLDSURVEYOR` | `http://localhost:8891` |

### Environment Variables

The auth system supports both service-specific and global environment variables:

#### Service-Specific (Recommended)
```bash
# Per-service configuration
AGENT_WORLDBUILDER_BASE_URL=http://localhost:8899
AGENT_WORLDBUILDER_AUTH_TOKEN=your_token_here
AGENT_WORLDBUILDER_HMAC_SECRET=your_secret_here

AGENT_WORLDVIEWER_BASE_URL=http://localhost:8900
AGENT_WORLDVIEWER_AUTH_TOKEN=your_token_here
AGENT_WORLDVIEWER_HMAC_SECRET=your_secret_here
```

#### Global Fallbacks
```bash
# Global configuration (used if service-specific not found)
AGENT_EXT_AUTH_TOKEN=global_token
AGENT_EXT_HMAC_SECRET=global_secret
AGENT_EXT_AUTH_ENABLED=1  # Set to 0 to disable auth for troubleshooting
```

## Architecture

### Components

1. **`MCPBaseClient`** - Main client with automatic auth negotiation
2. **`AuthNegotiator`** - Handles HTTP 401 challenge detection and retry logic
3. **Exception handling** - Proper `aiohttp.ClientError` types for specific error scenarios

### Authentication Flow

1. **Initial Request** - Try API call without authentication
2. **401 Challenge** - Parse `WWW-Authenticate` header if returned
3. **Auth Negotiation** - Configure HMAC-SHA256 based on challenge
4. **Retry Request** - Automatically retry with proper authentication headers
5. **Success** - Cache auth config for subsequent requests

### HMAC-SHA256 Format

The system uses Isaac Sim's expected HMAC format:
```
String to sign: "METHOD|PATH|TIMESTAMP"
Headers:
  X-Timestamp: unix_timestamp
  X-Signature: hmac_sha256_hex_digest
```

## Migration Guide

### From Custom Auth to Unified Auth

**Before (Custom patterns):**
```python
# Old inconsistent approaches
response = await self._make_request("POST", "/endpoint", data)
response = await self.client.post(f"{self.base_url}/endpoint", json=data)
```

**After (Unified pattern):**
```python
# New consistent approach
await self._initialize_client()
result = await self.client.post("/endpoint", json=data)
```

### Key Changes Made

1. **Replaced `httpx` with `aiohttp`** - Better async integration and session management
2. **Unified auth pattern** - All extensions use `MCPBaseClient`
3. **Automatic 401 retry** - No more manual auth header management
4. **Proper exception types** - `aiohttp.ClientError` instead of generic exceptions

## Troubleshooting

### Common Issues

#### Import Errors
```bash
ImportError: attempted relative import with no known parent package
```
**Solution:** Ensure shared path is added to `sys.path` before importing.

#### Connection Failures
```bash
Connection error: Could not connect to extension at http://localhost:8899
```
**Solutions:**
- Verify Isaac Sim is running
- Check extension is enabled and HTTP API is active
- Verify correct port in base URL

#### Authentication Errors
```bash
HTTP 401: Unauthorized
```
**Solutions:**
- Check `AGENT_EXT_HMAC_SECRET` environment variable
- Verify `AGENT_EXT_AUTH_TOKEN` is set
- Ensure extension HMAC validation is enabled in Isaac Sim
- Try setting `AGENT_EXT_AUTH_ENABLED=0` to temporarily disable auth

### Debug Mode

To disable authentication for troubleshooting:
```bash
export AGENT_EXT_AUTH_ENABLED=0
```

## Dependencies

The unified auth system requires:
- `aiohttp>=3.8.0` - HTTP client with async support
- `mcp>=1.13.1` - MCP framework

These are automatically installed when you run:
```bash
pip install -e .
```

## Development Notes

### Design Decisions

1. **Why aiohttp over httpx?** - Better async lifecycle management and connection pooling for long-running MCP servers
2. **Why unified client?** - Eliminates auth inconsistencies that were causing 401 errors on spatial queries and batch operations
3. **Why 401 challenge pattern?** - RFC 7235 compliant and allows dynamic auth configuration

### Future Improvements

- Consider unified venv for all extensions to reduce dependency duplication
- Add metrics/monitoring for auth success/failure rates
- Implement auth token refresh logic for long-running sessions

## Testing

To verify unified auth is working:
```python
# Test basic connectivity
health = await client.get("/health")

# Test authenticated endpoint
result = await client.post("/add_element", json={"element_type": "cube", ...})
```

The system should automatically handle auth negotiation and retry any 401 errors transparently.