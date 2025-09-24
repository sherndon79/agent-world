#!/usr/bin/env python3
"""
WorldSurveyor Import/Export Tools

Tools for importing and exporting waypoint data.
"""

from typing import Any, Dict, List, Optional
from mcp.server.fastmcp import FastMCP

from client import get_client
from config import config

# FastMCP instance (will be set by main.py)
mcp: FastMCP = None


async def worldsurveyor_export_waypoints(
    format_type: str = "json",
    include_groups: bool = True,
    group_ids: Optional[List[str]] = None
) -> Dict[str, Any]:
    """Export waypoints and groups to various formats.

    Args:
        format_type: Export format (json, csv, xml)
        include_groups: Whether to include group information
        group_ids: Optional list of specific group IDs to export
    """
    client = get_client()

    params = {
        "format": format_type,
        "include_groups": include_groups
    }

    if group_ids is not None:
        params["group_ids"] = ",".join(group_ids)

    result = await client.request('waypoints/export', method="GET", params=params)
    return result


async def worldsurveyor_import_waypoints(
    waypoint_data: Dict[str, Any],
    format_type: str = "json",
    merge_groups: bool = True,
    overwrite_existing: bool = False
) -> Dict[str, Any]:
    """Import waypoints and groups from data.

    Args:
        waypoint_data: Waypoint data to import
        format_type: Data format (json, csv, xml)
        merge_groups: Whether to merge with existing groups
        overwrite_existing: Whether to overwrite existing waypoints
    """
    client = get_client()

    args = {
        "data": waypoint_data,
        "format": format_type,
        "merge_groups": merge_groups,
        "overwrite_existing": overwrite_existing
    }

    result = await client.request('waypoints/import', payload=args)
    return result