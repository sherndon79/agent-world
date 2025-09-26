#!/usr/bin/env python3
"""
worldsurveyor Stdio Server

Creates and configures the traditional MCP stdio server with worldsurveyor tools.
Adapts FastMCP tools to traditional stdio transport.
"""

import logging
from mcp.server import Server
from mcp.server.models import InitializationOptions
from mcp.types import Tool

# Import tool modules
from tools import waypoints, groups, visibility, import_export, system

logger = logging.getLogger("worldsurveyor")


def create_stdio_server():
    """Create and configure the worldsurveyor stdio server."""
    server = Server("worldsurveyor")

    # Register waypoint and surveying tools
    @server.list_tools()
    async def handle_list_tools():
        """List available worldsurveyor tools."""
        return [
            # Waypoint Management Tools
            Tool(
                name="worldsurveyor_create_waypoint",
                description="Create a new spatial waypoint at specified position with type and metadata",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "position": {"type": "array", "items": {"type": "number"}, "minItems": 3, "maxItems": 3, "description": "3D position [x, y, z]"},
                        "waypoint_type": {"type": "string", "description": "Type of waypoint"},
                        "name": {"type": "string", "description": "Optional custom name"},
                        "target": {"type": "array", "items": {"type": "number"}, "minItems": 3, "maxItems": 3, "description": "Optional target coordinates"},
                        "metadata": {"type": "object", "description": "Optional additional metadata"}
                    },
                    "required": ["position"]
                }
            ),
            Tool(
                name="worldsurveyor_list_waypoints",
                description="List all waypoints in the scene with optional filtering",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "waypoint_type": {"type": "string", "description": "Optional filter by waypoint type"},
                        "group_id": {"type": "string", "description": "Optional filter by group ID"}
                    }
                }
            ),
            Tool(
                name="worldsurveyor_remove_waypoint",
                description="Remove a waypoint from the scene",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "waypoint_id": {"type": "string", "description": "ID of the waypoint to remove"}
                    },
                    "required": ["waypoint_id"]
                }
            ),
            Tool(
                name="worldsurveyor_update_waypoint",
                description="Update waypoint properties",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "waypoint_id": {"type": "string", "description": "ID of the waypoint to update"}
                    },
                    "required": ["waypoint_id"]
                }
            ),
            Tool(
                name="worldsurveyor_goto_waypoint",
                description="Navigate camera to a specific waypoint",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "waypoint_id": {"type": "string", "description": "ID of the waypoint to navigate to"}
                    },
                    "required": ["waypoint_id"]
                }
            ),
            Tool(
                name="worldsurveyor_clear_waypoints",
                description="Clear all waypoints from the scene",
                inputSchema={"type": "object", "properties": {}}
            ),

            # Group Management Tools
            Tool(
                name="worldsurveyor_create_group",
                description="Create a new waypoint group for hierarchical organization",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "Name of the group"},
                        "parent_group_id": {"type": "string", "description": "Optional parent group ID"},
                        "description": {"type": "string", "description": "Optional description"},
                        "color": {"type": "array", "items": {"type": "number"}, "minItems": 3, "maxItems": 3, "description": "Optional color [r, g, b]"}
                    },
                    "required": ["name"]
                }
            ),
            Tool(
                name="worldsurveyor_list_groups",
                description="List all waypoint groups",
                inputSchema={"type": "object", "properties": {}}
            ),
            Tool(
                name="worldsurveyor_get_group",
                description="Get details of a specific group",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "group_id": {"type": "string", "description": "ID of the group"}
                    },
                    "required": ["group_id"]
                }
            ),
            Tool(
                name="worldsurveyor_update_group",
                description="Update group properties",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "group_id": {"type": "string", "description": "ID of the group to update"}
                    },
                    "required": ["group_id"]
                }
            ),
            Tool(
                name="worldsurveyor_remove_group",
                description="Remove a waypoint group",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "group_id": {"type": "string", "description": "ID of the group to remove"}
                    },
                    "required": ["group_id"]
                }
            ),
            Tool(
                name="worldsurveyor_clear_groups",
                description="Clear all waypoint groups",
                inputSchema={"type": "object", "properties": {}}
            ),
            Tool(
                name="worldsurveyor_get_group_waypoints",
                description="Get all waypoints in a specific group",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "group_id": {"type": "string", "description": "ID of the group"}
                    },
                    "required": ["group_id"]
                }
            ),
            Tool(
                name="worldsurveyor_add_waypoint_to_groups",
                description="Add waypoint to one or more groups",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "waypoint_id": {"type": "string", "description": "ID of the waypoint"},
                        "group_ids": {"type": "array", "items": {"type": "string"}, "description": "List of group IDs"}
                    },
                    "required": ["waypoint_id", "group_ids"]
                }
            ),
            Tool(
                name="worldsurveyor_remove_waypoint_from_groups",
                description="Remove waypoint from one or more groups",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "waypoint_id": {"type": "string", "description": "ID of the waypoint"},
                        "group_ids": {"type": "array", "items": {"type": "string"}, "description": "List of group IDs"}
                    },
                    "required": ["waypoint_id", "group_ids"]
                }
            ),
            Tool(
                name="worldsurveyor_get_group_hierarchy",
                description="Get the complete group hierarchy",
                inputSchema={"type": "object", "properties": {}}
            ),
            Tool(
                name="worldsurveyor_get_waypoint_groups",
                description="Get all groups that contain a specific waypoint",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "waypoint_id": {"type": "string", "description": "ID of the waypoint"}
                    },
                    "required": ["waypoint_id"]
                }
            ),

            # Visibility Management Tools
            Tool(
                name="worldsurveyor_set_markers_visible",
                description="Set visibility of all waypoint markers",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "visible": {"type": "boolean", "description": "Whether markers should be visible"}
                    },
                    "required": ["visible"]
                }
            ),
            Tool(
                name="worldsurveyor_set_selective_markers_visible",
                description="Set visibility of specific waypoint markers by type or group",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "visible": {"type": "boolean", "description": "Whether markers should be visible"},
                        "waypoint_type": {"type": "string", "description": "Optional filter by waypoint type"},
                        "group_id": {"type": "string", "description": "Optional filter by group ID"}
                    },
                    "required": ["visible"]
                }
            ),
            Tool(
                name="worldsurveyor_set_individual_marker_visible",
                description="Set visibility of a single waypoint marker",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "waypoint_id": {"type": "string", "description": "ID of the waypoint"},
                        "visible": {"type": "boolean", "description": "Whether marker should be visible"}
                    },
                    "required": ["waypoint_id", "visible"]
                }
            ),

            # Import/Export Tools
            Tool(
                name="worldsurveyor_export_waypoints",
                description="Export waypoints to file",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "file_path": {"type": "string", "description": "Path to export file"},
                        "format": {"type": "string", "description": "Export format"}
                    },
                    "required": ["file_path"]
                }
            ),
            Tool(
                name="worldsurveyor_import_waypoints",
                description="Import waypoints from file",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "file_path": {"type": "string", "description": "Path to import file"},
                        "merge": {"type": "boolean", "description": "Whether to merge with existing waypoints"}
                    },
                    "required": ["file_path"]
                }
            ),

            # System Tools
            Tool(
                name="worldsurveyor_health_check",
                description="Check WorldSurveyor extension health and API status",
                inputSchema={"type": "object", "properties": {}}
            ),
            Tool(
                name="worldsurveyor_get_metrics",
                description="Get WorldSurveyor extension performance metrics and statistics",
                inputSchema={"type": "object", "properties": {}}
            ),
            Tool(
                name="worldsurveyor_metrics_prometheus",
                description="Get WorldSurveyor metrics in Prometheus format for monitoring systems",
                inputSchema={"type": "object", "properties": {}}
            ),
            Tool(
                name="worldsurveyor_debug_status",
                description="Get detailed debug status information",
                inputSchema={"type": "object", "properties": {}}
            )
        ]

    # Register tool handlers
    @server.call_tool()
    async def handle_call_tool(name: str, arguments: dict):
        """Handle tool calls by delegating to appropriate tool functions."""
        logger.info(f"Calling tool: {name} with args: {arguments}")

        try:
            # Waypoint Management Tools
            if name == "worldsurveyor_create_waypoint":
                return await waypoints.worldsurveyor_create_waypoint(**arguments)
            elif name == "worldsurveyor_list_waypoints":
                return await waypoints.worldsurveyor_list_waypoints(**arguments)
            elif name == "worldsurveyor_remove_waypoint":
                return await waypoints.worldsurveyor_remove_waypoint(**arguments)
            elif name == "worldsurveyor_update_waypoint":
                return await waypoints.worldsurveyor_update_waypoint(**arguments)
            elif name == "worldsurveyor_goto_waypoint":
                return await waypoints.worldsurveyor_goto_waypoint(**arguments)
            elif name == "worldsurveyor_clear_waypoints":
                return await waypoints.worldsurveyor_clear_waypoints(**arguments)

            # Group Management Tools
            elif name == "worldsurveyor_create_group":
                return await groups.worldsurveyor_create_group(**arguments)
            elif name == "worldsurveyor_list_groups":
                return await groups.worldsurveyor_list_groups(**arguments)
            elif name == "worldsurveyor_get_group":
                return await groups.worldsurveyor_get_group(**arguments)
            elif name == "worldsurveyor_update_group":
                return await groups.worldsurveyor_update_group(**arguments)
            elif name == "worldsurveyor_remove_group":
                return await groups.worldsurveyor_remove_group(**arguments)
            elif name == "worldsurveyor_clear_groups":
                return await groups.worldsurveyor_clear_groups(**arguments)
            elif name == "worldsurveyor_get_group_waypoints":
                return await groups.worldsurveyor_get_group_waypoints(**arguments)
            elif name == "worldsurveyor_add_waypoint_to_groups":
                return await groups.worldsurveyor_add_waypoint_to_groups(**arguments)
            elif name == "worldsurveyor_remove_waypoint_from_groups":
                return await groups.worldsurveyor_remove_waypoint_from_groups(**arguments)
            elif name == "worldsurveyor_get_group_hierarchy":
                return await groups.worldsurveyor_get_group_hierarchy(**arguments)
            elif name == "worldsurveyor_get_waypoint_groups":
                return await groups.worldsurveyor_get_waypoint_groups(**arguments)

            # Visibility Management Tools
            elif name == "worldsurveyor_set_markers_visible":
                return await visibility.worldsurveyor_set_markers_visible(**arguments)
            elif name == "worldsurveyor_set_selective_markers_visible":
                return await visibility.worldsurveyor_set_selective_markers_visible(**arguments)
            elif name == "worldsurveyor_set_individual_marker_visible":
                return await visibility.worldsurveyor_set_individual_marker_visible(**arguments)

            # Import/Export Tools
            elif name == "worldsurveyor_export_waypoints":
                return await import_export.worldsurveyor_export_waypoints(**arguments)
            elif name == "worldsurveyor_import_waypoints":
                return await import_export.worldsurveyor_import_waypoints(**arguments)

            # System Tools
            elif name == "worldsurveyor_health_check":
                return await system.worldsurveyor_health_check()
            elif name == "worldsurveyor_get_metrics":
                return await system.worldsurveyor_get_metrics()
            elif name == "worldsurveyor_metrics_prometheus":
                return await system.worldsurveyor_metrics_prometheus()
            elif name == "worldsurveyor_debug_status":
                return await system.worldsurveyor_debug_status()

            else:
                raise ValueError(f"Unknown tool: {name}")

        except Exception as e:
            logger.error(f"Error calling tool {name}: {e}")
            raise

    return server