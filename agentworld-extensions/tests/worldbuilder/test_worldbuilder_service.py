import time

import pytest

from omni.agent.worldbuilder.services.worldbuilder_service import WorldBuilderService


class FakeSceneBuilder:
    def __init__(self):
        self.added = []
        self.cleared = []

    def add_element_to_stage(self, element):
        self.added.append(element.name)
        return {"success": True, "element": element.name}

    def clear_stage_path(self, path):
        self.cleared.append(path)
        return {"success": True, "path": path}

    def query_objects_in_bounds(self, *_):
        return {"success": True}

    def get_scene_status(self):
        return {"success": True, "scene": "ok"}

    def list_batches(self):
        return {"success": True, "batches": []}


class FakeAPI:
    def __init__(self):
        self._scene_builder = FakeSceneBuilder()
        self._api_stats = {
            "requests_received": 3,
            "failed_requests": 1,
            "start_time": time.time() - 10,
            "server_running": True,
            "objects_queried": 0,
        }
        self._startup_error = None

    def get_port(self):
        return 8899


@pytest.fixture
def service():
    return WorldBuilderService(api_interface=FakeAPI())


def test_remove_element_missing_path_returns_structured_error(service):
    response = service.remove_element({})
    assert response == {
        "success": False,
        "error_code": "MISSING_PARAMETER",
        "error": "element_path is required",
        "details": {"parameter": "element_path"},
    }


def test_get_metrics_formats_payload(service):
    payload = service.get_metrics()
    assert payload["success"] is True
    metrics = payload["metrics"]
    assert metrics["requests_received"] == 3
    assert metrics["errors"] == 1
    assert metrics["scene_object_count"] == 0
    assert metrics["server_running"] is True


def test_clear_path_requires_parameter(service):
    response = service.clear_path({})
    assert response["error_code"] == "MISSING_PARAMETER"
    assert "parameter" in response["details"]


def test_add_element_passes_through(service):
    payload = {
        "name": "cube_1",
        "element_type": "cube",
    }
    result = service.add_element(payload)
    assert result["success"] is True
    assert service._scene_builder.added == ["cube_1"]


def test_startup_error_sets_failure_flags(service):
    service._api._startup_error = RuntimeError("socket busy")

    stats_response = service.get_stats()
    assert stats_response["success"] is False
    assert stats_response["error"] == "socket busy"

    metrics_response = service.get_metrics()
    assert metrics_response["success"] is False
    assert metrics_response["metrics"]["requests_received"] == 3
