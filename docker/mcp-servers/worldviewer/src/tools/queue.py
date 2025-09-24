#!/usr/bin/env python3
"""
WorldViewer Queue Management Tools

Tools for managing the cinematic shot queue.
"""

from typing import Any, Dict
from mcp.server.fastmcp import FastMCP

from client import get_client
from config import config

# FastMCP instance (will be set by main.py)
mcp: FastMCP = None


async def worldviewer_get_queue_status() -> Dict[str, Any]:
    """Get comprehensive shot queue status with timing information and queue state."""
    client = get_client()

    result = await client.request('camera/shot_queue_status', method="GET")
    return result


async def worldviewer_play_queue() -> Dict[str, Any]:
    """Start/resume queue processing."""
    client = get_client()

    result = await client.request('camera/queue/play', payload={})
    return result


async def worldviewer_pause_queue() -> Dict[str, Any]:
    """Pause queue processing (current movement continues, no new movements start)."""
    client = get_client()

    result = await client.request('camera/queue/pause', payload={})
    return result


async def worldviewer_stop_queue() -> Dict[str, Any]:
    """Stop and clear entire queue."""
    client = get_client()

    result = await client.request('camera/queue/stop', payload={})
    return result