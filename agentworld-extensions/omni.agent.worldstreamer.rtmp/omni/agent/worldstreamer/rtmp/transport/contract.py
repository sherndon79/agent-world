"""Transport contract definitions for WorldStreamer RTMP operations."""

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
    ToolContract("get_health", "health", "GET", "worldstreamer_health_check"),
    ToolContract("start_streaming", "streaming/start", "POST", "worldstreamer_start_streaming"),
    ToolContract("stop_streaming", "streaming/stop", "POST", "worldstreamer_stop_streaming"),
    ToolContract("get_status", "streaming/status", "GET", "worldstreamer_get_status"),
    ToolContract("get_streaming_urls", "streaming/urls", "GET", "worldstreamer_get_streaming_urls"),
    ToolContract("validate_environment", "streaming/environment/validate", "GET", "worldstreamer_validate_environment"),
]

HTTP_OPERATIONS: Dict[str, ToolContract] = {contract.http_route: contract for contract in TOOL_CONTRACTS}
MCP_OPERATIONS: Dict[str, ToolContract] = {contract.mcp_tool: contract for contract in TOOL_CONTRACTS}

__all__ = ["ToolContract", "TOOL_CONTRACTS", "HTTP_OPERATIONS", "MCP_OPERATIONS"]
