"""
Unified HTTP request handling for agenTW∞rld Extensions.

Eliminates code duplication across all World* extensions by providing:
- Common HTTP server request/response patterns
- Standard CORS, authentication, and rate limiting
- Consistent error handling and logging
- Unified metrics collection integration

Usage:
    from agentworld_core.http import WorldHTTPHandler
    
    class MyExtensionHTTPHandler(WorldHTTPHandler):
        def __init__(self, api_interface):
            super().__init__(api_interface, 'myextension')
        
        def get_routes(self):
            return {
                'my_endpoint': self._handle_my_endpoint,
                'another_endpoint': self._handle_another
            }
"""

import json
import logging
import time
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from typing import Dict, Any, Optional, Callable, Tuple
from urllib.parse import parse_qs, urlparse

logger = logging.getLogger(__name__)

try:
    from .versions import get_version, get_service_name
    VERSION_AVAILABLE = True
except ImportError:
    get_version = None
    get_service_name = None
    VERSION_AVAILABLE = False

# Try to import HTTP configuration
def _load_http_config():
    """Load HTTP configuration from agent-world-http.json."""
    try:
        config_path = Path(__file__).with_name("agent-world-http.json")
        with open(config_path, 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"Could not load HTTP config: {e}")
        return {}

# Initialize HTTP configuration (version info already handled above)
HTTP_CONFIG = _load_http_config()


class WorldHTTPHandler(BaseHTTPRequestHandler):
    """
    Base HTTP request handler for World* extensions.
    
    Provides unified request handling patterns while allowing extensions
    to define their specific routes and business logic.
    """
    
    # Class-level reference to API interface - set by subclasses
    api_interface = None
    
    def __init__(self, *args, extension_name: str = None, **kwargs):
        self.extension_name = extension_name or 'unknown'
        super().__init__(*args, **kwargs)
    
    @classmethod
    def create_handler_class(cls, api_interface, extension_name: str):
        """
        Factory method to create a handler class bound to an API interface.
        
        Args:
            api_interface: The API interface instance
            extension_name: Name of the extension (e.g., 'worldbuilder')
            
        Returns:
            HTTP handler class ready for use with HTTPServer
        """
        class BoundHandler(cls):
            def __init__(self, *args, **kwargs):
                # Set class-level reference for this instance
                BoundHandler.api_interface = api_interface
                super().__init__(*args, extension_name=extension_name, **kwargs)
            
            def get_routes(self) -> Dict[str, Callable]:
                """Defer to the subclass' route mapping."""
                try:
                    return super().get_routes()  # type: ignore[misc]
                except Exception:
                    return {}
        
        return BoundHandler
    
    def log_message(self, format, *args):
        """Override default HTTP logging to use our logger with proper levels."""
        if hasattr(self.api_interface, '_config'):
            config = self.api_interface._config
            if config.get('debug_mode') or config.get('verbose_logging'):
                logger.info(f"HTTP {format % args}")
        # Otherwise, suppress the default logging to stderr
    
    def do_OPTIONS(self):
        """Handle CORS preflight requests."""
        self._send_cors_response()
    
    def do_GET(self):
        """Handle GET requests."""
        self._handle_request('GET')
    
    def do_POST(self):
        """Handle POST requests."""
        self._handle_request('POST')
    
    def _send_cors_response(self):
        """Send CORS preflight response with security headers."""
        cors_config = HTTP_CONFIG.get('cors_headers', {})

        self.send_response(200)

        # Add security headers
        self._add_security_headers()

        # Add CORS headers
        self.send_header('Access-Control-Allow-Origin',
                        cors_config.get('access_control_allow_origin', '*'))
        self.send_header('Access-Control-Allow-Methods',
                        cors_config.get('access_control_allow_methods', 'GET, POST, OPTIONS'))
        self.send_header('Access-Control-Allow-Headers',
                        cors_config.get('access_control_allow_headers', 'Content-Type, Authorization'))
        self.send_header('Access-Control-Max-Age',
                        cors_config.get('access_control_max_age', '86400'))
        self.send_header('Vary', cors_config.get('vary_header', 'Origin'))
        self.end_headers()
    
    def _validate_security(self, method: str, client_ip: str) -> Tuple[bool, int, Optional[str]]:
        """Run rate limiting and authentication checks using the security manager."""
        manager = getattr(self.api_interface, 'security_manager', None)
        if not manager:
            return True, 200, None

        try:
            is_valid, error_msg = manager.validate_request(self.headers, client_ip, method, self.path)
        except Exception as exc:  # pragma: no cover - defensive fallback
            logger.warning(f"Security validation failed: {exc}")
            return True, 200, None

        if is_valid:
            return True, 200, None

        status_code = 401
        if error_msg == "Rate limit exceeded":
            status_code = 429
            metrics = getattr(self.api_interface, 'metrics', None)
            if metrics:
                try:
                    metrics.increment_rate_limited()
                except Exception:
                    pass
        else:
            metrics = getattr(self.api_interface, 'metrics', None)
            if metrics:
                try:
                    metrics.increment_auth_failures()
                except Exception:
                    pass

        return False, status_code, error_msg

    def _handle_request(self, method: str):
        """Main request handler with unified routing."""
        try:
            # Parse URL first
            parsed_url = urlparse(self.path)
            endpoint = parsed_url.path.strip('/')
            params = parse_qs(parsed_url.query)
            
            # Update request counter
            if hasattr(self.api_interface, 'metrics'):
                self.api_interface.metrics.increment_requests()
                try:
                    self.api_interface.metrics.increment_endpoint(endpoint)
                except Exception:
                    pass
            elif hasattr(self.api_interface, 'increment_request_counter'):
                self.api_interface.increment_request_counter()
            
            client_ip = self.client_address[0] if self.client_address else '127.0.0.1'

            # Combined rate limiting + authentication check
            secure_ok, failure_status, failure_reason = self._validate_security(method, client_ip)
            if not secure_ok:
                self._send_error_response(failure_status, failure_reason or 'Unauthorized')
                return

            # Route the request
            start_t = time.time()
            if method == 'GET':
                response = self._handle_get_request(endpoint, params)
            elif method == 'POST':
                # Read POST data
                content_length = int(self.headers.get('Content-Length', 0))
                post_data = self.rfile.read(content_length) if content_length > 0 else b''
                
                try:
                    data = json.loads(post_data.decode()) if post_data else {}
                except json.JSONDecodeError:
                    self._send_error_response(400, 'Invalid JSON')
                    return
                
                response = self._handle_post_request(endpoint, data)
            else:
                response = {'success': False, 'error': 'Method not allowed'}
            
            # Send response
            # Special-case docs/OpenAPI: 200 only when a valid spec is returned
            if endpoint in ('docs', 'openapi.json') and isinstance(response, dict) and response.get('_raw_text') is None:
                is_spec = 'openapi' in response
                self._send_json_response(response, status_code=200 if is_spec else 500)
                return
            if isinstance(response, dict) and response.get('_raw_text') is not None:
                # Raw response support with optional content type override
                content_type = response.get('_content_type', 'text/plain; version=0.0.4')
                self._send_raw_response(response.get('_raw_text', ''), content_type)
            else:
                self._send_json_response(response)
            try:
                cfg=getattr(self.api_interface, '_config', {})
                if cfg.get('json_logging'):
                    import json as _json
                    log_entry={
                        'ts': time.time(), 'method': method, 'endpoint': endpoint,
                        'duration_ms': (time.time()-start_t)*1000.0,
                        'success': (response.get('success') if isinstance(response, dict) else None)
                    }
                    logger.info(_json.dumps(log_entry))
            except Exception:
                pass
            # Record duration
            try:
                if hasattr(self.api_interface, 'metrics') and getattr(self.api_interface, 'metrics'):
                    self.api_interface.metrics.record_request_duration_ms((time.time() - start_t) * 1000.0)
            except Exception:
                pass
        
        except Exception as e:
            logger.error(f"Request handler error: {e}", exc_info=True)
            if hasattr(self.api_interface, 'metrics'):
                self.api_interface.metrics.increment_errors()
            elif hasattr(self.api_interface, 'increment_error_counter'):
                self.api_interface.increment_error_counter()
            self._send_error_response(500, str(e))
    
    def _handle_get_request(self, endpoint: str, params: Dict) -> Dict[str, Any]:
        """Handle GET requests - unified standard endpoints + extension routes."""
        
        # Standard endpoints (identical across all extensions)
        if endpoint == 'health':
            return self._handle_health_endpoint()
        elif endpoint in ['metrics', 'metrics.json']:
            return self._handle_metrics_json()
        elif endpoint == 'metrics.prom':
            return self._handle_metrics_prometheus()
        elif endpoint in ['docs', 'openapi.json']:
            return self._handle_openapi_endpoint()
        elif endpoint in ['status', 'ping']:
            return self._handle_status_endpoint()
        
        # Extension-specific routes
        routes = self.get_routes()
        if endpoint in routes:
            try:
                return routes[endpoint]('GET', params)
            except Exception as e:
                return {'success': False, 'error': f'Handler error: {str(e)}'}
        
        # Unknown endpoint
        error_config = HTTP_CONFIG.get('error_handling', {})
        return {
            'success': False, 
            'error': error_config.get('not_found_message', f'Unknown GET endpoint: {endpoint}')
        }
    
    def _handle_post_request(self, endpoint: str, data: Dict) -> Dict[str, Any]:
        """Handle POST requests - extension-specific routes only."""
        
        # Extension-specific routes
        routes = self.get_routes()
        if endpoint in routes:
            try:
                return routes[endpoint]('POST', data)
            except Exception as e:
                return {'success': False, 'error': f'Handler error: {str(e)}'}
        
        # Unknown endpoint
        error_config = HTTP_CONFIG.get('error_handling', {})
        return {
            'success': False,
            'error': error_config.get('not_found_message', f'Unknown POST endpoint: {endpoint}')
        }
    
    def _handle_health_endpoint(self) -> Dict[str, Any]:
        """Standard health check endpoint."""
        if VERSION_AVAILABLE:
            service_name = get_service_name(self.extension_name)
            version = get_version(self.extension_name, 'api_version')
        else:
            service_name = f'Agent {self.extension_name.title()} API'
            version = '0.1.0'
        
        port = getattr(self.api_interface, 'get_port', lambda: 8900)()
        
        response = {
            'success': True,
            'service': service_name,
            'version': version,
            'url': f'http://localhost:{port}',
            'timestamp': time.time()
        }
        
        # Add extension-specific health info if available
        if hasattr(self.api_interface, 'get_health_info'):
            try:
                health_info = self.api_interface.get_health_info()
                response.update(health_info)
            except Exception as e:
                logger.warning(f"Failed to get extension health info: {e}")
        
        return response
    
    def _handle_metrics_json(self) -> Dict[str, Any]:
        """Standard JSON metrics endpoint."""
        if hasattr(self.api_interface, 'metrics'):
            return self.api_interface.metrics.get_json_metrics()
        elif hasattr(self.api_interface, 'get_stats'):
            stats = self.api_interface.get_stats()
            return {'success': True, 'metrics': stats}
        else:
            return {'success': False, 'error': 'Metrics not available'}
    
    def _handle_metrics_prometheus(self) -> Dict[str, Any]:
        """Standard Prometheus metrics endpoint."""
        if hasattr(self.api_interface, 'metrics'):
            return {'success': True, '_raw_text': self.api_interface.metrics.get_prometheus_metrics()}
        else:
            return {'success': False, 'error': 'Prometheus metrics not available'}
    
    def _handle_openapi_endpoint(self) -> Dict[str, Any]:
        """Standard OpenAPI specification endpoint."""
        try:
            # Try to import extension-specific openapi module
            module_name = f'omni.agent.{self.extension_name}.openapi_spec'
            spec_module = __import__(module_name, fromlist=['build_openapi_spec'])
            
            port = getattr(self.api_interface, 'get_port', lambda: 8900)()
            return spec_module.build_openapi_spec(port)
        except Exception as e:
            logger.warning(f"OpenAPI spec generation failed: {e}")
            return {'success': False, 'error': 'OpenAPI specification not available'}
    
    def _handle_status_endpoint(self) -> Dict[str, Any]:
        """Standard status check endpoint."""
        return {
            'success': True,
            'status': 'running',
            'extension': self.extension_name,
            'timestamp': time.time()
        }
    
    def get_routes(self) -> Dict[str, Callable]:
        """
        Override in subclasses to define extension-specific routes.

        Returns:
            Dictionary mapping endpoint names to handler functions.
            Handler functions receive (method, data) and return dict response.
        """
        return {}

    def _add_security_headers(self):
        """Add security headers to prevent various web-based attacks."""
        security_config = HTTP_CONFIG.get('security_headers', {})

        # Content Security Policy - prevent XSS and code injection
        csp = security_config.get('content_security_policy',
                                 "default-src 'self'; script-src 'none'; object-src 'none'; "
                                 "style-src 'self' 'unsafe-inline'; img-src 'self' data:; "
                                 "connect-src 'self'; font-src 'self'; media-src 'none'; "
                                 "frame-src 'none'; form-action 'self'")
        self.send_header('Content-Security-Policy', csp)

        # X-Content-Type-Options - prevent MIME type sniffing
        self.send_header('X-Content-Type-Options',
                        security_config.get('x_content_type_options', 'nosniff'))

        # X-Frame-Options - prevent clickjacking
        self.send_header('X-Frame-Options',
                        security_config.get('x_frame_options', 'DENY'))

        # X-XSS-Protection - enable browser XSS protection
        self.send_header('X-XSS-Protection',
                        security_config.get('x_xss_protection', '1; mode=block'))

        # Referrer-Policy - control referrer information
        self.send_header('Referrer-Policy',
                        security_config.get('referrer_policy', 'strict-origin-when-cross-origin'))

        # Permissions-Policy - control browser features
        permissions_policy = security_config.get('permissions_policy',
                                                 'geolocation=(), microphone=(), camera=(), '
                                                 'payment=(), usb=(), magnetometer=(), gyroscope=()')
        self.send_header('Permissions-Policy', permissions_policy)

        # Strict-Transport-Security - enforce HTTPS (only if configured)
        if security_config.get('enable_hsts', False):
            hsts_value = security_config.get('hsts_max_age', 'max-age=31536000; includeSubDomains')
            self.send_header('Strict-Transport-Security', hsts_value)
    
    def _send_json_response(self, data: Dict[str, Any], status_code: int = 200):
        """Send JSON response with proper headers including security headers."""
        response_config = HTTP_CONFIG.get('response_formats', {})
        cors_config = HTTP_CONFIG.get('cors_headers', {})

        self.send_response(status_code)
        self.send_header('Content-Type', 'application/json')

        # Add security headers
        self._add_security_headers()

        # Add CORS headers
        self.send_header('Access-Control-Allow-Origin',
                        cors_config.get('access_control_allow_origin', '*'))
        self.send_header('Vary', cors_config.get('vary_header', 'Origin'))
        self.end_headers()
        
        # Use configured JSON formatting
        json_response = json.dumps(
            data, 
            ensure_ascii=response_config.get('json_ensure_ascii', False),
            indent=response_config.get('json_indent'),
            separators=response_config.get('json_separators', (',', ':'))
        )
        
        self.wfile.write(json_response.encode('utf-8'))
    
    def _send_raw_response(self, content: str, content_type: str, status_code: int = 200):
        """Send raw text response (for Prometheus metrics) with security headers."""
        cors_config = HTTP_CONFIG.get('cors_headers', {})

        self.send_response(status_code)
        self.send_header('Content-Type', content_type)

        # Add security headers
        self._add_security_headers()

        # Add CORS headers
        self.send_header('Access-Control-Allow-Origin',
                        cors_config.get('access_control_allow_origin', '*'))
        self.send_header('Vary', cors_config.get('vary_header', 'Origin'))
        self.end_headers()
        
        self.wfile.write(content.encode('utf-8'))
    
    def _send_error_response(self, status_code: int, error_message: str):
        """Send error response with proper status code and security headers."""
        cors_config = HTTP_CONFIG.get('cors_headers', {})

        self.send_response(status_code)
        self.send_header('Content-Type', 'application/json')

        # Add security headers
        self._add_security_headers()

        # Add CORS headers
        self.send_header('Access-Control-Allow-Origin',
                        cors_config.get('access_control_allow_origin', '*'))
        self.send_header('Vary', cors_config.get('vary_header', 'Origin'))

        # Add WWW-Authenticate header for 401 Unauthorized responses (uniform across extensions)
        if status_code == 401:
            realm = f"isaac-sim-{getattr(self, 'extension_name', 'world')}"
            self.send_header('WWW-Authenticate', f'HMAC-SHA256 realm="{realm}"')

        self.end_headers()
        
        response = {
            'success': False,
            'error': error_message,
            'timestamp': time.time()
        }
        
        self.wfile.write(json.dumps(response).encode('utf-8'))


# Example usage for extensions
class ExampleExtensionHTTPHandler(WorldHTTPHandler):
    """Example of how extensions should use the unified HTTP handler."""
    
    def get_routes(self) -> Dict[str, Callable]:
        """Define extension-specific routes."""
        return {
            'create_something': self._handle_create,
            'query_something': self._handle_query,
            'transform_something': self._handle_transform
        }
    
    def _handle_create(self, method: str, data: Any) -> Dict[str, Any]:
        """Handle create operation."""
        if method == 'POST':
            # Extension-specific create logic here
            return {'success': True, 'created': True}
        else:
            return {'success': False, 'error': 'Create requires POST method'}
    
    def _handle_query(self, method: str, data: Any) -> Dict[str, Any]:
        """Handle query operation."""
        if method == 'GET':
            # Extension-specific query logic here
            return {'success': True, 'results': []}
        else:
            return {'success': False, 'error': 'Query requires GET method'}
    
    def _handle_transform(self, method: str, data: Any) -> Dict[str, Any]:
        """Handle transform operation."""
        if method == 'POST':
            # Extension-specific transform logic here
            return {'success': True, 'transformed': True}
        else:
            return {'success': False, 'error': 'Transform requires POST method'}


if __name__ == "__main__":
    # Test the unified HTTP handler
    logging.basicConfig(level=logging.INFO)
    logger.info("agenTW∞rld Extensions Unified HTTP Handler")
    logger.info(f"Version management available: {VERSION_AVAILABLE}")
    logger.info(f"HTTP config loaded: {bool(HTTP_CONFIG)}")
    
    if HTTP_CONFIG:
        logger.info("HTTP Configuration:")
        for section, config in HTTP_CONFIG.items():
            if not section.startswith('_'):
                val = len(config) if isinstance(config, dict) else config
                logger.info(f"  {section}: {val}")
