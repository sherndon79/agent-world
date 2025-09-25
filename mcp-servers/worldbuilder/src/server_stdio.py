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
                name="worldbuilder_remove_element",
                description="Remove specific elements from Isaac Sim scene by USD path",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "usd_path": {"type": "string", "description": "USD path of element to remove (e.g., '/World/my_cube')"}
                    },
                    "required": ["usd_path"]
                }
            ),
            Tool(
                name="worldbuilder_batch_info",
                description="Get detailed information about a specific batch/group in the scene",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "batch_name": {"type": "string", "description": "Name of the batch to get information about"}
                    },
                    "required": ["batch_name"]
                }
            ),

            # Scene Management Tools
            Tool(
                name="worldbuilder_clear_scene",
                description="Clear entire scenes or specific paths (bulk removal)",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "USD path to clear (e.g., '/World' for entire scene)"},
                        "confirm": {"type": "boolean", "description": "Confirmation flag for destructive operation"}
                    },
                    "required": []
                }
            ),
            Tool(
                name="worldbuilder_clear_path",
                description="Surgical removal of specific USD stage paths. More precise than clear_scene for targeted hierarchy cleanup",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Specific USD path to remove (e.g., '/World/Buildings/House1', '/World/incomplete_batch')"},
                        "confirm": {"type": "boolean", "description": "Confirmation flag for destructive operation"}
                    },
                    "required": ["path"]
                }
            ),
            Tool(
                name="worldbuilder_get_scene",
                description="Get complete scene structure with hierarchical details",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "include_metadata": {"type": "boolean", "description": "Include detailed metadata for each element"}
                    },
                    "required": []
                }
            ),
            Tool(
                name="worldbuilder_scene_status",
                description="Get scene health status and basic statistics",
                inputSchema={"type": "object", "properties": {}}
            ),
            Tool(
                name="worldbuilder_list_elements",
                description="Get flat listing of all scene elements",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "filter_type": {"type": "string", "description": "Filter by element type (cube, sphere, etc.)"},
                        "page": {"type": "integer", "description": "Page number for pagination (1-based)"},
                        "page_size": {"type": "integer", "description": "Number of elements per page"},
                        "include_metadata": {"type": "boolean", "description": "Include detailed metadata for each element"}
                    },
                    "required": []
                }
            ),

            # Asset Management Tools
            Tool(
                name="worldbuilder_place_asset",
                description="Place USD assets in Isaac Sim scene via reference",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "Unique name for the asset instance"},
                        "asset_path": {"type": "string", "description": "Path to USD asset file (e.g., '/path/to/asset.usd')"},
                        "prim_path": {"type": "string", "description": "Target prim path in scene (e.g., '/World/my_asset')"},
                        "position": {"type": "array", "items": {"type": "number"}, "description": "XYZ position [x, y, z] in world coordinates (exactly 3 items required)"},
                        "rotation": {"type": "array", "items": {"type": "number"}, "description": "XYZ rotation [rx, ry, rz] in degrees (exactly 3 items required)"},
                        "scale": {"type": "array", "items": {"type": "number"}, "description": "XYZ scale [x, y, z] multipliers (exactly 3 items required)"}
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
                        "prim_path": {"type": "string", "description": "USD path of existing asset to transform (e.g., '/World/my_asset')"},
                        "position": {"type": "array", "items": {"type": "number"}, "description": "New XYZ position [x, y, z] in world coordinates (optional)"},
                        "rotation": {"type": "array", "items": {"type": "number"}, "description": "New XYZ rotation [rx, ry, rz] in degrees (optional, exactly 3 items required)"},
                        "scale": {"type": "array", "items": {"type": "number"}, "description": "New XYZ scale [x, y, z] multipliers (optional)"}
                    },
                    "required": ["prim_path"]
                }
            ),

            # Spatial Query Tools
            Tool(
                name="worldbuilder_query_objects_by_type",
                description="Query objects by semantic type (furniture, lighting, primitive, etc.)",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "object_type": {"type": "string", "description": "Object type to search for (e.g. 'furniture', 'lighting', 'decoration', 'architecture', 'vehicle', 'primitive')"}
                    },
                    "required": ["object_type"]
                }
            ),
            Tool(
                name="worldbuilder_query_objects_in_bounds",
                description="Query objects within spatial bounds (3D bounding box)",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "min_bounds": {"type": "array", "items": {"type": "number"}, "description": "Minimum bounds [x, y, z]"},
                        "max_bounds": {"type": "array", "items": {"type": "number"}, "description": "Maximum bounds [x, y, z]"}
                    },
                    "required": ["min_bounds", "max_bounds"]
                }
            ),
            Tool(
                name="worldbuilder_query_objects_near_point",
                description="Query objects near a specific point within radius",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "point": {"type": "array", "items": {"type": "number"}, "description": "Point coordinates [x, y, z]"},
                        "radius": {"type": "number", "description": "Search radius in world units"}
                    },
                    "required": ["point"]
                }
            ),
            Tool(
                name="worldbuilder_calculate_bounds",
                description="Calculate combined bounding box for multiple objects. Useful for understanding spatial extent of object groups",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "objects": {"type": "array", "items": {"type": "string"}, "description": "List of USD paths to objects (e.g., ['/World/cube1', '/World/sphere1'])"}
                    },
                    "required": ["objects"]
                }
            ),
            Tool(
                name="worldbuilder_find_ground_level",
                description="Find ground level at a position using consensus algorithm. Analyzes nearby objects to determine appropriate ground height",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "position": {"type": "array", "items": {"type": "number"}, "description": "Position coordinates [x, y, z]"},
                        "search_radius": {"type": "number", "description": "Search radius for ground detection"}
                    },
                    "required": ["position"]
                }
            ),
            Tool(
                name="worldbuilder_align_objects",
                description="Align objects along specified axis (x, y, z) with optional uniform spacing. Useful for organizing object layouts",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "objects": {"type": "array", "items": {"type": "string"}, "description": "List of USD paths to objects to align"},
                        "axis": {"type": "string", "description": "Axis to align along (x=left-right, y=up-down, z=forward-back)"},
                        "alignment": {"type": "string", "description": "Alignment type: min (left/bottom/front), max (right/top/back), center (middle)"},
                        "spacing": {"type": "number", "description": "Uniform spacing between objects (optional)"}
                    },
                    "required": ["objects", "axis"]
                }
            ),

            # System Tools
            Tool(
                name="worldbuilder_health_check",
                description="Check Isaac Sim WorldBuilder Extension health and API status",
                inputSchema={"type": "object", "properties": {}}
            ),
            Tool(
                name="worldbuilder_request_status",
                description="Get status of ongoing operations and request queue",
                inputSchema={"type": "object", "properties": {}}
            ),
            Tool(
                name="worldbuilder_get_metrics",
                description="Get performance metrics and statistics from WorldBuilder extension",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "format_type": {"type": "string", "description": "Output format: json for structured data, prom for Prometheus format"}
                    },
                    "required": []
                }
            ),
            Tool(
                name="worldbuilder_metrics_prometheus",
                description="Get WorldBuilder metrics in Prometheus format for monitoring systems",
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