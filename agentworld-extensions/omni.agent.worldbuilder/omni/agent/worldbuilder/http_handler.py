"""
HTTP request handler for Agent WorldBuilder API endpoints (unified HTTP).
"""

import logging

from agentworld_core.logging import module_logger

from .http import WorldBuilderController
from .services import WorldBuilderService
from .errors import error_response

try:
    from agentworld_core.http import WorldHTTPHandler
    UNIFIED = True
except ImportError:
    from http.server import BaseHTTPRequestHandler as WorldHTTPHandler  # type: ignore
    UNIFIED = False

logger = logging.getLogger(__name__)
request_logger = module_logger(service='worldbuilder', component='http_handler')



class WorldBuilderHTTPHandler(WorldHTTPHandler):
    """HTTP request handler for Agent WorldBuilder API endpoints (unified)."""

    api_interface = None

    @property
    def controller(self) -> WorldBuilderController:
        if not hasattr(self, '_controller') or self._controller is None:
            config = getattr(self.api_interface, '_config', None)
            service = WorldBuilderService(self.api_interface, config=config)
            self._controller = WorldBuilderController(service)
        return self._controller

    def get_routes(self):  # type: ignore[override]
        """Return route mappings for unified HTTP handler."""
        return {
            'get_extension_stats': self._handle_stats,
            'stats': self._handle_stats,
            'add_element': self._handle_add_element,
            'create_batch': self._handle_create_batch,
            'place_asset': self._handle_place_asset,
            'transform_asset': self._handle_transform_asset,
            'batch_info': self._handle_batch_info,
            'list_batches': self._handle_list_batches,
            'request_status': self._handle_request_status,
            'remove_element': self._handle_remove_element,
            'clear_path': self._handle_clear_path,
            'get_scene': self._handle_get_scene,
            'scene_contents': self._handle_get_scene,
            'list_elements': self._handle_list_elements,
            'scene_status': self._handle_scene_status,
            'query/objects_by_type': self._handle_query_by_type,
            'query/objects_in_bounds': self._handle_query_in_bounds,
            'query/objects_near_point': self._handle_query_near_point,
            'calculate_bounds': self._handle_calculate_bounds,
            'find_ground_level': self._handle_find_ground_level,
            'align_objects': self._handle_align_objects,
            'transform/calculate_bounds': self._handle_calculate_bounds,
            'transform/find_ground_level': self._handle_find_ground_level,
            'transform/align_objects': self._handle_align_objects,
        }
    
    # HTTP request handlers - unified base handles parsing, auth, and dispatch
    
    def _handle_stats(self, method: str = 'GET', request_data: dict | None = None):
        """Handle stats request."""
        return self.controller.get_stats()

    def _handle_add_element(self, method: str, request_data: dict):
        """Handle add element request."""
        if method != 'POST':
            request_logger.warning('method_not_allowed', extra={'route': 'add_element', 'method': method})
            return error_response('METHOD_NOT_ALLOWED', 'add_element requires POST method', details={'method': method})
        return self.controller.add_element(request_data or {})
    
    def _handle_health(self):
        """Handle health check request."""
        return self.controller.get_health()
    
    def _handle_metrics(self, request_data: dict):
        """Handle metrics endpoint request."""
        return self.controller.get_metrics()
    
    def _get_prometheus_metrics(self) -> str:
        """Get Prometheus formatted metrics."""
        try:
            return self.controller.get_prometheus_metrics()
        except Exception as exc:
            request_logger.exception('prometheus_metrics_error', extra={'error': str(exc)})
            return "# Error generating metrics\n"
    
    # HTTP response helpers handled by unified base class
    def _handle_create_batch(self, method: str, request_data: dict):
        """Handle create batch request.""" 
        if method != 'POST':
            request_logger.warning('method_not_allowed', extra={'route': 'create_batch', 'method': method})
            return error_response('METHOD_NOT_ALLOWED', 'create_batch requires POST method', details={'method': method})
        return self.controller.create_batch(request_data or {})

    def _handle_place_asset(self, method: str, request_data: dict):
        """Handle place asset request."""
        if method != 'POST':
            request_logger.warning('method_not_allowed', extra={'route': 'place_asset', 'method': method})
            return error_response('METHOD_NOT_ALLOWED', 'place_asset requires POST method', details={'method': method})
        return self.controller.place_asset(request_data or {})

    # Add other handler methods as needed...
    def _handle_transform_asset(self, method: str, request_data: dict):
        """Handle asset transformation request."""
        if method != 'POST':
            request_logger.warning('method_not_allowed', extra={'route': 'transform_asset', 'method': method})
            return error_response('METHOD_NOT_ALLOWED', 'transform_asset requires POST method', details={'method': method})
        return self.controller.transform_asset(request_data or {})

    def _handle_batch_info(self, method: str, request_data: dict):
        """Handle batch info request."""
        return self.controller.batch_info(request_data or {})

    def _handle_list_batches(self, method: str, request_data: dict):
        """Handle list batches request using stage discovery."""
        if method != 'GET':
            request_logger.warning('method_not_allowed', extra={'route': 'list_batches', 'method': method})
            return error_response('METHOD_NOT_ALLOWED', 'list_batches requires GET method', details={'method': method})
        return self.controller.list_batches()

    def _handle_request_status(self, method: str, request_data: dict):
        """Handle request status check."""
        return self.controller.request_status(request_data or {})
    
    def _handle_remove_element(self, method: str, request_data: dict):
        """Handle remove element request."""
        if method != 'POST':
            request_logger.warning('method_not_allowed', extra={'route': 'remove_element', 'method': method})
            return error_response('METHOD_NOT_ALLOWED', 'remove_element requires POST method', details={'method': method})
        return self.controller.remove_element(request_data or {})

    def _handle_clear_path(self, method: str, request_data: dict):
        """Handle clear path request."""
        if method != 'POST':
            request_logger.warning('method_not_allowed', extra={'route': 'clear_path', 'method': method})
            return error_response('METHOD_NOT_ALLOWED', 'clear_path requires POST method', details={'method': method})
        return self.controller.clear_path(request_data or {})

    def _handle_get_scene(self, method: str, request_data: dict):
        """Handle get scene request."""
        return self.controller.get_scene(request_data or {})

    def _handle_list_elements(self, method: str, request_data: dict):
        """Handle list elements request."""
        return self.controller.list_elements(request_data or {})

    def _handle_scene_status(self, method: str = 'GET', request_data: dict | None = None):
        """Handle scene status request."""
        return self.controller.scene_status()

    def _get_scene_status(self):
        """Get scene health and basic statistics."""
        return self.controller.scene_status()
    
    def _handle_query_by_type(self, method: str, request_data: dict):
        """Handle query by type request."""
        return self.controller.query_objects_by_type(request_data or {})
    
    def _handle_query_in_bounds(self, method: str, request_data: dict):
        """Handle query in bounds request."""
        return self.controller.query_objects_in_bounds(request_data or {})
    
    def _handle_query_near_point(self, method: str, request_data: dict):
        """Handle query near point request."""
        return self.controller.query_objects_near_point(request_data or {})

    def _handle_calculate_bounds(self, method: str, request_data: dict):
        """Handle calculate bounds request."""
        return self.controller.calculate_bounds(request_data or {})

    def _handle_find_ground_level(self, method: str, request_data: dict):
        """Handle find ground level request."""
        return self.controller.find_ground_level(request_data or {})

    def _handle_align_objects(self, method: str, request_data: dict):
        """Handle align objects request."""
        if method != 'POST':
            request_logger.warning('method_not_allowed', extra={'route': 'align_objects', 'method': method})
            return error_response('METHOD_NOT_ALLOWED', 'align_objects requires POST method', details={'method': method})
        return self.controller.align_objects(request_data or {})

    def log_message(self, format, *args):
        """Override default HTTP server logging to use our logger with proper levels."""
        # Only log HTTP server messages when debug mode is enabled
        config = self.api_interface._config
        if config.debug_mode or config.verbose_logging:
            logger.info(f"HTTP {format % args}")
        # Otherwise, suppress the default logging to stderr
