"""Domain-specific errors and helpers for the WorldBuilder extension."""

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
            "success": False,
            "error_code": self.code,
            "error": self.message,
        }
        if self.details:
            payload["details"] = self.details
        return payload


class WorldBuilderError(Exception):
    """Base exception for all WorldBuilder domain failures."""

    code: str = "WORLD_BUILDER_ERROR"

    def __init__(self, message: str, *, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}

    def to_payload(self) -> Dict[str, Any]:
        return ErrorPayload(self.code, self.message, self.details or None).to_dict()


class StageUnavailableError(WorldBuilderError):
    code = "STAGE_UNAVAILABLE"

    def __init__(self, message: str = "USD stage is not available", *, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, details=details)


class WorldBuilderValidationError(WorldBuilderError):
    code = "VALIDATION_ERROR"


class AuthFailureError(WorldBuilderError):
    code = "AUTH_FAILURE"


def error_response(code: str, message: str, *, details: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Return a standardised error payload."""
    return ErrorPayload(code, message, details).to_dict()
