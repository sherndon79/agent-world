#!/usr/bin/env python3
"""
WorldRecorder System Tools

Health checks, metrics, and system status tools.
"""

from typing import Any, Dict

from client import get_client
from config import config

# FastMCP instance (will be set by main.py)


async def worldrecorder_health_check() -> Dict[str, Any]:
    """Check WorldRecorder extension health and connectivity"""
    client = get_client()

    result = await client.request('health', method="GET")
    return result


async def worldrecorder_get_metrics() -> Dict[str, Any]:
    """Get WorldRecorder extension performance metrics and statistics"""
    client = get_client()

    result = await client.request('metrics', method="GET")
    return result


async def worldrecorder_metrics_prometheus() -> Dict[str, Any]:
    """Get WorldRecorder metrics in Prometheus format for monitoring systems"""
    client = get_client()

    result = await client.request('metrics.prom', method="GET")
    return result