#!/usr/bin/env python3
"""
WorldSurveyor Visibility Management Tools

Tools for controlling waypoint marker visibility and appearance.
"""

from typing import Any, Dict, List

from client import get_client
from config import config

# FastMCP instance (will be set by main.py)


async def worldsurveyor_set_markers_visible(visible: bool) -> Dict[str, Any]:
    """Set global visibility for all waypoint markers.

    Args:
        visible: Whether markers should be visible
    """
    client = get_client()

    args = {"visible": visible}
    result = await client.request('markers/visible', payload=args)
    return result


async def worldsurveyor_set_selective_markers_visible(
    waypoint_ids: List[str],
    visible: bool
) -> Dict[str, Any]:
    """Set visibility for specific waypoint markers.

    Args:
        waypoint_ids: List of waypoint IDs to affect
        visible: Whether these markers should be visible
    """
    client = get_client()

    args = {
        "waypoint_ids": waypoint_ids,
        "visible": visible
    }

    result = await client.request('markers/selective', payload=args)
    return result


async def worldsurveyor_set_individual_marker_visible(
    waypoint_id: str,
    visible: bool
) -> Dict[str, Any]:
    """Set visibility for a single waypoint marker.

    Args:
        waypoint_id: ID of the waypoint to affect
        visible: Whether this marker should be visible
    """
    client = get_client()

    args = {
        "waypoint_id": waypoint_id,
        "visible": visible
    }

    result = await client.request('markers/individual', payload=args)
    return result