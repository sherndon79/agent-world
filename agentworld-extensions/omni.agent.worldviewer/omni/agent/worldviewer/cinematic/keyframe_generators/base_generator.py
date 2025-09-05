"""
Base keyframe generator for WorldViewer cinematic camera movements.

This module provides the abstract base class and common functionality
for all keyframe generators. Each shot type inherits from BaseKeyframeGenerator
and implements the generate_keyframes method.
"""

import logging
import math
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Callable, Any

# Import from parent cinematic package
from ..movement_state import EasingType
from ..easing import EasingFunctions, get_easing_function
from ..style_registry import get_style_config, validate_style_params
from ..duration_calculator import calculate_distance, calculate_duration


logger = logging.getLogger(__name__)


class BaseKeyframeGenerator(ABC):
    """Abstract base class for all keyframe generators"""
    
    def __init__(self, camera_controller=None):
        """
        Initialize keyframe generator.
        
        Args:
            camera_controller: Camera controller instance for status queries
        """
        self.camera_controller = camera_controller
        self.logger = logging.getLogger(self.__class__.__name__)
        
    @abstractmethod
    def generate_keyframes(self, params: Dict) -> List[Dict]:
        """
        Generate keyframes for this shot type.
        
        Args:
            params: Shot parameters including positions, timing, easing, etc.
            
        Returns:
            List of keyframe dictionaries with position, target, timing info
        """
        pass
    
    def validate_params(self, params: Dict) -> Dict:
        """
        Validate and normalize parameters for keyframe generation.
        
        Args:
            params: Input parameters
            
        Returns:
            Validated and normalized parameters
            
        Raises:
            ValueError: If required parameters are missing or invalid
        """
        validated = dict(params)
        
        # Validate required position parameters
        if 'start_position' in params:
            validated['start_position'] = self._validate_position(params['start_position'])
        if 'end_position' in params:
            validated['end_position'] = self._validate_position(params['end_position'])
        if 'start_target' in params:
            validated['start_target'] = self._validate_position(params['start_target'])
        if 'end_target' in params:
            validated['end_target'] = self._validate_position(params['end_target'])
            
        # Validate timing parameters
        if 'duration' in params:
            duration = float(params['duration'])
            if duration <= 0:
                raise ValueError(f"Duration must be positive, got: {duration}")
            validated['duration'] = duration
            
        if 'speed' in params:
            speed = float(params['speed'])
            if speed <= 0:
                raise ValueError(f"Speed must be positive, got: {speed}")
            validated['speed'] = speed
            
        # Validate easing type
        if 'easing_type' in params:
            easing_str = params['easing_type']
            try:
                EasingType(easing_str)  # Validate it's a valid enum value
                validated['easing_type'] = easing_str
            except ValueError:
                self.logger.warning(f"Invalid easing type: {easing_str}, using ease_in_out")
                validated['easing_type'] = 'ease_in_out'
        else:
            validated['easing_type'] = 'ease_in_out'  # Default
            
        # Validate FPS
        if 'fps' in params:
            fps = float(params['fps'])
            if fps <= 0 or fps > 120:
                raise ValueError(f"FPS must be between 0 and 120, got: {fps}")
            validated['fps'] = fps
        else:
            validated['fps'] = 30.0  # Default
            
        return validated
    
    def apply_style_config(self, params: Dict, shot_type: str) -> Dict:
        """
        Apply style configuration to parameters.
        
        Args:
            params: Base parameters
            shot_type: Shot type for style lookup
            
        Returns:
            Parameters with style configuration applied
        """
        try:
            style_name = params.get('style', 'standard')
            styled_params = validate_style_params(shot_type, style_name, params)
            return styled_params
        except Exception as e:
            self.logger.warning(f"Error applying style config: {e}")
            return params
    
    def calculate_frame_count(self, duration: float, fps: float = 30.0) -> int:
        """Calculate number of frames for duration"""
        return max(1, int(duration * fps))
    
    def interpolate_position(self, start: List[float], end: List[float], t: float) -> List[float]:
        """
        Interpolate between two positions.
        
        Args:
            start: Starting position [x, y, z]
            end: Ending position [x, y, z]
            t: Interpolation factor (0.0 to 1.0)
            
        Returns:
            Interpolated position [x, y, z]
        """
        return [
            start[i] + (end[i] - start[i]) * t
            for i in range(len(start))
        ]
    
    def apply_easing(self, t: float, easing_type: str) -> float:
        """
        Apply easing function to time parameter.
        
        Args:
            t: Time parameter (0.0 to 1.0)
            easing_type: Type of easing function
            
        Returns:
            Eased time value
        """
        try:
            easing_enum = EasingType(easing_type)
            easing_func = get_easing_function(easing_enum)
            return easing_func(t)
        except (ValueError, KeyError):
            self.logger.warning(f"Unknown easing type: {easing_type}, using linear")
            return t
    
    def calculate_movement_duration(self, params: Dict) -> float:
        """
        Calculate movement duration based on parameters.
        
        Args:
            params: Parameters with duration, speed, or position info
            
        Returns:
            Duration in seconds
        """
        # Explicit duration takes precedence
        if 'duration' in params:
            return float(params['duration'])
        
        # Calculate from speed and distance
        if 'start_position' in params and 'end_position' in params:
            start_pos = params['start_position']
            end_pos = params['end_position']
            speed = params.get('speed', 5.0)
            
            return calculate_duration(start_pos, end_pos, speed, None)
        
        # Default fallback
        return 3.0
    
    def create_keyframe(self, position: List[float], target: Optional[List[float]] = None, 
                       frame_index: int = 0, total_frames: int = 1, 
                       timestamp: float = 0.0, **kwargs) -> Dict:
        """
        Create a keyframe dictionary with standard format.
        
        Args:
            position: Camera position [x, y, z]
            target: Look-at target [x, y, z] (optional)
            frame_index: Current frame index
            total_frames: Total frames in sequence
            timestamp: Time offset for this frame
            **kwargs: Additional keyframe data
            
        Returns:
            Keyframe dictionary
        """
        keyframe = {
            'position': list(position),
            'frame': frame_index,
            'total_frames': total_frames,
            'progress': frame_index / max(1, total_frames - 1),
            'timestamp': timestamp
        }
        
        if target is not None:
            keyframe['target'] = list(target)
            
        # Add any additional parameters
        keyframe.update(kwargs)
        
        return keyframe
    
    def _validate_position(self, position: Any) -> List[float]:
        """Validate and normalize position parameter"""
        if not isinstance(position, (list, tuple)):
            raise ValueError(f"Position must be a list or tuple, got: {type(position)}")
        
        if len(position) != 3:
            raise ValueError(f"Position must have 3 coordinates, got: {len(position)}")
        
        try:
            return [float(x) for x in position]
        except (ValueError, TypeError) as e:
            raise ValueError(f"Position coordinates must be numeric: {e}")
    
    def _clamp(self, value: float, min_val: float, max_val: float) -> float:
        """Clamp value between min and max"""
        return max(min_val, min(max_val, value))


class KeyframeGeneratorFactory:
    """Factory for creating appropriate keyframe generators"""
    
    def __init__(self, camera_controller=None):
        """
        Initialize factory.
        
        Args:
            camera_controller: Camera controller instance to pass to generators
        """
        self.camera_controller = camera_controller
        self._generators = {}
        self._initialize_generators()
    
    def _initialize_generators(self):
        """Initialize all available generators"""
        # Import generators here to avoid circular imports
        try:
            from .smooth_move import SmoothMoveGenerator
            from .arc_shot import ArcShotGenerator
            from .orbit_shot import OrbitShotGenerator, CinematicOrbitGenerator
            from .dolly_shot import DollyShotGenerator
            from .pan_tilt import PanTiltGenerator
            
            # Register generators
            self._generators = {
                'smooth_move': SmoothMoveGenerator(self.camera_controller),
                'arc_shot': ArcShotGenerator(self.camera_controller),
                'orbit_shot': OrbitShotGenerator(self.camera_controller),
                'cinematic_orbit': CinematicOrbitGenerator(self.camera_controller),
                'dolly_shot': DollyShotGenerator(self.camera_controller),
                'pan_tilt': PanTiltGenerator(self.camera_controller),
            }
            
            logger.info(f"Keyframe generator factory initialized with {len(self._generators)} generators")
            
        except ImportError as e:
            logger.error(f"Failed to import keyframe generators: {e}")
            self._generators = {}
    
    def get_generator(self, operation: str) -> Optional[BaseKeyframeGenerator]:
        """
        Get keyframe generator for operation type.
        
        Args:
            operation: Operation/shot type name
            
        Returns:
            Keyframe generator instance or None if not found
        """
        return self._generators.get(operation)
    
    def generate_keyframes(self, operation: str, params: Dict) -> List[Dict]:
        """
        Generate keyframes using appropriate generator.
        
        Args:
            operation: Operation/shot type name
            params: Parameters for keyframe generation
            
        Returns:
            List of keyframe dictionaries
            
        Raises:
            ValueError: If no generator found for operation
        """
        generator = self.get_generator(operation)
        if generator is None:
            raise ValueError(f"No keyframe generator found for operation: {operation}")
        
        # Validate parameters using the generator
        validated_params = generator.validate_params(params)
        
        # Generate keyframes
        keyframes = generator.generate_keyframes(validated_params)
        
        logger.debug(f"Generated {len(keyframes)} keyframes for {operation}")
        return keyframes
    
    def list_supported_operations(self) -> List[str]:
        """Get list of supported operation types"""
        return list(self._generators.keys())
    
    def is_operation_supported(self, operation: str) -> bool:
        """Check if operation is supported"""
        return operation in self._generators