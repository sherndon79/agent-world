#!/usr/bin/env python3
"""
WorldBuilder Asset Management Tools

Tools for placing and manipulating USD assets in the scene.
"""

from typing import Any, Dict, List, Optional
from mcp.server.fastmcp import FastMCP

from client import get_client
from config import config

# FastMCP instance (will be set by main.py)
mcp: FastMCP = None



async def worldbuilder_place_asset(
    name: str,
    asset_path: str,
    prim_path: str = "",
    position: List[float] = None,
    rotation: List[float] = None,
    scale: List[float] = None
) -> Dict[str, Any]:
    """Place USD assets in Isaac Sim scene via reference.

    Args:
        name: Unique name for the asset instance
        asset_path: Path to USD asset file (e.g., '/path/to/asset.usd')
        prim_path: Target prim path in scene (e.g., '/World/my_asset')
        position: XYZ position [x, y, z] in world coordinates (exactly 3 items required)
        rotation: XYZ rotation [rx, ry, rz] in degrees (exactly 3 items required)
        scale: XYZ scale [x, y, z] multipliers (exactly 3 items required)
    """
    client = get_client()

    args = {
        "name": name,
        "asset_path": asset_path
    }

    if prim_path:
        args["prim_path"] = prim_path
    if position is not None:
        args["position"] = position
    if rotation is not None:
        args["rotation"] = rotation
    if scale is not None:
        args["scale"] = scale

    timeout = config.get_timeout('place_asset')
    result = await client.request('place_asset', payload=args, timeout=timeout)
    return result



async def worldbuilder_transform_asset(
    prim_path: str,
    position: Optional[List[float]] = None,
    rotation: Optional[List[float]] = None,
    scale: Optional[List[float]] = None
) -> Dict[str, Any]:
    """Transform existing assets in Isaac Sim scene (move, rotate, scale).

    Args:
        prim_path: USD path of existing asset to transform (e.g., '/World/my_asset')
        position: New XYZ position [x, y, z] in world coordinates (optional)
        rotation: New XYZ rotation [rx, ry, rz] in degrees (optional, exactly 3 items required)
        scale: New XYZ scale [x, y, z] multipliers (optional)
    """
    client = get_client()

    args = {"prim_path": prim_path}

    if position is not None:
        args["position"] = position
    if rotation is not None:
        args["rotation"] = rotation
    if scale is not None:
        args["scale"] = scale

    timeout = config.get_timeout('transform_asset')
    result = await client.request('transform_asset', payload=args, timeout=timeout)
    return result