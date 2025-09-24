"""Minimal helper to reuse shared utilities when the full agentworld-extensions package is unavailable."""

from __future__ import annotations

from typing import Any, Dict


def normalize_transport_response(operation: str, response: Any, *, default_error_code: str) -> Dict[str, Any]:
    if not isinstance(response, dict):
        return error_response(
            'INVALID_RESPONSE',
            'Service returned unexpected response type',
            details={'operation': operation, 'type': type(response).__name__},
        )

    response.setdefault('success', True)
    if response['success'] is False:
        response.setdefault('error_code', default_error_code)
        response.setdefault('error', 'An unknown error occurred')
    return response


def error_response(code: str, message: str, *, details: Dict[str, Any] | None = None) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        'success': False,
        'error_code': code,
        'error': message,
    }
    if details:
        payload['details'] = details
    return payload


__all__ = ['normalize_transport_response', 'error_response']
