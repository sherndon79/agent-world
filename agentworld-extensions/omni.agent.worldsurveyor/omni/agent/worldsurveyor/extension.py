"""
Agent WorldSurveyor Extension - Refactored Implementation

Modular waypoint management system with improved performance and security.
Focuses on core functionality: waypoint storage, HTTP API, and camera capture.
"""

import logging
from typing import Optional

import omni.ext
import omni.ui as ui
from isaacsim.util.debug_draw import _debug_draw

from .config import get_config
from .waypoint_manager import WaypointManager
from .http_api_interface import HTTPAPIInterface

# Import toolbar integration
try:
    from .ui.waypoint_toolbar import WaypointToolbarManager
    TOOLBAR_AVAILABLE = True
except ImportError as e:
    TOOLBAR_AVAILABLE = False
    logging.warning(f"Toolbar integration not available: {e}")

logger = logging.getLogger(__name__)


class AgentWorldSurveyorExtension(omni.ext.IExt):
    """WorldSurveyor Extension - Refactored Implementation."""
    
    def __init__(self):
        super().__init__()
        self._config = get_config()
        self._waypoint_manager: Optional[WaypointManager] = None
        self._http_api: Optional[HTTPAPIInterface] = None
        self._toolbar_manager: Optional['WaypointToolbarManager'] = None
        self._window: Optional[ui.Window] = None
        
        # Thread coordination
        import threading
        self._main_thread_id = threading.get_ident()
        self._shutdown_event = threading.Event()
        self._toolbar_cleanup_complete = threading.Event()
        self._http_shutdown_complete = threading.Event()
        
        # Main thread processing timer 
        self._processing_timer = None
    
    def _is_main_thread(self) -> bool:
        """Check if we're running on the main thread."""
        import threading
        return threading.get_ident() == self._main_thread_id
    
    def _ensure_main_thread(self, operation_name: str):
        """Ensure operation is running on main thread."""
        if not self._is_main_thread():
            import threading
            current_thread = threading.current_thread().name
            raise RuntimeError(f"{operation_name} must run on main thread, but running on {current_thread}")
    
    def _ensure_background_thread(self, operation_name: str):
        """Ensure operation is running on background thread."""
        if self._is_main_thread():
            raise RuntimeError(f"{operation_name} must run on background thread, but running on main thread")
    
    def on_startup(self, ext_id: str):
        """Called when extension starts."""
        logger.info("Starting Agent WorldSurveyor Extension (Refactored)")
        
        try:
            # Clear any orphaned debug markers from previous sessions
            try:
                debug_draw = _debug_draw.acquire_debug_draw_interface()
                if debug_draw:
                    debug_draw.clear_points()
                    logger.info("Cleared orphaned debug markers from previous session")
                else:
                    logger.warning("Debug draw interface not available during startup")
            except Exception as e:
                logger.warning(f"Could not clear orphaned markers during startup: {e}")
            
            # Initialize components with improved error handling
            logger.info("Initializing waypoint manager...")
            self._waypoint_manager = WaypointManager()
            logger.info("Waypoint manager initialized successfully")
            
            logger.info("Initializing HTTP API interface...")
            try:
                self._http_api = HTTPAPIInterface(self._waypoint_manager, port=self._config.server_port)
                logger.info("HTTP API interface created successfully")
                
                # Check if server is running (with safety check)
                try:
                    if hasattr(self._http_api, '_api_stats') and self._http_api.is_running():
                        logger.info("HTTP API server confirmed running")
                    else:
                        logger.warning("HTTP API server is not running after initialization")
                except Exception as check_error:
                    logger.error(f"Error checking server status: {check_error}")
                    logger.warning("Unable to verify server status - proceeding anyway")
                    
            except Exception as http_error:
                logger.error(f"CRITICAL: HTTP API initialization failed: {http_error}")
                logger.error(f"Exception type: {type(http_error).__name__}")
                import traceback
                logger.error(f"Traceback: {traceback.format_exc()}")
                raise
            
            # HTTP API starts automatically in constructor
            
            # Initialize toolbar integration
            self._setup_toolbar_integration()
            
            # Create minimal status window (no waypoint editing here)
            self._create_window()

            # Auto-load stored waypoints if enabled
            self._auto_load_waypoints_if_enabled()
            
            # Start main thread processing timer for camera operations
            self._start_processing_timer()
            
            logger.info("Agent WorldSurveyor Extension started successfully")
            
        except Exception as e:
            logger.error(f"Failed to start Agent WorldSurveyor Extension: {e}")
            raise
    
    def _setup_toolbar_integration(self):
        """Set up the waypoint capture toolbar integration."""
        try:
            if not TOOLBAR_AVAILABLE:
                logger.info("Toolbar integration not available, skipping")
                return
            
            # Create toolbar manager
            self._toolbar_manager = WaypointToolbarManager(self._waypoint_manager)
            
            # Set reference to toolbar manager in API interface for cleanup
            self._http_api.set_toolbar_manager(self._toolbar_manager)
            
            # Set up the toolbar immediately
            if self._toolbar_manager.setup_toolbar():
                logger.info("Waypoint capture toolbar successfully integrated")
            else:
                logger.warning("Failed to integrate waypoint capture toolbar")
            
        except Exception as e:
            logger.error(f"Error setting up toolbar integration: {e}")
    
    def _auto_load_waypoints_if_enabled(self):
        """Auto-load stored waypoints on startup if enabled in configuration."""
        try:
            if not self._config.auto_load_waypoints:
                logger.info("Auto-load waypoints disabled in configuration")
                return
            
            if not self._waypoint_manager:
                logger.warning("Waypoint manager not available for auto-load")
                return
            
            # Get waypoint count from database to see if we should load
            waypoint_count = self._waypoint_manager.get_waypoint_count()
            if waypoint_count == 0:
                logger.info("No stored waypoints to auto-load")
                return
            
            logger.info(f"Auto-loading {waypoint_count} stored waypoints on startup")
            
            # Trigger refresh which loads all database waypoints and makes them visible
            self._waypoint_manager.refresh_waypoint_markers()
            
            # Get actual visible count after loading
            visible_count = self._waypoint_manager.get_visible_marker_count()
            logger.info(f"Successfully auto-loaded {visible_count} waypoint markers")
            
        except Exception as e:
            logger.error(f"Error during waypoint auto-load: {e}")
            # Don't raise - this is optional functionality that shouldn't prevent startup
    
    def _start_processing_timer(self):
        """Start main thread processing timer for camera operations."""
        self._ensure_main_thread("Processing timer setup")
        
        try:
            import omni.kit.app
            
            def process_operations(dt):
                """Process queued camera operations on main thread"""
                if self._http_api:
                    self._http_api.process_queued_operations()
                # Update UI roughly every 1s (assuming ~100ms tick)
                if hasattr(self, '_ui_update_counter'):
                    self._ui_update_counter += 1
                else:
                    self._ui_update_counter = 0
                if self._ui_update_counter % 10 == 0:
                    self._update_ui_stats()
            
            # Create timer to process operations every 100ms
            update_stream = omni.kit.app.get_app().get_update_event_stream()
            self._processing_timer = update_stream.create_subscription_to_pop(
                process_operations, name="worldsurveyor_processing_timer"
            )
            
            logger.info("WorldSurveyor processing timer started for camera operations")
            
        except Exception as e:
            logger.error(f"Failed to start processing timer: {e}")

    def _create_window(self):
        """Create a minimal status UI similar to other extensions."""
        try:
            self._ensure_main_thread("UI window creation")
            self._window = ui.Window("Agent WorldSurveyor", width=320, height=240)

            with self._window.frame:
                with ui.VStack(spacing=2):
                    # Title
                    with ui.HStack(height=0):
                        ui.Label("Agent WorldSurveyor Extension", style={"font_size": 14})
                    ui.Separator(height=2)

                    # Status
                    with ui.CollapsableFrame("Status", collapsed=False, height=0):
                        with ui.VStack(spacing=1):
                            self._status_label = ui.Label("Active - Waypoint services ready")
                            ui.Spacer(height=2)
                            ui.Label("HTTP API:", style={"font_size": 12})
                            self._api_status_label = ui.Label("Server: Starting...")
                            self._api_url_label = ui.Label("URL: Starting...")
                            self._api_requests_label = ui.Label("Requests: 0 | Errors: 0")

                    # Quick link to Waypoint Manager (opens browser)
                    with ui.HStack(height=0):
                        ui.Button("Open Waypoint Manager", clicked_fn=self._open_waypoint_manager)

            # Initial update
            self._update_ui_stats()
        except Exception as e:
            logger.error(f"Failed to create WorldSurveyor UI window: {e}")

    def _update_ui_stats(self):
        """Update UI with current HTTP API statistics."""
        try:
            if not hasattr(self, '_api_status_label'):
                return

            api_stats = {}
            if self._http_api:
                # Prefer unified stats if available
                try:
                    if hasattr(self._http_api, 'get_stats'):
                        api_stats = self._http_api.get_stats() or {}
                except Exception:
                    api_stats = {}

                # Server status and URL
                try:
                    running = self._http_api.is_running() if hasattr(self._http_api, 'is_running') else True
                except Exception:
                    running = True

                self._api_status_label.text = "Server: Running" if running else "Server: Stopped"

                # URL via unified config helper if present
                try:
                    server_url = self._config.get_server_url(self._config.server_port)
                except Exception:
                    server_url = f"http://{getattr(self._config, 'server_host', 'localhost')}:{self._config.server_port}"
                self._api_url_label.text = f"URL: {server_url}" if running else "URL: Not available"

                # Requests / Errors
                req = int(api_stats.get('requests_received', api_stats.get('requests', 0)) or 0)
                errs = int(api_stats.get('failed_requests', api_stats.get('errors', 0)) or 0)
                self._api_requests_label.text = f"Requests: {req} | Errors: {errs}"
            else:
                self._api_status_label.text = "Server: Not initialized"
                self._api_url_label.text = "URL: Not available"
                self._api_requests_label.text = "Requests: 0 | Errors: 0"
        except Exception as e:
            logger.warning(f"Failed to update WorldSurveyor UI stats: {e}")

    def _open_waypoint_manager(self):
        """Open the Waypoint Manager web UI in the default browser."""
        try:
            # Build URL to the served HTML page
            try:
                base_url = self._config.get_server_url(self._config.server_port)
            except Exception:
                base_url = f"http://{getattr(self._config, 'server_host', 'localhost')}:{self._config.server_port}"
            url = f"{base_url}/waypoint_manager.html"

            import webbrowser
            webbrowser.open(url)
            logger.info(f"Opened Waypoint Manager: {url}")
        except Exception as e:
            logger.error(f"Failed to open Waypoint Manager URL: {e}")

    def on_shutdown(self):
        """Coordinated shutdown with proper thread communication."""
        self._ensure_main_thread("Extension shutdown")
        logger.info("Agent WorldSurveyor Extension shutdown starting on main thread")
        
        try:
            # Signal shutdown to all threads
            self._shutdown_event.set()
            logger.info("Shutdown event signaled to all threads")
            
            # Phase 1: Stop processing timer on main thread
            self._cleanup_processing_timer()
            
            # Phase 2: Clean up toolbar on main thread (UI operations)
            self._cleanup_toolbar_main_thread()
            
            # Phase 3: Signal HTTP shutdown and wait for completion
            self._initiate_http_shutdown()
            
            # Phase 4: Wait for all background operations to complete
            self._wait_for_shutdown_completion()
            
            # Phase 5: Clear all references
            self._clear_all_references()
            
            logger.info("Extension shutdown complete")
            
        except Exception as e:
            logger.error(f"Error during extension shutdown: {e}")
            self._force_cleanup()
    
    def _cleanup_processing_timer(self):
        """Clean up the processing timer on main thread."""
        self._ensure_main_thread("Processing timer cleanup")
        
        if self._processing_timer:
            try:
                logger.info("Stopping camera operation processing timer")
                self._processing_timer.unsubscribe()
                self._processing_timer = None
                logger.info("Processing timer stopped successfully")
            except Exception as e:
                logger.error(f"Error stopping processing timer: {e}")
                self._processing_timer = None
        else:
            logger.info("No processing timer to clean up")
    
    def _cleanup_toolbar_main_thread(self):
        """Clean up toolbar on main thread with proper thread checking."""
        self._ensure_main_thread("Toolbar cleanup")
        
        if self._toolbar_manager:
            if self._config.debug_mode:
                logger.info("Phase 1: Cleaning up toolbar on main thread")
            try:
                import threading
                current_thread = threading.current_thread().name
                thread_id = threading.get_ident()
                
                if self._config.log_thread_info:
                    logger.info(f"Toolbar cleanup executing on thread: {current_thread} (ID: {thread_id})")
                    logger.info(f"Main thread ID: {self._main_thread_id}")
                
                # CRITICAL: Ensure we're on main thread before calling cleanup
                if threading.get_ident() != self._main_thread_id:
                    raise RuntimeError(f"Toolbar cleanup called on wrong thread! Current: {thread_id}, Main: {self._main_thread_id}")
                
                self._toolbar_manager.cleanup_toolbar()
                self._toolbar_manager = None
                
                # Signal completion
                self._toolbar_cleanup_complete.set()
                if self._config.debug_mode:
                    logger.info("Toolbar cleanup completed and signaled")
                
            except Exception as e:
                logger.error(f"Toolbar cleanup failed: {e}")
                self._toolbar_manager = None
                self._toolbar_cleanup_complete.set()  # Signal even on failure
        else:
            logger.info("Phase 1: No toolbar manager to clean up")
            self._toolbar_cleanup_complete.set()
    
    def _initiate_http_shutdown(self):
        """Initiate HTTP shutdown and coordinate with background thread."""
        self._ensure_main_thread("HTTP shutdown initiation")
        
        if self._http_api:
            if self._config.debug_mode:
                logger.info("Phase 2: Initiating HTTP shutdown")
            
            # Brief delay to ensure server is fully started before shutdown
            import time
            time.sleep(self._config.startup_delay)
            if self._config.debug_mode:
                logger.info("Starting HTTP shutdown after brief delay")
            
            # Tell the HTTP API to start shutdown (it will handle background thread coordination)
            import threading
            
            # Capture references to avoid closure capturing self
            http_api = self._http_api
            shutdown_complete_event = self._http_shutdown_complete
            main_thread_id = self._main_thread_id
            
            def coordinated_http_shutdown():
                try:
                    # Check thread without capturing self
                    current_thread_id = threading.get_ident()
                    if current_thread_id == main_thread_id:
                        raise RuntimeError("HTTP shutdown must run on background thread, but running on main thread")
                    
                    logger.info("HTTP shutdown executing on background thread")
                    
                    logger.info("About to call http_api.shutdown()")
                    http_api.shutdown()
                    logger.info("http_api.shutdown() completed")
                    
                    # Signal completion
                    logger.info("Setting shutdown complete event")
                    shutdown_complete_event.set()
                    logger.info("HTTP shutdown completed and signaled")
                    
                except Exception as e:
                    logger.error(f"HTTP shutdown failed: {e}")
                    logger.info("Setting shutdown complete event due to failure")
                    shutdown_complete_event.set()  # Signal even on failure
                finally:
                    logger.info("coordinated_http_shutdown function completed")
            
            # Start HTTP shutdown in background thread
            shutdown_thread = threading.Thread(
                target=coordinated_http_shutdown, 
                daemon=True,
                name="HTTPShutdown"
            )
            shutdown_thread.start()
            logger.info("HTTP shutdown thread started")
        else:
            logger.info("Phase 2: No HTTP API to shut down")
            self._http_shutdown_complete.set()
    
    def _wait_for_shutdown_completion(self):
        """Wait for all shutdown operations to complete with timeout."""
        self._ensure_main_thread("Shutdown completion wait")
        
        logger.info("Phase 3: Waiting for shutdown completion")
        
        # Wait for toolbar cleanup (should be immediate since it runs on main thread)
        if not self._toolbar_cleanup_complete.wait(timeout=self._config.toolbar_cleanup_timeout):
            logger.warning("Toolbar cleanup did not complete within timeout")
        
        # Wait for HTTP shutdown with longer timeout
        if self._config.debug_mode:
            logger.info("Waiting for HTTP shutdown completion...")
        if not self._http_shutdown_complete.wait(timeout=self._config.shutdown_timeout):
            logger.warning(f"HTTP shutdown did not complete within {self._config.shutdown_timeout} second timeout")
            # Force mark as complete to prevent hanging
            self._http_shutdown_complete.set()
        else:
            logger.info("HTTP shutdown completed successfully")
        
        logger.info("All shutdown operations completed or timed out")
    
    def _clear_all_references(self):
        """Clear all object references."""
        self._ensure_main_thread("Reference clearing")
        
        logger.info("Phase 4: Clearing all references")
        
        # Clean up database connections before clearing references
        if self._waypoint_manager and hasattr(self._waypoint_manager, '_database'):
            try:
                self._waypoint_manager._database.cleanup_connections()
            except Exception as e:
                logger.warning(f"Error cleaning up database connections: {e}")
        
        self._http_api = None
        self._waypoint_manager = None
        self._toolbar_manager = None
        
        # Clear events
        self._shutdown_event.clear()
        self._toolbar_cleanup_complete.clear()
        self._http_shutdown_complete.clear()
    
    def _force_cleanup(self):
        """Force cleanup in case of errors."""
        logger.warning("Force cleanup due to errors")
        try:
            if self._processing_timer:
                self._processing_timer.unsubscribe()
                self._processing_timer = None
            self._http_api = None
            self._waypoint_manager = None
            self._toolbar_manager = None
        except Exception:
            pass
