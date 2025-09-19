"""Domain-specific errors for WorldRecorder."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class ErrorPayload:
    code: str
    message: str
    details: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "success": False,
            "error_code": self.code,
            "error": self.message,
        }
        if self.details:
            payload["details"] = self.details
        return payload


def error_response(code: str, message: str, *, details: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    return ErrorPayload(code, message, details).to_dict()


class WorldRecorderError(Exception):
    """Base exception for recorder failures."""

    code = "WORLDRECORDER_ERROR"

    def __init__(self, message: str, *, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}

    def to_payload(self) -> Dict[str, Any]:
        return error_response(self.code, self.message, details=self.details)


class ValidationFailure(WorldRecorderError):
    code = "VALIDATION_ERROR"


class NotFoundError(WorldRecorderError):
    code = "NOT_FOUND"


class MethodNotAllowed(WorldRecorderError):
    code = "METHOD_NOT_ALLOWED"


__all__ = [
    "WorldRecorderError",
    "ValidationFailure",
    "NotFoundError",
    "MethodNotAllowed",
    "error_response",
]
