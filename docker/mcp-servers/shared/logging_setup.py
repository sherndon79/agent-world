"""
Unified logging setup for MCP servers.

This mirrors the extensions' agentworld_core.logging module to keep behavior consistent.
Defaults to stderr-only output; env-driven options for JSON, journald, and files.
"""

from __future__ import annotations

import json
import logging
import logging.handlers
import os
import sys
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


def setup_logging(service: str, level: Optional[str] = None, json_format: Optional[bool] = None) -> None:
    global _INITIALIZED
    if _INITIALIZED:
        return

    root = logging.getLogger()
    root.setLevel(_get_level(level or 'INFO'))

    use_json = (str(json_format).lower() in ('1','true','yes','on')) if json_format is not None \
        else (os.getenv('AGENT_LOG_JSON', '').lower() in ('1','true','yes','on'))
    if use_json:
        formatter = _JSONFormatter()
    else:
        formatter = logging.Formatter('%(asctime)s %(levelname)s %(name)s [%(service)s] %(message)s')

    service_filter = _ServiceFilter(service)

    # Split streams: INFO/DEBUG -> stdout, WARNING/ERROR -> stderr
    stdout_handler = logging.StreamHandler(stream=sys.stdout)
    stdout_handler.setFormatter(formatter)
    stdout_handler.addFilter(service_filter)
    stdout_handler.addFilter(_MaxLevelFilter(logging.INFO))
    root.addHandler(stdout_handler)

    stderr_handler = logging.StreamHandler(stream=sys.stderr)
    stderr_handler.setFormatter(formatter)
    stderr_handler.addFilter(service_filter)
    stderr_handler.addFilter(_MinLevelFilter(logging.WARNING))
    root.addHandler(stderr_handler)

    if os.getenv('AGENT_LOG_TO_JOURNAL', '').lower() in ('1','true','yes','on'):
        try:
            from systemd.journal import JournalHandler  # type: ignore
            jh = JournalHandler()
            jh.setFormatter(formatter)
            jh.addFilter(service_filter)
            root.addHandler(jh)
        except Exception:
            pass

    log_path = os.getenv('AGENT_LOG_FILE')
    if not log_path:
        log_dir = os.getenv('AGENT_LOG_DIR')
        if log_dir:
            log_path = str(Path(log_dir) / f'{service}.log')

    if log_path:
        try:
            Path(log_path).parent.mkdir(parents=True, exist_ok=True)
            fh = logging.handlers.RotatingFileHandler(log_path, maxBytes=5*1024*1024, backupCount=5, encoding='utf-8')
            fh.setFormatter(formatter)
            fh.addFilter(service_filter)
            root.addHandler(fh)
        except Exception:
            root.warning(f'Could not open log file {log_path}, using stderr only')

    _INITIALIZED = True


def get_logger(name: Optional[str] = None, **context) -> logging.LoggerAdapter:
    base = logging.getLogger(name or __name__)
    if 'service' not in context:
        context['service'] = ''
    return logging.LoggerAdapter(base, context)
