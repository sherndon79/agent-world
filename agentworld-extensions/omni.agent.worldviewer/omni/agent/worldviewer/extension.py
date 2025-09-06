"""
Agent WorldViewer Extension

Camera control and viewport management extension for Isaac Sim.
Provides HTTP API for AI-powered camera positioning and management.
Implements coordinated shutdown and thread validation patterns.
"""

import logging
import threading
import time
from typing import Optional, Dict, Any

import omni.ext
import omni.ui as ui
from omni.kit.viewport.utility import get_active_viewport_window

from .config import get_config
from .http_api_interface import HTTPAPIInterface


logger = logging.getLogger(__name__)


class CachedCameraStatus:
    """Cached camera status to reduce expensive USD operations on UI thread."""
    
    def __init__(self, cache_duration_ms: float = 500, extension=None):
        self.cache_duration_ms = cache_duration_ms
        self._extension = extension  # Reference to extension for accessing camera controller
        self._last_update_time = 0
        self._cached_status = {
            'position': None,
            'target': None,
            'camera_path': None,
            'connected': False,
            'error': None
        }
        # Thread coordination for cache updates
        self._cache_lock = threading.Lock()
        self._shutdown_event = threading.Event()
    
    def get_status(self) -> Dict[str, Any]:
        """Get camera status with caching to avoid expensive USD operations."""
        # Check if shutdown is in progress
        if self._shutdown_event.is_set():
            return {
                'position': None,
                'target': None,
                'camera_path': None,
                'connected': False,
                'error': 'Shutdown in progress'
            }
        
        with self._cache_lock:
            current_time = time.time() * 1000  # Convert to milliseconds
            
            # Return cached status if still valid
            if current_time - self._last_update_time < self.cache_duration_ms:
                return self._cached_status.copy()
            
            # Update cache with fresh status
            try:
                self._cached_status = self._fetch_camera_status()
                self._last_update_time = current_time
            except Exception as e:
                logger.error(f"Error updating camera status cache: {e}")
                # Return cached status on error
                pass
            
            return self._cached_status.copy()
    
    def signal_shutdown(self):
        """Signal cache that shutdown is in progress."""
        self._shutdown_event.set()
    
    def _fetch_camera_status(self) -> Dict[str, Any]:
        """Fetch fresh camera status from USD (expensive operation)."""
        try:
            viewport_window = get_active_viewport_window()
            if not viewport_window or not viewport_window.viewport_api:
                return {
                    'position': None,
                    'target': None,
                    'camera_path': None,
                    'connected': False,
                    'error': 'No viewport connection'
                }
            
            # Get camera position and target using camera controller
            position = None
            target = None
            camera_path = None
            
            try:
                camera_path = viewport_window.viewport_api.camera_path
                if camera_path:
                    # Use the existing camera controller if available to avoid creating new instances
                    camera_status = None
                    try:
                        # Try to use the extension's HTTP API camera controller first
                        if (self._extension and 
                            hasattr(self._extension, '_http_api_interface') and 
                            self._extension._http_api_interface and 
                            hasattr(self._extension._http_api_interface, 'camera_controller') and 
                            self._extension._http_api_interface.camera_controller):
                            camera_status = self._extension._http_api_interface.camera_controller.get_status()
                    except Exception:
                        pass
                    
                    # Fallback: create temporary controller only if needed
                    if not camera_status:
                        from .camera_controller import CameraController
                        temp_controller = CameraController()
                        camera_status = temp_controller.get_status()
                    
                    if camera_status.get('connected') and not camera_status.get('error'):
                        position = camera_status.get('position')
                        target = camera_status.get('target')
                    elif camera_status.get('error'):
                        return {
                            'position': None,
                            'target': None,
                            'camera_path': str(camera_path) if camera_path else None,
                            'connected': True,
                            'error': f'Camera error: {str(camera_status["error"])[:50]}'
                        }
            except Exception as e:
                return {
                    'position': None,
                    'target': None,
                    'camera_path': str(camera_path) if camera_path else None,
                    'connected': True,
                    'error': f'USD access error: {str(e)[:50]}'
                }
            
            return {
                'position': position,
                'target': target,
                'camera_path': str(camera_path) if camera_path else None,
                'connected': True,
                'error': None
            }
            
        except Exception as e:
            return {
                'position': None,
                'target': None,
                'camera_path': None,
                'connected': False,
                'error': f'Status fetch error: {str(e)[:50]}'
            }


class AgentWorldViewerExtension(omni.ext.IExt):
    """Agent WorldViewer Extension for Isaac Sim camera control"""
    
    def __init__(self):
        super().__init__()
        # Initialize ALL attributes first
        self._config = get_config()
        self._ext_id = None
        self._http_api_interface = None
        self._processing_timer = None
        self._ui_refresh_timer = None
        self._window = None
        self._camera_status_cache = None
        
        # Thread coordination
        self._main_thread_id = threading.get_ident()
        self._shutdown_event = threading.Event()
        self._http_shutdown_complete = threading.Event()
        self._ui_cleanup_complete = threading.Event()
        
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
    
    def on_startup(self, ext_id):
        """Called when extension starts up"""
        self._ensure_main_thread("Extension startup")
        logger.info("🚀 Starting Agent WorldViewer Extension (Coordinated Pattern)")
        
        try:
            self._ext_id = ext_id
            
            # Initialize cached camera status (performance optimization)
            self._camera_status_cache = CachedCameraStatus(cache_duration_ms=self._config.cache_duration_ms, extension=self)
            
            # Initialize HTTP API
            self._initialize_api()
            
            # Create UI window
            self._create_ui()
            
            # Start processing timer
            self._start_processing_timer()
            
            # Start UI refresh timer
            self._start_ui_refresh_timer()
            
            logger.info("✅ Agent WorldViewer Extension started successfully")
            
        except Exception as e:
            logger.error(f"❌ Failed to start Agent WorldViewer Extension: {e}")
            # Don't re-raise - allow object creation (protected constructor pattern)
            logger.error(f"Extension will continue with limited functionality")
    
    def on_shutdown(self):
        """Coordinated shutdown with proper thread communication."""
        self._ensure_main_thread("Extension shutdown")
        logger.info("🛑 Agent WorldViewer Extension shutdown starting on main thread")
        
        try:
            # Signal shutdown to all threads and caches
            self._shutdown_event.set()
            if self._camera_status_cache:
                self._camera_status_cache.signal_shutdown()
            logger.info("Shutdown event signaled to all threads")
            
            # Phase 1: Clean up main thread operations (UI, timers)
            self._cleanup_main_thread_operations()
            
            # Phase 2: Signal HTTP shutdown and wait for completion
            self._initiate_http_shutdown()
            
            # Phase 3: Wait for all background operations to complete
            self._wait_for_shutdown_completion()
            
            # Phase 4: Clear all references
            self._clear_all_references()
            
            logger.info("✅ Agent WorldViewer Extension shutdown complete")
            
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
            
            # Stop UI refresh timer
            if self._ui_refresh_timer:
                self._ui_refresh_timer.unsubscribe()
                self._ui_refresh_timer = None
                if self._config.debug_mode:
                    logger.info("UI refresh timer stopped")
            
            # Signal UI cleanup completion
            self._ui_cleanup_complete.set()
            
        except Exception as e:
            logger.error(f"Error in main thread cleanup: {e}")
            self._ui_cleanup_complete.set()  # Signal even on failure
    
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
            config = self._config
            
            def coordinated_http_shutdown():
                try:
                    # Check thread without capturing self
                    current_thread_id = threading.get_ident()
                    if current_thread_id == main_thread_id:
                        raise RuntimeError("HTTP shutdown must run on background thread, but running on main thread")
                    
                    logger.info("HTTP shutdown executing on background thread")
                    
                    # Stop cinematic movement timer if present
                    try:
                        if hasattr(http_api, 'camera_controller') and http_api.camera_controller:
                            camera_controller = http_api.camera_controller
                            if hasattr(camera_controller, '_cinematic_controller') and camera_controller._cinematic_controller:
                                camera_controller._cinematic_controller.stop_movement_timer()
                                if config.debug_mode:
                                    logger.info("Cinematic movement timer stopped")
                    except Exception as e:
                        logger.warning(f"Error stopping cinematic timer: {e}")
                    
                    # Shutdown HTTP API
                    if hasattr(http_api, 'shutdown'):
                        logger.info("About to call http_api.shutdown()")
                        http_api.shutdown()
                        logger.info("http_api.shutdown() completed")
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
        
        # Wait for UI cleanup (should be immediate since it runs on main thread)
        if not self._ui_cleanup_complete.wait(timeout=1.0):
            logger.warning("UI cleanup did not complete within timeout")
        
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
        self._ui_refresh_timer = None
        self._camera_status_cache = None
        
        # Clear events
        self._shutdown_event.clear()
        self._http_shutdown_complete.clear()
        self._ui_cleanup_complete.clear()
    
    def _force_cleanup(self):
        """Force cleanup in case of errors."""
        logger.warning("Force cleanup due to errors")
        try:
            self._http_api_interface = None
            self._window = None
            self._processing_timer = None
            self._ui_refresh_timer = None
            self._camera_status_cache = None
        except Exception:
            pass
    
    def _initialize_api(self):
        """Initialize the HTTP API interface"""
        self._ensure_main_thread("API initialization")
        try:
            self._http_api_interface = HTTPAPIInterface()
            
            if self._http_api_interface.initialize():
                logger.info(f"Agent WorldViewer HTTP API initialized successfully on port {self._config.server_port}")
            else:
                logger.error("Failed to initialize Agent WorldViewer HTTP API")
                self._http_api_interface = None
        except Exception as e:
            logger.error(f"Exception during API initialization: {e}")
            self._http_api_interface = None
    
    def _start_processing_timer(self):
        """Start the timer for processing queued operations"""
        if not self._http_api_interface:
            logger.warning("Cannot start processing timer - no HTTP API")
            return
        
        try:
            import omni.kit.app
            
            def process_operations(dt):
                """Process queued camera operations"""
                if self._http_api_interface:
                    self._http_api_interface.process_queued_operations()
            
            # Create timer to process operations every 100ms
            update_stream = omni.kit.app.get_app().get_update_event_stream()
            self._processing_timer = update_stream.create_subscription_to_pop(
                process_operations, name="xr_worldviewer_processing_timer"
            )
            
            logger.info("Agent WorldViewer processing timer started")
            
        except Exception as e:
            logger.error(f"Failed to start processing timer: {e}")
    
    def _start_ui_refresh_timer(self):
        """Start the timer for refreshing UI status display"""
        self._ensure_main_thread("UI refresh timer setup")
        try:
            update_interval_ms = self._config.ui_update_frequency_ms
        except (AttributeError, ValueError, TypeError):
            update_interval_ms = 500  # Default fallback
        
        try:
            def refresh_ui(dt):
                """Refresh UI status display"""
                self._update_ui_status()
            
            # Create timer to refresh UI at configured interval (convert ms to seconds)
            update_stream = omni.kit.app.get_app().get_update_event_stream()
            self._ui_refresh_timer = update_stream.create_subscription_to_pop(
                refresh_ui, name="xr_worldviewer_ui_refresh_timer"
            )
            
            logger.info(f"Agent WorldViewer UI refresh timer started ({update_interval_ms}ms)")
            
        except Exception as e:
            logger.error(f"Failed to start UI refresh timer: {e}")
    
    def _create_ui(self):
        """Create the extension UI window"""
        self._ensure_main_thread("UI window creation")
        try:
            self._window = ui.Window("Agent WorldViewer", width=320, height=280)
            
            with self._window.frame:
                with ui.VStack(spacing=2):
                    # Title section
                    with ui.HStack(height=0):
                        ui.Label("Agent WorldViewer Extension", style={"font_size": 14})
                    ui.Separator(height=2)
                    
                    # Status section
                    with ui.CollapsableFrame("Status", collapsed=False, height=0):
                        with ui.VStack(spacing=1):
                            self._status_label = ui.Label("Initializing...")
                            self._camera_status_label = ui.Label("Camera: Unknown")
                            self._camera_target_label = ui.Label("Target: Unknown")
                            self._api_status_label = ui.Label("API: Unknown")
                            self._api_requests_label = ui.Label("Requests: 0 | Errors: 0")
                    
                    # Queue Controls section
                    with ui.CollapsableFrame("Queue Controls", collapsed=False, height=0):
                        with ui.VStack(spacing=2):
                            # Queue status display
                            self._queue_status_label = ui.Label("Queue: Unknown")
                            self._queue_count_label = ui.Label("Shots: 0 | Duration: 0.0s")
                            
                            ui.Separator()
                            
                            # Media player style controls
                            ui.Label("Queue Playback:")
                            with ui.HStack():
                                self._play_btn = ui.Button("Play", clicked_fn=self._play_queue)
                                self._pause_btn = ui.Button("Pause", clicked_fn=self._pause_queue)
                                self._stop_btn = ui.Button("Stop", clicked_fn=self._stop_queue)
                            
                            ui.Separator()
                            
                            # Queue list display
                            ui.Label("Queued Shots:")
                            with ui.ScrollingFrame(height=120):
                                with ui.VStack(spacing=1):
                                    self._queue_list_container = ui.VStack(spacing=1)
                    
                    # Manual Camera Controls section
                    with ui.CollapsableFrame("Manual Controls", collapsed=False, height=0):
                        with ui.VStack(spacing=1):
                            
                            # Quick positions
                            ui.Label("Quick Positions:")
                            with ui.HStack():
                                ui.Button("Front", clicked_fn=lambda: self._quick_position("front"))
                                ui.Button("Top", clicked_fn=lambda: self._quick_position("top"))
                                ui.Button("Side", clicked_fn=lambda: self._quick_position("side"))
                            
                            ui.Separator()
                            
                            # Manual position controls
                            ui.Label("Manual Position:")
                            with ui.HStack():
                                ui.Label("X:", width=20)
                                self._pos_x = ui.FloatDrag(width=60)
                                ui.Label("Y:", width=20) 
                                self._pos_y = ui.FloatDrag(width=60)
                                ui.Label("Z:", width=20)
                                self._pos_z = ui.FloatDrag(width=60)
                            
                            ui.Button("Set Position", clicked_fn=self._set_manual_position)
                    
            
            # Update status periodically
            self._update_ui_status()
            
        except Exception as e:
            logger.error(f"Failed to create UI: {e}")
    
    def _update_ui_status(self):
        """Update UI status information with cached camera status (performance optimized)."""
        try:
            if not self._window or not hasattr(self, '_status_label'):
                return
            
            # Update extension status
            if self._http_api_interface:
                self._status_label.text = "Active - Monitoring camera operations"
                self._api_status_label.text = f"API: Running on port {self._config.server_port}"
                # Show API request and error counts from unified metrics
                try:
                    stats = self._http_api_interface.get_stats()
                    req = int(stats.get('requests_received', stats.get('requests', 0)) or 0)
                    errs = int(stats.get('errors', 0))
                    self._api_requests_label.text = f"Requests: {req} | Errors: {errs}"
                except Exception:
                    pass
            else:
                self._status_label.text = "Error - API not initialized"
                self._api_status_label.text = "API: Failed to start"
                self._api_requests_label.text = "Requests: 0 | Errors: 0"
            
            # Update camera status using cached system (avoids expensive USD operations)
            try:
                camera_status = self._camera_status_cache.get_status()
                
                if camera_status['error']:
                    # Show error with truncated message
                    error_msg = camera_status['error'][:30]
                    self._camera_status_label.text = f"Camera: {error_msg}"
                    self._camera_target_label.text = "Target: Error"
                elif not camera_status['connected']:
                    self._camera_status_label.text = "Camera: No viewport connection"
                    self._camera_target_label.text = "Target: No connection"
                elif camera_status['position']:
                    # Format position with 1 decimal place
                    pos = camera_status['position']
                    pos_str = f"[{pos[0]:.1f}, {pos[1]:.1f}, {pos[2]:.1f}]"
                    self._camera_status_label.text = f"Camera: {pos_str}"
                    
                    # Format target with 1 decimal place if available
                    if camera_status.get('target'):
                        target = camera_status['target']
                        target_str = f"[{target[0]:.1f}, {target[1]:.1f}, {target[2]:.1f}]"
                        self._camera_target_label.text = f"Target: {target_str}"
                    else:
                        self._camera_target_label.text = "Target: Unknown"
                else:
                    self._camera_status_label.text = "Camera: Position unknown"
                    self._camera_target_label.text = "Target: Unknown"
                    
            except Exception as e:
                self._camera_status_label.text = f"Camera: Cache error ({str(e)[:30]})"
                self._camera_target_label.text = "Target: Cache error"
            
            # Update queue status and control button states (if queue controls exist)
            if hasattr(self, '_queue_status_label'):
                self._update_queue_status()
            
        except Exception as e:
            logger.warning(f"Failed to update UI status: {e}")
    
    def _quick_position(self, position_name: str):
        """Set camera to a quick position relative to current view context"""
        if not self._http_api_interface or not self._http_api_interface.camera_controller:
            logger.warning("No camera controller available")
            return
        
        # Get current camera status to determine context
        try:
            # Priority 1: Use currently selected asset as center of interest
            center = self._get_selected_asset_center()
            context_source = "selected asset"
            
            if not center:
                # Priority 2: Use current camera target if available
                current_status = self._camera_status_cache.get_status()
                if current_status.get('target') and current_status['target'] != [0, 0, 0]:
                    center = current_status['target']
                    context_source = "camera target"
                elif current_status.get('position'):
                    # Priority 3: Use current camera position as reference
                    center = current_status['position']
                    context_source = "camera position"
                else:
                    # Priority 4: Fallback to world origin
                    center = [0, 0, 0]
                    context_source = "world origin"
            
            # Define relative positions around the center point
            distance = 15  # Standard viewing distance
            positions = {
                "front": {"position": [center[0], center[1] - distance, center[2]], "target": center},  # -Y for front view
                "top": {"position": [center[0], center[1], center[2] + distance], "target": center},     # +Z for top-down view
                "side": {"position": [center[0] + distance, center[1], center[2]], "target": center}     # +X for side view
            }
            
            if position_name in positions:
                pos_data = positions[position_name]
                result = self._http_api_interface.camera_controller.set_position(
                    pos_data["position"], pos_data["target"]
                )
            
                if result["success"]:
                    logger.info(f"Set camera to {position_name} view relative to {context_source}: {center}")
                else:
                    logger.warning(f"Failed to set {position_name} view: {result.get('error')}")
            else:
                logger.warning(f"Unknown position name: {position_name}")
                
        except Exception as e:
            logger.error(f"Error in quick position {position_name}: {e}")
            # Fallback to corrected coordinate system
            fallback_positions = {
                "front": {"position": [0, -15, 0], "target": [0, 0, 0]},  # -Y for front view
                "top": {"position": [0, 0, 15], "target": [0, 0, 0]},     # +Z for top-down view
                "side": {"position": [15, 0, 0], "target": [0, 0, 0]}     # +X for side view
            }
            if position_name in fallback_positions:
                pos_data = fallback_positions[position_name]
                result = self._http_api_interface.camera_controller.set_position(
                    pos_data["position"], pos_data["target"]
                )
                logger.info(f"Used fallback position for {position_name}")
    
    def _get_selected_asset_center(self):
        """Get the center position of currently selected asset(s) in the viewport."""
        try:
            import omni.usd
            from pxr import UsdGeom
            
            # Get USD context and selection
            usd_context = omni.usd.get_context()
            if not usd_context:
                return None
                
            selection = usd_context.get_selection()
            selected_paths = selection.get_selected_prim_paths()
            
            if not selected_paths:
                return None
            
            stage = usd_context.get_stage()
            if not stage:
                return None
            
            # If multiple objects selected, find the center of all
            all_positions = []
            
            for prim_path in selected_paths:
                prim = stage.GetPrimAtPath(prim_path)
                if not prim or not prim.IsValid():
                    continue
                    
                # Get the prim's world transform
                xformable = UsdGeom.Xformable(prim)
                if xformable:
                    # Get world transform matrix
                    world_transform = xformable.ComputeLocalToWorldTransform(0.0)
                    # Extract translation (position)
                    translation = world_transform.ExtractTranslation()
                    all_positions.append([float(translation[0]), float(translation[1]), float(translation[2])])
            
            if not all_positions:
                return None
                
            # Calculate center point of all selected objects
            if len(all_positions) == 1:
                return all_positions[0]
            else:
                # Average position of all selected objects
                center_x = sum(pos[0] for pos in all_positions) / len(all_positions)
                center_y = sum(pos[1] for pos in all_positions) / len(all_positions) 
                center_z = sum(pos[2] for pos in all_positions) / len(all_positions)
                return [center_x, center_y, center_z]
                
        except Exception as e:
            logger.debug(f"Could not get selected asset center: {e}")
            return None
    
    def _set_manual_position(self):
        """Set camera to manually entered position"""
        if not self._http_api_interface or not self._http_api_interface.camera_controller:
            logger.warning("No camera controller available")
            return
        
        try:
            position = [
                self._pos_x.model.get_value_as_float(),
                self._pos_y.model.get_value_as_float(),
                self._pos_z.model.get_value_as_float()
            ]
            
            result = self._http_api_interface.camera_controller.set_position(position)
            
            if result["success"]:
                logger.info(f"Set camera to position {position}")
            else:
                logger.warning(f"Failed to set position: {result.get('error')}")
                
        except Exception as e:
            logger.error(f"Error setting manual position: {e}")
    
    def _update_queue_status(self):
        """Update queue status display and button states"""
        try:
            if not self._http_api_interface or not hasattr(self, '_queue_status_label'):
                return
            
            # Get cinematic controller through camera controller
            if not self._http_api_interface.camera_controller:
                self._queue_status_label.text = "Queue: No camera controller"
                self._queue_count_label.text = "Shots: 0 | Duration: 0.0s"
                return
                
            cinematic_controller = self._http_api_interface.camera_controller.get_cinematic_controller()
            if not cinematic_controller:
                self._queue_status_label.text = "Queue: No cinematic controller"
                self._queue_count_label.text = "Shots: 0 | Duration: 0.0s"
                return
            
            try:
                queue_status = cinematic_controller.get_queue_status()
                if queue_status.get('success'):
                    state = queue_status.get('queue_state', 'unknown')
                    active_count = queue_status.get('active_count', 0)
                    queued_count = queue_status.get('queued_count', 0)
                    total_duration = queue_status.get('total_duration', 0.0)
                    
                    # Format status display
                    state_display = state.title() if state else 'Unknown'
                    self._queue_status_label.text = f"Queue: {state_display}"
                    self._queue_count_label.text = f"Shots: {active_count + queued_count} | Duration: {total_duration:.1f}s"
                    
                    # Update button states based on queue state
                    self._update_button_states(state, active_count + queued_count)
                    
                    # Update queue list display
                    self._update_queue_list(queue_status)
                    
                else:
                    self._queue_status_label.text = f"Queue: Error ({queue_status.get('error', 'Unknown')[:20]})"
                    self._queue_count_label.text = "Shots: 0 | Duration: 0.0s"
                    self._update_button_states('error', 0)
                    
            except Exception as e:
                self._queue_status_label.text = f"Queue: Status error ({str(e)[:20]})"
                self._queue_count_label.text = "Shots: 0 | Duration: 0.0s"
                self._update_button_states('error', 0)
                
        except Exception as e:
            logger.debug(f"Failed to update queue status: {e}")
    
    def _update_button_states(self, queue_state: str, total_shots: int):
        """Update button enabled/disabled states based on queue state"""
        try:
            if not hasattr(self, '_play_btn'):
                return
            
            # Default: all buttons enabled
            play_enabled = True
            pause_enabled = True  
            stop_enabled = True
            
            if queue_state == 'idle':
                # Idle: can play if shots exist, pause/stop not useful
                play_enabled = total_shots > 0
                pause_enabled = False
                stop_enabled = total_shots > 0  # Can stop to clear queue
                
            elif queue_state == 'running':
                # Running: can pause/stop, play not useful
                play_enabled = False
                pause_enabled = True
                stop_enabled = True
                
            elif queue_state == 'paused' or queue_state == 'pending':
                # Paused/Pending: can play to resume, stop to clear
                play_enabled = True
                pause_enabled = False
                stop_enabled = True
                
            elif queue_state == 'stopped':
                # Stopped: can play if shots exist
                play_enabled = total_shots > 0
                pause_enabled = False
                stop_enabled = False
                
            else:
                # Unknown/error: disable all
                play_enabled = False
                pause_enabled = False
                stop_enabled = False
            
            # Apply button states
            self._play_btn.enabled = play_enabled
            self._pause_btn.enabled = pause_enabled
            self._stop_btn.enabled = stop_enabled
            
        except Exception as e:
            logger.debug(f"Failed to update button states: {e}")
    
    def _update_queue_list(self, queue_status: dict):
        """Update the queue list display with current shots"""
        try:
            if not hasattr(self, '_queue_list_container'):
                return
            
            # Clear existing queue list
            self._queue_list_container.clear()
            
            # Get active and queued shots
            active_shots = queue_status.get('active_shots', [])
            queued_shots = queue_status.get('queued_shots', [])
            
            with self._queue_list_container:
                # Show active shot (if any)
                for i, shot in enumerate(active_shots):
                    operation = shot.get('operation', 'unknown')
                    mode = shot.get('execution', 'auto')
                    duration = shot.get('total_duration', shot.get('estimated_duration', 0.0))
                    details = self._format_shot_details(shot)
                    
                    # Format operation name nicely
                    op_display = operation.replace('_', ' ').title()
                    mode_symbol = "M" if mode == 'manual' else "A"
                    
                    ui.Label(f"ACTIVE: {op_display} [{mode_symbol}] {duration:.1f}s - {details}", style={"color": 0xFF00AA00, "font_size": 12})
                
                # Show queued shots
                for i, shot in enumerate(queued_shots):
                    operation = shot.get('operation', 'unknown')
                    mode = shot.get('execution', 'auto')
                    duration = shot.get('estimated_duration', 0.0)
                    details = self._format_shot_details(shot)
                    
                    # Format operation name nicely
                    op_display = operation.replace('_', ' ').title()
                    mode_symbol = "M" if mode == 'manual' else "A"
                    
                    # Different styling for pending manual shots
                    if mode == 'manual':
                        ui.Label(f"{i+1}. {op_display} [{mode_symbol}] {duration:.1f}s - {details}", style={"color": 0xFFFFAA00, "font_size": 12})
                    else:
                        ui.Label(f"{i+1}. {op_display} [{mode_symbol}] {duration:.1f}s - {details}", style={"color": 0xFFAAAAAA, "font_size": 12})
                
                # Show message if queue is empty
                if not active_shots and not queued_shots:
                    ui.Label("(No shots queued)", style={"color": 0xFF888888})
            
        except Exception as e:
            logger.debug(f"Failed to update queue list: {e}")
    
    def _format_shot_details(self, shot: dict) -> str:
        """Format shot parameters into a readable string"""
        try:
            params = shot.get('params', {})
            
            # Extract key parameters
            start_pos = params.get('start_position', [0, 0, 0])
            end_pos = params.get('end_position', [0, 0, 0])
            start_target = params.get('start_target')
            end_target = params.get('end_target')
            speed = params.get('speed')
            easing = params.get('easing_type', 'linear')
            
            # Format positions very compactly
            start_str = f"[{start_pos[0]:.0f},{start_pos[1]:.0f},{start_pos[2]:.0f}]"
            end_str = f"[{end_pos[0]:.0f},{end_pos[1]:.0f},{end_pos[2]:.0f}]"
            
            details_parts = [f"{start_str}->{end_str}"]
            
            # Add target info if available
            if start_target and end_target:
                target_start = f"[{start_target[0]:.0f},{start_target[1]:.0f},{start_target[2]:.0f}]"
                target_end = f"[{end_target[0]:.0f},{end_target[1]:.0f},{end_target[2]:.0f}]"
                details_parts.append(f"T:{target_start}->{target_end}")
            
            # Add speed and easing
            if speed:
                details_parts.append(f"spd:{speed}")
            details_parts.append(f"{easing}")
            
            return " ".join(details_parts)
            
        except Exception as e:
            logger.debug(f"Failed to format shot details: {e}")
            return "details unavailable"
    
    def _play_queue(self):
        """Play/resume the queue"""
        try:
            if not self._http_api_interface.camera_controller:
                logger.warning("No camera controller available for queue play")
                return
                
            cinematic_controller = self._http_api_interface.camera_controller.get_cinematic_controller()
            if cinematic_controller:
                result = cinematic_controller.play_queue()
                if result.get('success'):
                    logger.info(f"Queue play: {result.get('message', 'Started')}")
                else:
                    logger.warning(f"Queue play failed: {result.get('error', 'Unknown error')}")
            else:
                logger.warning("No cinematic controller available for queue play")
        except Exception as e:
            logger.error(f"Error playing queue: {e}")
    
    def _pause_queue(self):
        """Pause the queue"""
        try:
            if not self._http_api_interface.camera_controller:
                logger.warning("No camera controller available for queue pause")
                return
                
            cinematic_controller = self._http_api_interface.camera_controller.get_cinematic_controller()
            if cinematic_controller:
                result = cinematic_controller.pause_queue()
                if result.get('success'):
                    logger.info(f"Queue pause: {result.get('message', 'Paused')}")
                else:
                    logger.warning(f"Queue pause failed: {result.get('error', 'Unknown error')}")
            else:
                logger.warning("No cinematic controller available for queue pause")
        except Exception as e:
            logger.error(f"Error pausing queue: {e}")
    
    def _stop_queue(self):
        """Stop and clear the queue"""
        try:
            if not self._http_api_interface.camera_controller:
                logger.warning("No camera controller available for queue stop")
                return
                
            cinematic_controller = self._http_api_interface.camera_controller.get_cinematic_controller()
            if cinematic_controller:
                result = cinematic_controller.stop_queue()
                if result.get('success'):
                    logger.info(f"Queue stop: {result.get('message', 'Stopped and cleared')}")
                else:
                    logger.warning(f"Queue stop failed: {result.get('error', 'Unknown error')}")
            else:
                logger.warning("No cinematic controller available for queue stop")
        except Exception as e:
            logger.error(f"Error stopping queue: {e}")
    
    
