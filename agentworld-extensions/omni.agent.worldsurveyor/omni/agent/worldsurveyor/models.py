"""
Data models for WorldSurveyor extension.
"""

from dataclasses import dataclass
from typing import Any, Dict, Tuple


@dataclass
class Waypoint:
    """Simple waypoint data structure."""
    id: str
    name: str
    position: Tuple[float, float, float]
    target: Tuple[float, float, float]
    waypoint_type: str
    timestamp: str
    session_id: str
    metadata: Dict[str, Any]