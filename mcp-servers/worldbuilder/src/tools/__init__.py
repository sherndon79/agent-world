#!/usr/bin/env python3
"""
WorldBuilder Tools Registration (Stdio)

Provides tool function references for stdio MCP server.
"""


def get_tool_functions():
    """Get all WorldBuilder tool functions for stdio server."""
    # Import all tool modules
    from . import elements, assets, scene, spatial, system

    return {
        # Element Management Tools
        "worldbuilder_add_element": elements.worldbuilder_add_element,
        "worldbuilder_create_batch": elements.worldbuilder_create_batch,
        "worldbuilder_remove_element": elements.worldbuilder_remove_element,
        "worldbuilder_batch_info": elements.worldbuilder_batch_info,

        # Asset Management Tools
        "worldbuilder_place_asset": assets.worldbuilder_place_asset,
        "worldbuilder_transform_asset": assets.worldbuilder_transform_asset,

        # Scene Management Tools
        "worldbuilder_clear_scene": scene.worldbuilder_clear_scene,
        "worldbuilder_clear_path": scene.worldbuilder_clear_path,
        "worldbuilder_get_scene": scene.worldbuilder_get_scene,
        "worldbuilder_scene_status": scene.worldbuilder_scene_status,
        "worldbuilder_list_elements": scene.worldbuilder_list_elements,

        # Spatial Analysis Tools
        "worldbuilder_query_objects_by_type": spatial.worldbuilder_query_objects_by_type,
        "worldbuilder_query_objects_in_bounds": spatial.worldbuilder_query_objects_in_bounds,
        "worldbuilder_query_objects_near_point": spatial.worldbuilder_query_objects_near_point,
        "worldbuilder_calculate_bounds": spatial.worldbuilder_calculate_bounds,
        "worldbuilder_find_ground_level": spatial.worldbuilder_find_ground_level,
        "worldbuilder_align_objects": spatial.worldbuilder_align_objects,

        # System Tools
        "worldbuilder_health_check": system.worldbuilder_health_check,
        "worldbuilder_request_status": system.worldbuilder_request_status,
        "worldbuilder_get_metrics": system.worldbuilder_get_metrics,
        "worldbuilder_metrics_prometheus": system.worldbuilder_metrics_prometheus,
    }


def get_tool_names():
    """Get list of available tool names."""
    return list(get_tool_functions().keys())