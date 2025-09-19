from __future__ import annotations

from omni.agent.worldviewer.http.controller import WorldViewerController
from omni.agent.worldviewer.services.worldviewer_service import WorldViewerService
from agent_world_requests import RequestTracker


class _FakeService:
    def __init__(self, payload):
        self._payload = payload
        self.calls = []

    def get_camera_status(self):
        self.calls.append('get_camera_status')
        return self._payload

    def frame_object(self, payload):
        self.calls.append(('frame_object', payload))
        if 'object_path' not in payload:
            return {'success': False, 'error_code': 'MISSING_PARAMETER', 'error': 'object_path parameter required'}
        return {'success': True, 'object_path': payload['object_path']}


def test_controller_get_camera_status_normalizes_result():
    payload = {'success': True, 'status': 'ok'}
    controller = WorldViewerController(_FakeService(payload))

    result = controller.get_camera_status()

    assert result['success'] is True
    assert result['status'] == 'ok'


def test_controller_frame_object_missing_parameter_returns_error():
    controller = WorldViewerController(_FakeService({'success': True}))

    result = controller.frame_object({})

    assert result['success'] is False
    assert result['error_code'] in {'VALIDATION_ERROR', 'MISSING_PARAMETER'}


class _StubAPI:
    def __init__(self):
        self._camera_queue = []
        self._request_tracker = RequestTracker(ttl_seconds=30.0)
        import threading
        self._queue_lock = threading.Lock()
        self.camera_controller = None
        self._config = type('Config', (), {'debug_mode': False, 'verbose_logging': False})()


def test_service_camera_unavailable_when_controller_missing():
    service = WorldViewerService(_StubAPI())

    result = service.get_camera_status()

    assert result['success'] is False
    assert result['error_code'] == 'CAMERA_UNAVAILABLE'
