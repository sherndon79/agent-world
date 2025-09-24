#!/usr/bin/env python3
"""
WorldBuilder Configuration

Handles environment variables and configuration for the WorldBuilder MCP server.
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


try:  # Prefer packaged core helpers when available
    from agentworld_core.config import create_worldbuilder_config
except ImportError:  # pragma: no cover - fallback to source checkout detection
    if _ensure_core_path():
        try:
            from agentworld_core.config import create_worldbuilder_config
        except ImportError:  # pragma: no cover - core genuinely unavailable
            create_worldbuilder_config = None
    else:  # pragma: no cover - couldn't locate source tree
        create_worldbuilder_config = None

_unified_config = create_worldbuilder_config() if create_worldbuilder_config else None


class WorldBuilderConfig:
    """Configuration manager for WorldBuilder MCP server."""

    def __init__(self):
        self.unified_config = _unified_config

    @property
    def server_port(self) -> int:
        """Get the MCP server port."""
        return int(os.getenv("MCP_SERVER_PORT", 8700))

    @property
    def worldbuilder_base_url(self) -> str:
        """Get the WorldBuilder extension base URL."""
        return (
            os.getenv("AGENT_WORLDBUILDER_BASE_URL")
            or os.getenv("WORLDBUILDER_API_URL")
            or (self.unified_config.get_server_url() if self.unified_config else None)
            or "http://localhost:8899"
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
            'scene_status': 10.0,
            'add_element': 30.0,
            'create_batch': 60.0,
            'place_asset': 45.0,
            'transform_asset': 30.0,
            'query_objects': 30.0,
            'align_objects': 45.0,
            'clear_scene': 60.0,
            'clear_path': 45.0,
        }
        return timeouts.get(operation, 30.0)


# Global config instance
config = WorldBuilderConfig()
