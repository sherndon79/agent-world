"""Transport contract definitions for WorldSurveyor operations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List


@dataclass(frozen=True)
class ToolContract:
    operation: str
    http_route: str
    http_method: str
    mcp_tool: str


TOOL_CONTRACTS: List[ToolContract] = [
    ToolContract("get_health", "health", "GET", "worldsurveyor_health_check"),
    ToolContract("get_health", "health", "GET", "worldsurveyor_health"),
    ToolContract("get_metrics", "metrics", "GET", "worldsurveyor_get_metrics"),
    ToolContract("get_metrics", "metrics", "GET", "worldsurveyor_metrics"),
    ToolContract("get_prometheus_metrics", "metrics.prom", "GET", "worldsurveyor_metrics_prometheus"),
    ToolContract("waypoints_summary", "waypoints", "GET", "worldsurveyor_waypoints_summary"),
    ToolContract("create_waypoint", "waypoints/create", "POST", "worldsurveyor_create_waypoint"),
    ToolContract("list_waypoints", "waypoints/list", "GET", "worldsurveyor_list_waypoints"),
    ToolContract("update_waypoint", "waypoints/update", "POST", "worldsurveyor_update_waypoint"),
    ToolContract("remove_waypoint", "waypoints/remove", "POST", "worldsurveyor_remove_waypoint"),
    ToolContract("remove_selected_waypoints", "waypoints/remove_selected", "POST", "worldsurveyor_remove_selected_waypoints"),
    ToolContract("clear_waypoints", "waypoints/clear", "POST", "worldsurveyor_clear_waypoints"),
    ToolContract("export_waypoints", "waypoints/export", "GET", "worldsurveyor_export_waypoints"),
    ToolContract("import_waypoints", "waypoints/import", "POST", "worldsurveyor_import_waypoints"),
    ToolContract("goto_waypoint", "waypoints/goto", "POST", "worldsurveyor_goto_waypoint"),
    ToolContract("create_group", "groups/create", "POST", "worldsurveyor_create_group"),
    ToolContract("list_groups", "groups/list", "GET", "worldsurveyor_list_groups"),
    ToolContract("get_group", "groups/get", "GET", "worldsurveyor_get_group"),
    ToolContract("remove_group", "groups/remove", "POST", "worldsurveyor_remove_group"),
    ToolContract("group_hierarchy", "groups/hierarchy", "GET", "worldsurveyor_group_hierarchy"),
    ToolContract("add_waypoint_to_groups", "groups/add_waypoint", "POST", "worldsurveyor_add_waypoint_to_groups"),
    ToolContract("remove_waypoint_from_groups", "groups/remove_waypoint", "POST", "worldsurveyor_remove_waypoint_from_groups"),
    ToolContract("get_waypoint_groups", "groups/of_waypoint", "GET", "worldsurveyor_get_waypoint_groups"),
    ToolContract("get_group_waypoints", "groups/waypoints", "GET", "worldsurveyor_get_group_waypoints"),
    ToolContract("set_markers_visible", "markers/visible", "POST", "worldsurveyor_set_markers_visible"),
    ToolContract("set_individual_marker_visible", "markers/individual", "POST", "worldsurveyor_set_individual_marker_visible"),
    ToolContract("set_selective_markers_visible", "markers/selective", "POST", "worldsurveyor_set_selective_markers_visible"),
    ToolContract("debug_status", "markers/debug", "GET", "worldsurveyor_debug_status"),
]

HTTP_OPERATIONS: Dict[str, ToolContract] = {contract.http_route: contract for contract in TOOL_CONTRACTS}
MCP_OPERATIONS: Dict[str, ToolContract] = {contract.mcp_tool: contract for contract in TOOL_CONTRACTS}

__all__ = ["ToolContract", "TOOL_CONTRACTS", "HTTP_OPERATIONS", "MCP_OPERATIONS"]
