"""Service layer for WorldViewer HTTP operations."""

from __future__ import annotations

import time
import uuid
from typing import Any, Dict, Optional

from ..errors import error_response


class WorldViewerService:
    """Wrap camera and cinematic operations exposed over HTTP/MCP."""

    def __init__(self, api_interface) -> None:
        self._api = api_interface

    # ------------------------------------------------------------------
    # Helpers
    @property
    def _camera_controller(self):
        return getattr(self._api, 'camera_controller', None)

    def _ensure_controller(self) -> Optional[Dict[str, Any]]:
        if self._camera_controller is None:
            return error_response('CAMERA_UNAVAILABLE', 'Camera controller not initialized')
        return None

    def _cinematic_controller(self):
        controller = self._ensure_controller()
        if controller is not None:
            return None, controller
        cinematic = self._camera_controller.get_cinematic_controller()
        if cinematic is None:
            return None, error_response('CINEMATIC_UNAVAILABLE', 'Cinematic controller not available')
        return cinematic, None

    @staticmethod
    def _first_scalar(value: Any) -> Any:
        if isinstance(value, list):
            return value[0] if value else None
        return value

    def _queue_camera_operation(self, operation: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Queue a camera operation for execution on the main thread."""
        error = self._ensure_controller()
        if error is not None:
            return error

        request_id = f"camera_{operation}_{int(time.time() * 1000)}_{uuid.uuid4().hex[:8]}"
        request = {
            'request_id': request_id,
            'operation': operation,
            'params': params,
            'timestamp': time.time(),
            'completed': False,
            'result': None,
            'error': None,
        }

        queue_lock = getattr(self._api, '_queue_lock', None)
        camera_queue = getattr(self._api, '_camera_queue', None)
        tracker = getattr(self._api, '_request_tracker', None)
        if queue_lock is None or camera_queue is None or tracker is None:
            return error_response('QUEUE_UNAVAILABLE', 'Camera queue infrastructure unavailable')

        with queue_lock:
            camera_queue.append(request)
            tracker.add(request_id, request)

        return {
            'success': True,
            'request_id': request_id,
            'operation': operation,
            'status': 'queued',
            'timestamp': request['timestamp'],
        }

    # ------------------------------------------------------------------
    # Camera operations
    def get_camera_status(self) -> Dict[str, Any]:
        error = self._ensure_controller()
        if error is not None:
            return error
        try:
            status = self._camera_controller.get_status()
        except Exception as exc:  # pragma: no cover - USD errors surfaced to caller
            return error_response('STATUS_FAILED', str(exc))

        return {
            'success': True,
            'connected': status.get('connected', True),
            'position': status.get('position', [0.0, 0.0, 0.0]),
            'target': status.get('target', [0.0, 0.0, 0.0]),
            'up_vector': status.get('up_vector', [0.0, 1.0, 0.0]),
            'camera_path': status.get('camera_path', '/OmniverseKit_Persp'),
            'timestamp': time.time(),
        }

    def set_camera_position(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self._queue_camera_operation('set_position', payload)

    def frame_object(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self._queue_camera_operation('frame_object', payload)

    def orbit_camera(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self._queue_camera_operation('orbit_camera', payload)

    def smooth_move(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        payload.setdefault('operation', 'smooth_move')
        return self._queue_camera_operation('smooth_move', payload)

    def orbit_shot(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        payload.setdefault('operation', 'orbit_shot')
        return self._queue_camera_operation('orbit_shot', payload)

    def arc_shot(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        payload.setdefault('operation', 'arc_shot')
        return self._queue_camera_operation('arc_shot', payload)

    def stop_movement(self) -> Dict[str, Any]:
        cinematic, error = self._cinematic_controller()
        if error is not None:
            return error
        try:
            return cinematic.stop_movement()
        except Exception as exc:  # pragma: no cover
            return error_response('STOP_MOVEMENT_FAILED', str(exc))

    # ------------------------------------------------------------------
    # Queue + cinematic helpers
    def movement_status(self, movement_id: Any) -> Dict[str, Any]:
        movement_id = self._first_scalar(movement_id)
        if not movement_id:
            return error_response('MISSING_PARAMETER', 'movement_id parameter required', details={'parameter': 'movement_id'})

        cinematic, error = self._cinematic_controller()
        if error is not None:
            return error

        if hasattr(cinematic, 'get_movement_status'):
            try:
                return cinematic.get_movement_status(movement_id)
            except Exception as exc:  # pragma: no cover
                return error_response('MOVEMENT_STATUS_FAILED', str(exc))
        return error_response('NOT_SUPPORTED', 'Movement status not supported')

    def shot_queue_status(self) -> Dict[str, Any]:
        cinematic, error = self._cinematic_controller()
        if error is not None:
            return error
        if hasattr(cinematic, 'get_queue_status'):
            try:
                return cinematic.get_queue_status()
            except Exception as exc:  # pragma: no cover
                return error_response('QUEUE_STATUS_FAILED', str(exc))
        return error_response('NOT_SUPPORTED', 'Queue status not supported')

    def queue_play(self) -> Dict[str, Any]:
        cinematic, error = self._cinematic_controller()
        if error is not None:
            return error
        if hasattr(cinematic, 'play_queue'):
            try:
                return cinematic.play_queue()
            except Exception as exc:  # pragma: no cover
                return error_response('QUEUE_PLAY_FAILED', str(exc))
        return error_response('NOT_SUPPORTED', 'Queue control not supported')

    def queue_pause(self) -> Dict[str, Any]:
        cinematic, error = self._cinematic_controller()
        if error is not None:
            return error
        if hasattr(cinematic, 'pause_queue'):
            try:
                return cinematic.pause_queue()
            except Exception as exc:  # pragma: no cover
                return error_response('QUEUE_PAUSE_FAILED', str(exc))
        return error_response('NOT_SUPPORTED', 'Queue control not supported')

    def queue_stop(self) -> Dict[str, Any]:
        cinematic, error = self._cinematic_controller()
        if error is not None:
            return error
        if hasattr(cinematic, 'stop_queue'):
            try:
                return cinematic.stop_queue()
            except Exception as exc:  # pragma: no cover
                return error_response('QUEUE_STOP_FAILED', str(exc))
        return error_response('NOT_SUPPORTED', 'Queue control not supported')

    # ------------------------------------------------------------------
    # Asset + request helpers
    def asset_transform(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        error = self._ensure_controller()
        if error is not None:
            return error
        usd_path = payload.get('usd_path')
        if not usd_path:
            return error_response('MISSING_PARAMETER', 'usd_path parameter required', details={'parameter': 'usd_path'})
        calculation_mode = payload.get('calculation_mode', 'auto')
        try:
            result = self._camera_controller.get_asset_transform(usd_path, calculation_mode)
            if result.get('success'):
                result.setdefault('timestamp', time.time())
                result.setdefault('source', 'worldviewer')
            return result
        except Exception as exc:  # pragma: no cover
            return error_response('ASSET_TRANSFORM_FAILED', str(exc))

    def request_status(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        request_id = self._first_scalar(payload.get('request_id'))
        if not request_id:
            return error_response('MISSING_PARAMETER', 'request_id parameter required', details={'parameter': 'request_id'})

        tracker = getattr(self._api, '_request_tracker', None)
        if tracker is None:
            return error_response('QUEUE_UNAVAILABLE', 'Request tracking unavailable')

        request = tracker.get(request_id)
        if not request:
            return error_response('REQUEST_NOT_FOUND', f'Request {request_id} not found')

        return {
            'success': True,
            'request_id': request_id,
            'operation': request.get('operation'),
            'completed': request.get('completed', False),
            'result': request.get('result'),
            'error': request.get('error'),
            'timestamp': request.get('timestamp'),
        }


__all__ = ['WorldViewerService']
