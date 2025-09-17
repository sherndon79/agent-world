"""
Orbit shot keyframe generators for orbital camera movements.

This module provides multiple orbital movement generators:
- OrbitShotGenerator: Basic spherical orbital movements around origin
- CinematicOrbitGenerator: Advanced orbital movements with curved paths and target tracking
"""

import logging
import math
from typing import Dict, List, Optional
from .base_generator import BaseKeyframeGenerator


logger = logging.getLogger(__name__)


class OrbitShotGenerator(BaseKeyframeGenerator):
    """Generate keyframes for basic spherical orbital movements"""
    
    def generate_keyframes(self, params: Dict) -> List[Dict]:
        """
        Generate keyframes for spherical orbit around origin or target object.
        
        Args:
            params: Dictionary containing:
                - start_azimuth: Starting azimuth angle in degrees (optional, default 0)
                - end_azimuth: Ending azimuth angle in degrees (optional, default 360)
                - distance: Orbital radius from center (optional, default 10.0)
                - elevation: Elevation angle in degrees (optional, default 15.0)
                - duration: Movement duration in seconds (optional, default 8.0)
                - target_object: USD path to orbit around (optional, uses origin if not provided)
                - start_position: Starting camera position (optional, for target object mode)
                - fps: Frames per second (optional, default 30)
                
        Returns:
            List of keyframe dictionaries for orbital movement
            
        Raises:
            ValueError: If parameters are invalid
        """
        try:
            # Validate parameters
            validated_params = self.validate_params(params)
            
            # Check if we should delegate to cinematic orbit for target object mode
            if 'target_object' in validated_params or 'start_position' in validated_params:
                return self._generate_orbit_around_target(validated_params)
            
            # Basic spherical orbit around origin
            return self._generate_spherical_orbit(validated_params)
            
        except Exception as e:
            logger.error(f"Error generating orbit shot keyframes: {e}")
            raise
    
    def _generate_spherical_orbit(self, params: Dict) -> List[Dict]:
        """Generate spherical orbital keyframes around center point"""
        # Extract parameters with defaults
        start_azimuth = math.radians(params.get('start_azimuth', 0.0))
        end_azimuth = math.radians(params.get('end_azimuth', 360.0))
        distance = params.get('distance', 10.0)
        elevation = math.radians(params.get('elevation', 15.0))
        duration = params.get('duration', 8.0)
        fps = params.get('fps', 30.0)
        center = params.get('center', [0, 0, 0])  # Support custom center point
        
        num_frames = self.calculate_frame_count(duration, fps)
        keyframes = []
        
        # Get target parameters for interpolation
        start_target = params.get('start_target')
        end_target = params.get('end_target')

        for i in range(num_frames + 1):
            t = i / max(1, num_frames)
            azimuth = start_azimuth + (end_azimuth - start_azimuth) * t

            # Orbital easing
            eased_t = 0.5 * (1 - math.cos(math.pi * t))

            # Calculate position from spherical coordinates (Isaac Sim Z-up)
            x = center[0] + distance * math.cos(elevation) * math.cos(azimuth)
            y = center[1] + distance * math.cos(elevation) * math.sin(azimuth)
            z = center[2] + distance * math.sin(elevation)

            # Calculate target with interpolation support
            if start_target and end_target:
                # Linear interpolation between start and end targets across all rotations
                target = [
                    start_target[i] + (end_target[i] - start_target[i]) * eased_t
                    for i in range(3)
                ]
            elif start_target:
                # Use fixed start target
                target = start_target[:]
            else:
                # Look at center point
                target = center[:]

            keyframe = self.create_keyframe(
                position=[x, y, z],
                target=target,
                frame_index=i,
                total_frames=num_frames + 1,
                timestamp=t * duration,
                azimuth_degrees=math.degrees(azimuth),
                elevation_degrees=math.degrees(elevation),
                orbit_progress=eased_t if start_target and end_target else t
            )
            
            keyframes.append(keyframe)
        
        logger.debug(f"Generated {len(keyframes)} spherical orbit keyframes around {center}")
        return keyframes
    
    def _generate_orbit_around_target(self, params: Dict) -> List[Dict]:
        """Generate orbital movement around target object from starting position"""
        try:
            # Get starting position - either provided or current camera position
            start_pos = params.get('start_position')
            if not start_pos and 'target_object' in params:
                # Try to get current camera position
                if self.camera_controller:
                    current_status = self.camera_controller.get_status()
                    if current_status.get('connected') and current_status.get('position'):
                        start_pos = current_status['position']
                
                if not start_pos:
                    raise ValueError("start_position required when target_object is specified")
            
            target_object = params.get('target_object')
            orbit_count = float(params.get('orbit_count', 1.0))  # Number of full orbits
            arc_degrees = orbit_count * 360.0
            duration = float(params.get('duration', 8.0))
            fps = params.get('fps', 30.0)

            # Use provided center parameter, or calculate from target object
            orbit_center = params.get('center')
            if orbit_center is None:
                orbit_center = self._calculate_orbit_center(target_object)
            else:
                # Convert to list if needed
                orbit_center = list(orbit_center)
            
            # Calculate orbit parameters from starting position
            start_vec = [start_pos[i] - orbit_center[i] for i in range(3)]
            orbit_radius = math.sqrt(sum(x*x for x in start_vec))
            
            if orbit_radius == 0:
                raise ValueError("Starting position cannot be at orbit center")
            
            # Calculate starting angles
            start_azimuth = math.atan2(start_vec[1], start_vec[0])
            start_elevation = math.asin(start_vec[2] / orbit_radius)
            
            # Get target parameters for interpolation
            start_target = params.get('start_target')
            end_target = params.get('end_target')

            # Calculate original view elevation from start_target
            original_view_elevation = self._calculate_view_elevation(params, start_pos, orbit_center)
            
            # Calculate end angle
            arc_radians = math.radians(arc_degrees)
            end_azimuth = start_azimuth + arc_radians
            
            # Generate orbital keyframes
            num_frames = self.calculate_frame_count(duration, fps)
            keyframes = []
            
            for i in range(num_frames + 1):
                t = i / max(1, num_frames)
                
                # Orbital easing - smooth like satellite motion
                eased_t = 0.5 * (1 - math.cos(math.pi * t))
                
                # Calculate current orbital angle
                current_azimuth = start_azimuth + (end_azimuth - start_azimuth) * eased_t
                
                # Calculate position on orbital path
                pos = [
                    orbit_center[0] + orbit_radius * math.cos(start_elevation) * math.cos(current_azimuth),
                    orbit_center[1] + orbit_radius * math.cos(start_elevation) * math.sin(current_azimuth),
                    orbit_center[2] + orbit_radius * math.sin(start_elevation)
                ]
                
                # Calculate target with interpolation support
                if start_target and end_target:
                    # Linear interpolation between start and end targets across all rotations
                    target = [
                        start_target[i] + (end_target[i] - start_target[i]) * eased_t
                        for i in range(3)
                    ]
                elif start_target:
                    # Use fixed start target
                    target = start_target[:]
                else:
                    # Fallback to original orbital target calculation
                    target = self._calculate_orbital_target(pos, orbit_center, original_view_elevation)
                
                keyframe = self.create_keyframe(
                    position=pos,
                    target=target,
                    frame_index=i,
                    total_frames=num_frames + 1,
                    timestamp=t * duration,
                    orbit_progress=eased_t,
                    azimuth_degrees=math.degrees(current_azimuth)
                )
                
                keyframes.append(keyframe)
            
            logger.debug(f"Generated {len(keyframes)} target orbit keyframes around {target_object}")
            return keyframes
            
        except Exception as e:
            logger.error(f"Error generating orbit around target: {e}")
            raise
    
    def _calculate_orbit_center(self, target_object: Optional[str]) -> List[float]:
        """Calculate orbit center from target object or use origin"""
        if target_object and self.camera_controller:
            try:
                # Use camera controller's asset transform method
                transform_result = self.camera_controller.get_asset_transform(target_object, calculation_mode="auto")
                if transform_result.get('success') and transform_result.get('position'):
                    orbit_center = transform_result['position']
                    logger.debug(f"Using target object center: {target_object} at {orbit_center}")
                    return orbit_center
                else:
                    logger.warning(f"Failed to get transform for {target_object}: {transform_result.get('error', 'Unknown error')}")
            except Exception as e:
                logger.warning(f"Failed to calculate target object center: {e}")
        
        # Fallback to origin
        return [0, 0, 0]
    
    def _calculate_view_elevation(self, params: Dict, start_pos: List[float], orbit_center: List[float]) -> float:
        """Calculate original view elevation angle"""
        start_target = params.get('start_target')
        if start_target:
            # Calculate view vector from start position to target
            view_vector = [start_target[i] - start_pos[i] for i in range(3)]
            view_distance = math.sqrt(sum(x*x for x in view_vector))
            
            if view_distance > 0:
                return math.asin(view_vector[2] / view_distance)
        
        # Default slight downward angle
        return -0.1
    
    def _calculate_orbital_target(self, pos: List[float], orbit_center: List[float], view_elevation: float) -> List[float]:
        """Calculate target point for orbital camera"""
        # Calculate horizontal direction to orbit center
        horizontal_to_center = [orbit_center[0] - pos[0], orbit_center[1] - pos[1], 0]
        horizontal_distance = math.sqrt(horizontal_to_center[0]**2 + horizontal_to_center[1]**2)
        
        if horizontal_distance > 0:
            # Normalize horizontal direction
            horizontal_direction = [horizontal_to_center[0] / horizontal_distance, horizontal_to_center[1] / horizontal_distance, 0]
            
            # Apply original elevation angle
            target_distance = 100  # Fixed distance for target calculation
            target = [
                pos[0] + horizontal_direction[0] * target_distance * math.cos(view_elevation),
                pos[1] + horizontal_direction[1] * target_distance * math.cos(view_elevation),
                pos[2] + target_distance * math.sin(view_elevation)
            ]
            
            return target
        
        # Fallback
        return orbit_center
    
    def validate_params(self, params: Dict) -> Dict:
        """Validate orbit shot parameters"""
        validated = super().validate_params(params)
        
        # Validate orbital parameters
        if 'start_azimuth' in params:
            validated['start_azimuth'] = float(params['start_azimuth'])
        if 'end_azimuth' in params:
            validated['end_azimuth'] = float(params['end_azimuth'])
        if 'distance' in params:
            distance = float(params['distance'])
            if distance <= 0:
                raise ValueError("Distance must be positive")
            validated['distance'] = distance
        if 'elevation' in params:
            validated['elevation'] = float(params['elevation'])
        if 'orbit_count' in params:
            orbit_count = float(params['orbit_count'])
            if orbit_count <= 0:
                raise ValueError("Orbit count must be positive")
            validated['orbit_count'] = orbit_count

        # Validate target parameters
        if 'start_target' in params:
            validated['start_target'] = self._validate_position(params['start_target'])
        if 'end_target' in params:
            validated['end_target'] = self._validate_position(params['end_target'])

        return validated


class CinematicOrbitGenerator(BaseKeyframeGenerator):
    """Generate keyframes for cinematic curved orbital movements"""
    
    def generate_keyframes(self, params: Dict) -> List[Dict]:
        """
        Generate keyframes for cinematic sweeping arc path between positions.
        
        Creates curved dolly track-like movements with banking turns.
        
        Args:
            params: Dictionary containing:
                - start_position: Starting camera position [x, y, z] (required)
                - end_position: Ending camera position [x, y, z] (required)
                - start_target: Starting look-at target [x, y, z] (optional)
                - end_target: Ending look-at target [x, y, z] (optional)
                - duration: Movement duration in seconds (optional, default 8.0)
                - fps: Frames per second (optional, default 30)
                
        Returns:
            List of keyframe dictionaries for cinematic orbital movement
        """
        try:
            # Validate parameters
            validated_params = self.validate_params(params)
            
            start_pos = validated_params['start_position']
            end_pos = validated_params['end_position']
            start_target = validated_params.get('start_target')
            end_target = validated_params.get('end_target')
            duration = validated_params.get('duration', 8.0)
            fps = validated_params['fps']
            
            # Calculate Bezier control point for curved path
            control_point = self._calculate_curved_control_point(start_pos, end_pos)
            
            # Generate curved path keyframes
            num_frames = self.calculate_frame_count(duration, fps)
            keyframes = []
            
            for i in range(num_frames + 1):
                t = i / max(1, num_frames)
                
                # Smooth easing for cinematic feel
                eased_t = 0.5 * (1 - math.cos(math.pi * t))
                
                # Calculate position on Bezier curve
                position = self._calculate_bezier_position(start_pos, control_point, end_pos, eased_t, i, num_frames)
                
                # Calculate cinematic target
                target = self._calculate_cinematic_target(start_pos, end_pos, start_target, end_target, t, eased_t)
                
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
            
            logger.debug(f"Generated {len(keyframes)} cinematic orbit keyframes")
            return keyframes
            
        except Exception as e:
            logger.error(f"Error generating cinematic orbit keyframes: {e}")
            raise
    
    def _calculate_curved_control_point(self, start_pos: List[float], end_pos: List[float]) -> List[float]:
        """Calculate control point for curved orbital path"""
        # Calculate movement vector and distance
        move_vector = [end_pos[i] - start_pos[i] for i in range(3)]
        move_distance = math.sqrt(sum(x*x for x in move_vector))
        
        if move_distance == 0:
            return start_pos[:]
        
        # Normalize movement vector
        move_norm = [x / move_distance for x in move_vector]
        
        # Calculate perpendicular vector for arc curvature
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
        
        # Calculate midpoint and control point
        midpoint = [(start_pos[i] + end_pos[i]) * 0.5 for i in range(3)]
        
        # Arc curvature: 25% of movement distance as sideways offset
        arc_offset = move_distance * 0.25
        control_point = [
            midpoint[0] + perp[0] * arc_offset,
            midpoint[1] + perp[1] * arc_offset,
            midpoint[2] + perp[2] * arc_offset + move_distance * 0.1  # Slight elevation
        ]
        
        return control_point
    
    def _calculate_bezier_position(self, start_pos: List[float], control_point: List[float], 
                                 end_pos: List[float], eased_t: float, frame_index: int, 
                                 total_frames: int) -> List[float]:
        """Calculate position on quadratic Bezier curve"""
        # Ensure exact start and end positions
        if frame_index == 0:
            return start_pos[:]
        elif frame_index == total_frames:
            return end_pos[:]
        else:
            # Quadratic Bezier curve: P(t) = (1-t)²P₀ + 2(1-t)tP₁ + t²P₂
            t_sq = eased_t * eased_t
            one_minus_t = 1 - eased_t
            one_minus_t_sq = one_minus_t * one_minus_t
            
            return [
                one_minus_t_sq * start_pos[i] + 
                2 * one_minus_t * eased_t * control_point[i] + 
                t_sq * end_pos[i]
                for i in range(3)
            ]
    
    def _calculate_cinematic_target(self, start_pos: List[float], end_pos: List[float],
                                  start_target: Optional[List[float]], end_target: Optional[List[float]],
                                  t: float, eased_t: float) -> List[float]:
        """Calculate cinematic target with scene focus"""
        if start_target and end_target:
            # Calculate scene center (average of targets)
            scene_center = [(start_target[i] + end_target[i]) / 2 for i in range(3)]
            
            # Blend between linear interpolation and scene center
            scene_focus_factor = math.sin(math.pi * t) * 0.7  # Peak focus at t=0.5
            
            linear_target = [start_target[i] + (end_target[i] - start_target[i]) * eased_t for i in range(3)]
            
            return [
                linear_target[i] + (scene_center[i] - linear_target[i]) * scene_focus_factor
                for i in range(3)
            ]
        else:
            # Default: look at scene center (average of positions)
            return [
                (start_pos[0] + end_pos[0]) / 2,
                (start_pos[1] + end_pos[1]) / 2,
                (start_pos[2] + end_pos[2]) / 2 - 10  # Look slightly down
            ]
    
    def validate_params(self, params: Dict) -> Dict:
        """Validate cinematic orbit parameters"""
        validated = super().validate_params(params)
        
        # Check required parameters
        if 'start_position' not in params:
            raise ValueError("start_position is required for cinematic orbit")
        if 'end_position' not in params:
            raise ValueError("end_position is required for cinematic orbit")
        
        # Validate optional targets
        if 'start_target' in params:
            validated['start_target'] = self._validate_position(params['start_target'])
        if 'end_target' in params:
            validated['end_target'] = self._validate_position(params['end_target'])
        
        return validated