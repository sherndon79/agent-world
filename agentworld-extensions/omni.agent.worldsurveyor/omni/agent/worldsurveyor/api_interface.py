"""
HTTP API interface for WorldSurveyor communication.
"""

import logging
import socket
import struct
import threading
import time
from collections import deque
from datetime import datetime
from http.server import ThreadingHTTPServer
from typing import Any, Dict, Optional
from pathlib import Path
import sys

# Import unified metrics system
try:
    # Find the agentworld-extensions directory
    current = Path(__file__).resolve()
    for _ in range(10):  # Search up the directory tree
        if current.name == 'agentworld-extensions':
            sys.path.insert(0, str(current))
            break
        current = current.parent
    
    from agent_world_metrics import setup_worldsurveyor_metrics
    METRICS_AVAILABLE = True
except ImportError as e:
    logging.getLogger(__name__).warning(f"Could not import unified metrics system: {e}")
    METRICS_AVAILABLE = False

from .config import get_config
from agent_world_logging import setup_logging
from agent_world_requests import RequestTracker
from .http_handler import WorldSurveyorHTTPHandler
from .waypoint_manager import WaypointManager
from .security import WorldSurveyorAuth

logger = logging.getLogger(__name__)


class HTTPAPIInterface:
    """HTTP API interface for WorldSurveyor communication."""
    
    def __init__(self, waypoint_manager: WaypointManager, port: Optional[int] = None):
        setup_logging('worldsurveyor')
        self._config = get_config()
        self.waypoint_manager = waypoint_manager
        self._port = port or self._config.server_port
        self._server = None
        self._server_thread = None
        self._toolbar_manager = None  # Reference to toolbar manager for cleanup
        self.security_manager = WorldSurveyorAuth(config=self._config)
        
        # Thread coordination
        self._main_thread_id = threading.get_ident()
        self._shutdown_requested = threading.Event()
        
        # Camera operation queue for main thread processing
        self._camera_queue = deque()
        self._queue_lock = threading.Lock()
        tracker_ttl = getattr(self._config, 'request_tracker_ttl', 300.0)
        tracker_capacity = getattr(self._config, 'request_tracker_max_entries', 500)
        self._request_tracker = RequestTracker(
            max_entries=tracker_capacity,
            ttl_seconds=tracker_ttl,
        )
        self.max_operations_per_tick = 5  # Limit operations per update cycle
        
        # Always initialize _api_stats for backward compatibility
        self._api_stats = {
            'requests_received': 0,
            'successful_requests': 0,
            'failed_requests': 0,
            'server_running': False,
            'start_time': None
        }
        
        # Initialize unified metrics system (thread-safe)
        if METRICS_AVAILABLE:
            self.metrics = setup_worldsurveyor_metrics()
        
        # Add server ready synchronization
        self._server_ready = threading.Event()
        
        # Start the HTTP server immediately with error protection
        try:
            if self._config.debug_mode:
                logger.info(f"WorldSurveyor API initializing on port {self._port}")
            self._start_server()
        except Exception as e:
            logger.error(f"WorldSurveyor API startup failed: {e}")
            # Don't re-raise - allow object creation
    
    def _start_server(self):
        """Start the HTTP server."""
        try:
            # Create handler class using unified factory method
            handler_class = WorldSurveyorHTTPHandler.create_handler_class(self, 'worldsurveyor')
            
            # Start server with socket reuse
            self._server = ThreadingHTTPServer((self._config.server_host, self._port), handler_class)
            self._server.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self._server.socket.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack('ii', 1, 0))
            
            # Start server thread
            self._server_thread = threading.Thread(
                target=self._run_server,
                name=f"WorldSurveyor-HTTP-{self._port}",
                daemon=True
            )
            self._server_thread.start()
            
            # Wait for server readiness
            if self._server_ready.wait(timeout=5):
                logger.info(f"WorldSurveyor HTTP API server started on port {self._port}")
            else:
                logger.warning("WorldSurveyor HTTP API server start timeout")
                
        except Exception as e:
            logger.error(f"Failed to start WorldSurveyor HTTP server: {e}")
            raise
    
    def _run_server(self):
        """Run the HTTP server in background thread."""
        try:
            # Start metrics system
            if METRICS_AVAILABLE and hasattr(self, 'metrics'):
                self.metrics.start_server()
            else:
                self._api_stats['server_running'] = True
                self._api_stats['start_time'] = datetime.utcnow().isoformat()
            self._server_ready.set()
            
            if self._config.debug_mode:
                logger.info(f"WorldSurveyor HTTP server thread started on port {self._port}")
            
            self._server.serve_forever()
            
        except Exception as e:
            logger.error(f"WorldSurveyor HTTP server error: {e}")
        finally:
            # Stop metrics system
            if METRICS_AVAILABLE and hasattr(self, 'metrics'):
                self.metrics.stop_server()
            else:
                self._api_stats['server_running'] = False
            if self._config.debug_mode:
                logger.info("WorldSurveyor HTTP server thread stopped")
    
    def shutdown(self, timeout: float = 5.0):
        """Shutdown the HTTP server gracefully."""
        logger.info("WorldSurveyor API shutting down...")
        self._shutdown_requested.set()
        
        if self._server:
            try:
                self._server.shutdown()
                logger.info("WorldSurveyor HTTP server shutdown requested")
                
                if self._server_thread and self._server_thread.is_alive():
                    self._server_thread.join(timeout=timeout)
                    if self._server_thread.is_alive():
                        logger.warning("WorldSurveyor HTTP server thread did not terminate within timeout")
                    else:
                        logger.info("WorldSurveyor HTTP server thread terminated")
                        
            except Exception as e:
                logger.error(f"Error during WorldSurveyor HTTP server shutdown: {e}")
            finally:
                try:
                    self._server.server_close()
                    logger.info("WorldSurveyor HTTP server socket closed")
                except Exception as e:
                    logger.error(f"Error closing WorldSurveyor HTTP server socket: {e}")
        
        # Final metrics cleanup
        if METRICS_AVAILABLE and hasattr(self, 'metrics'):
            self.metrics.stop_server()
        else:
            self._api_stats['server_running'] = False
        
        logger.info("WorldSurveyor API shutdown complete")

    def get_health_info(self) -> Dict[str, Any]:
        waypoint_count = self.waypoint_manager.get_waypoint_count() if self.waypoint_manager else 0
        visible_markers = self.waypoint_manager.get_visible_marker_count() if self.waypoint_manager else 0
        return {
            'waypoint_count': waypoint_count,
            'visible_markers': visible_markers,
        }

    def process_queued_operations(self):
        """Process queued camera operations from the main thread."""
        operations_processed = 0
        
        # Process camera operations
        while operations_processed < self.max_operations_per_tick and self._camera_queue:
            with self._queue_lock:
                if self._camera_queue:
                    request = self._camera_queue.popleft()
                else:
                    break

            self._process_camera_request(request)
            operations_processed += 1

        if operations_processed:
            self._request_tracker.prune()

    def _process_camera_request(self, request: Dict):
        """Process a camera operation request on the main thread."""
        try:
            request_id = request.get('request_id')
            operation = request['operation']
            params = request['params']
            
            if operation == 'goto_waypoint':
                # Import Isaac Sim APIs here to ensure main thread access
                import omni.kit.viewport.utility as viewport_utils
                import omni.usd
                from omni.kit.viewport.utility import get_active_viewport_window
                from pxr import Gf, UsdGeom
                
                # Execute camera positioning
                waypoint_id = params.get('waypoint_id')
                waypoint = self.waypoint_manager.get_waypoint(waypoint_id)

                if not waypoint:
                    request['error'] = f'Waypoint not found: {waypoint_id}'
                    request['completed'] = True
                    if request_id:
                        self._request_tracker.mark_completed(request_id, error=request['error'])
                    return
                
                # Use exact same logic as original WorldViewer frontend call
                if waypoint.waypoint_type in ['camera_position', 'directional_lighting'] and waypoint.target:
                    # Exact captured position - restore camera to exact position and target
                    camera_position = list(waypoint.position)
                    camera_target = list(waypoint.target)
                    positioning_type = "exact_captured_position"
                else:
                    # Calculated viewing position - position camera to view waypoint (crosshair logic)
                    x, y, z = waypoint.position
                    camera_position = [x + 5, y + 5, z + 2]
                    camera_target = list(waypoint.position)  # Target the waypoint itself
                    positioning_type = "calculated_viewing_position"
                
                # Execute camera positioning using Isaac Sim APIs
                success = self._execute_camera_positioning(camera_position, camera_target)

                if success:
                    request['result'] = {
                        'success': True,
                        'message': f'Camera positioned at waypoint: {waypoint.name}',
                        'waypoint': {
                            'id': waypoint.id,
                            'name': waypoint.name,
                            'position': list(waypoint.position),
                            'target': list(waypoint.target) if waypoint.target else None
                        },
                        'camera_position': camera_position,
                        'camera_target': camera_target,
                        'positioning_type': positioning_type
                    }
                    logger.info(f"Camera positioned at waypoint '{waypoint.name}' using {positioning_type}")
                    if request_id:
                        self._request_tracker.mark_completed(request_id, result=request['result'])
                else:
                    request['result'] = {
                        'success': False,
                        'error': 'Failed to position camera - Isaac Sim viewport not available',
                        'waypoint': {
                            'id': waypoint.id,
                            'name': waypoint.name,
                            'position': list(waypoint.position),
                            'target': list(waypoint.target) if waypoint.target else None
                        }
                    }
                    if request_id:
                        self._request_tracker.mark_completed(request_id, result=request['result'])
            else:
                request['error'] = f'Unknown camera operation: {operation}'
                if request_id:
                    self._request_tracker.mark_completed(request_id, error=request['error'])

            request['completed'] = True

        except Exception as e:
            logger.error(f"Error processing camera request: {e}")
            request['error'] = str(e)
            request['completed'] = True
            request_id = request.get('request_id')
            if request_id:
                self._request_tracker.mark_completed(request_id, error=request['error'])

    def _execute_camera_positioning(self, position: list, target: list) -> bool:
        """Execute camera positioning using Isaac Sim APIs (must run on main thread)."""
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
            logger.debug("Camera positioned using isaacsim.core.utils.viewports")
            return True
        except ImportError:
            logger.debug("isaacsim.core.utils.viewports not available")
        except Exception as e:
            logger.debug(f"isaacsim.core.utils.viewports failed: {e}")
        
        # Method 2: Try Omniverse Kit viewport utilities (standard approach)
        try:
            from omni.kit.viewport.utility import get_active_viewport_window
            from pxr import Gf
            
            viewport_window = get_active_viewport_window()
            if viewport_window and viewport_window.viewport_api:
                viewport_api = viewport_window.viewport_api
                
                # Convert to Gf vectors
                eye_vec = Gf.Vec3d(eye_position[0], eye_position[1], eye_position[2])
                target_vec = Gf.Vec3d(target_position[0], target_position[1], target_position[2])
                
                # Set camera position and target using viewport API
                viewport_api.set_camera_position(eye_vec, True)
                # Always set target since we calculated it above
                viewport_api.set_camera_target(target_vec, True)
                
                logger.debug("Camera positioned using viewport_api")
                return True
        except Exception as e:
            logger.debug(f"viewport_api method failed: {e}")
        
        logger.warning("All camera positioning methods failed")
        return False
    
    def set_toolbar_manager(self, toolbar_manager):
        """Set reference to toolbar manager for proper cleanup coordination."""
        self._toolbar_manager = toolbar_manager
    
    @property
    def port(self):
        """Get the server port."""
        return self._port
    
    def get_port(self):
        """Get the server port (for health endpoint compatibility)."""
        return self._port
    
    def get_stats(self):
        """Get statistics - backward compatibility."""
        if METRICS_AVAILABLE and hasattr(self, 'metrics'):
            return self.metrics.get_stats_dict()
        else:
            return self._api_stats.copy()
    
    def is_running(self):
        """Check if the HTTP server is running."""
        if METRICS_AVAILABLE and hasattr(self, 'metrics'):
            return hasattr(self, 'metrics') and self.metrics.get_stats_dict().get('server_running', False)
        else:
            return self._api_stats.get('server_running', False)
    
    def increment_request_counter(self):
        """Increment request counter using unified system or fallback."""
        if METRICS_AVAILABLE and hasattr(self, 'metrics'):
            self.metrics.increment_requests()
        else:
            self._api_stats['requests_received'] += 1

    def increment_error_counter(self):
        """Increment error counter using unified system or fallback."""
        if METRICS_AVAILABLE and hasattr(self, 'metrics'):
            self.metrics.increment_errors()
        else:
            self._api_stats['failed_requests'] += 1
