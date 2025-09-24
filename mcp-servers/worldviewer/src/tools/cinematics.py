#!/usr/bin/env python3
"""
WorldViewer Cinematic Movement Tools

Tools for smooth camera movements, arc shots, and orbit shots.
"""

from typing import Any, Dict, List, Optional

from client import get_client
from config import config

# FastMCP instance (will be set by main.py)


async def worldviewer_smooth_move(
    start_position: List[float],
    end_position: List[float],
    start_target: List[float],
    end_target: List[float],
    start_rotation: Optional[List[float]] = None,
    end_rotation: Optional[List[float]] = None,
    speed: Optional[float] = None,
    duration: Optional[float] = None,
    easing_type: str = "ease_in_out",
    execution_mode: str = "auto"
) -> Dict[str, Any]:
    """Smooth camera movement between two camera states (position + rotation) with easing.

    Args:
        start_position: Starting camera position [x, y, z]
        end_position: Ending camera position [x, y, z]
        start_target: Starting look-at target [x, y, z] (required for practical cinematography)
        end_target: Ending look-at target [x, y, z] (required for practical cinematography)
        start_rotation: Starting camera rotation [pitch, yaw, roll] in degrees (optional)
        end_rotation: Ending camera rotation [pitch, yaw, roll] in degrees (optional)
        speed: Average speed in units per second (alternative to duration)
        duration: Duration in seconds (overrides speed if provided)
        easing_type: Movement easing function (linear, ease_in, ease_out, ease_in_out, bounce, elastic)
        execution_mode: Execution mode (auto or manual)
    """
    client = get_client()

    args = {
        "start_position": start_position,
        "end_position": end_position,
        "start_target": start_target,
        "end_target": end_target,
        "easing_type": easing_type,
        "execution_mode": execution_mode
    }

    if start_rotation is not None:
        args["start_rotation"] = start_rotation
    if end_rotation is not None:
        args["end_rotation"] = end_rotation
    if speed is not None:
        args["speed"] = speed
    if duration is not None:
        args["duration"] = duration

    result = await client.request('camera/smooth_move', payload=args)
    return result


async def worldviewer_arc_shot(
    start_position: List[float],
    end_position: List[float],
    start_target: List[float],
    end_target: List[float],
    speed: Optional[float] = None,
    duration: Optional[float] = None,
    movement_style: str = "standard",
    execution_mode: str = "auto"
) -> Dict[str, Any]:
    """Cinematic arc shot with curved Bezier path between two camera positions.

    Args:
        start_position: Starting camera position [x, y, z]
        end_position: Ending camera position [x, y, z]
        start_target: Starting look-at target [x, y, z] (required for practical cinematography)
        end_target: Ending look-at target [x, y, z] (required for practical cinematography)
        speed: Average speed in units per second (alternative to duration)
        duration: Duration in seconds (overrides speed if provided)
        movement_style: Arc movement style
        execution_mode: Execution mode (auto or manual)
    """
    client = get_client()

    args = {
        "start_position": start_position,
        "end_position": end_position,
        "start_target": start_target,
        "end_target": end_target,
        "movement_style": movement_style,
        "execution_mode": execution_mode
    }

    if speed is not None:
        args["speed"] = speed
    if duration is not None:
        args["duration"] = duration

    result = await client.request('camera/arc_shot', payload=args)
    return result


async def worldviewer_orbit_shot(
    center: List[float],
    distance: float = 10.0,
    start_azimuth: float = 0.0,
    end_azimuth: float = 360.0,
    elevation: float = 15.0,
    duration: float = 8.0,
    target_object: Optional[str] = None,
    start_position: Optional[List[float]] = None,
    start_target: Optional[List[float]] = None,
    end_target: Optional[List[float]] = None
) -> Dict[str, Any]:
    """Enhanced orbit shot with full orbital cinematography control and end_target support.

    Args:
        center: Center point to orbit around [x, y, z]
        distance: Distance from center point
        start_azimuth: Starting azimuth angle in degrees
        end_azimuth: Ending azimuth angle in degrees
        elevation: Elevation angle in degrees
        duration: Duration in seconds
        target_object: Optional object to focus on
        start_position: Optional starting camera position
        start_target: Optional starting look-at target
        end_target: Optional ending look-at target
    """
    client = get_client()

    args = {
        "center": center,
        "distance": distance,
        "start_azimuth": start_azimuth,
        "end_azimuth": end_azimuth,
        "elevation": elevation,
        "duration": duration
    }

    if target_object is not None:
        args["target_object"] = target_object
    if start_position is not None:
        args["start_position"] = start_position
    if start_target is not None:
        args["start_target"] = start_target
    if end_target is not None:
        args["end_target"] = end_target

    result = await client.request('camera/orbit_shot', payload=args)
    return result


async def worldviewer_stop_movement() -> Dict[str, Any]:
    """Stop an active cinematic movement."""
    client = get_client()

    result = await client.request('camera/stop_movement', payload={})
    return result


async def worldviewer_movement_status(movement_id: str) -> Dict[str, Any]:
    """Get status of a cinematic movement.

    Args:
        movement_id: ID of the movement to check
    """
    client = get_client()

    params = {"movement_id": movement_id}
    result = await client.request('camera/movement_status', method="GET", params=params)
    return result