"""Shared transport helpers for Agent World extensions."""

from __future__ import annotations

from typing import Any, Dict


def normalize_transport_response(
    operation: str,
    response: Any,
    *,
    default_error_code: str,
) -> Dict[str, Any]:
    """Ensure transport callers receive a structured response dictionary."""
    if response is None:
        return {
            "success": False,
            "error_code": "EMPTY_RESPONSE",
            "error": "Service returned no data",
            "details": {"operation": operation},
        }

    if not isinstance(response, dict):
        return {
            "success": False,
            "error_code": "INVALID_RESPONSE",
            "error": "Service returned unexpected response type",
            "details": {"operation": operation, "type": type(response).__name__},
        }

    response.setdefault("success", True)
    if response["success"] is False:
        response.setdefault("error_code", default_error_code)
        response.setdefault("error", "An unknown error occurred")

    return response


__all__ = ["normalize_transport_response"]
