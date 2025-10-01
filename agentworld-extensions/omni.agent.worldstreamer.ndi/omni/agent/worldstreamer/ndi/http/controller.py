"""HTTP controller coordinating WorldStreamer SRT requests."""

from __future__ import annotations

from typing import Any, Callable, Dict

from ..errors import MethodNotAllowed, ValidationFailure, WorldStreamerError, error_response
from ..transport import normalize_transport_response


class WorldStreamerController:
    """Coordinate validation, service calls, and response normalisation."""

    def __init__(self, service) -> None:
        self._service = service

    def get_health(self) -> Dict[str, Any]:
        return self._safe_call('get_health', self._service.get_health, 'HEALTH_FAILED')

    def start_streaming(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self._safe_call('start_streaming', lambda: self._service.start_streaming(payload), 'START_STREAMING_FAILED')

    def stop_streaming(self) -> Dict[str, Any]:
        return self._safe_call('stop_streaming', self._service.stop_streaming, 'STOP_STREAMING_FAILED')

    def streaming_status(self) -> Dict[str, Any]:
        return self._safe_call('get_status', self._service.get_streaming_status, 'STATUS_FAILED')

    def streaming_urls(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self._safe_call('get_streaming_urls', lambda: self._service.get_streaming_urls(payload), 'STREAMING_URLS_FAILED')

    def validate_environment(self) -> Dict[str, Any]:
        return self._safe_call('validate_environment', self._service.validate_environment, 'VALIDATE_ENVIRONMENT_FAILED')

    def _safe_call(self, operation: str, func: Callable[[], Dict[str, Any]], default_error_code: str) -> Dict[str, Any]:
        try:
            response = func()
        except MethodNotAllowed as exc:
            return error_response('METHOD_NOT_ALLOWED', exc.message, details=exc.details)
        except ValidationFailure as exc:
            return error_response('VALIDATION_ERROR', exc.message, details=exc.details)
        except WorldStreamerError as exc:
            return error_response(exc.code, exc.message, details=exc.details)
        except Exception as exc:  # pragma: no cover - unexpected failure
            return error_response(default_error_code, str(exc))

        return normalize_transport_response(operation, response, default_error_code=default_error_code)


__all__ = ["WorldStreamerController"]
