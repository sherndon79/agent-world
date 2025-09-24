"""
Agent WorldSurveyor Extension

Thread-safe waypoint management and spatial surveying extension with HTTP API 
for AI-powered scene planning in Isaac Sim.
"""

import sys
from pathlib import Path


def _ensure_core_path() -> bool:
    current = Path(__file__).resolve()
    for candidate in (current, *current.parents):
        core_path = candidate / 'agentworld-core' / 'src'
        if core_path.exists():
            core_str = str(core_path)
            if core_str not in sys.path:
                sys.path.insert(0, core_str)
            return True
    return False


_ensure_core_path()


# Get version from centralized version config
try:
    from agentworld_core.versions import get_version

    __version__ = get_version('worldsurveyor')
except Exception:
    __version__ = "0.1.0"  # Fallback

__author__ = "agenTW∞rld Team"

from .extension import AgentWorldSurveyorExtension

__all__ = ["AgentWorldSurveyorExtension"]
