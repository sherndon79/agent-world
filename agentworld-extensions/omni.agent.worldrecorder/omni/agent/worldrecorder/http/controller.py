"""HTTP controller coordinating WorldRecorder requests."""

from __future__ import annotations

from typing import Any, Callable, Dict

from ..errors import MethodNotAllowed, ValidationFailure, WorldRecorderError, error_response
from ..transport import normalize_transport_response


class WorldRecorderController:
    """Coordinate validation, service calls, and response normalisation."""

    def __init__(self, service) -> None:
        self._service = service

    # ------------------------------------------------------------------
    def video_status(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self._safe_call('get_status', lambda: self._service.get_status(payload), 'STATUS_FAILED')

    def start_video(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self._safe_call('start_video', lambda: self._service.start_video(payload), 'START_VIDEO_FAILED')

    def cancel_video(self) -> Dict[str, Any]:
        return self._safe_call('cancel_video', self._service.cancel_video, 'CANCEL_VIDEO_FAILED')

    def capture_frame(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self._safe_call('capture_frame', lambda: self._service.capture_frame(payload), 'CAPTURE_FRAME_FAILED')

    def cleanup_frames(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self._safe_call('cleanup_frames', lambda: self._service.cleanup_frames(payload), 'CLEANUP_FRAMES_FAILED')

    # ------------------------------------------------------------------
    def _safe_call(self, operation: str, func: Callable[[], Dict[str, Any]], default_error_code: str) -> Dict[str, Any]:
        try:
            response = func()
        except MethodNotAllowed as exc:
            return error_response('METHOD_NOT_ALLOWED', exc.message, details=exc.details)
        except ValidationFailure as exc:
            return error_response('VALIDATION_ERROR', exc.message, details=exc.details)
        except WorldRecorderError as exc:
            return error_response(exc.code, exc.message, details=exc.details)
        except Exception as exc:  # pragma: no cover - unexpected failure
            return error_response(default_error_code, str(exc))

        return normalize_transport_response(operation, response, default_error_code=default_error_code)


__all__ = ["WorldRecorderController"]
