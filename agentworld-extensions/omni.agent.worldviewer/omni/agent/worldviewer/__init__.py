"""
Agent WorldViewer Extension for Isaac Sim

Thread-safe camera control and viewport management extension with HTTP API for AI-powered
camera positioning. Features queue-based architecture that eliminates thread safety issues
and provides complete camera lifecycle management through RESTful endpoints.
"""

import sys
import json
from pathlib import Path

# Get version from centralized version config
try:
    # Find the agentworld-extensions directory
    current = Path(__file__).resolve()
    for _ in range(10):  # Search up the directory tree
        if current.name == 'agentworld-extensions':
            version_file = current / 'agent-world-versions.json'
            if version_file.exists():
                with open(version_file) as f:
                    version_data = json.load(f)
                __version__ = version_data['extensions']['worldviewer']['version']
                break
            current = current.parent
        current = current.parent
    else:
        __version__ = "0.1.0"  # Fallback
except Exception:
    __version__ = "0.1.0"  # Fallback

__author__ = "agenTW∞rld Team"

# Import and expose the extension class for Isaac Sim
from .extension import AgentWorldViewerExtension