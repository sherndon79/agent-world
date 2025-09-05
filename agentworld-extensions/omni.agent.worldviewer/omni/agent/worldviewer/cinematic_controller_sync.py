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
from collections import deque
from enum import Enum

import omni.usd
import omni.kit.app
from omni.kit.viewport.utility import get_active_viewport_window
from pxr import Gf, UsdGeom

# Import duration calculation utilities
from .cinematic.duration_calculator import calculate_distance, calculate_duration, validate_speed_parameters

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
    MAX_QUEUE_SIZE = 10  # Maximum number of movements (1 active + 9 queued)
    MOVEMENT_TRANSITION_DELAY = 0.2  # Small delay between movements for capture sync
    
    def __init__(self, camera_controller: CameraController):
        self.camera_controller = camera_controller
        
        # Sequential queuing system - only one movement active at a time
        self.active_movement = None  # Single active movement
        self.movement_queue = deque()  # Queue of pending movements
        self.movement_timer = None
        self.fps = self.DEFAULT_FPS
        self.frame_duration = 1.0 / self.fps  # Time per frame in seconds
        
        # Queue control state
        self._queue_state = 'idle'  # idle, running, paused, stopped
        self._paused_movement = None  # Store paused movement for resume
        
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
        """Update the single active movement (sequential processing)"""
        if not self.active_movement:
            return  # No active movement
            
        current_time = time.time()
        movement = self.active_movement
        
        try:
            # Check if movement is complete
            elapsed = current_time - movement.start_time
            if elapsed >= movement.duration:
                # Complete the movement with final frame
                self._apply_final_frame(movement)
                logger.info(f"Completed cinematic movement: {movement.movement_id}")
                
                # Clear active movement and start next queued movement
                self.active_movement = None
                self._start_next_queued_movement()
                return
            
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
            logger.error(f"Error updating movement {movement.movement_id}: {e}")
            # Clear failed movement and try next in queue
            self.active_movement = None
            self._start_next_queued_movement()
    
    def _apply_final_frame(self, movement: MovementState):
        """Apply the final frame of a movement"""
        if movement.keyframes:
            final_frame = movement.keyframes[-1]
            self.camera_controller.set_position(
                final_frame['position'],
                final_frame.get('target')
            )
    
    def _start_next_queued_movement(self):
        """Start the next movement in the queue with smooth transition"""
        if not self.movement_queue:
            # No queued movements - set state appropriately
            if self._queue_state == 'running':
                self._queue_state = 'idle'
            return
        
        # Don't start next movement if queue is stopped
        if self._queue_state == 'stopped':
            logger.info(f"Queue is stopped, not starting next movement")
            return
        
        # If queue is paused but next movement is auto, we should transition to running
        # This handles the case where auto movements follow manual movements
        
        # Get next movement from queue
        next_movement_data = self.movement_queue.popleft()
        movement_id, operation, params = next_movement_data
        
        # Check execution mode
        execution_mode = params.get('execution_mode', 'auto')
        
        if execution_mode == 'manual':
            # Put movement back at front of queue and wait for manual play
            self.movement_queue.appendleft((movement_id, operation, params))
            logger.info(f"Next movement {movement_id} is in manual mode - waiting for play command")
            self._queue_state = 'paused'  # Set to paused to wait for manual play
            return
        elif self._queue_state == 'paused':
            # If we're paused but next movement is auto, transition to running
            # This happens when auto movements follow manual movements
            logger.info(f"Transitioning from paused to running for auto movement {movement_id}")
            self._queue_state = 'running'
        
        # Add smooth transition from current camera position if needed
        params = self._add_smooth_transition(params)
        
        # Start the movement immediately (auto mode)
        self._start_movement_immediately(movement_id, operation, params)
    
    def _add_smooth_transition(self, params: Dict) -> Dict:
        """Add smooth transition from current camera position to movement start"""
        try:
            # Get current camera status
            current_status = self.camera_controller.get_status()
            if not current_status.get('connected') or not current_status.get('position'):
                return params  # Can't get current position, proceed without transition
            
            current_pos = current_status['position']
            current_target = current_status.get('target')
            
            # If the movement has a start_position, ensure smooth transition
            if 'start_position' in params:
                start_pos = params['start_position']
                
                # Calculate distance to see if transition is needed
                import math
                distance = math.sqrt(sum((a - b) ** 2 for a, b in zip(current_pos, start_pos)))
                
                # If camera is far from start position, update start position to current position
                if distance > 1.0:  # Threshold for smooth transition
                    logger.info(f"Adding smooth transition from {current_pos} to {start_pos}")
                    params = params.copy()
                    params['start_position'] = current_pos
                    if current_target:
                        params['start_target'] = current_target
            
            return params
            
        except Exception as e:
            logger.warning(f"Failed to add smooth transition: {e}")
            return params
    
    def start_movement(self, movement_id: str, operation: str, params: Dict):
        """Start a new cinematic movement (sequential queuing system)"""
        try:
            # Validate duration/speed parameters 
            duration = params.get('duration')
            speed = params.get('speed')
            
            # If neither duration nor speed provided, use default duration
            if duration is None and speed is None:
                duration = 3.0
                params['duration'] = duration
            
            # If duration is provided, validate it
            if duration is not None:
                if not (self.MIN_DURATION <= duration <= self.MAX_DURATION):
                    raise ValueError(f"Duration must be between {self.MIN_DURATION} and {self.MAX_DURATION} seconds")
            
            # Check if queue is stopped
            if self._queue_state == 'stopped':
                # Reset to idle when new movements are added to stopped queue
                self._queue_state = 'idle'
            
            # Check queue capacity (prevent infinite queueing)
            total_queued = len(self.movement_queue) + (1 if self.active_movement else 0)
            if total_queued >= self.MAX_QUEUE_SIZE:
                raise ValueError(f"Movement queue full ({total_queued}/{self.MAX_QUEUE_SIZE}). Too many movements queued. Use 'stop_movement' API to cancel queued movements.")
            
            # Get execution mode (auto by default)
            execution_mode = params.get('execution_mode', 'auto')
            
            # Manual movements are always queued and require explicit play command
            if execution_mode == 'manual':
                logger.info(f"Queueing manual movement: {movement_id} ({operation}). Position in queue: {len(self.movement_queue) + 1}")
                self.movement_queue.append((movement_id, operation, params))
                
                # If queue was idle, set to running but manual movements will pause queue
                if self._queue_state == 'idle':
                    self._queue_state = 'running'
                    
            # Auto movements: start immediately only if no active movement, no queue, and not paused/stopped
            elif self.active_movement is None and len(self.movement_queue) == 0 and self._queue_state not in ['paused', 'stopped']:
                logger.info(f"Starting movement immediately: {movement_id} ({operation}) - auto mode")
                self._queue_state = 'running'
                self._start_movement_immediately(movement_id, operation, params)
            else:
                # Queue auto movement for later
                logger.info(f"Queueing auto movement: {movement_id} ({operation}). Position in queue: {len(self.movement_queue) + 1}")
                self.movement_queue.append((movement_id, operation, params))
                
                # If queue was idle, set to running
                if self._queue_state == 'idle':
                    self._queue_state = 'running'
            
        except Exception as e:
            logger.error(f"Failed to start movement {movement_id}: {e}")
            raise  # Re-raise for API error handling
    
    def _start_movement_immediately(self, movement_id: str, operation: str, params: Dict):
        """Start a movement immediately (no queue checks)"""
        try:
            # Generate keyframes based on operation type
            if operation == 'smooth_move':
                keyframes = self._generate_smooth_move_keyframes(params)
            elif operation == 'orbit_shot':
                keyframes = self._generate_orbit_shot_keyframes(params)
            elif operation == 'arc_shot':
                keyframes = self._generate_arc_shot_keyframes(params)
            else:
                raise ValueError(f"Unknown operation: {operation}. Supported operations: 'smooth_move', 'orbit_shot', 'arc_shot'")
            
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
            
            # Set as the single active movement
            self.active_movement = movement
            logger.info(f"Started cinematic movement: {movement_id} ({operation})")
            
        except Exception as e:
            logger.error(f"Failed to start movement immediately {movement_id}: {e}")
            raise
    
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
        
        # Calculate duration using speed-based calculation if speed provided
        speed = params.get('speed')
        duration = params.get('duration')
        if speed is not None or duration is None:
            # Use speed-based calculation
            duration = calculate_duration(start_pos, end_pos, speed, duration)
            # Update params with calculated duration for MovementState
            params['duration'] = duration
        else:
            # Use provided duration or default
            duration = duration or 3.0
            params['duration'] = duration
            
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
        
        # Calculate duration using speed-based calculation if speed provided
        speed = params.get('speed')
        duration = params.get('duration')
        if speed is not None or duration is None:
            # Use speed-based calculation (arc shots default to slightly slower)
            duration = calculate_duration(start_pos, end_pos, speed or 8.0, duration)
            # Update params with calculated duration for MovementState
            params['duration'] = duration
        else:
            duration = float(duration or 6.0)
            params['duration'] = duration
            
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
    
    def stop_movement(self) -> Dict:
        """Stop all camera movement and return current position details"""
        stopped_count = 0
        stopped_movement_id = None
        
        # Get current camera position before stopping
        current_position = None
        current_target = None
        try:
            camera_status = self.camera_controller.get_status()
            if camera_status.get('connected'):
                current_position = camera_status.get('position')
                current_target = camera_status.get('target')
        except Exception as e:
            logger.warning(f"Could not get current camera position: {e}")
        
        # Stop active movement
        if self.active_movement:
            stopped_movement_id = self.active_movement.movement_id
            operation = self.active_movement.operation
            progress = 0.0
            
            # Calculate progress if possible
            try:
                elapsed = time.time() - self.active_movement.start_time
                progress = min(elapsed / self.active_movement.duration, 1.0)
            except:
                pass
            
            logger.info(f"Stopping active movement: {stopped_movement_id} ({operation}) at {progress*100:.1f}% progress")
            self.active_movement = None
            stopped_count += 1
        
        # Clear entire queue
        if self.movement_queue:
            queue_count = len(self.movement_queue)
            logger.info(f"Clearing entire queue: {queue_count} movements")
            self.movement_queue.clear()
            stopped_count += queue_count
        
        # Build response with position details
        response = {
            'success': True,
            'stopped_count': stopped_count,
            'message': f'Stopped all camera movement. Total stopped: {stopped_count} movements.'
        }
        
        # Add position information if available
        if current_position:
            response['stopped_at_position'] = current_position
        if current_target:
            response['stopped_at_target'] = current_target
        
        # Add interrupted movement details if there was one
        if stopped_movement_id:
            response['interrupted_movement_id'] = stopped_movement_id
            response['interrupted_operation'] = operation
            response['progress_when_stopped'] = f"{progress*100:.1f}%"
            response['message'] += f' Interrupted {operation} movement {stopped_movement_id} at {progress*100:.1f}% completion.'
        
        if stopped_count > 0:
            logger.info(f"Camera stopped at position {current_position}, looking at {current_target}")
        else:
            response['message'] = 'No active movements to stop. Camera already idle.'
        
        return response
    
    # Removed stop_all_movements() - stop_movement() now handles everything
    
    def get_movement_status(self, movement_id: str) -> Dict:
        """Get status of an active or queued movement"""
        # Check active movement
        if self.active_movement and self.active_movement.movement_id == movement_id:
            movement = self.active_movement
            elapsed = time.time() - movement.start_time
            progress = min(elapsed / movement.duration, 1.0)
            
            return {
                'success': True,
                'movement_id': movement_id,
                'operation': movement.operation,
                'status': 'active',
                'progress': progress,
                'elapsed_time': elapsed,
                'total_duration': movement.duration,
                'queue_position': 0  # Active movement is position 0
            }
        
        # Check queued movements
        for i, (queued_id, operation, params) in enumerate(self.movement_queue):
            if queued_id == movement_id:
                return {
                    'success': True,
                    'movement_id': movement_id,
                    'operation': operation,
                    'status': 'queued',
                    'progress': 0.0,
                    'elapsed_time': 0.0,
                    'total_duration': params.get('duration', 3.0),
                    'queue_position': i + 1  # Queue position (1-indexed)
                }
        
        return {'success': False, 'error': f'Movement {movement_id} not found'}
    
    def list_active_movements(self) -> Dict:
        """List active movement and queued movements"""
        movements = []
        
        # Add active movement
        if self.active_movement:
            elapsed = time.time() - self.active_movement.start_time
            progress = min(elapsed / self.active_movement.duration, 1.0)
            
            movements.append({
                'movement_id': self.active_movement.movement_id,
                'operation': self.active_movement.operation,
                'status': 'active',
                'progress': progress,
                'queue_position': 0
            })
        
        # Add queued movements
        for i, (movement_id, operation, params) in enumerate(self.movement_queue):
            movements.append({
                'movement_id': movement_id,
                'operation': operation,
                'status': 'queued',
                'progress': 0.0,
                'queue_position': i + 1
            })
        
        return {
            'success': True,
            'movements': movements,  # Changed from 'active_movements' to 'movements'
            'active_count': 1 if self.active_movement else 0,
            'queued_count': len(self.movement_queue),
            'total_count': len(movements)
        }
    
    def get_queue_status(self) -> Dict:
        """Get comprehensive queue status with timing information"""
        try:
            # Get actual queue state
            queue_state = self._get_actual_queue_state()
            
            # Initialize response
            response = {
                'success': True,
                'queue_state': queue_state,
                'timestamp': time.time()
            }
            
            # Get active shot info
            active_shot = None
            if self.active_movement:
                elapsed = time.time() - self.active_movement.start_time
                progress = min(elapsed / self.active_movement.duration, 1.0)
                remaining_time = max(0, self.active_movement.duration - elapsed)
                
                active_shot = {
                    'movement_id': self.active_movement.movement_id,
                    'operation': self.active_movement.operation,
                    'progress': progress,
                    'remaining_time': remaining_time,
                    'total_duration': self.active_movement.duration,
                    'execution': self.active_movement.params.get('execution', 'auto')
                }
            
            response['active_shot'] = active_shot
            
            # Get queued shots info
            queued_shots = []
            estimated_start_time = active_shot['remaining_time'] if active_shot else 0
            
            for i, (movement_id, operation, params) in enumerate(self.movement_queue):
                # Calculate duration for display (same logic as movement generation)
                if 'start_position' in params and 'end_position' in params:
                    start_pos = params['start_position']
                    end_pos = params['end_position']
                    speed = params.get('speed')
                    duration = params.get('duration')
                    if speed is not None or duration is None:
                        duration = calculate_duration(start_pos, end_pos, speed, duration)
                    else:
                        duration = duration or 3.0
                else:
                    duration = params.get('duration', 3.0)
                
                shot_info = {
                    'movement_id': movement_id,
                    'operation': operation,
                    'estimated_duration': duration,
                    'estimated_start_time': estimated_start_time,
                    'queue_position': i + 1,
                    'execution': params.get('execution_mode', 'auto'),
                    'params': params  # Include full parameters for UI display
                }
                
                queued_shots.append(shot_info)
                estimated_start_time += duration
            
            response['queued_shots'] = queued_shots
            
            # Calculate totals
            active_duration = active_shot['total_duration'] if active_shot else 0
            queued_duration = sum(shot['estimated_duration'] for shot in queued_shots)
            remaining_active = active_shot['remaining_time'] if active_shot else 0
            
            response.update({
                'total_duration': active_duration + queued_duration,
                'remaining_duration': remaining_active + queued_duration,
                'shot_count': len(queued_shots) + (1 if active_shot else 0),
                'active_count': 1 if active_shot else 0,
                'queued_count': len(queued_shots)
            })
            
            return response
            
        except Exception as e:
            return {'success': False, 'error': str(e)}

    # Queue Control Commands
    def play_queue(self) -> Dict:
        """Start/resume queue processing"""
        try:
            if self._queue_state == 'stopped':
                return {'success': False, 'error': 'Queue is stopped. Cannot play stopped queue.'}
            
            # Check actual current state (not just internal variable)
            actual_state = self._get_actual_queue_state()
            
            if actual_state == 'running':
                return {'success': True, 'message': 'Queue is already running', 'queue_state': 'running'}
            
            # Resume from paused state
            if self._queue_state == 'paused' and self._paused_movement:
                # Resume the paused movement from current position
                paused = self._paused_movement
                
                # Get current camera position for resume
                try:
                    camera_status = self.camera_controller.get_status()
                    current_pos = camera_status.get('position', [0, 0, 0])
                    
                    # Create modified parameters to continue from current position
                    resume_params = paused['params'].copy()
                    resume_params['start_position'] = current_pos
                    
                    # Calculate correct target based on original trajectory progress
                    progress = paused['progress']
                    original_start_target = paused['params'].get('start_target')
                    original_end_target = paused['params'].get('end_target')
                    
                    if original_start_target and original_end_target:
                        # Interpolate target based on progress
                        current_target = [
                            original_start_target[i] + (original_end_target[i] - original_start_target[i]) * progress
                            for i in range(3)
                        ]
                        resume_params['start_target'] = current_target
                    elif original_start_target:
                        resume_params['start_target'] = original_start_target
                    elif original_end_target:
                        resume_params['start_target'] = original_end_target
                    
                    # Adjust duration to remaining time
                    resume_params['duration'] = paused['remaining_time']
                    
                    logger.info(f"Resuming paused movement: {paused['movement_id']} from position {current_pos} with {paused['remaining_time']:.1f}s remaining")
                    self._start_movement_immediately(paused['movement_id'] + "_resumed", paused['operation'], resume_params)
                    self._paused_movement = None
                    
                except Exception as e:
                    logger.error(f"Failed to resume movement: {e}")
                    # Fallback to restart
                    self._start_movement_immediately(paused['movement_id'], paused['operation'], paused['params'])
                    self._paused_movement = None
            
            # Set state to running
            self._queue_state = 'running'
            
            # If we have queued movements but no active movement, check for manual shots
            if not self.active_movement and self.movement_queue:
                # Check if first queued movement is manual
                next_movement_data = self.movement_queue[0]  # Peek at next movement
                movement_id, operation, params = next_movement_data
                execution_mode = params.get('execution_mode', 'auto')
                
                if execution_mode == 'manual':
                    # Start the manual movement immediately when play is pressed
                    self.movement_queue.popleft()  # Remove from queue
                    logger.info(f"Starting manual movement via play command: {movement_id} ({operation})")
                    self._start_movement_immediately(movement_id, operation, params)
                else:
                    # Start auto movements normally
                    self._start_next_queued_movement()
            
            return {
                'success': True,
                'message': 'Queue resumed/started',
                'queue_state': self._queue_state,
                'active_count': 1 if self.active_movement else 0,
                'queued_count': len(self.movement_queue)
            }
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def pause_queue(self) -> Dict:
        """Pause queue processing (stops current movement and prevents new ones)"""
        try:
            if self._queue_state == 'stopped':
                return {'success': False, 'error': 'Queue is stopped. Cannot pause stopped queue.'}
                
            if self._queue_state == 'paused':
                return {'success': True, 'message': 'Queue is already paused', 'queue_state': 'paused'}
            
            # Store current movement state for resume
            paused_movement = None
            if self.active_movement:
                # Calculate current progress
                elapsed = time.time() - self.active_movement.start_time
                progress = min(elapsed / self.active_movement.duration, 1.0)
                
                # Store paused movement info for resume
                paused_movement = {
                    'movement_id': self.active_movement.movement_id,
                    'operation': self.active_movement.operation,
                    'params': self.active_movement.params,
                    'progress': progress,
                    'remaining_time': max(0, self.active_movement.duration - elapsed)
                }
                
                # Clear active movement (stops the camera)
                self.active_movement = None
                logger.info(f"Paused movement at {progress*100:.1f}% progress")
            
            # Set queue state to paused
            self._queue_state = 'paused'
            self._paused_movement = paused_movement  # Store for resume
            
            return {
                'success': True,
                'message': 'Queue paused. Camera movement stopped.',
                'queue_state': self._queue_state,
                'active_count': 0,  # No active movement when paused
                'queued_count': len(self.movement_queue),
                'paused_progress': f"{paused_movement['progress']*100:.1f}%" if paused_movement else None
            }
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def stop_queue(self) -> Dict:
        """Stop and clear entire queue"""
        try:
            # Stop current movement
            stop_result = self.stop_movement()
            
            # Set queue state to stopped
            self._queue_state = 'stopped'
            
            return {
                'success': True,
                'message': 'Queue stopped and cleared',
                'queue_state': self._queue_state,
                'stopped_movements': stop_result.get('stopped_count', 0),
                'active_count': 0,
                'queued_count': 0
            }
            
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def _get_actual_queue_state(self) -> str:
        """Get the actual current queue state based on conditions"""
        if self._queue_state == 'stopped':
            return 'stopped'
        elif self._queue_state == 'paused':
            return 'paused'
        elif self.active_movement is not None:
            return 'running'  # Has active movement
        elif self.movement_queue:
            # Check if next movement is manual
            next_movement_data = self.movement_queue[0]
            movement_id, operation, params = next_movement_data
            execution_mode = params.get('execution_mode', 'auto')
            if execution_mode == 'manual':
                return 'pending'  # Manual shot waiting for play command
            else:
                return 'running'  # Auto shots in queue
        else:
            return 'idle'     # Empty queue, ready for work