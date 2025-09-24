#!/usr/bin/env python3
"""
WorldStreamer Tools Registration

Imports and registers all WorldStreamer tools with FastMCP.
"""

from mcp.server.fastmcp import FastMCP


def register_tools(mcp_instance: FastMCP):
    """Register all WorldStreamer tools with the FastMCP instance."""

    # Import all tool modules
    from . import streaming, system

    # Set the mcp instance for all tool modules
    streaming.mcp = mcp_instance
    system.mcp = mcp_instance

    # Manually register each tool function with FastMCP
    # Streaming Management Tools
    mcp_instance.tool()(streaming.worldstreamer_start_streaming)
    mcp_instance.tool()(streaming.worldstreamer_stop_streaming)
    mcp_instance.tool()(streaming.worldstreamer_get_status)
    mcp_instance.tool()(streaming.worldstreamer_get_streaming_urls)
    mcp_instance.tool()(streaming.worldstreamer_validate_environment)

    # System Tools
    mcp_instance.tool()(system.worldstreamer_health_check)
    mcp_instance.tool()(system.worldstreamer_get_metrics)
    mcp_instance.tool()(system.worldstreamer_metrics_prometheus)

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