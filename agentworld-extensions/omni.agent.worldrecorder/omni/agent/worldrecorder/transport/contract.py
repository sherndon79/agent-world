"""Transport contract definitions for WorldRecorder operations."""

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
    ToolContract("get_health", "health", "GET", "worldrecorder_health_check"),
    ToolContract("get_metrics", "metrics", "GET", "worldrecorder_get_metrics"),
    ToolContract("get_prometheus_metrics", "metrics.prom", "GET", "worldrecorder_metrics_prometheus"),
    ToolContract("get_status", "video/status", "GET", "worldrecorder_get_status"),
    ToolContract("start_video", "video/start", "POST", "worldrecorder_start_video"),
    ToolContract("cancel_video", "video/cancel", "POST", "worldrecorder_cancel_video"),
    ToolContract("capture_frame", "viewport/capture_frame", "POST", "worldrecorder_capture_frame"),
    ToolContract("cleanup_frames", "cleanup/frames", "POST", "worldrecorder_cleanup_frames"),
    # Recording aliases -------------------------------------------------------
    ToolContract("get_status", "recording/status", "GET", "worldrecorder_recording_status"),
    ToolContract("start_video", "recording/start", "POST", "worldrecorder_start_recording"),
    ToolContract("cancel_video", "recording/cancel", "POST", "worldrecorder_cancel_recording"),
    # Convenience aliases -----------------------------------------------------
    ToolContract("get_health", "health", "GET", "worldrecorder_health"),
]

HTTP_OPERATIONS: Dict[str, ToolContract] = {contract.http_route: contract for contract in TOOL_CONTRACTS}
MCP_OPERATIONS: Dict[str, ToolContract] = {contract.mcp_tool: contract for contract in TOOL_CONTRACTS}

__all__ = ["ToolContract", "TOOL_CONTRACTS", "HTTP_OPERATIONS", "MCP_OPERATIONS"]
