#!/usr/bin/env python3
"""
Isaac Sim WorldBuilder MCP Server

Provides Claude Code with direct Isaac Sim worldbuilding capabilities through MCP tools.
Interfaces with the Agent WorldBuilder Extension HTTP API running on localhost:8899.
"""

import asyncio
import json
import logging
from typing import Any, Dict, List
from mcp.server import Server
from mcp.server.models import InitializationOptions
from mcp.server.stdio import stdio_server
from mcp.server.lowlevel import NotificationOptions
from mcp.types import Tool
import mcp.types as types
import aiohttp
import sys
import os
from logging_setup import setup_logging

# Add shared modules to path
shared_path = os.path.join(os.path.dirname(__file__), '..', '..', 'shared')
if shared_path not in sys.path:
    sys.path.insert(0, shared_path)

try:
    from worldbuilder_config import get_config
    config = get_config()
except ImportError:
    # Fallback if shared config not available
    config = None

# Import unified auth client
from mcp_base_client import MCPBaseClient

# Import Pydantic compatibility utilities
try:
    from pydantic_compat import (
        create_compatible_position_schema,
        create_compatible_color_schema,
        create_compatible_scale_schema,
        PYDANTIC_VERSION
    )
    HAS_COMPAT = True
except ImportError:
    HAS_COMPAT = False
    PYDANTIC_VERSION = 1
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('worldbuilder-mcp')


def create_element_schemas():
    """Create element schemas compatible with target environment."""
    if HAS_COMPAT:
        return {
            "position": create_compatible_position_schema("XYZ position [x, y, z] in world coordinates"),
            "color": create_compatible_color_schema("RGB color [r, g, b] values between 0-1"),
            "scale": create_compatible_scale_schema("XYZ scale [x, y, z] multipliers")
        }
    else:
        # Fallback to basic schemas without v2 constraints
        return {
            "position": {
                "type": "array",
                "items": {"type": "number"},
                "description": "XYZ position [x, y, z] in world coordinates (exactly 3 items required)"
            },
            "color": {
                "type": "array",
                "items": {"type": "number", "minimum": 0, "maximum": 1},
                "description": "RGB color [r, g, b] values between 0-1 (exactly 3 items required)"
            },
            "scale": {
                "type": "array", 
                "items": {"type": "number", "minimum": 0.1},
                "description": "XYZ scale [x, y, z] multipliers (exactly 3 items required)"
            }
        }


class WorldBuilderMCP:
    """MCP Server for Isaac Sim WorldBuilder Extension integration."""
    
    def __init__(self, base_url: str = None):
        # Use configuration if available, otherwise fallback to parameter or default
        # Standardized env override
        env_base = os.getenv("AGENT_WORLDBUILDER_BASE_URL") or os.getenv("WORLDBUILDER_API_URL")
        if config:
            self.base_url = env_base or base_url or config.base_url
            self.retry_attempts = config.mcp_retry_attempts
            self.retry_backoff = config.mcp_retry_backoff
        else:
            self.base_url = env_base or base_url or "http://localhost:8899"
            self.retry_attempts = 3
            self.retry_backoff = 0.5
        
        self.server = Server("worldbuilder")
        
        # Initialize unified auth client
        self.client = MCPBaseClient("WORLDBUILDER", self.base_url)
        
        self._setup_tools()
    
    async def _initialize_client(self):
        """Initialize the unified auth client"""
        if not self.client._initialized:
            await self.client.initialize()
    
    def _get_timeout(self, operation_type: str = 'standard') -> float:
        """Get timeout for operation type using configuration."""
        if config:
            return config.get_timeout_for_operation(operation_type)
        else:
            # Fallback timeouts
            return {'simple': 5.0, 'standard': 10.0, 'complex': 15.0}.get(operation_type, 10.0)
    
    async def __aenter__(self):
        """Async context manager entry"""
        await self._initialize_client()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.client.close()
        
    def _setup_tools(self):
        """Register all MCP tools for Isaac Sim worldbuilding."""
        
        @self.server.list_tools()
        async def handle_list_tools() -> List[Tool]:
            """List all available Isaac Sim worldbuilding tools."""
            schemas = create_element_schemas()
            return [
                Tool(
                    name="worldbuilder_add_element",
                    description="Add individual 3D elements (cubes, spheres, cylinders) to Isaac Sim scene",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "element_type": {
                                "type": "string",
                                "enum": ["cube", "sphere", "cylinder", "cone"],
                                "description": "Type of 3D primitive to create"
                            },
                            "name": {
                                "type": "string",
                                "description": "Unique name for the element"
                            },
                            "position": schemas["position"],
                            "color": {**schemas["color"], "default": [0.5, 0.5, 0.5]},
                            "scale": {**schemas["scale"], "default": [1.0, 1.0, 1.0]}
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
                            "batch_name": {
                                "type": "string",
                                "description": "Name for the batch/group"
                            },
                            "elements": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "element_type": {"type": "string", "enum": ["cube", "sphere", "cylinder", "cone"]},
                                        "name": {"type": "string"},
                                        "position": schemas["position"],
                                        "color": schemas["color"],
                                        "scale": schemas["scale"]
                                    },
                                    "required": ["element_type", "name", "position"]
                                },
                                "description": "List of elements to create as a batch"
                            },
                            "parent_path": {
                                "type": "string",
                                "description": "USD path for the parent group",
                                "default": "/World"
                            }
                        },
                        "required": ["batch_name", "elements"]
                    }
                ),
                
                Tool(
                    name="worldbuilder_remove_element",
                    description="Remove specific elements from Isaac Sim scene by USD path",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "usd_path": {
                                "type": "string",
                                "description": "USD path of element to remove (e.g., '/World/my_cube')"
                            }
                        },
                        "required": ["usd_path"]
                    }
                ),
                
                Tool(
                    name="worldbuilder_clear_scene",
                    description="Clear entire scenes or specific paths (bulk removal)",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "path": {
                                "type": "string",
                                "description": "USD path to clear (e.g., '/World' for entire scene)",
                                "default": "/World"
                            },
                            "confirm": {
                                "type": "boolean",
                                "description": "Confirmation flag for destructive operation",
                                "default": False
                            }
                        },
                        "required": ["confirm"]
                    }
                ),
                
                Tool(
                    name="worldbuilder_clear_path",
                    description="Surgical removal of specific USD stage paths. More precise than clear_scene for targeted hierarchy cleanup.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "path": {
                                "type": "string",
                                "description": "Specific USD path to remove (e.g., '/World/Buildings/House1', '/World/incomplete_batch')"
                            },
                            "confirm": {
                                "type": "boolean",
                                "description": "Confirmation flag for destructive operation",
                                "default": False
                            }
                        },
                        "required": ["path", "confirm"]
                    }
                ),
                
                Tool(
                    name="worldbuilder_get_scene",
                    description="Get complete scene structure with hierarchical details",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "include_metadata": {
                                "type": "boolean",
                                "description": "Include detailed metadata for each element",
                                "default": True
                            }
                        }
                    }
                ),
                
                Tool(
                    name="worldbuilder_scene_status",
                    description="Get scene health status and basic statistics",
                    inputSchema={
                        "type": "object",
                        "properties": {}
                    }
                ),
                
                Tool(
                    name="worldbuilder_list_elements",
                    description="Get flat listing of all scene elements",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "filter_type": {
                                "type": "string",
                                "description": "Filter by element type (cube, sphere, etc.)",
                                "default": ""
                            }
                        }
                    }
                ),
                
                Tool(
                    name="worldbuilder_extension_health",
                    description="Check Isaac Sim WorldBuilder Extension health and API status",
                    inputSchema={
                        "type": "object",
                        "properties": {}
                    }
                ),
                
                Tool(
                    name="worldbuilder_place_asset",
                    description="Place USD assets in Isaac Sim scene via reference",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "name": {
                                "type": "string",
                                "description": "Unique name for the asset instance"
                            },
                            "asset_path": {
                                "type": "string",
                                "description": "Path to USD asset file (e.g., '/path/to/asset.usd')"
                            },
                            "prim_path": {
                                "type": "string",
                                "description": "Target prim path in scene (e.g., '/World/my_asset')",
                                "default": ""
                            },
                            "position": {**schemas["position"], "default": [0, 0, 0]},
                            "rotation": {
                                "type": "array",
                                "items": {"type": "number"},
                                "description": "XYZ rotation [rx, ry, rz] in degrees (exactly 3 items required)",
                                "default": [0, 0, 0]
                            },
                            "scale": {**schemas["scale"], "default": [1, 1, 1]}
                        },
                        "required": ["name", "asset_path"]
                    }
                ),
                
                Tool(
                    name="worldbuilder_transform_asset",
                    description="Transform existing assets in Isaac Sim scene (move, rotate, scale)",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "prim_path": {
                                "type": "string",
                                "description": "USD path of existing asset to transform (e.g., '/World/my_asset')"
                            },
                            "position": {
                                **schemas["position"],
                                "description": "New XYZ position [x, y, z] in world coordinates (optional)"
                            },
                            "rotation": {
                                "type": "array",
                                "items": {"type": "number"},
                                "description": "New XYZ rotation [rx, ry, rz] in degrees (optional, exactly 3 items required)"
                            },
                            "scale": {
                                **schemas["scale"],
                                "description": "New XYZ scale [x, y, z] multipliers (optional)"
                            }
                        },
                        "required": ["prim_path"]
                    }
                ),
                
                Tool(
                    name="worldbuilder_batch_info",
                    description="Get detailed information about a specific batch/group in the scene",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "batch_name": {
                                "type": "string",
                                "description": "Name of the batch to get information about"
                            }
                        },
                        "required": ["batch_name"]
                    }
                ),
                
                Tool(
                    name="worldbuilder_clear_batch",
                    description="Clear/remove a specific batch and all its elements from the scene",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "batch_name": {
                                "type": "string",
                                "description": "Name of the batch to clear"
                            },
                            "confirm": {
                                "type": "boolean",
                                "description": "Confirmation flag for destructive operation",
                                "default": False
                            }
                        },
                        "required": ["batch_name", "confirm"]
                    }
                ),
                
                Tool(
                    name="worldbuilder_request_status",
                    description="Get status of ongoing operations and request queue",
                    inputSchema={
                        "type": "object",
                        "properties": {}
                    }
                ),
                
                Tool(
                    name="worldbuilder_get_metrics",
                    description="Get performance metrics and statistics from WorldBuilder extension",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "format": {
                                "type": "string",
                                "enum": ["json", "prom"],
                                "description": "Output format: json for structured data, prom for Prometheus format",
                                "default": "json"
                            }
                        }
                    }
                ),
                Tool(
                    name="worldbuilder_query_objects_by_type",
                    description="Query objects by semantic type (furniture, lighting, primitive, etc.)",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "type": {
                                "type": "string",
                                "description": "Object type to search for (e.g. 'furniture', 'lighting', 'decoration', 'architecture', 'vehicle', 'primitive')"
                            }
                        },
                        "required": ["type"]
                    }
                ),
                Tool(
                    name="worldbuilder_query_objects_in_bounds",
                    description="Query objects within spatial bounds (3D bounding box)",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "min": {
                                "type": "array",
                                "items": {"type": "number"},
                                "minItems": 3,
                                "maxItems": 3,
                                "description": "Minimum bounds [x, y, z]"
                            },
                            "max": {
                                "type": "array",
                                "items": {"type": "number"},
                                "minItems": 3,
                                "maxItems": 3,
                                "description": "Maximum bounds [x, y, z]"
                            }
                        },
                        "required": ["min", "max"]
                    }
                ),
                Tool(
                    name="worldbuilder_query_objects_near_point",
                    description="Query objects near a specific point within radius",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "point": {
                                "type": "array",
                                "items": {"type": "number"},
                                "minItems": 3,
                                "maxItems": 3,
                                "description": "Point coordinates [x, y, z]"
                            },
                            "radius": {
                                "type": "number",
                                "description": "Search radius in world units",
                                "default": 5.0,
                                "minimum": 0.1
                            }
                        },
                        "required": ["point"]
                    }
                ),
                
                Tool(
                    name="worldbuilder_calculate_bounds",
                    description="Calculate combined bounding box for multiple objects. Useful for understanding spatial extent of object groups.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "objects": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "List of USD paths to objects (e.g., ['/World/cube1', '/World/sphere1'])",
                                "minItems": 1
                            }
                        },
                        "required": ["objects"]
                    }
                ),
                
                Tool(
                    name="worldbuilder_find_ground_level",
                    description="Find ground level at a position using consensus algorithm. Analyzes nearby objects to determine appropriate ground height.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "position": {
                                "type": "array",
                                "items": {"type": "number"},
                                "minItems": 3,
                                "maxItems": 3,
                                "description": "Position coordinates [x, y, z]"
                            },
                            "search_radius": {
                                "type": "number",
                                "description": "Search radius for ground detection",
                                "default": 10.0,
                                "minimum": 1.0
                            }
                        },
                        "required": ["position"]
                    }
                ),
                
                Tool(
                    name="worldbuilder_align_objects",
                    description="Align objects along specified axis (x, y, z) with optional uniform spacing. Useful for organizing object layouts.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "objects": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "List of USD paths to objects to align",
                                "minItems": 2
                            },
                            "axis": {
                                "type": "string",
                                "enum": ["x", "y", "z"],
                                "description": "Axis to align along (x=left-right, y=up-down, z=forward-back)"
                            },
                            "alignment": {
                                "type": "string",
                                "enum": ["min", "max", "center"],
                                "description": "Alignment type: min (left/bottom/front), max (right/top/back), center (middle)",
                                "default": "center"
                            },
                            "spacing": {
                                "type": "number",
                                "description": "Uniform spacing between objects (optional)",
                                "minimum": 0.1
                            }
                        },
                        "required": ["objects", "axis"]
                    }
                ),
                
                Tool(
                    name="worldbuilder_get_metrics",
                    description="Get performance metrics and statistics from WorldBuilder extension",
                    inputSchema={
                        "type": "object", 
                        "properties": {
                            "format": {
                                "type": "string",
                                "enum": ["json", "prom"],
                                "description": "Output format: json for structured data, prom for Prometheus format",
                                "default": "json"
                            }
                        },
                        "additionalProperties": False
                    }
                ),
                
                Tool(
                    name="worldbuilder_metrics_prometheus",
                    description="Get WorldBuilder metrics in Prometheus format for monitoring systems",
                    inputSchema={
                        "type": "object",
                        "properties": {},
                        "additionalProperties": False
                    }
                )
            ]
        
        @self.server.call_tool()
        async def handle_call_tool(name: str, arguments: Dict[str, Any]) -> List[types.TextContent]:
            """Handle tool calls and route to appropriate Isaac Sim API endpoints."""
            
            try:
                if name == "worldbuilder_add_element":
                    return await self._add_element(arguments)
                elif name == "worldbuilder_create_batch":
                    return await self._create_batch(arguments)
                elif name == "worldbuilder_remove_element":
                    return await self._remove_element(arguments)
                elif name == "worldbuilder_clear_scene":
                    return await self._clear_scene(arguments)
                elif name == "worldbuilder_clear_path":
                    return await self._clear_path(arguments)
                elif name == "worldbuilder_get_scene":
                    return await self._get_scene(arguments)
                elif name == "worldbuilder_scene_status":
                    return await self._scene_status(arguments)
                elif name == "worldbuilder_list_elements":
                    return await self._list_elements(arguments)
                elif name == "worldbuilder_extension_health":
                    return await self._extension_health(arguments)
                elif name == "worldbuilder_place_asset":
                    return await self._place_asset(arguments)
                elif name == "worldbuilder_transform_asset":
                    return await self._transform_asset(arguments)
                elif name == "worldbuilder_batch_info":
                    return await self._batch_info(arguments)
                elif name == "worldbuilder_clear_batch":
                    return await self._clear_batch(arguments)
                elif name == "worldbuilder_request_status":
                    return await self._request_status(arguments)
                elif name == "worldbuilder_query_objects_by_type":
                    return await self._query_objects_by_type(arguments)
                elif name == "worldbuilder_query_objects_in_bounds":
                    return await self._query_objects_in_bounds(arguments)
                elif name == "worldbuilder_query_objects_near_point":
                    return await self._query_objects_near_point(arguments)
                elif name == "worldbuilder_calculate_bounds":
                    return await self._calculate_bounds(arguments)
                elif name == "worldbuilder_find_ground_level":
                    return await self._find_ground_level(arguments)
                elif name == "worldbuilder_align_objects":
                    return await self._align_objects(arguments)
                elif name == "worldbuilder_get_metrics":
                    return await self._get_metrics(arguments)
                elif name == "worldbuilder_metrics_prometheus":
                    return await self._metrics_prometheus(arguments)
                else:
                    return [types.TextContent(
                        type="text",
                        text=f"❌ Unknown tool: {name}"
                    )]
                    
            except aiohttp.ClientError as e:
                logger.error(f"Connection error calling tool {name}: {e}")
                return [types.TextContent(
                    type="text",
                    text=f"❌ Connection error: {str(e)}"
                )]
            except Exception as e:
                logger.error(f"Error calling tool {name}: {e}")
                return [types.TextContent(
                    type="text",
                    text=f"❌ Error executing {name}: {str(e)}"
                )]
    
    async def _add_element(self, args: Dict[str, Any]) -> List[types.TextContent]:
        """Add individual 3D element to Isaac Sim scene."""
        try:
            # Prepare API request
            payload = {
                "element_type": args["element_type"],
                "name": args["name"],
                "position": args["position"],
                "color": args.get("color", [0.5, 0.5, 0.5]),
                "scale": args.get("scale", [1.0, 1.0, 1.0])
            }
            
            await self._initialize_client()
            result = await self.client.post(
                "/add_element",
                json=payload,
                timeout=self._get_timeout('standard')
            )
            
            if result.get("success"):
                    return [types.TextContent(
                        type="text",
                        text=f"✅ Created {args['element_type']} '{args['name']}' at {args['position']}"
                    )]
            else:
                return [types.TextContent(
                    type="text",
                    text=f"❌ Failed to create element: {result.get('error', 'Unknown error')}"
                )]
                
        except aiohttp.ClientError as e:
            return [types.TextContent(
                type="text",
                text=f"❌ Connection error: {str(e)}. Is Isaac Sim running with the WorldBuilder Extension?"
            )]
    
    async def _create_batch(self, args: Dict[str, Any]) -> List[types.TextContent]:
        """Create hierarchical batch of objects."""
        try:
            payload = {
                "batch_name": args["batch_name"],
                "elements": args["elements"],
                "parent_path": args.get("parent_path", "/World")
            }
            
            await self._initialize_client()
            result = await self.client.post(
                "/create_batch",
                json=payload,
                timeout=self._get_timeout('complex')
            )
            
            if result.get("success"):
                    return [types.TextContent(
                        type="text",
                        text=f"✅ Created batch '{args['batch_name']}' with {len(args['elements'])} elements"
                    )]
            else:
                return [types.TextContent(
                    type="text",
                    text=f"❌ Failed to create batch: {result.get('error', 'Unknown error')}"
                )]
                
        except aiohttp.ClientError as e:
            return [types.TextContent(
                type="text",
                text=f"❌ Connection error: {str(e)}"
            )]
    
    async def _remove_element(self, args: Dict[str, Any]) -> List[types.TextContent]:
        """Remove specific element by USD path."""
        try:
            payload = {"element_path": args["usd_path"]}
            
            await self._initialize_client()
            result = await self.client.post(
                "/remove_element",
                json=payload,
                timeout=10
            )
            
            if result.get("success"):
                    return [types.TextContent(
                        type="text",
                        text=f"✅ Removed element: {args['usd_path']}"
                    )]
            else:
                return [types.TextContent(
                    type="text",
                    text=f"❌ Failed to remove element: {result.get('error', 'Unknown error')}"
                )]
                
        except aiohttp.ClientError as e:
            return [types.TextContent(
                type="text",
                text=f"❌ Connection error: {str(e)}"
            )]
    
    async def _clear_scene(self, args: Dict[str, Any]) -> List[types.TextContent]:
        """Clear scene or specific paths."""
        if not args.get("confirm", False):
            return [types.TextContent(
                type="text",
                text="❌ Destructive operation requires confirm=true parameter"
            )]
        
        try:
            payload = {"path": args.get("path", "/World")}
            
            await self._initialize_client()
            result = await self.client.post(
                "/clear_path",
                json=payload,
                timeout=10
            )
            
            if result.get("success"):
                    return [types.TextContent(
                        type="text",
                        text=f"✅ Cleared path: {args.get('path', '/World')}"
                    )]
            else:
                return [types.TextContent(
                    type="text",
                    text=f"❌ Failed to clear path: {result.get('error', 'Unknown error')}"
                )]
                
        except aiohttp.ClientError as e:
            return [types.TextContent(
                type="text",
                text=f"❌ Connection error: {str(e)}"
            )]
    
    async def _clear_path(self, args: Dict[str, Any]) -> List[types.TextContent]:
        """Surgical removal of specific USD stage path."""
        path = args.get("path")
        if not path:
            return [types.TextContent(
                type="text",
                text="❌ Error: path parameter is required"
            )]
            
        if not args.get("confirm", False):
            return [types.TextContent(
                type="text",
                text="❌ Destructive operation requires confirm=true parameter"
            )]
        
        try:
            payload = {"path": path}
            
            await self._initialize_client()
            result = await self.client.post(
                "/clear_path",
                json=payload,
                timeout=10
            )
            
            if result.get("success"):
                    return [types.TextContent(
                        type="text",
                        text=f"🔧 **Surgical Path Removal Complete**\n\n"
                             f"• **Removed Path:** {path}\n"
                             f"• **Operation:** Targeted USD hierarchy cleanup\n"
                             f"• **Status:** {result.get('message', 'Path cleared successfully')}"
                    )]
            else:
                return [types.TextContent(
                    type="text",
                    text=f"❌ Failed to clear path '{path}': {result.get('error', 'Unknown error')}"
                )]
                
        except aiohttp.ClientError as e:
            return [types.TextContent(
                type="text",
                text=f"❌ Connection error: {str(e)}"
            )]
    
    async def _get_scene(self, args: Dict[str, Any]) -> List[types.TextContent]:
        """Get complete scene structure."""
        try:
            await self._initialize_client()
            result = await self.client.get('/get_scene', timeout=10)
            
            if result.get("success"):
                    scene_data = result.get("contents", {})
                    formatted_scene = json.dumps(scene_data, indent=2)
                    return [types.TextContent(
                        type="text",
                        text=f"📊 Scene Structure:\n```json\n{formatted_scene}\n```"
                    )]
            else:
                return [types.TextContent(
                    type="text",
                    text=f"❌ Failed to get scene: {result.get('error', 'Unknown error')}"
                )]
                
        except aiohttp.ClientError as e:
            return [types.TextContent(
                type="text",
                text=f"❌ Connection error: {str(e)}"
            )]
    
    async def _scene_status(self, args: Dict[str, Any]) -> List[types.TextContent]:
        """Get scene health status."""
        try:
            await self._initialize_client()
            result = await self.client.get('/scene_status', timeout=5)
            
            if result.get("success"):
                # Support both legacy { scene: { ... } } and flat fields
                scene = result.get("scene") or result
                # Elements
                prim_count = scene.get('prim_count')
                if prim_count is None:
                    prim_count = scene.get('total_prims', 0)
                # Assets (may not be provided by all versions)
                asset_count = scene.get('asset_count', 0)
                # Stage/health inference
                has_stage = scene.get('has_stage')
                if has_stage is None:
                    # Infer active stage from presence of prims or active batches
                    has_stage = bool(prim_count) or bool(scene.get('active_batches', 0))
                stage_text = 'Active' if has_stage else 'None'
                
                return [types.TextContent(
                    type="text",
                    text=(
                        "📊 Scene Status:\n"
                        f"• Stage: {stage_text}\n"
                        f"• Elements: {prim_count} prims\n"
                        f"• Assets: {asset_count} assets"
                    )
                )]
            else:
                return [types.TextContent(
                    type="text",
                    text=f"❌ Failed to get status: {result.get('error', 'Unknown error')}"
                )]
                
        except aiohttp.ClientError as e:
            return [types.TextContent(
                type="text",
                text=f"❌ Connection error: {str(e)}"
            )]
    
    async def _list_elements(self, args: Dict[str, Any]) -> List[types.TextContent]:
        """Get flat listing of scene elements."""
        try:
            await self._initialize_client()
            result = await self.client.get('/list_elements', timeout=10)
            
            if result.get("success"):
                    elements = result.get("elements", [])
                    if not elements:
                        return [types.TextContent(
                            type="text",
                            text="📋 Scene is empty - no elements found"
                        )]
                    
                    filter_type = args.get("filter_type", "")
                    if filter_type:
                        elements = [e for e in elements if filter_type.lower() in e.get("type", "").lower()]
                    
                    element_list = "\n".join([
                        f"• {e.get('path', 'Unknown')} ({e.get('type', 'Unknown')})"
                        for e in elements
                    ])
                    
                    return [types.TextContent(
                        type="text",
                        text=f"📋 Scene Elements ({len(elements)} found):\n{element_list}"
                    )]
            else:
                return [types.TextContent(
                    type="text",
                    text=f"❌ Failed to list elements: {result.get('error', 'Unknown error')}"
                )]
                
        except aiohttp.ClientError as e:
            return [types.TextContent(
                type="text",
                text=f"❌ Connection error: {str(e)}"
            )]
    
    async def _extension_health(self, args: Dict[str, Any]) -> List[types.TextContent]:
        """Check extension health and API status."""
        try:
            await self._initialize_client()
            result = await self.client.get('/health', timeout=self._get_timeout('simple'))
            
            if result.get("success"):
                    return [types.TextContent(
                        type="text",
                        text=f"✅ WorldBuilder Health\n" +
                             f"• Service: {result.get('service', 'Unknown')}\n" +
                             f"• Version: {result.get('version', 'Unknown')}\n" +
                             f"• URL: {result.get('url', 'Unknown')}\n" +
                             f"• Timestamp: {result.get('timestamp', 'Unknown')}\n" +
                             f"• Scene Object Count: {result.get('scene_object_count', 0)}"
                    )]
            else:
                return [types.TextContent(
                    type="text",
                    text=f"❌ Extension unhealthy: {result.get('error', 'Unknown error')}"
                )]
                
        except aiohttp.ClientError as e:
            return [types.TextContent(
                type="text",
                text=f"❌ Connection error: {str(e)}. Is Isaac Sim running with the WorldBuilder Extension on port 8899?"
            )]

    async def _place_asset(self, args: Dict[str, Any]) -> List[types.TextContent]:
        """Place USD asset in Isaac Sim scene via reference."""
        try:
            # Prepare API request payload
            payload = {
                "name": args["name"],
                "asset_path": args["asset_path"],
                "prim_path": args.get("prim_path", args["name"]),
                "position": args.get("position", [0, 0, 0]),
                "rotation": args.get("rotation", [0, 0, 0]),
                "scale": args.get("scale", [1, 1, 1])
            }
            
            # Call Isaac Sim place_asset API via base client
            await self._initialize_client()
            result = await self.client.post(
                "/place_asset",
                json=payload,
                timeout=10
            )
            
            if result.get("success"):
                    return [types.TextContent(
                        type="text",
                        text=f"✅ Asset placed successfully!\n" +
                             f"• Name: {result.get('asset_name', 'Unknown')}\n" +
                             f"• Path: {result.get('prim_path', 'Unknown')}\n" +
                             f"• Position: {result.get('position', 'Unknown')}\n" +
                             f"• Request ID: {result.get('request_id', 'Unknown')}\n" +
                             f"• Status: {result.get('status', 'Unknown')}"
                    )]
            else:
                return [types.TextContent(
                    type="text",
                    text=f"❌ Asset placement failed: {result.get('error', 'Unknown error')}"
                )]
                
        except aiohttp.ClientError as e:
            return [types.TextContent(
                type="text",
                text=f"❌ Connection error: {str(e)}. Is Isaac Sim running with the WorldBuilder Extension on port 8899?"
            )]

    async def _transform_asset(self, args: Dict[str, Any]) -> List[types.TextContent]:
        """Transform existing asset in Isaac Sim scene."""
        try:
            # Prepare API request payload
            payload = {
                "prim_path": args["prim_path"]
            }
            
            # Add optional transform parameters if provided
            if "position" in args:
                payload["position"] = args["position"]
            if "rotation" in args:
                payload["rotation"] = args["rotation"]
            if "scale" in args:
                payload["scale"] = args["scale"]
            
            # Call Isaac Sim transform_asset API via base client
            await self._initialize_client()
            result = await self.client.post(
                "/transform_asset",
                json=payload,
                timeout=10
            )
            
            if result.get("success"):
                transform_info = []
                if result.get("position"):
                    transform_info.append(f"• Position: {result['position']}")
                if result.get("rotation"):
                    transform_info.append(f"• Rotation: {result['rotation']}")
                if result.get("scale"):
                    transform_info.append(f"• Scale: {result['scale']}")
                
                return [types.TextContent(
                    type="text",
                    text=f"✅ Asset transformed successfully!\n" +
                         f"• Path: {result.get('prim_path', 'Unknown')}\n" +
                         f"• Request ID: {result.get('request_id', 'Unknown')}\n" +
                         f"• Status: {result.get('status', 'Unknown')}\n" +
                         ("\n".join(transform_info) if transform_info else "")
                )]
            else:
                return [types.TextContent(
                    type="text",
                    text=f"❌ Asset transformation failed: {result.get('error', 'Unknown error')}"
                )]
                
        except aiohttp.ClientError as e:
            return [types.TextContent(
                type="text",
                text=f"❌ Connection error: {str(e)}. Is Isaac Sim running with the WorldBuilder Extension on port 8899?"
            )]
    
    async def _batch_info(self, args: Dict[str, Any]) -> List[types.TextContent]:
        """Get detailed information about a specific batch/group in the scene."""
        try:
            batch_name = args.get('batch_name')
            if not batch_name:
                return [types.TextContent(type="text", text="❌ Error: batch_name is required")]
            
            await self._initialize_client()
            result = await self.client.get("/batch_info", params={'batch_name': batch_name})
            
            if result.get('success'):
                    element_count = result.get('element_count', 0)
                    elements = result.get('elements', [])
                    
                    # Format element details
                    element_details = []
                    for elem in elements:
                        pos = elem.get('position', [0, 0, 0])
                        element_details.append(
                            f"  - **{elem.get('name', 'Unknown')}** ({elem.get('type', 'Unknown')})\n"
                            f"    Position: [{pos[0]:.2f}, {pos[1]:.2f}, {pos[2]:.2f}]"
                        )
                    
                    element_text = "\n".join(element_details) if element_details else "  (No elements)"
                    
                    return [types.TextContent(
                        type="text",
                        text=f"✅ **Batch Information: {batch_name}**\n" +
                             f"• Element Count: {element_count}\n" +
                             f"• Batch Name: {result.get('batch_name', batch_name)}\n\n" +
                             f"**Elements:**\n{element_text}"
                    )]
            else:
                return [types.TextContent(type="text", text=f"❌ Failed to get batch info: {result.get('error', 'Unknown error')}")]
                
        except aiohttp.ClientError as e:
            return [types.TextContent(type="text", text=f"❌ Connection error: {str(e)}. Is Isaac Sim running?")]
    
    async def _clear_batch(self, args: Dict[str, Any]) -> List[types.TextContent]:
        """Clear/remove a specific batch and all its elements from the scene."""
        try:
            batch_name = args.get('batch_name')
            confirm = args.get('confirm', False)
            
            if not batch_name:
                return [types.TextContent(type="text", text="❌ Error: batch_name is required")]
            
            if not confirm:
                return [types.TextContent(type="text", text="❌ Error: confirm=true required for destructive operation")]
            
            await self._initialize_client()
            result = await self.client.post("/clear_batch", json={'batch_name': batch_name, 'confirm': confirm})
            
            if result.get('success'):
                    cleared_count = result.get('cleared_count', 0)
                    return [types.TextContent(
                        type="text",
                        text=f"✅ **Batch Cleared Successfully**\n" +
                             f"• Batch: {batch_name}\n" +
                             f"• Elements Removed: {cleared_count}"
                    )]
            else:
                return [types.TextContent(type="text", text=f"❌ Failed to clear batch: {result.get('error', 'Unknown error')}")]
                
        except aiohttp.ClientError as e:
            return [types.TextContent(type="text", text=f"❌ Connection error: {str(e)}. Is Isaac Sim running?")]
    
    async def _request_status(self, args: Dict[str, Any]) -> List[types.TextContent]:
        """Get status of ongoing operations and request queue."""
        try:
            await self._initialize_client()
            result = await self.client.get("/request_status")
            
            if result.get('success'):
                    status_data = result.get('status', {})
                    queue_info = status_data.get('queue_info', {})
                    return [types.TextContent(
                        type="text",
                        text=f"✅ **Request Status**\n" +
                             f"• Queue Size: {queue_info.get('pending', 0)}\n" +
                             f"• Processing: {queue_info.get('active', 0)}\n" +
                             f"• Completed: {queue_info.get('completed', 0)}\n" +
                             f"• Failed: {queue_info.get('failed', 0)}\n" +
                             f"• System Status: {status_data.get('system_status', 'Unknown')}"
                    )]
            else:
                return [types.TextContent(type="text", text=f"❌ Failed to get request status: {result.get('error', 'Unknown error')}")]
                
        except aiohttp.ClientError as e:
            return [types.TextContent(type="text", text=f"❌ Connection error: {str(e)}. Is Isaac Sim running?")]
    
    async def _get_metrics(self, args: Dict[str, Any]) -> List[types.TextContent]:
        """Get performance metrics and statistics from WorldBuilder extension."""
        try:
            format_type = args.get('format', 'json')
            
            endpoint = "/metrics.prom" if format_type == "prom" else "/metrics"
            await self._initialize_client()
            result = await self.client.get(endpoint)
            
            if format_type == "prom":
                # Handle raw text fallback or structured text
                if '_raw_text' in result:
                    prom_text = result['_raw_text']
                else:
                    prom_text = result.get('prometheus_metrics') or result.get('raw_response') or result.get('text', str(result))
                return [types.TextContent(type="text", text=f"✅ **WorldBuilder Metrics (Prometheus)**\n```\n{prom_text}\n```")]
            else:
                if result.get('success'):
                    metrics = result.get('metrics', {})
                    api_metrics = metrics.get('api', {})
                    scene_metrics = metrics.get('scene', {})
                    return [types.TextContent(
                        type="text",
                        text=f"✅ **WorldBuilder Metrics**\n" +
                             f"• **API Stats:**\n" +
                             f"  - Requests: {api_metrics.get('requests_received', 0)}\n" +
                             f"  - Successful: {api_metrics.get('successful_requests', 0)}\n" +
                             f"  - Failed: {api_metrics.get('failed_requests', 0)}\n" +
                             f"  - Uptime: {api_metrics.get('uptime_seconds', 0):.1f}s\n" +
                             f"• **Scene Stats:**\n" +
                             f"  - Elements: {scene_metrics.get('element_count', 0)}\n" +
                             f"  - Batches: {scene_metrics.get('batch_count', 0)}"
                    )]
                else:
                    return [types.TextContent(type="text", text=f"❌ Failed to get metrics: {result.get('error', 'Unknown error')}")]
                
        except aiohttp.ClientError as e:
            return [types.TextContent(type="text", text=f"❌ Connection error: {str(e)}. Is Isaac Sim running?")]
    
    async def _query_objects_by_type(self, args: Dict[str, Any]) -> List[types.TextContent]:
        """Query objects by semantic type (furniture, lighting, etc.)."""
        try:
            object_type = args.get('type')
            if not object_type:
                return [types.TextContent(type="text", text="❌ Error: type parameter is required")]
            
            await self._initialize_client()
            params = {'type': object_type}
            result = await self.client.get(
                "/query/objects_by_type",
                params=params,
                timeout=self._get_timeout('simple')
            )
            
            if result.get('success'):
                objects = result.get('objects', [])
                count = result.get('count', 0)
                
                if count == 0:
                    return [types.TextContent(
                        type="text",
                        text=f"✅ **No objects found**\n• Type: {object_type}\n• Consider checking spelling or try broader categories like 'furniture', 'primitive', 'lighting'"
                    )]
                
                # Format object list
                object_list = []
                for obj in objects[:10]:  # Limit to first 10 for readability
                    pos = obj.get('position', [0, 0, 0])
                    object_list.append(
                        f"  - **{obj.get('name', 'Unknown')}** ({obj.get('type', 'Unknown')})\n" +
                        f"    Path: `{obj.get('path', 'Unknown')}`\n" +
                        f"    Position: [{pos[0]:.1f}, {pos[1]:.1f}, {pos[2]:.1f}]"
                    )
                
                more_text = f"\n\n*Showing {min(10, count)} of {count} objects*" if count > 10 else ""
                
                return [types.TextContent(
                    type="text",
                    text=f"✅ **Found {count} objects of type '{object_type}'**\n\n" +
                         "\n\n".join(object_list) + more_text
                )]
            else:
                return [types.TextContent(
                    type="text",
                    text=f"❌ Query failed: {result.get('error', 'Unknown error')}"
                )]
                
        except aiohttp.ClientError as e:
            return [types.TextContent(
                type="text",
                text=f"❌ Connection error: {str(e)}. Is Isaac Sim running with WorldBuilder extension?"
            )]
    
    async def _query_objects_in_bounds(self, args: Dict[str, Any]) -> List[types.TextContent]:
        """Query objects within spatial bounds."""
        try:
            min_bounds = args.get('min')
            max_bounds = args.get('max')
            
            if not min_bounds or not max_bounds:
                return [types.TextContent(type="text", text="❌ Error: min and max bounds are required")]
            
            if len(min_bounds) != 3 or len(max_bounds) != 3:
                return [types.TextContent(type="text", text="❌ Error: bounds must be [x,y,z] coordinates")]
            
            params = {
                'min': ','.join(map(str, min_bounds)),
                'max': ','.join(map(str, max_bounds))
            }
            await self._initialize_client()
            result = await self.client.get(
                "/query/objects_in_bounds",
                params=params,
                timeout=self._get_timeout('simple')
            )
            
            if result.get('success'):
                objects = result.get('objects', [])
                count = result.get('count', 0)
                bounds = result.get('bounds', {})
                
                if count == 0:
                    return [types.TextContent(
                        type="text",
                        text=f"✅ **No objects found in bounds**\n• Min: [{min_bounds[0]}, {min_bounds[1]}, {min_bounds[2]}]\n• Max: [{max_bounds[0]}, {max_bounds[1]}, {max_bounds[2]}]"
                    )]
                
                # Format object list
                object_list = []
                for obj in objects[:10]:  # Limit to first 10
                    pos = obj.get('position', [0, 0, 0])
                    object_list.append(
                        f"  - **{obj.get('name', 'Unknown')}** ({obj.get('type', 'Unknown')})\n" +
                        f"    Position: [{pos[0]:.1f}, {pos[1]:.1f}, {pos[2]:.1f}]"
                    )
                
                more_text = f"\n\n*Showing {min(10, count)} of {count} objects*" if count > 10 else ""
                
                return [types.TextContent(
                    type="text",
                    text=f"✅ **Found {count} objects in bounds**\n" +
                         f"• Min: [{min_bounds[0]}, {min_bounds[1]}, {min_bounds[2]}]\n" +
                         f"• Max: [{max_bounds[0]}, {max_bounds[1]}, {max_bounds[2]}]\n\n" +
                         "\n\n".join(object_list) + more_text
                )]
            else:
                return [types.TextContent(
                    type="text",
                    text=f"❌ Query failed: {result.get('error', 'Unknown error')}"
                )]
                
        except aiohttp.ClientError as e:
            return [types.TextContent(
                type="text",
                text=f"❌ Connection error: {str(e)}. Is Isaac Sim running with WorldBuilder extension?"
            )]
    
    async def _query_objects_near_point(self, args: Dict[str, Any]) -> List[types.TextContent]:
        """Query objects near a specific point within radius."""
        try:
            point = args.get('point')
            radius = args.get('radius', 5.0)
            
            if not point:
                return [types.TextContent(type="text", text="❌ Error: point parameter is required")]
            
            if len(point) != 3:
                return [types.TextContent(type="text", text="❌ Error: point must be [x,y,z] coordinates")]
            
            params = {
                'point': ','.join(map(str, point)),
                'radius': radius
            }
            await self._initialize_client()
            result = await self.client.get(
                "/query/objects_near_point",
                params=params,
                timeout=self._get_timeout('simple')
            )
            
            if result.get('success'):
                objects = result.get('objects', [])
                count = result.get('count', 0)
                query_point = result.get('query_point', point)
                query_radius = result.get('radius', radius)
                
                if count == 0:
                    return [types.TextContent(
                        type="text",
                        text=f"✅ **No objects found near point**\n• Point: [{point[0]}, {point[1]}, {point[2]}]\n• Radius: {radius} units"
                    )]
                
                # Format object list (sorted by distance)
                object_list = []
                for obj in objects[:10]:  # Limit to first 10
                    pos = obj.get('position', [0, 0, 0])
                    distance = obj.get('distance_from_point', 0)
                    object_list.append(
                        f"  - **{obj.get('name', 'Unknown')}** ({obj.get('type', 'Unknown')})\n" +
                        f"    Distance: {distance:.1f} units\n" +
                        f"    Position: [{pos[0]:.1f}, {pos[1]:.1f}, {pos[2]:.1f}]"
                    )
                
                more_text = f"\n\n*Showing {min(10, count)} of {count} objects (sorted by distance)*" if count > 10 else ""
                
                return [types.TextContent(
                    type="text",
                    text=f"✅ **Found {count} objects near point**\n" +
                         f"• Point: [{point[0]}, {point[1]}, {point[2]}]\n" +
                         f"• Radius: {radius} units\n\n" +
                         "\n\n".join(object_list) + more_text
                )]
            else:
                return [types.TextContent(
                    type="text",
                    text=f"❌ Query failed: {result.get('error', 'Unknown error')}"
                )]
                
        except aiohttp.ClientError as e:
            return [types.TextContent(
                type="text",
                text=f"❌ Connection error: {str(e)}. Is Isaac Sim running with WorldBuilder extension?"
            )]
    
    async def _calculate_bounds(self, args: Dict[str, Any]) -> List[types.TextContent]:
        """Calculate combined bounding box for multiple objects."""
        try:
            objects = args.get('objects', [])
            
            if not objects:
                return [types.TextContent(type="text", text="❌ Error: objects list is required")]
            
            if not isinstance(objects, list) or len(objects) < 1:
                return [types.TextContent(type="text", text="❌ Error: objects must be a non-empty list")]
            
            payload = {"objects": objects}
            await self._initialize_client()
            result = await self.client.post(
                "/transform/calculate_bounds",
                json=payload,
                timeout=self._get_timeout('standard')
            )
            
            if result.get('success'):
                bounds = result.get('bounds', {})
                count = result.get('object_count', 0)
                
                min_coords = bounds.get('min', [0, 0, 0])
                max_coords = bounds.get('max', [0, 0, 0])
                center = bounds.get('center', [0, 0, 0])
                size = bounds.get('size', [0, 0, 0])
                volume = result.get('volume', 0.0)
                
                return [types.TextContent(
                    type="text",
                    text=f"✅ **Calculated combined bounds for {count} objects**\n\n" +
                         f"• **Min bounds:** [{min_coords[0]:.2f}, {min_coords[1]:.2f}, {min_coords[2]:.2f}]\n" +
                         f"• **Max bounds:** [{max_coords[0]:.2f}, {max_coords[1]:.2f}, {max_coords[2]:.2f}]\n" +
                         f"• **Center:** [{center[0]:.2f}, {center[1]:.2f}, {center[2]:.2f}]\n" +
                         f"• **Size (W×H×D):** {size[0]:.2f} × {size[1]:.2f} × {size[2]:.2f}\n" +
                         f"• **Volume:** {volume:.2f} cubic units\n\n" +
                         f"*Combined bounding box encompasses all {count} objects*"
                )]
            else:
                return [types.TextContent(
                    type="text",
                    text=f"❌ Bounds calculation failed: {result.get('error', 'Unknown error')}"
                )]
                
        except aiohttp.ClientError as e:
            return [types.TextContent(
                type="text",
                text=f"❌ Connection error: {str(e)}. Is Isaac Sim running with WorldBuilder extension?"
            )]
    
    async def _find_ground_level(self, args: Dict[str, Any]) -> List[types.TextContent]:
        """Find ground level at position using consensus algorithm."""
        try:
            position = args.get('position')
            search_radius = args.get('search_radius', 10.0)
            
            if not position:
                return [types.TextContent(type="text", text="❌ Error: position is required")]
            
            if len(position) != 3:
                return [types.TextContent(type="text", text="❌ Error: position must be [x,y,z] coordinates")]
            
            payload = {
                "position": position,
                "search_radius": search_radius
            }
            await self._initialize_client()
            result = await self.client.post(
                "/transform/find_ground_level",
                json=payload,
                timeout=self._get_timeout('standard')
            )
            
            if result.get('success'):
                ground_y = result.get('ground_level', 0.0)
                method = result.get('detection_method', 'unknown')
                confidence = result.get('confidence', 0.0)
                reference_objects = result.get('reference_objects', [])
                
                method_desc = {
                    'consensus': 'Consensus from nearby objects',
                    'lowest_object': 'Lowest nearby object',
                    'surface_detection': 'Surface detection',
                    'default': 'Default ground level (no objects found)'
                }.get(method, method)
                
                reference_text = ""
                if reference_objects:
                    ref_list = [f"  - {obj}" for obj in reference_objects[:5]]
                    more_ref = f"\n  - *...and {len(reference_objects) - 5} more*" if len(reference_objects) > 5 else ""
                    reference_text = f"\n\n**Reference objects:**\n" + "\n".join(ref_list) + more_ref
                
                return [types.TextContent(
                    type="text",
                    text=f"✅ **Ground level detected**\n\n" +
                         f"• **Position:** [{position[0]}, {position[1]}, {position[2]}]\n" +
                         f"• **Ground level (Y):** {ground_y:.2f}\n" +
                         f"• **Detection method:** {method_desc}\n" +
                         f"• **Confidence:** {confidence:.1%}\n" +
                         f"• **Search radius:** {search_radius} units" +
                         reference_text
                )]
            else:
                return [types.TextContent(
                    type="text",
                    text=f"❌ Ground level detection failed: {result.get('error', 'Unknown error')}"
                )]
                
        except aiohttp.ClientError as e:
            return [types.TextContent(
                type="text",
                text=f"❌ Connection error: {str(e)}. Is Isaac Sim running with WorldBuilder extension?"
            )]
    
    async def _align_objects(self, args: Dict[str, Any]) -> List[types.TextContent]:
        """Align objects along specified axis with optional spacing."""
        try:
            objects = args.get('objects', [])
            axis = args.get('axis')
            alignment = args.get('alignment', 'center')
            spacing = args.get('spacing')
            
            if not objects:
                return [types.TextContent(type="text", text="❌ Error: objects list is required")]
            
            if not axis:
                return [types.TextContent(type="text", text="❌ Error: axis is required (x, y, or z)")]
            
            if len(objects) < 2:
                return [types.TextContent(type="text", text="❌ Error: at least 2 objects required for alignment")]
            
            payload = {
                "objects": objects,
                "axis": axis,
                "alignment": alignment
            }
            if spacing is not None:
                payload["spacing"] = spacing
            
            await self._initialize_client()
            result = await self.client.post(
                "/transform/align_objects",
                json=payload,
                timeout=self._get_timeout('standard')
            )
            
            if result.get('success'):
                aligned_count = result.get('aligned_count', 0)
                axis_used = result.get('axis', axis)
                alignment_used = result.get('alignment', alignment)
                spacing_used = result.get('spacing')
                transformations = result.get('transformations', [])
                
                axis_names = {'x': 'X (left-right)', 'y': 'Y (up-down)', 'z': 'Z (forward-back)'}
                axis_display = axis_names.get(axis_used, axis_used)
                
                alignment_names = {
                    'min': 'minimum (left/bottom/front)',
                    'max': 'maximum (right/top/back)', 
                    'center': 'center (middle)'
                }
                alignment_display = alignment_names.get(alignment_used, alignment_used)
                
                spacing_text = ""
                if spacing_used is not None:
                    spacing_text = f"\n• **Spacing:** {spacing_used} units between objects"
                
                # Show transformation details
                transform_details = ""
                if transformations:
                    details = []
                    for t in transformations[:5]:  # Limit to first 5
                        old_pos = t.get('old_position', [0, 0, 0])
                        new_pos = t.get('new_position', [0, 0, 0])
                        details.append(
                            f"  - **{t.get('object', 'Unknown')}**\n" +
                            f"    From: [{old_pos[0]:.2f}, {old_pos[1]:.2f}, {old_pos[2]:.2f}]\n" +
                            f"    To: [{new_pos[0]:.2f}, {new_pos[1]:.2f}, {new_pos[2]:.2f}]"
                        )
                    
                    more_details = f"\n\n*Showing 5 of {len(transformations)} transformations*" if len(transformations) > 5 else ""
                    transform_details = f"\n\n**Object movements:**\n" + "\n\n".join(details) + more_details
                
                return [types.TextContent(
                    type="text",
                    text=f"✅ **Aligned {aligned_count} objects successfully**\n\n" +
                         f"• **Axis:** {axis_display}\n" +
                         f"• **Alignment:** {alignment_display}" +
                         spacing_text + transform_details
                )]
            else:
                return [types.TextContent(
                    type="text",
                    text=f"❌ Object alignment failed: {result.get('error', 'Unknown error')}"
                )]
                
        except aiohttp.ClientError as e:
            return [types.TextContent(
                type="text",
                text=f"❌ Connection error: {str(e)}. Is Isaac Sim running with WorldBuilder extension?"
            )]

    async def _get_metrics(self, args: Dict[str, Any]) -> List[types.TextContent]:
        """Get performance metrics and statistics from WorldBuilder extension."""
        try:
            format_type = args.get('format', 'json')
            await self._initialize_client()
            if format_type == 'prom':
                result = await self.client.get("/metrics.prom", timeout=self._get_timeout('fast'))
            else:
                result = await self.client.get("/metrics", timeout=self._get_timeout('fast'))
            
            if format_type == 'prom':
                # Return raw Prometheus text format (support multiple possible keys)
                prom_text = result.get('_raw_text') or result.get('prometheus_metrics') or result.get('raw_response') or result.get('text', str(result))
                return [types.TextContent(
                    type="text",
                    text=f"✅ **Prometheus Metrics Retrieved**\n\n```\n{prom_text}\n```"
                )]
            else:
                if result.get('success'):
                    metrics = result.get('metrics', {})
                    return [types.TextContent(
                        type="text",
                        text=(
                            "✅ **WorldBuilder Metrics**\n\n"
                            f"• **Requests Received:** {metrics.get('requests_received', 0)}\n"
                            f"• **Errors:** {metrics.get('errors', 0)}\n"
                            f"• **Elements Created:** {metrics.get('elements_created', 0)}\n"
                            f"• **Batches Created:** {metrics.get('batches_created', 0)}\n"
                            f"• **Assets Placed:** {metrics.get('assets_placed', 0)}\n"
                            f"• **Objects Queried:** {metrics.get('objects_queried', 0)}\n"
                            f"• **Transformations Applied:** {metrics.get('transformations_applied', 0)}\n"
                            f"• **Server Uptime:** {metrics.get('uptime_seconds', 0):.1f}s"
                        )
                    )]
                else:
                    return [types.TextContent(type="text", text=f"❌ Failed: {result.get('error', 'Unknown error')}")]
        except aiohttp.ClientError as e:
            return [types.TextContent(
                type="text",
                text=f"❌ Connection error: {str(e)}. Is Isaac Sim running with WorldBuilder extension?"
            )]

    async def _metrics_prometheus(self, args: Dict[str, Any]) -> List[types.TextContent]:
        """Get WorldBuilder metrics in Prometheus format for monitoring systems."""
        try:
            await self._initialize_client()
            result = await self.client.get("/metrics.prom", timeout=self._get_timeout('fast'))
            prom_text = result.get('_raw_text') or result.get('prometheus_metrics') or result.get('raw_response') or result.get('text', str(result))
            return [types.TextContent(
                type="text",
                text=f"✅ **Prometheus Metrics Retrieved**\n\n```\n{prom_text}\n```"
            )]
        except aiohttp.ClientError as e:
            return [types.TextContent(
                type="text",
                text=f"❌ Connection error: {str(e)}. Is Isaac Sim running with WorldBuilder extension?"
            )]

async def main():
    """Main entry point for the MCP server."""
    # Unified logging (stderr by default; env-driven options)
    setup_logging('worldbuilder')
    logger.info("🚀 Starting Isaac Sim WorldBuilder MCP Server")
    
    # Initialize MCP server
    mcp_server = WorldBuilderMCP()
    
    try:
        # Run the server
        async with stdio_server() as (read_stream, write_stream):
            await mcp_server.server.run(
                read_stream,
                write_stream,
                InitializationOptions(
                    server_name="worldbuilder",
                    server_version="0.1.0",
                    capabilities=mcp_server.server.get_capabilities(
                        notification_options=NotificationOptions(),
                        experimental_capabilities={}
                    ),
                ),
            )
    finally:
        # Clean up HTTP client
        await mcp_server.client.close()

if __name__ == "__main__":
    asyncio.run(main())
