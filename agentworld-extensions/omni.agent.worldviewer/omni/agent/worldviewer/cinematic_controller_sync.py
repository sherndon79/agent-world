"""
XR WorldViewer Synchronous Cinematic Camera Controller

Provides smooth, interpolated camera movements using Isaac Sim's timer system.
No asyncio - all operations run on the main thread via timers.
"""

import logging
import math
import time
from typing import Dict, List, Optional, Tuple, Callable
from dataclasses import dataclass
from enum import Enum

import omni.usd
import omni.kit.app
from omni.kit.viewport.utility import get_active_viewport_window
from pxr import Gf, UsdGeom

from .camera_controller import CameraController


logger = logging.getLogger(__name__)


class EasingType(Enum):
    """Easing function types for smooth movement"""
    LINEAR = "linear"
    EASE_IN = "ease_in"
    EASE_OUT = "ease_out"
    EASE_IN_OUT = "ease_in_out"
    BOUNCE = "bounce"
    ELASTIC = "elastic"


class ShotType(Enum):
    """Cinematic shot type classifications"""
    CLOSE_UP = "close_up"
    MEDIUM = "medium"
    WIDE = "wide"
    ESTABLISHING = "establishing"
    EXTREME_WIDE = "extreme_wide"


class FramingStyle(Enum):
    """Camera framing composition styles"""
    CENTER = "center"
    RULE_OF_THIRDS_LEFT = "rule_of_thirds_left"
    RULE_OF_THIRDS_RIGHT = "rule_of_thirds_right"
    LOW_ANGLE = "low_angle"
    HIGH_ANGLE = "high_angle"


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
    import math
    
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


@dataclass
class MovementState:
    """State of an active movement"""
    movement_id: str
    operation: str
    start_time: float
    duration: float
    keyframes: List[Dict]
    current_frame: int
    status: str
    params: Dict


class EasingFunctions:
    """Collection of easing functions for smooth animations"""
    
    @staticmethod
    def linear(t: float) -> float:
        return t
    
    @staticmethod
    def ease_in(t: float) -> float:
        return t * t
    
    @staticmethod
    def ease_out(t: float) -> float:
        return 1 - (1 - t) * (1 - t)
    
    @staticmethod
    def ease_in_out(t: float) -> float:
        if t < 0.5:
            return 2 * t * t
        return 1 - 2 * (1 - t) * (1 - t)
    
    @staticmethod
    def bounce(t: float) -> float:
        if t < 1/2.75:
            return 7.5625 * t * t
        elif t < 2/2.75:
            t -= 1.5/2.75
            return 7.5625 * t * t + 0.75
        elif t < 2.5/2.75:
            t -= 2.25/2.75
            return 7.5625 * t * t + 0.9375
        else:
            t -= 2.625/2.75
            return 7.5625 * t * t + 0.984375
    
    @staticmethod
    def elastic(t: float) -> float:
        if t == 0 or t == 1:
            return t
        return -(2**(-10 * t)) * math.sin((t - 0.1) * (2 * math.pi) / 0.4) + 1


class SynchronousCinematicController:
    """Synchronous cinematic camera controller using Isaac Sim timers"""
    
    # Configuration constants
    DEFAULT_FPS = 30
    MAX_DURATION = 60.0  # Maximum movement duration in seconds
    MIN_DURATION = 0.1   # Minimum movement duration in seconds
    MAX_CONCURRENT_MOVEMENTS = 10  # Allow more queued camera transitions for better workflow
    MOVEMENT_TRANSITION_DELAY = 0.2  # Small delay between movements for capture sync
    
    def __init__(self, camera_controller: CameraController):
        self.camera_controller = camera_controller
        self.active_movements = {}
        self.movement_timer = None
        self.fps = self.DEFAULT_FPS
        self.frame_duration = 1.0 / self.fps  # Time per frame in seconds
        
        # Easing function mapping
        self.easing_functions = {
            EasingType.LINEAR: EasingFunctions.linear,
            EasingType.EASE_IN: EasingFunctions.ease_in,
            EasingType.EASE_OUT: EasingFunctions.ease_out,
            EasingType.EASE_IN_OUT: EasingFunctions.ease_in_out,
            EasingType.BOUNCE: EasingFunctions.bounce,
            EasingType.ELASTIC: EasingFunctions.elastic
        }
        
        self._start_movement_timer()
    
    def _start_movement_timer(self):
        """Start the timer that processes movement frames"""
        try:
            def process_movements(dt):
                """Process all active movements"""
                self._update_movements()
            
            # Create timer to process movements at target FPS
            update_stream = omni.kit.app.get_app().get_update_event_stream()
            self.movement_timer = update_stream.create_subscription_to_pop(
                process_movements, name="cinematic_movement_timer"
            )
            
            logger.info(f"Cinematic movement timer started at {self.fps} FPS")
            
        except Exception as e:
            logger.error(f"Failed to start movement timer: {e}")
    
    def stop_movement_timer(self):
        """Stop the movement timer"""
        if self.movement_timer:
            self.movement_timer.unsubscribe()
            self.movement_timer = None
    
    def _update_movements(self):
        """Update all active movements"""
        if not self.active_movements:
            return  # Early exit if no movements
            
        current_time = time.time()
        completed_movements = []
        
        for movement_id, movement in self.active_movements.items():
            try:
                # Check if movement is complete
                elapsed = current_time - movement.start_time
                if elapsed >= movement.duration:
                    # Complete the movement with final frame
                    self._apply_final_frame(movement)
                    completed_movements.append(movement_id)
                    continue
                
                # Calculate current frame
                progress = elapsed / movement.duration
                frame_index = int(progress * len(movement.keyframes))
                frame_index = min(frame_index, len(movement.keyframes) - 1)
                
                # Apply current frame
                if frame_index < len(movement.keyframes):
                    frame = movement.keyframes[frame_index]
                    self.camera_controller.set_position(
                        frame['position'], 
                        frame.get('target')
                    )
                    movement.current_frame = frame_index
                
            except Exception as e:
                logger.error(f"Error updating movement {movement_id}: {e}")
                completed_movements.append(movement_id)
        
        # Clean up completed movements
        for movement_id in completed_movements:
            del self.active_movements[movement_id]
            logger.info(f"Completed cinematic movement: {movement_id}")
    
    def _apply_final_frame(self, movement: MovementState):
        """Apply the final frame of a movement"""
        if movement.keyframes:
            final_frame = movement.keyframes[-1]
            self.camera_controller.set_position(
                final_frame['position'],
                final_frame.get('target')
            )
    
    def start_movement(self, movement_id: str, operation: str, params: Dict):
        """Start a new cinematic movement"""
        try:
            # Check concurrent movement limit
            if len(self.active_movements) >= self.MAX_CONCURRENT_MOVEMENTS:
                raise ValueError(f"Camera movement queue full ({len(self.active_movements)}/{self.MAX_CONCURRENT_MOVEMENTS}). Use 'stop_movement' API to cancel active movements or wait for completion.")
            
            # Validate duration
            duration = params.get('duration', 3.0)
            if not (self.MIN_DURATION <= duration <= self.MAX_DURATION):
                raise ValueError(f"Duration must be between {self.MIN_DURATION} and {self.MAX_DURATION} seconds")
            # Generate keyframes based on operation type
            if operation == 'smooth_move':
                keyframes = self._generate_smooth_move_keyframes(params)
            elif operation == 'aerial_shot':
                keyframes = self._generate_aerial_shot_keyframes(params)
            elif operation == 'orbit_shot':
                keyframes = self._generate_orbit_shot_keyframes(params)
            elif operation == 'dolly_shot':
                keyframes = self._generate_dolly_shot_keyframes(params)
            elif operation == 'pan_tilt_shot':
                keyframes = self._generate_pan_tilt_keyframes(params)
            elif operation == 'arc_shot':
                keyframes = self._generate_arc_shot_keyframes(params)
            else:
                raise ValueError(f"Unknown operation: {operation}")
            
            # Create movement state
            movement = MovementState(
                movement_id=movement_id,
                operation=operation,
                start_time=time.time(),
                duration=params.get('duration', 3.0),
                keyframes=keyframes,
                current_frame=0,
                status='active',
                params=params
            )
            
            self.active_movements[movement_id] = movement
            logger.info(f"Started cinematic movement: {movement_id} ({operation})")
            
        except Exception as e:
            logger.error(f"Failed to start movement {movement_id}: {e}")
    
    def _generate_smooth_move_keyframes(self, params: Dict) -> List[Dict]:
        """Generate keyframes for smooth movement"""
        # Validate required parameters
        if 'start_position' not in params or 'end_position' not in params:
            raise ValueError("start_position and end_position are required")
        
        start_pos = params['start_position']
        end_pos = params['end_position']
        
        # Validate position format
        if not (isinstance(start_pos, list) and len(start_pos) == 3):
            raise ValueError("start_position must be [x, y, z] list")
        if not (isinstance(end_pos, list) and len(end_pos) == 3):
            raise ValueError("end_position must be [x, y, z] list")
        # Handle rotation data if provided (preferred over target points)
        start_rotation = params.get('start_rotation')
        end_rotation = params.get('end_rotation')
        start_target = params.get('start_target')
        end_target = params.get('end_target')
        duration = params.get('duration', 3.0)
        easing_value = params.get('easing_type', 'ease_in_out')
        easing_type = EasingType(easing_value) if easing_value is not None else EasingType.EASE_IN_OUT
        
        # Debug: Log rotation data
        logger.info(f"DEBUG: start_rotation = {start_rotation} (type: {type(start_rotation)})")
        logger.info(f"DEBUG: end_rotation = {end_rotation} (type: {type(end_rotation)})")
        
        # Convert rotation to target points if rotation data is provided
        if start_rotation is not None:
            # Validate rotation format
            if not (isinstance(start_rotation, list) and len(start_rotation) == 3):
                raise ValueError("start_rotation must be [pitch, yaw, roll] list")
            start_target = rotation_to_target(start_pos, start_rotation)
        elif start_target is None:
            current_status = self.camera_controller.get_status()
            if current_status.get('connected') and current_status.get('target'):
                start_target = current_status['target']
            else:
                start_target = [start_pos[0], start_pos[1], start_pos[2] - 10]
        
        if end_rotation is not None:
            # Validate rotation format
            if not (isinstance(end_rotation, list) and len(end_rotation) == 3):
                raise ValueError("end_rotation must be [pitch, yaw, roll] list")
            end_target = rotation_to_target(end_pos, end_rotation)
        elif end_target is None:
            end_target = [end_pos[0], end_pos[1], end_pos[2] - 10]
        
        # Generate keyframes
        num_frames = int(duration * self.fps)
        keyframes = []
        easing_func = self.easing_functions[easing_type]
        
        for i in range(num_frames + 1):
            t = i / num_frames
            eased_t = easing_func(t)
            
            # Interpolate position
            pos = [
                start_pos[0] + (end_pos[0] - start_pos[0]) * eased_t,
                start_pos[1] + (end_pos[1] - start_pos[1]) * eased_t,
                start_pos[2] + (end_pos[2] - start_pos[2]) * eased_t
            ]
            
            # Interpolate target
            target = [
                start_target[0] + (end_target[0] - start_target[0]) * eased_t,
                start_target[1] + (end_target[1] - start_target[1]) * eased_t,
                start_target[2] + (end_target[2] - start_target[2]) * eased_t
            ]
            
            keyframes.append({
                'position': pos,
                'target': target,
                'time': t * duration
            })
        
        return keyframes
    
    def _generate_aerial_shot_keyframes(self, params: Dict) -> List[Dict]:
        """Generate keyframes for aerial shot"""
        # Check if keyframe mode (start_position provided)
        if 'start_position' in params and 'end_position' in params:
            # Use keyframe parameters directly
            return self._generate_smooth_move_keyframes({
                'start_position': params['start_position'],
                'end_position': params['end_position'],
                'start_target': params.get('start_target'),
                'end_target': params.get('end_target'),
                'duration': params.get('duration', 8.0),
                'easing_type': params.get('easing_type', 'ease_in_out')
            })
        else:
            # Fallback to original height/radius mode
            return self._generate_smooth_move_keyframes({
                'start_position': [0, params['start_height'], params['start_radius']],
                'end_position': [0, params['end_height'], params['end_radius']],
                'duration': params.get('duration', 8.0),
                'easing_type': params.get('easing_type', 'ease_in_out')
            })
    
    def _generate_orbit_shot_keyframes(self, params: Dict) -> List[Dict]:
        """Generate keyframes for orbit shot"""
        # Check if keyframe mode (start_position provided) or target_object mode
        if 'start_position' in params or 'target_object' in params:
            # If target_object provided but no start_position, get current camera position
            if 'target_object' in params and 'start_position' not in params:
                try:
                    current_status = self.camera_controller.get_status()
                    if current_status.get('connected') and current_status.get('position'):
                        params = params.copy()  # Don't modify original
                        params['start_position'] = current_status['position']
                except Exception as e:
                    logger.warning(f"Failed to get current camera position for orbit shot: {e}")
                    # Fallback to spherical orbit mode
                    pass
                else:
                    return self._generate_cinematic_orbit_around_target(params)
            else:
                return self._generate_cinematic_orbit_around_target(params)
        
        # Fallback to original spherical orbit mode - provide defaults if missing
        start_azimuth = math.radians(params.get('start_azimuth', 0.0))
        end_azimuth = math.radians(params.get('end_azimuth', 360.0))
        distance = params.get('distance', 10.0)
        elevation = math.radians(params.get('elevation', 15.0))
        duration = params.get('duration', 8.0)
        
        num_frames = int(duration * self.fps)
        keyframes = []
        
        for i in range(num_frames + 1):
            t = i / num_frames
            azimuth = start_azimuth + (end_azimuth - start_azimuth) * t
            
            # Calculate position from spherical coordinates
            x = distance * math.cos(elevation) * math.cos(azimuth)
            y = distance * math.sin(elevation)
            z = distance * math.cos(elevation) * math.sin(azimuth)
            
            keyframes.append({
                'position': [x, y, z],
                'target': [0, 0, 0],  # Look at origin
                'time': t * duration
            })
        
        return keyframes
    
    def _generate_cinematic_orbit_around_target(self, params: Dict) -> List[Dict]:
        """Generate orbital movement around target object from keyframe starting position"""
        import math
        
        start_pos = params['start_position']
        target_object = params.get('target_object')
        orbit_count = float(params.get('orbit_count', 1.0))  # Number of full orbits (1.0 = 360°)
        arc_degrees = orbit_count * 360.0  # Convert orbit count to degrees
        duration = float(params.get('duration', 8.0))
        
        # Calculate orbit center from actual target object using worldviewer's asset transform
        if target_object:
            try:
                # Use camera controller's asset transform method (the proper way!)
                transform_result = self.camera_controller.get_asset_transform(target_object, calculation_mode="auto")
                if transform_result.get('success') and transform_result.get('position'):
                    orbit_center = transform_result['position']
                    logger.info(f"🎯 Using target object center: {target_object} at {orbit_center}")
                else:
                    logger.warning(f"Failed to get transform for {target_object}: {transform_result.get('error', 'Unknown error')}")
                    orbit_center = [0, 0, 0]  # Fallback
            except Exception as e:
                logger.warning(f"Failed to calculate target object center via asset transform: {e}")
                orbit_center = [0, 0, 0]  # Fallback
        else:
            orbit_center = [0, 0, 0]
        
        # Calculate orbit parameters from starting position
        start_vec = [start_pos[0] - orbit_center[0], start_pos[1] - orbit_center[1], start_pos[2] - orbit_center[2]]
        orbit_radius = math.sqrt(sum(x*x for x in start_vec))  # Use keyframe distance as orbital radius
        
        # Calculate starting angle in XY plane (azimuth)
        start_azimuth = math.atan2(start_vec[1], start_vec[0])
        
        # Calculate elevation (angle from XY plane for orbital position)
        start_elevation = math.asin(start_vec[2] / orbit_radius) if orbit_radius > 0 else 0
        
        # Calculate the original camera's elevation angle to preserve up/down viewing
        start_target = params.get('start_target')
        if not start_target:
            # Default target if not provided
            start_target = orbit_center
        
        # Calculate the original viewing direction vector from keyframe
        view_vector = [
            start_target[0] - start_pos[0],
            start_target[1] - start_pos[1], 
            start_target[2] - start_pos[2]
        ]
        view_distance = math.sqrt(sum(x*x for x in view_vector))
        
        # Calculate the original elevation angle of the camera's view
        if view_distance > 0:
            # Elevation angle = angle between view vector and horizontal plane
            original_view_elevation = math.asin(view_vector[2] / view_distance)
        else:
            original_view_elevation = -0.1  # Default slight downward angle
        
        # Calculate end angle based on arc degrees
        arc_radians = math.radians(arc_degrees)
        end_azimuth = start_azimuth + arc_radians
        
        # Generate orbital keyframes
        num_frames = int(duration * self.fps)
        keyframes = []
        
        for i in range(num_frames + 1):
            t = i / num_frames
            
            # Orbital easing - smooth like satellite motion
            eased_t = 0.5 * (1 - math.cos(math.pi * t))
            
            # Calculate current orbital angle
            current_azimuth = start_azimuth + (end_azimuth - start_azimuth) * eased_t
            
            # Calculate position on orbital path (maintaining elevation)
            pos = [
                orbit_center[0] + orbit_radius * math.cos(start_elevation) * math.cos(current_azimuth),
                orbit_center[1] + orbit_radius * math.cos(start_elevation) * math.sin(current_azimuth), 
                orbit_center[2] + orbit_radius * math.sin(start_elevation)
            ]
            
            # Calculate horizontal direction to orbit center for tracking
            horizontal_to_center = [
                orbit_center[0] - pos[0],
                orbit_center[1] - pos[1],
                0  # Keep horizontal only
            ]
            horizontal_distance = math.sqrt(horizontal_to_center[0]**2 + horizontal_to_center[1]**2)
            
            if horizontal_distance > 0:
                # Normalize horizontal direction
                horizontal_direction = [
                    horizontal_to_center[0] / horizontal_distance,
                    horizontal_to_center[1] / horizontal_distance,
                    0
                ]
                
                # Apply the original elevation angle to the horizontal tracking direction
                target_distance = 100  # Fixed distance for target calculation
                target = [
                    pos[0] + horizontal_direction[0] * target_distance * math.cos(original_view_elevation),
                    pos[1] + horizontal_direction[1] * target_distance * math.cos(original_view_elevation),
                    pos[2] + target_distance * math.sin(original_view_elevation)
                ]
            else:
                # Fallback if no horizontal distance
                target = orbit_center
            
            keyframes.append({
                'position': pos,
                'target': target,
                'time': t * duration
            })
        
        return keyframes
    
    def _generate_cinematic_orbit_keyframes(self, params: Dict) -> List[Dict]:
        """Generate cinematic sweeping arc path between keyframes (like banking turn/curved dolly track)"""
        import math
        
        start_pos = params['start_position']
        end_pos = params['end_position']
        start_target = params.get('start_target')
        end_target = params.get('end_target')
        duration = params.get('duration', 8.0)
        
        # Calculate movement vector and distance
        move_vector = [end_pos[0] - start_pos[0], end_pos[1] - start_pos[1], end_pos[2] - start_pos[2]]
        move_distance = math.sqrt(sum(x*x for x in move_vector))
        
        # Create a curved arc path using quadratic Bezier curve
        # Control point is offset perpendicular to the movement vector
        if move_distance > 0:
            # Normalize movement vector
            move_norm = [x / move_distance for x in move_vector]
            
            # Calculate perpendicular vector for arc curvature
            # Use cross product with Z-up to get a horizontal arc
            if abs(move_norm[2]) < 0.9:  # Not mostly vertical movement
                # Cross product with Z-up [0,0,1] gives horizontal perpendicular
                perp = [move_norm[1], -move_norm[0], 0]
            else:
                # For vertical movement, use Y-axis perpendicular
                perp = [0, 1, 0]
            
            # Normalize perpendicular vector
            perp_mag = math.sqrt(sum(x*x for x in perp))
            if perp_mag > 0:
                perp = [x / perp_mag for x in perp]
            else:
                perp = [1, 0, 0]  # Fallback
            
            # Calculate control point for Bezier curve (offset sideways from midpoint)
            midpoint = [
                start_pos[0] + move_vector[0] * 0.5,
                start_pos[1] + move_vector[1] * 0.5,
                start_pos[2] + move_vector[2] * 0.5
            ]
            
            # Arc curvature: 25% of movement distance as sideways offset
            arc_offset = move_distance * 0.25
            control_point = [
                midpoint[0] + perp[0] * arc_offset,
                midpoint[1] + perp[1] * arc_offset,
                midpoint[2] + perp[2] * arc_offset + move_distance * 0.1  # Slight elevation too
            ]
        else:
            # No movement, fallback to linear
            control_point = start_pos
        
        # Create curved arc path
        num_frames = int(duration * self.fps)
        keyframes = []
        
        for i in range(num_frames + 1):
            t = i / num_frames
            
            # Smooth easing for cinematic feel
            eased_t = 0.5 * (1 - math.cos(math.pi * t))  # Sinusoidal easing
            
            # CRITICAL: Ensure exact start and end positions
            if i == 0:
                pos = start_pos[:]
            elif i == num_frames:
                pos = end_pos[:]
            else:
                # Quadratic Bezier curve: P(t) = (1-t)²P₀ + 2(1-t)tP₁ + t²P₂
                # P₀ = start_pos, P₁ = control_point, P₂ = end_pos
                t_sq = eased_t * eased_t
                one_minus_t = 1 - eased_t
                one_minus_t_sq = one_minus_t * one_minus_t
                
                pos = [
                    one_minus_t_sq * start_pos[0] + 2 * one_minus_t * eased_t * control_point[0] + t_sq * end_pos[0],
                    one_minus_t_sq * start_pos[1] + 2 * one_minus_t * eased_t * control_point[1] + t_sq * end_pos[1],
                    one_minus_t_sq * start_pos[2] + 2 * one_minus_t * eased_t * control_point[2] + t_sq * end_pos[2]
                ]
            
            # Smart target calculation for curved path
            if start_target and end_target:
                if i == 0:
                    target = start_target[:]
                elif i == num_frames:
                    target = end_target[:]
                else:
                    # Instead of linear interpolation, calculate target that maintains scene focus
                    # Find the scene center (average of start and end targets)
                    scene_center = [
                        (start_target[0] + end_target[0]) / 2,
                        (start_target[1] + end_target[1]) / 2,
                        (start_target[2] + end_target[2]) / 2
                    ]
                    
                    # Blend between current interpolated target and scene center
                    # More scene center in the middle of the arc for natural looking
                    scene_focus_factor = math.sin(math.pi * t) * 0.7  # Peak focus on scene center at t=0.5
                    
                    linear_target = [
                        start_target[0] + (end_target[0] - start_target[0]) * eased_t,
                        start_target[1] + (end_target[1] - start_target[1]) * eased_t,
                        start_target[2] + (end_target[2] - start_target[2]) * eased_t
                    ]
                    
                    target = [
                        linear_target[0] + (scene_center[0] - linear_target[0]) * scene_focus_factor,
                        linear_target[1] + (scene_center[1] - linear_target[1]) * scene_focus_factor,
                        linear_target[2] + (scene_center[2] - linear_target[2]) * scene_focus_factor
                    ]
            else:
                # Default: look at scene center (average of positions)
                scene_center = [
                    (start_pos[0] + end_pos[0]) / 2,
                    (start_pos[1] + end_pos[1]) / 2,
                    (start_pos[2] + end_pos[2]) / 2 - 10  # Look slightly down
                ]
                target = scene_center
            
            keyframes.append({
                'position': pos,
                'target': target,
                'time': t * duration
            })
        
        return keyframes
    
    def _generate_dolly_shot_keyframes(self, params: Dict) -> List[Dict]:
        """Generate keyframes for dolly shot with cinematic dolly behavior"""
        # Check if keyframe mode (start_position provided)
        if 'start_position' in params and 'end_position' in params:
            # Implement true dolly behavior between keyframes
            return self._generate_cinematic_dolly_keyframes(params)
        else:
            # Fallback to original target_object mode
            return self._generate_smooth_move_keyframes({
                'start_position': [0, 0, params['start_distance']],
                'end_position': [0, 0, params['end_distance']],
                'duration': params.get('duration', 5.0),
                'easing_type': params.get('easing_type', 'ease_in_out')
            })
    
    def _generate_cinematic_dolly_keyframes(self, params: Dict) -> List[Dict]:
        """Generate cinematic dolly movement between keyframes"""
        import math
        
        start_pos = params['start_position']
        end_pos = params['end_position']
        start_target = params.get('start_target')
        end_target = params.get('end_target')
        duration = params.get('duration', 5.0)
        movement_style = params.get('movement_style', 'standard')
        
        # Get style configuration
        style_config = get_style_config('dolly_shot', movement_style)
        
        # Calculate movement vector
        move_vector = [
            end_pos[0] - start_pos[0],
            end_pos[1] - start_pos[1], 
            end_pos[2] - start_pos[2]
        ]
        move_distance = math.sqrt(sum(x*x for x in move_vector))
        
        num_frames = int(duration * self.fps)
        keyframes = []
        
        for i in range(num_frames + 1):
            t = i / num_frames
            
            # Style-driven easing curve based on movement_style
            approach_curve = style_config.get('approach_curve', 'ease_in_out')
            
            if approach_curve == 'ease_in_cubic':
                eased_t = t * t * t
            elif approach_curve == 'ease_out':
                eased_t = 1 - (1 - t) * (1 - t)
            elif approach_curve == 'ease_in_out_quartic':
                if t < 0.5:
                    eased_t = 8 * t * t * t * t
                else:
                    eased_t = 1 - 8 * (1 - t) * (1 - t) * (1 - t) * (1 - t)
            else:  # Default ease_in_out
                if t < 0.5:
                    eased_t = 2 * t * t
                else:
                    eased_t = 1 - 2 * (1 - t) * (1 - t)
            
            # Style-driven deceleration for final approach (last 20% of movement)
            deceleration_factor = style_config.get('deceleration_factor', 0.5)
            if t > 0.8:
                decel_amount = 1 - (t - 0.8) * deceleration_factor
                eased_t = 0.8 + (eased_t - 0.8) * decel_amount
            
            # Interpolate position
            pos = [
                start_pos[0] + move_vector[0] * eased_t,
                start_pos[1] + move_vector[1] * eased_t,
                start_pos[2] + move_vector[2] * eased_t
            ]
            
            # Dolly target behavior: if both targets provided, interpolate
            # If not, maintain focus on the average target point
            if start_target and end_target:
                target = [
                    start_target[0] + (end_target[0] - start_target[0]) * eased_t,
                    start_target[1] + (end_target[1] - start_target[1]) * eased_t,
                    start_target[2] + (end_target[2] - start_target[2]) * eased_t
                ]
            elif start_target:
                target = start_target
            elif end_target:
                target = end_target
            else:
                # Default: look at midpoint between start and end positions
                mid_point = [
                    (start_pos[0] + end_pos[0]) / 2,
                    (start_pos[1] + end_pos[1]) / 2,
                    (start_pos[2] + end_pos[2]) / 2
                ]
                target = mid_point
            
            keyframes.append({
                'position': pos,
                'target': target,
                'time': t * duration
            })
        
        return keyframes
    
    def _generate_pan_tilt_keyframes(self, params: Dict) -> List[Dict]:
        """Generate keyframes for pan/tilt shot"""
        # Check if keyframe mode (start_position provided)
        if 'start_position' in params and 'end_position' in params:
            # Use keyframe parameters directly
            return self._generate_smooth_move_keyframes({
                'start_position': params['start_position'],
                'end_position': params['end_position'],
                'start_target': params.get('start_target'),
                'end_target': params.get('end_target'),
                'duration': params.get('duration', 6.0),
                'easing_type': params.get('easing_type', 'ease_in_out')
            })
        else:
            # Fallback to original azimuth/elevation mode
            return self._generate_orbit_shot_keyframes({
                'start_azimuth': params['start_azimuth'],
                'end_azimuth': params['end_azimuth'],
                'distance': 10.0,
                'elevation': (params['start_elevation'] + params['end_elevation']) / 2,
                'duration': params.get('duration', 6.0)
            })
    
    def _generate_arc_shot_keyframes(self, params: Dict) -> List[Dict]:
        """Generate keyframes for arc shot with curved Bezier path between keyframes"""
        import math
        
        # Validate required parameters
        if 'start_position' not in params or 'end_position' not in params:
            raise ValueError("Arc shot requires start_position and end_position")
        
        start_pos = params['start_position']
        end_pos = params['end_position']
        start_target = params.get('start_target')
        end_target = params.get('end_target')
        duration = float(params.get('duration', 6.0))
        movement_style = params.get('movement_style', 'standard')
        
        # Get style configuration
        style_config = get_style_config('arc_shot', movement_style)
        
        # Calculate movement vector and distance
        move_vector = [end_pos[0] - start_pos[0], end_pos[1] - start_pos[1], end_pos[2] - start_pos[2]]
        move_distance = math.sqrt(sum(x*x for x in move_vector))
        
        # Create a curved arc path using quadratic Bezier curve
        # Control point is offset perpendicular to the movement vector
        if move_distance > 0:
            # Normalize movement vector
            move_norm = [x / move_distance for x in move_vector]
            
            # Calculate perpendicular vector for arc curvature
            # Use cross product with Z-up to get a horizontal arc
            if abs(move_norm[2]) < 0.9:  # Not mostly vertical movement
                # Cross product with Z-up [0,0,1] gives horizontal perpendicular
                perp = [move_norm[1], -move_norm[0], 0]
            else:
                # For vertical movement, use Y-axis perpendicular
                perp = [0, 1, 0]
            
            # Normalize perpendicular vector
            perp_mag = math.sqrt(sum(x*x for x in perp))
            if perp_mag > 0:
                perp = [x / perp_mag for x in perp]
            else:
                perp = [1, 0, 0]  # Fallback
            
            # Calculate control point for Bezier curve (offset sideways from midpoint)
            midpoint = [
                start_pos[0] + move_vector[0] * 0.5,
                start_pos[1] + move_vector[1] * 0.5,
                start_pos[2] + move_vector[2] * 0.5
            ]
            
            # Style-driven arc curvature intensity
            curvature_intensity = style_config.get('curvature_intensity', 0.25)
            arc_offset = move_distance * curvature_intensity
            control_point = [
                midpoint[0] + perp[0] * arc_offset,
                midpoint[1] + perp[1] * arc_offset,
                midpoint[2] + perp[2] * arc_offset + move_distance * 0.1  # Slight elevation too
            ]
        else:
            # No movement, fallback to linear
            control_point = start_pos
        
        # Create curved arc path
        num_frames = int(duration * self.fps)
        keyframes = []
        
        for i in range(num_frames + 1):
            t = i / num_frames
            
            # Arc-specific easing for smooth banking motion
            eased_t = 0.5 * (1 - math.cos(math.pi * t))  # Sinusoidal easing
            
            # CRITICAL: Ensure exact start and end positions
            if i == 0:
                pos = start_pos[:]
            elif i == num_frames:
                pos = end_pos[:]
            else:
                # Quadratic Bezier curve: P(t) = (1-t)²P₀ + 2(1-t)tP₁ + t²P₂
                # P₀ = start_pos, P₁ = control_point, P₂ = end_pos
                t_sq = eased_t * eased_t
                one_minus_t = 1 - eased_t
                one_minus_t_sq = one_minus_t * one_minus_t
                
                pos = [
                    one_minus_t_sq * start_pos[0] + 2 * one_minus_t * eased_t * control_point[0] + t_sq * end_pos[0],
                    one_minus_t_sq * start_pos[1] + 2 * one_minus_t * eased_t * control_point[1] + t_sq * end_pos[1],
                    one_minus_t_sq * start_pos[2] + 2 * one_minus_t * eased_t * control_point[2] + t_sq * end_pos[2]
                ]
            
            # Simple linear target interpolation for arc shot
            if start_target and end_target:
                if i == 0:
                    target = start_target[:]
                elif i == num_frames:
                    target = end_target[:]
                else:
                    # Linear interpolation between start and end targets
                    target = [
                        start_target[0] + (end_target[0] - start_target[0]) * eased_t,
                        start_target[1] + (end_target[1] - start_target[1]) * eased_t,
                        start_target[2] + (end_target[2] - start_target[2]) * eased_t
                    ]
            else:
                # Default: look ahead along the movement direction
                if i < num_frames:
                    # Look toward the next position for natural forward-facing movement
                    next_i = min(i + 5, num_frames)  # Look a few frames ahead
                    next_t = next_i / num_frames
                    next_eased_t = 0.5 * (1 - math.cos(math.pi * next_t))
                    
                    if next_i == num_frames:
                        look_ahead_pos = end_pos[:]
                    else:
                        next_t_sq = next_eased_t * next_eased_t
                        next_one_minus_t = 1 - next_eased_t
                        next_one_minus_t_sq = next_one_minus_t * next_one_minus_t
                        
                        look_ahead_pos = [
                            next_one_minus_t_sq * start_pos[0] + 2 * next_one_minus_t * next_eased_t * control_point[0] + next_t_sq * end_pos[0],
                            next_one_minus_t_sq * start_pos[1] + 2 * next_one_minus_t * next_eased_t * control_point[1] + next_t_sq * end_pos[1],
                            next_one_minus_t_sq * start_pos[2] + 2 * next_one_minus_t * next_eased_t * control_point[2] + next_t_sq * end_pos[2]
                        ]
                    
                    target = look_ahead_pos
                else:
                    target = end_pos
            
            keyframes.append({
                'position': pos,
                'target': target,
                'time': t * duration
            })
        
        return keyframes
    
    def stop_movement(self, movement_id: str) -> Dict:
        """Stop an active movement"""
        if movement_id in self.active_movements:
            del self.active_movements[movement_id]
            return {'success': True, 'message': f'Stopped movement {movement_id}'}
        return {'success': False, 'error': f'Movement {movement_id} not found'}
    
    def get_movement_status(self, movement_id: str) -> Dict:
        """Get status of a movement"""
        if movement_id in self.active_movements:
            movement = self.active_movements[movement_id]
            elapsed = time.time() - movement.start_time
            progress = min(elapsed / movement.duration, 1.0)
            
            return {
                'success': True,
                'movement_id': movement_id,
                'operation': movement.operation,
                'status': movement.status,
                'progress': progress,
                'elapsed_time': elapsed,
                'total_duration': movement.duration
            }
        
        return {'success': False, 'error': f'Movement {movement_id} not found'}
    
    def list_active_movements(self) -> Dict:
        """List all active movements"""
        movements = []
        for movement_id, movement in self.active_movements.items():
            elapsed = time.time() - movement.start_time
            progress = min(elapsed / movement.duration, 1.0)
            
            movements.append({
                'movement_id': movement_id,
                'operation': movement.operation,
                'status': movement.status,
                'progress': progress
            })
        
        return {
            'success': True,
            'active_movements': movements,
            'count': len(movements)
        }