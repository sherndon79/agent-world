#!/usr/bin/env python3
"""
WorldRecorder Tools Registration

Imports and registers all WorldRecorder tools with FastMCP.
"""

from mcp.server.fastmcp import FastMCP


def register_tools(mcp_instance: FastMCP):
    """Register all WorldRecorder tools with the FastMCP instance."""

    # Import all tool modules
    from . import recording, capture, system

    # Set the mcp instance for all tool modules
    recording.mcp = mcp_instance
    capture.mcp = mcp_instance
    system.mcp = mcp_instance

    # Manually register each tool function with FastMCP
    # Recording Management Tools
    mcp_instance.tool()(recording.worldrecorder_start_video)
    mcp_instance.tool()(recording.worldrecorder_start_recording)
    mcp_instance.tool()(recording.worldrecorder_cancel_recording)
    mcp_instance.tool()(recording.worldrecorder_recording_status)
    mcp_instance.tool()(recording.worldrecorder_cancel_video)
    mcp_instance.tool()(recording.worldrecorder_get_status)

    # Frame Capture Tools
    mcp_instance.tool()(capture.worldrecorder_capture_frame)
    mcp_instance.tool()(capture.worldrecorder_cleanup_frames)

    # System Tools
    mcp_instance.tool()(system.worldrecorder_health_check)
    mcp_instance.tool()(system.worldrecorder_get_metrics)
    mcp_instance.tool()(system.worldrecorder_metrics_prometheus)

    return [
        # Recording Management Tools
        "worldrecorder_start_video",
        "worldrecorder_start_recording",
        "worldrecorder_cancel_recording",
        "worldrecorder_recording_status",
        "worldrecorder_cancel_video",
        "worldrecorder_get_status",

        # Frame Capture Tools
        "worldrecorder_capture_frame",
        "worldrecorder_cleanup_frames",

        # System Tools
        "worldrecorder_health_check",
        "worldrecorder_get_metrics",
        "worldrecorder_metrics_prometheus",
    ]