#!/usr/bin/env python3
"""
WorldStreamer Stdio Server

Creates and configures the traditional MCP stdio server with WorldStreamer tools.
Adapts FastMCP tools to traditional stdio transport.
"""

import logging
from mcp.server import Server
from mcp.server.models import InitializationOptions
from mcp.types import Tool

# Import tool modules
from tools import streaming, system

logger = logging.getLogger("worldstreamer")


def create_stdio_server():
    """Create and configure the WorldStreamer stdio server."""
    server = Server("worldstreamer")

    # Register streaming management tools
    @server.list_tools()
    async def handle_list_tools():
        """List available WorldStreamer tools."""
        return [
            # Streaming Management Tools
            Tool(
                name="worldstreamer_start_streaming",
                description="Start SRT streaming from Isaac Sim viewport to external receivers",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "width": {"type": "integer", "description": "Stream width in pixels"},
                        "height": {"type": "integer", "description": "Stream height in pixels"},
                        "fps": {"type": "integer", "description": "Frames per second"},
                        "bitrate": {"type": "integer", "description": "Stream bitrate in kbps"},
                        "port": {"type": "integer", "description": "SRT port number"},
                    },
                    "required": []
                }
            ),
            Tool(
                name="worldstreamer_stop_streaming",
                description="Stop active SRT streaming session",
                inputSchema={"type": "object", "properties": {}}
            ),
            Tool(
                name="worldstreamer_get_status",
                description="Get current streaming status and session information",
                inputSchema={"type": "object", "properties": {}}
            ),
            Tool(
                name="worldstreamer_get_streaming_urls",
                description="Get available streaming URLs and connection details",
                inputSchema={"type": "object", "properties": {}}
            ),
            Tool(
                name="worldstreamer_validate_environment",
                description="Validate Isaac Sim environment and streaming setup",
                inputSchema={"type": "object", "properties": {}}
            ),

            # System Tools
            Tool(
                name="worldstreamer_health_check",
                description="Check WorldStreamer extension health and connectivity",
                inputSchema={"type": "object", "properties": {}}
            ),
            Tool(
                name="worldstreamer_get_metrics",
                description="Get WorldStreamer extension performance metrics and statistics",
                inputSchema={"type": "object", "properties": {}}
            ),
            Tool(
                name="worldstreamer_metrics_prometheus",
                description="Get WorldStreamer metrics in Prometheus format for monitoring systems",
                inputSchema={"type": "object", "properties": {}}
            ),
        ]

    # Register tool handlers
    @server.call_tool()
    async def handle_call_tool(name: str, arguments: dict):
        """Handle tool calls by delegating to appropriate tool functions."""
        logger.info(f"Calling tool: {name} with args: {arguments}")

        try:
            # Streaming Management Tools
            if name == "worldstreamer_start_streaming":
                return await streaming.worldstreamer_start_streaming(**arguments)
            elif name == "worldstreamer_stop_streaming":
                return await streaming.worldstreamer_stop_streaming()
            elif name == "worldstreamer_get_status":
                return await streaming.worldstreamer_get_status()
            elif name == "worldstreamer_get_streaming_urls":
                return await streaming.worldstreamer_get_streaming_urls()
            elif name == "worldstreamer_validate_environment":
                return await streaming.worldstreamer_validate_environment()

            # System Tools
            elif name == "worldstreamer_health_check":
                return await system.worldstreamer_health_check()
            elif name == "worldstreamer_get_metrics":
                return await system.worldstreamer_get_metrics()
            elif name == "worldstreamer_metrics_prometheus":
                return await system.worldstreamer_metrics_prometheus()

            else:
                raise ValueError(f"Unknown tool: {name}")

        except Exception as e:
            logger.error(f"Error calling tool {name}: {e}")
            raise

    return server