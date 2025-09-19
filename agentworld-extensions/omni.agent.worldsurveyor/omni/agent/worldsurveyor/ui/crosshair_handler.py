"""
Crosshair interaction system for WorldSurveyor waypoint capture.

This module handles all crosshair-related functionality including viewport overlay,
mouse click detection, and waypoint placement at crosshair position. Extracted
from monolithic waypoint_toolbar.py for better feature separation.
"""

import logging
from typing import Optional, Tuple
from .waypoint_types import get_waypoint_type_behavior

logger = logging.getLogger(__name__)

try:
    import omni.ui as ui
    import omni.kit.viewport.utility
    import omni.appwindow
    import carb.input
    UI_AVAILABLE = True
except ImportError:
    UI_AVAILABLE = False
    logging.warning("UI components not available for crosshair handler")


class CrosshairInteractionHandler:
    """
    Handles crosshair overlay display and viewport click interactions for waypoint placement.
    
    Features:
    - Crosshair overlay at viewport center
    - Mouse click detection within viewport bounds
    - Waypoint placement at crosshair position
    - Camera position and forward vector calculations
    """
    
    def __init__(self, waypoint_manager, toolbar_controller, config):
        """
        Initialize crosshair interaction handler.
        
        Args:
            waypoint_manager: WaypointManager instance for creating waypoints
            toolbar_controller: Main toolbar controller for callbacks
            config: Configuration object
        """
        self.waypoint_manager = waypoint_manager
        self.toolbar_controller = toolbar_controller
        self._config = config
        
        # Crosshair state
        self._is_capture_mode = False
        self._crosshair_window = None
        self._crosshair_polling_subscription = None
        self._last_crosshair_waypoint_id = None
        
        # Input handling
        self._input_interface = None
        self._viewport_window = None
        self._polling_active = False
        self._last_left_button_state = False
        self._last_x_key_state = False
        
    def enter_capture_mode(self, selected_waypoint_type: str) -> bool:
        """
        Enter crosshair capture mode.
        
        Args:
            selected_waypoint_type: Currently selected waypoint type
            
        Returns:
            True if capture mode entered successfully, False otherwise
        """
        try:
            self._is_capture_mode = True
            self._selected_waypoint_type = selected_waypoint_type
            
            # Set up crosshair and click handlers
            self._setup_crosshair_system()
            
            self._dinfo("🎯 Entered crosshair capture mode")
            return True
            
        except Exception as e:
            logger.error(f"Error entering capture mode: {e}")
            return False
    
    def exit_capture_mode(self):
        """Exit crosshair capture mode and cleanup."""
        try:
            self._is_capture_mode = False
            
            # Clean up crosshair system
            self._cleanup_crosshair_system()
            
            self._dinfo("🎯 Exited crosshair capture mode")
            
        except Exception as e:
            logger.error(f"Error exiting capture mode: {e}")
    
    def _setup_crosshair_system(self):
        """Set up crosshair visual overlay and input polling."""
        if not UI_AVAILABLE:
            self._dinfo("🎯 Crosshair mode active (UI not available)")
            return
            
        try:
            # Get active viewport window
            viewport_window = omni.kit.viewport.utility.get_active_viewport_window()
            if not viewport_window:
                logger.error("No active viewport window for crosshair system")
                return
                
            self._viewport_window = viewport_window
            
            # Show crosshair overlay
            self._show_crosshair()
            
            # Set up keyboard input for left/right click detection
            self._input_interface = carb.input.acquire_input_interface()
            if self._input_interface:
                self._setup_crosshair_input_polling()
                self._dinfo("✅ Crosshair system initialized")
            else:
                logger.error("❌ Failed to get input interface for crosshair system")
            
        except Exception as e:
            logger.error(f"Error setting up crosshair system: {e}")
    
    def _show_crosshair(self):
        """Display crosshair overlay at viewport center."""
        if not UI_AVAILABLE or not self._viewport_window:
            return
            
        try:
            # Create simple crosshair overlay using omni.ui
            try:
                # Get viewport frame for positioning
                viewport_frame = self._viewport_window.frame
                if viewport_frame:
                    # Create crosshair overlay window
                    self._crosshair_window = ui.Window(
                        "Crosshair", 
                        width=40, 
                        height=40,
                        flags=ui.WINDOW_FLAGS_NO_TITLE_BAR | ui.WINDOW_FLAGS_NO_RESIZE | ui.WINDOW_FLAGS_NO_MOVE | ui.WINDOW_FLAGS_NO_SCROLLBAR,
                    )
                    
                    with self._crosshair_window.frame:
                        with ui.VStack():
                            with ui.HStack():
                                ui.Spacer(width=18)
                                # Simple crosshair using UI elements
                                with ui.ZStack():
                                    ui.Rectangle(width=4, height=20, style={"background_color": 0xFF0000FF})  # Red vertical line
                                    ui.Rectangle(width=20, height=4, style={"background_color": 0xFF0000FF})  # Red horizontal line
                                ui.Spacer(width=18)
                            ui.Spacer(height=20)
                    
                    # Position crosshair at viewport center
                    self._position_crosshair_at_center(viewport_frame)
                    
                    self._dinfo("🎯 Crosshair displayed at viewport center")
                    
            except Exception as ui_e:
                logger.warning(f"Could not create crosshair UI overlay: {ui_e}")
                # Fallback: just log that crosshair mode is active
                self._dinfo("🎯 Crosshair mode active (no visual overlay)")
            
        except Exception as e:
            logger.error(f"Error showing crosshair: {e}")
    
    def _position_crosshair_at_center(self, viewport_frame):
        """Position the crosshair overlay at the viewport center."""
        try:
            if self._crosshair_window and viewport_frame:
                # Calculate center position
                center_x = viewport_frame.computed_content_width / 2 - 20  # Half crosshair width
                center_y = viewport_frame.computed_content_height / 2 - 20  # Half crosshair height
                
                # Position the crosshair window
                self._crosshair_window.position_x = center_x
                self._crosshair_window.position_y = center_y
                
        except Exception as e:
            logger.warning(f"Error positioning crosshair: {e}")
    
    def _setup_crosshair_input_polling(self):
        """Set up polling for left/right mouse clicks when crosshair is active."""
        try:
            import omni.kit.app
            
            # Initialize polling state
            self._last_left_button_state = False
            self._last_x_key_state = False
            self._polling_active = True
            
            def poll_crosshair_input(dt):
                if not self._is_capture_mode or not self._polling_active:
                    return
                    
                try:
                    # Get input interface and check if available
                    if not self._input_interface:
                        return
                    
                    # Get mouse and keyboard for input checking
                    app_window = omni.appwindow.get_default_app_window()
                    if not app_window:
                        if self._config.debug_mode:
                            logger.warning("No app window for input polling")
                        return
                    mouse = app_window.get_mouse()
                    if not mouse:
                        if self._config.debug_mode:
                            logger.warning("No mouse device for input polling")
                        return
                    
                    # Check for LEFT CLICK (waypoint creation)
                    left_button_pressed = self._input_interface.is_mouse_button_pressed(mouse, carb.input.MouseInput.LEFT_BUTTON)
                    
                    # Detect LEFT BUTTON press (not held)
                    if left_button_pressed and not self._last_left_button_state:
                        self._last_left_button_state = True
                        
                        # Check if click is within viewport bounds
                        if self._is_click_within_viewport():
                            self._dinfo("🖱️ LEFT CLICK (WITHIN VIEWPORT) - Creating waypoint")
                            self._place_waypoint_at_crosshair()
                            
                            # Add small delay to prevent double-click issues
                            import time
                            time.sleep(0.5)  # 500ms delay to prevent double-click detection
                            if self._config.debug_mode:
                                self._dinfo("⏱️ Double-click prevention delay applied (500ms)")
                        else:
                            if self._config.debug_mode:
                                self._dinfo("🚫 LEFT CLICK (OUTSIDE VIEWPORT) - Ignoring click")
                    
                    elif not left_button_pressed:
                        self._last_left_button_state = False
                    
                    # Check for X KEY (waypoint removal) - using keyboard input
                    keyboard = app_window.get_keyboard()
                    if keyboard:
                        x_key_pressed = self._input_interface.is_key_pressed(keyboard, carb.input.KeyboardInput.X)
                        if x_key_pressed and not self._last_x_key_state:
                            self._last_x_key_state = True
                            self._dinfo("⌨️ X KEY PRESSED - Removing last waypoint")
                            self._remove_last_crosshair_waypoint()
                        elif not x_key_pressed:
                            self._last_x_key_state = False
                    
                except Exception as poll_e:
                    if self._config.debug_mode:
                        logger.warning(f"Polling error: {poll_e}")
            
            # Subscribe to update stream for polling
            update_stream = omni.kit.app.get_app().get_update_event_stream()
            self._crosshair_polling_subscription = update_stream.create_subscription_to_pop(
                poll_crosshair_input, name="crosshair_input_polling"
            )
            
        except Exception as e:
            logger.error(f"Error setting up crosshair input polling: {e}")
    
    def _is_click_within_viewport(self) -> bool:
        """Check if the current mouse click is within the viewport bounds."""
        try:
            # Get current mouse position
            app_window = omni.appwindow.get_default_app_window()
            if not app_window:
                if self._config.debug_mode:
                    logger.warning("No app window for mouse position check")
                return False
            
            mouse = app_window.get_mouse()
            if not mouse:
                if self._config.debug_mode:
                    logger.warning("No mouse device for position check")
                return False
            
            # Get mouse coordinates
            mouse_coords = self._input_interface.get_mouse_coords_pixel(mouse)
            if not mouse_coords:
                if self._config.debug_mode:
                    logger.warning("Could not get mouse coordinates")
                return False
            
            mouse_x, mouse_y = mouse_coords
            
            # Get viewport window and frame
            if not self._viewport_window or not hasattr(self._viewport_window, 'frame'):
                if self._config.debug_mode:
                    logger.warning("No viewport window/frame for bounds check")
                return False
            
            viewport_frame = self._viewport_window.frame
            if not viewport_frame:
                if self._config.debug_mode:
                    logger.warning("No viewport frame for bounds check")
                return False
            
            # Get viewport bounds (approximate)
            viewport_left = viewport_frame.screen_position_x
            viewport_top = viewport_frame.screen_position_y
            viewport_right = viewport_left + viewport_frame.computed_content_width
            viewport_bottom = viewport_top + viewport_frame.computed_content_height
            
            # Check if mouse is within bounds
            is_within = (viewport_left <= mouse_x <= viewport_right and 
                           viewport_top <= mouse_y <= viewport_bottom)
            
            if self._config.debug_mode:
                logger.info(f"🔍 VIEWPORT BOUNDS CHECK:")
                logger.info(f"   Mouse position: ({mouse_x:.1f}, {mouse_y:.1f})")
                logger.info(f"   Viewport bounds: ({viewport_left:.1f}, {viewport_top:.1f}) to ({viewport_right:.1f}, {viewport_bottom:.1f})")
                logger.info(f"   Within viewport: {is_within}")
            
            return is_within
            
        except Exception as e:
            logger.error(f"Error checking viewport bounds: {e}")
            return False
    
    def _place_waypoint_at_crosshair(self):
        """Create a waypoint at the crosshair position."""
        try:
            # Special handling for camera behavior waypoints - capture exact camera state
            if get_waypoint_type_behavior(self._selected_waypoint_type) == 'camera':
                self._capture_exact_waypoint()
                return
            
            # For all other waypoint types, use crosshair placement
            # Calculate crosshair world position using simple camera math
            camera_position, camera_forward = self._get_camera_position_and_forward()
            if not camera_position or not camera_forward:
                logger.error("❌ Could not get camera position and forward vector")
                return
            
            # Get current distance setting
            distance = self.toolbar_controller.get_current_distance()
            
            # Calculate waypoint position
            waypoint_position = [
                camera_position[0] + camera_forward[0] * distance,
                camera_position[1] + camera_forward[1] * distance,
                camera_position[2] + camera_forward[2] * distance
            ]
            
            if self._config.debug_mode:
                logger.info(f"🎯 CROSSHAIR PLACEMENT:")
                logger.info(f"   Distance: {distance}")
                logger.info(f"   Camera position: {camera_position}")
                logger.info(f"   Camera forward: {camera_forward}")
                logger.info(f"   Waypoint position: {waypoint_position}")
            
            # Create waypoint using HTTP API for thread safety
            import requests
            
            # Use the general create_waypoint HTTP endpoint for thread safety
            base_url = self._config.get_server_url()
            response = requests.post(
                f"{base_url}/create_waypoint",
                json={
                    'position': waypoint_position,
                    'waypoint_type': self._selected_waypoint_type,
                    'metadata': {'created_via': 'crosshair_click'}
                },
                timeout=5
            )
            
            if response.status_code == 200:
                result = response.json()
                self.toolbar_controller.show_capture_feedback(f"✅ {self._selected_waypoint_type} created")
                
                # Cache the waypoint ID for potential removal
                if 'waypoint_id' in result:
                    self._last_crosshair_waypoint_id = result['waypoint_id']
                
                if self._config.debug_mode:
                    logger.info(f"📷 {self._selected_waypoint_type} waypoint captured: {result.get('waypoint_id')}")
                
            else:
                logger.error(f"Failed to create crosshair waypoint: {response.status_code}")
                self.toolbar_controller.show_capture_feedback("❌ Failed to create waypoint")
                
        except Exception as e:
            logger.error(f"Error placing waypoint at crosshair: {e}")
            self.toolbar_controller.show_capture_feedback("❌ Error creating waypoint")
    
    def _remove_last_crosshair_waypoint(self):
        """Remove the last waypoint created via crosshair click."""
        try:
            # Check if we have a cached waypoint to remove
            if self._last_crosshair_waypoint_id is None:
                if self._config.debug_mode:
                    logger.info("No cached waypoint - ignoring removal request")
                return
            
            waypoint_id = self._last_crosshair_waypoint_id
            
            if self._config.debug_mode:
                logger.info(f"🗑️ Attempting to remove cached waypoint: {waypoint_id}")
            
            import requests
            
            base_url = self._config.get_server_url()
            response = requests.post(
                f"{base_url}/remove_waypoint",
                json={'waypoint_id': waypoint_id},
                timeout=5
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get('success'):
                    if self._config.debug_mode:
                        logger.info(f"✅ Waypoint {waypoint_id} removed successfully")
                    self.toolbar_controller.show_capture_feedback("Last waypoint removed")
                    self._last_crosshair_waypoint_id = None  # Clear cache
                else:
                    logger.error(f"Server reported failure: {data.get('message', 'Unknown error')}")
            else:
                logger.error(f"HTTP error removing waypoint: {response.status_code}")
                
        except Exception as e:
            logger.error(f"Error removing last crosshair waypoint: {e}")
    
    def _get_camera_position_and_forward(self) -> Tuple[Optional[list], Optional[list]]:
        """
        Get camera position and forward vector for waypoint placement calculations.
        
        Returns:
            Tuple of (camera_position, camera_forward) as lists, or (None, None) on error
        """
        try:
            import omni.usd
            from pxr import UsdGeom, Gf
            
            # Get the current stage
            stage = omni.usd.get_context().get_stage()
            if not stage:
                logger.error("No active USD stage")
                return None, None
            
            # Get active viewport camera
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
            transform_matrix = camera_xform.ComputeLocalToWorldTransform(omni.usd.get_context().get_time_code())
            
            # Extract position and forward vector
            camera_position = transform_matrix.ExtractTranslation()
            camera_position = [float(camera_position[0]), float(camera_position[1]), float(camera_position[2])]
            
            # Calculate forward vector (negative Z in camera space)
            forward_vec = transform_matrix.TransformDir(Gf.Vec3d(0, 0, -1))
            camera_forward = [float(forward_vec[0]), float(forward_vec[1]), float(forward_vec[2])]
            
            if self._config.debug_mode:
                logger.info(f"🔍 CAMERA DEBUG:")
                logger.info(f"   Camera path: {camera_path}")
                logger.info(f"   Camera position: {camera_position}")
                logger.info(f"   Camera forward: {camera_forward}")
            
            return camera_position, camera_forward
            
        except Exception as e:
            logger.error(f"Error getting camera position and forward: {e}")
            return None, None
    
    def _capture_exact_waypoint(self):
        """Capture exact camera waypoint with position and target information."""
        try:
            # Get camera position and forward for target calculation
            camera_position, camera_forward = self._get_camera_position_and_forward()
            if not camera_position or not camera_forward:
                logger.error("Could not get camera information")
                return
            
            # Calculate target point at a reasonable distance
            target_distance = 10.0  # Fixed distance for target calculation
            target_position = [
                camera_position[0] + camera_forward[0] * target_distance,
                camera_position[1] + camera_forward[1] * target_distance,
                camera_position[2] + camera_forward[2] * target_distance
            ]
            
            # Create waypoint with position and target
            import requests
            
            base_url = self._config.get_server_url()
            response = requests.post(
                f"{base_url}/create_waypoint",
                json={
                    'position': camera_position,
                    'waypoint_type': self._selected_waypoint_type,
                    'target': target_position,
                    'metadata': {
                        'created_via': 'camera_capture',
                        'camera_forward': camera_forward
                    }
                },
                timeout=5
            )
            
            if response.status_code == 200:
                result = response.json()
                if 'waypoint_id' in result:
                    self._last_crosshair_waypoint_id = result['waypoint_id']
                    if self._config.debug_mode:
                        logger.info(f"✅ Crosshair waypoint created and cached: {self._last_crosshair_waypoint_id}")
                else:
                    if self._config.debug_mode:
                        logger.info(f"✅ Crosshair waypoint created: {result}")
                
                self.toolbar_controller.show_capture_feedback(f"✅ {self._selected_waypoint_type} captured")
            else:
                logger.error(f"Failed to create exact waypoint: {response.status_code}")
                
        except Exception as e:
            logger.error(f"Error capturing exact waypoint: {e}")
    
    def _hide_crosshair(self):
        """Hide and cleanup crosshair overlay."""
        try:
            if self._crosshair_window:
                self._crosshair_window.destroy()
                self._crosshair_window = None
                self._dinfo("🎯 Crosshair overlay hidden")
        except Exception as e:
            logger.error(f"Error hiding crosshair: {e}")
    
    def _cleanup_crosshair_system(self):
        """Clean up all crosshair-related resources."""
        try:
            # Stop polling
            self._polling_active = False
            
            # Clean up crosshair polling subscription
            if hasattr(self, '_crosshair_polling_subscription') and self._crosshair_polling_subscription:
                try:
                    self._crosshair_polling_subscription.unsubscribe()
                    self._crosshair_polling_subscription = None
                    self._dinfo("🔄 Crosshair polling subscription cleaned up")
                except Exception as e:
                    logger.warning(f"Error unsubscribing crosshair polling: {e}")
            
            # Hide crosshair overlay
            self._hide_crosshair()
            
            # Clear references
            self._input_interface = None
            self._viewport_window = None
            
        except Exception as e:
            logger.error(f"Error cleaning up crosshair system: {e}")
    
    def cleanup(self):
        """Full cleanup of crosshair handler."""
        try:
            if self._is_capture_mode:
                self.exit_capture_mode()
            self._cleanup_crosshair_system()
            
        except Exception as e:
            logger.error(f"Error in crosshair handler cleanup: {e}")
    
    # Debug helpers
    def _dinfo(self, msg: str):
        """Debug info logging."""
        if self._config.debug_mode:
            logger.info(msg)