#!/usr/bin/env python3
"""
WorldStreamer MCP Server

Model Context Protocol server for Isaac Sim RTMP streaming control.
Provides AI agents with tools to manage streaming sessions through HTTP API.
"""

import asyncio
import json
import logging
import httpx
from typing import Any, Sequence
from pathlib import Path

from mcp.server.models import InitializationOptions
from mcp.server import NotificationOptions, Server
from mcp.types import (
    Resource, Tool, TextContent, ImageContent, EmbeddedResource
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("worldstreamer-server")

# Configuration
# Default base URLs for auto-detection - can be overridden via environment variable WORLDSTREAMER_BASE_URL
# Ports come from agentworld-extensions/agent-world-config.json
DEFAULT_RTMP_URL = "http://localhost:8906"  # worldstreamer.rtmp.server_port
DEFAULT_SRT_URL = "http://localhost:8908"   # worldstreamer.srt.server_port
REQUEST_TIMEOUT = 30.0
HEALTH_CHECK_TIMEOUT = 5.0

class WorldStreamerMCPServer:
    """MCP server for WorldStreamer streaming control with auto-detection."""
    
    def __init__(self, base_url: str = None):
        """
        Initialize WorldStreamer MCP server with auto-detection.
        
        Args:
            base_url: Optional override base URL for WorldStreamer API
        """
        self.rtmp_url = DEFAULT_RTMP_URL.rstrip('/')
        self.srt_url = DEFAULT_SRT_URL.rstrip('/')
        self.base_url = None  # Will be set by auto-detection
        self.active_protocol = None  # 'rtmp' or 'srt'
        
        # Override URLs if base_url provided
        if base_url:
            self.base_url = base_url.rstrip('/')
            self.active_protocol = "manual"
            logger.info(f"Manual mode: Using provided base URL: {self.base_url}")
        
        self.server = Server("worldstreamer-server")
        
        # Register tools and handlers
        self._register_tools()
        self._register_handlers()
        
        logger.info(f"WorldStreamer MCP server initialized - RTMP: {self.rtmp_url}, SRT: {self.srt_url}")
    
    async def _detect_active_service(self) -> str:
        """
        Auto-detect which WorldStreamer service is running.
        
        Returns:
            Base URL of the active service
            
        Raises:
            Exception if no service is available
        """
        if self.base_url and self.active_protocol == "manual":
            return self.base_url
        
        # Test both services
        services = [
            (self.rtmp_url, "RTMP"),
            (self.srt_url, "SRT")
        ]
        
        for url, protocol in services:
            try:
                async with httpx.AsyncClient(timeout=HEALTH_CHECK_TIMEOUT) as client:
                    response = await client.get(f"{url}/health")
                    if response.status_code == 200:
                        result = response.json()
                        if result.get('success'):
                            self.base_url = url
                            self.active_protocol = protocol.lower()
                            logger.info(f"Auto-detected active service: {protocol} at {url}")
                            return url
            except Exception as e:
                logger.debug(f"{protocol} service at {url} not available: {e}")
                continue
        
        # No service available
        raise Exception(f"No WorldStreamer service available at {self.rtmp_url} or {self.srt_url}")
    
    def _register_tools(self):
        """Register MCP tools for WorldStreamer operations."""
        
        @self.server.list_tools()
        async def handle_list_tools() -> list[Tool]:
            """List available WorldStreamer tools."""
            return [
                Tool(
                    name="worldstreamer_start_streaming",
                    description="Start Isaac Sim streaming session (auto-detects RTMP/SRT)",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "server_ip": {
                                "type": "string",
                                "description": "Optional server IP override for streaming URLs"
                            }
                        },
                        "additionalProperties": False
                    }
                ),
                Tool(
                    name="worldstreamer_stop_streaming", 
                    description="Stop active Isaac Sim streaming session (auto-detects RTMP/SRT)",
                    inputSchema={
                        "type": "object",
                        "properties": {},
                        "additionalProperties": False
                    }
                ),
                Tool(
                    name="worldstreamer_get_status",
                    description="Get current streaming status and information (auto-detects RTMP/SRT)",
                    inputSchema={
                        "type": "object",
                        "properties": {},
                        "additionalProperties": False
                    }
                ),
                Tool(
                    name="worldstreamer_get_streaming_urls",
                    description="Get streaming client URLs for connection (auto-detects RTMP/SRT)",
                    inputSchema={
                        "type": "object", 
                        "properties": {
                            "server_ip": {
                                "type": "string",
                                "description": "Optional server IP override for streaming URLs"
                            }
                        },
                        "additionalProperties": False
                    }
                ),
                Tool(
                    name="worldstreamer_validate_environment",
                    description="Validate Isaac Sim environment for streaming (auto-detects RTMP/SRT)",
                    inputSchema={
                        "type": "object",
                        "properties": {},
                        "additionalProperties": False
                    }
                ),
                Tool(
                    name="worldstreamer_health_check", 
                    description="Check WorldStreamer extension health and connectivity (auto-detects RTMP/SRT)",
                    inputSchema={
                        "type": "object",
                        "properties": {},
                        "additionalProperties": False
                    }
                )
            ]
    
    def _register_handlers(self):
        """Register MCP request handlers."""
        
        @self.server.call_tool()
        async def handle_call_tool(name: str, arguments: dict | None) -> list[TextContent]:
            """Handle tool execution requests."""
            if arguments is None:
                arguments = {}
            
            try:
                # Route to appropriate handler
                if name == "worldstreamer_start_streaming":
                    return await self._start_streaming(arguments)
                elif name == "worldstreamer_stop_streaming":
                    return await self._stop_streaming(arguments)
                elif name == "worldstreamer_get_status":
                    return await self._get_status(arguments)
                elif name == "worldstreamer_get_streaming_urls":
                    return await self._get_streaming_urls(arguments)
                elif name == "worldstreamer_validate_environment":
                    return await self._validate_environment(arguments)
                elif name == "worldstreamer_health_check":
                    return await self._health_check(arguments)
                else:
                    return [TextContent(
                        type="text",
                        text=f"Unknown tool: {name}"
                    )]
                    
            except Exception as e:
                logger.error(f"Tool execution error for {name}: {e}")
                return [TextContent(
                    type="text",
                    text=f"Tool execution failed: {str(e)}"
                )]
    
    async def _start_streaming(self, arguments: dict) -> list[TextContent]:
        """Start streaming session (auto-detects RTMP/SRT)."""
        try:
            # Auto-detect active service
            base_url = await self._detect_active_service()
            
            async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
                response = await client.post(
                    f"{base_url}/streaming/start",
                    json=arguments
                )
                response.raise_for_status()
                result = response.json()
                
                if result.get('success'):
                    # Format successful response with protocol info
                    protocol_name = self.active_protocol.upper() if self.active_protocol != "manual" else "Streaming"
                    message_lines = [f"✅ **{protocol_name} Streaming Started Successfully**", ""]
                    
                    if 'streaming_info' in result:
                        info = result['streaming_info']
                        port_label = f"**{protocol_name} Port:**" if protocol_name != "Streaming" else "**Port:**"
                        message_lines.extend([
                            f"{port_label} {info.get('rtmp_port', info.get('port', 'unknown'))}",
                            f"**FPS:** {info.get('fps', 'unknown')}",
                            f"**Resolution:** {info.get('resolution', 'unknown')}",
                            f"**Start Time:** {info.get('start_time', 'unknown')}", 
                            ""
                        ])
                        
                        if 'urls' in info:
                            urls = info['urls']
                            message_lines.append("**Streaming URLs:**")
                            if 'rtmp_stream_url' in urls:
                                message_lines.append(f"• RTMP Stream: {urls['rtmp_stream_url']}")
                            if 'local_network_rtmp_url' in urls:
                                message_lines.append(f"• Local Network: {urls['local_network_rtmp_url']}")
                            if 'public_rtmp_url' in urls:
                                message_lines.append(f"• Public: {urls['public_rtmp_url']}")
                            if 'client_urls' in urls and 'obs_studio' in urls['client_urls']:
                                message_lines.append(f"• OBS Studio: {urls['client_urls']['obs_studio']}")
                            message_lines.append("")
                            
                            if 'recommendations' in urls:
                                message_lines.append("**Recommendations:**")
                                for rec in urls['recommendations']:
                                    message_lines.append(f"• {rec}")
                    
                    return [TextContent(type="text", text="\n".join(message_lines))]
                else:
                    return [TextContent(
                        type="text",
                        text=f"❌ **Streaming Start Failed**\n\nError: {result.get('error', 'Unknown error')}"
                    )]
                    
        except httpx.HTTPError as e:
            logger.error(f"HTTP error starting streaming: {e}")
            return [TextContent(
                type="text", 
                text=f"❌ **HTTP Error**\n\nFailed to start streaming: {str(e)}"
            )]
        except Exception as e:
            logger.error(f"Error starting streaming: {e}")
            return [TextContent(
                type="text",
                text=f"❌ **Error**\n\nFailed to start streaming: {str(e)}"
            )]
    
    async def _stop_streaming(self, arguments: dict) -> list[TextContent]:
        """Stop streaming session (auto-detects RTMP/SRT)."""
        try:
            # Auto-detect active service
            base_url = await self._detect_active_service()
            
            async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
                response = await client.post(f"{base_url}/streaming/stop")
                response.raise_for_status()
                result = response.json()
                
                if result.get('success'):
                    # Format successful response
                    message_lines = ["✅ **Streaming Stopped Successfully**", ""]
                    
                    if 'session_info' in result:
                        info = result['session_info'] 
                        message_lines.extend([
                            f"**Duration:** {info.get('duration_seconds', 'unknown')} seconds",
                            f"**Stop Time:** {info.get('stop_time', 'unknown')}"
                        ])
                    
                    return [TextContent(type="text", text="\n".join(message_lines))]
                else:
                    return [TextContent(
                        type="text",
                        text=f"❌ **Streaming Stop Failed**\n\nError: {result.get('error', 'Unknown error')}"
                    )]
                    
        except httpx.HTTPError as e:
            logger.error(f"HTTP error stopping streaming: {e}")
            return [TextContent(
                type="text",
                text=f"❌ **HTTP Error**\n\nFailed to stop streaming: {str(e)}"
            )]
        except Exception as e:
            logger.error(f"Error stopping streaming: {e}")
            return [TextContent(
                type="text", 
                text=f"❌ **Error**\n\nFailed to stop streaming: {str(e)}"
            )]
    
    async def _get_status(self, arguments: dict) -> list[TextContent]:
        """Get streaming status (auto-detects RTMP/SRT)."""
        try:
            # Auto-detect active service
            base_url = await self._detect_active_service()
            
            async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
                response = await client.get(f"{base_url}/streaming/status")
                response.raise_for_status()
                result = response.json()
                
                if result.get('success'):
                    status = result.get('status', {})
                    
                    # Format status response with protocol info
                    protocol_name = self.active_protocol.upper() if self.active_protocol != "manual" else "Streaming"
                    message_lines = [f"📊 **{protocol_name} Streaming Status**", ""]
                    message_lines.extend([
                        f"**Protocol:** {protocol_name}",
                        f"**State:** {status.get('state', 'unknown')}",
                        f"**Active:** {'Yes' if status.get('is_active') else 'No'}",
                        f"**Port:** {status.get('port', 'unknown')}"
                    ])
                    
                    if status.get('is_active') and status.get('uptime_seconds'):
                        uptime = status['uptime_seconds']
                        hours = int(uptime // 3600)
                        minutes = int((uptime % 3600) // 60)
                        seconds = int(uptime % 60)
                        message_lines.append(f"**Uptime:** {hours:02d}:{minutes:02d}:{seconds:02d}")
                    
                    if status.get('is_error') and status.get('error_message'):
                        message_lines.extend(["", f"**Error:** {status['error_message']}"])
                    
                    if status.get('urls'):
                        urls = status['urls']
                        message_lines.extend(["", "**URLs:**"])
                        for key, url in urls.items():
                            if key.endswith('_url') and url:
                                name = key.replace('_url', '').replace('_', ' ').title()
                                message_lines.append(f"• {name}: {url}")
                    
                    return [TextContent(type="text", text="\n".join(message_lines))]
                else:
                    return [TextContent(
                        type="text",
                        text=f"❌ **Status Check Failed**\n\nError: {result.get('error', 'Unknown error')}"
                    )]
                    
        except httpx.HTTPError as e:
            logger.error(f"HTTP error getting status: {e}")
            return [TextContent(
                type="text",
                text=f"❌ **HTTP Error**\n\nFailed to get status: {str(e)}"
            )]
        except Exception as e:
            logger.error(f"Error getting status: {e}")
            return [TextContent(
                type="text",
                text=f"❌ **Error**\n\nFailed to get status: {str(e)}"
            )]
    
    async def _get_streaming_urls(self, arguments: dict) -> list[TextContent]:
        """Get streaming URLs (auto-detects RTMP/SRT)."""
        try:
            # Auto-detect active service
            base_url = await self._detect_active_service()
            
            params = {}
            if 'server_ip' in arguments:
                params['server_ip'] = arguments['server_ip']
            
            async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
                response = await client.get(
                    f"{base_url}/streaming/urls",
                    params=params
                )
                response.raise_for_status()
                result = response.json()
                
                if result.get('success'):
                    urls = result.get('urls', {})
                    
                    # Format URLs response
                    message_lines = ["🔗 **Streaming URLs**", ""]
                    
                    # Protocol-specific URL mappings
                    if self.active_protocol == "rtmp":
                        url_mapping = {
                            'rtmp_stream_url': 'RTMP Stream',
                            'local_network_rtmp_url': 'Local Network RTMP',
                            'public_rtmp_url': 'Public RTMP'
                        }
                    else:  # SRT
                        url_mapping = {
                            'srt_uri': 'SRT Stream'
                        }
                    
                    for key, label in url_mapping.items():
                        if key in urls and urls[key]:
                            message_lines.append(f"**{label}:** {urls[key]}")
                    
                    if 'connection_info' in urls:
                        info = urls['connection_info']
                        message_lines.extend(["", "**Connection Info:**"])
                        message_lines.append(f"• Protocol: {info.get('protocol', 'unknown')}")
                        message_lines.append(f"• Port: {info.get('port', 'unknown')}")
                        if 'local_ip' in info:
                            message_lines.append(f"• Local IP: {info['local_ip']}")
                        if 'public_ip' in info:
                            message_lines.append(f"• Public IP: {info['public_ip']}")
                    
                    if 'recommendations' in urls:
                        message_lines.extend(["", "**Recommendations:**"])
                        for rec in urls['recommendations']:
                            message_lines.append(f"• {rec}")
                    
                    return [TextContent(type="text", text="\n".join(message_lines))]
                else:
                    return [TextContent(
                        type="text",
                        text=f"❌ **URL Generation Failed**\n\nError: {result.get('error', 'Unknown error')}"
                    )]
                    
        except httpx.HTTPError as e:
            logger.error(f"HTTP error getting URLs: {e}")
            return [TextContent(
                type="text",
                text=f"❌ **HTTP Error**\n\nFailed to get URLs: {str(e)}"
            )]
        except Exception as e:
            logger.error(f"Error getting URLs: {e}")
            return [TextContent(
                type="text",
                text=f"❌ **Error**\n\nFailed to get URLs: {str(e)}"
            )]
    
    async def _validate_environment(self, arguments: dict) -> list[TextContent]:
        """Validate streaming environment (auto-detects RTMP/SRT)."""
        try:
            # Auto-detect active service
            base_url = await self._detect_active_service()
            
            async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
                response = await client.get(f"{base_url}/streaming/environment/validate")
                response.raise_for_status()
                result = response.json()
                
                if result.get('success'):
                    validation = result.get('validation', {})
                    
                    # Format validation response
                    status_icon = "✅" if validation.get('valid') else "⚠️"
                    message_lines = [f"{status_icon} **Environment Validation**", ""]
                    message_lines.append(f"**Valid:** {'Yes' if validation.get('valid') else 'No'}")
                    
                    if validation.get('errors'):
                        message_lines.extend(["", "**Errors:**"])
                        for error in validation['errors']:
                            message_lines.append(f"❌ {error}")
                    
                    if validation.get('warnings'):
                        message_lines.extend(["", "**Warnings:**"])
                        for warning in validation['warnings']:
                            message_lines.append(f"⚠️ {warning}")
                    
                    if validation.get('recommendations'):
                        message_lines.extend(["", "**Recommendations:**"])
                        for rec in validation['recommendations']:
                            message_lines.append(f"💡 {rec}")
                    
                    if validation.get('environment_details'):
                        details = validation['environment_details']
                        message_lines.extend(["", "**Environment Details:**"])
                        for key, value in details.items():
                            formatted_key = key.replace('_', ' ').title()
                            message_lines.append(f"• {formatted_key}: {value}")
                    
                    return [TextContent(type="text", text="\n".join(message_lines))]
                else:
                    return [TextContent(
                        type="text",
                        text=f"❌ **Validation Failed**\n\nError: {result.get('error', 'Unknown error')}"
                    )]
                    
        except httpx.HTTPError as e:
            logger.error(f"HTTP error validating environment: {e}")
            return [TextContent(
                type="text",
                text=f"❌ **HTTP Error**\n\nFailed to validate environment: {str(e)}"
            )]
        except Exception as e:
            logger.error(f"Error validating environment: {e}")
            return [TextContent(
                type="text",
                text=f"❌ **Error**\n\nFailed to validate environment: {str(e)}"
            )]
    
    async def _health_check(self, arguments: dict) -> list[TextContent]:
        """Check extension health (auto-detects RTMP/SRT)."""
        try:
            # Auto-detect active service
            base_url = await self._detect_active_service()
            
            async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
                response = await client.get(f"{base_url}/health")
                response.raise_for_status()
                result = response.json()
                
                if result.get('success'):
                    # Unified agent world health format: success=true indicates healthy
                    status = "healthy" if result.get('success') else "unhealthy"
                    status_icon = "✅"
                    protocol_name = self.active_protocol.upper() if self.active_protocol != "manual" else "WorldStreamer"
                    
                    message_lines = [f"{status_icon} **{protocol_name} Health Check**", ""]
                    message_lines.extend([
                        f"**Service:** {result.get('service', 'WorldStreamer')} ({protocol_name})",
                        f"**Version:** {result.get('version', 'unknown')}",
                        f"**Status:** {status.title()}",
                        f"**URL:** {base_url}",
                        f"**Timestamp:** {result.get('timestamp', 'unknown')}"
                    ])
                    
                    # Note: Unified agent world health format is simple - no complex details
                    
                    return [TextContent(type="text", text="\n".join(message_lines))]
                else:
                    return [TextContent(
                        type="text",
                        text=f"❌ **Health Check Failed**\n\nError: {result.get('error', 'Unknown error')}"
                    )]
                    
        except httpx.HTTPError as e:
            logger.error(f"HTTP error in health check: {e}")
            return [TextContent(
                type="text",
                text=f"❌ **HTTP Error**\n\nHealth check failed: {str(e)}"
            )]
        except Exception as e:
            logger.error(f"Error in health check: {e}")
            return [TextContent(
                type="text",
                text=f"❌ **Error**\n\nHealth check failed: {str(e)}"
            )]

# Server instance
server_instance = None

async def main():
    """Main server entry point."""
    global server_instance
    
    # Get base URL from environment (optional override)
    import os
    base_url = os.getenv("WORLDSTREAMER_BASE_URL")  # None if not set - enables auto-detection
    
    # Get version from centralized config
    try:
        from . import __version__ as server_version
    except ImportError:
        server_version = "0.1.0"  # Fallback
    
    # Create and run server (auto-detection mode if base_url is None)
    server_instance = WorldStreamerMCPServer(base_url=base_url)
    
    # Run the server
    from mcp.server.stdio import stdio_server
    
    async with stdio_server() as (read_stream, write_stream):
        await server_instance.server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="worldstreamer-server",
                server_version=server_version,
                capabilities=server_instance.server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={}
                )
            )
        )

if __name__ == "__main__":
    asyncio.run(main())