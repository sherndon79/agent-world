#!/usr/bin/env python3
"""
WorldStreamer Configuration

Handles environment variables and configuration for the WorldStreamer MCP server.
"""

import os
import sys
from pathlib import Path
from typing import Optional


def _ensure_core_path() -> bool:
    current = Path(__file__).resolve()
    for candidate in (current, *current.parents):
        core_path = candidate / 'agentworld-core' / 'src'
        if core_path.exists():
            core_str = str(core_path)
            if core_str not in sys.path:
                sys.path.insert(0, core_str)
            return True
    return False


try:
    from agentworld_core.config import create_worldstreamer_config
except ImportError:  # pragma: no cover - attempt to locate source checkout
    if _ensure_core_path():
        try:
            from agentworld_core.config import create_worldstreamer_config
        except ImportError:  # pragma: no cover
            create_worldstreamer_config = None
    else:
        create_worldstreamer_config = None

_unified_config = create_worldstreamer_config() if create_worldstreamer_config else None


class WorldStreamerConfig:
    """Configuration manager for WorldStreamer MCP server."""

    def __init__(self):
        self.unified_config = _unified_config

    @property
    def server_port(self) -> int:
        """Get the MCP server port."""
        return int(os.getenv("MCP_SERVER_PORT", 8702))

    @property
    def rtmp_base_url(self) -> str:
        """Get the WorldStreamer RTMP extension base URL."""
        return (
            os.getenv("AGENT_WORLDSTREAMER_RTMP_BASE_URL")
            or os.getenv("WORLDSTREAMER_RTMP_API_URL")
            or (self.unified_config.get_rtmp_server_url() if self.unified_config else None)
            or "http://localhost:8906"
        )

    @property
    def srt_base_url(self) -> str:
        """Get the WorldStreamer SRT extension base URL."""
        return (
            os.getenv("AGENT_WORLDSTREAMER_SRT_BASE_URL")
            or os.getenv("WORLDSTREAMER_SRT_API_URL")
            or (self.unified_config.get_srt_server_url() if self.unified_config else None)
            or "http://localhost:8908"
        )

    @property
    def worldstreamer_base_url(self) -> Optional[str]:
        """Get manual override base URL for WorldStreamer extension."""
        return (
            os.getenv("AGENT_WORLDSTREAMER_BASE_URL")
            or os.getenv("WORLDSTREAMER_API_URL")
        )

    @property
    def log_level(self) -> str:
        """Get the logging level."""
        return os.getenv("LOG_LEVEL", "INFO").upper()

    @property
    def auth_enabled(self) -> bool:
        """Check if authentication is enabled."""
        return os.getenv("AGENT_EXT_AUTH_ENABLED", "0") == "1"

    @property
    def auth_token(self) -> Optional[str]:
        """Get the authentication token."""
        return os.getenv("AGENT_EXT_AUTH_TOKEN")

    @property
    def hmac_secret(self) -> Optional[str]:
        """Get the HMAC secret."""
        return os.getenv("AGENT_EXT_HMAC_SECRET")

    def get_timeout(self, operation: str) -> float:
        """Get timeout for specific operations."""
        if self.unified_config:
            return self.unified_config.get(f'{operation}_timeout', 30.0)

        # Default timeouts for different operations
        timeouts = {
            'health_check': 5.0,
            'start_streaming': 30.0,
            'stop_streaming': 30.0,
            'get_status': 10.0,
            'get_streaming_urls': 10.0,
            'validate_environment': 30.0,
        }
        return timeouts.get(operation, 30.0)


# Global config instance
config = WorldStreamerConfig()
