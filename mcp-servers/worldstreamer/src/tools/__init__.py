#!/usr/bin/env python3
"""
WorldStreamer Tools Registration (Stdio)

Provides tool function references for stdio MCP server.
"""


def get_tool_functions():
    """Get all WorldStreamer tool functions for stdio server."""
    # Import all tool modules
    from . import streaming, system

    return {
        # Streaming Management Tools
        "worldstreamer_start_streaming": streaming.worldstreamer_start_streaming,
        "worldstreamer_stop_streaming": streaming.worldstreamer_stop_streaming,
        "worldstreamer_get_status": streaming.worldstreamer_get_status,
        "worldstreamer_get_streaming_urls": streaming.worldstreamer_get_streaming_urls,
        "worldstreamer_validate_environment": streaming.worldstreamer_validate_environment,

        # System Tools
        "worldstreamer_health_check": system.worldstreamer_health_check,
        "worldstreamer_get_metrics": system.worldstreamer_get_metrics,
        "worldstreamer_metrics_prometheus": system.worldstreamer_metrics_prometheus,
    }


def get_tool_names():
    """Get list of available tool names."""
    return [
        # Streaming Management Tools
        "worldstreamer_start_streaming",
        "worldstreamer_stop_streaming",
        "worldstreamer_get_status",
        "worldstreamer_get_streaming_urls",
        "worldstreamer_validate_environment",

        # System Tools
        "worldstreamer_health_check",
        "worldstreamer_get_metrics",
        "worldstreamer_metrics_prometheus",
    ]