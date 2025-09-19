"""Service layer implementing WorldStreamer RTMP operations."""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, Optional

from ..errors import ValidationFailure, WorldStreamerError

LOGGER = logging.getLogger('worldstreamer.rtmp.service')


class WorldStreamerService:
    """Encapsulates streaming operations for HTTP/MCP transports."""

    def __init__(self, api_interface) -> None:
        self._api = api_interface
        self._streaming = getattr(api_interface, '_streaming', None)
        self._logger = LOGGER

    # ------------------------------------------------------------------
    def get_health(self) -> Dict[str, Any]:
        streaming = self._require_streaming()
        try:
            status = streaming.get_health_status()
        except Exception as exc:  # pragma: no cover - requires Isaac runtime
            raise WorldStreamerError('Failed to retrieve health status', details={'error': str(exc)}) from exc

        return {
            'success': bool(status.get('streaming_interface_functional', True)),
            'service': 'WorldStreamer RTMP',
            'timestamp': self._timestamp(),
            'details': status,
        }

    def start_streaming(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        streaming = self._require_streaming()
        try:
            result = streaming.start_streaming(server_ip=payload.get('server_ip'))
        except Exception as exc:  # pragma: no cover - requires Isaac runtime
            raise WorldStreamerError('Failed to start streaming', details={'error': str(exc)}) from exc

        result.setdefault('timestamp', self._timestamp())
        result.setdefault('success', True)
        return result

    def stop_streaming(self) -> Dict[str, Any]:
        streaming = self._require_streaming()
        try:
            result = streaming.stop_streaming()
        except Exception as exc:  # pragma: no cover
            raise WorldStreamerError('Failed to stop streaming', details={'error': str(exc)}) from exc

        result.setdefault('timestamp', self._timestamp())
        result.setdefault('success', True)
        return result

    def get_streaming_status(self) -> Dict[str, Any]:
        streaming = self._require_streaming()
        try:
            status = streaming.get_streaming_status()
        except Exception as exc:  # pragma: no cover
            raise WorldStreamerError('Failed to obtain streaming status', details={'error': str(exc)}) from exc

        status.setdefault('timestamp', self._timestamp())
        status.setdefault('success', True)
        return status

    def get_streaming_urls(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        streaming = self._require_streaming()
        try:
            urls = streaming.get_streaming_urls(server_ip=payload.get('server_ip'))
        except Exception as exc:  # pragma: no cover
            raise WorldStreamerError('Failed to obtain streaming URLs', details={'error': str(exc)}) from exc

        urls.setdefault('timestamp', self._timestamp())
        urls.setdefault('success', True)
        return urls

    def validate_environment(self) -> Dict[str, Any]:
        streaming = self._require_streaming()
        try:
            validation = streaming.validate_environment()
        except Exception as exc:  # pragma: no cover
            raise WorldStreamerError('Environment validation failed', details={'error': str(exc)}) from exc

        validation.setdefault('timestamp', self._timestamp())
        validation.setdefault('success', bool(validation.get('valid', False)))
        return validation

    # ------------------------------------------------------------------
    def _require_streaming(self):
        if not self._streaming:
            raise WorldStreamerError('Streaming interface unavailable')
        return self._streaming

    @staticmethod
    def _timestamp() -> float:
        return time.time()


__all__ = ["WorldStreamerService"]
