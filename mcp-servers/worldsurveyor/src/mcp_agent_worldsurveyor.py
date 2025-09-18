#!/usr/bin/env python3
"""MCP Server for WorldSurveyor."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
from typing import Any, Dict, List

import aiohttp
from mcp.server import Server
from mcp.server.models import InitializationOptions
from mcp.server.stdio import stdio_server
from mcp.server.lowlevel import NotificationOptions
from mcp.types import Tool, TextContent

# Add shared modules to path
shared_path = os.path.join(os.path.dirname(__file__), '..', '..', 'shared')
if shared_path not in sys.path:
    sys.path.insert(0, shared_path)

from logging_setup import setup_logging
from mcp_base_client import MCPBaseClient

# Add agentworld-extensions to path for unified config
extensions_path = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'agentworld-extensions')
if os.path.exists(extensions_path) and extensions_path not in sys.path:
    sys.path.insert(0, extensions_path)

try:
    from agent_world_config import create_worldsurveyor_config
    config = create_worldsurveyor_config()
except ImportError:
    config = None

from agent_world_transport import normalize_transport_response
from omni.agent.worldsurveyor.errors import error_response
from omni.agent.worldsurveyor.transport import TOOL_CONTRACTS, MCP_OPERATIONS

logger = logging.getLogger(__name__)


class WorldSurveyorMCP:
    """MCP server exposing WorldSurveyor HTTP endpoints."""

    def __init__(self, base_url: str = "http://localhost:8891"):
        self.base_url = base_url.rstrip('/')
        self.server = Server("worldsurveyor")
        self.client = MCPBaseClient("WORLDSURVEYOR", self.base_url)
        self._register_tools()
        self._contract_map = MCP_OPERATIONS
        logger.info("WorldSurveyor MCP initialized at %s", self.base_url)

    async def _initialize_client(self) -> None:
        if not self.client._initialized:
            await self.client.initialize()

    async def __aenter__(self):
        await self._initialize_client()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.close()

    def _get_timeout(self, operation_type: str = 'standard') -> float:
        return 10.0

    def _register_tools(self) -> None:
        @self.server.list_tools()
        async def handle_list_tools() -> List[Tool]:
            return [
                Tool(
                    name="worldsurveyor_create_waypoint",
                    description="Create a new spatial waypoint at specified position with type and metadata",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "position": {
                                "type": "array",
                                "items": {"type": "number"},
                                "minItems": 3,
                                "maxItems": 3,
                                "description": "3D position [x, y, z] for the waypoint"
                            },
                            "waypoint_type": {
                                "type": "string",
                                "enum": [
                                    "camera_position",
                                    "directional_lighting",
                                    "object_anchor",
                                    "point_of_interest",
                                    "selection_mark",
                                    "lighting_position",
                                    "audio_source",
                                    "spawn_point"
                                ],
                                "default": "point_of_interest",
                                "description": "Type of waypoint to create"
                            },
                            "name": {
                                "type": "string",
                                "description": "Optional custom name for the waypoint"
                            },
                            "target": {
                                "type": "array",
                                "items": {"type": "number"},
                                "minItems": 3,
                                "maxItems": 3,
                                "default": [0.0, 0.0, 0.0],
                                "description": "Optional target coordinates [x, y, z] for camera positioning"
                            },
                            "metadata": {
                                "type": "object",
                                "description": "Optional additional metadata for the waypoint"
                            }
                        },
                        "required": ["position"],
                        "additionalProperties": False
                    }
                ),
                Tool(
                    name="worldsurveyor_list_waypoints",
                    description="List all waypoints with optional filtering by type",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "waypoint_type": {
                                "type": "string",
                                "enum": [
                                    "camera_position",
                                    "directional_lighting",
                                    "object_anchor",
                                    "point_of_interest",
                                    "selection_mark",
                                    "lighting_position",
                                    "audio_source",
                                    "spawn_point"
                                ],
                                "description": "Optional filter by waypoint type"
                            },
                            "group_id": {
                                "type": "string",
                                "description": "Optional filter by group ID"
                            }
                        },
                        "additionalProperties": False
                    }
                ),
                Tool(
                    name="worldsurveyor_health_check",
                    description="Check WorldSurveyor extension health and API status",
                    inputSchema={
                        "type": "object",
                        "additionalProperties": False
                    }
                ),
                Tool(
                    name="worldsurveyor_set_markers_visible",
                    description="Show or hide waypoint markers in the 3D scene for better spatial context",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "visible": {
                                "type": "boolean",
                                "description": "Whether to show (true) or hide (false) waypoint markers"
                            }
                        },
                        "required": ["visible"],
                        "additionalProperties": False
                    }
                ),
                Tool(
                    name="worldsurveyor_debug_status",
                    description="Get debug draw system status and marker information",
                    inputSchema={
                        "type": "object",
                        "additionalProperties": False
                    }
                ),
                Tool(
                    name="worldsurveyor_update_waypoint",
                    description="Update existing waypoint properties such as name or metadata",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "waypoint_id": {
                                "type": "string",
                                "description": "ID of the waypoint to update"
                            },
                            "name": {"type": "string"},
                            "waypoint_type": {"type": "string"},
                            "notes": {"type": "string"},
                            "metadata": {"type": "object"},
                            "position": {
                                "type": "array",
                                "items": {"type": "number"},
                                "minItems": 3,
                                "maxItems": 3
                            },
                            "target": {
                                "type": "array",
                                "items": {"type": "number"},
                                "minItems": 3,
                                "maxItems": 3
                            }
                        },
                        "required": ["waypoint_id"],
                        "additionalProperties": False
                    }
                ),
                Tool(
                    name="worldsurveyor_remove_waypoint",
                    description="Remove a waypoint by ID",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "waypoint_id": {
                                "type": "string",
                                "description": "ID of the waypoint to remove"
                            }
                        },
                        "required": ["waypoint_id"],
                        "additionalProperties": False
                    }
                ),
                Tool(
                    name="worldsurveyor_remove_selected_waypoints",
                    description="Remove multiple waypoints by IDs",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "waypoint_ids": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "List of waypoint IDs to remove"
                            }
                        },
                        "required": ["waypoint_ids"],
                        "additionalProperties": False
                    }
                ),
                Tool(
                    name="worldsurveyor_clear_waypoints",
                    description="Clear all waypoints from the scene",
                    inputSchema={
                        "type": "object",
                        "additionalProperties": False
                    }
                ),
                Tool(
                    name="worldsurveyor_create_group",
                    description="Create a waypoint group",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "parent_group_id": {"type": "string"},
                            "description": {"type": "string"}
                        },
                        "required": ["name"],
                        "additionalProperties": False
                    }
                ),
                Tool(
                    name="worldsurveyor_list_groups",
                    description="List waypoint groups",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "parent_group_id": {
                                "type": "string",
                                "description": "Optional parent group filter"
                            }
                        },
                        "additionalProperties": False
                    }
                ),
                Tool(
                    name="worldsurveyor_get_group",
                    description="Get details for a specific group",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "group_id": {
                                "type": "string",
                                "description": "ID of the group"
                            }
                        },
                        "required": ["group_id"],
                        "additionalProperties": False
                    }
                ),
                Tool(
                    name="worldsurveyor_remove_group",
                    description="Remove a waypoint group",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "group_id": {"type": "string"},
                            "cascade": {"type": "boolean"}
                        },
                        "required": ["group_id"],
                        "additionalProperties": False
                    }
                ),
                Tool(
                    name="worldsurveyor_group_hierarchy",
                    description="Get the hierarchy of waypoint groups",
                    inputSchema={
                        "type": "object",
                        "additionalProperties": False
                    }
                ),
                Tool(
                    name="worldsurveyor_add_waypoint_to_groups",
                    description="Add a waypoint to one or more groups",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "waypoint_id": {"type": "string"},
                            "group_ids": {
                                "type": "array",
                                "items": {"type": "string"}
                            }
                        },
                        "required": ["waypoint_id", "group_ids"],
                        "additionalProperties": False
                    }
                ),
                Tool(
                    name="worldsurveyor_remove_waypoint_from_groups",
                    description="Remove a waypoint from groups",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "waypoint_id": {"type": "string"},
                            "group_ids": {
                                "type": "array",
                                "items": {"type": "string"}
                            }
                        },
                        "required": ["waypoint_id", "group_ids"],
                        "additionalProperties": False
                    }
                ),
                Tool(
                    name="worldsurveyor_get_waypoint_groups",
                    description="List groups that contain a specific waypoint",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "waypoint_id": {
                                "type": "string",
                                "description": "Waypoint ID to fetch group memberships for"
                            }
                        },
                        "required": ["waypoint_id"],
                        "additionalProperties": False
                    }
                ),
                Tool(
                    name="worldsurveyor_get_group_waypoints",
                    description="Get all waypoints in a specific group",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "group_id": {
                                "type": "string",
                                "description": "ID of the group to get waypoints from"
                            },
                            "include_nested": {
                                "type": "boolean",
                                "default": False,
                                "description": "Whether to include waypoints from nested child groups"
                            }
                        },
                        "required": ["group_id"],
                        "additionalProperties": False
                    }
                ),
                Tool(
                    name="worldsurveyor_export_waypoints",
                    description="Export waypoints and groups to JSON format",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "include_groups": {
                                "type": "boolean",
                                "default": True,
                                "description": "Whether to include group information"
                            }
                        },
                        "additionalProperties": False
                    }
                ),
                Tool(
                    name="worldsurveyor_import_waypoints",
                    description="Import waypoints and groups from JSON format",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "import_data": {"type": "object"},
                            "merge_mode": {
                                "type": "string",
                                "enum": ["replace", "append"],
                                "default": "replace"
                            }
                        },
                        "required": ["import_data"],
                        "additionalProperties": False
                    }
                ),
                Tool(
                    name="worldsurveyor_goto_waypoint",
                    description="Navigate camera to a specific waypoint",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "waypoint_id": {
                                "type": "string",
                                "description": "ID of the waypoint to navigate to"
                            }
                        },
                        "required": ["waypoint_id"],
                        "additionalProperties": False
                    }
                ),
                Tool(
                    name="worldsurveyor_health",
                    description="Alias for WorldSurveyor health check",
                    inputSchema={
                        "type": "object",
                        "additionalProperties": False
                    }
                ),
                Tool(
                    name="worldsurveyor_metrics",
                    description="Alias for WorldSurveyor metrics",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "format": {
                                "type": "string",
                                "enum": ["json"],
                                "default": "json"
                            }
                        },
                        "additionalProperties": False
                    }
                ),
                Tool(
                    name="worldsurveyor_metrics_prometheus",
                    description="Get WorldSurveyor metrics in Prometheus format",
                    inputSchema={
                        "type": "object",
                        "additionalProperties": False
                    }
                ),
            ]

    @staticmethod
    def _prepare_params(payload: Dict[str, Any]) -> Dict[str, Any]:
        params: Dict[str, Any] = {}
        for key, value in payload.items():
            if isinstance(value, bool):
                params[key] = 'true' if value else 'false'
            else:
                params[key] = value
        return params

    async def _perform_operation(self, operation: str, method: str, route: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        await self._initialize_client()
        timeout = self._get_timeout()
        try:
            if method.upper() == 'GET':
                response = await self.client.get(f"/{route}", params=self._prepare_params(payload), timeout=timeout)
            elif method.upper() == 'POST':
                response = await self.client.post(f"/{route}", json=payload, timeout=timeout)
            else:
                return error_response('METHOD_NOT_SUPPORTED', f'Unsupported method {method}', details={'operation': operation})
            return normalize_transport_response(operation, response, default_error_code=f'{operation.upper()}_FAILED')
        except asyncio.TimeoutError:
            return error_response('REQUEST_TIMEOUT', 'Request timed out', details={'operation': operation})
        except aiohttp.ClientError as exc:
            return error_response('CONNECTION_ERROR', f'Connection error: {exc}', details={'operation': operation})
        except Exception as exc:
            return error_response(f'{operation.upper()}_FAILED', str(exc), details={'operation': operation})

    @staticmethod
    def _wrap_response(payload: Dict[str, Any]) -> List[TextContent]:
        return [TextContent(type='text', text=json.dumps(payload, indent=2, sort_keys=True))]

    async def _handle_tool_call(self, name: str, arguments: Dict[str, Any]) -> List[TextContent]:
        contract = self._contract_map.get(name)
        if not contract:
            return self._wrap_response(error_response('UNKNOWN_TOOL', f'Unknown tool: {name}'))
        response = await self._perform_operation(contract.operation, contract.http_method, contract.http_route, arguments or {})
        return self._wrap_response(response)

    def setup_handlers(self) -> None:
        @self.server.call_tool()
        async def handle_call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
            return await self._handle_tool_call(name, arguments)

    async def run(self) -> None:
        self.setup_handlers()
        await self._initialize_client()
        async with stdio_server() as (read_stream, write_stream):
            await self.server.run(
                read_stream,
                write_stream,
                InitializationOptions(
                    server_name="worldsurveyor",
                    server_version="0.1.0",
                    capabilities=self.server.get_capabilities(
                        notification_options=NotificationOptions(),
                        experimental_capabilities={},
                    ),
                ),
            )
        await self.client.close()


def main() -> None:
    setup_logging('worldsurveyor')
    base_url = (
        os.getenv("AGENT_WORLDSURVEYOR_BASE_URL")
        or os.getenv("WORLDSURVEYOR_API_URL")
        or "http://localhost:8891"
    )
    server = WorldSurveyorMCP(base_url)
    asyncio.run(server.run())


if __name__ == "__main__":
    main()
