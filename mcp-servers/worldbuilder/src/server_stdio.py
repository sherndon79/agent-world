#!/usr/bin/env python3
"""
WorldBuilder Stdio Server

Creates and configures the traditional MCP stdio server with WorldBuilder tools.
"""

import logging
from mcp.server import Server
from mcp.types import Tool, TextContent

# Import tool modules
from tools import get_tool_functions, get_tool_names

logger = logging.getLogger("worldbuilder")


def create_stdio_server():
    """Create and configure the WorldBuilder stdio server."""
    server = Server("worldbuilder")

    @server.list_tools()
    async def handle_list_tools():
        """List available WorldBuilder tools."""
        return [
            # Element Management Tools
            Tool(
                name="worldbuilder_add_element",
                description="Add individual 3D elements (cubes, spheres, cylinders) to Isaac Sim scene",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "element_type": {"type": "string", "description": "Type of 3D primitive"},
                        "name": {"type": "string", "description": "Unique name for the element"},
                        "position": {"type": "array", "items": {"type": "number"}, "description": "XYZ position"},
                        "color": {"type": "array", "items": {"type": "number"}, "description": "RGB color"},
                        "scale": {"type": "array", "items": {"type": "number"}, "description": "XYZ scale"},
                        "parent_path": {"type": "string", "description": "USD parent path"}
                    },
                    "required": ["element_type", "name", "position"]
                }
            ),
            Tool(
                name="worldbuilder_create_batch",
                description="Create hierarchical batches of objects (furniture sets, buildings, etc.)",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "batch_name": {"type": "string", "description": "Name for the batch/group"},
                        "elements": {"type": "array", "description": "List of elements to create"},
                        "parent_path": {"type": "string", "description": "USD parent path"}
                    },
                    "required": ["batch_name", "elements"]
                }
            ),
            Tool(
                name="worldbuilder_health_check",
                description="Check Isaac Sim WorldBuilder Extension health and API status",
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