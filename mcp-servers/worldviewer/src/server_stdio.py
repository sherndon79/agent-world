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
                name="worldviewer_frame_object",
                description="Frame an object in the Isaac Sim viewport",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "object_path": {"type": "string", "description": "USD path to the object (e.g., '/World/my_cube')"},
                        "distance": {"type": "number", "description": "Optional distance from object (auto-calculated if not provided)"}
                    },
                    "required": ["object_path"]
                }
            ),
            Tool(
                name="worldviewer_orbit_camera",
                description="Orbit camera around a target point or object",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "target": {"type": "array", "items": {"type": "number"}, "description": "Target point [x, y, z] or object USD path"},
                        "radius": {"type": "number", "description": "Orbit radius"},
                        "speed": {"type": "number", "description": "Orbit speed (degrees per second)"},
                        "duration": {"type": "number", "description": "Orbit duration in seconds"}
                    },
                    "required": ["target"]
                }
            ),
            Tool(
                name="worldviewer_get_camera_status",
                description="Get current camera status and position",
                inputSchema={"type": "object", "properties": {}}
            ),
            Tool(
                name="worldviewer_get_asset_transform",
                description="Get transform information for assets in Isaac Sim scene",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "asset_path": {"type": "string", "description": "USD path to the asset (e.g., '/World/my_asset')"}
                    },
                    "required": ["asset_path"]
                }
            ),

            # Cinematic Movement Tools
            Tool(
                name="worldviewer_smooth_move",
                description="Smoothly move camera to new position with optional target",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "position": {"type": "array", "items": {"type": "number"}, "description": "Target camera position [x, y, z]"},
                        "target": {"type": "array", "items": {"type": "number"}, "description": "Optional look-at target [x, y, z]"},
                        "duration": {"type": "number", "description": "Movement duration in seconds"},
                        "easing": {"type": "string", "description": "Easing function (linear, ease-in, ease-out, ease-in-out)"}
                    },
                    "required": ["position"]
                }
            ),
            Tool(
                name="worldviewer_arc_shot",
                description="Create cinematic arc shot movement",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "start_position": {"type": "array", "items": {"type": "number"}, "description": "Starting camera position [x, y, z]"},
                        "end_position": {"type": "array", "items": {"type": "number"}, "description": "Ending camera position [x, y, z]"},
                        "target": {"type": "array", "items": {"type": "number"}, "description": "Target to look at during arc [x, y, z]"},
                        "arc_height": {"type": "number", "description": "Height of the arc"},
                        "duration": {"type": "number", "description": "Arc shot duration in seconds"}
                    },
                    "required": ["start_position", "end_position", "target"]
                }
            ),
            Tool(
                name="worldviewer_orbit_shot",
                description="Create cinematic orbital shot around target",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "target": {"type": "array", "items": {"type": "number"}, "description": "Target center point [x, y, z]"},
                        "radius": {"type": "number", "description": "Orbit radius"},
                        "start_angle": {"type": "number", "description": "Starting angle in degrees"},
                        "end_angle": {"type": "number", "description": "Ending angle in degrees"},
                        "height_offset": {"type": "number", "description": "Camera height offset from target"},
                        "duration": {"type": "number", "description": "Orbit duration in seconds"}
                    },
                    "required": ["target"]
                }
            ),
            Tool(
                name="worldviewer_stop_movement",
                description="Stop all camera movement and transitions",
                inputSchema={"type": "object", "properties": {}}
            ),
            Tool(
                name="worldviewer_movement_status",
                description="Get current camera movement status",
                inputSchema={"type": "object", "properties": {}}
            ),

            # Queue Management Tools
            Tool(
                name="worldviewer_get_queue_status",
                description="Get current camera operation queue status",
                inputSchema={"type": "object", "properties": {}}
            ),
            Tool(
                name="worldviewer_play_queue",
                description="Start playing queued camera operations",
                inputSchema={"type": "object", "properties": {}}
            ),
            Tool(
                name="worldviewer_pause_queue",
                description="Pause current camera operation queue",
                inputSchema={"type": "object", "properties": {}}
            ),
            Tool(
                name="worldviewer_stop_queue",
                description="Stop and clear camera operation queue",
                inputSchema={"type": "object", "properties": {}}
            ),

            # System Tools
            Tool(
                name="worldviewer_health_check",
                description="Check Agent WorldViewer extension health and API status",
                inputSchema={"type": "object", "properties": {}}
            ),
            Tool(
                name="worldviewer_get_metrics",
                description="Get performance metrics and statistics from WorldViewer extension",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "format": {"type": "string", "description": "Output format (json or prom)"}
                    },
                    "required": []
                }
            ),
            Tool(
                name="worldviewer_metrics_prometheus",
                description="Get WorldViewer metrics in Prometheus format for monitoring systems",
                inputSchema={"type": "object", "properties": {}}
            )
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