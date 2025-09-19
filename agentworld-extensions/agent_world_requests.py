"""Shared request tracking utilities for Agent World extensions."""

from __future__ import annotations

import threading
import time
from collections import OrderedDict
from typing import Any, Dict, Optional


class RequestTracker:
    """Thread-safe tracker for queued operations.

    Stores request metadata, automatically prunes completed/expired entries, and
    exposes helpers for status lookups shared across HTTP and MCP transports.
    """

    def __init__(
        self,
        *,
        max_entries: int = 500,
        ttl_seconds: Optional[float] = 300.0,
    ) -> None:
        self._lock = threading.Lock()
        self._requests: "OrderedDict[str, Dict[str, Any]]" = OrderedDict()
        self._max_entries = max(1, max_entries)
        self._ttl_seconds = ttl_seconds if ttl_seconds is None or ttl_seconds > 0 else None

    # ------------------------------------------------------------------
    def add(self, request_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Register a request. Returns the stored payload copy."""
        entry = dict(payload)
        entry.setdefault('timestamp', time.time())
        entry.setdefault('completed', False)

        with self._lock:
            self._requests[request_id] = entry
            self._prune_locked()
            return dict(entry)

    def mark_completed(
        self,
        request_id: str,
        *,
        result: Any | None = None,
        error: Any | None = None,
    ) -> Optional[Dict[str, Any]]:
        """Mark a request as completed and optionally store result/error."""
        update: Dict[str, Any] = {'completed': True, 'completed_time': time.time()}
        if result is not None:
            update['result'] = result
        if error is not None:
            update['error'] = error
        return self.update(request_id, **update)

    def update(self, request_id: str, **updates: Any) -> Optional[Dict[str, Any]]:
        """Apply arbitrary updates to a tracked request."""
        with self._lock:
            entry = self._requests.get(request_id)
            if not entry:
                return None
            entry.update(updates)
            if updates.get('completed') and 'completed_time' not in entry:
                entry['completed_time'] = time.time()
            return dict(entry)

    def get(self, request_id: str, *, remove_if_expired: bool = True) -> Optional[Dict[str, Any]]:
        """Fetch a request snapshot. Optionally removes expired entries."""
        with self._lock:
            entry = self._requests.get(request_id)
            if not entry:
                return None
            if self._ttl_seconds is not None and self._is_expired(entry):
                if remove_if_expired:
                    self._requests.pop(request_id, None)
                return None
            return dict(entry)

    def pop(self, request_id: str) -> Optional[Dict[str, Any]]:
        """Remove a request from the tracker and return it."""
        with self._lock:
            entry = self._requests.pop(request_id, None)
            if entry and self._ttl_seconds is not None and self._is_expired(entry):
                return None
            return dict(entry) if entry else None

    def prune(self) -> None:
        """Public method to prune expired or excess entries."""
        with self._lock:
            self._prune_locked()

    def clear(self) -> None:
        with self._lock:
            self._requests.clear()

    def __len__(self) -> int:  # pragma: no cover - simple helper
        with self._lock:
            return len(self._requests)

    # ------------------------------------------------------------------
    def _prune_locked(self) -> None:
        if self._ttl_seconds is not None:
            expired_keys = [key for key, entry in self._requests.items() if self._is_expired(entry)]
            for key in expired_keys:
                self._requests.pop(key, None)

        while len(self._requests) > self._max_entries:
            self._requests.popitem(last=False)

    def _is_expired(self, entry: Dict[str, Any]) -> bool:
        if self._ttl_seconds is None:
            return False
        reference = entry.get('completed_time') or entry.get('timestamp') or time.time()
        return (time.time() - reference) > self._ttl_seconds


__all__ = ["RequestTracker"]
