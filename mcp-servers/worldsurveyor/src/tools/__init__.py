#!/usr/bin/env python3
"""
WorldSurveyor Tools Registration (Stdio)

Provides tool function references for stdio MCP server.
"""


def get_tool_functions():
    """Get all WorldSurveyor tool functions for stdio server."""
    # Import all tool modules
    from . import waypoints, groups, visibility, import_export, system

    return {
        # Waypoint Management Tools
        "worldsurveyor_create_waypoint": waypoints.worldsurveyor_create_waypoint,
        "worldsurveyor_list_waypoints": waypoints.worldsurveyor_list_waypoints,
        "worldsurveyor_remove_waypoint": waypoints.worldsurveyor_remove_waypoint,
        "worldsurveyor_update_waypoint": waypoints.worldsurveyor_update_waypoint,
        "worldsurveyor_goto_waypoint": waypoints.worldsurveyor_goto_waypoint,
        "worldsurveyor_clear_waypoints": waypoints.worldsurveyor_clear_waypoints,

        # Group Management Tools
        "worldsurveyor_create_group": groups.worldsurveyor_create_group,
        "worldsurveyor_list_groups": groups.worldsurveyor_list_groups,
        "worldsurveyor_get_group": groups.worldsurveyor_get_group,
        "worldsurveyor_update_group": groups.worldsurveyor_update_group,
        "worldsurveyor_remove_group": groups.worldsurveyor_remove_group,
        "worldsurveyor_clear_groups": groups.worldsurveyor_clear_groups,
        "worldsurveyor_get_group_waypoints": groups.worldsurveyor_get_group_waypoints,
        "worldsurveyor_add_waypoint_to_groups": groups.worldsurveyor_add_waypoint_to_groups,
        "worldsurveyor_remove_waypoint_from_groups": groups.worldsurveyor_remove_waypoint_from_groups,
        "worldsurveyor_get_group_hierarchy": groups.worldsurveyor_get_group_hierarchy,
        "worldsurveyor_get_waypoint_groups": groups.worldsurveyor_get_waypoint_groups,

        # Visibility Management Tools
        "worldsurveyor_set_markers_visible": visibility.worldsurveyor_set_markers_visible,
        "worldsurveyor_set_selective_markers_visible": visibility.worldsurveyor_set_selective_markers_visible,
        "worldsurveyor_set_individual_marker_visible": visibility.worldsurveyor_set_individual_marker_visible,

        # Import/Export Tools
        "worldsurveyor_export_waypoints": import_export.worldsurveyor_export_waypoints,
        "worldsurveyor_import_waypoints": import_export.worldsurveyor_import_waypoints,

        # System Tools
        "worldsurveyor_health_check": system.worldsurveyor_health_check,
        "worldsurveyor_get_metrics": system.worldsurveyor_get_metrics,
        "worldsurveyor_metrics_prometheus": system.worldsurveyor_metrics_prometheus,
        "worldsurveyor_debug_status": system.worldsurveyor_debug_status,
    }


def get_tool_names():
    """Get list of available tool names."""
    return list(get_tool_functions().keys())