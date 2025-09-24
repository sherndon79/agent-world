#!/usr/bin/env python3
"""
WorldViewer System Tools

Health checks, metrics, and system status tools.
"""

from typing import Any, Dict

from client import get_client
from config import config

# FastMCP instance (will be set by main.py)


async def worldviewer_health_check() -> Dict[str, Any]:
    """Check Agent WorldViewer extension health and API status."""
    client = get_client()

    result = await client.request('health', method="GET")
    return result


async def worldviewer_get_metrics(format: str = "json") -> Dict[str, Any]:
    """Get performance metrics and statistics from WorldViewer extension.

    Args:
        format: Output format (json or prom)
    """
    client = get_client()

    endpoint = 'metrics.prom' if format == 'prom' else 'metrics'
    result = await client.request(endpoint, method="GET")
    return result


async def worldviewer_metrics_prometheus() -> Dict[str, Any]:
    """Get WorldViewer metrics in Prometheus format for monitoring systems."""
    client = get_client()

    result = await client.request('metrics.prom', method="GET")
    return result