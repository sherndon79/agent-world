"""HTTP handler bridging WorldRecorder routes to controller/service stack."""

from __future__ import annotations

from typing import Any, Dict

from agent_world_logging import module_logger

from .http import WorldRecorderController
from .services import WorldRecorderService
from .errors import MethodNotAllowed, ValidationFailure, error_response

try:
    from agent_world_http import WorldHTTPHandler
    UNIFIED = True
except ImportError:  # pragma: no cover - Isaac fallback
    from http.server import BaseHTTPRequestHandler as WorldHTTPHandler  # type: ignore
    UNIFIED = False

LOGGER = module_logger(service='worldrecorder', component='http_handler')


class WorldRecorderHTTPHandler(WorldHTTPHandler):
    """HTTP request handler for WorldRecorder operations."""

    api_interface = None

    @property
    def controller(self) -> WorldRecorderController:
        if not hasattr(self, '_controller'):
            service = WorldRecorderService(self.api_interface)
            self._controller = WorldRecorderController(service)
        return self._controller

    def get_routes(self):  # type: ignore[override]
        return {
            'video/status': self._route_status,
            'video/start': self._route_start,
            'video/cancel': self._route_cancel,
            'video/stop': self._route_cancel,
            'recording/status': self._route_status,
            'recording/start': self._route_start,
            'recording/cancel': self._route_cancel,
            'recording/stop': self._route_cancel,
            'viewport/capture_frame': self._route_capture_frame,
            'cleanup/frames': self._route_cleanup_frames,
        }

    # ------------------------------------------------------------------
    def _route_status(self, method: str, data: Dict[str, Any]) -> Dict[str, Any]:
        if method != 'GET':
            raise MethodNotAllowed('status requires GET', details={'method': method})
        return self.controller.video_status(self._normalize_query_params(data))

    def _route_start(self, method: str, data: Dict[str, Any]) -> Dict[str, Any]:
        if method != 'POST':
            raise MethodNotAllowed('start requires POST', details={'method': method})
        return self.controller.start_video(data or {})

    def _route_cancel(self, method: str, data: Dict[str, Any]) -> Dict[str, Any]:
        if method != 'POST':
            raise MethodNotAllowed('cancel requires POST', details={'method': method})
        return self.controller.cancel_video()

    def _route_capture_frame(self, method: str, data: Dict[str, Any]) -> Dict[str, Any]:
        if method != 'POST':
            raise MethodNotAllowed('viewport/capture_frame requires POST', details={'method': method})
        return self.controller.capture_frame(data or {})

    def _route_cleanup_frames(self, method: str, data: Dict[str, Any]) -> Dict[str, Any]:
        if method != 'POST':
            raise MethodNotAllowed('cleanup/frames requires POST', details={'method': method})
        return self.controller.cleanup_frames(data or {})

    # ------------------------------------------------------------------
    @staticmethod
    def _normalize_query_params(params: Dict[str, Any]) -> Dict[str, Any]:
        normalized: Dict[str, Any] = {}
        for key, value in (params or {}).items():
            if isinstance(value, list):
                normalized[key] = value[0] if len(value) == 1 else value
            else:
                normalized[key] = value
        return normalized

    def handle_one_request(self):  # type: ignore[override]
        try:
            super().handle_one_request()
        except MethodNotAllowed as exc:
            self._send_error_response(405, exc.message)
        except ValidationFailure as exc:
            self._send_error_response(400, exc.message)
        except Exception as exc:  # pragma: no cover - unexpected failure
            LOGGER.exception('http_handler_unexpected', extra={'error': str(exc)})
            try:
                self._send_json_response(error_response('WORLDRECORDER_ERROR', str(exc)), status_code=500)
            except Exception:
                pass


__all__ = ['WorldRecorderHTTPHandler']
