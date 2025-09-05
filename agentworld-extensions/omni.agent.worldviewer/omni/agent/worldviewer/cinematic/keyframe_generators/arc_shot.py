"""
Arc shot keyframe generator for curved camera movements.

This generator creates keyframes for curved movements using Bezier curves,
providing natural arcing motion between two positions. Supports style-based
curvature control and banking effects for cinematic shots.
"""

import logging
import math
from typing import Dict, List
from .base_generator import BaseKeyframeGenerator


logger = logging.getLogger(__name__)


class ArcShotGenerator(BaseKeyframeGenerator):
    """Generate keyframes for curved arc movements using Bezier paths"""
    
    def generate_keyframes(self, params: Dict) -> List[Dict]:
        """
        Generate keyframes for arc shot with curved Bezier path.
        
        Args:
            params: Dictionary containing:
                - start_position: Starting camera position [x, y, z] (required)
                - end_position: Ending camera position [x, y, z] (required)  
                - start_target: Starting look-at target [x, y, z] (optional)
                - end_target: Ending look-at target [x, y, z] (optional)
                - duration: Movement duration in seconds (optional, calculated from speed if not provided)
                - speed: Movement speed in units/second (optional, default 8.0 for arc shots)
                - movement_style: Style variant for arc parameters (optional, default 'standard')
                - fps: Frames per second for keyframe generation (optional, default 30)
                
        Returns:
            List of keyframe dictionaries with curved path positions and targets
            
        Raises:
            ValueError: If required parameters are missing or invalid
        """
        try:
            # Validate parameters using base class
            validated_params = self.validate_params(params)
            
            # Extract required parameters
            start_pos = validated_params['start_position']
            end_pos = validated_params['end_position']
            
            # Get optional target parameters
            start_target = validated_params.get('start_target')
            end_target = validated_params.get('end_target')
            
            # Calculate duration (arc shots default to slightly slower speed)
            if 'speed' not in validated_params and 'duration' not in params:
                validated_params['speed'] = 8.0  # Default slower speed for arc shots
            duration = self.calculate_movement_duration(validated_params)
            
            # Get style configuration
            movement_style = validated_params.get('movement_style', 'standard')
            style_config = self.apply_style_config(validated_params, 'arc_shot')
            
            fps = validated_params['fps']
            
            # Calculate Bezier control point for curved path
            control_point = self._calculate_bezier_control_point(start_pos, end_pos, style_config)
            
            # Generate keyframes along curved path
            num_frames = self.calculate_frame_count(duration, fps)
            keyframes = []
            
            for i in range(num_frames + 1):
                t = i / max(1, num_frames)  # Avoid division by zero
                
                # Arc-specific easing for smooth banking motion
                eased_t = self._apply_arc_easing(t)
                
                # Calculate position on Bezier curve
                position = self._calculate_bezier_position(start_pos, control_point, end_pos, eased_t, i, num_frames)
                
                # Calculate target (linear interpolation or look-ahead)
                target = self._calculate_arc_target(
                    start_pos, end_pos, control_point, start_target, end_target,
                    eased_t, i, num_frames
                )
                
                # Create keyframe with arc-specific data
                keyframe = self.create_keyframe(
                    position=position,
                    target=target,
                    frame_index=i,
                    total_frames=num_frames + 1,
                    timestamp=t * duration,
                    curve_progress=eased_t,
                    control_point=control_point
                )
                
                keyframes.append(keyframe)
            
            logger.debug(f"Generated {len(keyframes)} arc shot keyframes over {duration:.1f}s")
            return keyframes
            
        except Exception as e:
            logger.error(f"Error generating arc shot keyframes: {e}")
            raise
    
    def _calculate_bezier_control_point(self, start_pos: List[float], end_pos: List[float], style_config: Dict) -> List[float]:
        """
        Calculate the control point for the quadratic Bezier curve.
        
        Creates a control point offset perpendicular to the movement vector
        to generate the curved arc path.
        """
        # Calculate movement vector and distance
        move_vector = [end_pos[i] - start_pos[i] for i in range(3)]
        move_distance = math.sqrt(sum(x*x for x in move_vector))
        
        if move_distance == 0:
            # No movement, return start position as control point
            return start_pos[:]
        
        # Normalize movement vector
        move_norm = [x / move_distance for x in move_vector]
        
        # Calculate perpendicular vector for arc curvature
        perp = self._calculate_perpendicular_vector(move_norm)
        
        # Calculate midpoint between start and end
        midpoint = [
            start_pos[i] + move_vector[i] * 0.5 for i in range(3)
        ]
        
        # Apply style-driven curvature intensity
        curvature_intensity = style_config.get('curvature_intensity', 0.25)
        arc_offset = move_distance * curvature_intensity
        
        # Calculate control point offset from midpoint
        control_point = [
            midpoint[0] + perp[0] * arc_offset,
            midpoint[1] + perp[1] * arc_offset,
            midpoint[2] + perp[2] * arc_offset + move_distance * 0.1  # Slight elevation
        ]
        
        return control_point
    
    def _calculate_perpendicular_vector(self, move_norm: List[float]) -> List[float]:
        """Calculate perpendicular vector to movement direction"""
        # Use cross product with Z-up to get horizontal perpendicular
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
        
        return perp
    
    def _apply_arc_easing(self, t: float) -> float:
        """Apply arc-specific easing for smooth banking motion"""
        # Sinusoidal easing for smooth arc motion
        return 0.5 * (1 - math.cos(math.pi * t))
    
    def _calculate_bezier_position(self, start_pos: List[float], control_point: List[float], 
                                 end_pos: List[float], eased_t: float, frame_index: int, 
                                 total_frames: int) -> List[float]:
        """
        Calculate position on quadratic Bezier curve.
        
        Ensures exact start and end positions for frame 0 and final frame.
        """
        # CRITICAL: Ensure exact start and end positions
        if frame_index == 0:
            return start_pos[:]
        elif frame_index == total_frames:
            return end_pos[:]
        else:
            # Quadratic Bezier curve: P(t) = (1-t)²P₀ + 2(1-t)tP₁ + t²P₂
            # P₀ = start_pos, P₁ = control_point, P₂ = end_pos
            t_sq = eased_t * eased_t
            one_minus_t = 1 - eased_t
            one_minus_t_sq = one_minus_t * one_minus_t
            
            position = [
                one_minus_t_sq * start_pos[i] + 
                2 * one_minus_t * eased_t * control_point[i] + 
                t_sq * end_pos[i]
                for i in range(3)
            ]
            
            return position
    
    def _calculate_arc_target(self, start_pos: List[float], end_pos: List[float], 
                            control_point: List[float], start_target: List[float] = None,
                            end_target: List[float] = None, eased_t: float = 0.0,
                            frame_index: int = 0, total_frames: int = 1) -> List[float]:
        """
        Calculate target point for arc shot.
        
        Uses linear interpolation if explicit targets provided,
        otherwise calculates look-ahead target for natural motion.
        """
        # If explicit targets provided, use linear interpolation
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
        
        # Default: look ahead along the curve for natural forward-facing movement
        if frame_index < total_frames:
            # Look a few frames ahead for natural targeting
            look_ahead_frames = min(5, total_frames - frame_index)
            next_frame = min(frame_index + look_ahead_frames, total_frames)
            next_t = next_frame / max(1, total_frames)
            next_eased_t = self._apply_arc_easing(next_t)
            
            look_ahead_pos = self._calculate_bezier_position(
                start_pos, control_point, end_pos, next_eased_t, next_frame, total_frames
            )
            
            return look_ahead_pos
        else:
            return end_pos[:]
    
    def validate_params(self, params: Dict) -> Dict:
        """
        Validate arc shot specific parameters.
        
        Extends base validation with arc shot requirements.
        """
        # First run base validation
        validated = super().validate_params(params)
        
        # Check required parameters
        if 'start_position' not in params:
            raise ValueError("start_position is required for arc shot")
        if 'end_position' not in params:
            raise ValueError("end_position is required for arc shot")
        
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