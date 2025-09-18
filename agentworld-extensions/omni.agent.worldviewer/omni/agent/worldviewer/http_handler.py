"""HTTP handler bridging WorldViewer routes to the controller/service stack."""

from __future__ import annotations

from typing import Any, Dict

from agent_world_logging import module_logger

try:
    from agent_world_http import WorldHTTPHandler
    UNIFIED = True
except ImportError:  # pragma: no cover - Isaac fallback
    from http.server import BaseHTTPRequestHandler as WorldHTTPHandler  # type: ignore
    UNIFIED = False

from .http import WorldViewerController
from .services import WorldViewerService

logger = module_logger(service='worldviewer', component='http_handler')


class WorldViewerHTTPHandler(WorldHTTPHandler):
    """HTTP request handler for WorldViewer operations (unified)."""

    api_interface = None

    @property
    def controller(self) -> WorldViewerController:
        if not hasattr(self, '_controller') or self._controller is None:
            service = WorldViewerService(self.api_interface)
            self._controller = WorldViewerController(service)
        return self._controller

    # ------------------------------------------------------------------
    # Route registration
    def get_routes(self):  # type: ignore[override]
        return {
            'camera/status': self._route_camera_status,
            'camera/set_position': self._route_set_position,
            'camera/frame_object': self._route_frame_object,
            'camera/orbit': self._route_orbit_camera,
            'camera/smooth_move': self._route_smooth_move,
            'camera/orbit_shot': self._route_orbit_shot,
            'camera/arc_shot': self._route_arc_shot,
            'camera/stop_movement': self._route_stop_movement,
            'movement/stop': self._route_stop_movement,
            'camera/movement_status': self._route_movement_status,
            'camera/shot_queue_status': self._route_shot_queue_status,
            'camera/queue/play': self._route_queue_play,
            'camera/queue/pause': self._route_queue_pause,
            'camera/queue/stop': self._route_queue_stop,
            'get_asset_transform': self._route_asset_transform,
            'request_status': self._route_request_status,
        }

    # ------------------------------------------------------------------
    # Route handlers
    def _route_camera_status(self, method: str, data: Dict[str, Any]) -> Dict[str, Any]:
        if method != 'GET':
            return self._method_not_allowed('camera/status', method, 'GET')
        return self.controller.get_camera_status()

    def _route_set_position(self, method: str, data: Dict[str, Any]) -> Dict[str, Any]:
        if method != 'POST':
            return self._method_not_allowed('camera/set_position', method, 'POST')
        return self.controller.set_camera_position(data or {})

    def _route_frame_object(self, method: str, data: Dict[str, Any]) -> Dict[str, Any]:
        if method != 'POST':
            return self._method_not_allowed('camera/frame_object', method, 'POST')
        return self.controller.frame_object(data or {})

    def _route_orbit_camera(self, method: str, data: Dict[str, Any]) -> Dict[str, Any]:
        if method != 'POST':
            return self._method_not_allowed('camera/orbit', method, 'POST')
        return self.controller.orbit_camera(data or {})

    def _route_smooth_move(self, method: str, data: Dict[str, Any]) -> Dict[str, Any]:
        if method != 'POST':
            return self._method_not_allowed('camera/smooth_move', method, 'POST')
        return self.controller.smooth_move(data or {})

    def _route_orbit_shot(self, method: str, data: Dict[str, Any]) -> Dict[str, Any]:
        if method != 'POST':
            return self._method_not_allowed('camera/orbit_shot', method, 'POST')
        return self.controller.orbit_shot(data or {})

    def _route_arc_shot(self, method: str, data: Dict[str, Any]) -> Dict[str, Any]:
        if method != 'POST':
            return self._method_not_allowed('camera/arc_shot', method, 'POST')
        return self.controller.arc_shot(data or {})

    def _route_stop_movement(self, method: str, data: Dict[str, Any]) -> Dict[str, Any]:
        return self.controller.stop_movement()

    def _route_movement_status(self, method: str, data: Dict[str, Any]) -> Dict[str, Any]:
        if method != 'GET':
            return self._method_not_allowed('camera/movement_status', method, 'GET')
        return self.controller.movement_status(self._normalize_query_params(data))

    def _route_shot_queue_status(self, method: str, data: Dict[str, Any]) -> Dict[str, Any]:
        if method != 'GET':
            return self._method_not_allowed('camera/shot_queue_status', method, 'GET')
        return self.controller.shot_queue_status()

    def _route_queue_play(self, method: str, data: Dict[str, Any]) -> Dict[str, Any]:
        return self.controller.queue_play()

    def _route_queue_pause(self, method: str, data: Dict[str, Any]) -> Dict[str, Any]:
        return self.controller.queue_pause()

    def _route_queue_stop(self, method: str, data: Dict[str, Any]) -> Dict[str, Any]:
        return self.controller.queue_stop()

    def _route_asset_transform(self, method: str, data: Dict[str, Any]) -> Dict[str, Any]:
        if method != 'GET':
            return self._method_not_allowed('get_asset_transform', method, 'GET')
        return self.controller.asset_transform(self._normalize_query_params(data))

    def _route_request_status(self, method: str, data: Dict[str, Any]) -> Dict[str, Any]:
        if method != 'GET':
            return self._method_not_allowed('request_status', method, 'GET')
        return self.controller.request_status(self._normalize_query_params(data))

    # ------------------------------------------------------------------
    def _normalize_query_params(self, params: Dict[str, Any]) -> Dict[str, Any]:
        normalized: Dict[str, Any] = {}
        for key, value in (params or {}).items():
            if isinstance(value, list):
                normalized[key] = value[0] if len(value) == 1 else value
            else:
                normalized[key] = value
        return normalized

    def _method_not_allowed(self, route: str, method: str, expected: str) -> Dict[str, Any]:
        logger.warning('method_not_allowed', extra={'route': route, 'method': method, 'expected': expected})
        return {
            'success': False,
            'error': f'{route} requires {expected} method',
            'error_code': 'METHOD_NOT_ALLOWED',
            'details': {'method': method},
        }

    def log_message(self, format, *args):  # pragma: no cover - HTTP server logging
        config = getattr(self.api_interface, '_config', None)
        if config and getattr(config, 'debug_mode', False) or getattr(config, 'verbose_logging', False):
            logger.info('http_server_message', extra={'message': format % args})
        # Suppress default BaseHTTPRequestHandler logging otherwise
