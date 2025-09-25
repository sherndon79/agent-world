"""
Unified logging setup for Agent World services (extensions + MCP).

Defaults:
- stderr StreamHandler only (journald/systemd captures it on Linux)
- Level INFO (overridable via env)
- Optional JSON format and optional extra handlers via env, no static paths

Env options (optional):
- AGENT_LOG_LEVEL=DEBUG|INFO|WARNING|ERROR (default INFO)
- AGENT_LOG_JSON=1 (JSON formatting)
- AGENT_LOG_TO_JOURNAL=1 (use systemd.journal if available; else ignored)
- AGENT_LOG_FILE=/path/to/file.log (RotatingFileHandler)
- AGENT_LOG_DIR=/path/to/dir (uses <service>.log when AGENT_LOG_FILE unset)
"""

from __future__ import annotations

import json
import logging
import logging.handlers
import os
import sys
from pathlib import Path
from typing import Iterable, Optional


_INITIALIZED = False
_DEFAULT_SERVICE = ""
_SERVICE_PREFIXES: list[tuple[str, str]] = []

__all__ = [
    "setup_logging",
    "get_logger",
    "module_logger",
]


def _normalize_alias(alias: str) -> str:
    alias = alias.strip()
    return alias


def _register_alias(service: str, alias: str) -> None:
    normalized = _normalize_alias(alias)
    if not normalized:
        return

    # Replace existing mapping when the alias already exists
    for idx, (prefix, _) in enumerate(_SERVICE_PREFIXES):
        if prefix == normalized:
            _SERVICE_PREFIXES[idx] = (normalized, service)
            break
    else:
        _SERVICE_PREFIXES.append((normalized, service))

    # Longest prefixes first for more specific matches
    _SERVICE_PREFIXES.sort(key=lambda item: len(item[0]), reverse=True)


def _ensure_service_metadata(record: logging.LogRecord) -> str:
    current = getattr(record, 'service', None)
    if current:
        return current

    name = record.name
    for prefix, service in _SERVICE_PREFIXES:
        if name == prefix or name.startswith(f"{prefix}.") or name.startswith(f"{prefix}:"):
            record.service = service
            return service

    record.service = _DEFAULT_SERVICE
    return record.service


class _ServiceFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        _ensure_service_metadata(record)
        return True


class _JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            'ts': self.formatTime(record, datefmt='%Y-%m-%dT%H:%M:%S'),
            'level': record.levelname,
            'name': record.name,
            'service': getattr(record, 'service', ''),
            'message': record.getMessage(),
        }
        return json.dumps(payload, ensure_ascii=False)


class _MinLevelFilter(logging.Filter):
    def __init__(self, min_level: int):
        super().__init__()
        self.min_level = min_level

    def filter(self, record: logging.LogRecord) -> bool:
        return record.levelno >= self.min_level


class _MaxLevelFilter(logging.Filter):
    def __init__(self, max_level: int):
        super().__init__()
        self.max_level = max_level

    def filter(self, record: logging.LogRecord) -> bool:
        return record.levelno <= self.max_level


def _get_level(default: str = 'INFO') -> int:
    level = os.getenv('AGENT_LOG_LEVEL', default).upper()
    return getattr(logging, level, logging.INFO)


def _collect_aliases(service: str, provided: Optional[Iterable[str]]) -> set[str]:
    aliases: set[str] = {service}

    # Common module prefixes for extensions and MCP servers
    aliases.add(f"omni.agent.{service}")
    aliases.add(f"agent.world.{service}")

    # Include caller-provided aliases
    if provided:
        for alias in provided:
            normalized = _normalize_alias(str(alias))
            if normalized:
                aliases.add(normalized)

    return {alias for alias in aliases if alias}


def setup_logging(
    service: str,
    level: Optional[str] = None,
    json_format: Optional[bool] = None,
    aliases: Optional[Iterable[str]] = None,
) -> None:
    """Configure unified logging once. Safe to call multiple times.

    Args:
        service: service label (e.g., 'worldbuilder')
        level: optional level override (DEBUG/INFO/...) else from env
        json_format: optional flag to force JSON format, else from env
        aliases: optional iterable of logger-name prefixes that should map to
            this service when no explicit service context is provided.
    """
    alias_set = _collect_aliases(service, aliases)

    global _DEFAULT_SERVICE
    global _INITIALIZED

    logger = logging.getLogger()

    if not _INITIALIZED:
        logger.setLevel(_get_level(level or 'INFO'))

        # Formatter
        use_json = (str(json_format).lower() in ('1', 'true', 'yes', 'on')) if json_format is not None \
            else (os.getenv('AGENT_LOG_JSON', '').lower() in ('1', 'true', 'yes', 'on'))
        if use_json:
            formatter = _JSONFormatter()
        else:
            formatter = logging.Formatter('%(asctime)s %(levelname)s %(name)s [%(service)s] %(message)s')

        # Filter to inject service field
        service_filter = _ServiceFilter()

        # Split streams: INFO/DEBUG -> stdout, WARNING/ERROR -> stderr
        stdout_handler = logging.StreamHandler(stream=sys.stdout)
        stdout_handler.setFormatter(formatter)
        stdout_handler.addFilter(service_filter)
        stdout_handler.addFilter(_MaxLevelFilter(logging.INFO))
        logger.addHandler(stdout_handler)

        stderr_handler = logging.StreamHandler(stream=sys.stderr)
        stderr_handler.setFormatter(formatter)
        stderr_handler.addFilter(service_filter)
        stderr_handler.addFilter(_MinLevelFilter(logging.WARNING))
        logger.addHandler(stderr_handler)

        # Optional journald handler
        if os.getenv('AGENT_LOG_TO_JOURNAL', '').lower() in ('1', 'true', 'yes', 'on'):
            try:
                from systemd.journal import JournalHandler  # type: ignore
                jh = JournalHandler()
                jh.setFormatter(formatter)
                jh.addFilter(service_filter)
                logger.addHandler(jh)
            except Exception:
                # systemd not available; silently skip
                pass

        # Optional file handler
        log_path = os.getenv('AGENT_LOG_FILE')
        if not log_path:
            log_dir = os.getenv('AGENT_LOG_DIR')
            if log_dir:
                log_path = str(Path(log_dir) / f'{service}.log')

        if log_path:
            try:
                Path(log_path).parent.mkdir(parents=True, exist_ok=True)
                fh = logging.handlers.RotatingFileHandler(log_path, maxBytes=5 * 1024 * 1024, backupCount=5, encoding='utf-8')
                fh.setFormatter(formatter)
                fh.addFilter(service_filter)
                logger.addHandler(fh)
            except Exception:
                # Fallback to stderr-only if file handler fails
                logger.warning(f"Could not open log file {log_path}, using stderr only")

        _INITIALIZED = True
        if not _DEFAULT_SERVICE:
            _DEFAULT_SERVICE = service

    # Register aliases even when handlers are already configured
    for alias in alias_set:
        _register_alias(service, alias)


def get_logger(name: Optional[str] = None, **context) -> logging.LoggerAdapter:
    base = logging.getLogger(name or __name__)
    # Ensure 'service' in context so formatter always sees it; rely on filter as fallback
    if 'service' not in context:
        context['service'] = ''
    return logging.LoggerAdapter(base, context)


def module_logger(**context) -> logging.LoggerAdapter:
    """Convenience to get a logger for the caller's module."""
    name = sys._getframe(1).f_globals.get('__name__', __name__)
    return get_logger(name, **context)
