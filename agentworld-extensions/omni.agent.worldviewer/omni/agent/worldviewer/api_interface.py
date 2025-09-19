"""
HTTP API interface for WorldViewer communication.
Maintains compatibility with extension.py expectations while following WorldSurveyor pattern.
"""

import logging
import socket
import struct
import threading
import time
from collections import deque
from http.server import ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, Optional
import logging
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
    
    from agent_world_metrics import setup_worldviewer_metrics
    METRICS_AVAILABLE = True
except ImportError as e:
    logging.getLogger(__name__).warning(f"Could not import unified metrics system: {e}")
    METRICS_AVAILABLE = False

from .config import get_config
from agent_world_logging import setup_logging
from .http_handler import WorldViewerHTTPHandler
from .security import WorldViewerAuth
from agent_world_requests import RequestTracker

logger = logging.getLogger(__name__)


class HTTPAPIInterface:
    """HTTP API interface for WorldViewer communication."""
    
    def __init__(self, port: Optional[int] = None):
        setup_logging('worldviewer')
        self._config = get_config()
        self._port = port or self._config.server_port or 8900
        self._server = None
        self._server_thread = None
        self.security_manager = WorldViewerAuth(config=self._config)
        
        # Always initialize _api_stats for backward compatibility
        self._api_stats = {
            'requests_received': 0,
            'errors': 0,
            'start_time': None,
            'server_running': False
        }
        
        # Initialize unified metrics system (thread-safe)
        if METRICS_AVAILABLE:
            self.metrics = setup_worldviewer_metrics()
        
        # Thread-safe operation queues (for extension compatibility)
        self._camera_queue = deque()
        self._queue_lock = threading.Lock()
        tracker_ttl = getattr(self._config, 'request_tracker_ttl', 300.0)
        tracker_capacity = getattr(self._config, 'request_tracker_max_entries', 500)
        self._request_tracker = RequestTracker(
            max_entries=tracker_capacity,
            ttl_seconds=tracker_ttl,
        )
        
        # Controllers (will be initialized in initialize())
        self.camera_controller = None
        
        # Processing settings (for extension compatibility)
        self.max_operations_per_tick = 5
        self.tick_interval_ms = 100
        
        # Main thread ID for thread safety validation
        self._main_thread_id = threading.get_ident()
        
        # Port property for extension compatibility
        self.port = self._port
        
        logger.info(f"WorldViewer HTTPAPIInterface initialized on port {self._port}")

    def initialize(self):
        """Initialize the HTTP API and controllers (extension compatibility method)."""
        try:
            # Import here to avoid circular imports
            from .camera_controller import CameraController
            self.camera_controller = CameraController()
            
            self.start_server()
            logger.info(f"WorldViewer HTTP API initialized on port {self.port}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize WorldViewer HTTP API: {e}")
            return False

    def process_queued_operations(self):
        """Process queued operations from the main thread (extension compatibility method)."""
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

            if not self.camera_controller:
                request['error'] = 'Camera controller not initialized'
                request['completed'] = True
                if request_id:
                    self._request_tracker.mark_completed(request_id, error=request['error'])
                return
            
            operation = request['operation']
            params = request['params']
            
            if operation == 'set_position':
                result = self.camera_controller.set_position(
                    position=params.get('position'),
                    target=params.get('target'),
                    up_vector=params.get('up_vector')
                )
            
            elif operation == 'frame_object':
                result = self.camera_controller.frame_object(
                    object_path=params.get('object_path'),
                    distance=params.get('distance')
                )
            
            elif operation == 'orbit_camera':
                result = self.camera_controller.orbit(
                    center=params.get('center'),
                    distance=params.get('distance'),
                    elevation=params.get('elevation'),
                    azimuth=params.get('azimuth')
                )
                
            elif operation == 'smooth_move':
                result = self._start_cinematic_operation('smooth_move', params)
            
            elif operation == 'orbit_shot':
                result = self._start_cinematic_operation('orbit_shot', params)
                
            elif operation == 'arc_shot':
                result = self._start_cinematic_operation('arc_shot', params)
                
            elif operation == 'stop_movement':
                result = self._handle_stop_movement(params)
            
            else:
                raise ValueError(f"Unknown camera operation: {operation}")
            
            request['result'] = result
            request['completed'] = True
            if request_id:
                self._request_tracker.mark_completed(request_id, result=result)

        except Exception as e:
            request['error'] = str(e)
            request['completed'] = True
            logger.error(f"Camera operation failed: {e}")
            if request_id:
                self._request_tracker.mark_completed(request_id, error=request['error'])

    def _start_cinematic_operation(self, operation: str, params: Dict) -> Dict:
        """Start a cinematic camera operation (these run asynchronously)"""
        try:
            cinematic_controller = self.camera_controller.get_cinematic_controller()
            
            # Generate a movement ID for this cinematic operation
            import uuid
            movement_id = f"{operation}_{int(time.time() * 1000)}_{uuid.uuid4().hex[:8]}"
            
            # Start cinematic operation
            cinematic_controller.start_movement(movement_id, operation, params)
            
            return {
                'success': True,
                'movement_id': movement_id,
                'operation': operation,
                'status': 'started',
                'timestamp': time.time()
            }
            
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def _handle_stop_movement(self, params: Dict) -> Dict:
        """Stop all ongoing camera movement."""
        try:
            cinematic_controller = self.camera_controller.get_cinematic_controller()
            result = cinematic_controller.stop_movement()  # No parameters needed
            return result
            
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def shutdown(self):
        """Shutdown the HTTP server and cleanup (extension compatibility method)."""
        self.stop_server()

    def get_health_info(self) -> Dict[str, Any]:
        """Provide extension-specific health metadata for unified HTTP handler."""
        try:
            from .services.worldviewer_service import WorldViewerService  # Local import to avoid cycles

            service = WorldViewerService(self)
            status = service.get_camera_status()
            info: Dict[str, Any] = {
                'camera_status': status,
            }
            if status.get('success'):
                info['camera_position'] = status.get('position')
            return info
        except Exception as exc:  # pragma: no cover - health info is best effort
            logger.debug(f"Health info unavailable: {exc}")
            return {}

    def start_server(self):
        """Start the HTTP server in a background thread."""
        if self._server is not None:
            logger.warning("Server already running")
            return

        try:
            # Create handler class using unified factory method
            handler_class = WorldViewerHTTPHandler.create_handler_class(self, 'worldviewer')
            
            # Create server with socket reuse options
            self._server = ThreadingHTTPServer((self._config.server_host, self._port), handler_class)
            self._server.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self._server.socket.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack('ii', 1, 0))
            
            # Start server in background thread
            self._server_thread = threading.Thread(target=self._server.serve_forever, daemon=True)
            self._server_thread.start()
            
            # Start metrics system
            if METRICS_AVAILABLE and hasattr(self, 'metrics'):
                self.metrics.start_server()
            else:
                self._api_stats['server_running'] = True
                self._api_stats['start_time'] = time.time()
            
            logger.info(f"WorldViewer HTTP server started on port {self._port}")
            
        except Exception as e:
            logger.error(f"Failed to start HTTP server: {e}")
            self._server = None
            raise

    def stop_server(self):
        """Stop the HTTP server gracefully."""
        if self._server:
            try:
                logger.info("Stopping WorldViewer HTTP server...")
                self._server.shutdown()
                self._server.server_close()
                
                if self._server_thread and self._server_thread.is_alive():
                    self._server_thread.join(timeout=5.0)
                
                # Stop metrics system
                if METRICS_AVAILABLE and hasattr(self, 'metrics'):
                    self.metrics.stop_server()
                else:
                    self._api_stats['server_running'] = False
                
                logger.info("WorldViewer HTTP server stopped")
                
            except Exception as e:
                logger.error(f"Error stopping server: {e}")
            finally:
                self._server = None
                self._server_thread = None

    def is_running(self) -> bool:
        """Check if the server is running."""
        if METRICS_AVAILABLE and hasattr(self, 'metrics'):
            return hasattr(self, 'metrics') and self.metrics.get_stats_dict().get('server_running', False)
        else:
            return self._server is not None and self._api_stats.get('server_running', False)

    def get_port(self) -> int:
        """Get the server port."""
        return self._port

    def get_stats(self) -> dict:
        """Get statistics - backward compatibility."""
        if METRICS_AVAILABLE and hasattr(self, 'metrics'):
            return self.metrics.get_stats_dict()
        else:
            return self._api_stats.copy()

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
            self._api_stats['errors'] += 1
