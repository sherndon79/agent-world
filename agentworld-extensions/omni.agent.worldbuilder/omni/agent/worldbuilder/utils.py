"""Shared helper utilities for the Agent WorldBuilder extension."""

from __future__ import annotations

import re
import time
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

VectorProvider = Callable[[], Any]


def sanitize_usd_name(name: str) -> str:
    """Sanitise a string so it is safe for use in USD prim paths."""
    sanitized = re.sub(r"[^a-zA-Z0-9_\-]", "_", name)
    if sanitized and sanitized[0].isdigit():
        sanitized = f"_{sanitized}"
    return sanitized


def ensure_vector3(value: Any) -> List[float]:
    """Coerce incoming data into a 3-element float vector."""
    if isinstance(value, tuple):
        value = list(value)

    if isinstance(value, list):
        if len(value) == 1 and isinstance(value[0], str):
            value = value[0]
        else:
            coerced = [float(part) for part in value]
            if len(coerced) != 3:
                raise ValueError("Vector must contain exactly three values")
            return coerced

    if isinstance(value, str):
        parts = [part.strip() for part in value.split(",") if part.strip()]
        if len(parts) != 3:
            raise ValueError("Vector must contain exactly three values")
        return [float(part) for part in parts]

    raise ValueError("Vector must contain exactly three values")


def count_world_children(stage_getter: VectorProvider, world_path: str = "/World") -> int:
    """Count direct children beneath the provided world path."""
    try:
        stage = stage_getter()
        if not stage:
            return 0
        world_prim = stage.GetPrimAtPath(world_path)
        if not world_prim:
            return 0
        return len(list(world_prim.GetAllChildren()))
    except Exception:
        return 0


def collect_metrics(
    stats: Dict[str, Any],
    *,
    scene_counter: Callable[[], int],
    now: Optional[Callable[[], float]] = None,
) -> Dict[str, Any]:
    """Build a metrics snapshot using shared formatting rules."""
    now_fn = now or time.time
    scene_object_count = scene_counter()

    uptime = 0.0
    start_time = stats.get("start_time")
    if start_time:
        try:
            if isinstance(start_time, str):
                start_timestamp = datetime.fromisoformat(start_time.replace("Z", "+00:00")).timestamp()
            else:
                start_timestamp = float(start_time)
            uptime = max(0.0, now_fn() - start_timestamp)
        except Exception:
            uptime = 0.0

    return {
        "requests_received": stats.get("requests_received", 0),
        "errors": stats.get("failed_requests", 0),
        "elements_created": stats.get("elements_created", 0),
        "batches_created": stats.get("batches_created", 0),
        "assets_placed": stats.get("assets_placed", 0),
        "objects_queried": stats.get("objects_queried", 0),
        "transformations_applied": stats.get("transformations_applied", 0),
        "uptime_seconds": uptime,
        "scene_object_count": scene_object_count,
        "server_running": bool(stats.get("server_running", False)),
        "start_time": start_time,
    }


__all__ = [
    "sanitize_usd_name",
    "ensure_vector3",
    "count_world_children",
    "collect_metrics",
]
