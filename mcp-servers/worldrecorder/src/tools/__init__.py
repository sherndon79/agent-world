#!/usr/bin/env python3
"""
WorldRecorder Tools Registration (Stdio)

Provides tool function references for stdio MCP server.
"""


def get_tool_functions():
    """Get all WorldRecorder tool functions for stdio server."""
    # Import all tool modules
    from . import recording, capture, system

    return {
        # Video Recording Tools
        "worldrecorder_start_video": recording.worldrecorder_start_video,
        "worldrecorder_start_recording": recording.worldrecorder_start_recording,
        "worldrecorder_cancel_recording": recording.worldrecorder_cancel_recording,
        "worldrecorder_recording_status": recording.worldrecorder_recording_status,
        "worldrecorder_cancel_video": recording.worldrecorder_cancel_video,
        "worldrecorder_get_status": recording.worldrecorder_get_status,

        # Frame Capture Tools
        "worldrecorder_capture_frame": capture.worldrecorder_capture_frame,
        "worldrecorder_cleanup_frames": capture.worldrecorder_cleanup_frames,

        # System Tools
        "worldrecorder_health_check": system.worldrecorder_health_check,
        "worldrecorder_get_metrics": system.worldrecorder_get_metrics,
        "worldrecorder_metrics_prometheus": system.worldrecorder_metrics_prometheus,
    }


def get_tool_names():
    """Get list of available tool names."""
    return list(get_tool_functions().keys())