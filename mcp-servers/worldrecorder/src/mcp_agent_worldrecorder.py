#!/usr/bin/env python3
"""StdIO MCP server for WorldRecorder using shared transport contracts."""

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
from omni.agent.worldrecorder.errors import error_response
from omni.agent.worldrecorder.transport import ToolContract, TOOL_CONTRACTS, MCP_OPERATIONS

try:
    from agent_world_config import create_worldrecorder_config
    CONFIG = create_worldrecorder_config()
except ImportError:  # pragma: no cover - fallback when extensions not available
    CONFIG = None

LOGGER = logging.getLogger('worldrecorder-stdio')
SERVER = Server('worldrecorder')

# Preserve legacy tool names -----------------------------------------------------
LEGACY_ALIASES = {
    'worldrecorder_health': 'worldrecorder_health_check',
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

# Tool schemas -------------------------------------------------------------------
DEFAULT_SCHEMA: Dict[str, Any] = {"type": "object", "additionalProperties": True}

START_SCHEMA = {
    'type': 'object',
    'properties': {
        'output_path': {'type': 'string', 'description': "Output file path (e.g. '/tmp/recording.mp4')"},
        'fps': {'type': 'number', 'minimum': 1, 'maximum': 240, 'default': 30},
        'duration_sec': {'type': 'number', 'minimum': 0.1, 'maximum': 86400},
        'width': {'type': 'integer', 'minimum': 64, 'maximum': 7680},
        'height': {'type': 'integer', 'minimum': 64, 'maximum': 4320},
        'file_type': {'type': 'string', 'description': 'Optional override (e.g. .mp4)'},
        'session_id': {'type': 'string'},
        'show_progress': {'type': 'boolean', 'default': False},
        'cleanup_frames': {'type': 'boolean', 'default': True},
    },
    'required': ['output_path', 'duration_sec'],
    'additionalProperties': False,
}

CAPTURE_SCHEMA = {
    'type': 'object',
    'properties': {
        'output_path': {'type': 'string', 'description': "Target file (single) or directory (sequence)"},
        'duration_sec': {'type': 'number', 'minimum': 0.1, 'maximum': 86400},
        'interval_sec': {'type': 'number', 'minimum': 0.1, 'maximum': 3600},
        'frame_count': {'type': 'integer', 'minimum': 1, 'maximum': 100000},
        'width': {'type': 'integer', 'minimum': 64, 'maximum': 7680},
        'height': {'type': 'integer', 'minimum': 64, 'maximum': 4320},
        'file_type': {'type': 'string', 'description': 'Optional override (e.g. .png)'},
    },
    'required': ['output_path'],
    'additionalProperties': False,
}

CLEANUP_SCHEMA = {
    'type': 'object',
    'properties': {
        'session_id': {'type': 'string', 'description': 'Session identifier to clean'},
        'output_path': {'type': 'string', 'description': 'Explicit output path to clean'},
    },
    'additionalProperties': False,
}

SCHEMA_OVERRIDES: Dict[str, Dict[str, Any]] = {
    'worldrecorder_start_video': START_SCHEMA,
    'worldrecorder_start_recording': START_SCHEMA,
    'worldrecorder_capture_frame': CAPTURE_SCHEMA,
    'worldrecorder_cleanup_frames': CLEANUP_SCHEMA,
}

TOOL_DEFINITIONS: List[Tool] = [
    Tool(
        name=contract.mcp_tool,
        description=f"Proxy for WorldRecorder operation '{contract.operation}'",
        inputSchema=SCHEMA_OVERRIDES.get(contract.mcp_tool, DEFAULT_SCHEMA),
    )
    for contract in ALL_CONTRACTS
]


class WorldRecorderClient:
    """HTTP client wrapper that mirrors the stdio MCP server."""

    def __init__(self) -> None:
        base_url = (
            os.getenv('AGENT_WORLDRECORDER_BASE_URL')
            or os.getenv('WORLDRECORDER_API_URL')
            or (CONFIG.get_server_url() if CONFIG else 'http://localhost:8892')
        )
        self.base_url = base_url.rstrip('/')
        self.client = MCPBaseClient('WORLDRECORDER', self.base_url)

    async def initialize(self) -> None:
        if not self.client._initialized:
            await self.client.initialize()

    async def close(self) -> None:
        await self.client.close()

    def _timeout(self, tool_name: str) -> float:
        if CONFIG:
            if tool_name in {'worldrecorder_start_video', 'worldrecorder_start_recording'}:
                return CONFIG.get('video_start_timeout', 60.0)
            if tool_name in {'worldrecorder_cancel_video', 'worldrecorder_cancel_recording'}:
                return CONFIG.get('video_cancel_timeout', 60.0)
            if tool_name == 'worldrecorder_capture_frame':
                return CONFIG.get('frame_capture_timeout', 45.0)
            return CONFIG.get('standard_timeout', 15.0)

        defaults = {
            'worldrecorder_start_video': 60.0,
            'worldrecorder_start_recording': 60.0,
            'worldrecorder_cancel_video': 60.0,
            'worldrecorder_cancel_recording': 60.0,
            'worldrecorder_capture_frame': 45.0,
        }
        return defaults.get(tool_name, 15.0)

    @staticmethod
    def _prepare_params(payload: Dict[str, Any]) -> Dict[str, Any]:
        params: Dict[str, Any] = {}
        for key, value in payload.items():
            if isinstance(value, bool):
                params[key] = 'true' if value else 'false'
            else:
                params[key] = value
        return params

    async def perform(self, tool_name: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        contract = CONTRACT_MAP.get(tool_name)
        if not contract:
            return error_response('UNKNOWN_TOOL', f'No contract for tool {tool_name}')

        await self.initialize()
        timeout = self._timeout(tool_name)
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


CLIENT = WorldRecorderClient()


@SERVER.list_tools()
async def list_tools() -> List[Tool]:
    return TOOL_DEFINITIONS


@SERVER.call_tool()
async def call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
    payload = arguments or {}
    result = await CLIENT.perform(name, payload)
    return [TextContent(type='text', text=json.dumps(result, indent=2, sort_keys=True))]


async def main() -> None:
    setup_logging('worldrecorder-stdio')
    await CLIENT.initialize()
    try:
        async with stdio_server() as (read_stream, write_stream):
            await SERVER.run(
                read_stream,
                write_stream,
                InitializationOptions(
                    server_name='worldrecorder',
                    server_version='1.0.0',
                    capabilities=SERVER.get_capabilities(
                        notification_options=NotificationOptions(),
                        experimental_capabilities={},
                    ),
                ),
            )
    finally:
        await CLIENT.close()


if __name__ == '__main__':
    asyncio.run(main())
