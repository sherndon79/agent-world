"""Domain-specific errors for WorldSurveyor."""

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


class WorldSurveyorError(Exception):
    code = "WORLDSURVEYOR_ERROR"

    def __init__(self, message: str, *, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}

    def to_payload(self) -> Dict[str, Any]:
        return error_response(self.code, self.message, details=self.details)


class ValidationFailure(WorldSurveyorError):
    code = "VALIDATION_ERROR"


class NotFoundError(WorldSurveyorError):
    code = "NOT_FOUND"


class MethodNotAllowed(WorldSurveyorError):
    code = "METHOD_NOT_ALLOWED"
