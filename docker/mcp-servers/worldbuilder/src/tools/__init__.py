#!/usr/bin/env python3
"""
WorldBuilder Tools Registration

Imports and registers all WorldBuilder tools with FastMCP.
"""

from mcp.server.fastmcp import FastMCP


def register_tools(mcp_instance: FastMCP):
    """Register all WorldBuilder tools with the FastMCP instance."""

    # Import all tool modules
    from . import elements, scene, assets, spatial, system

    # Set the mcp instance for all tool modules
    elements.mcp = mcp_instance
    scene.mcp = mcp_instance
    assets.mcp = mcp_instance
    spatial.mcp = mcp_instance
    system.mcp = mcp_instance

    # Manually register each tool function with FastMCP
    # Element Management Tools
    mcp_instance.tool()(elements.worldbuilder_add_element)
    mcp_instance.tool()(elements.worldbuilder_create_batch)
    mcp_instance.tool()(elements.worldbuilder_remove_element)
    mcp_instance.tool()(elements.worldbuilder_batch_info)

    # Scene Management Tools
    mcp_instance.tool()(scene.worldbuilder_clear_scene)
    mcp_instance.tool()(scene.worldbuilder_clear_path)
    mcp_instance.tool()(scene.worldbuilder_get_scene)
    mcp_instance.tool()(scene.worldbuilder_scene_status)
    mcp_instance.tool()(scene.worldbuilder_list_elements)

    # Asset Management Tools
    mcp_instance.tool()(assets.worldbuilder_place_asset)
    mcp_instance.tool()(assets.worldbuilder_transform_asset)

    # Spatial Query Tools
    mcp_instance.tool()(spatial.worldbuilder_query_objects_by_type)
    mcp_instance.tool()(spatial.worldbuilder_query_objects_in_bounds)
    mcp_instance.tool()(spatial.worldbuilder_query_objects_near_point)
    mcp_instance.tool()(spatial.worldbuilder_calculate_bounds)
    mcp_instance.tool()(spatial.worldbuilder_find_ground_level)
    mcp_instance.tool()(spatial.worldbuilder_align_objects)

    # System Tools
    mcp_instance.tool()(system.worldbuilder_health_check)
    mcp_instance.tool()(system.worldbuilder_request_status)
    mcp_instance.tool()(system.worldbuilder_get_metrics)
    mcp_instance.tool()(system.worldbuilder_metrics_prometheus)

    return [
        # Element Management Tools
        "worldbuilder_add_element",
        "worldbuilder_create_batch",
        "worldbuilder_remove_element",
        "worldbuilder_batch_info",

        # Scene Management Tools
        "worldbuilder_clear_scene",
        "worldbuilder_clear_path",
        "worldbuilder_get_scene",
        "worldbuilder_scene_status",
        "worldbuilder_list_elements",

        # Asset Management Tools
        "worldbuilder_place_asset",
        "worldbuilder_transform_asset",

        # Spatial Query Tools
        "worldbuilder_query_objects_by_type",
        "worldbuilder_query_objects_in_bounds",
        "worldbuilder_query_objects_near_point",
        "worldbuilder_calculate_bounds",
        "worldbuilder_find_ground_level",
        "worldbuilder_align_objects",

        # System Tools
        "worldbuilder_health_check",
        "worldbuilder_request_status",
        "worldbuilder_get_metrics",
        "worldbuilder_metrics_prometheus",
    ]