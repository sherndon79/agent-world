import logging
import socket
import struct
import threading
import time
from http.server import ThreadingHTTPServer
from typing import Optional, Callable, Any
from collections import deque

from .http_handler import WorldRecorderHTTPHandler
from .security import SecurityManager
from .config import WorldRecorderConfig
from agent_world_metrics import WorldExtensionMetrics

logger = logging.getLogger(__name__)


class HTTPAPIInterface:
    def __init__(self, host: str = '127.0.0.1', port: int = 0):
        self._server: Optional[ThreadingHTTPServer] = None
        self._thread: Optional[threading.Thread] = None
        self._api_stats = {
            'requests_received': 0,
            'errors': 0,
            'start_time': None,
            'server_running': False,
        }
        # Load unified config
        self._config = WorldRecorderConfig()
        self.host = host or self._config.server_host
        self.port = (port or 0) or self._config.server_port
        # Unified security / metrics
        self.security_manager = SecurityManager()
        self.metrics = WorldExtensionMetrics('worldrecorder')
        
        # Main-thread task queue (process on Kit update stream)
        self._main_queue: deque[tuple[Callable[[], Any], threading.Event, list]] = deque()
        self._queue_lock = threading.Lock()
        self._update_sub = None

        # Session tracking
        self.current_session_id: str | None = None
        self.last_session_id: str | None = None
        self.sessions: dict[str, dict] = {}

    def get_port(self) -> int:
        return self.port

    def get_stats(self) -> dict:
        try:
            if hasattr(self, 'metrics') and self.metrics:
                return self.metrics.get_stats_dict()
        except Exception:
            pass
        return self._api_stats.copy()

    def increment_request_counter(self):
        self._api_stats['requests_received'] += 1

    def increment_error_counter(self):
        self._api_stats['errors'] += 1

    def start(self) -> bool:
        """Start the HTTP server and initialize main thread queue processing."""
        if self._server:
            return True
            
        try:
            # Create handler class using unified factory method
            handler_class = WorldRecorderHTTPHandler.create_handler_class(self, 'worldrecorder')
            
            self._server = ThreadingHTTPServer((self.host, self.port), handler_class)
            
            # Configure socket options for better reuse
            self._server.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self._server.socket.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack('ii', 1, 0))
            
            # Start server thread
            self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
            self._thread.start()
            
            # Initialize metrics
            self.metrics.start_server()
            
            # Subscribe to Kit update stream for main thread processing
            self._setup_main_thread_processing()
            
            # Update status
            self._api_stats['server_running'] = True
            self._api_stats['start_time'] = time.time()
            
            logger.info(f"WorldRecorder HTTP server started on {self.host}:{self.port}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start HTTP server: {e}")
            return False
    
    def _setup_main_thread_processing(self) -> None:
        """Set up Kit main thread processing for USD operations."""
        try:
            import omni.kit.app
            app = omni.kit.app.get_app()
            self._update_sub = app.get_update_event_stream().create_subscription_to_pop(
                self._on_update, name="WorldRecorderHTTPUpdate")
        except Exception as e:
            logger.warning(f"Could not set up main thread processing: {e}")
            # Extension will still work, but USD operations may be unsafe

    def stop(self) -> None:
        """Stop the HTTP server and cleanup resources."""
        if not self._server:
            return
            
        try:
            # Stop main thread processing subscription
            if self._update_sub:
                self._update_sub.unsubscribe()
                self._update_sub = None
                
            # Shutdown server
            self._server.shutdown()
            self._server.server_close()
            
            # Wait for server thread to finish
            if self._thread and self._thread.is_alive():
                self._thread.join(timeout=5.0)
                if self._thread.is_alive():
                    logger.warning("Server thread did not shutdown cleanly")
                    
        except Exception as e:
            logger.error(f"Error during server shutdown: {e}")
        finally:
            # Cleanup state regardless of errors
            self._server = None
            self._thread = None
            self._api_stats['server_running'] = False
            
            # Stop metrics
            try:
                self.metrics.stop_server()
            except Exception as e:
                logger.warning(f"Error stopping metrics: {e}")
                
            logger.info("WorldRecorder HTTP server stopped")

    def _on_update(self, e=None) -> None:
        """Process queued main thread tasks (runs on Kit main thread)."""
        try:
            # Process all queued tasks in this update cycle
            while True:
                with self._queue_lock:
                    if not self._main_queue:
                        break
                    fn, ev, sink = self._main_queue.popleft()
                
                # Execute task and store result
                try:
                    result = fn()
                    sink.append(result)
                except Exception as ex:
                    sink.append({'success': False, 'error': str(ex)})
                finally:
                    ev.set()  # Signal completion to waiting thread
                    
        except Exception as e:
            logger.error(f"Error in main thread update: {e}")

    def run_on_main(self, fn: Callable[[], Any], timeout: float = 5.0) -> Any:
        """Execute a function on the Kit main thread and wait for result.
        
        Args:
            fn: Function to execute on main thread
            timeout: Maximum time to wait for completion
            
        Returns:
            Function result or error dict if timeout/failure
        """
        ev = threading.Event()
        sink: list = []
        
        with self._queue_lock:
            self._main_queue.append((fn, ev, sink))
        
        # Wait for completion
        if ev.wait(timeout):
            return sink[0] if sink else {'success': False, 'error': 'no result'}
        else:
            return {'success': False, 'error': f'timeout after {timeout}s'}
