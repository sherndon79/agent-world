"""Transport contract definitions for WorldViewer operations."""

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
    ToolContract('get_health', 'health', 'GET', 'worldviewer_extension_health'),
    ToolContract('get_metrics', 'metrics', 'GET', 'worldviewer_get_metrics'),
    ToolContract('get_prometheus_metrics', 'metrics.prom', 'GET', 'worldviewer_metrics_prometheus'),
    ToolContract('get_camera_status', 'camera/status', 'GET', 'worldviewer_get_camera_status'),
    ToolContract('set_camera_position', 'camera/set_position', 'POST', 'worldviewer_set_camera_position'),
    ToolContract('frame_object', 'camera/frame_object', 'POST', 'worldviewer_frame_object'),
    ToolContract('orbit_camera', 'camera/orbit', 'POST', 'worldviewer_orbit_camera'),
    ToolContract('smooth_move', 'camera/smooth_move', 'POST', 'worldviewer_smooth_move'),
    ToolContract('orbit_shot', 'camera/orbit_shot', 'POST', 'worldviewer_orbit_shot'),
    ToolContract('arc_shot', 'camera/arc_shot', 'POST', 'worldviewer_arc_shot'),
    ToolContract('stop_movement', 'camera/stop_movement', 'POST', 'worldviewer_stop_movement'),
    ToolContract('stop_movement', 'movement/stop', 'POST', 'worldviewer_stop_movement'),
    ToolContract('movement_status', 'camera/movement_status', 'GET', 'worldviewer_movement_status'),
    ToolContract('shot_queue_status', 'camera/shot_queue_status', 'GET', 'worldviewer_get_queue_status'),
    ToolContract('queue_play', 'camera/queue/play', 'POST', 'worldviewer_play_queue'),
    ToolContract('queue_pause', 'camera/queue/pause', 'POST', 'worldviewer_pause_queue'),
    ToolContract('queue_stop', 'camera/queue/stop', 'POST', 'worldviewer_stop_queue'),
    ToolContract('asset_transform', 'get_asset_transform', 'GET', 'worldviewer_get_asset_transform'),
    ToolContract('request_status', 'request_status', 'GET', 'worldviewer_request_status'),
]

HTTP_OPERATIONS: Dict[str, ToolContract] = {contract.http_route: contract for contract in TOOL_CONTRACTS}
MCP_OPERATIONS: Dict[str, ToolContract] = {contract.mcp_tool: contract for contract in TOOL_CONTRACTS}

__all__ = ['ToolContract', 'TOOL_CONTRACTS', 'HTTP_OPERATIONS', 'MCP_OPERATIONS']
