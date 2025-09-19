from __future__ import annotations

import pytest

from omni.agent.worldstreamer.rtmp.http.controller import WorldStreamerController as RTMPController
from omni.agent.worldstreamer.rtmp.services import WorldStreamerService as RTMPService
from omni.agent.worldstreamer.srt.http.controller import WorldStreamerController as SRTController
from omni.agent.worldstreamer.srt.services import WorldStreamerService as SRTService


class DummyStreaming:
    def __init__(self) -> None:
        self.started = False

    def get_health_status(self):
        return {'streaming_interface_functional': True}

    def start_streaming(self, server_ip=None):
        self.started = True
        return {'success': True, 'info': {'server_ip': server_ip}}

    def stop_streaming(self):
        self.started = False
        return {'success': True}

    def get_streaming_status(self):
        return {'success': True, 'is_streaming': self.started}

    def get_streaming_urls(self, server_ip=None):
        return {'success': True, 'urls': {'primary': 'rtmp://example'}}

    def validate_environment(self):
        return {'valid': True, 'success': True}


class DummyAPI:
    def __init__(self) -> None:
        self._streaming = DummyStreaming()


@pytest.mark.parametrize(
    'controller_cls, service_cls',
    [
        (RTMPController, RTMPService),
        (SRTController, SRTService),
    ],
)
def test_start_and_stop_streaming(controller_cls, service_cls):
    api = DummyAPI()
    controller = controller_cls(service_cls(api))

    start_response = controller.start_streaming({})
    assert start_response['success'] is True
    assert start_response['timestamp']

    status_response = controller.streaming_status()
    assert status_response['success'] is True
    assert status_response['is_streaming'] is True

    stop_response = controller.stop_streaming()
    assert stop_response['success'] is True
    assert stop_response['timestamp']


@pytest.mark.parametrize(
    'controller_cls, service_cls',
    [
        (RTMPController, RTMPService),
        (SRTController, SRTService),
    ],
)
def test_streaming_urls(controller_cls, service_cls):
    api = DummyAPI()
    controller = controller_cls(service_cls(api))

    response = controller.streaming_urls({'server_ip': '1.2.3.4'})
    assert response['success'] is True
    assert 'urls' in response


@pytest.mark.parametrize(
    'controller_cls, service_cls',
    [
        (RTMPController, RTMPService),
        (SRTController, SRTService),
    ],
)
def test_validate_environment(controller_cls, service_cls):
    api = DummyAPI()
    controller = controller_cls(service_cls(api))

    response = controller.validate_environment()
    assert response['success'] is True
    assert response['valid'] is True


@pytest.mark.parametrize(
    'controller_cls, service_cls',
    [
        (RTMPController, RTMPService),
        (SRTController, SRTService),
    ],
)
def test_missing_streaming_interface_returns_error(controller_cls, service_cls):
    api = DummyAPI()
    api._streaming = None
    controller = controller_cls(service_cls(api))

    response = controller.start_streaming({})
    assert response['success'] is False
    assert response['error_code'] == 'WORLDSTREAMER_ERROR'
