# MCP Servers Authentication Setup

This directory contains MCP servers with a unified authentication architecture that automatically detects and handles auth requirements.

## Architecture

All MCP servers use a **unified auth handler** with **401 retry pattern**:

1. **Initial request** - Sent without authentication
2. **401 response** - Server indicates auth is required
3. **Automatic retry** - Client resends with proper HMAC authentication
4. **Success** - Authenticated request succeeds

This pattern allows:
- ✅ **Automatic detection** - No manual configuration of which servers need auth
- ✅ **Graceful fallback** - Servers without auth work seamlessly
- ✅ **Zero configuration** - Auth headers added automatically when needed

## Current Servers

### Active MCP Servers
- 🔧 `worldbuilder` - 3D scene construction and object management
- 📹 `worldrecorder` - Video recording and frame capture
- 👁️ `worldviewer` - Camera control and scene navigation
- 📡 `worldstreamer` - SRT/RTMP streaming (autodetects protocols)
- 🗺️ `worldsurveyor` - Spatial waypoint management
- 📸 `desktop-screenshot` - Screen capture (removed HTTP version, kept stdio)

## Configuration

### Environment Variables
The auth system uses global environment variables:

```bash
# Global authentication (auto-detected via 401 retry)
AGENT_EXT_AUTH_ENABLED=1
AGENT_EXT_AUTH_TOKEN=your-auth-token
AGENT_EXT_HMAC_SECRET=your-hmac-secret
```

### Auto-Configuration
- **No per-server configuration needed** - 401 retry pattern handles detection
- **Unified auth headers** - All servers use same HMAC authentication
- **Automatic fallback** - Servers without auth requirements work without modification

## Usage

Simply start any MCP server - authentication is handled automatically:

```bash
# All servers work the same way - auth is auto-detected
docker-compose up worldstreamer
docker-compose up worldbuilder
docker-compose up worldviewer
# etc.
```

## Benefits

- 🚀 **Zero configuration** - No need to specify which servers need auth
- 🔄 **Automatic retry** - Failed auth requests are automatically retried
- 🔧 **Easy development** - New servers inherit auth support automatically
- 📊 **Consistent behavior** - All servers follow same auth pattern