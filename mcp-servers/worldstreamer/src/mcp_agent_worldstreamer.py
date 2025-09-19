#!/usr/bin/env python3
"""StdIO MCP server for WorldStreamer using shared transport contracts."""

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
from omni.agent.worldstreamer.rtmp.transport import ToolContract, TOOL_CONTRACTS, MCP_OPERATIONS
from omni.agent.worldstreamer.rtmp.errors import error_response, WorldStreamerError

try:
    from agent_world_config import create_worldstreamer_config
    CONFIG = create_worldstreamer_config()
except ImportError:  # pragma: no cover - fallback when extensions not available
    CONFIG = None

LOGGER = logging.getLogger('worldstreamer-stdio')
SERVER = Server('worldstreamer')

# Legacy tool name for backward compatibility
LEGACY_ALIASES = {
    'worldstreamer_health': 'worldstreamer_health_check',
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
        'server_ip': {
            'type': 'string',
            'description': 'Optional server IP override for generated streaming URLs'
        }
    },
    'additionalProperties': False,
}

SCHEMA_OVERRIDES: Dict[str, Dict[str, Any]] = {
    'worldstreamer_start_streaming': START_SCHEMA,
    'worldstreamer_get_streaming_urls': START_SCHEMA,
}

TOOL_DEFINITIONS: List[Tool] = [
    Tool(
        name=contract.mcp_tool,
        description=f"Proxy for WorldStreamer operation '{contract.operation}'",
        inputSchema=SCHEMA_OVERRIDES.get(contract.mcp_tool, DEFAULT_SCHEMA),
    )
    for contract in ALL_CONTRACTS
]


class WorldStreamerClient:
    """HTTP client wrapper that auto-detects RTMP vs SRT endpoints."""

    def __init__(self) -> None:
        self.rtmp_url = os.getenv('WORLDSTREAMER_RTMP_URL', 'http://localhost:8906').rstrip('/')
        self.srt_url = os.getenv('WORLDSTREAMER_SRT_URL', 'http://localhost:8908').rstrip('/')
        manual_url = os.getenv('WORLDSTREAMER_BASE_URL')

        self.base_url = manual_url.rstrip('/') if manual_url else None
        self.active_protocol = 'manual' if manual_url else None
        self.client: MCPBaseClient | None = None

    async def perform(self, tool_name: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        contract = CONTRACT_MAP.get(tool_name)
        if not contract:
            return error_response('UNKNOWN_TOOL', f'No contract for tool {tool_name}')

        await self._ensure_client()
        timeout = self._timeout(tool_name)
        try:
            if contract.http_method.upper() == 'GET':
                response = await self.client.get(  # type: ignore[union-attr]
                    f"/{contract.http_route}",
                    params=self._prepare_params(payload),
                    timeout=timeout,
                )
            else:
                response = await self.client.post(  # type: ignore[union-attr]
                    f"/{contract.http_route}",
                    json=payload,
                    timeout=timeout,
                )
            normalized = normalize_transport_response(contract.operation, response, default_error_code=f'{contract.operation.upper()}_FAILED')
            if self.active_protocol:
                normalized.setdefault('details', {})['active_protocol'] = self.active_protocol
            if self.base_url:
                normalized.setdefault('details', {})['base_url'] = self.base_url
            return normalized
        except asyncio.TimeoutError:
            return error_response('REQUEST_TIMEOUT', 'Request timed out', details={'operation': contract.operation})
        except aiohttp.ClientError as exc:
            return error_response('CONNECTION_ERROR', f'Connection error: {exc}', details={'operation': contract.operation})
        except Exception as exc:  # pragma: no cover - unexpected failure
            LOGGER.exception('tool_execution_failed', extra={'tool': tool_name, 'error': str(exc)})
            return error_response(f'{contract.operation.upper()}_FAILED', str(exc))

    async def _ensure_client(self) -> None:
        if not self.base_url or self.active_protocol != 'manual':
            await self._detect_active_service()
        if self.client is None or self.client.base_url != self.base_url:
            self.client = MCPBaseClient('WORLDSTREAMER', self.base_url)
            await self.client.initialize()

    async def _detect_active_service(self) -> None:
        if self.active_protocol == 'manual' and self.base_url:
            return

        for url, protocol in ((self.rtmp_url, 'rtmp'), (self.srt_url, 'srt')):
            try:
                async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=5)) as session:
                    async with session.get(f"{url}/health") as response:
                        if response.status == 200:
                            payload = await response.json()
                            if payload.get('success'):
                                self.base_url = url
                                self.active_protocol = protocol
                                LOGGER.info('Detected %s WorldStreamer at %s', protocol.upper(), url)
                                return
            except Exception:  # pragma: no cover - detection best effort
                continue

        raise WorldStreamerError('No WorldStreamer service available', details={'rtmp_url': self.rtmp_url, 'srt_url': self.srt_url})

    def _timeout(self, tool_name: str) -> float:
        if CONFIG:
            mapping = {
                'worldstreamer_start_streaming': CONFIG.get('standard_timeout', 30.0),
                'worldstreamer_stop_streaming': CONFIG.get('standard_timeout', 30.0),
                'worldstreamer_get_status': CONFIG.get('standard_timeout', 30.0),
                'worldstreamer_get_streaming_urls': CONFIG.get('standard_timeout', 30.0),
                'worldstreamer_validate_environment': CONFIG.get('standard_timeout', 30.0),
                'worldstreamer_health_check': CONFIG.get('simple_timeout', 5.0),
            }
            return mapping.get(tool_name, CONFIG.get('standard_timeout', 30.0))

        defaults = {
            'worldstreamer_health_check': 5.0,
        }
        return defaults.get(tool_name, 30.0)

    @staticmethod
    def _prepare_params(payload: Dict[str, Any]) -> Dict[str, Any]:
        params: Dict[str, Any] = {}
        for key, value in payload.items():
            if isinstance(value, bool):
                params[key] = 'true' if value else 'false'
            else:
                params[key] = value
        return params


CLIENT = WorldStreamerClient()


@SERVER.list_tools()
async def list_tools() -> List[Tool]:
    return TOOL_DEFINITIONS


@SERVER.call_tool()
async def call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
    payload = arguments or {}
    result = await CLIENT.perform(name, payload)
    return [TextContent(type='text', text=json.dumps(result, indent=2, sort_keys=True))]


async def main() -> None:
    setup_logging('worldstreamer-stdio')
    try:
        async with stdio_server() as (read_stream, write_stream):
            await SERVER.run(
                read_stream,
                write_stream,
                InitializationOptions(
                    server_name='worldstreamer',
                    server_version='1.0.0',
                    capabilities=SERVER.get_capabilities(
                        notification_options=NotificationOptions(),
                        experimental_capabilities={},
                    ),
                ),
            )
    finally:
        if CLIENT.client:
            await CLIENT.client.close()


if __name__ == '__main__':
    asyncio.run(main())
