"""
Smooth move keyframe generator for linear camera movements.

This generator creates keyframes for smooth linear movements between two positions,
with optional target interpolation and rotation-based targeting. Supports various
easing functions for natural motion curves.
"""

import logging
from typing import Dict, List
from .base_generator import BaseKeyframeGenerator
from ..style_registry import rotation_to_target


logger = logging.getLogger(__name__)


class SmoothMoveGenerator(BaseKeyframeGenerator):
    """Generate keyframes for smooth linear movements"""
    
    def generate_keyframes(self, params: Dict) -> List[Dict]:
        """
        Generate keyframes for smooth movement between two positions.
        
        Args:
            params: Dictionary containing:
                - start_position: Starting camera position [x, y, z] (required)
                - end_position: Ending camera position [x, y, z] (required)
                - start_target: Starting look-at target [x, y, z] (optional)
                - end_target: Ending look-at target [x, y, z] (optional)
                - start_rotation: Starting rotation [pitch, yaw, roll] (optional, overrides start_target)
                - end_rotation: Ending rotation [pitch, yaw, roll] (optional, overrides end_target)
                - duration: Movement duration in seconds (optional, calculated from speed if not provided)
                - speed: Movement speed in units/second (optional, used if duration not provided)
                - easing_type: Easing function type (optional, default 'ease_in_out')
                - fps: Frames per second for keyframe generation (optional, default 30)
                
        Returns:
            List of keyframe dictionaries with position, target, and timing information
            
        Raises:
            ValueError: If required parameters are missing or invalid
        """
        try:
            # Validate parameters using base class
            validated_params = self.validate_params(params)
            
            # Extract required parameters
            start_pos = validated_params['start_position']
            end_pos = validated_params['end_position']
            
            # Get timing parameters
            duration = self.calculate_movement_duration(validated_params)
            easing_type = validated_params['easing_type']
            fps = validated_params['fps']
            
            # Handle target calculation
            start_target, end_target = self._calculate_targets(validated_params, start_pos, end_pos)
            
            # Generate keyframes
            num_frames = self.calculate_frame_count(duration, fps)
            keyframes = []
            
            for i in range(num_frames + 1):
                t = i / max(1, num_frames)  # Avoid division by zero
                eased_t = self.apply_easing(t, easing_type)
                
                # Interpolate position
                position = self.interpolate_position(start_pos, end_pos, eased_t)
                
                # Interpolate target
                target = self.interpolate_position(start_target, end_target, eased_t)
                
                # Create keyframe
                keyframe = self.create_keyframe(
                    position=position,
                    target=target,
                    frame_index=i,
                    total_frames=num_frames + 1,
                    timestamp=t * duration,
                    easing_progress=eased_t
                )
                
                keyframes.append(keyframe)
            
            logger.debug(f"Generated {len(keyframes)} smooth move keyframes over {duration:.1f}s")
            return keyframes
            
        except Exception as e:
            logger.error(f"Error generating smooth move keyframes: {e}")
            raise
    
    def _calculate_targets(self, params: Dict, start_pos: List[float], end_pos: List[float]) -> tuple:
        """
        Calculate start and end targets for camera look-at.
        
        Handles rotation data (preferred) or explicit target points.
        Falls back to sensible defaults if neither is provided.
        
        Args:
            params: Validated parameters
            start_pos: Starting position
            end_pos: Ending position
            
        Returns:
            Tuple of (start_target, end_target) as [x, y, z] lists
        """
        start_target = None
        end_target = None
        
        # Handle rotation data (preferred over target points)
        if 'start_rotation' in params:
            start_rotation = self._validate_rotation(params['start_rotation'])
            start_target = rotation_to_target(start_pos, start_rotation)
            logger.debug(f"Calculated start_target from rotation: {start_target}")
        elif 'start_target' in params:
            start_target = params['start_target']
        else:
            # Try to get current target from camera controller
            start_target = self._get_current_target_or_default(start_pos)
        
        if 'end_rotation' in params:
            end_rotation = self._validate_rotation(params['end_rotation'])
            end_target = rotation_to_target(end_pos, end_rotation)
            logger.debug(f"Calculated end_target from rotation: {end_target}")
        elif 'end_target' in params:
            end_target = params['end_target']
        else:
            # Default target relative to end position
            end_target = [end_pos[0], end_pos[1], end_pos[2] - 10]
        
        return start_target, end_target
    
    def _validate_rotation(self, rotation) -> List[float]:
        """Validate rotation parameter format"""
        if not isinstance(rotation, (list, tuple)) or len(rotation) != 3:
            raise ValueError("Rotation must be [pitch, yaw, roll] list with 3 values")
        
        try:
            return [float(x) for x in rotation]
        except (ValueError, TypeError):
            raise ValueError("Rotation values must be numeric")
    
    def _get_current_target_or_default(self, position: List[float]) -> List[float]:
        """Get current camera target or return sensible default"""
        try:
            if self.camera_controller:
                current_status = self.camera_controller.get_status()
                if current_status.get('connected') and current_status.get('target'):
                    return current_status['target']
        except Exception as e:
            logger.debug(f"Could not get current camera target: {e}")
        
        # Default: look 10 units in front of camera (negative Z)
        return [position[0], position[1], position[2] - 10]
    
    def validate_params(self, params: Dict) -> Dict:
        """
        Validate smooth move specific parameters.
        
        Extends base validation with smooth move requirements.
        """
        # First run base validation
        validated = super().validate_params(params)
        
        # Check required parameters
        if 'start_position' not in params:
            raise ValueError("start_position is required for smooth move")
        if 'end_position' not in params:
            raise ValueError("end_position is required for smooth move")
        
        # Validate positions were handled by base class _validate_position
        
        # Validate optional targets
        if 'start_target' in params:
            validated['start_target'] = self._validate_position(params['start_target'])
        if 'end_target' in params:
            validated['end_target'] = self._validate_position(params['end_target'])
            
        # Validate optional rotations
        if 'start_rotation' in params:
            validated['start_rotation'] = self._validate_rotation(params['start_rotation'])
        if 'end_rotation' in params:
            validated['end_rotation'] = self._validate_rotation(params['end_rotation'])
        
        return validated