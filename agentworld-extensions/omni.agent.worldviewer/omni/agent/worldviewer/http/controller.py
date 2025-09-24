"""Controller functions for WorldViewer HTTP routes."""

from __future__ import annotations

from typing import Any, Callable, Dict

from agentworld_core.logging import module_logger

from ..services.worldviewer_service import WorldViewerService
from ..transport import normalize_transport_response
from .schemas import (
    SetCameraPositionPayload,
    FrameObjectPayload,
    OrbitCameraPayload,
    SmoothMovePayload,
    OrbitShotPayload,
    ArcShotPayload,
    MovementStatusPayload,
    RequestStatusPayload,
    AssetTransformQuery,
    validate_payload,
)


logger = module_logger(service='worldviewer', component='controller')


class WorldViewerController:
    """Coordinate payload validation and service execution."""

    def __init__(self, service: WorldViewerService) -> None:
        self._service = service

    # ------------------------------------------------------------------
    # Basic endpoints
    def get_camera_status(self) -> Dict[str, Any]:
        return self._safe_call('get_camera_status', self._service.get_camera_status, default_error_code='CAMERA_STATUS_FAILED')

    def set_camera_position(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        data = validate_payload(SetCameraPositionPayload, payload)
        return self._safe_call('set_camera_position', lambda: self._service.set_camera_position(data), default_error_code='SET_CAMERA_POSITION_FAILED')

    def frame_object(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        data = validate_payload(FrameObjectPayload, payload)
        return self._safe_call('frame_object', lambda: self._service.frame_object(data), default_error_code='FRAME_OBJECT_FAILED')

    def orbit_camera(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        data = validate_payload(OrbitCameraPayload, payload)
        return self._safe_call('orbit_camera', lambda: self._service.orbit_camera(data), default_error_code='ORBIT_CAMERA_FAILED')

    def smooth_move(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        data = validate_payload(SmoothMovePayload, payload)
        return self._safe_call('smooth_move', lambda: self._service.smooth_move(data), default_error_code='SMOOTH_MOVE_FAILED')

    def orbit_shot(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        data = validate_payload(OrbitShotPayload, payload)
        return self._safe_call('orbit_shot', lambda: self._service.orbit_shot(data), default_error_code='ORBIT_SHOT_FAILED')

    def arc_shot(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        data = validate_payload(ArcShotPayload, payload)
        return self._safe_call('arc_shot', lambda: self._service.arc_shot(data), default_error_code='ARC_SHOT_FAILED')

    def stop_movement(self) -> Dict[str, Any]:
        return self._safe_call('stop_movement', self._service.stop_movement, default_error_code='STOP_MOVEMENT_FAILED')

    def movement_status(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        data = validate_payload(MovementStatusPayload, payload)
        return self._safe_call('movement_status', lambda: self._service.movement_status(data['movement_id']), default_error_code='MOVEMENT_STATUS_FAILED')

    def shot_queue_status(self) -> Dict[str, Any]:
        return self._safe_call('shot_queue_status', self._service.shot_queue_status, default_error_code='QUEUE_STATUS_FAILED')

    def queue_play(self) -> Dict[str, Any]:
        return self._safe_call('queue_play', self._service.queue_play, default_error_code='QUEUE_PLAY_FAILED')

    def queue_pause(self) -> Dict[str, Any]:
        return self._safe_call('queue_pause', self._service.queue_pause, default_error_code='QUEUE_PAUSE_FAILED')

    def queue_stop(self) -> Dict[str, Any]:
        return self._safe_call('queue_stop', self._service.queue_stop, default_error_code='QUEUE_STOP_FAILED')

    def asset_transform(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        data = validate_payload(AssetTransformQuery, payload)
        return self._safe_call('asset_transform', lambda: self._service.asset_transform(data), default_error_code='ASSET_TRANSFORM_FAILED')

    def request_status(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        data = validate_payload(RequestStatusPayload, payload)
        return self._safe_call('request_status', lambda: self._service.request_status({'request_id': data['request_id']}), default_error_code='REQUEST_STATUS_FAILED')

    # ------------------------------------------------------------------
    def _safe_call(self, operation: str, func: Callable[[], Dict[str, Any]], *, default_error_code: str) -> Dict[str, Any]:
        try:
            response = func()
        except ValueError as exc:
            logger.warning('validation_failed', extra={'operation': operation, 'error': str(exc)})
            response = {'success': False, 'error': str(exc), 'error_code': 'VALIDATION_ERROR'}
        except Exception as exc:  # pragma: no cover - unexpected service failure
            logger.exception('controller_error', extra={'operation': operation, 'error': str(exc)})
            response = {'success': False, 'error': str(exc), 'error_code': default_error_code}
        return normalize_transport_response(operation, response, default_error_code=default_error_code)


__all__ = ['WorldViewerController']
