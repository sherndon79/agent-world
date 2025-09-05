"""
Dolly shot keyframe generator for cinematic push/pull movements.

This generator creates keyframes for dolly movements with style-driven approach curves
and deceleration control. Supports traditional dolly behaviors like slow approaches
and dramatic push-ins.
"""

import logging
import math
from typing import Dict, List
from .base_generator import BaseKeyframeGenerator


logger = logging.getLogger(__name__)


class DollyShotGenerator(BaseKeyframeGenerator):
    """Generate keyframes for cinematic dolly movements"""
    
    def generate_keyframes(self, params: Dict) -> List[Dict]:
        """
        Generate keyframes for dolly shot movement.
        
        Args:
            params: Dictionary containing:
                - start_position: Starting camera position [x, y, z] (required)
                - end_position: Ending camera position [x, y, z] (required)
                - start_target: Starting look-at target [x, y, z] (optional)
                - end_target: Ending look-at target [x, y, z] (optional)
                - duration: Movement duration in seconds (optional, default 5.0)
                - movement_style: Style variant for dolly parameters (optional, default 'standard')
                - fps: Frames per second for keyframe generation (optional, default 30)
                
        Returns:
            List of keyframe dictionaries with dolly movement characteristics
            
        Raises:
            ValueError: If required parameters are missing or invalid
        """
        try:
            # Validate parameters using base class
            validated_params = self.validate_params(params)
            
            # Extract required parameters
            start_pos = validated_params['start_position']
            end_pos = validated_params['end_position']
            start_target = validated_params.get('start_target')
            end_target = validated_params.get('end_target')
            duration = validated_params.get('duration', 5.0)
            movement_style = validated_params.get('movement_style', 'standard')
            fps = validated_params['fps']
            
            # Get style configuration
            style_config = self.apply_style_config(validated_params, 'dolly_shot')
            
            # Calculate movement vector and distance
            move_vector = [end_pos[i] - start_pos[i] for i in range(3)]
            move_distance = math.sqrt(sum(x*x for x in move_vector))
            
            # Generate keyframes with dolly-specific timing
            num_frames = self.calculate_frame_count(duration, fps)
            keyframes = []
            
            for i in range(num_frames + 1):
                t = i / max(1, num_frames)  # Avoid division by zero
                
                # Apply dolly-specific easing with style configuration
                eased_t = self._apply_dolly_easing(t, style_config)
                
                # Interpolate position
                position = [
                    start_pos[0] + move_vector[0] * eased_t,
                    start_pos[1] + move_vector[1] * eased_t,
                    start_pos[2] + move_vector[2] * eased_t
                ]
                
                # Calculate dolly target behavior
                target = self._calculate_dolly_target(
                    start_pos, end_pos, start_target, end_target, eased_t, i, num_frames
                )
                
                # Create keyframe with dolly-specific data
                keyframe = self.create_keyframe(
                    position=position,
                    target=target,
                    frame_index=i,
                    total_frames=num_frames + 1,
                    timestamp=t * duration,
                    dolly_progress=eased_t,
                    move_distance=move_distance
                )
                
                keyframes.append(keyframe)
            
            logger.debug(f"Generated {len(keyframes)} dolly shot keyframes over {duration:.1f}s")
            return keyframes
            
        except Exception as e:
            logger.error(f"Error generating dolly shot keyframes: {e}")
            raise
    
    def _apply_dolly_easing(self, t: float, style_config: Dict) -> float:
        """
        Apply style-driven easing curve for dolly movement.
        
        Supports various approach curves for different dolly styles.
        """
        approach_curve = style_config.get('approach_curve', 'ease_in_out')
        deceleration_factor = style_config.get('deceleration_factor', 0.5)
        
        # Apply primary easing based on approach curve
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
        
        # Apply style-driven deceleration for final approach (last 20% of movement)
        if t > 0.8:
            decel_amount = 1 - (t - 0.8) * deceleration_factor
            eased_t = 0.8 + (eased_t - 0.8) * decel_amount
        
        return eased_t
    
    def _calculate_dolly_target(self, start_pos: List[float], end_pos: List[float],
                              start_target: List[float] = None, end_target: List[float] = None,
                              eased_t: float = 0.0, frame_index: int = 0, 
                              total_frames: int = 1) -> List[float]:
        """
        Calculate target point for dolly shot.
        
        Implements dolly-specific target behavior:
        - If both targets provided: interpolate between them
        - If only one target: maintain focus on that target
        - If no targets: focus on midpoint between positions
        """
        # Ensure exact start and end targets for precise framing
        if start_target and end_target:
            if frame_index == 0:
                return start_target[:]
            elif frame_index == total_frames:
                return end_target[:]
            else:
                # Linear interpolation between start and end targets
                return [
                    start_target[i] + (end_target[i] - start_target[i]) * eased_t
                    for i in range(3)
                ]
        
        elif start_target:
            # Maintain focus on start target (classic dolly behavior)
            return start_target[:]
        
        elif end_target:
            # Focus on end target
            return end_target[:]
        
        else:
            # Default: look at midpoint between start and end positions
            return [
                (start_pos[0] + end_pos[0]) / 2,
                (start_pos[1] + end_pos[1]) / 2,
                (start_pos[2] + end_pos[2]) / 2
            ]
    
    def validate_params(self, params: Dict) -> Dict:
        """
        Validate dolly shot specific parameters.
        
        Extends base validation with dolly shot requirements.
        """
        # First run base validation
        validated = super().validate_params(params)
        
        # Check required parameters
        if 'start_position' not in params:
            raise ValueError("start_position is required for dolly shot")
        if 'end_position' not in params:
            raise ValueError("end_position is required for dolly shot")
        
        # Validate optional targets
        if 'start_target' in params:
            validated['start_target'] = self._validate_position(params['start_target'])
        if 'end_target' in params:
            validated['end_target'] = self._validate_position(params['end_target'])
        
        # Validate movement style
        if 'movement_style' in params:
            validated['movement_style'] = str(params['movement_style'])
        else:
            validated['movement_style'] = 'standard'
        
        return validated