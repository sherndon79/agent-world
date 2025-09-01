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
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


_INITIALIZED = False


class _ServiceFilter(logging.Filter):
    def __init__(self, service: str):
        super().__init__()
        self.service = service

    def filter(self, record: logging.LogRecord) -> bool:
        if not hasattr(record, 'service'):
            record.service = self.service
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


def _get_level(default: str = 'INFO') -> int:
    level = os.getenv('AGENT_LOG_LEVEL', default).upper()
    return getattr(logging, level, logging.INFO)


def setup_logging(service: str, level: Optional[str] = None, json_format: Optional[bool] = None) -> None:
    """Configure unified logging once. Safe to call multiple times.

    Args:
        service: service label (e.g., 'worldbuilder')
        level: optional level override (DEBUG/INFO/...) else from env
        json_format: optional flag to force JSON format, else from env
    """
    global _INITIALIZED
    if _INITIALIZED:
        return

    logger = logging.getLogger()
    logger.setLevel(_get_level(level or 'INFO'))

    # Formatter
    use_json = (str(json_format).lower() in ('1', 'true', 'yes', 'on')) if json_format is not None \
        else (os.getenv('AGENT_LOG_JSON', '').lower() in ('1', 'true', 'yes', 'on'))
    if use_json:
        formatter = _JSONFormatter()
    else:
        formatter = logging.Formatter('%(asctime)s %(levelname)s %(name)s [%(service)s] %(message)s')

    # Filter to inject service field
    service_filter = _ServiceFilter(service)

    # Always stderr stream handler
    sh = logging.StreamHandler(stream=sys.stderr)
    sh.setFormatter(formatter)
    sh.addFilter(service_filter)
    logger.addHandler(sh)

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

