"""
WorldStreamer API Interface

HTTP API interface following unified agent_world services pattern.
Provides RESTful API endpoints for SRT streaming control.
"""

import logging
import socket
import struct
import threading
import time
from collections import deque
from http.server import ThreadingHTTPServer
from typing import Optional, Dict, Any
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
    
    from agent_world_metrics import setup_worldstreamer_metrics
    METRICS_AVAILABLE = True
except ImportError as e:
    logging.getLogger(__name__).warning(f"Could not import unified metrics system: {e}")
    METRICS_AVAILABLE = False

# For now, assume HTTP services are available (can be enhanced later)
HTTP_AVAILABLE = True

from agent_world_logging import setup_logging
from .http_handler import WorldStreamerHTTPHandler
from .openapi_spec import get_worldstreamer_openapi_spec

logger = logging.getLogger(__name__)


class WorldStreamerAPI:
    """
    WorldStreamer API interface using unified HTTP services.
    
    Provides RESTful endpoints for SRT streaming control with
    standardized authentication, error handling, and OpenAPI documentation.
    """
    
    def __init__(self, config, auth, streaming, port: int):
        """
        Initialize WorldStreamer API interface.
        
        Args:
            config: WorldStreamerConfig instance
            auth: WorldStreamerAuth instance  
            streaming: StreamingInterface instance
            port: HTTP server port (from unified config)
        """
        self._config = config
        self._auth = auth
        self._streaming = streaming
        self._port = port
        self._server = None
        self._server_thread = None
        
        # Initialize API stats for backward compatibility
        self._api_stats = {
            'requests_received': 0,
            'errors': 0,
            'start_time': None,
            'server_running': False
        }
        
        # Initialize unified metrics system
        if METRICS_AVAILABLE:
            self.metrics = setup_worldstreamer_metrics()
        
        logger.info(f"WorldStreamerAPI initialized for port {port}")
    
    def start_server(self) -> Dict[str, Any]:
        """
        Start the HTTP API server.
        
        Returns:
            Dict with server start result
        """
        try:
            if not HTTP_AVAILABLE:
                return {
                    'success': False,
                    'error': 'Unified HTTP services not available'
                }
            
            if self._server:
                return {
                    'success': False,
                    'error': 'Server already running'
                }
            
            # Get OpenAPI specification
            openapi_spec = get_worldstreamer_openapi_spec(
                port=self._port,
                auth_enabled=self._auth.is_enabled()
            )
            
            # Create handler class using unified factory method
            handler_class = WorldStreamerHTTPHandler.create_handler_class(self, 'worldstreamer')
            
            # Create server with socket reuse options (consistent with other extensions)
            self._server = ThreadingHTTPServer((self._config.get('server_host', 'localhost'), self._port), handler_class)
            self._server.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self._server.socket.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack('ii', 1, 0))
            
            # Start server in background thread
            self._server_thread = threading.Thread(target=self._server.serve_forever, daemon=True)
            self._server_thread.start()
            
            # Start metrics system
            if METRICS_AVAILABLE and hasattr(self, 'metrics'):
                self.metrics.start_server()
            else:
                self._api_stats['start_time'] = time.time()
                self._api_stats['server_running'] = True
            logger.info(f"WorldStreamer API server started on port {self._port}")
            
            return {
                'success': True,
                'message': f'WorldStreamer API server started on port {self._port}',
                'port': self._port,
                'endpoints': self._get_endpoint_summary()
            }
                
        except Exception as e:
            error_msg = f"Failed to start WorldStreamer API server: {e}"
            logger.error(error_msg)
            return {
                'success': False,
                'error': error_msg
            }
    
    def stop_server(self) -> Dict[str, Any]:
        """
        Stop the HTTP API server.
        
        Returns:
            Dict with server stop result
        """
        try:
            if not self._server:
                return {
                    'success': False,
                    'error': 'No server running'
                }
            
            # Shutdown the ThreadingHTTPServer
            self._server.shutdown()
            self._server.server_close()
            
            # Stop metrics system
            if METRICS_AVAILABLE and hasattr(self, 'metrics'):
                self.metrics.stop_server()
            else:
                self._api_stats['server_running'] = False
            
            self._server = None
            self._server_thread = None
            
            logger.info("WorldStreamer API server stopped")
            return {
                'success': True,
                'message': 'WorldStreamer API server stopped'
            }
                
        except Exception as e:
            error_msg = f"Failed to stop WorldStreamer API server: {e}"
            logger.error(error_msg)
            return {
                'success': False,
                'error': error_msg
            }
    
    def get_server_status(self) -> Dict[str, Any]:
        """
        Get API server status information.
        
        Returns:
            Dict with server status
        """
        try:
            if not self._server:
                return {
                    'running': False,
                    'port': self._port,
                    'message': 'Server not initialized'
                }
            
            # Check if server thread is alive
            is_running = self._server_thread and self._server_thread.is_alive()
            
            return {
                'running': is_running,
                'port': self._port,
                'server_info': {
                    'thread_alive': is_running,
                    'server_address': self._server.server_address if self._server else None
                },
                'endpoints': self._get_endpoint_summary(),
                'authentication': {
                    'enabled': self._auth.is_enabled(),
                    'status': self._auth.get_health_status()
                },
                'streaming_status': self._streaming.get_health_status()
            }
            
        except Exception as e:
            logger.error(f"Failed to get server status: {e}")
            return {
                'running': False,
                'port': self._port,
                'error': str(e)
            }
    
    def _get_endpoint_summary(self) -> Dict[str, str]:
        """
        Get summary of available API endpoints.
        
        Returns:
            Dict mapping endpoint paths to descriptions
        """
        return {
            '/streaming/start': 'Start SRT streaming',
            '/streaming/stop': 'Stop SRT streaming', 
            '/streaming/status': 'Get streaming status',
            '/streaming/urls': 'Get streaming URI',
            '/streaming/environment/validate': 'Validate streaming environment',
            '/health': 'Extension health check',
            '/openapi.json': 'OpenAPI specification',
            '/docs': 'API documentation'
        }
    
    def get_health_status(self) -> Dict[str, Any]:
        """
        Get comprehensive API health status.
        
        Returns:
            Dict with health information
        """
        try:
            health = {
                'api_functional': True,
                'server_running': self._server is not None,
                'port': self._port,
                'http_services_available': HTTP_AVAILABLE
            }
            
            # Add server health if running
            if self._server:
                try:
                    server_health = self._server.get_health()
                    health['server_health'] = server_health
                except Exception as e:
                    health['server_health'] = {'error': str(e)}
            
            # Add component health
            health['components'] = {
                'streaming_interface': self._streaming.get_health_status(),
                'authentication': self._auth.get_health_status(),
                'configuration': self._config.get_health_status()
            }
            
            return health
            
        except Exception as e:
            logger.error(f"Health status check failed: {e}")
            return {
                'api_functional': False,
                'error': str(e)
            }
