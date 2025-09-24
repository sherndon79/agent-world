#!/usr/bin/env python3
"""
WorldBuilder Spatial Query Tools

Tools for spatial queries, bounds calculation, and object alignment.
"""

from typing import Any, Dict, List, Optional
from mcp.server.fastmcp import FastMCP

from client import get_client
from config import config

# FastMCP instance (will be set by main.py)
mcp: FastMCP = None



async def worldbuilder_query_objects_by_type(object_type: str) -> Dict[str, Any]:
    """Query objects by semantic type (furniture, lighting, primitive, etc.).

    Args:
        object_type: Object type to search for (e.g. 'furniture', 'lighting', 'decoration', 'architecture', 'vehicle', 'primitive')
    """
    client = get_client()

    args = {"type": object_type}
    timeout = config.get_timeout('query_objects')
    result = await client.request('query/objects_by_type', payload=args, timeout=timeout)
    return result



async def worldbuilder_query_objects_in_bounds(
    min_bounds: List[float],
    max_bounds: List[float]
) -> Dict[str, Any]:
    """Query objects within spatial bounds (3D bounding box).

    Args:
        min_bounds: Minimum bounds [x, y, z]
        max_bounds: Maximum bounds [x, y, z]
    """
    client = get_client()

    args = {
        "min_bounds": min_bounds,
        "max_bounds": max_bounds
    }

    timeout = config.get_timeout('query_objects')
    result = await client.request('query/objects_in_bounds', payload=args, timeout=timeout)
    return result



async def worldbuilder_query_objects_near_point(
    point: List[float],
    radius: float = 5.0
) -> Dict[str, Any]:
    """Query objects near a specific point within radius.

    Args:
        point: Point coordinates [x, y, z]
        radius: Search radius in world units
    """
    client = get_client()

    args = {
        "point": point,
        "radius": radius
    }

    timeout = config.get_timeout('query_objects')
    result = await client.request('query/objects_near_point', payload=args, timeout=timeout)
    return result



async def worldbuilder_calculate_bounds(objects: List[str]) -> Dict[str, Any]:
    """Calculate combined bounding box for multiple objects. Useful for understanding spatial extent of object groups.

    Args:
        objects: List of USD paths to objects (e.g., ['/World/cube1', '/World/sphere1'])
    """
    client = get_client()

    args = {"objects": objects}
    result = await client.request('transform/calculate_bounds', payload=args)
    return result



async def worldbuilder_find_ground_level(
    position: List[float],
    search_radius: float = 10.0
) -> Dict[str, Any]:
    """Find ground level at a position using consensus algorithm. Analyzes nearby objects to determine appropriate ground height.

    Args:
        position: Position coordinates [x, y, z]
        search_radius: Search radius for ground detection
    """
    client = get_client()

    args = {
        "position": position,
        "search_radius": search_radius
    }

    result = await client.request('transform/find_ground_level', payload=args)
    return result



async def worldbuilder_align_objects(
    objects: List[str],
    axis: str,
    alignment: str = "center",
    spacing: Optional[float] = None
) -> Dict[str, Any]:
    """Align objects along specified axis (x, y, z) with optional uniform spacing. Useful for organizing object layouts.

    Args:
        objects: List of USD paths to objects to align
        axis: Axis to align along (x=left-right, y=up-down, z=forward-back)
        alignment: Alignment type: min (left/bottom/front), max (right/top/back), center (middle)
        spacing: Uniform spacing between objects (optional)
    """
    client = get_client()

    args = {
        "objects": objects,
        "axis": axis,
        "alignment": alignment
    }

    if spacing is not None:
        args["spacing"] = spacing

    timeout = config.get_timeout('align_objects')
    result = await client.request('transform/align_objects', payload=args, timeout=timeout)
    return result