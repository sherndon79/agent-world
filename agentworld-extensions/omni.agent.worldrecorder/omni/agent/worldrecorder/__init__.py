"""
Agent WorldRecorder Extension

HTTP API for Kit-native video recording and screenshot capture via omni.kit.capture.viewport.
Replaces the original PyAV-based worldrecorder with a more reliable Kit-native implementation.
"""

__version__ = "0.1.0"
__author__ = "agenTW∞rld Team"

# Expose the extension class so Kit can discover it
from .extension import AgentWorldRecorderExtension
