#!/usr/bin/env python3
"""
Waypoint Toolbar Integration for Isaac Sim

Provides a toolbar button for quick waypoint capture with scroll wheel type selection.
Integrates with the main Isaac Sim toolbar alongside select/move/rotate tools.
"""

import logging
from typing import Optional, Dict, Any, List
from carb.input import KeyboardInput as Key

from .waypoint_types import WaypointTypeRegistry
from .crosshair_handler import CrosshairInteractionHandler
from .input_handler import WaypointInputHandler
from .waypoint_capture import WaypointCaptureHandler
from .ui_components import UIComponentsHandler

try:
    import omni.ui as ui
    from omni.kit.widget.toolbar import WidgetGroup, get_instance as get_toolbar_instance
    from omni.kit.widget.toolbar import Hotkey
    UI_AVAILABLE = True
except ImportError:
    UI_AVAILABLE = False
    logging.warning("omni.ui or toolbar widgets not available")

try:
    import omni.kit.viewport.utility
    VIEWPORT_AVAILABLE = True
except ImportError:
    VIEWPORT_AVAILABLE = False
    logging.warning("Viewport utility not available")

logger = logging.getLogger(__name__)

# Global tracking to prevent multiple instances
_GLOBAL_TOOLBAR_WIDGET = None
_GLOBAL_TOOLBAR_MANAGER = None


class WaypointCaptureToolbar(WidgetGroup):
    """
    Waypoint capture toolbar widget with scroll wheel type selection.
    Integrates with Isaac Sim's main toolbar for quick waypoint creation.
    """
    
    # Waypoint types now managed by dedicated feature module
    WAYPOINT_TYPES = WaypointTypeRegistry.get_all_types()
    
    def __init__(self, waypoint_manager):
        """
        Initialize waypoint capture toolbar.
        
        Args:
            waypoint_manager: Instance of WaypointManager for creating waypoints
        """
        import traceback
        super().__init__()
        
        # Load configuration first to access debug flags
        from ..config import get_config
        self._config = get_config()
        
        # DEBUG: Track widget creation
        if self._config.debug_mode:
            logger.info("🎯 WaypointCaptureToolbar.__init__() called")
            logger.info(f"🔍 Widget creation stack trace:")
            for line in traceback.format_stack()[-5:]:
                logger.info(f"   {line.strip()}")
        
        self.waypoint_manager = waypoint_manager
        
        self._toolbar_button = None
        self._is_capture_mode = False
        self._selected_waypoint_type = WaypointTypeRegistry.get_default_type_id()
        self._click_subscription = None
        
        # UI references
        self._main_button = None
        self._is_active = False
        self._toolbar_instance = None
        
        # Initialize crosshair interaction handler
        self._crosshair_handler = CrosshairInteractionHandler(
            waypoint_manager, self, self._config
        )
        
        # Initialize input handler for hotkeys and scroll wheel
        self._input_handler = WaypointInputHandler(self, self._config)
        
        # Initialize waypoint capture handler
        self._capture_handler = WaypointCaptureHandler(waypoint_manager, self, self._config)
        
        # Initialize UI components handler
        self._ui_handler = UIComponentsHandler(self, self._config)
        
        if self._config.debug_mode:
            logger.info("WaypointCaptureToolbar initialized")

    # Debug logging helpers to reduce release noise
    def _dinfo(self, msg: str):
        try:
            if self._config.debug_mode:
                logger.info(msg)
        except Exception:
            pass

    def _dwarn(self, msg: str):
        try:
            if self._config.debug_mode:
                logger.warning(msg)
        except Exception:
            pass
    
    def clean(self):
        """Clean up toolbar widget and resources following Omniverse pattern."""
        try:
            self._dinfo("🧹 WaypointCaptureToolbar clean() - following Omniverse pattern")
            
            # Clean subscriptions first
            if self._click_subscription:
                self._click_subscription.unsubscribe()
            self._click_subscription = None
            
            
            # Clean up input handler
            if hasattr(self, '_input_handler') and self._input_handler:
                self._input_handler.cleanup()
                self._input_handler = None
                
            # Clean up capture handler
            if hasattr(self, '_capture_handler'):
                self._capture_handler = None
                
            # Clean up UI handler
            if hasattr(self, '_ui_handler') and self._ui_handler:
                self._ui_handler.cleanup_ui_components()
                self._ui_handler = None
            
            # Clean up viewport interactions
            self.cleanup()
            
            # Nullify ALL references (following pattern)
            self._main_button = None
            self._toolbar_button = None
            self._is_active = False
            self._toolbar_instance = None
            self.waypoint_manager = None
            self._selected_waypoint_type = None
            self._is_capture_mode = False
            
            self._dinfo("✅ WaypointCaptureToolbar clean() completed")
            
        except Exception as e:
            logger.error(f"❌ Error in WaypointCaptureToolbar clean(): {e}")
            
        # ALWAYS call super().clean() at the end (Omniverse pattern)
        super().clean()
    
    def get_style(self):
        """Define custom styling for the waypoint toolbar button."""
        return {
            "Button.Image::waypoint_capture": {
                "image_url": "${glyphs}/camera.svg",  # Use camera icon for waypoint capture
                "color": 0xFFFFFFFF  # White color like other toolbar icons
            },
            "Button.Image::waypoint_capture:checked": {
                "image_url": "${glyphs}/camera.svg", 
                "color": 0xFF0088FF  # Blue when active
            }
        }
    
    def create(self, default_size):
        """
        Create the main toolbar button UI.
        
        Args:
            default_size: Standard toolbar button size
        """
        if not UI_AVAILABLE:
            logger.error("Cannot create toolbar - UI not available")
            return None
            
        try:
            # Create main waypoint capture button only
            # Note: For now, simplifying to just the main button to avoid toolbar integration issues
            # Button handles waypoint capture mode toggle
            self._main_button = ui.ToolButton(
                name="waypoint_capture",
                width=default_size,
                height=default_size,
                tooltip=f"Waypoint Capture Tool - Capture: Click - Scroll Current: {self._get_current_type_name()}"
            )
            
            # Subscribe to both toggle state changes and click events
            self._main_button.model.subscribe_value_changed_fn(self._on_toolbar_button_toggled)
            # Alternative: use clicked_fn for immediate response
            self._main_button.set_clicked_fn(self._on_toolbar_button_clicked)
            
            # Set scroll wheel handler with debug logging
            self._main_button.set_mouse_wheel_fn(self._on_scroll_wheel)
            self._dinfo("🔄 Scroll wheel handler attached to waypoint button")
            self._dinfo("🔄 Button click handler attached to waypoint button")
            
            self._is_active = False
            
            # Main button click toggles waypoint capture mode
            
            # Input handler manages hotkeys automatically
            
            # Create distance input field that allows typing exact values
            self._distance_slider = ui.FloatField(
                width=80,  # Compact width for toolbar
                height=default_size,
                tooltip=f"Waypoint Distance: {self._config.waypoint_distance_min}-{self._config.waypoint_distance_max} units (type exact value)"
            )
            
            # Set initial value and step interval
            self._distance_slider.model.set_value(self._config.waypoint_distance_default)
            # Note: Isaac Sim UI doesn't expose step directly, but we'll use it in logic
            
            # Subscribe to field value changes for real-time feedback
            self._distance_slider.model.subscribe_value_changed_fn(self._on_distance_changed)
            
            self._dinfo("Waypoint capture toolbar button and distance slider created")
            # Return dictionary as required by toolbar system - include both widgets
            return {
                "waypoint_capture": self._main_button,
                "waypoint_distance_slider": self._distance_slider
            }
            
        except Exception as e:
            logger.error(f"Error creating waypoint capture toolbar: {e}")
            return None
    
    
    def _on_scroll_wheel(self, x, y, modifier):
        """Handle scroll wheel - delegate to input handler."""
        self._input_handler.handle_scroll_wheel(x, y, modifier)
    
    def handle_scroll_type_change(self, y):
        """Handle scroll wheel type change (callback for input handler)."""
        try:
            # Debug logging
            self._dinfo(f"🔄 Scroll wheel event: active={self._is_active}, y={y}")
            
            # Only allow scrolling when tool is active
            if not self._is_active:
                self._dinfo("⚠️ Scroll ignored - tool not active. Click camera button first!")
                self.show_capture_feedback("Activate waypoint tool first (click camera button)")
                return
                
            # Get current index
            current_index = next((i for i, wtype in enumerate(self.WAYPOINT_TYPES) 
                                if wtype["id"] == self._selected_waypoint_type), 0)
            
            # Scroll up = previous type, scroll down = next type
            if y > 0:  # Scroll up
                next_index = (current_index - 1) % len(self.WAYPOINT_TYPES)
            else:  # Scroll down  
                next_index = (current_index + 1) % len(self.WAYPOINT_TYPES)
                
            self._selected_waypoint_type = self.WAYPOINT_TYPES[next_index]["id"]
            
            # Update tooltip
            current_name = self._get_current_type_name()
            if self._main_button:
                self._main_button.tooltip = f"Waypoint Capture Tool - Capture: Click - Scroll Current: {current_name}"
            
            self._dinfo(f"Scroll changed waypoint type to: {self._selected_waypoint_type}")
            self.show_capture_feedback(f"Selected: {current_name}")
            
        except Exception as e:
            logger.error(f"Error handling scroll wheel: {e}")
            
    def handle_hotkey_capture(self):
        """Handle hotkey capture (callback for input handler)."""
        try:
            # Delegate to capture handler
            self._capture_handler.capture_camera_waypoint(self._selected_waypoint_type)
            self._dinfo(f"Quick waypoint capture via hotkey: {self._selected_waypoint_type}")
        except Exception as e:
            logger.error(f"Error in hotkey capture: {e}")
    
    def _on_distance_changed(self, model):
        """Handle distance slider value changes - delegate to UI handler."""
        self._ui_handler.handle_distance_change(model)
    
    def _on_toolbar_button_toggled(self, model):
        """Handle main toolbar button toggle - delegate to UI handler."""
        self._ui_handler.handle_toolbar_button_toggled(model)
    
    def handle_button_toggle(self, is_active: bool):
        """Handle button toggle state change (callback for UI handler)."""
        try:
            self._is_active = is_active
            current_name = self._get_current_type_name()
            
            if self._is_active:
                self._dinfo(f"Waypoint capture tool ACTIVATED - Type: {self._selected_waypoint_type}")
                self.show_capture_feedback(f"Waypoint tool active: {current_name}")
                # Acquire toolbar context like other tools
                self._acquire_toolbar_context()
            else:
                self._dinfo("Waypoint capture tool DEACTIVATED")
                self.show_capture_feedback("Waypoint tool deactivated")
                # Release toolbar context
                self._release_toolbar_context()
                
        except Exception as e:
            logger.error(f"Error handling toolbar button toggle: {e}")
    
    def _on_toolbar_button_clicked(self):
        """Handle direct button clicks - delegate to UI handler."""
        self._ui_handler.handle_toolbar_button_clicked()
    
    def handle_button_click(self):
        """Handle button click event (callback for UI handler)."""
        try:
            # Toggle the active state manually since ToolButton might not handle toggle properly
            self._is_active = not self._is_active
            current_name = self._get_current_type_name()
            
            # Update button visual state
            if self._main_button and hasattr(self._main_button.model, 'set_value'):
                self._main_button.model.set_value(self._is_active)
            
            if self._is_active:
                self._dinfo(f"Waypoint capture tool ACTIVATED via click - Type: {self._selected_waypoint_type}")
                self.show_capture_feedback(f"Waypoint tool active: {current_name}")
                # Acquire toolbar context like other tools
                self._acquire_toolbar_context()
                # Enter capture mode for viewport clicks
                self._enter_capture_mode()
            else:
                self._dinfo("Waypoint capture tool DEACTIVATED via click")
                self.show_capture_feedback("Waypoint tool deactivated")
                # Release toolbar context
                self._release_toolbar_context()
                # Exit capture mode
                self._exit_capture_mode()
                
        except Exception as e:
            logger.error(f"Error handling toolbar button click: {e}")
    
    def _acquire_toolbar_context(self):
        """Acquire exclusive toolbar context like other Isaac Sim tools."""
        try:
            # Get toolbar instance and acquire context
            if self._toolbar_instance:
                # Some Isaac Sim tools acquire context to become the active tool
                self._dinfo("Acquiring toolbar context for waypoint tool")
            else:
                self._dwarn("No toolbar instance available for context acquisition")
        except Exception as e:
            logger.error(f"Error acquiring toolbar context: {e}")
    
    def _release_toolbar_context(self):
        """Release toolbar context when tool is deactivated."""
        try:
            # Release exclusive context
            if self._toolbar_instance:
                self._dinfo("Releasing toolbar context for waypoint tool")
            else:
                self._dwarn("No toolbar instance available for context release")
        except Exception as e:
            logger.error(f"Error releasing toolbar context: {e}")
    
    def _get_current_type_name(self) -> str:
        """Get the display name of the currently selected waypoint type."""
        return WaypointTypeRegistry.get_type_name(self._selected_waypoint_type)
    
    def _get_next_waypoint_number(self, waypoint_type: str) -> int:
        """Get the next available number for a waypoint type, accounting for deleted waypoints."""
        try:
            # Get all existing waypoint names of the same type
            existing_names = []
            for wp in self.waypoint_manager._waypoints.values():
                if wp.waypoint_type == waypoint_type:
                    existing_names.append(wp.name)
            
            # Extract numbers from existing names
            existing_numbers = set()
            for name in existing_names:
                # Look for numbers at the end of names like "point_of_interest_crosshair_5" or "Camera Position 3"
                import re
                number_match = re.search(r'_(\d+)$|[ _](\d+)$', name)
                if number_match:
                    # Get whichever group matched (crosshair format or display format)
                    number = int(number_match.group(1) or number_match.group(2))
                    existing_numbers.add(number)
            
            # Find the next available number starting from 1
            next_number = 1
            while next_number in existing_numbers:
                next_number += 1
                
            return next_number
            
        except Exception as e:
            logger.error(f"Error finding next waypoint number: {e}")
            # Fallback to count + 1 if regex fails
            same_type_count = len([wp for wp in self.waypoint_manager._waypoints.values() 
                                 if wp.waypoint_type == waypoint_type])
            return same_type_count + 1
    
    def get_current_distance(self) -> float:
        """Get current distance setting from slider."""
        if hasattr(self, '_distance_slider') and self._distance_slider:
            return self._distance_slider.model.get_value_as_float()
        return self._config.waypoint_distance_default
    
    
    def _enter_capture_mode(self):
        """Enter crosshair-based waypoint placement mode."""
        try:
            if not VIEWPORT_AVAILABLE:
                logger.error("Viewport utilities not available for crosshair capture")
                return
            
            self._is_capture_mode = True
            
            # Set up crosshair and click handlers
            self._setup_crosshair_system()
            
            # Visual feedback
            self.show_capture_feedback(f"Crosshair active - Left click: place {self._get_current_type_name()}, X key: remove last")
            
            self._dinfo(f"Entered crosshair capture mode for {self._selected_waypoint_type}")
            
        except Exception as e:
            logger.error(f"Error entering crosshair capture mode: {e}")
    
    def _exit_capture_mode(self):
        """Exit crosshair capture mode and clean up handlers."""
        try:
            self._is_capture_mode = False
            
            # Clean up crosshair system
            self._cleanup_crosshair_system()
            
            # Visual feedback
            self.show_capture_feedback("Crosshair mode deactivated")
            
            self._dinfo("Exited crosshair capture mode")
            
        except Exception as e:
            logger.error(f"Error exiting crosshair capture mode: {e}")
    
    def _setup_crosshair_system(self):
        """Set up crosshair overlay and keyboard/mouse handlers for FPS-style waypoint placement."""
        try:
            # Import required modules
            from omni.kit.viewport.utility import get_active_viewport_window
            import carb.input
            
            # Get active viewport window
            viewport_window = get_active_viewport_window()
            if not viewport_window:
                logger.warning("Could not get active viewport window")
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
        """Display crosshair overlay in the center of the viewport."""
        try:
            from omni.kit.viewport.utility import get_active_viewport_window
            
            viewport_window = get_active_viewport_window()
            if not viewport_window:
                logger.warning("No active viewport window for crosshair")
                return
                
            # Create simple crosshair overlay using omni.ui
            # This creates a basic crosshair at viewport center
            try:
                # Get viewport frame for positioning
                viewport_frame = viewport_window.frame
                if viewport_frame:
                    # Create crosshair overlay window
                    self._crosshair_window = ui.Window(
                        "Crosshair", 
                        width=40, 
                        height=40,
                        flags=ui.WINDOW_FLAGS_NO_TITLE_BAR | ui.WINDOW_FLAGS_NO_RESIZE | ui.WINDOW_FLAGS_NO_BACKGROUND
                    )
                    
                    with self._crosshair_window.frame:
                        with ui.VStack():
                            ui.Spacer(height=18)
                            with ui.HStack():
                                ui.Spacer(width=18)
                                # Simple crosshair using UI elements
                                with ui.ZStack():
                                    ui.Rectangle(width=4, height=20, style={"background_color": 0xFF0000FF})  # Red vertical line
                                    ui.Rectangle(width=20, height=4, style={"background_color": 0xFF0000FF})  # Red horizontal line
                                ui.Spacer(width=18)
                            ui.Spacer(height=18)
                    
                    # Position crosshair at viewport center
                    self._position_crosshair_at_center(viewport_frame)
                    
                    self._dinfo("🎯 Crosshair displayed at viewport center")
                else:
                    logger.warning("Could not get viewport frame for crosshair positioning")
                    
            except Exception as ui_e:
                logger.warning(f"Could not create crosshair UI overlay: {ui_e}")
                # Fallback: just log that crosshair mode is active
                self._dinfo("🎯 Crosshair mode active (no visual overlay)")
            
        except Exception as e:
            logger.error(f"Error showing crosshair: {e}")
    
    def _position_crosshair_at_center(self, viewport_frame):
        """Position crosshair window at the center of the viewport."""
        try:
            if self._crosshair_window and viewport_frame:
                # Calculate center position
                center_x = viewport_frame.screen_position_x + (viewport_frame.computed_width // 2) - 20
                center_y = viewport_frame.screen_position_y + (viewport_frame.computed_height // 2) - 20
                
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
                    # Get mouse device
                    import omni.appwindow
                    import carb.input
                    
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
                    
                    # Check left mouse button
                    left_value = self._input_interface.get_mouse_value(mouse, carb.input.MouseInput.LEFT_BUTTON)
                    left_pressed = left_value > 0
                    
                    # Check 'x' key for waypoint removal
                    keyboard = app_window.get_keyboard()
                    x_pressed = self._input_interface.get_keyboard_value(keyboard, carb.input.KeyboardInput.X) if keyboard else False
                    
                    # Debug: Log polling activity every 60 frames
                    if self._config.debug_mode:
                        if not hasattr(self, '_debug_poll_counter'):
                            self._debug_poll_counter = 0
                        self._debug_poll_counter += 1
                        if self._debug_poll_counter % 60 == 0:
                            self._dinfo(f"🔄 Input polling active: L={left_pressed}, X={x_pressed}")
                    
                    # Detect left click (place waypoint) - CHECK VIEWPORT BOUNDS FIRST
                    if left_pressed and not self._last_left_button_state:
                        # CRITICAL FIX: Validate click is within viewport before placing waypoint
                        if self._is_click_within_viewport():
                            self._dinfo("🎯 LEFT CLICK (WITHIN VIEWPORT) - Placing waypoint at crosshair")
                            self._place_waypoint_at_crosshair()
                            
                            # MICROSLEEP: Prevent accidental double-clicks from registering twice
                            import time
                            time.sleep(0.5)  # 500ms delay to prevent double-click detection
                            if self._config.debug_mode:
                                self._dinfo("⏱️ Double-click prevention delay applied (500ms)")
                        else:
                            if self._config.debug_mode:
                                self._dinfo("🚫 LEFT CLICK (OUTSIDE VIEWPORT) - Ignoring click")
                    
                    # Detect 'x' key press (remove last waypoint)
                    if x_pressed and not self._last_x_key_state:
                        self._dinfo("🎯 X KEY - Removing last waypoint")
                        self._remove_last_waypoint()
                    
                    self._last_left_button_state = left_pressed
                    self._last_x_key_state = x_pressed
                    
                except Exception as e:
                    logger.error(f"Error in crosshair input polling: {e}")
            
            # Create polling timer
            update_stream = omni.kit.app.get_app().get_update_event_stream()
            self._crosshair_polling_subscription = update_stream.create_subscription_to_pop(
                poll_crosshair_input,
                name="waypoint_crosshair_polling"
            )
            
            self._dinfo("✅ Crosshair input polling setup completed")
            
        except Exception as e:
            logger.error(f"Error setting up crosshair input polling: {e}")
    
    def _is_click_within_viewport(self) -> bool:
        """
        Check if current mouse position is within the Isaac Sim viewport bounds.
        
        Returns:
            bool: True if mouse is within viewport, False otherwise
        """
        try:
            # Get current mouse position using correct carb.input API
            import omni.appwindow
            import carb.input
            
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
            
            # FIXED: Use correct carb.input API for mouse coordinates
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
            
            # Get viewport bounds
            viewport_left = viewport_frame.screen_position_x
            viewport_top = viewport_frame.screen_position_y
            viewport_right = viewport_left + viewport_frame.computed_width
            viewport_bottom = viewport_top + viewport_frame.computed_height
            
            # Check if mouse is within viewport bounds
            within_bounds = (viewport_left <= mouse_x <= viewport_right and 
                           viewport_top <= mouse_y <= viewport_bottom)
            
            if self._config.debug_mode:
                logger.info(f"🔍 VIEWPORT BOUNDS CHECK:")
                logger.info(f"   Mouse position: ({mouse_x:.1f}, {mouse_y:.1f})")
                logger.info(f"   Viewport bounds: ({viewport_left:.1f}, {viewport_top:.1f}) to ({viewport_right:.1f}, {viewport_bottom:.1f})")
                logger.info(f"   Within viewport: {within_bounds}")
            
            return within_bounds
            
        except Exception as e:
            logger.error(f"Error checking viewport bounds: {e}")
            # Default to allowing clicks if we can't determine bounds
            return True
    
    def _place_waypoint_at_crosshair(self):
        """Place waypoint - camera waypoints capture exact camera state, others use crosshair placement."""
        try:
            # Special handling for camera behavior waypoints - capture exact camera state
            if WaypointTypeRegistry.get_type_behavior(self._selected_waypoint_type) == 'camera':
                self._capture_handler.capture_exact_waypoint(self._selected_waypoint_type)
                return
            
            # For all other waypoint types, use crosshair placement
            # Calculate crosshair world position using simple camera math
            camera_position, camera_forward = self._capture_handler.get_camera_position_and_forward()
            if not camera_position or not camera_forward:
                logger.error("❌ Could not get camera position and forward vector")
                return
            
            # Get distance from slider
            distance = self.get_current_distance()
            
            # Calculate waypoint position: camera + (forward * distance)
            waypoint_position = [
                camera_position[0] + camera_forward[0] * distance,
                camera_position[1] + camera_forward[1] * distance,
                camera_position[2] + camera_forward[2] * distance
            ]
            
            if self._config.debug_mode:
                logger.info(f"🎯 CROSSHAIR PLACEMENT:")
                logger.info(f"   Distance: {distance}")
                logger.info(f"   Waypoint position: {waypoint_position}")
            
            # Create waypoint using HTTP API
            self._capture_handler.create_waypoint_via_http(waypoint_position, self._selected_waypoint_type)
            
        except Exception as e:
            logger.error(f"Error placing waypoint at crosshair: {e}")
    
    
    def _remove_last_waypoint(self):
        """Remove the most recently placed crosshair waypoint."""
        try:
            # Check if we have a cached waypoint to remove
            if self._last_crosshair_waypoint_id is None:
                if self._config.debug_mode:
                    logger.info("No cached waypoint - ignoring removal request")
                return
            
            waypoint_id = self._last_crosshair_waypoint_id
            
            if self._config.debug_mode:
                logger.info(f"🗑️ Attempting to remove cached waypoint: {waypoint_id}")
            
            # Use correct remove_waypoint POST endpoint
            import requests

            base_url = self._config.get_server_url()
            response = requests.post(
                f"{base_url}/waypoints/remove",
                json={'waypoint_id': waypoint_id},
                timeout=5.0,
                headers={'Content-Type': 'application/json'}
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get('success'):
                    if self._config.debug_mode:
                        logger.info(f"✅ Waypoint {waypoint_id} removed successfully")
                    self.show_capture_feedback("Last waypoint removed")
                else:
                    logger.info(f"Failed to remove waypoint: {data.get('error', 'Unknown error')}")
                    self.show_capture_feedback("Waypoint not found")
            else:
                logger.info(f"Unable to remove waypoint {waypoint_id}: {response.status_code}")
                self.show_capture_feedback("Unable to remove waypoint")
            
            # Always clear the cache after removal attempt
            self._last_crosshair_waypoint_id = None
                
        except requests.RequestException as http_e:
            logger.info(f"Network error removing waypoint {waypoint_id}: {http_e}")
            self.show_capture_feedback("Network error removing waypoint")
            # Clear cache even on network error
            self._last_crosshair_waypoint_id = None
        except Exception as e:
            logger.info(f"Error removing waypoint: {e}")
            self.show_capture_feedback("Error removing waypoint")
            # Clear cache even on error
            self._last_crosshair_waypoint_id = None
    
    
    
    def _cleanup_crosshair_system(self):
        """Clean up crosshair system resources."""
        try:
            # Stop polling
            if hasattr(self, '_polling_active'):
                self._polling_active = False
            
            # Clean up crosshair polling subscription
            if hasattr(self, '_crosshair_polling_subscription') and self._crosshair_polling_subscription:
                try:
                    self._crosshair_polling_subscription.unsubscribe()
                    logger.info("✅ Crosshair polling subscription removed")
                except Exception as e:
                    logger.debug(f"Error removing crosshair polling subscription: {e}")
                self._crosshair_polling_subscription = None
            
            # Hide crosshair overlay
            self._hide_crosshair()
            
            # Clear references
            self._viewport_window = None
            self._input_interface = None
            
            # Clear waypoint cache
            self._last_crosshair_waypoint_id = None
            
            logger.info("✅ Crosshair system cleaned up")
            
        except Exception as e:
            logger.error(f"❌ Error cleaning up crosshair system: {e}")
    
    def _hide_crosshair(self):
        """Hide crosshair overlay."""
        try:
            if hasattr(self, '_crosshair_window') and self._crosshair_window:
                self._crosshair_window.visible = False
                self._crosshair_window.destroy()
                self._crosshair_window = None
                logger.info("🎯 Crosshair hidden")
            
        except Exception as e:
            logger.error(f"Error hiding crosshair: {e}")
    
    def show_capture_feedback(self, message: str):
        """Show user feedback for waypoint capture operations - delegate to UI handler."""
        self._ui_handler.show_capture_feedback(message)
    
    def cleanup(self):
        """Clean up crosshair system and other resources."""
        try:
            # Clean up crosshair system first
            if hasattr(self, '_is_capture_mode') and self._is_capture_mode:
                self._cleanup_crosshair_system()
            
            # Clean up legacy mouse event subscription (Kit official API)
            if hasattr(self, '_mouse_event_subscription') and self._mouse_event_subscription:
                try:
                    self._mouse_event_subscription.unsubscribe()
                    logger.info("Legacy mouse event subscription removed during cleanup")
                except Exception as e:
                    logger.debug(f"Error removing mouse event subscription during cleanup: {e}")
                self._mouse_event_subscription = None
            
            # Clean up legacy mouse polling subscription
            if hasattr(self, '_mouse_polling_subscription') and self._mouse_polling_subscription:
                try:
                    if hasattr(self, '_polling_active'):
                        self._polling_active = False  # Stop polling first
                    self._mouse_polling_subscription.unsubscribe()
                    logger.info("Legacy mouse polling subscription removed during cleanup")
                except Exception as e:
                    logger.debug(f"Error removing mouse polling subscription during cleanup: {e}")
                self._mouse_polling_subscription = None
            
            # Clean up references
            self._raycast_query = None
            self._viewport_window = None
            self._click_gesture = None
            self._check_for_mouse_click = None
            
            logger.info("✅ Toolbar cleanup completed")
            
        except Exception as e:
            logger.error(f"Error during toolbar cleanup: {e}")


class WaypointToolbarManager:
    """
    Manager class for integrating waypoint capture toolbar with Isaac Sim.
    """
    
    def __init__(self, waypoint_manager):
        """
        Initialize the toolbar manager.
        
        Args:
            waypoint_manager: Instance of WaypointManager
        """
        self.waypoint_manager = waypoint_manager
        self._toolbar_widget = None
        self._toolbar_instance = None

    # Debug helpers
    def _debug_enabled(self) -> bool:
        try:
            return bool(getattr(self.waypoint_manager, '_config', None) and self.waypoint_manager._config.debug_mode)
        except Exception:
            return False

    def _dinfo(self, msg: str):
        if self._debug_enabled():
            logger.info(msg)

    def _dwarn(self, msg: str):
        if self._debug_enabled():
            logger.warning(msg)
        
    def setup_toolbar(self) -> bool:
        """
        Set up the waypoint capture toolbar in Isaac Sim with global tracking.
        
        Returns:
            bool: True if successfully set up, False otherwise
        """
        global _GLOBAL_TOOLBAR_WIDGET, _GLOBAL_TOOLBAR_MANAGER
        
        try:
            # DEBUG: Track setup calls
            if hasattr(self, 'waypoint_manager') and hasattr(self.waypoint_manager, '_config') and self.waypoint_manager._config.debug_mode:
                import traceback
                logger.info("🔧 WaypointToolbarManager.setup_toolbar() called")
                logger.info(f"🔍 Setup call stack trace:")
                for line in traceback.format_stack()[-3:]:
                    logger.info(f"   {line.strip()}")
            
            if not UI_AVAILABLE:
                logger.error("Cannot setup toolbar - UI not available")
                return False
            
            # FORCE CLEANUP: Remove any existing camera icons from toolbar
            self._dinfo("🧹 Force cleaning any existing camera widgets from toolbar")
            self._force_cleanup_camera_widgets()
            
            self._dinfo("🔄 Proceeding with clean setup")
            
            # Get the global toolbar instance first
            self._toolbar_instance = get_toolbar_instance()
            
            # Create the toolbar widget and pass toolbar instance
            self._toolbar_widget = WaypointCaptureToolbar(self.waypoint_manager)
            self._toolbar_widget._toolbar_instance = self._toolbar_instance
            
            # Set global tracking
            _GLOBAL_TOOLBAR_WIDGET = self._toolbar_widget
            _GLOBAL_TOOLBAR_MANAGER = self
            
            # Add to toolbar with priority (higher number = more to the right)
            self._toolbar_instance.add_widget(
                widget_group=self._toolbar_widget,
                priority=200  # Place after standard tools but before play controls
            )
            
            self._dinfo("✅ Waypoint capture toolbar successfully added with global tracking")
            return True
            
        except Exception as e:
            logger.error(f"Error setting up waypoint toolbar: {e}")
            return False
    
    def cleanup_toolbar(self):
        """Clean up and remove waypoint toolbar following EXACT Omniverse documentation pattern."""
        import threading
        
        try:
            self._dinfo("🧹 Starting toolbar cleanup - following exact Omniverse pattern")
            current_thread = threading.current_thread().name
            thread_id = threading.get_ident()
            self._dinfo(f"🔄 Cleanup running in thread: {current_thread} (ID: {thread_id})")
            
            # CRITICAL: UI operations must be on main thread
            main_thread_name = "MainThread"
            if "shutdown" in current_thread.lower() or "http" in current_thread.lower():
                raise RuntimeError(f"CRITICAL ERROR: Toolbar cleanup called from background thread '{current_thread}'! UI operations must be on main thread.")
            
            # First clean up hotkeys and subscriptions before touching widgets
            self._dinfo("🔄 Cleaning hotkeys and subscriptions first")
            if self._toolbar_widget and hasattr(self._toolbar_widget, 'clean'):
                self._dinfo("Calling toolbar widget clean() method")
                self._toolbar_widget.clean()
            else:
                self._dinfo("No toolbar widget to clean or no clean method")
            
            if self._toolbar_widget and self._toolbar_instance:
                try:
                    # EXACT Omniverse pattern: 
                    # 1. Remove from toolbar FIRST
                    # 2. Clean the widget  
                    # 3. Delete the widget
                    
                    # Check if we're in a shutdown thread - use different approach
                    if "shutdown" in current_thread.lower():
                        self._dinfo("⚠️ In shutdown thread - using safe cleanup approach")
                        # Just clean and delete - let toolbar handle removal naturally
                        self._toolbar_widget.clean()
                        del self._toolbar_widget
                        self._toolbar_widget = None
                        self._dinfo("✅ Safe shutdown cleanup completed")
                    else:
                        self._dinfo("🔄 Normal thread - using full Omniverse pattern")
                        
                        # Step 1: Remove widget from toolbar (Omniverse pattern)
                        self._dinfo("🔄 Step 1: toolbar.remove_widget()")
                        result = self._toolbar_instance.remove_widget(self._toolbar_widget)
                        
                        # Handle coroutine if returned
                        import asyncio
                        if asyncio.iscoroutine(result):
                            result.close()  # Just close it to prevent warnings
                        
                        # Step 2: Clean the widget (Omniverse pattern)
                        self._dinfo("🔄 Step 2: widget.clean()")
                        self._toolbar_widget.clean()
                        
                        # Step 3: Delete the widget (Omniverse pattern)
                        self._dinfo("🔄 Step 3: del widget")
                        del self._toolbar_widget
                        self._toolbar_widget = None
                        
                        self._dinfo("✅ Full Omniverse pattern cleanup completed")
                    
                except Exception as e:
                    logger.warning(f"⚠️ Cleanup failed: {e}")
                    # Emergency fallback
                    if self._toolbar_widget:
                        try:
                            self._toolbar_widget.clean()
                            self._toolbar_widget = None
                        except Exception as e:
                            self._toolbar_widget = None
            
            self._toolbar_instance = None
            
            # Clear global tracking
            global _GLOBAL_TOOLBAR_WIDGET, _GLOBAL_TOOLBAR_MANAGER
            if _GLOBAL_TOOLBAR_WIDGET == self._toolbar_widget:
                _GLOBAL_TOOLBAR_WIDGET = None
            if _GLOBAL_TOOLBAR_MANAGER == self:
                _GLOBAL_TOOLBAR_MANAGER = None
            
            self._dinfo("✅ Toolbar cleanup completed with global tracking cleared")
            
        except Exception as e:
            logger.error(f"❌ Error in toolbar cleanup: {e}")
    
    def is_active(self) -> bool:
        """Check if the toolbar is currently active."""
        return self._toolbar_widget is not None
    
    def _simple_cleanup(self):
        """Simple cleanup that doesn't interact with toolbar instance to avoid async issues."""
        try:
            self._dinfo("🧹 Simple cleanup: widget resources only")
            
            # Just clean widget resources without touching toolbar
            if self._toolbar_widget:
                self._toolbar_widget.clean()
                self._toolbar_widget = None
                self._dinfo("✅ Widget cleaned")
            
            # Clear references
            self._toolbar_instance = None
            self._dinfo("✅ Simple cleanup completed")
            
        except Exception as e:
            logger.error(f"❌ Error in simple cleanup: {e}")
    
    def _force_remove_existing_waypoint_widgets(self):
        """Force remove any existing waypoint widgets from toolbar to prevent duplicates."""
        try:
            # Get config for debug flag check
            if self._debug_enabled():
                logger.info("🔍 Checking for existing waypoint widgets in toolbar")
            
            # Get toolbar instance
            toolbar_instance = get_toolbar_instance()
            if not toolbar_instance:
                self._dinfo("ℹ️ No toolbar instance available")
                return
            
            # Check if toolbar has widgets
            if not hasattr(toolbar_instance, '_widgets'):
                self._dinfo("ℹ️ Toolbar has no _widgets attribute")
                return
                
            widgets_to_remove = []
            
            # Find any widgets that look like waypoint widgets
            for widget in toolbar_instance._widgets:
                try:
                    # Check if this widget has waypoint-related attributes
                    if (hasattr(widget, '_main_button') or 
                        hasattr(widget, '_selected_waypoint_type') or
                        (hasattr(widget, '__class__') and 'waypoint' in widget.__class__.__name__.lower())):
                        widgets_to_remove.append(widget)
                        self._dinfo(f"🎯 Found existing waypoint widget: {widget.__class__.__name__}")
                except Exception as check_e:
                    # Skip widgets that can't be inspected
                    pass
            
            # Remove found waypoint widgets
            for widget in widgets_to_remove:
                try:
                    self._dinfo(f"🗑️ Force removing existing waypoint widget: {widget}")
                    # Clean the widget first
                    if hasattr(widget, 'clean'):
                        widget.clean()
                    # Remove from toolbar's widget list directly
                    if widget in toolbar_instance._widgets:
                        toolbar_instance._widgets.remove(widget)
                    self._dinfo("✅ Existing waypoint widget removed")
                except Exception as remove_e:
                    logger.warning(f"⚠️ Failed to remove existing widget: {remove_e}")
            
            if widgets_to_remove:
                self._dinfo(f"✅ Removed {len(widgets_to_remove)} existing waypoint widgets")
            else:
                self._dinfo("ℹ️ No existing waypoint widgets found")
                
        except Exception as e:
            logger.warning(f"⚠️ Error during force cleanup of existing widgets: {e}")
    
    def _cleanup_global_instances(self):
        """Clean up any existing global toolbar instances."""
        global _GLOBAL_TOOLBAR_WIDGET, _GLOBAL_TOOLBAR_MANAGER
        
        try:
            self._dinfo("🌍 Cleaning up global toolbar instances")
            
            # Clean up global widget
            if _GLOBAL_TOOLBAR_WIDGET is not None:
                try:
                    self._dinfo("🗑️ Cleaning global toolbar widget")
                    _GLOBAL_TOOLBAR_WIDGET.clean()
                    self._dinfo("✅ Global widget cleaned")
                except Exception as e:
                    logger.warning(f"⚠️ Error cleaning global widget: {e}")
                _GLOBAL_TOOLBAR_WIDGET = None
            
            # Clean up global manager
            if _GLOBAL_TOOLBAR_MANAGER is not None:
                try:
                    self._dinfo("🗑️ Cleaning global toolbar manager")
                    if _GLOBAL_TOOLBAR_MANAGER != self:  # Don't clean ourselves
                        _GLOBAL_TOOLBAR_MANAGER.cleanup_toolbar()
                    self._dinfo("✅ Global manager cleaned")
                except Exception as e:
                    logger.warning(f"⚠️ Error cleaning global manager: {e}")
                _GLOBAL_TOOLBAR_MANAGER = None
            
            self._dinfo("✅ Global instances cleanup completed")
            
        except Exception as e:
            logger.error(f"❌ Error during global cleanup: {e}")
    
    def _force_cleanup_camera_widgets(self):
        """Aggressively remove any camera widgets from toolbar to fix accumulation."""
        try:
            # Get config for debug flag check
            if self._debug_enabled():
                logger.info("🔍 Scanning toolbar for camera widgets to remove")
            
            toolbar_instance = get_toolbar_instance()
            if not toolbar_instance or not hasattr(toolbar_instance, '_widgets'):
                self._dinfo("ℹ️ No toolbar or widgets to scan")
                return
            
            widgets_removed = 0
            widgets_to_remove = []
            
            # Find widgets that look like camera/waypoint widgets
            for widget in toolbar_instance._widgets[:]:  # Copy list to avoid modification during iteration
                try:
                    # Check for camera-related widgets
                    is_camera_widget = False
                    
                    # Check class name
                    if hasattr(widget, '__class__') and 'waypoint' in widget.__class__.__name__.lower():
                        is_camera_widget = True
                        self._dinfo(f"🎯 Found waypoint widget by class: {widget.__class__.__name__}")
                    
                    # Check for our specific widget attributes
                    elif (hasattr(widget, '_main_button') or 
                          hasattr(widget, '_selected_waypoint_type') or
                          hasattr(widget, '_is_capture_mode')):
                        is_camera_widget = True
                        self._dinfo(f"🎯 Found waypoint widget by attributes: {widget}")
                    
                    # Check for button with camera icon
                    elif hasattr(widget, '_main_button') and hasattr(widget._main_button, 'name'):
                        if 'waypoint' in str(widget._main_button.name).lower():
                            is_camera_widget = True
                            self._dinfo(f"🎯 Found waypoint widget by button name: {widget._main_button.name}")
                    
                    if is_camera_widget:
                        widgets_to_remove.append(widget)
                        
                except Exception as check_e:
                    # Skip widgets that can't be inspected
                    pass
            
            # Remove found widgets
            for widget in widgets_to_remove:
                try:
                    self._dinfo(f"🗑️ Force removing camera widget: {widget}")
                    
                    # Clean the widget first
                    if hasattr(widget, 'clean'):
                        widget.clean()
                    
                    # Remove from toolbar's widget list directly
                    if widget in toolbar_instance._widgets:
                        toolbar_instance._widgets.remove(widget)
                        widgets_removed += 1
                        
                except Exception as remove_e:
                    logger.warning(f"⚠️ Failed to remove camera widget: {remove_e}")
            
            self._dinfo(f"✅ Force removed {widgets_removed} camera widgets from toolbar")
            
        except Exception as e:
            logger.error(f"❌ Error during force camera widget cleanup: {e}")
