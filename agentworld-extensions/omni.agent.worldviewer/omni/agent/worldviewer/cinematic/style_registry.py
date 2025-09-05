"""
Cinematic style registry for WorldViewer camera movements.

This module contains the centralized style configuration system that provides
data-driven control over cinematic shot parameters. Each shot type can have
multiple style variants with different parameter sets.
"""

import math
from typing import Dict, List


# Centralized Style Registry - Data-driven approach for maximum flexibility
CINEMATIC_STYLES = {
    "dolly_shot": {
        "standard": {
            "description": "Balanced dolly movement with moderate deceleration",
            "deceleration_factor": 0.5,
            "approach_curve": "ease_in_out"
        },
        "creeping": {
            "description": "Slow emotional reveal - Hitchcock style",
            "deceleration_factor": 0.8,
            "approach_curve": "ease_in_cubic"
        },
        "aggressive": {
            "description": "Fast dramatic approach - action sequences",
            "deceleration_factor": 0.2,
            "approach_curve": "ease_out"
        },
        "floating": {
            "description": "Dreamy, weightless movement",
            "deceleration_factor": 0.95,
            "approach_curve": "ease_in_out_quartic"
        }
    },
    "orbit_shot": {
        "standard": {
            "description": "Balanced orbital movement",
            "banking_angle": 2,
            "speed_variation": 0.1,
            "elevation_drift": 0
        },
        "surveillance": {
            "description": "Clinical, steady orbital observation",
            "banking_angle": 0,
            "speed_variation": 0.0,
            "elevation_drift": 0
        },
        "hero_reveal": {
            "description": "Dramatic character introduction",
            "banking_angle": 5,
            "speed_variation": 0.3,
            "elevation_drift": 2
        },
        "intimate": {
            "description": "Close emotional circling",
            "banking_angle": 2,
            "speed_variation": 0.1,
            "elevation_drift": -1
        }
    },
    "aerial_shot": {
        "standard": {
            "description": "Balanced aerial movement",
            "banking_angle": 3,
            "spiral_factor": 0.1,
            "altitude_curve": "ease_in_out"
        },
        "establishing": {
            "description": "Wide landscape context shots",
            "banking_angle": 0,
            "spiral_factor": 0.0,
            "altitude_curve": "linear"
        },
        "tracking": {
            "description": "Following subjects from above",
            "banking_angle": 8,
            "spiral_factor": 0.2,
            "altitude_curve": "ease_in_out"
        },
        "flyover": {
            "description": "Geographic perspective sweep",
            "banking_angle": 3,
            "spiral_factor": 0.0,
            "altitude_curve": "ease_out"
        }
    },
    "arc_shot": {
        "standard": {
            "description": "Balanced curved movement",
            "curvature_intensity": 0.25,
            "banking_behavior": True,
            "scene_focus_factor": 0.7
        },
        "gentle": {
            "description": "Subtle curved movement",
            "curvature_intensity": 0.15,
            "banking_behavior": False,
            "scene_focus_factor": 0.3
        },
        "dramatic": {
            "description": "Pronounced curved movement with banking",
            "curvature_intensity": 0.4,
            "banking_behavior": True,
            "scene_focus_factor": 1.0
        },
        "smooth": {
            "description": "Ultra-smooth arc with minimal banking",
            "curvature_intensity": 0.2,
            "banking_behavior": False,
            "scene_focus_factor": 0.5
        }
    },
    "pan_tilt_shot": {
        "standard": {
            "description": "Balanced rotational movement",
            "rotation_smoothness": 0.5,
            "acceleration_curve": "ease_in_out",
            "pivot_behavior": "fixed"
        },
        "mechanical": {
            "description": "Precise, steady rotation",
            "rotation_smoothness": 0.1,
            "acceleration_curve": "linear",
            "pivot_behavior": "fixed"
        },
        "handheld": {
            "description": "Natural, slightly uneven rotation",
            "rotation_smoothness": 0.8,
            "acceleration_curve": "ease_in_out",
            "pivot_behavior": "slight_drift"
        },
        "dramatic": {
            "description": "Dynamic rotation with varied speed",
            "rotation_smoothness": 0.6,
            "acceleration_curve": "ease_out",
            "pivot_behavior": "fixed"
        }
    }
}


def get_style_config(shot_type: str, style_name: str = "standard") -> Dict:
    """
    Get style configuration for a specific shot type and style.
    
    Args:
        shot_type: The type of shot (dolly_shot, orbit_shot, etc.)
        style_name: The style variant (standard, creeping, aggressive, etc.)
        
    Returns:
        Dict containing style parameters, defaults to standard if not found
    """
    shot_styles = CINEMATIC_STYLES.get(shot_type, {})
    return shot_styles.get(style_name, shot_styles.get("standard", {}))


def get_available_styles(shot_type: str) -> List[str]:
    """
    Get list of available styles for a specific shot type.
    
    Args:
        shot_type: The type of shot
        
    Returns:
        List of available style names for the shot type
    """
    return list(CINEMATIC_STYLES.get(shot_type, {}).keys())


def validate_style_params(shot_type: str, style_name: str, params: Dict) -> Dict:
    """
    Validate and merge style parameters with user-provided parameters.
    
    Args:
        shot_type: The type of shot
        style_name: The style variant
        params: User-provided parameters
        
    Returns:
        Dict with merged and validated parameters
    """
    style_config = get_style_config(shot_type, style_name)
    
    # Start with style defaults
    merged_params = dict(style_config)
    
    # Override with user parameters
    merged_params.update(params)
    
    # Ensure style information is preserved
    merged_params['_style_type'] = shot_type
    merged_params['_style_name'] = style_name
    
    return merged_params


def list_all_shot_types() -> List[str]:
    """Get list of all available shot types"""
    return list(CINEMATIC_STYLES.keys())


def list_all_styles() -> Dict[str, List[str]]:
    """Get dict mapping shot types to their available styles"""
    return {shot_type: get_available_styles(shot_type) for shot_type in list_all_shot_types()}


def rotation_to_target(position: List[float], rotation: List[float], distance: float = 10.0) -> List[float]:
    """
    Convert camera rotation angles to target point using Isaac Sim's coordinate system.
    
    Args:
        position: Camera position [x, y, z]
        rotation: Camera rotation [rx, ry, rz] in degrees (Isaac Sim format)
        distance: Distance from camera to target point
        
    Returns:
        Target point [x, y, z] where camera should look
    """
    # Ensure all values are numeric
    try:
        px, py, pz = [float(p) for p in position]
        rx, ry, rz = [math.radians(float(r)) for r in rotation]
    except (ValueError, TypeError) as e:
        raise ValueError(f"Position and rotation must be numeric values: {e}")
    
    # Isaac Sim rotation matrix conversion
    # Create rotation matrices for each axis (Isaac Sim uses XYZ Euler angles)
    
    # Rotation around X-axis (pitch)
    cos_x, sin_x = math.cos(rx), math.sin(rx)
    # Rotation around Y-axis (yaw) 
    cos_y, sin_y = math.cos(ry), math.sin(ry)
    # Rotation around Z-axis (roll)
    cos_z, sin_z = math.cos(rz), math.sin(rz)
    
    # Combined rotation matrix (ZYX order) applied to forward vector
    # Isaac Sim camera forward direction is typically -Z in local space
    # Forward vector in local camera space: [0, 0, -1]
    
    # Apply rotations in order: Z(roll) * Y(yaw) * X(pitch) * [0, 0, -1]
    # This gives us the world-space forward direction
    fx = sin_y
    fy = -sin_x * cos_y  
    fz = -cos_x * cos_y
    
    # Calculate target point
    target = [
        px + fx * distance,
        py + fy * distance, 
        pz + fz * distance
    ]
    
    return target