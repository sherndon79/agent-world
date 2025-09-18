"""Transport contract definitions for WorldBuilder operations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List


@dataclass(frozen=True)
class ToolContract:
    operation: str
    http_route: str
    http_method: str
    mcp_tool: str


TOOL_CONTRACTS: List[ToolContract] = [
    ToolContract("get_health", "health", "GET", "worldbuilder_health_check"),
    ToolContract("get_metrics", "metrics", "GET", "worldbuilder_get_metrics"),
    ToolContract("get_prometheus_metrics", "metrics.prom", "GET", "worldbuilder_metrics_prometheus"),
    ToolContract("add_element", "add_element", "POST", "worldbuilder_add_element"),
    ToolContract("create_batch", "create_batch", "POST", "worldbuilder_create_batch"),
    ToolContract("place_asset", "place_asset", "POST", "worldbuilder_place_asset"),
    ToolContract("transform_asset", "transform_asset", "POST", "worldbuilder_transform_asset"),
    ToolContract("remove_element", "remove_element", "POST", "worldbuilder_remove_element"),
    ToolContract("clear_path", "clear_path", "POST", "worldbuilder_clear_path"),
    ToolContract("get_scene", "get_scene", "GET", "worldbuilder_get_scene"),
    ToolContract("scene_status", "scene_status", "GET", "worldbuilder_scene_status"),
    ToolContract("list_elements", "list_elements", "GET", "worldbuilder_list_elements"),
    ToolContract("batch_info", "batch_info", "GET", "worldbuilder_batch_info"),
    ToolContract("request_status", "request_status", "GET", "worldbuilder_request_status"),
    ToolContract("query_objects_by_type", "query/objects_by_type", "GET", "worldbuilder_query_objects_by_type"),
    ToolContract("query_objects_in_bounds", "query/objects_in_bounds", "GET", "worldbuilder_query_objects_in_bounds"),
    ToolContract("query_objects_near_point", "query/objects_near_point", "GET", "worldbuilder_query_objects_near_point"),
    ToolContract("calculate_bounds", "transform/calculate_bounds", "POST", "worldbuilder_calculate_bounds"),
    ToolContract("find_ground_level", "transform/find_ground_level", "POST", "worldbuilder_find_ground_level"),
    ToolContract("align_objects", "transform/align_objects", "POST", "worldbuilder_align_objects"),
]

# Provide quick lookup maps
HTTP_OPERATIONS = {contract.http_route: contract for contract in TOOL_CONTRACTS}
MCP_OPERATIONS = {contract.mcp_tool: contract for contract in TOOL_CONTRACTS}

__all__ = ["ToolContract", "TOOL_CONTRACTS", "HTTP_OPERATIONS", "MCP_OPERATIONS"]
