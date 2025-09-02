"""
Agent WorldRecorder Extension - Main Extension Class

Isaac Sim extension for video/frame recording with HTTP API.
Implements coordinated shutdown and thread validation patterns.
"""

import logging
import threading
from typing import Optional

import omni.ext
import omni.ui as ui

from .config import get_config
from .http_api_interface import HTTPAPIInterface


logger = logging.getLogger(__name__)


class AgentWorldRecorderExtension(omni.ext.IExt):
    """Main extension class for Agent WorldRecorder automation."""

    def __init__(self):
        super().__init__()
        # Initialize ALL attributes first
        self._config = get_config()
        self._http_api_interface: Optional[HTTPAPIInterface] = None
        self._window: Optional[ui.Window] = None
        self._processing_timer = None
        
        # Thread coordination
        self._main_thread_id = threading.get_ident()
        self._shutdown_event = threading.Event()
        self._http_shutdown_complete = threading.Event()
        
        # Then attempt risky operations in on_startup()
        # Protected constructor pattern - don't do heavy initialization here

    def _is_main_thread(self) -> bool:
        """Check if we're running on the main thread."""
        return threading.get_ident() == self._main_thread_id
    
    def _ensure_main_thread(self, operation_name: str):
        """Ensure operation is running on main thread."""
        if not self._is_main_thread():
            current_thread = threading.current_thread().name
            raise RuntimeError(f"{operation_name} must run on main thread, but running on {current_thread}")
    
    def _ensure_background_thread(self, operation_name: str):
        """Ensure operation is running on background thread."""
        if self._is_main_thread():
            raise RuntimeError(f"{operation_name} must run on background thread, but running on main thread")
    
    def on_startup(self, ext_id: str):
        """Initialize extension components on startup."""
        self._ensure_main_thread("Extension startup")
        logger.info("🚀 Starting Agent WorldRecorder Extension (Coordinated Pattern)")
        
        try:
            # Initialize HTTP API interface for real-time communication
            self._http_api_interface = HTTPAPIInterface(port=self._config.server_port)
            
            # Start the API server
            if hasattr(self._http_api_interface, 'start'):
                if self._http_api_interface.start():
                    logger.info(f"HTTP API interface started on port {self._config.server_port}")
                else:
                    logger.error("Failed to start HTTP API interface")
                    self._http_api_interface = None
            else:
                logger.info(f"HTTP API interface created on port {self._config.server_port}")
            
            # Create UI window
            self._create_window()
            
            # Start processing timer for queue operations
            self._start_processing_timer()
            
            # Initial UI update
            self._update_ui_stats()
            
            logger.info("✅ Agent WorldRecorder Extension started successfully")
            
        except Exception as e:
            logger.error(f"❌ Failed to start Agent WorldRecorder Extension: {e}")
            # Don't re-raise - allow object creation (protected constructor pattern)
            logger.error(f"Extension will continue with limited functionality")

    def on_shutdown(self):
        """Coordinated shutdown with proper thread communication."""
        self._ensure_main_thread("Extension shutdown")
        logger.info("🛑 Agent WorldRecorder Extension shutdown starting on main thread")
        
        try:
            # Signal shutdown to all threads
            self._shutdown_event.set()
            logger.info("Shutdown event signaled to all threads")
            
            # Phase 1: Clean up main thread operations (UI, timers)
            self._cleanup_main_thread_operations()
            
            # Phase 2: Signal HTTP shutdown and wait for completion
            self._initiate_http_shutdown()
            
            # Phase 3: Wait for all background operations to complete
            self._wait_for_shutdown_completion()
            
            # Phase 4: Clear all references
            self._clear_all_references()
            
            logger.info("✅ Agent WorldRecorder Extension shutdown complete")
            
        except Exception as e:
            logger.error(f"❌ Error during extension shutdown: {e}")
            self._force_cleanup()
    
    def _cleanup_main_thread_operations(self):
        """Clean up operations that must run on main thread."""
        self._ensure_main_thread("Main thread cleanup")
        
        if self._config.debug_mode:
            logger.info("Phase 1: Cleaning up main thread operations")
        
        try:
            # Stop processing timer
            if self._processing_timer:
                self._processing_timer.unsubscribe()
                self._processing_timer = None
                if self._config.debug_mode:
                    logger.info("Processing timer stopped")
        except Exception as e:
            logger.error(f"Error stopping processing timer: {e}")
    
    def _initiate_http_shutdown(self):
        """Initiate HTTP shutdown and coordinate with background thread."""
        self._ensure_main_thread("HTTP shutdown initiation")
        
        if self._http_api_interface:
            if self._config.debug_mode:
                logger.info("Phase 2: Initiating HTTP shutdown")
            
            # Brief delay to ensure server is fully started before shutdown
            import time
            time.sleep(self._config.startup_delay)
            
            # Capture references to avoid closure capturing self
            http_api = self._http_api_interface
            shutdown_complete_event = self._http_shutdown_complete
            main_thread_id = self._main_thread_id
            
            def coordinated_http_shutdown():
                try:
                    # Check thread without capturing self
                    current_thread_id = threading.get_ident()
                    if current_thread_id == main_thread_id:
                        raise RuntimeError("HTTP shutdown must run on background thread, but running on main thread")
                    
                    logger.info("HTTP shutdown executing on background thread")
                    
                    # Shutdown HTTP API
                    if hasattr(http_api, 'stop'):
                        logger.info("About to call http_api.stop()")
                        http_api.stop()
                        logger.info("http_api.stop() completed")
                    else:
                        # Fallback for older API interface
                        if hasattr(http_api, '_api_stats'):
                            http_api._api_stats['server_running'] = False
                        logger.info("HTTP API marked as stopped")
                    
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
        
        # Wait for HTTP shutdown with timeout
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
        self._http_api_interface = None
        self._window = None
        self._processing_timer = None
        
        # Clear events
        self._shutdown_event.clear()
        self._http_shutdown_complete.clear()
    
    def _force_cleanup(self):
        """Force cleanup in case of errors."""
        logger.warning("Force cleanup due to errors")
        try:
            self._http_api_interface = None
            self._window = None
            self._processing_timer = None
        except Exception:
            pass

    def _start_processing_timer(self):
        """Start the timer for processing queued operations"""
        if not self._http_api_interface:
            logger.warning("Cannot start processing timer - no HTTP API")
            return
        
        try:
            import omni.kit.app
            
            def process_operations(dt):
                """Process queued operations and update UI"""
                if self._http_api_interface and hasattr(self._http_api_interface, 'process_queued_operations'):
                    self._http_api_interface.process_queued_operations()
                
                # Update UI stats periodically (every ~1 second)
                if hasattr(self, '_ui_update_counter'):
                    self._ui_update_counter += 1
                else:
                    self._ui_update_counter = 0
                
                # Update UI every 10 timer cycles (~1 second at 100ms intervals)
                if self._ui_update_counter % 10 == 0:
                    self._update_ui_stats()
            
            # Create timer to process operations every 100ms
            update_stream = omni.kit.app.get_app().get_update_event_stream()
            self._processing_timer = update_stream.create_subscription_to_pop(
                process_operations, name="xr_worldrecorder_processing_timer"
            )
            
            logger.info("Agent WorldRecorder processing timer started")
            
        except Exception as e:
            logger.error(f"Failed to start processing timer: {e}")

    def _create_window(self):
        """Create the extension's UI window."""
        self._ensure_main_thread("UI window creation")
        self._window = ui.Window("Agent WorldRecorder", width=320, height=280)
        
        with self._window.frame:
            with ui.VStack(spacing=2):
                # Title section
                with ui.HStack(height=0):
                    ui.Label("Agent WorldRecorder Extension", style={"font_size": 14})
                ui.Separator(height=2)
                
                # Status section
                with ui.CollapsableFrame("Status", collapsed=False, height=0):
                    with ui.VStack(spacing=1):
                        self._status_label = ui.Label("Active - Recording ready")
                        
                        ui.Spacer(height=2)
                        ui.Label("HTTP API:", style={"font_size": 12})
                        self._api_status_label = ui.Label("Server: Starting...")
                        self._api_url_label = ui.Label("URL: Starting...")
                        
                        ui.Spacer(height=2)
                        ui.Label("Recording Status:", style={"font_size": 12})
                        self._recording_status_label = ui.Label("Recording: Idle")
                        self._api_requests_label = ui.Label("Requests: 0 | Errors: 0")
                

    def _update_ui_stats(self):
        """Update UI with current statistics."""
        api_stats = {}
        
        # Update HTTP API status
        if hasattr(self, '_http_api_interface') and self._http_api_interface:
            # Get stats through the proper API method (unified or fallback)
            if hasattr(self._http_api_interface, 'get_stats'):
                api_stats = self._http_api_interface.get_stats()
            
            # Debug log to see what stats we're getting
            if self._config.debug_mode:
                logger.info(f"UI Stats Debug: {api_stats}")
            
            if hasattr(self._http_api_interface, 'is_running') and callable(self._http_api_interface.is_running):
                if self._http_api_interface.is_running():
                    self._api_status_label.text = "Server: Running"
                    self._api_url_label.text = f"URL: {self._config.get_server_url()}"
                    req = int(api_stats.get('requests_received', api_stats.get('requests', 0)) or 0)
                    errs = int(api_stats.get('errors', 0))
                    self._api_requests_label.text = f"Requests: {req} | Errors: {errs}"
                else:
                    self._api_status_label.text = "Server: Stopped"
                    self._api_url_label.text = "URL: Not available"
                    self._api_requests_label.text = "Requests: 0 | Errors: 0"
            else:
                # Fallback for simpler API interfaces
                self._api_status_label.text = "Server: Running"
                self._api_url_label.text = f"URL: {self._config.get_server_url()}"
                req = int(api_stats.get('requests_received', api_stats.get('requests', 0)) or 0)
                errs = int(api_stats.get('errors', 0))
                self._api_requests_label.text = f"Requests: {req} | Errors: {errs}"
        
        # Recording status
        if hasattr(self, '_recording_status_label'):
            self._recording_status_label.text = "Recording: Idle"

    @property
    def window(self) -> Optional[ui.Window]:
        """Get the extension's UI window."""
        return self._window
