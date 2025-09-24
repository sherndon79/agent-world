#!/usr/bin/env python3
"""
WorldStreamer Streaming Tools

Streaming control and management tools.
"""

from typing import Any, Dict, Optional
from mcp.server.fastmcp import FastMCP

from client import get_client
from config import config

# FastMCP instance (will be set by main.py)
mcp: FastMCP = None


async def worldstreamer_start_streaming(server_ip: Optional[str] = None) -> Dict[str, Any]:
    """Start Isaac Sim streaming session (auto-detects RTMP/SRT).

    Args:
        server_ip: Optional server IP override for streaming URLs
    """
    client = get_client()

    payload = {}
    if server_ip:
        payload['server_ip'] = server_ip

    timeout = config.get_timeout('start_streaming')
    result = await client.request('streaming/start', payload=payload, timeout=timeout)
    return result


async def worldstreamer_stop_streaming() -> Dict[str, Any]:
    """Stop active Isaac Sim streaming session (auto-detects RTMP/SRT)."""
    client = get_client()

    timeout = config.get_timeout('stop_streaming')
    result = await client.request('streaming/stop', timeout=timeout)
    return result


async def worldstreamer_get_status() -> Dict[str, Any]:
    """Get current streaming status and information (auto-detects RTMP/SRT)."""
    client = get_client()

    timeout = config.get_timeout('get_status')
    result = await client.request('streaming/status', method="GET", timeout=timeout)
    return result


async def worldstreamer_get_streaming_urls(server_ip: Optional[str] = None) -> Dict[str, Any]:
    """Get streaming client URLs for connection (auto-detects RTMP/SRT).

    Args:
        server_ip: Optional server IP override for streaming URLs
    """
    client = get_client()

    params = {}
    if server_ip:
        params['server_ip'] = server_ip

    timeout = config.get_timeout('get_streaming_urls')
    result = await client.request('streaming/urls', method="GET", params=params, timeout=timeout)
    return result


async def worldstreamer_validate_environment() -> Dict[str, Any]:
    """Validate Isaac Sim environment for streaming (auto-detects RTMP/SRT)."""
    client = get_client()

    timeout = config.get_timeout('validate_environment')
    result = await client.request('streaming/environment/validate', method="GET", timeout=timeout)
    return result