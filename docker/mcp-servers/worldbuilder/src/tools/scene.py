#!/usr/bin/env python3
"""
WorldBuilder Scene Management Tools

Tools for managing overall scene state, clearing, and inspection.
"""

from typing import Any, Dict
from mcp.server.fastmcp import FastMCP

from client import get_client
from config import config

# FastMCP instance (will be set by main.py)
mcp: FastMCP = None



async def worldbuilder_clear_scene(path: str = "/World", confirm: bool = False) -> Dict[str, Any]:
    """Clear entire scenes or specific paths (bulk removal).

    Args:
        path: USD path to clear (e.g., '/World' for entire scene)
        confirm: Confirmation flag for destructive operation
    """
    client = get_client()

    args = {"path": path, "confirm": confirm}
    timeout = config.get_timeout('clear_scene')
    result = await client.request('clear_path', payload=args, timeout=timeout)
    return result



async def worldbuilder_clear_path(path: str, confirm: bool = False) -> Dict[str, Any]:
    """Surgical removal of specific USD stage paths. More precise than clear_scene for targeted hierarchy cleanup.

    Args:
        path: Specific USD path to remove (e.g., '/World/Buildings/House1', '/World/incomplete_batch')
        confirm: Confirmation flag for destructive operation
    """
    client = get_client()

    args = {"path": path, "confirm": confirm}
    timeout = config.get_timeout('clear_path')
    result = await client.request('clear_path', payload=args, timeout=timeout)
    return result



async def worldbuilder_get_scene(include_metadata: bool = True) -> Dict[str, Any]:
    """Get complete scene structure with hierarchical details.

    Args:
        include_metadata: Include detailed metadata for each element
    """
    client = get_client()

    args = {"include_metadata": include_metadata}
    result = await client.request('get_scene', method="GET", timeout=10)
    return result



async def worldbuilder_scene_status() -> Dict[str, Any]:
    """Get scene health status and basic statistics."""
    client = get_client()

    timeout = config.get_timeout('scene_status')
    result = await client.request('scene_status', method="GET", timeout=timeout)
    return result



async def worldbuilder_list_elements(
    filter_type: str = "",
    page: int = 1,
    page_size: int = 50,
    include_metadata: bool = False
) -> Dict[str, Any]:
    """Get flat listing of all scene elements.

    Args:
        filter_type: Filter by element type (cube, sphere, etc.)
        page: Page number for pagination (1-based)
        page_size: Number of elements per page
        include_metadata: Include detailed metadata for each element
    """
    client = get_client()

    # Note: Isaac Sim uses GET with query params, not POST with payload
    params = {}
    if filter_type:
        params["filter_type"] = filter_type
    if page != 1:
        params["page"] = page
    if page_size != 50:
        params["page_size"] = page_size
    if include_metadata:
        params["include_metadata"] = include_metadata

    result = await client.request('list_elements', method="GET", params=params)
    return result