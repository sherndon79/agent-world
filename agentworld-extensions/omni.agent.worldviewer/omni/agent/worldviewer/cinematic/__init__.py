"""
Cinematic module for WorldViewer camera movements.

This module provides modular components for cinematic camera control:
- Queue management for sequential shot execution
- Keyframe generation for different shot types  
- Duration calculation based on speed and distance
- Position continuity validation
- Movement state tracking
"""

from .movement_state import MovementState, EasingType
from .duration_calculator import calculate_distance, calculate_duration

__all__ = [
    'MovementState', 
    'EasingType',
    'calculate_distance',
    'calculate_duration'
]