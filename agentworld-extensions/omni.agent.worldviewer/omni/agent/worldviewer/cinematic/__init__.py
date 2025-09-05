"""
Cinematic module for WorldViewer camera movements.

This module provides modular components for cinematic camera control:
- Movement state data structures and enums
- Style registry for cinematic shot configurations
- Easing functions for smooth motion curves
- Duration calculation based on speed and distance
- Position continuity validation
- Movement state tracking
"""

# Core data structures
from .movement_state import MovementState, EasingType, ShotType, FramingStyle

# Style management
from .style_registry import (
    CINEMATIC_STYLES,
    get_style_config,
    get_available_styles,
    validate_style_params,
    list_all_shot_types,
    list_all_styles,
    rotation_to_target
)

# Easing functions
from .easing import EasingFunctions, get_easing_function, get_easing_function_by_name

# Duration calculations
from .duration_calculator import calculate_distance, calculate_duration, validate_speed_parameters

# Queue management
from .queue_manager import QueueManager, QueueStateManager

__all__ = [
    # Data structures
    'MovementState', 
    'EasingType',
    'ShotType',
    'FramingStyle',
    
    # Style management
    'CINEMATIC_STYLES',
    'get_style_config',
    'get_available_styles',
    'validate_style_params',
    'list_all_shot_types',
    'list_all_styles',
    'rotation_to_target',
    
    # Easing functions
    'EasingFunctions',
    'get_easing_function',
    'get_easing_function_by_name',
    
    # Duration calculations
    'calculate_distance',
    'calculate_duration',
    'validate_speed_parameters',
    
    # Queue management
    'QueueManager',
    'QueueStateManager'
]