"""
Agent WorldRecorder Extension

HTTP API for Kit-native video recording and screenshot capture via omni.kit.capture.viewport.
Replaces the original PyAV-based worldrecorder with a more reliable Kit-native implementation.
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
                __version__ = version_data['extensions']['worldrecorder']['version']
                break
            current = current.parent
        current = current.parent
    else:
        __version__ = "0.1.0"  # Fallback
except Exception:
    __version__ = "0.1.0"  # Fallback

__author__ = "agenTW∞rld Team"

# Expose the extension class so Kit can discover it
from .extension import AgentWorldRecorderExtension
