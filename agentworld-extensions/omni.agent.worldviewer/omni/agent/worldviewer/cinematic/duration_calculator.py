"""
Duration calculation utilities for cinematic camera movements.

Provides speed-based duration calculation and distance utilities.
"""

import math
from typing import List, Optional


def calculate_distance(start_position: List[float], end_position: List[float]) -> float:
    """
    Calculate 3D Euclidean distance between two positions.
    
    Args:
        start_position: Starting position [x, y, z]
        end_position: Ending position [x, y, z]
    
    Returns:
        Distance in 3D space
    """
    if len(start_position) != 3 or len(end_position) != 3:
        raise ValueError("Positions must be [x, y, z] arrays")
    
    dx = end_position[0] - start_position[0]
    dy = end_position[1] - start_position[1] 
    dz = end_position[2] - start_position[2]
    
    return math.sqrt(dx*dx + dy*dy + dz*dz)


def calculate_duration(start_position: List[float], end_position: List[float], 
                      speed: Optional[float] = None, duration: Optional[float] = None) -> float:
    """
    Calculate movement duration based on distance and speed.
    
    Args:
        start_position: Starting position [x, y, z]
        end_position: Ending position [x, y, z]  
        speed: Average speed in units per second (optional)
        duration: Direct duration override (optional)
    
    Returns:
        Duration in seconds
        
    Note:
        - If duration is provided, it takes precedence
        - If speed is provided, duration = distance / speed
        - If neither provided, uses default speed
    """
    # Direct duration override takes precedence
    if duration is not None:
        return duration
    
    # Calculate distance
    distance = calculate_distance(start_position, end_position)
    
    # Handle zero distance (same position)
    if distance < 0.001:  # Small epsilon for floating point comparison
        return 0.1  # Minimum duration for zero movement
    
    # Use provided speed or reasonable default
    if speed is None or speed <= 0:
        speed = 10.0  # Default speed: 10 units per second
    
    return distance / speed


def get_default_speeds() -> dict:
    """
    Get default speeds for different shot types.
    
    Returns:
        Dictionary mapping shot types to default speeds
    """
    return {
        'smooth_move': 10.0,   # Moderate speed for smooth transitions  
        'arc_shot': 8.0,       # Slightly slower for curved movements
        'orbit_shot': 15.0,    # Faster for orbital movements
    }


def validate_speed_parameters(params: dict) -> dict:
    """
    Validate and normalize speed/duration parameters.
    
    Args:
        params: Shot parameters dictionary
        
    Returns:
        Updated parameters with calculated duration
    """
    # Get speed and duration from params
    speed = params.get('speed')
    duration = params.get('duration')
    operation = params.get('operation', 'smooth_move')
    
    # Need positions for calculation
    start_pos = params.get('start_position')
    end_pos = params.get('end_position')
    
    if not start_pos or not end_pos:
        # Can't calculate distance-based duration
        if duration is None:
            params['duration'] = 3.0  # Fallback default
        return params
    
    # Get default speed for shot type if not provided
    if speed is None and duration is None:
        default_speeds = get_default_speeds()
        speed = default_speeds.get(operation, 10.0)
    
    # Calculate duration
    calculated_duration = calculate_duration(start_pos, end_pos, speed, duration)
    
    # Update params with calculated duration
    params['duration'] = calculated_duration
    
    # Store original speed for reference
    if speed is not None:
        params['calculated_from_speed'] = speed
    
    return params