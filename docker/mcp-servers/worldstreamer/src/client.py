#!/usr/bin/env python3
"""
WorldStreamer HTTP Client

Handles HTTP communication with the Isaac Sim WorldStreamer Extension.
Supports auto-detection between RTMP and SRT services.
"""

import asyncio
import logging
import os
import sys
from typing import Any, Dict, List
import aiohttp
import httpx

# Add shared modules to path
shared_path = os.path.join(os.path.dirname(__file__), '..', '..', 'shared')
if shared_path not in sys.path:
    sys.path.insert(0, shared_path)

from mcp_base_client import MCPBaseClient

# Shared transport helpers from agentworld-extensions
try:
    from omni.agent.worldstreamer.errors import error_response
    from omni.agent.worldstreamer.transport import normalize_transport_response
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

logger = logging.getLogger("worldstreamer.client")

# Default service URLs
DEFAULT_RTMP_URL = "http://localhost:8906"  # worldstreamer.rtmp.server_port
DEFAULT_SRT_URL = "http://localhost:8908"   # worldstreamer.srt.server_port


class WorldStreamerClient:
    """HTTP client for WorldStreamer extension communication with auto-detection."""

    def __init__(self, base_url: str = None):
        from config import config

        self.rtmp_url = config.rtmp_base_url.rstrip('/')
        self.srt_url = config.srt_base_url.rstrip('/')
        self.base_url = None  # Will be set by auto-detection
        self.active_protocol = None  # 'rtmp' or 'srt' or 'manual'
        self.client: MCPBaseClient = None
        self._initialized = False

        # Override URLs if base_url provided or from config
        manual_override = base_url or config.worldstreamer_base_url
        if manual_override:
            self.base_url = manual_override.rstrip('/')
            self.active_protocol = "manual"
            logger.info(f"Manual mode: Using provided base URL: {self.base_url}")

        logger.info(f"WorldStreamer client initialized - RTMP: {self.rtmp_url}, SRT: {self.srt_url}")

    async def initialize(self):
        """Initialize the HTTP client."""
        if not self._initialized:
            await self._detect_active_service()
            if not self.client:
                self.client = MCPBaseClient('WORLDSTREAMER', self.base_url)
                await self.client.initialize()
            self._initialized = True

    async def close(self):
        """Close the HTTP client."""
        if self.client:
            await self.client.close()

    async def _detect_active_service(self) -> str:
        """
        Auto-detect which WorldStreamer service is running using auth-aware client.

        Returns:
            Base URL of the active service

        Raises:
            Exception if no service is available
        """
        if self.base_url and self.active_protocol == "manual":
            return self.base_url

        # Test both services using auth-aware clients
        services = [
            (self.rtmp_url, "RTMP"),
            (self.srt_url, "SRT")
        ]

        for url, protocol in services:
            temp_client = None
            try:
                # Create temporary auth-aware client for health check
                temp_client = MCPBaseClient('WORLDSTREAMER', url)
                await temp_client.initialize()

                # Perform authenticated health check
                response = await temp_client.get("health")

                if response.get('success'):
                    self.base_url = url
                    self.active_protocol = protocol.lower()
                    logger.info(f"Auto-detected active service: {protocol} at {url}")
                    return url
                else:
                    logger.debug(f"{protocol} service at {url} returned error: {response.get('error', 'Unknown error')}")

            except Exception as e:
                logger.debug(f"{protocol} service at {url} not available: {e}")
            finally:
                # Clean up temporary client
                if temp_client:
                    try:
                        await temp_client.close()
                    except Exception:
                        pass  # Ignore cleanup errors

        # No service available
        raise Exception(f"No WorldStreamer service available at {self.rtmp_url} or {self.srt_url}")

    async def request(self, endpoint: str, method: str = "POST", payload: Dict[str, Any] = None, params: Dict[str, Any] = None, timeout: float = 30.0) -> Dict[str, Any]:
        """Make HTTP request to WorldStreamer extension."""
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
_client: WorldStreamerClient = None


def get_client() -> WorldStreamerClient:
    """Get the global WorldStreamer client instance."""
    global _client
    if _client is None:
        _client = WorldStreamerClient()
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