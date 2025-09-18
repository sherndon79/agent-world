"""Shared transport helpers for WorldBuilder HTTP/MCP integrations."""

from __future__ import annotations

from typing import Any, Dict

from ..errors import error_response


def normalize_transport_response(
    operation: str,
    response: Any,
    *,
    default_error_code: str,
) -> Dict[str, Any]:
    """Ensure downstream transports receive a structured response."""
    if response is None:
        return error_response(
            "EMPTY_RESPONSE",
            "Service returned no data",
            details={"operation": operation},
        )

    if not isinstance(response, dict):
        return error_response(
            "INVALID_RESPONSE",
            "Service returned unexpected response type",
            details={"operation": operation, "type": type(response).__name__},
        )

    response.setdefault("success", True)
    if response["success"] is False:
        response.setdefault("error_code", default_error_code)
        response.setdefault("error", "An unknown error occurred")

    return response


__all__ = ["normalize_transport_response"]
