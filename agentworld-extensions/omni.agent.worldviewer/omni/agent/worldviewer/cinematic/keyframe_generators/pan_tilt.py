"""
Pan/Tilt keyframe generator for rotation-based camera movements.

This generator creates keyframes for pan and tilt movements using either
position-based keyframes or traditional azimuth/elevation control.
Supports both modern keyframe-based control and legacy rotation parameters.
"""

import logging
from typing import Dict, List
from .base_generator import BaseKeyframeGenerator


logger = logging.getLogger(__name__)


class PanTiltGenerator(BaseKeyframeGenerator):
    """Generate keyframes for pan/tilt rotation movements"""
    
    def generate_keyframes(self, params: Dict) -> List[Dict]:
        """
        Generate keyframes for pan/tilt movement.
        
        Supports two modes:
        1. Keyframe mode: Uses start_position/end_position for modern control
        2. Rotation mode: Uses azimuth/elevation angles for traditional control
        
        Args:
            params: Dictionary containing:
                Keyframe mode:
                - start_position: Starting camera position [x, y, z] (required for keyframe mode)
                - end_position: Ending camera position [x, y, z] (required for keyframe mode)
                - start_target: Starting look-at target [x, y, z] (optional)
                - end_target: Ending look-at target [x, y, z] (optional)
                - duration: Movement duration in seconds (optional, default 6.0)
                - easing_type: Easing function type (optional, default 'ease_in_out')
                
                Rotation mode:
                - start_azimuth: Starting azimuth angle in degrees (required for rotation mode)
                - end_azimuth: Ending azimuth angle in degrees (required for rotation mode)
                - start_elevation: Starting elevation angle in degrees (optional)
                - end_elevation: Ending elevation angle in degrees (optional)
                - distance: Distance from orbit center (optional, default 10.0)
                - duration: Movement duration in seconds (optional, default 6.0)
                
                - fps: Frames per second for keyframe generation (optional, default 30)
                
        Returns:
            List of keyframe dictionaries for pan/tilt movement
            
        Raises:
            ValueError: If required parameters are missing or invalid
        """
        try:
            # Validate parameters using base class
            validated_params = self.validate_params(params)
            
            # Determine which mode to use
            if self._is_keyframe_mode(validated_params):
                return self._generate_keyframe_pan_tilt(validated_params)
            else:
                return self._generate_rotation_pan_tilt(validated_params)
                
        except Exception as e:
            logger.error(f"Error generating pan/tilt keyframes: {e}")
            raise
    
    def _is_keyframe_mode(self, params: Dict) -> bool:
        """Check if parameters indicate keyframe mode"""
        return 'start_position' in params and 'end_position' in params
    
    def _generate_keyframe_pan_tilt(self, params: Dict) -> List[Dict]:
        """Generate keyframes using position-based keyframe mode"""
        start_pos = params['start_position']
        end_pos = params['end_position']
        start_target = params.get('start_target')
        end_target = params.get('end_target')
        duration = params.get('duration', 6.0)
        easing_type = params.get('easing_type', 'ease_in_out')
        fps = params['fps']
        
        # Generate keyframes using smooth linear interpolation
        num_frames = self.calculate_frame_count(duration, fps)
        keyframes = []
        
        for i in range(num_frames + 1):
            t = i / max(1, num_frames)  # Avoid division by zero
            eased_t = self.apply_easing(t, easing_type)
            
            # Interpolate position
            position = self.interpolate_position(start_pos, end_pos, eased_t)
            
            # Interpolate target if both provided
            if start_target and end_target:
                target = self.interpolate_position(start_target, end_target, eased_t)
            elif start_target:
                target = start_target
            elif end_target:
                target = end_target
            else:
                # Default target behavior
                target = self._calculate_default_target(position)
            
            # Create keyframe with pan/tilt specific data
            keyframe = self.create_keyframe(
                position=position,
                target=target,
                frame_index=i,
                total_frames=num_frames + 1,
                timestamp=t * duration,
                pan_tilt_progress=eased_t
            )
            
            keyframes.append(keyframe)
        
        logger.debug(f"Generated {len(keyframes)} keyframe pan/tilt keyframes over {duration:.1f}s")
        return keyframes
    
    def _generate_rotation_pan_tilt(self, params: Dict) -> List[Dict]:
        """Generate keyframes using traditional azimuth/elevation rotation mode"""
        import math
        
        start_azimuth = math.radians(params['start_azimuth'])
        end_azimuth = math.radians(params['end_azimuth'])
        start_elevation = math.radians(params.get('start_elevation', 0.0))
        end_elevation = math.radians(params.get('end_elevation', 0.0))
        distance = params.get('distance', 10.0)
        duration = params.get('duration', 6.0)
        fps = params['fps']
        
        # Calculate average elevation for orbital movement
        avg_elevation = (start_elevation + end_elevation) / 2
        
        # Generate orbital keyframes using the orbit generator approach
        num_frames = self.calculate_frame_count(duration, fps)
        keyframes = []
        
        for i in range(num_frames + 1):
            t = i / max(1, num_frames)  # Avoid division by zero
            
            # Linear interpolation for rotation parameters
            current_azimuth = start_azimuth + (end_azimuth - start_azimuth) * t
            current_elevation = start_elevation + (end_elevation - start_elevation) * t
            
            # Calculate position from spherical coordinates
            x = distance * math.cos(current_elevation) * math.cos(current_azimuth)
            y = distance * math.cos(current_elevation) * math.sin(current_azimuth)
            z = distance * math.sin(current_elevation)
            
            # Target is always the origin for traditional pan/tilt
            target = [0, 0, 0]
            
            # Create keyframe with rotation-specific data
            keyframe = self.create_keyframe(
                position=[x, y, z],
                target=target,
                frame_index=i,
                total_frames=num_frames + 1,
                timestamp=t * duration,
                azimuth_degrees=math.degrees(current_azimuth),
                elevation_degrees=math.degrees(current_elevation)
            )
            
            keyframes.append(keyframe)
        
        logger.debug(f"Generated {len(keyframes)} rotation pan/tilt keyframes over {duration:.1f}s")
        return keyframes
    
    def _calculate_default_target(self, position: List[float]) -> List[float]:
        """Calculate default target for pan/tilt movement"""
        # Default: look 10 units in front of camera (negative Z direction)
        return [position[0], position[1], position[2] - 10]
    
    def validate_params(self, params: Dict) -> Dict:
        """
        Validate pan/tilt specific parameters.
        
        Supports both keyframe and rotation parameter modes.
        """
        # First run base validation
        validated = super().validate_params(params)
        
        # Determine mode and validate accordingly
        has_positions = 'start_position' in params and 'end_position' in params
        has_rotations = 'start_azimuth' in params and 'end_azimuth' in params
        
        if not has_positions and not has_rotations:
            raise ValueError(
                "Pan/tilt requires either (start_position, end_position) for keyframe mode "
                "or (start_azimuth, end_azimuth) for rotation mode"
            )
        
        # Keyframe mode validation
        if has_positions:
            # Positions already validated by base class
            
            # Validate optional targets
            if 'start_target' in params:
                validated['start_target'] = self._validate_position(params['start_target'])
            if 'end_target' in params:
                validated['end_target'] = self._validate_position(params['end_target'])
            
            # Validate easing type
            if 'easing_type' in params:
                validated['easing_type'] = str(params['easing_type'])
            else:
                validated['easing_type'] = 'ease_in_out'
        
        # Rotation mode validation
        if has_rotations:
            validated['start_azimuth'] = float(params['start_azimuth'])
            validated['end_azimuth'] = float(params['end_azimuth'])
            
            if 'start_elevation' in params:
                validated['start_elevation'] = float(params['start_elevation'])
            if 'end_elevation' in params:
                validated['end_elevation'] = float(params['end_elevation'])
            
            if 'distance' in params:
                distance = float(params['distance'])
                if distance <= 0:
                    raise ValueError("Distance must be positive for rotation mode")
                validated['distance'] = distance
        
        return validated