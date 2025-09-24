"""
Agent WorldBuilder Extension for Isaac Sim

Thread-safe USD scene management extension with HTTP API for AI-powered worldbuilding.
Features revolutionary queue-based architecture that eliminates all thread safety issues
and provides complete scene lifecycle management through RESTful endpoints.
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

    __version__ = get_version('worldbuilder')
except Exception:
    __version__ = "0.1.0"  # Fallback when core package unavailable

__author__ = "agenTW∞rld Team"

# Import and expose the extension class for Isaac Sim when available
try:
    from .extension import AgentWorldBuilderExtension
except (ModuleNotFoundError, ImportError):  # pragma: no cover - allows headless test imports
    AgentWorldBuilderExtension = None
