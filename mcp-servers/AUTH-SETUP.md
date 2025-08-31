# MCP Servers Authentication Setup

This directory contains configuration for selective authentication across MCP servers.

## Current Status

### Servers WITH HMAC Authentication Support
- ✅ `worldbuilder` - Has HMAC auth, currently working
- ✅ `worldrecorder-server` - Has HMAC auth, currently working  
- ✅ `worldviewer` - Has HMAC auth, currently working
- ✅ `desktop-screenshot` - Working (check if needs auth)

### Servers WITHOUT Authentication  
- ❌ `videocapture` - Has auth code but Isaac Sim extension doesn't support it yet
- ❌ `worldsurveyor` - No authentication implementation

## Configuration Files

### `mcp-auth-config.env`
Central authentication configuration:
- Sets global HMAC secret and auth token for servers that support it
- Keeps videocapture auth variables unset (disables auth for that server only)
- Configure your actual secrets here for production

### `start-with-auth-config.sh`
Unified startup script that:
- Loads the auth configuration
- Starts any MCP server with proper auth settings
- Explicitly disables auth for videocapture by unsetting its auth variables

## Usage

1. **Configure your secrets** in `mcp-auth-config.env`:
   ```bash
   # Replace with your actual secure values
   AGENT_EXT_HMAC_SECRET=your-secure-hmac-secret-here
   AGENT_EXT_AUTH_TOKEN=your-secure-auth-token-here
   ```

2. **Start servers with proper auth**:
   ```bash
   # VideoCapture (auth disabled)
   ./start-with-auth-config.sh videocapture
   
   # WorldBuilder (auth enabled)
   ./start-with-auth-config.sh worldbuilder
   
   # etc.
   ```

## How It Works

- **Servers with auth support** get the global HMAC secret and token
- **VideoCapture** has its auth variables explicitly unset, so no auth headers are sent
- **WorldSurveyor** has no auth code, so it just works without auth
- **Global auth enabled** (`AGENT_EXT_AUTH_ENABLED=1`) but server-specific variables control the actual behavior

This approach allows:
- ✅ Proper HMAC authentication for servers that support it
- ✅ No authentication for servers that don't support it yet  
- ✅ Easy migration when videocapture and worldsurveyor get auth support

## Testing

The configuration has been tested and videocapture should now connect properly with authentication disabled while other servers maintain their HMAC authentication.