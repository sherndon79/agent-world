#!/usr/bin/env python3
"""StdIO MCP server for WorldViewer using shared transport contracts."""

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

# Shared helpers ----------------------------------------------------------------
shared_path = os.path.join(os.path.dirname(__file__), '..', '..', 'shared')
if shared_path not in sys.path:
    sys.path.insert(0, shared_path)

from logging_setup import setup_logging
from mcp_base_client import MCPBaseClient

# Extension helpers --------------------------------------------------------------
extensions_path = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'agentworld-extensions')
if os.path.exists(extensions_path) and extensions_path not in sys.path:
    sys.path.insert(0, extensions_path)

from agent_world_transport import normalize_transport_response
from omni.agent.worldviewer.errors import error_response
from omni.agent.worldviewer.transport import ToolContract, TOOL_CONTRACTS, MCP_OPERATIONS

try:
    from agent_world_config import create_worldviewer_config
    CONFIG = create_worldviewer_config()
except ImportError:  # pragma: no cover - fallback when extensions not available
    CONFIG = None

LOGGER = logging.getLogger('worldviewer-stdio')
SERVER = Server('worldviewer')

# Extend contract list with legacy aliases --------------------------------------
LEGACY_ALIASES = {
    'worldviewer_health': 'worldviewer_extension_health',
    'worldviewer_metrics': 'worldviewer_get_metrics',
}

ALIAS_CONTRACTS: List[ToolContract] = [
    ToolContract(
        operation=MCP_OPERATIONS[target].operation,
        http_route=MCP_OPERATIONS[target].http_route,
        http_method=MCP_OPERATIONS[target].http_method,
        mcp_tool=alias,
    )
    for alias, target in LEGACY_ALIASES.items()
]

ALL_CONTRACTS: List[ToolContract] = TOOL_CONTRACTS + ALIAS_CONTRACTS
CONTRACT_MAP: Dict[str, ToolContract] = {contract.mcp_tool: contract for contract in ALL_CONTRACTS}

# Minimal schemas for tools (clients receive structured metadata) ---------------
DEFAULT_SCHEMA: Dict[str, Any] = {"type": "object", "additionalProperties": True}
SCHEMA_OVERRIDES: Dict[str, Dict[str, Any]] = {
    'worldviewer_set_camera_position': {
        'type': 'object',
        'properties': {
            'position': {
                'type': 'array',
                'items': {'type': 'number'},
                'minItems': 3,
                'maxItems': 3,
                'description': 'Camera position [x, y, z]'
            },
            'target': {
                'type': 'array',
                'items': {'type': 'number'},
                'minItems': 3,
                'maxItems': 3,
                'description': 'Optional look-at target [x, y, z]'
            },
            'up_vector': {
                'type': 'array',
                'items': {'type': 'number'},
                'minItems': 3,
                'maxItems': 3,
                'description': 'Optional up vector [x, y, z]'
            },
        },
        'required': ['position'],
        'additionalProperties': False,
    },
    'worldviewer_frame_object': {
        'type': 'object',
        'properties': {
            'object_path': {'type': 'string', 'description': "USD path (e.g. '/World/my_cube')"},
            'distance': {'type': 'number', 'description': 'Optional distance from object'},
        },
        'required': ['object_path'],
        'additionalProperties': False,
    },
    'worldviewer_get_camera_status': {'type': 'object', 'additionalProperties': False},
}

TOOL_DEFINITIONS: List[Tool] = [
    Tool(
        name=contract.mcp_tool,
        description=f"Proxy for WorldViewer operation '{contract.operation}'",
        inputSchema=SCHEMA_OVERRIDES.get(contract.mcp_tool, DEFAULT_SCHEMA),
    )
    for contract in ALL_CONTRACTS
]


class WorldViewerClient:
    """HTTP client wrapper that mirrors the stdio MCP server."""

    def __init__(self) -> None:
        base_url = (
            os.getenv('AGENT_WORLDVIEWER_BASE_URL')
            or os.getenv('WORLDVIEWER_API_URL')
            or (CONFIG.get_server_url() if CONFIG else 'http://localhost:8900')
        )
        self.base_url = base_url.rstrip('/')
        self.client = MCPBaseClient('WORLDVIEWER', self.base_url)

    async def initialize(self) -> None:
        if not self.client._initialized:
            await self.client.initialize()

    async def close(self) -> None:
        await self.client.close()

    def _timeout(self, kind: str = 'standard') -> float:
        if CONFIG:
            return CONFIG.get(f'{kind}_timeout', 10.0)
        defaults = {'simple': 5.0, 'standard': 10.0, 'complex': 20.0}
        return defaults.get(kind, defaults['standard'])

    @staticmethod
    def _prepare_params(payload: Dict[str, Any]) -> Dict[str, Any]:
        params: Dict[str, Any] = {}
        for key, value in payload.items():
            if isinstance(value, bool):
                params[key] = 'true' if value else 'false'
            else:
                params[key] = value
        return params

    async def perform(self, tool_name: str, payload: Dict[str, Any], *, timeout_kind: str = 'standard') -> Dict[str, Any]:
        contract = CONTRACT_MAP.get(tool_name)
        if not contract:
            return error_response('UNKNOWN_TOOL', f'No contract for tool {tool_name}')

        await self.initialize()
        timeout = self._timeout(timeout_kind)
        try:
            if contract.http_method.upper() == 'GET':
                response = await self.client.get(f"/{contract.http_route}", params=self._prepare_params(payload), timeout=timeout)
            else:
                response = await self.client.post(f"/{contract.http_route}", json=payload, timeout=timeout)
            return normalize_transport_response(contract.operation, response, default_error_code=f'{contract.operation.upper()}_FAILED')
        except asyncio.TimeoutError:
            return error_response('REQUEST_TIMEOUT', 'Request timed out', details={'operation': contract.operation})
        except aiohttp.ClientError as exc:
            return error_response('CONNECTION_ERROR', f'Connection error: {exc}', details={'operation': contract.operation})
        except Exception as exc:  # pragma: no cover - unexpected failure
            LOGGER.exception('tool_execution_failed', extra={'tool': tool_name, 'error': str(exc)})
            return error_response(f'{contract.operation.upper()}_FAILED', str(exc))


CLIENT = WorldViewerClient()


@SERVER.list_tools()
async def list_tools() -> List[Tool]:
    return TOOL_DEFINITIONS


@SERVER.call_tool()
async def call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
    payload = arguments or {}
    # Determine timeout kind based on operation type
    timeout_kind = 'complex' if name in {
        'worldviewer_smooth_move',
        'worldviewer_arc_shot',
        'worldviewer_orbit_shot',
    } else 'standard'
    result = await CLIENT.perform(name, payload, timeout_kind=timeout_kind)
    return [TextContent(type='text', text=json.dumps(result, indent=2, sort_keys=True))]


async def main() -> None:
    setup_logging('worldviewer-stdio')
    await CLIENT.initialize()
    try:
        async with stdio_server() as (read_stream, write_stream):
            await SERVER.run(
                read_stream,
                write_stream,
                InitializationOptions(
                    server_name='worldviewer',
                    server_version='0.1.0',
                    capabilities=SERVER.get_capabilities(notification_options=NotificationOptions(), experimental_capabilities={}),
                ),
            )
    finally:
        await CLIENT.close()


if __name__ == '__main__':
    asyncio.run(main())
