"""
Waypoint capture and camera handling features for WorldSurveyor.

This module contains all waypoint creation and camera interaction functionality,
including HTTP API communication, camera positioning calculations, and waypoint
numbering. Extracted from monolithic waypoint_toolbar.py for better feature
separation and maintainability.
"""

import logging
import json
from typing import Optional, Tuple, List
import asyncio

from .waypoint_types import WaypointTypeRegistry

try:
    import omni.usd
    from pxr import UsdGeom, Gf
    USD_AVAILABLE = True
except ImportError:
    USD_AVAILABLE = False
    logging.warning("USD and UsdGeom not available")

try:
    import omni.kit.viewport.utility
    VIEWPORT_AVAILABLE = True
except ImportError:
    VIEWPORT_AVAILABLE = False
    logging.warning("Viewport utility not available")

logger = logging.getLogger(__name__)


class WaypointCaptureHandler:
    """
    Handles waypoint capture operations and camera interactions.
    
    Provides centralized functionality for creating waypoints at camera positions,
    calculating camera transforms, managing waypoint numbering, and communicating
    with the HTTP API for waypoint storage.
    """
    
    def __init__(self, waypoint_manager, toolbar_controller, config):
        """
        Initialize waypoint capture handler.
        
        Args:
            waypoint_manager: Reference to WaypointManager for core operations
            toolbar_controller: Reference to main toolbar for UI callbacks
            config: Configuration object for debug settings and HTTP endpoints
        """
        self.waypoint_manager = waypoint_manager
        self.toolbar_controller = toolbar_controller
        self._config = config
        
        # Import unified services if available
        try:
            from ..services import get_unified_logger, get_unified_http_client
            self._http_client = get_unified_http_client()
            self._logger = get_unified_logger()
            if config.debug_mode:
                logger.info("Using unified services for waypoint capture")
        except ImportError:
            if config.debug_mode:
                logger.info("Unified services not available, using basic HTTP")
            self._http_client = None
            self._logger = logger
    
    def capture_camera_waypoint(self, waypoint_type: str):
        """
        Capture a waypoint at the current camera position.
        
        Args:
            waypoint_type: The type of waypoint to create
        """
        try:
            # Get camera position and create waypoint using existing methods
            position, target = self.waypoint_manager.get_camera_position_and_target()
            
            # Get next available number for this waypoint type
            next_number = self._get_next_waypoint_number(waypoint_type)
            
            # Use target-based approach for accurate camera positioning
            waypoint_id = self.waypoint_manager.create_waypoint(
                position=position,
                target=target,  # Store target coordinates for accurate recall
                waypoint_type=waypoint_type,
                name=f"{waypoint_type}_{next_number}"
            )
            
            if self._config.debug_mode:
                logger.info(f"Waypoint captured: {waypoint_id} ({waypoint_type})")
                
            # Notify toolbar for UI feedback
            if hasattr(self.toolbar_controller, 'show_capture_feedback'):
                type_name = self._get_waypoint_type_display_name(waypoint_type)
                self.toolbar_controller.show_capture_feedback(f"{type_name} waypoint captured!")
                
        except Exception as e:
            logger.error(f"Error capturing camera waypoint: {e}")
    
    def capture_exact_waypoint(self, waypoint_type: str):
        """
        Capture waypoint at exact camera position using create_waypoint method.
        
        Args:
            waypoint_type: The type of waypoint to create
        """
        try:
            # This is essentially the same as capture_camera_waypoint but kept separate
            # for potential future differentiation between "camera" and "exact" capture
            self.capture_camera_waypoint(waypoint_type)
                
        except Exception as e:
            logger.error(f"Error capturing exact waypoint: {e}")
    
    def get_camera_position_and_forward(self) -> Tuple[Optional[List[float]], Optional[List[float]]]:
        """
        Get camera position and forward vector for waypoint placement calculations.
        
        Returns:
            Tuple of (camera_position, camera_forward) as lists, or (None, None) on error
        """
        try:
            if not USD_AVAILABLE:
                logger.error("USD not available for camera calculations")
                return None, None
                
            # Get the current stage
            stage = omni.usd.get_context().get_stage()
            if not stage:
                logger.error("No active USD stage")
                return None, None
            
            # Get active viewport camera
            if not VIEWPORT_AVAILABLE:
                logger.error("Viewport utility not available")
                return None, None
                
            viewport_api = omni.kit.viewport.utility.get_active_viewport()
            if not viewport_api:
                logger.error("No active viewport")
                return None, None
            
            camera_path = viewport_api.camera_path
            if not camera_path:
                logger.error("No camera path in active viewport")
                return None, None
            
            # Get camera prim and extract transform
            camera_prim = stage.GetPrimAtPath(camera_path)
            if not camera_prim:
                logger.error(f"No camera prim at path: {camera_path}")
                return None, None
            
            # Get camera world transform
            camera_xform = UsdGeom.Xformable(camera_prim)
            
            # Get current time code - handle API variations
            try:
                usd_context = omni.usd.get_context()
                if hasattr(usd_context, 'get_time_code'):
                    time_code = usd_context.get_time_code()
                elif hasattr(usd_context, 'get_current_time'):
                    time_code = usd_context.get_current_time()
                else:
                    # Fallback to time 0.0
                    time_code = 0.0
            except Exception:
                time_code = 0.0
                
            transform_matrix = camera_xform.ComputeLocalToWorldTransform(time_code)
            
            # Extract position and forward vector
            camera_position = transform_matrix.ExtractTranslation()
            camera_position = [float(camera_position[0]), float(camera_position[1]), float(camera_position[2])]
            
            # Extract forward direction from transform matrix (negative Z in camera space)
            forward_vector = -transform_matrix.GetRow3(2)  # Negative Z axis
            camera_forward = [float(forward_vector[0]), float(forward_vector[1]), float(forward_vector[2])]
            
            if self._config.debug_mode:
                logger.info(f"📸 Camera position: {camera_position}")
                logger.info(f"📸 Camera forward: {camera_forward}")
            
            return camera_position, camera_forward
            
        except Exception as e:
            logger.error(f"Error getting camera position and forward: {e}")
            return None, None
    
    def create_waypoint_via_http(self, position: List[float], waypoint_type: Optional[str] = None):
        """
        Create waypoint using HTTP API with proper error handling.
        
        Args:
            position: The 3D position [x, y, z] for the waypoint
            waypoint_type: Optional waypoint type, uses toolbar's current selection if None
        """
        try:
            if waypoint_type is None:
                waypoint_type = getattr(self.toolbar_controller, '_selected_waypoint_type', WaypointTypeRegistry.get_default_type_id())
            
            # Get next available number for naming
            next_number = self._get_next_waypoint_number(waypoint_type)
            
            # Create waypoint data
            waypoint_data = {
                "position": position,
                "waypoint_type": waypoint_type,
                "name": f"{waypoint_type}_{next_number}",
                "metadata": {
                    "created_via": "crosshair_placement",
                    "distance_from_camera": getattr(self.toolbar_controller, 'get_current_distance', lambda: 10.0)()
                }
            }
            
            # Use unified HTTP client if available
            if self._http_client:
                response = self._http_client.post("/waypoints/create", json=waypoint_data)
            else:
                # Fallback to basic HTTP
                import requests
                port = getattr(self._config, 'server_port', getattr(self._config, 'http_port', 8891))
                response = requests.post(
                    f"http://localhost:{port}/waypoints/create",
                    json=waypoint_data,
                    timeout=5
                )
            
            if response.status_code == 200:
                data = response.json()
                if data.get("success"):
                    waypoint_id = data.get("waypoint_id", "unknown")
                    
                    if self._config.debug_mode:
                        logger.info(f"✅ Waypoint created via HTTP: {waypoint_id}")
                        logger.info(f"   Position: {position}")
                        logger.info(f"   Type: {waypoint_type}")
                    
                    # Notify toolbar for UI feedback
                    if hasattr(self.toolbar_controller, 'show_capture_feedback'):
                        type_name = self._get_waypoint_type_display_name(waypoint_type)
                        self.toolbar_controller.show_capture_feedback(f"{type_name} waypoint created!")
                else:
                    error_msg = data.get('message', data.get('error', 'Unknown error'))
                    logger.error(f"Server reported failure: {error_msg}")
                    if self._config.debug_mode:
                        logger.error(f"Full server response: {data}")
                        logger.error(f"Request data was: {waypoint_data}")
            else:
                logger.error(f"HTTP error creating waypoint: {response.status_code}")
                if self._config.debug_mode:
                    logger.error(f"Response text: {response.text}")
                    logger.error(f"Request data was: {waypoint_data}")
                
        except Exception as e:
            logger.error(f"Error creating waypoint via HTTP: {e}")
    
    def _get_next_waypoint_number(self, waypoint_type: str) -> int:
        """
        Get the next available sequential number for a waypoint type.
        
        Args:
            waypoint_type: The waypoint type to get number for
            
        Returns:
            Next available number (starting from 1)
        """
        try:
            # Query existing waypoints to find the highest number
            existing_waypoints = self.waypoint_manager.list_waypoints()
            
            max_number = 0
            prefix = f"{waypoint_type}_"
            
            for waypoint in existing_waypoints:
                # Handle both dict-like and object-like waypoints
                if hasattr(waypoint, 'name'):
                    name = waypoint.name
                elif hasattr(waypoint, 'get'):
                    name = waypoint.get('name', '')
                else:
                    name = getattr(waypoint, 'name', '')
                    
                if name and name.startswith(prefix):
                    try:
                        # Extract number from name like "camera_position_5"
                        number_part = name[len(prefix):]
                        if number_part.isdigit():
                            max_number = max(max_number, int(number_part))
                    except (ValueError, IndexError):
                        continue
            
            return max_number + 1
            
        except Exception as e:
            logger.error(f"Error getting next waypoint number: {e}")
            return 1  # Default to 1 on error
    
    def _get_waypoint_type_display_name(self, waypoint_type: str) -> str:
        """
        Get display name for waypoint type.
        
        Args:
            waypoint_type: The waypoint type ID
            
        Returns:
            Human-readable display name
        """
        try:
            from .waypoint_types import WaypointTypeRegistry
            return WaypointTypeRegistry.get_type_name(waypoint_type)
        except ImportError:
            # Fallback if waypoint_types not available
            return waypoint_type.replace('_', ' ').title()
    
    def force_cleanup_camera_widgets(self):
        """Force cleanup of camera-related UI widgets."""
        try:
            # This method is kept for compatibility but may not be needed
            # in the extracted version since camera widgets are managed elsewhere
            if self._config.debug_mode:
                logger.info("Force cleanup camera widgets called (no-op in extracted version)")
        except Exception as e:
            logger.error(f"Error in force cleanup camera widgets: {e}")


# Convenience functions for backward compatibility
def create_capture_handler(waypoint_manager, toolbar_controller, config) -> Optional[WaypointCaptureHandler]:
    """
    Create and return a new waypoint capture handler instance.
    
    Args:
        waypoint_manager: Reference to WaypointManager
        toolbar_controller: Reference to main toolbar
        config: Configuration object
        
    Returns:
        WaypointCaptureHandler instance or None on error
    """
    try:
        return WaypointCaptureHandler(waypoint_manager, toolbar_controller, config)
    except Exception as e:
        logger.error(f"Failed to create capture handler: {e}")
        return None