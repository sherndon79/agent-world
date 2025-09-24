#!/usr/bin/env python3
"""
WorldSurveyor Group Management Tools

Tools for organizing waypoints into hierarchical groups.
"""

from typing import Any, Dict, List, Optional
from mcp.server.fastmcp import FastMCP

from client import get_client
from config import config

# FastMCP instance (will be set by main.py)
mcp: FastMCP = None


async def worldsurveyor_create_group(
    name: str,
    parent_group_id: Optional[str] = None,
    description: Optional[str] = None,
    color: Optional[List[float]] = None
) -> Dict[str, Any]:
    """Create a new waypoint group for hierarchical organization.

    Args:
        name: Name of the group
        parent_group_id: Optional parent group ID for hierarchy
        description: Optional description of the group
        color: Optional color as [r, g, b] values (0-1)
    """
    client = get_client()

    args = {"name": name}

    if parent_group_id is not None:
        args["parent_group_id"] = parent_group_id
    if description is not None:
        args["description"] = description
    if color is not None:
        # Convert RGB array to hex string for extension database storage
        if isinstance(color, list) and len(color) == 3:
            r = int(round(color[0] * 255))
            g = int(round(color[1] * 255))
            b = int(round(color[2] * 255))
            args["color"] = f"#{r:02x}{g:02x}{b:02x}"
        else:
            args["color"] = color

    result = await client.request('groups/create', payload=args)
    return result


async def worldsurveyor_list_groups(parent_group_id: Optional[str] = None) -> Dict[str, Any]:
    """List all groups or groups under a specific parent.

    Args:
        parent_group_id: Optional parent group ID to filter by
    """
    client = get_client()

    params = {}
    if parent_group_id is not None:
        params["parent_group_id"] = parent_group_id

    result = await client.request('groups/list', method="GET", params=params)
    return result


async def worldsurveyor_get_group(group_id: str) -> Dict[str, Any]:
    """Get detailed information about a specific group.

    Args:
        group_id: ID of the group to retrieve
    """
    client = get_client()

    params = {"group_id": group_id}
    result = await client.request('groups/get', method="GET", params=params)
    return result


async def worldsurveyor_update_group(
    group_id: str,
    name: Optional[str] = None,
    description: Optional[str] = None,
    color: Optional[List[float]] = None,
    parent_group_id: Optional[str] = None
) -> Dict[str, Any]:
    """Update an existing waypoint group.

    Args:
        group_id: ID of the group to update
        name: New name (optional)
        description: New description (optional)
        color: New color as [r, g, b] values (0-1) (optional)
        parent_group_id: New parent group ID (optional)
    """
    client = get_client()

    args = {"group_id": group_id}

    if name is not None:
        args["name"] = name
    if description is not None:
        args["description"] = description
    if color is not None:
        args["color"] = color
    if parent_group_id is not None:
        args["parent_group_id"] = parent_group_id

    result = await client.request('groups/update', payload=args)
    return result


async def worldsurveyor_remove_group(
    group_id: str,
    recursive: bool = False
) -> Dict[str, Any]:
    """Remove a group and optionally its children.

    Args:
        group_id: ID of the group to remove
        recursive: Whether to remove child groups recursively
    """
    client = get_client()

    args = {
        "group_id": group_id,
        "recursive": recursive
    }

    result = await client.request('groups/remove', payload=args)
    return result


async def worldsurveyor_clear_groups(confirm: bool = False) -> Dict[str, Any]:
    """Clear all groups from the scene.

    Args:
        confirm: Confirmation flag for destructive operation
    """
    client = get_client()

    args = {"confirm": confirm}
    result = await client.request('groups/clear', payload=args)
    return result


async def worldsurveyor_get_group_waypoints(
    group_id: str,
    include_children: bool = False
) -> Dict[str, Any]:
    """Get all waypoints in a specific group.

    Args:
        group_id: ID of the group
        include_children: Whether to include waypoints from child groups
    """
    client = get_client()

    params = {
        "group_id": group_id,
        "include_children": include_children
    }

    result = await client.request('groups/waypoints', method="GET", params=params)
    return result


async def worldsurveyor_add_waypoint_to_groups(
    waypoint_id: str,
    group_ids: List[str]
) -> Dict[str, Any]:
    """Add a waypoint to one or more groups.

    Args:
        waypoint_id: ID of the waypoint to add
        group_ids: List of group IDs to add the waypoint to
    """
    client = get_client()

    args = {
        "waypoint_id": waypoint_id,
        "group_ids": group_ids
    }

    result = await client.request('groups/add_waypoint', payload=args)
    return result


async def worldsurveyor_remove_waypoint_from_groups(
    waypoint_id: str,
    group_ids: List[str]
) -> Dict[str, Any]:
    """Remove a waypoint from one or more groups.

    Args:
        waypoint_id: ID of the waypoint to remove
        group_ids: List of group IDs to remove the waypoint from
    """
    client = get_client()

    args = {
        "waypoint_id": waypoint_id,
        "group_ids": group_ids
    }

    result = await client.request('groups/remove_waypoint', payload=args)
    return result


async def worldsurveyor_get_group_hierarchy(
    root_group_id: Optional[str] = None,
    max_depth: int = 10
) -> Dict[str, Any]:
    """Get hierarchical tree structure of groups.

    Args:
        root_group_id: Optional root group to start from (default: all root groups)
        max_depth: Maximum depth to traverse (default: 10)
    """
    client = get_client()

    params = {"max_depth": max_depth}
    if root_group_id is not None:
        params["root_group_id"] = root_group_id

    result = await client.request('groups/hierarchy', method="GET", params=params)
    return result


async def worldsurveyor_get_waypoint_groups(waypoint_id: str) -> Dict[str, Any]:
    """Get all groups that contain a specific waypoint.

    Args:
        waypoint_id: ID of the waypoint
    """
    client = get_client()

    params = {"waypoint_id": waypoint_id}
    result = await client.request('groups/of_waypoint', method="GET", params=params)
    return result