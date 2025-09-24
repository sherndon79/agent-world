#!/usr/bin/env python3
"""
WorldViewer Tools Registration

Imports and registers all WorldViewer tools with FastMCP.
"""

from mcp.server.fastmcp import FastMCP


def register_tools(mcp_instance: FastMCP):
    """Register all WorldViewer tools with the FastMCP instance."""

    # Import all tool modules
    from . import camera, cinematics, queue, system

    # Set the mcp instance for all tool modules
    camera.mcp = mcp_instance
    cinematics.mcp = mcp_instance
    queue.mcp = mcp_instance
    system.mcp = mcp_instance

    # Manually register each tool function with FastMCP
    # Camera Management Tools
    mcp_instance.tool()(camera.worldviewer_set_camera_position)
    mcp_instance.tool()(camera.worldviewer_frame_object)
    mcp_instance.tool()(camera.worldviewer_orbit_camera)
    mcp_instance.tool()(camera.worldviewer_get_camera_status)
    mcp_instance.tool()(camera.worldviewer_get_asset_transform)

    # Cinematic Movement Tools
    mcp_instance.tool()(cinematics.worldviewer_smooth_move)
    mcp_instance.tool()(cinematics.worldviewer_arc_shot)
    mcp_instance.tool()(cinematics.worldviewer_orbit_shot)
    mcp_instance.tool()(cinematics.worldviewer_stop_movement)
    mcp_instance.tool()(cinematics.worldviewer_movement_status)

    # Queue Management Tools
    mcp_instance.tool()(queue.worldviewer_get_queue_status)
    mcp_instance.tool()(queue.worldviewer_play_queue)
    mcp_instance.tool()(queue.worldviewer_pause_queue)
    mcp_instance.tool()(queue.worldviewer_stop_queue)

    # System Tools
    mcp_instance.tool()(system.worldviewer_health_check)
    mcp_instance.tool()(system.worldviewer_get_metrics)
    mcp_instance.tool()(system.worldviewer_metrics_prometheus)

    return [
        # Camera Management Tools
        "worldviewer_set_camera_position",
        "worldviewer_frame_object",
        "worldviewer_orbit_camera",
        "worldviewer_get_camera_status",
        "worldviewer_get_asset_transform",

        # Cinematic Movement Tools
        "worldviewer_smooth_move",
        "worldviewer_arc_shot",
        "worldviewer_orbit_shot",
        "worldviewer_stop_movement",
        "worldviewer_movement_status",

        # Queue Management Tools
        "worldviewer_get_queue_status",
        "worldviewer_play_queue",
        "worldviewer_pause_queue",
        "worldviewer_stop_queue",

        # System Tools
        "worldviewer_health_check",
        "worldviewer_get_metrics",
        "worldviewer_metrics_prometheus",
    ]