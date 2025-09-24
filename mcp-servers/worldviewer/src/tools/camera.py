#!/usr/bin/env python3
"""
WorldViewer Camera Management Tools

Tools for camera positioning, framing, and orbital movements.
"""

from typing import Any, Dict, List, Optional

from client import get_client
from config import config

# FastMCP instance (will be set by main.py)


async def worldviewer_set_camera_position(
    position: List[float],
    target: Optional[List[float]] = None,
    up_vector: Optional[List[float]] = None
) -> Dict[str, Any]:
    """Set camera position and optionally target in Isaac Sim viewport.

    Args:
        position: Camera position as [x, y, z] (exactly 3 items required)
        target: Optional look-at target as [x, y, z] (exactly 3 items required)
        up_vector: Optional up vector as [x, y, z] (exactly 3 items required)
    """
    client = get_client()

    args = {"position": position}
    if target is not None:
        args["target"] = target
    if up_vector is not None:
        args["up_vector"] = up_vector

    result = await client.request('camera/set_position', payload=args)
    return result


async def worldviewer_frame_object(
    object_path: str,
    distance: Optional[float] = None
) -> Dict[str, Any]:
    """Frame an object in the Isaac Sim viewport.

    Args:
        object_path: USD path to the object (e.g., '/World/my_cube')
        distance: Optional distance from object (auto-calculated if not provided)
    """
    client = get_client()

    args = {"object_path": object_path}
    if distance is not None:
        args["distance"] = distance

    result = await client.request('camera/frame_object', payload=args)
    return result


async def worldviewer_orbit_camera(
    center: List[float],
    distance: float,
    elevation: float,
    azimuth: float
) -> Dict[str, Any]:
    """Position camera in orbital coordinates around a center point.

    Args:
        center: Center point to orbit around as [x, y, z] (exactly 3 items required)
        distance: Distance from center point
        elevation: Elevation angle in degrees (-90 to 90)
        azimuth: Azimuth angle in degrees (0 = front, 90 = right)
    """
    client = get_client()

    args = {
        "center": center,
        "distance": distance,
        "elevation": elevation,
        "azimuth": azimuth
    }

    result = await client.request('camera/orbit', payload=args)
    return result


async def worldviewer_get_camera_status() -> Dict[str, Any]:
    """Get current camera status and position."""
    client = get_client()

    result = await client.request('camera/status', method="GET")
    return result


async def worldviewer_get_asset_transform(
    usd_path: str,
    calculation_mode: str = "auto"
) -> Dict[str, Any]:
    """Get transform information (position, rotation, scale, bounds) for a specific asset in the scene.

    Args:
        usd_path: USD path to the asset (e.g., '/World/my_cube' or '/World/ProperCity')
        calculation_mode: How to calculate position for complex assets (auto, center, pivot, bounds)
    """
    client = get_client()

    params = {"usd_path": usd_path, "calculation_mode": calculation_mode}
    result = await client.request('get_asset_transform', method="GET", params=params)
    return result