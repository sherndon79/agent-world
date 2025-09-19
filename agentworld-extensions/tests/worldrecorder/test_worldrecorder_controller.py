from __future__ import annotations

from omni.agent.worldrecorder.http.controller import WorldRecorderController
from omni.agent.worldrecorder.services.worldrecorder_service import WorldRecorderService


class DummyAPI:
    def __init__(self) -> None:
        self.sessions = {}
        self.current_session_id = None
        self.last_session_id = None

    def run_on_main(self, fn):  # pragma: no cover - not used in validation tests
        return fn()


def build_controller() -> WorldRecorderController:
    api = DummyAPI()
    service = WorldRecorderService(api)
    return WorldRecorderController(service)


def test_start_video_requires_output_path():
    controller = build_controller()
    response = controller.start_video({'duration_sec': 5})
    assert response['success'] is False
    assert response['error_code'] == 'VALIDATION_ERROR'


def test_start_video_requires_duration():
    controller = build_controller()
    response = controller.start_video({'output_path': '/tmp/test.mp4'})
    assert response['success'] is False
    assert response['error_code'] == 'VALIDATION_ERROR'


def test_capture_frame_requires_output_path():
    controller = build_controller()
    response = controller.capture_frame({})
    assert response['success'] is False
    assert response['error_code'] == 'VALIDATION_ERROR'


def test_cleanup_frames_requires_identifier():
    controller = build_controller()
    response = controller.cleanup_frames({})
    assert response['success'] is False
    assert response['error_code'] == 'VALIDATION_ERROR'
