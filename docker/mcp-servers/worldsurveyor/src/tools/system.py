#!/usr/bin/env python3
"""
WorldSurveyor System Tools

Health checks, metrics, and system status tools.
"""

from typing import Any, Dict
from mcp.server.fastmcp import FastMCP

from client import get_client
from config import config

# FastMCP instance (will be set by main.py)
mcp: FastMCP = None


async def worldsurveyor_health_check() -> Dict[str, Any]:
    """Check WorldSurveyor extension health and API status."""
    client = get_client()

    result = await client.request('health', method="GET")
    return result


async def worldsurveyor_get_metrics(format: str = "json") -> Dict[str, Any]:
    """Get WorldSurveyor metrics in JSON or Prometheus format.

    Args:
        format: 'json' or 'prom'
    """
    client = get_client()

    endpoint = 'metrics.prom' if format == 'prom' else 'metrics'
    result = await client.request(endpoint, method="GET")
    return result


async def worldsurveyor_metrics_prometheus() -> Dict[str, Any]:
    """Get WorldSurveyor metrics in Prometheus format for monitoring systems."""
    client = get_client()

    result = await client.request('metrics.prom', method="GET")
    return result


async def worldsurveyor_debug_status() -> Dict[str, Any]:
    """Get debug status and marker information."""
    client = get_client()

    result = await client.request('markers/debug', method="GET")
    return result