#!/usr/bin/env python3
"""
WorldViewer HTTP Client

Handles HTTP communication with the Isaac Sim WorldViewer Extension.
"""

import asyncio
import logging
import os
import sys
from typing import Any, Dict, List
import aiohttp

# Add shared modules to path
shared_path = os.path.join(os.path.dirname(__file__), '..', '..', 'shared')
if shared_path not in sys.path:
    sys.path.insert(0, shared_path)

from mcp_base_client import MCPBaseClient

# Shared transport helpers from agentworld-extensions
try:
    from omni.agent.worldbuilder.errors import error_response
    from omni.agent.worldbuilder.transport import normalize_transport_response
except ImportError:  # pragma: no cover - fallback when extensions not available
    def error_response(code: str, message: str, *, details=None):
        payload = {"success": False, "error_code": code, "error": message}
        if details:
            payload["details"] = details
        return payload

    def normalize_transport_response(operation: str, response, *, default_error_code: str):
        if isinstance(response, dict):
            response.setdefault("success", True)
            if response["success"] is False:
                response.setdefault("error_code", default_error_code)
                response.setdefault("error", "An unknown error occurred")
            return response
        return error_response(
            "INVALID_RESPONSE",
            "Service returned unexpected response type",
            details={"operation": operation, "type": type(response).__name__},
        )

logger = logging.getLogger("worldviewer.client")


class WorldViewerClient:
    """HTTP client for WorldViewer extension communication."""

    def __init__(self, base_url: str = None):
        self.base_url = base_url or os.getenv("AGENT_WORLDVIEWER_BASE_URL", "http://localhost:8900")
        self.base_url = self.base_url.rstrip('/')
        self.client = MCPBaseClient('WORLDVIEWER', self.base_url)
        self._initialized = False

    async def initialize(self):
        """Initialize the HTTP client."""
        if not self._initialized:
            await self.client.initialize()
            self._initialized = True

    async def close(self):
        """Close the HTTP client."""
        if self.client:
            await self.client.close()

    async def request(self, endpoint: str, method: str = "POST", payload: Dict[str, Any] = None, params: Dict[str, Any] = None, timeout: float = 30.0) -> Dict[str, Any]:
        """Make HTTP request to WorldBuilder extension."""
        await self.initialize()

        try:
            if method.upper() == "GET":
                # For GET requests, use params for query parameters
                response = await self.client.get(f"/{endpoint}", params=params, timeout=timeout)
            else:
                response = await self.client.post(f"/{endpoint}", json=payload or {}, timeout=timeout)

            return normalize_transport_response(endpoint, response, default_error_code=f'{endpoint.upper()}_FAILED')

        except asyncio.TimeoutError:
            return error_response('REQUEST_TIMEOUT', 'Request timed out', details={'endpoint': endpoint})
        except aiohttp.ClientError as exc:
            return error_response('CONNECTION_ERROR', f'Connection error: {exc}', details={'endpoint': endpoint})
        except Exception as exc:
            logger.exception('request_failed', extra={'endpoint': endpoint, 'error': str(exc)})
            return error_response(f'{endpoint.upper()}_FAILED', str(exc))


# Global client instance
_client: WorldViewerClient = None


def get_client() -> WorldViewerClient:
    """Get the global WorldViewer client instance."""
    global _client
    if _client is None:
        _client = WorldViewerClient()
    return _client


async def initialize_client():
    """Initialize the global client."""
    client = get_client()
    await client.initialize()


async def close_client():
    """Close the global client."""
    global _client
    if _client:
        await _client.close()
        _client = None