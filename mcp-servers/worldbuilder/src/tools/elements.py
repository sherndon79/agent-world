#!/usr/bin/env python3
"""
WorldBuilder Element Management Tools

Tools for creating, managing, and organizing individual elements and batches.
"""

from typing import Any, Dict, List
from mcp.server.fastmcp import FastMCP

from client import get_client
from config import config

# FastMCP instance (will be set by main.py)
mcp: FastMCP = None


async def worldbuilder_add_element(
    element_type: str,
    name: str,
    position: List[float],
    color: List[float] = None,
    scale: List[float] = None,
    parent_path: str = "/World"
) -> Dict[str, Any]:
    """Add individual 3D elements (cubes, spheres, cylinders) to Isaac Sim scene.

    Args:
        element_type: Type of 3D primitive to create (cube, sphere, cylinder, cone)
        name: Unique name for the element
        position: XYZ position [x, y, z] in world coordinates (exactly 3 items required)
        color: RGB color [r, g, b] values between 0-1 (exactly 3 items required)
        scale: XYZ scale [x, y, z] multipliers (exactly 3 items required)
        parent_path: USD parent path for hierarchical placement (optional, defaults to /World)
    """
    client = get_client()

    args = {
        "element_type": element_type,
        "name": name,
        "position": position,
        "parent_path": parent_path
    }

    if color is not None:
        args["color"] = color
    if scale is not None:
        args["scale"] = scale

    timeout = config.get_timeout('add_element')
    result = await client.request('add_element', payload=args, timeout=timeout)
    return result


async def worldbuilder_create_batch(
    batch_name: str,
    elements: List[Dict[str, Any]],
    parent_path: str = "/World"
) -> Dict[str, Any]:
    """Create hierarchical batches of objects (furniture sets, buildings, etc.).

    Args:
        batch_name: Name for the batch/group
        elements: List of elements to create as a batch
        parent_path: USD path for the parent group
    """
    client = get_client()

    args = {
        "batch_name": batch_name,
        "elements": elements,
        "parent_path": parent_path
    }

    timeout = config.get_timeout('create_batch')
    result = await client.request('create_batch', payload=args, timeout=timeout)
    return result


async def worldbuilder_remove_element(usd_path: str) -> Dict[str, Any]:
    """Remove specific elements from Isaac Sim scene by USD path.

    Args:
        usd_path: USD path of element to remove (e.g., '/World/my_cube')
    """
    client = get_client()

    args = {"element_path": usd_path}
    result = await client.request('remove_element', payload=args)
    return result


async def worldbuilder_batch_info(batch_name: str) -> Dict[str, Any]:
    """Get detailed information about a specific batch/group in the scene.

    Args:
        batch_name: Name of the batch to get information about
    """
    client = get_client()

    args = {"batch_name": batch_name}
    result = await client.request('batch_info', payload=args)
    return result