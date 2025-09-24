#!/usr/bin/env python3
"""
WorldViewer Stdio Server

Creates and configures the traditional MCP stdio server with WorldViewer tools.
"""

import logging
from mcp.server import Server
from mcp.types import Tool, TextContent

# Import tool modules
from tools import get_tool_functions, get_tool_names

logger = logging.getLogger("worldviewer")


def create_stdio_server():
    """Create and configure the WorldViewer stdio server."""
    server = Server("worldviewer")

    @server.list_tools()
    async def handle_list_tools():
        """List available WorldViewer tools."""
        return [
            # Camera Management Tools
            Tool(
                name="worldviewer_set_camera_position",
                description="Set camera position and optionally target in Isaac Sim viewport",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "position": {"type": "array", "items": {"type": "number"}, "description": "Camera position [x, y, z]"},
                        "target": {"type": "array", "items": {"type": "number"}, "description": "Look-at target [x, y, z]"},
                        "up_vector": {"type": "array", "items": {"type": "number"}, "description": "Up vector [x, y, z]"}
                    },
                    "required": ["position"]
                }
            ),
            Tool(
                name="worldviewer_get_camera_status",
                description="Get current camera status and position",
                inputSchema={"type": "object", "properties": {}}
            ),
            Tool(
                name="worldviewer_health_check",
                description="Check Agent WorldViewer extension health and API status",
                inputSchema={"type": "object", "properties": {}}
            ),
            # Add more tools as needed...
        ]

    @server.call_tool()
    async def handle_call_tool(name: str, arguments: dict):
        """Handle tool calls by delegating to appropriate tool functions."""
        logger.info(f"Calling tool: {name} with args: {arguments}")

        try:
            tool_functions = get_tool_functions()

            if name in tool_functions:
                if arguments:
                    result = await tool_functions[name](**arguments)
                else:
                    result = await tool_functions[name]()

                return [TextContent(type="text", text=str(result))]
            else:
                raise ValueError(f"Unknown tool: {name}")

        except Exception as e:
            logger.error(f"Error calling tool {name}: {e}")
            return [TextContent(type="text", text=f"Error: {str(e)}")]

    return server