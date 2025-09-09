"""
UI components and interactions for WorldSurveyor waypoint management.

This module contains UI component handlers including distance slider management,
user feedback systems, and toolbar interactions. Extracted from monolithic
waypoint_toolbar.py for better feature separation and maintainability.
"""

import logging
from typing import Optional, Callable

try:
    import omni.ui as ui
    UI_AVAILABLE = True
except ImportError:
    UI_AVAILABLE = False
    logging.warning("omni.ui not available")

logger = logging.getLogger(__name__)


class UIComponentsHandler:
    """
    Handles UI component interactions and feedback systems.
    
    Manages distance slider interactions, user feedback display, tooltip updates,
    and other UI-related functionality for the waypoint toolbar system.
    """
    
    def __init__(self, toolbar_controller, config):
        """
        Initialize UI components handler.
        
        Args:
            toolbar_controller: Reference to main toolbar for UI updates
            config: Configuration object for UI settings and debug mode
        """
        self.toolbar_controller = toolbar_controller
        self._config = config
        
    def handle_distance_change(self, model):
        """
        Handle distance slider value changes with bounds checking and UI updates.
        
        Args:
            model: The UI model from the distance slider
        """
        try:
            # Get raw slider value
            raw_value = model.get_value_as_float()
            
            if self._config.debug_mode:
                logger.info(f"🔄 Distance slider changed: {raw_value:.2f}")
            
            # Ensure value stays within bounds (no interval snapping for text input)
            min_val = self._config.waypoint_distance_min
            max_val = self._config.waypoint_distance_max
            clamped_value = max(min_val, min(max_val, raw_value))
            
            # Only update if we had to clamp the value to prevent invalid float warnings
            if abs(raw_value - clamped_value) > 0.001:
                model.set_value(clamped_value)
                raw_value = clamped_value
            
            # Update tooltip with current distance
            self.update_main_button_tooltip(raw_value)
                
        except Exception as e:
            logger.error(f"Error handling distance change: {e}")
    
    def update_main_button_tooltip(self, distance: Optional[float] = None):
        """
        Update the main toolbar button tooltip with current state information.
        
        Args:
            distance: Optional distance value to include in tooltip
        """
        try:
            if not hasattr(self.toolbar_controller, '_main_button') or not self.toolbar_controller._main_button:
                return
                
            # Get current type name
            if hasattr(self.toolbar_controller, '_get_current_type_name'):
                current_type = self.toolbar_controller._get_current_type_name()
            else:
                current_type = "Unknown"
            
            # Build tooltip with current state
            tooltip = f"Waypoint Capture Tool - Capture: Click - Scroll Current: {current_type}"
            
            # Add distance if provided
            if distance is not None:
                tooltip += f" - Distance: {distance:.1f}u"
                
            self.toolbar_controller._main_button.tooltip = tooltip
            
        except Exception as e:
            logger.error(f"Error updating main button tooltip: {e}")
    
    def show_capture_feedback(self, message: str):
        """
        Show user feedback for waypoint capture operations.
        
        Args:
            message: Feedback message to display to user
        """
        try:
            # For now, just log the message
            # In a full implementation, this could show a toast notification
            logger.info(f"Waypoint feedback: {message}")
            
            # TODO: Implement proper UI feedback systems:
            # - Toast notifications
            # - Status bar updates  
            # - Temporary overlay messages
            # - Progress indicators
            
        except Exception as e:
            logger.error(f"Error showing capture feedback: {e}")
    
    def handle_toolbar_button_toggled(self, model):
        """
        Handle toolbar button toggle state changes.
        
        Args:
            model: The UI model from the toolbar button
        """
        try:
            # Delegate to toolbar controller for state management
            if hasattr(self.toolbar_controller, 'handle_button_toggle'):
                is_active = model.get_value_as_bool() if hasattr(model, 'get_value_as_bool') else False
                self.toolbar_controller.handle_button_toggle(is_active)
            else:
                logger.warning("Toolbar controller missing handle_button_toggle method")
                
        except Exception as e:
            logger.error(f"Error handling toolbar button toggle: {e}")
    
    def handle_toolbar_button_clicked(self):
        """Handle toolbar button click events."""
        try:
            # Delegate to toolbar controller for click handling
            if hasattr(self.toolbar_controller, 'handle_button_click'):
                self.toolbar_controller.handle_button_click()
            else:
                logger.warning("Toolbar controller missing handle_button_click method")
                
        except Exception as e:
            logger.error(f"Error handling toolbar button click: {e}")
    
    def create_distance_slider_widget(self, default_distance: float, min_distance: float, max_distance: float):
        """
        Create and configure a distance slider widget.
        
        Args:
            default_distance: Default slider value
            min_distance: Minimum allowed distance
            max_distance: Maximum allowed distance
            
        Returns:
            Configured distance slider widget or None if UI not available
        """
        try:
            if not UI_AVAILABLE:
                logger.warning("UI not available, cannot create distance slider")
                return None
            
            # Create distance input field that allows typing exact values
            distance_slider = ui.FloatField(
                width=80,
                height=24,
                tooltip=f"Distance ahead of camera ({min_distance}-{max_distance}u)"
            )
            
            # Set initial value and constraints
            distance_slider.model.set_value(default_distance)
            distance_slider.model.set_min(min_distance)
            distance_slider.model.set_max(max_distance)
            
            # Connect change handler
            distance_slider.model.add_value_changed_fn(self.handle_distance_change)
            
            if self._config.debug_mode:
                logger.info(f"Distance slider created: {default_distance}u ({min_distance}-{max_distance})")
            
            return distance_slider
            
        except Exception as e:
            logger.error(f"Error creating distance slider widget: {e}")
            return None
    
    def setup_ui_styling(self):
        """
        Set up UI styling and theme configurations.
        
        Returns:
            Style dictionary for UI components
        """
        try:
            if not UI_AVAILABLE:
                return {}
            
            # Define consistent styling for waypoint UI components
            style = {
                "Button": {
                    "background_color": 0xFF2C2C2C,
                    "border_color": 0xFF444444,
                    "border_width": 1,
                },
                "Button.Hovered": {
                    "background_color": 0xFF3C3C3C,
                },
                "Button.Pressed": {
                    "background_color": 0xFF1C1C1C,
                },
                "FloatField": {
                    "background_color": 0xFF1A1A1A,
                    "border_color": 0xFF444444,
                    "color": 0xFFCCCCCC,
                },
            }
            
            if self._config.debug_mode:
                logger.info("UI styling configured for waypoint components")
            
            return style
            
        except Exception as e:
            logger.error(f"Error setting up UI styling: {e}")
            return {}
    
    def cleanup_ui_components(self):
        """Clean up UI component resources and subscriptions."""
        try:
            # UI components are typically cleaned up automatically by omni.ui
            # but we can perform any custom cleanup here if needed
            
            if self._config.debug_mode:
                logger.info("UI components handler cleanup completed")
                
        except Exception as e:
            logger.error(f"Error during UI components cleanup: {e}")


# Convenience functions for backward compatibility
def create_ui_handler(toolbar_controller, config) -> Optional[UIComponentsHandler]:
    """
    Create and return a new UI components handler instance.
    
    Args:
        toolbar_controller: Reference to main toolbar
        config: Configuration object
        
    Returns:
        UIComponentsHandler instance or None on error
    """
    try:
        return UIComponentsHandler(toolbar_controller, config)
    except Exception as e:
        logger.error(f"Failed to create UI components handler: {e}")
        return None