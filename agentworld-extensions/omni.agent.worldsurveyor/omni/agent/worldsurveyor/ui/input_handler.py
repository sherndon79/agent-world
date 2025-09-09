"""
Input handling features for WorldSurveyor waypoint management.

This module handles all user input interactions including hotkeys and scroll wheel
events for waypoint type selection and capture. Extracted from monolithic
waypoint_toolbar.py for better feature separation and maintainability.
"""

import logging
from typing import Optional, Callable
from carb.input import KeyboardInput as Key

try:
    from omni.kit.widget.toolbar import Hotkey
    HOTKEY_AVAILABLE = True
except ImportError:
    HOTKEY_AVAILABLE = False
    logging.warning("Hotkey functionality not available")

logger = logging.getLogger(__name__)


class WaypointInputHandler:
    """
    Handles all input interactions for waypoint capture including hotkeys and scroll wheel.
    
    Provides centralized input management for waypoint type selection and capture
    operations, supporting both keyboard shortcuts and mouse scroll interactions.
    """
    
    def __init__(self, toolbar_controller, config):
        """
        Initialize input handler with toolbar controller reference.
        
        Args:
            toolbar_controller: Reference to main toolbar for callbacks
            config: Configuration object for debug settings
        """
        self.toolbar_controller = toolbar_controller
        self._config = config
        self._hotkey = None
        
        # Set up input handling only if enabled in config
        # Default to False to avoid hotkey conflicts
        if getattr(config, 'hotkey_enabled', False):
            self._setup_hotkey()
        else:
            if config.debug_mode:
                logger.info("Hotkey setup skipped (disabled in config - set hotkey_enabled=true to enable X key hotkey)")
    
    def _setup_hotkey(self):
        """Setup keyboard hotkey for quick waypoint capture."""
        try:
            if not HOTKEY_AVAILABLE:
                if self._config.debug_mode:
                    logger.info("Hotkey API not available, skipping hotkey setup")
                return
            
            # Try to clean up any lingering hotkeys first
            self._cleanup_existing_hotkeys()
                
            # Use Hotkey API with a globally unique action name to avoid collisions
            # Include a timestamp or instance ID to ensure uniqueness across reloads
            import time
            action_name = f"omni.agent.worldsurveyor.waypoint_capture_x_{int(time.time())}"
            
            try:
                self._hotkey = Hotkey(action_name, Key.X, self._on_hotkey_pressed, lambda: True)
                
                if self._config.debug_mode:
                    logger.info(f"Waypoint capture hotkey (X) registered: {action_name}")
            except Exception as hotkey_error:
                if self._config.debug_mode:
                    logger.info(f"Hotkey registration failed (may be due to conflicts): {hotkey_error}")
                    logger.info("Extension will continue without hotkey support")
                self._hotkey = None
                
        except Exception as e:
            logger.error(f"Error setting up hotkey: {e}")
            # Continue without hotkey if it fails
            self._hotkey = None
    
    def _cleanup_existing_hotkeys(self):
        """Attempt to clean up any existing hotkey registrations."""
        try:
            # This is a best-effort cleanup - hotkey registry is global
            # and we can't easily enumerate or clean up other registrations
            if self._hotkey:
                self._hotkey = None
                
            # Small delay to allow registry cleanup
            import time
            time.sleep(0.01)
            
        except Exception as e:
            # Ignore cleanup errors - they're not critical
            pass
    
    def _on_hotkey_pressed(self):
        """Handle hotkey press for quick waypoint capture."""
        try:
            # Delegate to toolbar controller
            if hasattr(self.toolbar_controller, 'handle_hotkey_capture'):
                self.toolbar_controller.handle_hotkey_capture()
            else:
                logger.error("Toolbar controller missing handle_hotkey_capture method")
                
            if self._config.debug_mode:
                logger.info(f"Quick waypoint capture via hotkey triggered")
        except Exception as e:
            logger.error(f"Error in hotkey capture: {e}")
    
    def handle_scroll_wheel(self, x, y, modifier):
        """
        Handle scroll wheel events for waypoint type cycling.
        
        Args:
            x: Horizontal scroll amount (unused)
            y: Vertical scroll amount (positive = up, negative = down)
            modifier: Keyboard modifiers (unused)
        """
        try:
            # Debug logging
            if self._config.debug_mode:
                logger.info(f"🔄 Scroll wheel event: y={y}")
            
            # Delegate to toolbar controller
            if hasattr(self.toolbar_controller, 'handle_scroll_type_change'):
                self.toolbar_controller.handle_scroll_type_change(y)
            else:
                logger.error("Toolbar controller missing handle_scroll_type_change method")
                
        except Exception as e:
            logger.error(f"Error handling scroll wheel: {e}")
    
    def cleanup(self):
        """Clean up input handler resources."""
        try:
            if self._hotkey:
                try:
                    # Attempt proper hotkey cleanup if available
                    if hasattr(self._hotkey, 'cleanup'):
                        self._hotkey.cleanup()
                    elif hasattr(self._hotkey, 'destroy'):
                        self._hotkey.destroy()
                except Exception as hotkey_cleanup_error:
                    # Log but don't fail - hotkey cleanup can be tricky
                    logger.debug(f"Hotkey cleanup error (non-fatal): {hotkey_cleanup_error}")
                finally:
                    self._hotkey = None
                
            if self._config.debug_mode:
                logger.info("Input handler cleanup completed")
        except Exception as e:
            logger.error(f"Error during input handler cleanup: {e}")
    
    def is_hotkey_active(self) -> bool:
        """
        Check if hotkey is properly set up and active.
        
        Returns:
            True if hotkey is available and set up, False otherwise
        """
        return self._hotkey is not None and HOTKEY_AVAILABLE


# Convenience functions for backward compatibility
def create_input_handler(toolbar_controller, config) -> Optional[WaypointInputHandler]:
    """
    Create and return a new input handler instance.
    
    Args:
        toolbar_controller: Reference to main toolbar for callbacks
        config: Configuration object
        
    Returns:
        WaypointInputHandler instance or None on error
    """
    try:
        return WaypointInputHandler(toolbar_controller, config)
    except Exception as e:
        logger.error(f"Failed to create input handler: {e}")
        return None