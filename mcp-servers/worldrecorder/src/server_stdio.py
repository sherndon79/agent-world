#!/usr/bin/env python3
"""
worldrecorder Stdio Server

Creates and configures the traditional MCP stdio server with worldrecorder tools.
Adapts FastMCP tools to traditional stdio transport.
"""

import logging
from mcp.server import Server
from mcp.server.models import InitializationOptions
from mcp.types import Tool

# Import tool modules
from tools import recording, capture, system

logger = logging.getLogger("worldrecorder")


def create_stdio_server():
    """Create and configure the worldrecorder stdio server."""
    server = Server("worldrecorder")

    # Register recording tools
    @server.list_tools()
    async def handle_list_tools():
        """List available worldrecorder tools."""
        return [
            # Recording Management Tools
            Tool(
                name="worldrecorder_start_video",
                description="Start continuous video recording in Isaac Sim viewport",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "output_path": {"type": "string", "description": "File path for video output"},
                        "duration_sec": {"type": "number", "description": "Recording duration in seconds"},
                        "fps": {"type": "number", "description": "Frames per second", "default": 30},
                        "width": {"type": "integer", "description": "Video width in pixels"},
                        "height": {"type": "integer", "description": "Video height in pixels"},
                        "file_type": {"type": "string", "description": "Video file format", "default": ".mp4"},
                        "session_id": {"type": "string", "description": "Recording session ID", "default": ""},
                        "show_progress": {"type": "boolean", "description": "Show recording progress", "default": false},
                        "cleanup_frames": {"type": "boolean", "description": "Clean up temporary frames", "default": true}
                    },
                    "required": ["output_path", "duration_sec"]
                }
            ),
            Tool(
                name="worldrecorder_start_recording",
                description="Start a new recording session with specified parameters",
                inputSchema={"type": "object", "properties": {}}
            ),
            Tool(
                name="worldrecorder_cancel_recording",
                description="Cancel the current recording session",
                inputSchema={"type": "object", "properties": {}}
            ),
            Tool(
                name="worldrecorder_recording_status",
                description="Get status of current recording session",
                inputSchema={"type": "object", "properties": {}}
            ),
            Tool(
                name="worldrecorder_cancel_video",
                description="Cancel current video recording",
                inputSchema={"type": "object", "properties": {}}
            ),
            Tool(
                name="worldrecorder_get_status",
                description="Get overall worldrecorder status",
                inputSchema={"type": "object", "properties": {}}
            ),

            # Frame Capture Tools
            Tool(
                name="worldrecorder_capture_frame",
                description="Capture a single frame or frame sequence from Isaac Sim viewport",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "output_path": {"type": "string", "description": "File path for image output"},
                        "duration_sec": {"type": "number", "description": "Total capture duration for sequences"},
                        "interval_sec": {"type": "number", "description": "Time between frames for sequences"},
                        "frame_count": {"type": "integer", "description": "Number of frames to capture"},
                        "width": {"type": "integer", "description": "Image width in pixels"},
                        "height": {"type": "integer", "description": "Image height in pixels"},
                        "file_type": {"type": "string", "description": "Image file format", "default": ".png"}
                    },
                    "required": ["output_path"]
                }
            ),
            Tool(
                name="worldrecorder_cleanup_frames",
                description="Clean up temporary frame files",
                inputSchema={"type": "object", "properties": {}}
            ),

            # System Tools
            Tool(
                name="worldrecorder_health_check",
                description="Check worldrecorder extension health and connectivity",
                inputSchema={"type": "object", "properties": {}}
            ),
            Tool(
                name="worldrecorder_get_metrics",
                description="Get worldrecorder extension performance metrics and statistics",
                inputSchema={"type": "object", "properties": {}}
            ),
            Tool(
                name="worldrecorder_metrics_prometheus",
                description="Get worldrecorder metrics in Prometheus format for monitoring systems",
                inputSchema={"type": "object", "properties": {}}
            )
        ]

    # Register tool handlers
    @server.call_tool()
    async def handle_call_tool(name: str, arguments: dict):
        """Handle tool calls by delegating to appropriate tool functions."""
        logger.info(f"Calling tool: {name} with args: {arguments}")

        try:
            # Recording Management Tools
            if name == "worldrecorder_start_video":
                return await recording.worldrecorder_start_video(**arguments)
            elif name == "worldrecorder_start_recording":
                return await recording.worldrecorder_start_recording(**arguments)
            elif name == "worldrecorder_cancel_recording":
                return await recording.worldrecorder_cancel_recording(**arguments)
            elif name == "worldrecorder_recording_status":
                return await recording.worldrecorder_recording_status(**arguments)
            elif name == "worldrecorder_cancel_video":
                return await recording.worldrecorder_cancel_video(**arguments)
            elif name == "worldrecorder_get_status":
                return await recording.worldrecorder_get_status(**arguments)

            # Frame Capture Tools
            elif name == "worldrecorder_capture_frame":
                return await capture.worldrecorder_capture_frame(**arguments)
            elif name == "worldrecorder_cleanup_frames":
                return await capture.worldrecorder_cleanup_frames(**arguments)

            # System Tools
            elif name == "worldrecorder_health_check":
                return await system.worldrecorder_health_check()
            elif name == "worldrecorder_get_metrics":
                return await system.worldrecorder_get_metrics()
            elif name == "worldrecorder_metrics_prometheus":
                return await system.worldrecorder_metrics_prometheus()

            else:
                raise ValueError(f"Unknown tool: {name}")

        except Exception as e:
            logger.error(f"Error calling tool {name}: {e}")
            raise

    return server