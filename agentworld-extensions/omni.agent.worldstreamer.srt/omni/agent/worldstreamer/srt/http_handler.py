"""HTTP handler bridging WorldStreamer SRT routes to controller/service stack."""

from __future__ import annotations

from typing import Any, Dict

from agentworld_core.logging import module_logger

from .http import WorldStreamerController
from .services import WorldStreamerService
from .errors import MethodNotAllowed, ValidationFailure, error_response

try:
    from agentworld_core.http import WorldHTTPHandler
    UNIFIED = True
except ImportError:  # pragma: no cover - Isaac fallback
    from http.server import BaseHTTPRequestHandler as WorldHTTPHandler  # type: ignore
    UNIFIED = False

LOGGER = module_logger(service='worldstreamer.srt', component='http_handler')


class WorldStreamerHTTPHandler(WorldHTTPHandler):
    """HTTP request handler for WorldStreamer SRT operations."""

    api_interface = None

    @property
    def controller(self) -> WorldStreamerController:
        if not hasattr(self, '_controller'):
            service = WorldStreamerService(self.api_interface)
            self._controller = WorldStreamerController(service)
        return self._controller

    def get_routes(self):  # type: ignore[override]
        return {
            'health': self._route_health,
            'streaming/start': self._route_start,
            'streaming/stop': self._route_stop,
            'streaming/status': self._route_status,
            'streaming/urls': self._route_urls,
            'streaming/environment/validate': self._route_validate_environment,
        }

    def _route_health(self, method: str, data: Dict[str, Any]) -> Dict[str, Any]:
        if method != 'GET':
            raise MethodNotAllowed('health requires GET', details={'method': method})
        return self.controller.get_health()

    def _route_start(self, method: str, data: Dict[str, Any]) -> Dict[str, Any]:
        if method != 'POST':
            raise MethodNotAllowed('streaming/start requires POST', details={'method': method})
        return self.controller.start_streaming(data or {})

    def _route_stop(self, method: str, data: Dict[str, Any]) -> Dict[str, Any]:
        if method != 'POST':
            raise MethodNotAllowed('streaming/stop requires POST', details={'method': method})
        return self.controller.stop_streaming()

    def _route_status(self, method: str, data: Dict[str, Any]) -> Dict[str, Any]:
        if method != 'GET':
            raise MethodNotAllowed('streaming/status requires GET', details={'method': method})
        return self.controller.streaming_status()

    def _route_urls(self, method: str, data: Dict[str, Any]) -> Dict[str, Any]:
        if method != 'GET':
            raise MethodNotAllowed('streaming/urls requires GET', details={'method': method})
        return self.controller.streaming_urls(self._normalize_query_params(data))

    def _route_validate_environment(self, method: str, data: Dict[str, Any]) -> Dict[str, Any]:
        if method != 'GET':
            raise MethodNotAllowed('streaming/environment/validate requires GET', details={'method': method})
        return self.controller.validate_environment()

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
                self._send_json_response(error_response('WORLDSTREAMER_ERROR', str(exc)), status_code=500)
            except Exception:
                pass


__all__ = ['WorldStreamerHTTPHandler']
