#!/usr/bin/env python3
"""
WorldBuilder System Tools

Health checks, metrics, and system status tools.
"""

from typing import Any, Dict
from mcp.server.fastmcp import FastMCP

from client import get_client
from config import config

# FastMCP instance (will be set by main.py)
mcp: FastMCP = None



async def worldbuilder_health_check() -> Dict[str, Any]:
    """Check Isaac Sim WorldBuilder Extension health and API status."""
    client = get_client()

    timeout = config.get_timeout('health_check')
    result = await client.request('health', method="GET", timeout=timeout)
    return result



async def worldbuilder_request_status() -> Dict[str, Any]:
    """Get status of ongoing operations and request queue."""
    client = get_client()

    result = await client.request('request_status', method="GET")
    return result



async def worldbuilder_get_metrics(format_type: str = "json") -> Dict[str, Any]:
    """Get performance metrics and statistics from WorldBuilder extension.

    Args:
        format_type: Output format: json for structured data, prom for Prometheus format
    """
    client = get_client()

    endpoint = 'metrics.prom' if format_type == 'prom' else 'metrics'
    result = await client.request(endpoint, method="GET")
    return result



async def worldbuilder_metrics_prometheus() -> Dict[str, Any]:
    """Get WorldBuilder metrics in Prometheus format for monitoring systems."""
    client = get_client()

    result = await client.request('metrics.prom', method="GET")
    return result