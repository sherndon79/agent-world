#!/usr/bin/env python3
"""
WorldSurveyor Waypoint Management Tools

Tools for creating, managing, and navigating waypoints in the 3D scene.
"""

from typing import Any, Dict, List, Optional
from mcp.server.fastmcp import FastMCP

from client import get_client
from config import config

# FastMCP instance (will be set by main.py)
mcp: FastMCP = None


async def worldsurveyor_create_waypoint(
    position: List[float],
    waypoint_type: str = "point_of_interest",
    name: Optional[str] = None,
    target: Optional[List[float]] = None,
    metadata: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Create a new spatial waypoint at specified position with type and metadata.

    Args:
        position: 3D position [x, y, z] for the waypoint (exactly 3 items required)
        waypoint_type: Type of waypoint (camera_position, directional_lighting, object_anchor, point_of_interest, selection_mark, lighting_position, audio_source, spawn_point)
        name: Optional custom name for the waypoint
        target: Optional target coordinates [x, y, z] for camera positioning
        metadata: Optional additional metadata for the waypoint
    """
    client = get_client()

    args = {
        "position": position,
        "waypoint_type": waypoint_type
    }

    if name is not None:
        args["name"] = name
    if target is not None:
        args["target"] = target
    if metadata is not None:
        args["metadata"] = metadata

    result = await client.request('waypoints/create', payload=args)
    return result


async def worldsurveyor_list_waypoints(waypoint_type: Optional[str] = None) -> Dict[str, Any]:
    """List all waypoints with optional filtering by type.

    Args:
        waypoint_type: Optional filter by waypoint type (camera_position, directional_lighting, object_anchor, point_of_interest, selection_mark, lighting_position, audio_source, spawn_point)
    """
    client = get_client()

    params = {}
    if waypoint_type is not None:
        params["waypoint_type"] = waypoint_type

    result = await client.request('waypoints/list', method="GET", params=params)
    return result


async def worldsurveyor_remove_waypoint(waypoint_id: str) -> Dict[str, Any]:
    """Remove a waypoint from the scene.

    Args:
        waypoint_id: ID of the waypoint to remove
    """
    client = get_client()

    args = {"waypoint_id": waypoint_id}
    result = await client.request('waypoints/remove', payload=args)
    return result


async def worldsurveyor_update_waypoint(
    waypoint_id: str,
    position: Optional[List[float]] = None,
    name: Optional[str] = None,
    target: Optional[List[float]] = None,
    metadata: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Update an existing waypoint.

    Args:
        waypoint_id: ID of the waypoint to update
        position: New position [x, y, z] (optional)
        name: New name (optional)
        target: New target coordinates [x, y, z] (optional)
        metadata: New metadata (optional)
    """
    client = get_client()

    args = {"waypoint_id": waypoint_id}

    if position is not None:
        args["position"] = position
    if name is not None:
        args["name"] = name
    if target is not None:
        args["target"] = target
    if metadata is not None:
        args["metadata"] = metadata

    result = await client.request('waypoints/update', payload=args)
    return result


async def worldsurveyor_goto_waypoint(
    waypoint_id: str,
    smooth_transition: bool = True,
    transition_duration: float = 2.0
) -> Dict[str, Any]:
    """Navigate camera to a specific waypoint.

    Args:
        waypoint_id: ID of the waypoint to navigate to
        smooth_transition: Whether to use smooth camera transition
        transition_duration: Duration of the transition in seconds
    """
    client = get_client()

    args = {
        "waypoint_id": waypoint_id,
        "smooth_transition": smooth_transition,
        "transition_duration": transition_duration
    }

    result = await client.request('waypoints/goto', payload=args)
    return result


async def worldsurveyor_clear_waypoints(confirm: bool = False) -> Dict[str, Any]:
    """Clear all waypoints from the scene.

    Args:
        confirm: Confirmation flag for destructive operation
    """
    client = get_client()

    args = {"confirm": confirm}
    result = await client.request('waypoints/clear', payload=args)
    return result