#!/usr/bin/env python3
"""
WorldSurveyor Tools Registration

Imports and registers all WorldSurveyor tools with FastMCP.
"""

from mcp.server.fastmcp import FastMCP


def register_tools(mcp_instance: FastMCP):
    """Register all WorldSurveyor tools with the FastMCP instance."""

    # Import all tool modules
    from . import waypoints, groups, visibility, import_export, system

    # Set the mcp instance for all tool modules
    waypoints.mcp = mcp_instance
    groups.mcp = mcp_instance
    visibility.mcp = mcp_instance
    import_export.mcp = mcp_instance
    system.mcp = mcp_instance

    # Manually register each tool function with FastMCP
    # Waypoint Management Tools
    mcp_instance.tool()(waypoints.worldsurveyor_create_waypoint)
    mcp_instance.tool()(waypoints.worldsurveyor_list_waypoints)
    mcp_instance.tool()(waypoints.worldsurveyor_remove_waypoint)
    mcp_instance.tool()(waypoints.worldsurveyor_update_waypoint)
    mcp_instance.tool()(waypoints.worldsurveyor_goto_waypoint)
    mcp_instance.tool()(waypoints.worldsurveyor_clear_waypoints)

    # Group Management Tools
    mcp_instance.tool()(groups.worldsurveyor_create_group)
    mcp_instance.tool()(groups.worldsurveyor_list_groups)
    mcp_instance.tool()(groups.worldsurveyor_get_group)
    mcp_instance.tool()(groups.worldsurveyor_update_group)
    mcp_instance.tool()(groups.worldsurveyor_remove_group)
    mcp_instance.tool()(groups.worldsurveyor_clear_groups)
    mcp_instance.tool()(groups.worldsurveyor_get_group_waypoints)
    mcp_instance.tool()(groups.worldsurveyor_add_waypoint_to_groups)
    mcp_instance.tool()(groups.worldsurveyor_remove_waypoint_from_groups)
    mcp_instance.tool()(groups.worldsurveyor_get_group_hierarchy)
    mcp_instance.tool()(groups.worldsurveyor_get_waypoint_groups)

    # Visibility Management Tools
    mcp_instance.tool()(visibility.worldsurveyor_set_markers_visible)
    mcp_instance.tool()(visibility.worldsurveyor_set_selective_markers_visible)
    mcp_instance.tool()(visibility.worldsurveyor_set_individual_marker_visible)

    # Import/Export Tools
    mcp_instance.tool()(import_export.worldsurveyor_export_waypoints)
    mcp_instance.tool()(import_export.worldsurveyor_import_waypoints)

    # System Tools
    mcp_instance.tool()(system.worldsurveyor_health_check)
    mcp_instance.tool()(system.worldsurveyor_get_metrics)
    mcp_instance.tool()(system.worldsurveyor_metrics_prometheus)
    mcp_instance.tool()(system.worldsurveyor_debug_status)

    return [
        # Waypoint Management Tools
        "worldsurveyor_create_waypoint",
        "worldsurveyor_list_waypoints",
        "worldsurveyor_remove_waypoint",
        "worldsurveyor_update_waypoint",
        "worldsurveyor_goto_waypoint",
        "worldsurveyor_clear_waypoints",

        # Group Management Tools
        "worldsurveyor_create_group",
        "worldsurveyor_list_groups",
        "worldsurveyor_get_group",
        "worldsurveyor_update_group",
        "worldsurveyor_remove_group",
        "worldsurveyor_clear_groups",
        "worldsurveyor_get_group_waypoints",
        "worldsurveyor_add_waypoint_to_groups",
        "worldsurveyor_remove_waypoint_from_groups",
        "worldsurveyor_get_group_hierarchy",
        "worldsurveyor_get_waypoint_groups",

        # Visibility Management Tools
        "worldsurveyor_set_markers_visible",
        "worldsurveyor_set_selective_markers_visible",
        "worldsurveyor_set_individual_marker_visible",

        # Import/Export Tools
        "worldsurveyor_export_waypoints",
        "worldsurveyor_import_waypoints",

        # System Tools
        "worldsurveyor_health_check",
        "worldsurveyor_get_metrics",
        "worldsurveyor_metrics_prometheus",
        "worldsurveyor_debug_status",
    ]