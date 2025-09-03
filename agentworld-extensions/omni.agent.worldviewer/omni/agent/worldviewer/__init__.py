"""
Agent WorldViewer Extension for Isaac Sim

Thread-safe camera control and viewport management extension with HTTP API for AI-powered
camera positioning. Features queue-based architecture that eliminates thread safety issues
and provides complete camera lifecycle management through RESTful endpoints.
"""

__version__ = "0.1.0"
__author__ = "agenTW∞rld Team"

# Import and expose the extension class for Isaac Sim
from .extension import AgentWorldViewerExtension