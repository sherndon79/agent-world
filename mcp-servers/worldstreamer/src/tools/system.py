#!/usr/bin/env python3
"""
WorldStreamer System Tools

Health checks, metrics, and system status tools.
"""

from typing import Any, Dict

from client import get_client
from config import config


async def worldstreamer_health_check() -> Dict[str, Any]:
    """Check WorldStreamer extension health and connectivity (auto-detects RTMP/SRT)."""
    client = get_client()

    timeout = config.get_timeout('health_check')
    result = await client.request('health', method="GET", timeout=timeout)
    return result


async def worldstreamer_get_metrics(format_type: str = "json") -> Dict[str, Any]:
    """Get performance metrics and statistics from WorldStreamer extension.

    Args:
        format_type: Output format: json for structured data, prom for Prometheus format
    """
    client = get_client()

    endpoint = 'metrics.prom' if format_type == 'prom' else 'metrics'
    result = await client.request(endpoint, method="GET")
    return result


async def worldstreamer_metrics_prometheus() -> Dict[str, Any]:
    """Get WorldStreamer metrics in Prometheus format for monitoring systems."""
    client = get_client()

    result = await client.request('metrics.prom', method="GET")
    return result