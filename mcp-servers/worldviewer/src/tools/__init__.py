#!/usr/bin/env python3
"""
WorldViewer Tools Registration (Stdio)

Provides tool function references for stdio MCP server.
"""


def get_tool_functions():
    """Get all WorldViewer tool functions for stdio server."""
    # Import all tool modules
    from . import camera, cinematics, queue, system

    return {
        # Camera Management Tools
        "worldviewer_set_camera_position": camera.worldviewer_set_camera_position,
        "worldviewer_frame_object": camera.worldviewer_frame_object,
        "worldviewer_orbit_camera": camera.worldviewer_orbit_camera,
        "worldviewer_get_camera_status": camera.worldviewer_get_camera_status,
        "worldviewer_get_asset_transform": camera.worldviewer_get_asset_transform,

        # Cinematic Movement Tools
        "worldviewer_smooth_move": cinematics.worldviewer_smooth_move,
        "worldviewer_arc_shot": cinematics.worldviewer_arc_shot,
        "worldviewer_orbit_shot": cinematics.worldviewer_orbit_shot,
        "worldviewer_stop_movement": cinematics.worldviewer_stop_movement,
        "worldviewer_movement_status": cinematics.worldviewer_movement_status,

        # Queue Management Tools
        "worldviewer_get_queue_status": queue.worldviewer_get_queue_status,
        "worldviewer_play_queue": queue.worldviewer_play_queue,
        "worldviewer_pause_queue": queue.worldviewer_pause_queue,
        "worldviewer_stop_queue": queue.worldviewer_stop_queue,

        # System Tools
        "worldviewer_health_check": system.worldviewer_health_check,
        "worldviewer_get_metrics": system.worldviewer_get_metrics,
        "worldviewer_metrics_prometheus": system.worldviewer_metrics_prometheus,
    }


def get_tool_names():
    """Get list of available tool names."""
    return list(get_tool_functions().keys())