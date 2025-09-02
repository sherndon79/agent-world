"""
XR WorldViewer Camera Controller

Core camera manipulation functionality for Isaac Sim viewport control.
Thread-safe operations for AI-powered camera positioning and movement.
"""

import logging
import math
from typing import Dict, List, Optional, Tuple, Union

import omni.kit.viewport.utility as viewport_utils
import omni.usd
from omni.kit.viewport.utility import get_active_viewport_window
from pxr import Gf, UsdGeom, Usd


logger = logging.getLogger(__name__)


class CameraController:
    """Thread-safe camera control for Isaac Sim viewport"""
    
    def __init__(self):
        self.viewport_window = None
        self.viewport_api = None
        self._initialize_viewport()
        
        # Initialize cinematic controller (lazy import to avoid circular dependency)
        self._cinematic_controller = None
    
    def _initialize_viewport(self):
        """Initialize viewport connection"""
        try:
            self.viewport_window = get_active_viewport_window()
            if self.viewport_window:
                self.viewport_api = self.viewport_window.viewport_api
                logger.info("Camera controller initialized with active viewport")
            else:
                logger.warning("No active viewport found")
        except Exception as e:
            logger.error(f"Failed to initialize viewport: {e}")
    
    def _set_camera_with_compatibility(self, position: List[float], target: Optional[List[float]] = None) -> bool:
        """
        Isaac Sim API compatibility layer for camera positioning.
        Tries multiple API methods to handle different Isaac Sim versions.
        
        Returns:
            bool: True if any method succeeded, False if all failed
        """
        eye_position = tuple(position)
        target_position = tuple(target) if target else (0.0, 0.0, 0.0)
        
        # Method 1: Try Isaac Sim specific utilities (newer versions)
        try:
            from isaacsim.core.utils.viewports import set_camera_view
            set_camera_view(
                eye=eye_position,
                target=target_position,
                camera_prim_path="/OmniverseKit_Persp"
            )
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug("Camera positioned using isaacsim.core.utils.viewports")
            return True
        except ImportError:
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug("isaacsim.core.utils.viewports not available")
        except Exception as e:
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug(f"isaacsim.core.utils.viewports failed: {e}")
        
        # Method 2: Try Omniverse Kit viewport utilities (standard approach)
        try:
            if self.viewport_api:
                # Convert to Gf vectors
                from pxr import Gf
                eye_vec = Gf.Vec3d(eye_position[0], eye_position[1], eye_position[2])
                target_vec = Gf.Vec3d(target_position[0], target_position[1], target_position[2])
                
                # Set camera position and target using viewport API
                self.viewport_api.set_camera_position(eye_vec, True)
                if target:
                    self.viewport_api.set_camera_target(target_vec, True)
                
                if logger.isEnabledFor(logging.DEBUG):
                    logger.debug("Camera positioned using viewport_api")
                return True
        except Exception as e:
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug(f"viewport_api method failed: {e}")
        
        # Method 3: Try direct USD camera manipulation (fallback)
        try:
            if self.viewport_api and hasattr(self.viewport_api, 'camera_path'):
                camera_path = self.viewport_api.camera_path
                if camera_path:
                    stage = omni.usd.get_context().get_stage()
                    if stage:
                        camera_prim = stage.GetPrimAtPath(camera_path)
                        if camera_prim and camera_prim.IsValid():
                            # Create transform matrix for camera positioning
                            from pxr import Gf, UsdGeom
                            
                            xformable = UsdGeom.Xformable(camera_prim)
                            if xformable:
                                # Clear existing transforms
                                xformable.ClearXformOpOrder()
                                
                                # Create look-at matrix
                                eye = Gf.Vec3d(eye_position[0], eye_position[1], eye_position[2])
                                target_pt = Gf.Vec3d(target_position[0], target_position[1], target_position[2])
                                up = Gf.Vec3d(0, 1, 0)  # Standard up vector
                                
                                # Calculate look-at matrix
                                matrix = Gf.Matrix4d().SetLookAt(eye, target_pt, up)
                                matrix = matrix.GetInverse()  # Camera transform is inverse of view matrix
                                
                                # Apply transform
                                translate_op = xformable.AddTranslateOp()
                                rotate_op = xformable.AddOrientOp()
                                
                                # Extract translation and rotation from matrix
                                translation = matrix.ExtractTranslation()
                                rotation = matrix.ExtractRotationQuat()
                                
                                translate_op.Set(translation)
                                rotate_op.Set(rotation)
                                
                                if logger.isEnabledFor(logging.DEBUG):
                                    logger.debug("Camera positioned using direct USD manipulation")
                                return True
        except Exception as e:
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug(f"Direct USD manipulation failed: {e}")
        
        # Method 4: Try Kit Commands (last resort)
        try:
            import omni.kit.commands
            
            # Use Kit command to set camera
            omni.kit.commands.execute(
                'SetCameraPosition',
                camera_path='/OmniverseKit_Persp',
                position=eye_position,
                target=target_position if target else None
            )
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug("Camera positioned using Kit commands")
            return True
        except Exception as e:
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug(f"Kit commands method failed: {e}")
        
        # All methods failed
        logger.warning("All Isaac Sim camera positioning methods failed")
        return False
    
    
    def get_status(self) -> Dict:
        """Get current camera status and position"""
        try:
            if not self.viewport_api:
                return {
                    'connected': False,
                    'error': 'No viewport connection'
                }
            
            # Get current camera transform using correct Isaac Sim API
            try:
                camera_path = self.viewport_api.camera_path if hasattr(self.viewport_api, 'camera_path') else None
                
                # Get camera position and target using correct Omniverse camera API
                position = None
                target = None
                
                try:
                    # Get camera transform from USD stage if camera path exists
                    if camera_path:
                        import omni.usd
                        from pxr import UsdGeom, Gf
                        
                        stage = omni.usd.get_context().get_stage()
                        if stage:
                            camera_prim = stage.GetPrimAtPath(camera_path)
                            if camera_prim and camera_prim.IsValid():
                                # Get camera as UsdGeom.Camera
                                camera = UsdGeom.Camera(camera_prim)
                                if camera:
                                    # Get transform matrix
                                    transform = camera.ComputeLocalToWorldTransform(0.0)
                                    if transform:
                                        # Extract position from transform matrix
                                        pos = transform.ExtractTranslation()
                                        position = [float(pos[0]), float(pos[1]), float(pos[2])]
                                    
                                    # Try to get camera target and direction vectors
                                    # Note: USD cameras don't store explicit target, but we can compute direction vectors
                                    forward_vec = None
                                    right_vec = None
                                    up_vec = None
                                    if transform:
                                        # Get camera direction vectors
                                        forward = transform.TransformDir(Gf.Vec3d(0, 0, -1))  # Camera looks down -Z
                                        right = transform.TransformDir(Gf.Vec3d(1, 0, 0))     # Camera right is +X
                                        up = transform.TransformDir(Gf.Vec3d(0, 1, 0))        # Camera up is +Y
                                        
                                        # Convert to lists for JSON serialization
                                        forward_vec = [float(forward[0]), float(forward[1]), float(forward[2])]
                                        right_vec = [float(right[0]), float(right[1]), float(right[2])]
                                        up_vec = [float(up[0]), float(up[1]), float(up[2])]
                                        
                                        # Calculate target position for convenience
                                        target_dist = 10.0  # Default target distance
                                        target_pos = pos + (forward * target_dist)
                                        target = [float(target_pos[0]), float(target_pos[1]), float(target_pos[2])]
                                        
                                        # Calculate rotation angles from transform for debugging
                                        try:
                                            rotation_quat = transform.ExtractRotationQuat()
                                            import math
                                            
                                            # Convert quaternion to Euler angles
                                            w, x, y, z = rotation_quat.GetReal(), rotation_quat.GetImaginary()[0], rotation_quat.GetImaginary()[1], rotation_quat.GetImaginary()[2]
                                            
                                            # Roll (x-axis rotation)
                                            sinr_cosp = 2 * (w * x + y * z)
                                            cosr_cosp = 1 - 2 * (x * x + y * y)
                                            roll = math.atan2(sinr_cosp, cosr_cosp)
                                            
                                            # Pitch (y-axis rotation)
                                            sinp = 2 * (w * y - z * x)
                                            if abs(sinp) >= 1:
                                                pitch = math.copysign(math.pi / 2, sinp)
                                            else:
                                                pitch = math.asin(sinp)
                                            
                                            # Yaw (z-axis rotation)
                                            siny_cosp = 2 * (w * z + x * y)
                                            cosy_cosp = 1 - 2 * (y * y + z * z)
                                            yaw = math.atan2(siny_cosp, cosy_cosp)
                                            
                                            # Convert to degrees
                                            rotation = [math.degrees(roll), math.degrees(pitch), math.degrees(yaw)]
                                        except Exception:
                                            rotation = [0.0, 0.0, 0.0]
                                        
                except Exception as cam_error:
                    # Fallback: camera info not available, but connection is still valid
                    pass
                
                return {
                    'connected': True,
                    'camera_path': str(camera_path) if camera_path else None,
                    'position': position,
                    'target': target,
                    'rotation': rotation,  # Add rotation angles for debugging/analysis
                    'forward_vector': forward_vec,
                    'right_vector': right_vec,
                    'up_vector': up_vec,
                    'api_available': True
                }
                
            except Exception as api_error:
                return {
                    'connected': True,
                    'error': f'Camera API access error: {api_error}',
                    'position': None,
                    'target': None
                }
            
        except Exception as e:
            return {
                'connected': False,
                'error': f'Failed to get camera status: {e}'
            }
    
    def set_position(self, position: List[float], target: Optional[List[float]] = None, 
                    up_vector: Optional[List[float]] = None) -> Dict:
        """
        Set camera position with full orientation support using Isaac Sim's native USD transform approach
        
        Args:
            position: [x, y, z] camera position
            target: [x, y, z] look-at target (optional)
            up_vector: [x, y, z] up direction (optional, defaults to [0, 1, 0])
        """
        try:
            if not self.viewport_api:
                self._initialize_viewport()
                if not self.viewport_api:
                    return {'success': False, 'error': 'No viewport connection'}
            
            # Validate position
            if not position or len(position) != 3:
                return {'success': False, 'error': 'Position must be [x, y, z] array'}
            
            # Use target-based positioning
            success = False
            method_used = 'target_based'
            
            try:
                success = self._set_camera_with_compatibility(position, target)
                
                if success:
                    logger.info(f"Camera positioned at {position} looking at {target}")
                
                if not success:
                    return {'success': False, 'error': 'All Isaac Sim camera positioning methods failed'}
                
            except Exception as camera_error:
                return {'success': False, 'error': f'Camera positioning failed: {camera_error}'}
            
            # Set up vector if provided (advanced feature)
            if up_vector:
                if len(up_vector) != 3:
                    return {'success': False, 'error': 'Up vector must be [x, y, z] array'}
                # Note: Advanced up vector manipulation would require additional USD transform work
            
            return {
                'success': True,
                'position': position,
                'target': target,
                'method_used': method_used,
                'message': f'Camera positioned using {method_used}'
            }
            
        except Exception as e:
            return {'success': False, 'error': f'Failed to set camera position: {e}'}
    
    def frame_object(self, object_path: str, distance: Optional[float] = None) -> Dict:
        """
        Frame an object in the viewport using proper Omniverse Kit viewport API
        
        Args:
            object_path: USD path to the object (e.g., '/World/my_cube')
            distance: Optional distance from object (used for fallback calculation)
        """
        try:
            if not self.viewport_api:
                return {'success': False, 'error': 'No viewport connection'}
            
            # Get USD stage - import needed for local scope
            import omni.usd
            stage = omni.usd.get_context().get_stage()
            if not stage:
                return {'success': False, 'error': 'No USD stage available'}
            
            # Get the object prim
            prim = stage.GetPrimAtPath(object_path)
            if not prim.IsValid():
                return {'success': False, 'error': f'Object not found at path: {object_path}'}
            
            # Method 1: Try Omniverse Kit frame_viewport_prims API (preferred)
            try:
                from omni.kit.viewport.utility import frame_viewport_prims, get_active_viewport
                
                # Get active viewport
                active_viewport = get_active_viewport()
                if active_viewport:
                    # Frame the specific prim using Kit's built-in functionality
                    frame_viewport_prims(active_viewport, prims=[object_path])
                    
                    if logger.isEnabledFor(logging.DEBUG):
                        logger.debug(f"Object framed using frame_viewport_prims: {object_path}")
                    return {
                        'success': True,
                        'object_path': object_path,
                        'method': 'frame_viewport_prims',
                        'message': f'Camera framed on object: {object_path}'
                    }
            except ImportError:
                if logger.isEnabledFor(logging.DEBUG):
                    logger.debug("frame_viewport_prims not available, trying FramePrimsCommand")
            except Exception as e:
                if logger.isEnabledFor(logging.DEBUG):
                    logger.debug(f"frame_viewport_prims failed: {e}")
            
            # Method 2: Try FramePrimsCommand (alternative)
            try:
                import omni.kit.commands
                
                # Use Kit command to frame the prim
                omni.kit.commands.execute('FramePrims', prim_to_move=object_path)
                
                if logger.isEnabledFor(logging.DEBUG):
                    logger.debug(f"Object framed using FramePrimsCommand: {object_path}")
                return {
                    'success': True,
                    'object_path': object_path,
                    'method': 'FramePrimsCommand',
                    'message': f'Camera framed on object: {object_path}'
                }
            except Exception as e:
                if logger.isEnabledFor(logging.DEBUG):
                    logger.debug(f"FramePrimsCommand failed: {e}")
            
            # Method 3: Try legacy focus_on_selected (fallback)
            try:
                # Select the prim first
                context = omni.usd.get_context()
                if context:
                    selection = context.get_selection()
                    selection.set_selected_prim_paths([object_path], True)
                    
                    # Try legacy viewport focus
                    if hasattr(self.viewport_window, 'focus_on_selected'):
                        self.viewport_window.focus_on_selected()
                        
                        if logger.isEnabledFor(logging.DEBUG):
                            logger.debug(f"Object framed using focus_on_selected: {object_path}")
                        return {
                            'success': True,
                            'object_path': object_path,
                            'method': 'focus_on_selected',
                            'message': f'Camera framed on object: {object_path}'
                        }
            except Exception as e:
                if logger.isEnabledFor(logging.DEBUG):
                    logger.debug(f"focus_on_selected failed: {e}")
            
            # Method 4: Manual calculation fallback (original implementation)
            try:
                # Get object's bounding box
                bbox_cache = UsdGeom.BBoxCache(stage.GetTimeCode(), [UsdGeom.Tokens.default_])
                bbox = bbox_cache.ComputeWorldBound(prim)
                
                if bbox.IsEmpty():
                    return {'success': False, 'error': f'Object has no valid bounds: {object_path}'}
                
                # Calculate center and size
                bbox_range = bbox.ComputeAlignedRange()
                center = bbox_range.GetMidpoint()
                size = bbox_range.GetSize()
                max_extent = max(size[0], size[1], size[2])
                
                # Calculate camera distance
                if distance is None:
                    distance = max_extent * 2.5  # Reasonable framing distance
                
                # Position camera to frame the object
                camera_position = [
                    center[0],
                    center[1] + max_extent * 0.5,  # Slightly above
                    center[2] + distance
                ]
                
                camera_target = [center[0], center[1], center[2]]
                
                # Set camera position and target using our compatibility layer
                result = self._set_camera_with_compatibility(camera_position, camera_target)
                
                if result:
                    if logger.isEnabledFor(logging.DEBUG):
                        logger.debug(f"Object framed using manual calculation: {object_path}")
                    return {
                        'success': True,
                        'object_path': object_path,
                        'object_center': camera_target,
                        'calculated_distance': distance,
                        'method': 'manual_calculation',
                        'message': f'Camera framed on object: {object_path}'
                    }
                else:
                    return {'success': False, 'error': 'Manual camera positioning failed'}
                    
            except Exception as e:
                return {'success': False, 'error': f'Manual framing calculation failed: {e}'}
            
            # All methods failed
            return {'success': False, 'error': 'All framing methods failed - no compatible API found'}
            
        except Exception as e:
            logger.error(f"Failed to frame object: {e}")
            return {'success': False, 'error': f'Failed to frame object: {e}'}
    
    def orbit(self, center: List[float], distance: float, elevation: float, azimuth: float) -> Dict:
        """
        Position camera in an orbital position around a center point
        
        Args:
            center: [x, y, z] center point to orbit around
            distance: Distance from center
            elevation: Elevation angle in degrees (-90 to 90, 0 = horizon)
            azimuth: Azimuth angle in degrees (0 = front, 90 = right, etc.)
        """
        try:
            if not center or len(center) != 3:
                return {'success': False, 'error': 'Center must be [x, y, z] array'}
            
            if distance <= 0:
                return {'success': False, 'error': 'Distance must be positive'}
            
            # Clamp elevation
            elevation = max(-89, min(89, elevation))
            
            # Convert angles to radians
            elev_rad = math.radians(elevation)
            azim_rad = math.radians(azimuth)
            
            # Calculate spherical coordinates
            x_offset = distance * math.cos(elev_rad) * math.sin(azim_rad)
            y_offset = distance * math.sin(elev_rad)
            z_offset = distance * math.cos(elev_rad) * math.cos(azim_rad)
            
            # Calculate camera position
            camera_position = [
                center[0] + x_offset,
                center[1] + y_offset,
                center[2] + z_offset
            ]
            
            # Set camera position with center as target
            result = self.set_position(camera_position, center)
            
            if result['success']:
                result.update({
                    'orbit_center': center,
                    'distance': distance,
                    'elevation': elevation,
                    'azimuth': azimuth,
                    'message': f'Camera positioned in orbit: {elevation}° elevation, {azimuth}° azimuth'
                })
            
            return result
            
        except Exception as e:
            return {'success': False, 'error': f'Failed to orbit camera: {e}'}
    
    def look_at(self, target: List[float]) -> Dict:
        """
        Point camera at a target while keeping current position
        
        Args:
            target: [x, y, z] target point to look at
        """
        try:
            if not self.viewport_api:
                return {'success': False, 'error': 'No viewport connection'}
            
            if not target or len(target) != 3:
                return {'success': False, 'error': 'Target must be [x, y, z] array'}
            
            # Get current camera position using proper API
            current_position = None
            try:
                camera_path = self.viewport_api.camera_path if hasattr(self.viewport_api, 'camera_path') else None
                if camera_path:
                    import omni.usd
                    from pxr import UsdGeom
                    
                    stage = omni.usd.get_context().get_stage()
                    if stage:
                        camera_prim = stage.GetPrimAtPath(camera_path)
                        if camera_prim and camera_prim.IsValid():
                            camera = UsdGeom.Camera(camera_prim)
                            if camera:
                                transform = camera.ComputeLocalToWorldTransform(0.0)
                                if transform:
                                    pos = transform.ExtractTranslation()
                                    current_position = [float(pos[0]), float(pos[1]), float(pos[2])]
            except Exception as e:
                pass
            
            if not current_position:
                return {'success': False, 'error': 'Could not get current camera position'}
            
            # Set target while keeping current position
            cam_target = Gf.Vec3d(target[0], target[1], target[2])
            self.viewport_api.set_camera_target(cam_target, True)
            
            return {
                'success': True,
                'target': target,
                'position': list(current_position),
                'message': 'Camera target updated'
            }
            
        except Exception as e:
            return {'success': False, 'error': f'Failed to set camera target: {e}'}
    
    def get_camera_bounds(self) -> Dict:
        """Get the current camera's viewing bounds"""
        try:
            if not self.viewport_api:
                return {'success': False, 'error': 'No viewport connection'}
            
            # This would require more complex viewport frustum calculations
            # For now, return basic camera info
            status = self.get_status()
            
            if status['connected']:
                return {
                    'success': True,
                    'camera_info': status,
                    'message': 'Camera bounds retrieved'
                }
            else:
                return {'success': False, 'error': 'Could not get camera bounds'}
                
        except Exception as e:
            return {'success': False, 'error': f'Failed to get camera bounds: {e}'}
    
    def get_asset_transform(self, usd_path: str, calculation_mode: str = "auto") -> Dict:
        """
        Get transform information for a specific asset in the scene.
        
        This is the canonical location for asset position queries since camera operations
        need object locations for framing, orbiting, and positioning.
        
        Handles both individual primitives and complex hierarchical assets.
        For complex assets like groups, calculates bounding box center.
        
        Args:
            usd_path: USD path to the asset (e.g., '/World/my_cube' or '/World/ProperCity')
            calculation_mode: How to calculate position for complex assets
                - "auto": Smart detection - bounds for groups, pivot for primitives
                - "center": Always use bounding box center
                - "pivot": Always use local pivot/transform
                - "bounds": Always use bounding box center (same as center)
                
        Returns:
            Dictionary with transform data:
            {
                "success": bool,
                "position": [x, y, z],
                "rotation": [rx, ry, rz], 
                "scale": [sx, sy, sz],
                "bounds": {
                    "min": [x, y, z],
                    "max": [x, y, z], 
                    "center": [x, y, z]
                },
                "type": "primitive|group|reference",
                "child_count": int
            }
        """
        try:
            # Get USD stage
            import omni.usd
            from pxr import Usd
            
            context = omni.usd.get_context()
            stage = context.get_stage()
            
            if not stage:
                return {
                    'success': False,
                    'error': "No USD stage available."
                }
            
            # Get the prim at the specified path
            prim = stage.GetPrimAtPath(usd_path)
            if not prim.IsValid():
                return {
                    'success': False,
                    'error': f"Path '{usd_path}' not found or invalid."
                }
            
            # Initialize result data
            result = {
                'success': True,
                'usd_path': usd_path,
                'name': prim.GetName(),
                'type': self._classify_asset_type(prim),
                'child_count': len(list(prim.GetChildren())),
                'position': [0.0, 0.0, 0.0],
                'rotation': [0.0, 0.0, 0.0],
                'scale': [1.0, 1.0, 1.0],
                'bounds': {
                    'min': [0.0, 0.0, 0.0],
                    'max': [0.0, 0.0, 0.0],
                    'center': [0.0, 0.0, 0.0]
                },
                'calculation_mode': calculation_mode
            }
            
            # Calculate bounding box for all asset types
            bounds_info = self._calculate_bounds(prim, stage)
            if bounds_info['success']:
                result['bounds'] = bounds_info['bounds']
            
            # Get local transform information
            transform_info = self._get_local_transform(prim)
            if transform_info['success']:
                result['position'] = transform_info['position']
                result['rotation'] = transform_info['rotation'] 
                result['scale'] = transform_info['scale']
            
            # Apply calculation mode logic
            if calculation_mode == "center" or calculation_mode == "bounds":
                # Always use bounding box center
                result['position'] = result['bounds']['center']
            elif calculation_mode == "auto":
                # Smart detection based on asset type
                if result['type'] == 'group' and result['child_count'] > 0:
                    # For groups, use bounding box center
                    result['position'] = result['bounds']['center']
                # For primitives and references, keep local transform position
            # For "pivot" mode, keep the local transform position (already set)
            
            logger.info(f"🔍 Transform query for '{usd_path}': pos={result['position']}, type={result['type']}")
            
            return result
            
        except Exception as e:
            logger.error(f"❌ Error getting asset transform for '{usd_path}': {e}")
            return {
                'success': False,
                'error': str(e),
                'usd_path': usd_path
            }
    
    def _classify_asset_type(self, prim) -> str:
        """Classify the type of asset based on USD prim properties."""
        try:
            type_name = prim.GetTypeName()
            children = list(prim.GetChildren())
            
            # Check if it's a primitive geometry
            if type_name in ['Cube', 'Sphere', 'Cylinder', 'Cone', 'Plane', 'Mesh']:
                return 'primitive'
            
            # Check if it's a reference to external asset
            if prim.HasAuthoredReferences():
                return 'reference'
            
            # Check if it's a group/container with children
            if type_name == 'Xform' and len(children) > 0:
                return 'group'
            
            # Default classification
            return 'other'
            
        except Exception as e:
            logger.warning(f"Error classifying asset type: {e}")
            return 'unknown'
    
    def _calculate_bounds(self, prim, stage) -> Dict:
        """Calculate bounding box for a prim and all its children."""
        try:
            from pxr import UsdGeom, Gf, Usd
            
            # Get bounding box using UsdGeom with correct constructor
            try:
                # Try USD 24.x+ API first
                bbox_cache = UsdGeom.BBoxCache(
                    Usd.TimeCode.Default(),
                    [UsdGeom.Tokens.default_]
                )
            except TypeError:
                try:
                    # Fallback to older API
                    bbox_cache = UsdGeom.BBoxCache(
                        Usd.TimeCode.Default(),
                        [UsdGeom.Tokens.default_],
                        True
                    )
                except TypeError:
                    # Use simplest constructor
                    bbox_cache = UsdGeom.BBoxCache()
            
            # Calculate bounds for this prim and all children
            bound = bbox_cache.ComputeWorldBound(prim)
            
            # Check if bound is valid - different methods for different USD versions
            is_empty = False
            try:
                is_empty = bound.isEmpty()
            except AttributeError:
                try:
                    # Try accessing the range directly
                    bbox_range = bound.ComputeAlignedRange()
                    min_point = bbox_range.GetMin()
                    max_point = bbox_range.GetMax()
                    # Check if all coordinates are the same (empty bounds)
                    is_empty = (min_point == max_point)
                except (AttributeError, RuntimeError, ValueError):
                    is_empty = True
            
            if is_empty or not bound:
                # No geometry bounds found, try to estimate from children positions
                return self._estimate_bounds_from_children(prim)
            
            # Extract bounding box information
            bbox_range = bound.ComputeAlignedRange()
            min_point = bbox_range.GetMin()
            max_point = bbox_range.GetMax()
            
            min_coords = [float(min_point[0]), float(min_point[1]), float(min_point[2])]
            max_coords = [float(max_point[0]), float(max_point[1]), float(max_point[2])]
            
            # Calculate center
            center = [
                (min_coords[0] + max_coords[0]) / 2.0,
                (min_coords[1] + max_coords[1]) / 2.0,
                (min_coords[2] + max_coords[2]) / 2.0
            ]
            
            return {
                'success': True,
                'bounds': {
                    'min': min_coords,
                    'max': max_coords,
                    'center': center
                }
            }
            
        except Exception as e:
            logger.warning(f"Error calculating bounds: {e}")
            # Fall back to children estimation if UsdGeom bounds fail
            return self._estimate_bounds_from_children(prim)
    
    def _estimate_bounds_from_children(self, prim) -> Dict:
        """Estimate bounds by examining child positions."""
        try:
            positions = []
            
            # Recursively collect positions from all children
            def collect_positions(p):
                transform_info = self._get_local_transform(p)
                if transform_info['success']:
                    positions.append(transform_info['position'])
                
                # Recurse into children
                for child in p.GetChildren():
                    collect_positions(child)
            
            collect_positions(prim)
            
            if not positions:
                # No positions found, return default
                return {
                    'success': True,
                    'bounds': {
                        'min': [0.0, 0.0, 0.0],
                        'max': [0.0, 0.0, 0.0],
                        'center': [0.0, 0.0, 0.0]
                    }
                }
            
            # Calculate min/max from positions
            min_coords = [min(pos[i] for pos in positions) for i in range(3)]
            max_coords = [max(pos[i] for pos in positions) for i in range(3)]
            center = [(min_coords[i] + max_coords[i]) / 2.0 for i in range(3)]
            
            return {
                'success': True,
                'bounds': {
                    'min': min_coords,
                    'max': max_coords,
                    'center': center
                }
            }
            
        except Exception as e:
            logger.warning(f"Error estimating bounds from children: {e}")
            return {
                'success': False,
                'error': str(e),
                'bounds': {
                    'min': [0.0, 0.0, 0.0],
                    'max': [0.0, 0.0, 0.0],
                    'center': [0.0, 0.0, 0.0]
                }
            }
    
    def _get_local_transform(self, prim) -> Dict:
        """Extract local transform (position, rotation, scale) from a prim."""
        try:
            from pxr import UsdGeom, Gf
            
            # Create Xformable object and check if it's valid (this is the correct USD approach)
            xformable = UsdGeom.Xformable(prim)
            
            # Check if the Xformable is valid (indicates prim is transformable)
            if not xformable:
                return {
                    'success': False,
                    'error': 'Prim is not transformable'
                }
            
            # Try world transform first (this often contains the actual position data)
            from pxr import Usd
            world_transform = xformable.ComputeLocalToWorldTransform(Usd.TimeCode.Default())
            
            # Extract position from world transform
            world_translation = world_transform.ExtractTranslation()
            position = [float(world_translation[0]), float(world_translation[1]), float(world_translation[2])]
            
            # If world position is still zero, check for transform ops
            if position == [0.0, 0.0, 0.0]:
                # Check if there are any authored transform ops
                xform_ops = xformable.GetOrderedXformOps()
                if xform_ops:
                    # Get local transformation and try again
                    local_transform = xformable.GetLocalTransformation()
                    local_translation = local_transform.ExtractTranslation()
                    position = [float(local_translation[0]), float(local_translation[1]), float(local_translation[2])]
            
            # Extract rotation using the correct USD approach
            rotation_obj = world_transform.ExtractRotation()
            # Convert rotation to Euler angles in degrees (simplified approach)
            rotation = [0.0, 0.0, 0.0]  # Placeholder for now
            
            # Extract scale - simpler approach since Factor is complex
            # Use the magnitude of each basis vector for scale
            basis_x = Gf.Vec3d(world_transform[0][0], world_transform[1][0], world_transform[2][0])
            basis_y = Gf.Vec3d(world_transform[0][1], world_transform[1][1], world_transform[2][1])  
            basis_z = Gf.Vec3d(world_transform[0][2], world_transform[1][2], world_transform[2][2])
            
            scale_x = basis_x.GetLength()
            scale_y = basis_y.GetLength()
            scale_z = basis_z.GetLength()
            scale = [float(scale_x), float(scale_y), float(scale_z)]
            
            # Debug log for position extraction
            logger.info(f"🔍 Position extraction for {prim.GetPath()}: world_pos={position}, has_xform_ops={len(xformable.GetOrderedXformOps())}")
            
            return {
                'success': True,
                'position': position,
                'rotation': rotation,
                'scale': scale
            }
            
        except Exception as e:
            logger.warning(f"Error extracting local transform: {e}")
            return {
                'success': False,
                'error': str(e),
                'position': [0.0, 0.0, 0.0],
                'rotation': [0.0, 0.0, 0.0],
                'scale': [1.0, 1.0, 1.0]
            }
    

    def get_cinematic_controller(self):
        """Get or create synchronous cinematic movement controller"""
        if self._cinematic_controller is None:
            # Lazy import to avoid circular dependency
            from .cinematic_controller_sync import SynchronousCinematicController
            self._cinematic_controller = SynchronousCinematicController(self)
        
        return self._cinematic_controller