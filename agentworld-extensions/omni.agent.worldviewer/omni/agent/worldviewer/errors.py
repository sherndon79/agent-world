"""Domain-specific errors and helpers for the WorldViewer extension."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class ErrorPayload:
    """Structured error payload returned to HTTP/MCP clients."""

    code: str
    message: str
    details: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            'success': False,
            'error_code': self.code,
            'error': self.message,
        }
        if self.details:
            payload['details'] = self.details
        return payload


class WorldViewerError(Exception):
    """Base exception for WorldViewer domain failures."""

    code: str = 'WORLDVIEWER_ERROR'

    def __init__(self, message: str, *, details: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}

    def to_payload(self) -> Dict[str, Any]:
        return ErrorPayload(self.code, self.message, self.details or None).to_dict()


class ValidationFailure(WorldViewerError):
    code = 'VALIDATION_ERROR'


class CameraUnavailable(WorldViewerError):
    code = 'CAMERA_UNAVAILABLE'


class QueueUnavailable(WorldViewerError):
    code = 'QUEUE_UNAVAILABLE'


def error_response(code: str, message: str, *, details: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Return a standardised error payload."""
    return ErrorPayload(code, message, details).to_dict()


__all__ = [
    'ErrorPayload',
    'WorldViewerError',
    'ValidationFailure',
    'CameraUnavailable',
    'QueueUnavailable',
    'error_response',
]
