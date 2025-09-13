"""
WorldStreamer HTTP Request Handler

Handles HTTP requests for WorldStreamer streaming control API.
Processes streaming control operations and returns standardized responses.
"""

import json
import logging
import os
import time
from pathlib import Path
from typing import Dict, Any, Optional
from urllib.parse import urlparse, parse_qs

# Unified HTTP handler import with fallback
try:
    import sys as _sys
    from pathlib import Path as _P
    _cur = _P(__file__).resolve()
    for _ in range(10):
        if _cur.name == 'agentworld-extensions':
            _sys.path.insert(0, str(_cur))
            break
        _cur = _cur.parent
    from agent_world_http import WorldHTTPHandler
    UNIFIED = True
except Exception:
    from http.server import BaseHTTPRequestHandler as WorldHTTPHandler  # type: ignore
    UNIFIED = False

# Import centralized version management (optional)
def _find_and_import_versions():
    try:
        import sys
        # Strategy 1: Search upward in directory tree for agentworld-extensions
        current = Path(__file__).resolve()
        for _ in range(10):
            if current.name == 'agentworld-extensions' or (current / 'agent_world_versions.py').exists():
                sys.path.insert(0, str(current))
                from agent_world_versions import get_version, get_service_name
                return get_version, get_service_name
            if current.parent == current:
                break
            current = current.parent
        # Strategy 2: Environment variable fallback
        env_path = os.getenv('AGENT_WORLD_VERSIONS_PATH')
        if env_path:
            sys.path.insert(0, env_path)
            from agent_world_versions import get_version, get_service_name
            return get_version, get_service_name
        return None, None
    except Exception:
        return None, None

try:
    get_version, get_service_name = _find_and_import_versions()
    VERSION_AVAILABLE = get_version is not None
except Exception:
    VERSION_AVAILABLE = False

logger = logging.getLogger(__name__)


class WorldStreamerHTTPHandler(WorldHTTPHandler):
    """
    HTTP request handler for WorldStreamer streaming control API.
    
    Processes HTTP requests and delegates to appropriate streaming interface methods.
    Provides standardized response formatting and error handling.
    """
    
    api_interface = None
    
    def get_routes(self) -> Dict[str, Any]:
        """
        Get route mappings for the unified HTTP handler.
        
        Returns:
            Dict mapping endpoint names to handler functions
        """
        return {
            'health': self._handle_health_unified,
            'streaming/start': self._handle_start_streaming_unified,
            'streaming/stop': self._handle_stop_streaming_unified,
            'streaming/status': self._handle_get_streaming_status_unified,
            'streaming/urls': self._handle_get_streaming_urls_unified,
            'streaming/environment/validate': self._handle_validate_environment_unified,
        }
    
    
    def _handle_health(self, request_data: Dict[str, Any], headers: Dict[str, str]) -> Dict[str, Any]:
        """Handle health check requests."""
        try:
            health_status = self.api_interface._streaming.get_health_status()
            
            return {
                'success': True,
                'service': 'WorldStreamer',
                'status': 'healthy' if health_status.get('streaming_interface_functional') else 'degraded',
                'timestamp': self._get_timestamp(),
                'details': health_status
            }
            
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return {
                'success': False,
                'service': 'WorldStreamer',
                'status': 'unhealthy',
                'error': str(e)
            }
    
    def _handle_start_streaming(self, request_data: Dict[str, Any], headers: Dict[str, str]) -> Dict[str, Any]:
        """Handle streaming start requests."""
        try:
            # Extract optional server IP override
            server_ip = request_data.get('server_ip')
            
            # Start streaming
            result = self.api_interface._streaming.start_streaming(server_ip=server_ip)
            
            # Add timestamp to response
            result['timestamp'] = self._get_timestamp()
            
            return result
            
        except Exception as e:
            logger.error(f"Start streaming request failed: {e}")
            return {
                'success': False,
                'error': f'Start streaming failed: {e}',
                'timestamp': self._get_timestamp()
            }
    
    def _handle_stop_streaming(self, request_data: Dict[str, Any], headers: Dict[str, str]) -> Dict[str, Any]:
        """Handle streaming stop requests."""
        try:
            result = self.api_interface._streaming.stop_streaming()
            
            # Add timestamp to response  
            result['timestamp'] = self._get_timestamp()
            
            return result
            
        except Exception as e:
            logger.error(f"Stop streaming request failed: {e}")
            return {
                'success': False,
                'error': f'Stop streaming failed: {e}',
                'timestamp': self._get_timestamp()
            }
    
    def _handle_get_streaming_status(self, request_data: Dict[str, Any], headers: Dict[str, str]) -> Dict[str, Any]:
        """Handle streaming status requests."""
        try:
            result = self.api_interface._streaming.get_streaming_status()
            
            # Add timestamp to response
            result['timestamp'] = self._get_timestamp()
            
            return result
            
        except Exception as e:
            logger.error(f"Get streaming status failed: {e}")
            return {
                'success': False,
                'error': f'Status retrieval failed: {e}',
                'timestamp': self._get_timestamp()
            }
    
    def _handle_get_streaming_urls(self, request_data: Dict[str, Any], headers: Dict[str, str]) -> Dict[str, Any]:
        """Handle streaming URLs requests."""
        try:
            # Extract optional server IP override
            server_ip = request_data.get('server_ip')
            
            result = self.api_interface._streaming.get_streaming_urls(server_ip=server_ip)
            
            # Add timestamp to response
            result['timestamp'] = self._get_timestamp()
            
            return result
            
        except Exception as e:
            logger.error(f"Get streaming URLs failed: {e}")
            return {
                'success': False,
                'error': f'URL generation failed: {e}',
                'timestamp': self._get_timestamp()
            }
    
    def _handle_validate_environment(self, request_data: Dict[str, Any], headers: Dict[str, str]) -> Dict[str, Any]:
        """Handle environment validation requests."""
        try:
            validation_result = self.api_interface._streaming.validate_environment()
            
            return {
                'success': True,
                'validation': validation_result,
                'timestamp': self._get_timestamp()
            }
            
        except Exception as e:
            logger.error(f"Environment validation failed: {e}")
            return {
                'success': False,
                'error': f'Environment validation failed: {e}',
                'timestamp': self._get_timestamp()
            }
    
    def _create_error_response(self, status_code: int, error_message: str) -> Dict[str, Any]:
        """
        Create standardized error response.
        
        Args:
            status_code: HTTP status code
            error_message: Error message
            
        Returns:
            Dict with error response format
        """
        error_response = {
            'success': False,
            'error': error_message,
            'error_code': f'HTTP_{status_code}',
            'timestamp': self._get_timestamp()
        }
        
        return {
            'status_code': status_code,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps(error_response)
        }
    
    def _get_timestamp(self) -> str:
        """Get current timestamp in ISO format."""
        from datetime import datetime
        return datetime.utcnow().isoformat() + 'Z'
    
    def get_supported_routes(self) -> Dict[str, Dict[str, str]]:
        """
        Get supported HTTP routes.
        
        Returns:
            Dict mapping methods to route descriptions
        """
        routes = {}
        for method, method_routes in self._routes.items():
            routes[method] = {}
            for route in method_routes.keys():
                # Generate description based on route
                if 'health' in route:
                    routes[method][route] = 'Health check endpoint'
                elif 'start' in route:
                    routes[method][route] = 'Start RTMP streaming'
                elif 'stop' in route:
                    routes[method][route] = 'Stop RTMP streaming'
                elif 'status' in route:
                    routes[method][route] = 'Get streaming status'
                elif 'urls' in route:
                    routes[method][route] = 'Get streaming URLs'
                elif 'validate' in route:
                    routes[method][route] = 'Validate streaming environment'
                else:
                    routes[method][route] = 'WorldStreamer endpoint'
        
        return routes
    
    # Unified handler methods (for integration with unified HTTP system)
    def _handle_health_unified(self, method: str, data: Any) -> Dict[str, Any]:
        """Unified handler for health check."""
        if method != 'GET':
            return {'success': False, 'error': 'Health check requires GET method'}
        return self._handle_health(data or {}, {})
    
    def _handle_start_streaming_unified(self, method: str, data: Any) -> Dict[str, Any]:
        """Unified handler for starting streaming."""
        if method != 'POST':
            return {'success': False, 'error': 'Start streaming requires POST method'}
        return self._handle_start_streaming(data or {}, {})
    
    def _handle_stop_streaming_unified(self, method: str, data: Any) -> Dict[str, Any]:
        """Unified handler for stopping streaming."""
        if method != 'POST':
            return {'success': False, 'error': 'Stop streaming requires POST method'}
        return self._handle_stop_streaming(data or {}, {})
    
    def _handle_get_streaming_status_unified(self, method: str, data: Any) -> Dict[str, Any]:
        """Unified handler for getting streaming status."""
        if method != 'GET':
            return {'success': False, 'error': 'Get streaming status requires GET method'}
        return self._handle_get_streaming_status(data or {}, {})
    
    def _handle_get_streaming_urls_unified(self, method: str, data: Any) -> Dict[str, Any]:
        """Unified handler for getting streaming URLs."""
        if method != 'GET':
            return {'success': False, 'error': 'Get streaming URLs requires GET method'}
        return self._handle_get_streaming_urls(data or {}, {})
    
    def _handle_validate_environment_unified(self, method: str, data: Any) -> Dict[str, Any]:
        """Unified handler for validating streaming environment."""
        if method != 'GET':
            return {'success': False, 'error': 'Validate environment requires GET method'}
        return self._handle_validate_environment(data or {}, {})