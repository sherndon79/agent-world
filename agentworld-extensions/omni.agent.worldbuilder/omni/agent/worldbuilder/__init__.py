"""
Agent WorldBuilder Extension for Isaac Sim

Thread-safe USD scene management extension with HTTP API for AI-powered worldbuilding.
Features revolutionary queue-based architecture that eliminates all thread safety issues
and provides complete scene lifecycle management through RESTful endpoints.
"""

__version__ = "1.0.0"
__author__ = "agenTW∞rld Team"

# Import and expose the extension class for Isaac Sim
from .extension import AgentWorldBuilderExtension