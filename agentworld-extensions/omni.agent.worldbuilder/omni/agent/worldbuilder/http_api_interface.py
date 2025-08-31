"""
Compatibility wrapper for WorldBuilder HTTP API Interface.

This module provides backward compatibility by re-exporting the HTTPAPIInterface 
from api_interface.py. This maintains compatibility with existing imports while 
following the naming patterns of other World* extensions.
"""

from .api_interface import HTTPAPIInterface  # noqa: F401

# Re-export for backward compatibility
__all__ = ['HTTPAPIInterface']