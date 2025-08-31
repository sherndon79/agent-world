#!/usr/bin/env python3
"""
MCP Server for WorldSurveyor - Spatial selection and waypoint management

Provides MCP tools for creating, managing, and organizing spatial waypoints
in Isaac Sim for AI-collaborative 3D scene creation.

Key Features:
- Create waypoints at specified positions with different types
- List and filter waypoints by type and location
- Manage spatial selections and click-to-create mode
- Search for waypoints near positions
- Clear and organize waypoint collections

This server communicates with the WorldSurveyor Isaac Sim extension via HTTP API
to provide natural language access to spatial selection capabilities.
"""

import asyncio
import json
import logging
import os
import sys
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

import httpx
from mcp.server import Server
from mcp.server.models import InitializationOptions
from mcp.server.stdio import stdio_server
from mcp.server.lowlevel import NotificationOptions
from mcp.types import Resource, Tool, TextContent, ImageContent, EmbeddedResource
import mcp.types as types


# Configure logging with environment-based paths
log_dir = os.getenv('AGENT_WORLD_LOG_DIR', '/tmp')
log_file = os.path.join(log_dir, 'mcp_worldsurveyor.log')

# Ensure log directory exists
os.makedirs(log_dir, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler(sys.stderr)
    ]
)
logger = logging.getLogger("mcp-worldsurveyor")


class WorldSurveyorMCP:
    """
    MCP server for WorldSurveyor spatial selection and waypoint management.
    
    Provides natural language interface to WorldSurveyor extension running in Isaac Sim.
    Enables creation, management, and organization of spatial waypoints for AI-collaborative
    3D scene creation workflows.
    """
    
    def __init__(self, base_url: str = "http://localhost:8891"):
        """
        Initialize WorldSurveyor MCP server.
        
        Args:
            base_url: Base URL of WorldSurveyor HTTP API
        """
        self.base_url = base_url.rstrip('/')
        self.server = Server("worldsurveyor")
        
        # HTTP client for API calls
        self.client = httpx.AsyncClient(timeout=30.0)
        
        # Register tools
        self._register_tools()
        
        logger.info(f"WorldSurveyor MCP initialized with base_url: {self.base_url}")
    
    def _register_tools(self):
        """Register MCP tools for WorldSurveyor functionality."""
        
        @self.server.list_tools()
        async def handle_list_tools() -> List[Tool]:
            """List available WorldSurveyor tools."""
            return [
                Tool(
                    name="worldsurveyor_create_waypoint",
                    description="Create a new spatial waypoint at specified position with type and metadata",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "position": {
                                "type": "array",
                                "items": {"type": "number"},
                                "minItems": 3,
                                "maxItems": 3,
                                "description": "3D position [x, y, z] for the waypoint"
                            },
                            "waypoint_type": {
                                "type": "string",
                                "enum": [
                                    "camera_position",
                                    "directional_lighting",
                                    "object_anchor", 
                                    "point_of_interest",
                                    "selection_mark",
                                    "lighting_position",
                                    "audio_source",
                                    "spawn_point"
                                ],
                                "default": "point_of_interest",
                                "description": "Type of waypoint to create"
                            },
                            "name": {
                                "type": "string",
                                "description": "Optional custom name for the waypoint"
                            },
                            "target": {
                                "type": "array",
                                "items": {"type": "number"},
                                "minItems": 3,
                                "maxItems": 3,
                                "default": [0.0, 0.0, 0.0],
                                "description": "Optional target coordinates [x, y, z] for camera positioning"
                            },
                            "metadata": {
                                "type": "object",
                                "description": "Optional additional metadata for the waypoint"
                            }
                        },
                        "required": ["position"],
                        "additionalProperties": False
                    }
                ),
                Tool(
                    name="worldsurveyor_list_waypoints",
                    description="List all waypoints with optional filtering by type",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "waypoint_type": {
                                "type": "string",
                                "enum": [
                                    "camera_position",
                                    "directional_lighting",
                                    "object_anchor",
                                    "point_of_interest", 
                                    "selection_mark",
                                    "lighting_position",
                                    "audio_source",
                                    "spawn_point"
                                ],
                                "description": "Optional filter by waypoint type"
                            }
                        },
                        "additionalProperties": False
                    }
                ),
                Tool(
                    name="worldsurveyor_health_check",
                    description="Check WorldSurveyor extension health and API status",
                    inputSchema={
                        "type": "object",
                        "additionalProperties": False
                    }
                ),
                Tool(
                    name="worldsurveyor_set_markers_visible",
                    description="Show or hide waypoint markers in the 3D scene for better spatial context",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "visible": {
                                "type": "boolean",
                                "description": "Whether to show (true) or hide (false) waypoint markers"
                            }
                        },
                        "required": ["visible"],
                        "additionalProperties": False
                    }
                ),
                Tool(
                    name="worldsurveyor_debug_status",
                    description="Get debug draw system status and marker information",
                    inputSchema={
                        "type": "object",
                        "additionalProperties": False
                    }
                ),
                Tool(
                    name="worldsurveyor_update_waypoint",
                    description="Update waypoint name, notes, or metadata for better organization and AI context",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "waypoint_id": {
                                "type": "string",
                                "description": "ID of the waypoint to update"
                            },
                            "name": {
                                "type": "string",
                                "description": "New name for the waypoint (optional)"
                            },
                            "notes": {
                                "type": "string",
                                "description": "Notes/comments about this waypoint (optional)"
                            },
                            "metadata": {
                                "type": "object",
                                "description": "Additional metadata to merge (optional)"
                            }
                        },
                        "required": ["waypoint_id"],
                        "additionalProperties": False
                    }
                ),
                Tool(
                    name="worldsurveyor_clear_all_waypoints",
                    description="Clear all waypoints from the scene - use with caution as this cannot be undone",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "confirm": {
                                "type": "boolean",
                                "description": "Must be set to true to confirm the destructive operation",
                                "default": False
                            }
                        },
                        "required": ["confirm"],
                        "additionalProperties": False
                    }
                ),
                Tool(
                    name="worldsurveyor_remove_waypoint",
                    description="Remove a specific waypoint from the scene by ID",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "waypoint_id": {
                                "type": "string",
                                "description": "ID of the waypoint to remove"
                            }
                        },
                        "required": ["waypoint_id"],
                        "additionalProperties": False
                    }
                ),
                Tool(
                    name="worldsurveyor_set_individual_marker_visible",
                    description="Show or hide a specific waypoint marker in the 3D scene",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "waypoint_id": {
                                "type": "string",
                                "description": "ID of the waypoint marker to show/hide"
                            },
                            "visible": {
                                "type": "boolean",
                                "description": "Whether to show (true) or hide (false) the marker"
                            }
                        },
                        "required": ["waypoint_id", "visible"],
                        "additionalProperties": False
                    }
                ),
                Tool(
                    name="worldsurveyor_set_selective_markers_visible",
                    description="Show only specific waypoints while hiding all others - useful for focusing on subset of waypoints",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "visible_waypoint_ids": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "List of waypoint IDs to show (all others will be hidden)"
                            }
                        },
                        "required": ["visible_waypoint_ids"],
                        "additionalProperties": False
                    }
                ),
                Tool(
                    name="worldsurveyor_get_metrics",
                    description="Get API and system metrics for monitoring WorldSurveyor extension performance",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "format": {
                                "type": "string",
                                "enum": ["json", "prom"],
                                "default": "json",
                                "description": "Output format - json for structured data or prom for Prometheus format"
                            }
                        },
                        "additionalProperties": False
                    }
                ),
                
                # Group Management Tools
                Tool(
                    name="worldsurveyor_create_group",
                    description="Create a new waypoint group for hierarchical organization",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "name": {
                                "type": "string",
                                "description": "Name of the group"
                            },
                            "description": {
                                "type": "string",
                                "description": "Optional description of the group"
                            },
                            "parent_group_id": {
                                "type": "string",
                                "description": "Optional parent group ID for nested groups"
                            },
                            "color": {
                                "type": "string",
                                "default": "#4A90E2",
                                "description": "Optional color for the group (hex format)"
                            }
                        },
                        "required": ["name"],
                        "additionalProperties": False
                    }
                ),
                Tool(
                    name="worldsurveyor_list_groups",
                    description="List waypoint groups with optional parent filtering",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "parent_group_id": {
                                "type": "string",
                                "description": "Optional parent group ID to filter children"
                            }
                        },
                        "additionalProperties": False
                    }
                ),
                Tool(
                    name="worldsurveyor_get_group",
                    description="Get detailed information about a specific group",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "group_id": {
                                "type": "string",
                                "description": "ID of the group to get information about"
                            }
                        },
                        "required": ["group_id"],
                        "additionalProperties": False
                    }
                ),
                Tool(
                    name="worldsurveyor_get_group_hierarchy",
                    description="Get complete group hierarchy as nested structure",
                    inputSchema={
                        "type": "object",
                        "additionalProperties": False
                    }
                ),
                Tool(
                    name="worldsurveyor_remove_group",
                    description="Remove a waypoint group - use with caution",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "group_id": {
                                "type": "string",
                                "description": "ID of the group to remove"
                            },
                            "cascade": {
                                "type": "boolean",
                                "default": False,
                                "description": "Whether to remove child groups (destructive operation)"
                            }
                        },
                        "required": ["group_id"],
                        "additionalProperties": False
                    }
                ),
                Tool(
                    name="worldsurveyor_add_waypoint_to_groups",
                    description="Add a waypoint to one or more groups for organization",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "waypoint_id": {
                                "type": "string",
                                "description": "ID of the waypoint to add to groups"
                            },
                            "group_ids": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "List of group IDs to add the waypoint to"
                            }
                        },
                        "required": ["waypoint_id", "group_ids"],
                        "additionalProperties": False
                    }
                ),
                Tool(
                    name="worldsurveyor_remove_waypoint_from_groups",
                    description="Remove a waypoint from one or more groups",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "waypoint_id": {
                                "type": "string",
                                "description": "ID of the waypoint to remove from groups"
                            },
                            "group_ids": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "List of group IDs to remove the waypoint from"
                            }
                        },
                        "required": ["waypoint_id", "group_ids"],
                        "additionalProperties": False
                    }
                ),
                Tool(
                    name="worldsurveyor_get_waypoint_groups",
                    description="Get all groups that contain a specific waypoint",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "waypoint_id": {
                                "type": "string",
                                "description": "ID of the waypoint to get group memberships for"
                            }
                        },
                        "required": ["waypoint_id"],
                        "additionalProperties": False
                    }
                ),
                Tool(
                    name="worldsurveyor_get_group_waypoints",
                    description="Get all waypoints in a specific group",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "group_id": {
                                "type": "string",
                                "description": "ID of the group to get waypoints from"
                            },
                            "include_nested": {
                                "type": "boolean",
                                "default": False,
                                "description": "Whether to include waypoints from nested child groups"
                            }
                        },
                        "required": ["group_id"],
                        "additionalProperties": False
                    }
                ),
                Tool(
                    name="worldsurveyor_export_waypoints",
                    description="Export waypoints and groups to JSON format for backup or transfer",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "include_groups": {
                                "type": "boolean",
                                "default": True,
                                "description": "Whether to include group information in export"
                            }
                        },
                        "additionalProperties": False
                    }
                ),
                Tool(
                    name="worldsurveyor_import_waypoints",
                    description="Import waypoints and groups from JSON format - use with caution",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "import_data": {
                                "type": "object",
                                "description": "JSON data structure containing waypoints and groups to import"
                            },
                            "merge_mode": {
                                "type": "string",
                                "enum": ["replace", "append"],
                                "default": "replace",
                                "description": "Whether to replace existing data or append to it"
                            }
                        },
                        "required": ["import_data"],
                        "additionalProperties": False
                    }
                ),
                Tool(
                    name="worldsurveyor_goto_waypoint",
                    description="Navigate camera to a specific waypoint for quick spatial reference",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "waypoint_id": {
                                "type": "string",
                                "description": "ID of the waypoint to navigate to"
                            }
                        },
                        "required": ["waypoint_id"],
                        "additionalProperties": False
                    }
                ),
                Tool(
                    name="worldsurveyor_health",
                    description="Check WorldSurveyor extension health and connectivity status",
                    inputSchema={
                        "type": "object",
                        "properties": {},
                        "additionalProperties": False
                    }
                ),
                Tool(
                    name="worldsurveyor_metrics",
                    description="Get WorldSurveyor metrics in JSON format for monitoring and analysis",
                    inputSchema={
                        "type": "object", 
                        "properties": {
                            "format": {
                                "type": "string",
                                "enum": ["json"],
                                "default": "json",
                                "description": "Output format (JSON only for this endpoint)"
                            }
                        },
                        "additionalProperties": False
                    }
                ),
                Tool(
                    name="worldsurveyor_metrics_prometheus",
                    description="Get WorldSurveyor metrics in Prometheus format for monitoring systems",
                    inputSchema={
                        "type": "object",
                        "properties": {},
                        "additionalProperties": False
                    }
                )
            ]
        
        @self.server.call_tool()
        async def handle_call_tool(name: str, arguments: Dict[str, Any]) -> List[types.TextContent]:
            """Handle tool calls for WorldSurveyor operations."""
            try:
                logger.info(f"🔧 Calling tool: {name} with args: {arguments}")
                
                if name == "worldsurveyor_create_waypoint":
                    return await self._create_waypoint(arguments)
                elif name == "worldsurveyor_list_waypoints":
                    return await self._list_waypoints(arguments)
                elif name == "worldsurveyor_health_check":
                    return await self._health_check(arguments)
                elif name == "worldsurveyor_set_markers_visible":
                    return await self._set_markers_visible(arguments)
                elif name == "worldsurveyor_debug_status":
                    return await self._debug_status(arguments)
                elif name == "worldsurveyor_update_waypoint":
                    return await self._update_waypoint(arguments)
                elif name == "worldsurveyor_clear_all_waypoints":
                    return await self._clear_all_waypoints(arguments)
                elif name == "worldsurveyor_remove_waypoint":
                    return await self._remove_waypoint(arguments)
                elif name == "worldsurveyor_set_individual_marker_visible":
                    return await self._set_individual_marker_visible(arguments)
                elif name == "worldsurveyor_set_selective_markers_visible":
                    return await self._set_selective_markers_visible(arguments)
                elif name == "worldsurveyor_get_metrics":
                    return await self._get_metrics(arguments)
                
                # Group management tools
                elif name == "worldsurveyor_create_group":
                    return await self._create_group(arguments)
                elif name == "worldsurveyor_list_groups":
                    return await self._list_groups(arguments)
                elif name == "worldsurveyor_get_group":
                    return await self._get_group(arguments)
                elif name == "worldsurveyor_get_group_hierarchy":
                    return await self._get_group_hierarchy(arguments)
                elif name == "worldsurveyor_remove_group":
                    return await self._remove_group(arguments)
                elif name == "worldsurveyor_add_waypoint_to_groups":
                    return await self._add_waypoint_to_groups(arguments)
                elif name == "worldsurveyor_remove_waypoint_from_groups":
                    return await self._remove_waypoint_from_groups(arguments)
                elif name == "worldsurveyor_get_waypoint_groups":
                    return await self._get_waypoint_groups(arguments)
                elif name == "worldsurveyor_get_group_waypoints":
                    return await self._get_group_waypoints(arguments)
                elif name == "worldsurveyor_export_waypoints":
                    return await self._export_waypoints(arguments)
                elif name == "worldsurveyor_import_waypoints":
                    return await self._import_waypoints(arguments)
                elif name == "worldsurveyor_goto_waypoint":
                    return await self._goto_waypoint(arguments)
                elif name == "worldsurveyor_health":
                    return await self._health(arguments)
                elif name == "worldsurveyor_metrics":
                    return await self._metrics(arguments)
                elif name == "worldsurveyor_metrics_prometheus":
                    return await self._metrics_prometheus(arguments)
                
                else:
                    return [types.TextContent(
                        type="text",
                        text=f"❌ Unknown tool: {name}"
                    )]
                    
            except Exception as e:
                logger.error(f"❌ Error in tool {name}: {e}")
                return [types.TextContent(
                    type="text", 
                    text=f"❌ Error calling {name}: {str(e)}"
                )]
    
    async def _create_waypoint(self, args: Dict[str, Any]) -> List[types.TextContent]:
        """Create a new waypoint."""
        try:
            response = await self.client.post(
                f"{self.base_url}/waypoints/create",
                json=args,
                timeout=10.0
            )
            result = response.json()
            
            if result.get('success'):
                waypoint_id = result.get('waypoint_id', 'unknown')
                position = args.get('position', [0, 0, 0])
                waypoint_type = args.get('waypoint_type', 'point_of_interest')
                name = args.get('name', 'Auto-generated')
                
                return [types.TextContent(
                    type="text",
                    text=f"📍 **Waypoint Created Successfully!**\n\n"
                         f"• **ID:** {waypoint_id}\n"
                         f"• **Name:** {name}\n"
                         f"• **Type:** {waypoint_type.replace('_', ' ').title()}\n"
                         f"• **Position:** [{position[0]:.2f}, {position[1]:.2f}, {position[2]:.2f}]\n"
                         f"• **Status:** {result.get('message', 'Ready for use')}"
                )]
            else:
                return [types.TextContent(
                    type="text",
                    text=f"❌ Failed to create waypoint: {result.get('error', 'Unknown error')}"
                )]
                
        except httpx.RequestError as e:
            return [types.TextContent(
                type="text",
                text=f"❌ Connection error: {str(e)}"
            )]
        except Exception as e:
            return [types.TextContent(
                type="text",
                text=f"❌ Error creating waypoint: {str(e)}"
            )]
    
    async def _list_waypoints(self, args: Dict[str, Any]) -> List[types.TextContent]:
        """List waypoints with optional filtering."""
        try:
            params = {}
            if 'waypoint_type' in args:
                params['waypoint_type'] = args['waypoint_type']
            
            response = await self.client.get(
                f"{self.base_url}/waypoints/list",
                params=params,
                timeout=10.0
            )
            result = response.json()
            
            if result.get('success'):
                waypoints = result.get('waypoints', [])
                count = result.get('count', 0)
                
                if count == 0:
                    filter_text = f" of type '{args.get('waypoint_type', 'any')}'" if 'waypoint_type' in args else ""
                    return [types.TextContent(
                        type="text",
                        text=f"📍 No waypoints found{filter_text}"
                    )]
                
                # Format waypoint list
                waypoint_lines = []
                for waypoint in waypoints:
                    pos = waypoint.get('position', [0, 0, 0])
                    target = waypoint.get('target', [0, 0, 0])
                    waypoint_type = waypoint.get('waypoint_type', 'unknown').replace('_', ' ').title()
                    name = waypoint.get('name', 'Unnamed')
                    waypoint_id = waypoint.get('id', 'unknown')
                    
                    # For waypoints with target (camera_position and directional_lighting), show both position and target
                    if waypoint.get('waypoint_type') in ['camera_position', 'directional_lighting']:
                        waypoint_lines.append(
                            f"• **{name}** ({waypoint_type}) [ID: {waypoint_id}]\n"
                            f"  Position: [{pos[0]:.2f}, {pos[1]:.2f}, {pos[2]:.2f}]\n"
                            f"  Target: [{target[0]:.2f}, {target[1]:.2f}, {target[2]:.2f}]"
                        )
                    else:
                        waypoint_lines.append(
                            f"• {name} ({waypoint_type}) at [{pos[0]:.2f}, {pos[1]:.2f}, {pos[2]:.2f}] [ID: {waypoint_id}]"
                        )
                
                filter_text = f" (filtered by {args.get('waypoint_type', 'any')})" if 'waypoint_type' in args else ""
                
                return [types.TextContent(
                    type="text",
                    text=f"📍 Found {count} waypoint(s){filter_text}:\n\n" + "\n".join(waypoint_lines)
                )]
            else:
                return [types.TextContent(
                    type="text",
                    text=f"❌ Failed to list waypoints: {result.get('error', 'Unknown error')}"
                )]
                
        except httpx.RequestError as e:
            return [types.TextContent(
                type="text",
                text=f"❌ Connection error: {str(e)}"
            )]
        except Exception as e:
            return [types.TextContent(
                type="text",
                text=f"❌ Error listing waypoints: {str(e)}"
            )]
    
    async def _health_check(self, args: Dict[str, Any]) -> List[types.TextContent]:
        """Check WorldSurveyor health status."""
        try:
            response = await self.client.get(
                f"{self.base_url}/health",
                timeout=10.0
            )
            result = response.json()
            
            if result.get('success'):
                service = result.get('service', 'Unknown')
                version = result.get('version', 'Unknown')
                url = result.get('url', 'Unknown')
                timestamp = result.get('timestamp', 'Unknown')
                waypoint_count = result.get('waypoint_count', 0)
                
                return [types.TextContent(
                    type="text",
                    text=f"✅ WorldSurveyor Health\n"
                         f"• Service: {service}\n"
                         f"• Version: {version}\n"
                         f"• URL: {url}\n"
                         f"• Timestamp: {timestamp}\n"
                         f"• Waypoint Count: {waypoint_count}"
                )]
            else:
                return [types.TextContent(
                    type="text",
                    text=f"❌ Health check failed: {result.get('error', 'Unknown error')}"
                )]
                
        except Exception as e:
            return [types.TextContent(
                type="text",
                text=f"🔌 **Connection Failed - Agent WorldSurveyor**\n\n"
                     f"❌ **Error:** {str(e)}\n\n"
                     f"💡 **Troubleshooting:**\n"
                     f"• Ensure Isaac Sim is running\n"
                     f"• Enable WorldSurveyor extension in Extension Manager\n"
                     f"• Verify API is running on: {self.base_url}\n"
                     f"• Check Isaac Sim logs for extension errors"
            )]
    
    async def _set_markers_visible(self, args: Dict[str, Any]) -> List[types.TextContent]:
        """Set waypoint marker visibility in the 3D scene."""
        try:
            visible = args['visible']
            
            payload = {"visible": visible}
            response = await self.client.post(
                f"{self.base_url}/markers/visible",
                json=payload,
                timeout=10.0
            )
            result = response.json()
            
            if result.get('success'):
                status = "shown" if visible else "hidden"
                return [types.TextContent(
                    type="text",
                    text=f"👁️ Waypoint markers {status} successfully\n\n"
                         f"🎯 **Visual Context:** Waypoint markers provide spatial reference in the 3D scene\n"
                         f"• Red points: Camera position waypoints\n"
                         f"• Blue points: Points of interest\n"
                         f"• Green points: Asset placement markers\n"
                         f"• Markers are visible: {'✅ Yes' if visible else '❌ No'}"
                )]
            else:
                return [types.TextContent(
                    type="text",
                    text=f"❌ Failed to set marker visibility: {result.get('error', 'Unknown error')}"
                )]
                
        except httpx.RequestError as e:
            return [types.TextContent(
                type="text",
                text=f"❌ Connection error: {str(e)}"
            )]
        except Exception as e:
            return [types.TextContent(
                type="text",
                text=f"❌ Error setting marker visibility: {str(e)}"
            )]
    
    async def _debug_status(self, args: Dict[str, Any]) -> List[types.TextContent]:
        """Get debug draw system status and marker information."""
        try:
            response = await self.client.get(
                f"{self.base_url}/markers/debug",
                timeout=10.0
            )
            result = response.json()
            
            if result.get('success'):
                debug_status = result.get('debug_status', {})
                waypoint_count = result.get('waypoint_count', 0)
                
                available = debug_status.get('available', False)
                num_points = debug_status.get('num_points', 0)
                markers_visible = debug_status.get('markers_visible', False)
                tracked_markers = debug_status.get('tracked_markers', 0)
                
                status_text = "🔍 **Debug Draw System Status**\n\n"
                status_text += f"• Debug Draw Available: {'✅ Yes' if available else '❌ No'}\n"
                
                if available:
                    status_text += f"• Active Debug Points: {num_points}\n"
                    status_text += f"• Waypoint Markers Visible: {'✅ Yes' if markers_visible else '❌ No'}\n"
                    status_text += f"• Tracked Markers: {tracked_markers}\n"
                    status_text += f"• Total Waypoints: {waypoint_count}\n\n"
                    
                    if not markers_visible and waypoint_count > 0:
                        status_text += "💡 **Tip:** Use `worldsurveyor_set_markers_visible` to show waypoint markers for better spatial context"
                else:
                    error = debug_status.get('error', 'Unknown error')
                    status_text += f"• Error: {error}\n\n"
                    status_text += "💡 **Troubleshooting:**\n"
                    status_text += "• Ensure `isaacsim.util.debug_draw` extension is enabled\n"
                    status_text += "• Check Isaac Sim Extension Manager"
                
                return [types.TextContent(
                    type="text",
                    text=status_text
                )]
            else:
                return [types.TextContent(
                    type="text",
                    text=f"❌ Failed to get debug status: {result.get('error', 'Unknown error')}"
                )]
                
        except httpx.RequestError as e:
            return [types.TextContent(
                type="text",
                text=f"❌ Connection error: {str(e)}"
            )]
        except Exception as e:
            return [types.TextContent(
                type="text",
                text=f"❌ Error getting debug status: {str(e)}"
            )]
    
    async def _update_waypoint(self, args: Dict[str, Any]) -> List[types.TextContent]:
        """Update waypoint name, notes, or metadata."""
        try:
            waypoint_id = args.get('waypoint_id')
            if not waypoint_id:
                return [types.TextContent(
                    type="text",
                    text="❌ Error: waypoint_id is required"
                )]
            
            response = await self.client.post(
                f"{self.base_url}/waypoints/update",
                json=args,
                timeout=10.0
            )
            result = response.json()
            
            if result.get('success'):
                waypoint = result.get('waypoint', {})
                notes = waypoint.get('metadata', {}).get('notes', '')
                notes_text = f"\nNotes: {notes}" if notes else ""
                
                return [types.TextContent(
                    type="text",
                    text=f"✅ Waypoint {waypoint_id} updated successfully\n"
                         f"Name: {waypoint.get('name', 'Unknown')}"
                         f"{notes_text}"
                )]
            else:
                return [types.TextContent(
                    type="text",
                    text=f"❌ Error updating waypoint: {result.get('error', 'Unknown error')}"
                )]
                
        except httpx.RequestError as e:
            return [types.TextContent(
                type="text",
                text=f"❌ Connection error: {str(e)}"
            )]
        except Exception as e:
            return [types.TextContent(
                type="text",
                text=f"❌ Error updating waypoint: {str(e)}"
            )]
    
    async def _clear_all_waypoints(self, args: Dict[str, Any]) -> List[types.TextContent]:
        """Clear all waypoints from the scene."""
        try:
            confirm = args.get('confirm', False)
            if not confirm:
                return [types.TextContent(
                    type="text",
                    text="⚠️ **Confirmation Required**\n\n"
                         "This operation will permanently delete ALL waypoints from the scene.\n"
                         "To proceed, call this tool with `confirm: true`.\n\n"
                         "This action cannot be undone!"
                )]
            
            response = await self.client.post(
                f"{self.base_url}/waypoints/clear",
                json={"confirm": True},
                timeout=10.0
            )
            result = response.json()
            
            if result.get('success'):
                cleared_count = result.get('cleared_count', 0)
                return [types.TextContent(
                    type="text",
                    text=f"🧹 **All Waypoints Cleared Successfully**\n\n"
                         f"• **Waypoints Removed:** {cleared_count}\n"
                         f"• **Scene Status:** Clean slate ready for new waypoints\n"
                         f"• **Markers:** All visual markers removed from 3D scene\n\n"
                         f"✨ The scene is now ready for fresh spatial planning!"
                )]
            else:
                return [types.TextContent(
                    type="text",
                    text=f"❌ Failed to clear waypoints: {result.get('error', 'Unknown error')}"
                )]
                
        except Exception as e:
            return [types.TextContent(
                type="text",
                text=f"❌ Error clearing waypoints: {str(e)}"
            )]
    
    async def _remove_waypoint(self, args: Dict[str, Any]) -> List[types.TextContent]:
        """Remove a specific waypoint from the scene."""
        try:
            waypoint_id = args.get('waypoint_id')
            if not waypoint_id:
                return [types.TextContent(
                    type="text",
                    text="❌ Error: waypoint_id is required"
                )]
            
            response = await self.client.post(
                f"{self.base_url}/waypoints/remove",
                json={"waypoint_id": waypoint_id},
                timeout=10.0
            )
            result = response.json()
            
            if result.get('success'):
                return [types.TextContent(
                    type="text",
                    text=f"🗑️ **Waypoint Removed Successfully**\n\n"
                         f"• **Waypoint ID:** {waypoint_id}\n"
                         f"• **Status:** {result.get('message', 'Waypoint removed from scene')}\n"
                         f"• **Marker:** Visual marker cleared from 3D scene"
                )]
            else:
                return [types.TextContent(
                    type="text",
                    text=f"❌ Failed to remove waypoint: {result.get('error', 'Unknown error')}"
                )]
                
        except Exception as e:
            return [types.TextContent(
                type="text",
                text=f"❌ Error removing waypoint: {str(e)}"
            )]
    
    async def _set_individual_marker_visible(self, args: Dict[str, Any]) -> List[types.TextContent]:
        """Show or hide a specific waypoint marker."""
        try:
            waypoint_id = args.get('waypoint_id')
            visible = args.get('visible')
            
            if not waypoint_id:
                return [types.TextContent(
                    type="text",
                    text="❌ Error: waypoint_id is required"
                )]
            
            if visible is None:
                return [types.TextContent(
                    type="text",
                    text="❌ Error: visible parameter is required"
                )]
            
            response = await self.client.post(
                f"{self.base_url}/markers/individual",
                json={"waypoint_id": waypoint_id, "visible": visible},
                timeout=10.0
            )
            result = response.json()
            
            if result.get('success'):
                status = "shown" if visible else "hidden"
                return [types.TextContent(
                    type="text",
                    text=f"👁️ **Individual Marker {status.title()}**\n\n"
                         f"• **Waypoint ID:** {waypoint_id}\n"
                         f"• **Marker Status:** {status.title()}\n"
                         f"• **Message:** {result.get('message', f'Marker {status}')}"
                )]
            else:
                return [types.TextContent(
                    type="text",
                    text=f"❌ Failed to set marker visibility: {result.get('error', 'Unknown error')}"
                )]
                
        except httpx.RequestError as e:
            return [types.TextContent(
                type="text",
                text=f"❌ Connection error: {str(e)}"
            )]
        except Exception as e:
            return [types.TextContent(
                type="text",
                text=f"❌ Error setting marker visibility: {str(e)}"
            )]
    
    async def _set_selective_markers_visible(self, args: Dict[str, Any]) -> List[types.TextContent]:
        """Show only specific waypoints while hiding all others."""
        try:
            visible_waypoint_ids = args.get('visible_waypoint_ids', [])
            
            if not isinstance(visible_waypoint_ids, list):
                return [types.TextContent(
                    type="text",
                    text="❌ Error: visible_waypoint_ids must be an array"
                )]
            
            if len(visible_waypoint_ids) == 0:
                return [types.TextContent(
                    type="text",
                    text="❌ Error: at least one waypoint ID must be provided"
                )]
            
            response = await self.client.post(
                f"{self.base_url}/markers/selective",
                json={"visible_waypoint_ids": visible_waypoint_ids},
                timeout=10.0
            )
            result = response.json()
            
            if result.get('success'):
                return [types.TextContent(
                    type="text",
                    text=f"🎯 **Selective Visibility Activated**\n\n"
                         f"• **Visible Waypoints:** {len(visible_waypoint_ids)}\n"
                         f"• **Waypoint IDs:** {', '.join(visible_waypoint_ids[:5])}{'...' if len(visible_waypoint_ids) > 5 else ''}\n"
                         f"• **Mode:** Selective visibility (all other waypoints hidden)\n"
                         f"• **Status:** {result.get('message', 'Selective mode activated')}"
                )]
            else:
                return [types.TextContent(
                    type="text",
                    text=f"❌ Failed to set selective visibility: {result.get('error', 'Unknown error')}"
                )]
                
        except Exception as e:
            return [types.TextContent(
                type="text",
                text=f"❌ Error setting selective visibility: {str(e)}"
            )]
    
    async def _get_metrics(self, args: Dict[str, Any]) -> List[types.TextContent]:
        """Get API and system metrics for monitoring."""
        try:
            format_type = args.get('format', 'json')
            
            params = {}
            if format_type == 'prom':
                params['format'] = 'prom'
            
            response = await self.client.get(
                f"{self.base_url}/metrics",
                params=params,
                timeout=10.0
            )
            result = response.json()
            
            if result.get('success'):
                metrics = result.get('metrics', {})
                
                if format_type == 'prom' and 'prometheus' in metrics:
                    # Return Prometheus format
                    return [types.TextContent(
                        type="text",
                        text=f"📊 **WorldSurveyor Metrics (Prometheus Format)**\n\n"
                             f"```\n{metrics['prometheus']}\n```"
                    )]
                else:
                    # Return JSON format with formatted display
                    api_metrics = metrics.get('api', {})
                    waypoint_metrics = metrics.get('waypoints', {})
                    
                    uptime_seconds = api_metrics.get('uptime_seconds', 0)
                    uptime_minutes = int(uptime_seconds // 60)
                    uptime_hours = int(uptime_minutes // 60)
                    uptime_display = f"{uptime_hours}h {uptime_minutes % 60}m {uptime_seconds % 60:.0f}s"
                    
                    success_rate = 0
                    total_requests = api_metrics.get('requests_received', 0)
                    if total_requests > 0:
                        success_rate = (api_metrics.get('successful_requests', 0) / total_requests) * 100
                    
                    return [types.TextContent(
                        type="text",
                        text=f"📊 **WorldSurveyor System Metrics**\n\n"
                             f"🔌 **API Performance:**\n"
                             f"• **Total Requests:** {total_requests:,}\n"
                             f"• **Successful:** {api_metrics.get('successful_requests', 0):,}\n"
                             f"• **Failed:** {api_metrics.get('failed_requests', 0):,}\n"
                             f"• **Success Rate:** {success_rate:.1f}%\n"
                             f"• **Server Port:** {api_metrics.get('port', 'Unknown')}\n"
                             f"• **Uptime:** {uptime_display}\n"
                             f"• **Status:** {'🟢 Running' if api_metrics.get('server_running', False) else '🔴 Stopped'}\n\n"
                             f"📍 **Waypoint Storage:**\n"
                             f"• **Total Waypoints:** {waypoint_metrics.get('count', 0):,}\n\n"
                             f"⏱️ **Last Updated:** {result.get('timestamp', 'Unknown')}"
                    )]
            else:
                return [types.TextContent(
                    type="text",
                    text=f"❌ Failed to get metrics: {result.get('error', 'Unknown error')}"
                )]
                
        except Exception as e:
            return [types.TextContent(
                type="text",
                text=f"❌ Error getting metrics: {str(e)}"
            )]
    
    # =====================================================================
    # GROUP MANAGEMENT METHODS
    # =====================================================================
    
    async def _create_group(self, args: Dict[str, Any]) -> List[types.TextContent]:
        """Create a new waypoint group."""
        try:
            name = args.get('name')
            if not name:
                return [types.TextContent(
                    type="text",
                    text="❌ Error: Group name is required"
                )]
            
            response = await self.client.post(
                f"{self.base_url}/groups/create",
                json=args,
                timeout=10.0
            )
            result = response.json()
            
            if result.get('success'):
                group_id = result.get('group_id', 'unknown')
                parent_text = f" (child of {args.get('parent_group_id')})" if args.get('parent_group_id') else ""
                
                return [types.TextContent(
                    type="text",
                    text=f"📁 **Group Created Successfully!**\n\n"
                         f"• **Group ID:** {group_id}\n"
                         f"• **Name:** {name}\n"
                         f"• **Description:** {args.get('description', 'No description')}\n"
                         f"• **Color:** {args.get('color', '#4A90E2')}\n"
                         f"• **Hierarchy:** {'Root level' if not args.get('parent_group_id') else f'Child group{parent_text}'}\n"
                         f"• **Status:** {result.get('message', 'Ready for waypoint organization')}"
                )]
            else:
                return [types.TextContent(
                    type="text",
                    text=f"❌ Failed to create group: {result.get('error', 'Unknown error')}"
                )]
                
        except Exception as e:
            return [types.TextContent(
                type="text",
                text=f"❌ Error creating group: {str(e)}"
            )]
    
    async def _list_groups(self, args: Dict[str, Any]) -> List[types.TextContent]:
        """List waypoint groups with optional parent filtering."""
        try:
            params = {}
            if 'parent_group_id' in args:
                params['parent_group_id'] = args['parent_group_id']
            
            response = await self.client.get(
                f"{self.base_url}/groups/list",
                params=params,
                timeout=10.0
            )
            result = response.json()
            
            if result.get('success'):
                groups = result.get('groups', [])
                count = result.get('count', 0)
                
                if count == 0:
                    filter_text = f" under parent '{args.get('parent_group_id')}'" if 'parent_group_id' in args else ""
                    return [types.TextContent(
                        type="text",
                        text=f"📁 No groups found{filter_text}"
                    )]
                
                # Format group list
                group_lines = []
                for group in groups:
                    name = group.get('name', 'Unnamed')
                    description = group.get('description', '')
                    color = group.get('color', '#4A90E2')
                    desc_text = f" - {description}" if description else ""
                    
                    group_lines.append(
                        f"• {name} (ID: {group.get('id', 'unknown')}) {color}{desc_text}"
                    )
                
                filter_text = f" (children of {args.get('parent_group_id')})" if 'parent_group_id' in args else " (root level)" if 'parent_group_id' not in args else ""
                
                return [types.TextContent(
                    type="text",
                    text=f"📁 Found {count} group(s){filter_text}:\n\n" + "\n".join(group_lines)
                )]
            else:
                return [types.TextContent(
                    type="text",
                    text=f"❌ Failed to list groups: {result.get('error', 'Unknown error')}"
                )]
                
        except Exception as e:
            return [types.TextContent(
                type="text",
                text=f"❌ Error listing groups: {str(e)}"
            )]
    
    async def _get_group(self, args: Dict[str, Any]) -> List[types.TextContent]:
        """Get detailed information about a specific group."""
        try:
            group_id = args.get('group_id')
            if not group_id:
                return [types.TextContent(type="text", text="❌ Error: group_id required")]
            
            response = await self.client.get(
                f"{self.base_url}/groups/get",
                params={'group_id': group_id},
                timeout=10.0
            )
            result = response.json()
            
            if result.get('success'):
                group = result.get('group', {})
                name = group.get('name', 'Unnamed')
                description = group.get('description', 'No description')
                color = group.get('color', '#4A90E2')
                parent_id = group.get('parent_group_id', 'None')
                created = group.get('created_at', 'Unknown')
                waypoint_count = group.get('waypoint_count', 0)
                
                return [types.TextContent(
                    type="text",
                    text=f"📁 **Group Details: {name}**\n\n" +
                         f"• ID: {group_id}\n" +
                         f"• Description: {description}\n" +
                         f"• Color: {color}\n" +
                         f"• Parent Group: {parent_id}\n" +
                         f"• Created: {created}\n" +
                         f"• Waypoints: {waypoint_count}"
                )]
            else:
                return [types.TextContent(
                    type="text",
                    text=f"❌ Failed to get group: {result.get('error', 'Unknown error')}"
                )]
                
        except Exception as e:
            return [types.TextContent(
                type="text",
                text=f"❌ Error listing groups: {str(e)}"
            )]
    
    async def _get_group_hierarchy(self, args: Dict[str, Any]) -> List[types.TextContent]:
        """Get complete group hierarchy as nested structure."""
        try:
            response = await self.client.get(
                f"{self.base_url}/groups/hierarchy",
                timeout=10.0
            )
            result = response.json()
            
            if result.get('success'):
                hierarchy = result.get('hierarchy', [])
                total_groups = result.get('total_groups', 0)
                
                if total_groups == 0:
                    return [types.TextContent(
                        type="text",
                        text="📁 No groups found. Create groups to organize your waypoints hierarchically."
                    )]
                
                # Format hierarchy tree
                def format_hierarchy(groups, indent=0):
                    lines = []
                    prefix = "  " * indent
                    for group in groups:
                        name = group.get('name', 'Unnamed')
                        group_id = group.get('id', 'unknown')
                        description = group.get('description', '')
                        desc_text = f" - {description}" if description else ""
                        
                        lines.append(f"{prefix}📁 {name} (ID: {group_id}){desc_text}")
                        
                        # Add children recursively
                        children = group.get('children', [])
                        if children:
                            lines.extend(format_hierarchy(children, indent + 1))
                    
                    return lines
                
                hierarchy_lines = format_hierarchy(hierarchy)
                
                return [types.TextContent(
                    type="text",
                    text=f"🌳 **Group Hierarchy** ({total_groups} total groups)\n\n" + "\n".join(hierarchy_lines)
                )]
            else:
                return [types.TextContent(
                    type="text",
                    text=f"❌ Failed to get group hierarchy: {result.get('error', 'Unknown error')}"
                )]
                
        except Exception as e:
            return [types.TextContent(
                type="text",
                text=f"❌ Error getting group hierarchy: {str(e)}"
            )]
    
    async def _remove_group(self, args: Dict[str, Any]) -> List[types.TextContent]:
        """Remove a waypoint group."""
        try:
            group_id = args.get('group_id')
            if not group_id:
                return [types.TextContent(
                    type="text",
                    text="❌ Error: Group ID is required"
                )]
            
            cascade = args.get('cascade', False)
            
            response = await self.client.post(
                f"{self.base_url}/groups/remove",
                json={"group_id": group_id, "cascade": cascade},
                timeout=10.0
            )
            result = response.json()
            
            if result.get('success'):
                cascade_text = " and all child groups" if cascade else ""
                return [types.TextContent(
                    type="text",
                    text=f"🗑️ **Group Removed Successfully**\n\n"
                         f"• **Group ID:** {group_id}\n"
                         f"• **Cascade:** {'Yes' if cascade else 'No'}{cascade_text}\n"
                         f"• **Status:** {result.get('message', 'Group removed from organization')}\n"
                         f"• **Waypoints:** Unassigned from removed group(s)"
                )]
            else:
                return [types.TextContent(
                    type="text",
                    text=f"❌ Failed to remove group: {result.get('error', 'Unknown error')}"
                )]
                
        except Exception as e:
            return [types.TextContent(
                type="text",
                text=f"❌ Error removing group: {str(e)}"
            )]
    
    async def _add_waypoint_to_groups(self, args: Dict[str, Any]) -> List[types.TextContent]:
        """Add waypoint to groups."""
        try:
            waypoint_id = args.get('waypoint_id')
            group_ids = args.get('group_ids', [])
            
            if not waypoint_id:
                return [types.TextContent(
                    type="text",
                    text="❌ Error: Waypoint ID is required"
                )]
            if not group_ids:
                return [types.TextContent(
                    type="text",
                    text="❌ Error: At least one group ID is required"
                )]
            
            response = await self.client.post(
                f"{self.base_url}/groups/add_waypoint",
                json={"waypoint_id": waypoint_id, "group_ids": group_ids},
                timeout=10.0
            )
            result = response.json()
            
            if result.get('success'):
                added_count = result.get('added_to_groups', 0)
                return [types.TextContent(
                    type="text",
                    text=f"📍➕ **Waypoint Added to Groups**\n\n"
                         f"• **Waypoint ID:** {waypoint_id}\n"
                         f"• **Groups Added:** {added_count}/{len(group_ids)}\n"
                         f"• **Group IDs:** {', '.join(group_ids)}\n"
                         f"• **Status:** {result.get('message', 'Waypoint organized into groups')}"
                )]
            else:
                return [types.TextContent(
                    type="text",
                    text=f"❌ Failed to add waypoint to groups: {result.get('error', 'Unknown error')}"
                )]
                
        except Exception as e:
            return [types.TextContent(
                type="text",
                text=f"❌ Error adding waypoint to groups: {str(e)}"
            )]
    
    async def _remove_waypoint_from_groups(self, args: Dict[str, Any]) -> List[types.TextContent]:
        """Remove waypoint from groups."""
        try:
            waypoint_id = args.get('waypoint_id')
            group_ids = args.get('group_ids', [])
            
            if not waypoint_id:
                return [types.TextContent(
                    type="text",
                    text="❌ Error: Waypoint ID is required"
                )]
            if not group_ids:
                return [types.TextContent(
                    type="text",
                    text="❌ Error: At least one group ID is required"
                )]
            
            response = await self.client.post(
                f"{self.base_url}/groups/remove_waypoint",
                json={"waypoint_id": waypoint_id, "group_ids": group_ids},
                timeout=10.0
            )
            result = response.json()
            
            if result.get('success'):
                removed_count = result.get('removed_from_groups', 0)
                return [types.TextContent(
                    type="text",
                    text=f"📍➖ **Waypoint Removed from Groups**\n\n"
                         f"• **Waypoint ID:** {waypoint_id}\n"
                         f"• **Groups Removed:** {removed_count}/{len(group_ids)}\n"
                         f"• **Group IDs:** {', '.join(group_ids)}\n"
                         f"• **Status:** {result.get('message', 'Waypoint unassigned from groups')}"
                )]
            else:
                return [types.TextContent(
                    type="text",
                    text=f"❌ Failed to remove waypoint from groups: {result.get('error', 'Unknown error')}"
                )]
                
        except Exception as e:
            return [types.TextContent(
                type="text",
                text=f"❌ Error removing waypoint from groups: {str(e)}"
            )]
    
    async def _get_waypoint_groups(self, args: Dict[str, Any]) -> List[types.TextContent]:
        """Get all groups that contain a waypoint."""
        try:
            waypoint_id = args.get('waypoint_id')
            if not waypoint_id:
                return [types.TextContent(
                    type="text",
                    text="❌ Error: Waypoint ID is required"
                )]
            
            response = await self.client.get(
                f"{self.base_url}/groups/of_waypoint",
                params={"waypoint_id": waypoint_id},
                timeout=10.0
            )
            result = response.json()
            
            if result.get('success'):
                groups = result.get('groups', [])
                count = result.get('count', 0)
                
                if count == 0:
                    return [types.TextContent(
                        type="text",
                        text=f"📍 Waypoint {waypoint_id} is not assigned to any groups"
                    )]
                
                # Format group memberships
                group_lines = []
                for group in groups:
                    name = group.get('name', 'Unnamed')
                    description = group.get('description', '')
                    desc_text = f" - {description}" if description else ""
                    
                    group_lines.append(f"• {name} (ID: {group.get('id', 'unknown')}){desc_text}")
                
                return [types.TextContent(
                    type="text",
                    text=f"📍 **Waypoint Group Memberships**\n\n"
                         f"• **Waypoint ID:** {waypoint_id}\n"
                         f"• **Member of {count} group(s):**\n\n" + "\n".join(group_lines)
                )]
            else:
                return [types.TextContent(
                    type="text",
                    text=f"❌ Failed to get waypoint groups: {result.get('error', 'Unknown error')}"
                )]
                
        except Exception as e:
            return [types.TextContent(
                type="text",
                text=f"❌ Error getting waypoint groups: {str(e)}"
            )]
    
    async def _get_group_waypoints(self, args: Dict[str, Any]) -> List[types.TextContent]:
        """Get all waypoints in a group."""
        try:
            group_id = args.get('group_id')
            if not group_id:
                return [types.TextContent(
                    type="text",
                    text="❌ Error: Group ID is required"
                )]
            
            include_nested = args.get('include_nested', False)
            
            response = await self.client.get(
                f"{self.base_url}/groups/waypoints",
                params={"group_id": group_id, "include_nested": include_nested},
                timeout=10.0
            )
            result = response.json()
            
            if result.get('success'):
                waypoints = result.get('waypoints', [])
                count = result.get('count', 0)
                
                if count == 0:
                    nested_text = " (including nested groups)" if include_nested else ""
                    return [types.TextContent(
                        type="text",
                        text=f"📁 Group {group_id} contains no waypoints{nested_text}"
                    )]
                
                # Format waypoint list
                waypoint_lines = []
                for waypoint in waypoints:
                    pos = waypoint.get('position', [0, 0, 0])
                    waypoint_type = waypoint.get('waypoint_type', 'unknown').replace('_', ' ').title()
                    name = waypoint.get('name', 'Unnamed')
                    waypoint_id = waypoint.get('id', 'unknown')
                    
                    waypoint_lines.append(
                        f"• {name} ({waypoint_type}) at [{pos[0]:.2f}, {pos[1]:.2f}, {pos[2]:.2f}] (ID: {waypoint_id})"
                    )
                
                nested_text = f" (including nested groups)" if include_nested else ""
                
                return [types.TextContent(
                    type="text",
                    text=f"📁 **Group Contents**\n\n"
                         f"• **Group ID:** {group_id}\n"
                         f"• **Waypoints:** {count}{nested_text}\n\n" + "\n".join(waypoint_lines)
                )]
            else:
                return [types.TextContent(
                    type="text",
                    text=f"❌ Failed to get group waypoints: {result.get('error', 'Unknown error')}"
                )]
                
        except Exception as e:
            return [types.TextContent(
                type="text",
                text=f"❌ Error getting group waypoints: {str(e)}"
            )]
    
    async def _export_waypoints(self, args: Dict[str, Any]) -> List[types.TextContent]:
        """Export waypoints and groups to JSON."""
        try:
            include_groups = args.get('include_groups', True)
            
            response = await self.client.get(
                f"{self.base_url}/waypoints/export",
                params={"include_groups": include_groups},
                timeout=15.0
            )
            result = response.json()
            
            if result.get('success'):
                export_data = result.get('export_data', {})
                waypoint_count = result.get('waypoint_count', 0)
                group_count = result.get('group_count', 0)
                
                # Format JSON for display
                export_json = json.dumps(export_data, indent=2)
                
                groups_text = f" and {group_count} groups" if include_groups else ""
                
                return [types.TextContent(
                    type="text",
                    text=f"📤 **Waypoint Export Complete**\n\n"
                         f"• **Waypoints:** {waypoint_count}\n"
                         f"• **Groups:** {group_count if include_groups else 'Not included'}\n"
                         f"• **Export Size:** {len(export_json):,} characters\n\n"
                         f"**Exported Data:**\n```json\n{export_json[:2000]}{'...' if len(export_json) > 2000 else ''}\n```\n\n"
                         f"💾 Save this JSON data to import into other WorldSurveyor instances."
                )]
            else:
                return [types.TextContent(
                    type="text",
                    text=f"❌ Failed to export waypoints: {result.get('error', 'Unknown error')}"
                )]
                
        except Exception as e:
            return [types.TextContent(
                type="text",
                text=f"❌ Error exporting waypoints: {str(e)}"
            )]
    
    async def _import_waypoints(self, args: Dict[str, Any]) -> List[types.TextContent]:
        """Import waypoints and groups from JSON."""
        try:
            import_data = args.get('import_data')
            if not import_data:
                return [types.TextContent(
                    type="text",
                    text="❌ Error: Import data is required"
                )]
            
            merge_mode = args.get('merge_mode', 'replace')
            
            response = await self.client.post(
                f"{self.base_url}/waypoints/import",
                json={"import_data": import_data, "merge_mode": merge_mode},
                timeout=30.0  # Longer timeout for import operations
            )
            result = response.json()
            
            if result.get('success'):
                imported_waypoints = result.get('imported_waypoints', 0)
                imported_groups = result.get('imported_groups', 0)
                errors = result.get('errors', 0)
                
                error_text = f"\n• **Errors:** {errors}" if errors > 0 else ""
                
                return [types.TextContent(
                    type="text",
                    text=f"📥 **Import Complete**\n\n"
                         f"• **Mode:** {merge_mode.title()}\n"
                         f"• **Waypoints Imported:** {imported_waypoints}\n"
                         f"• **Groups Imported:** {imported_groups}{error_text}\n"
                         f"• **Status:** {result.get('message', 'Import successful')}\n\n"
                         f"🔄 Waypoint markers have been refreshed to reflect imported data."
                )]
            else:
                return [types.TextContent(
                    type="text",
                    text=f"❌ Failed to import waypoints: {result.get('error', 'Unknown error')}"
                )]
                
        except Exception as e:
            return [types.TextContent(
                type="text",
                text=f"❌ Error importing waypoints: {str(e)}"
            )]
    
    async def _goto_waypoint(self, args: Dict[str, Any]) -> List[types.TextContent]:
        """Navigate camera to a waypoint."""
        try:
            waypoint_id = args.get('waypoint_id')
            if not waypoint_id:
                return [types.TextContent(
                    type="text", 
                    text="❌ Error: waypoint_id is required"
                )]
            
            response = await self.client.post(
                f"{self.base_url}/waypoints/goto",
                json={"waypoint_id": waypoint_id},
                timeout=10.0
            )
            result = response.json()
            
            if result.get('success'):
                return [types.TextContent(
                    type="text",
                    text=f"📍 **Camera Navigation Successful!**\n\n"
                         f"• **Waypoint ID:** {waypoint_id}\n"
                         f"• **Status:** {result.get('message', 'Camera moved to waypoint')}"
                )]
            else:
                return [types.TextContent(
                    type="text",
                    text=f"❌ Failed to navigate to waypoint: {result.get('error', 'Unknown error')}"
                )]
                
        except Exception as e:
            return [types.TextContent(
                type="text",
                text=f"❌ Error navigating to waypoint: {str(e)}"
            )]
    
    async def _health(self, args: Dict[str, Any]) -> List[types.TextContent]:
        """Check WorldSurveyor health."""
        try:
            response = await self.client.get(
                f"{self.base_url}/health",
                timeout=5.0
            )
            result = response.json()
            
            if result.get('success'):
                return [types.TextContent(
                    type="text",
                    text=f"✅ **WorldSurveyor Health**\n\n"
                         f"• **Service:** {result.get('service', 'Unknown')}\n"
                         f"• **Version:** {result.get('version', 'Unknown')}\n"
                         f"• **URL:** {result.get('url', self.base_url)}\n"
                         f"• **Waypoints:** {result.get('waypoint_count', 0)}\n"
                         f"• **Timestamp:** {result.get('timestamp', 'Unknown')}"
                )]
            else:
                return [types.TextContent(
                    type="text",
                    text=f"❌ Health check failed: {result.get('error', 'Unknown error')}"
                )]
                
        except Exception as e:
            return [types.TextContent(
                type="text",
                text=f"❌ Health check error: {str(e)}"
            )]
    
    async def _metrics(self, args: Dict[str, Any]) -> List[types.TextContent]:
        """Get metrics in JSON format."""
        try:
            response = await self.client.get(
                f"{self.base_url}/metrics",
                timeout=5.0
            )
            result = response.json()
            
            if result.get('success'):
                import json
                metrics_data = result.get('metrics', {})
                return [types.TextContent(
                    type="text",
                    text=f"📊 **WorldSurveyor Metrics**\n\n```json\n{json.dumps(metrics_data, indent=2)}\n```"
                )]
            else:
                return [types.TextContent(
                    type="text",
                    text=f"❌ Failed to get metrics: {result.get('error', 'Unknown error')}"
                )]
                
        except Exception as e:
            return [types.TextContent(
                type="text",
                text=f"❌ Error getting metrics: {str(e)}"
            )]
    
    async def _metrics_prometheus(self, args: Dict[str, Any]) -> List[types.TextContent]:
        """Get metrics in Prometheus format."""
        try:
            response = await self.client.get(
                f"{self.base_url}/metrics.prom",
                timeout=5.0
            )
            
            # For Prometheus format, response is plain text
            if response.status_code == 200:
                metrics_text = response.text
                return [types.TextContent(
                    type="text",
                    text=f"📊 **WorldSurveyor Prometheus Metrics**\n\n```\n{metrics_text}\n```"
                )]
            else:
                return [types.TextContent(
                    type="text",
                    text=f"❌ Failed to get Prometheus metrics: HTTP {response.status_code}"
                )]
                
        except Exception as e:
            return [types.TextContent(
                type="text",
                text=f"❌ Error getting Prometheus metrics: {str(e)}"
            )]


async def main():
    """Main entry point for WorldSurveyor MCP server."""
    import os
    
    # Get base URL with standardized env var, fallback to legacy name, then default
    base_url = (
        os.getenv("AGENT_WORLDSURVEYOR_BASE_URL")
        or os.getenv("WORLDSURVEYOR_API_URL")
        or "http://localhost:8891"
    )
    
    # Initialize MCP server
    mcp_server = WorldSurveyorMCP(base_url)
    
    # Run the server
    try:
        async with stdio_server() as (read_stream, write_stream):
            await mcp_server.server.run(
                read_stream,
                write_stream,
                InitializationOptions(
                    server_name="worldsurveyor",
                    server_version="0.1.0",
                    capabilities=mcp_server.server.get_capabilities(
                        notification_options=NotificationOptions(),
                        experimental_capabilities={}
                    ),
                ),
            )
    finally:
        # Ensure HTTP client is closed
        try:
            await mcp_server.client.aclose()
        except Exception:
            pass


if __name__ == "__main__":
    asyncio.run(main())
