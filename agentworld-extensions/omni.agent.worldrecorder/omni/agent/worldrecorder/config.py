"""
Unified configuration for WorldRecorder extension.
"""
import os
import sys
import tempfile
import logging
from pathlib import Path

# Import the unified config system from agentworld-extensions root
try:
    # Find the agentworld-extensions directory
    current = Path(__file__).resolve()
    for _ in range(10):  # Search up the directory tree
        if current.name == 'agentworld-extensions':
            sys.path.insert(0, str(current))
            break
        current = current.parent
    
    from agent_world_config import WorldExtensionConfig
    CONFIG_AVAILABLE = True
except ImportError as e:
    logging.getLogger(__name__).warning(f"Could not import unified config system: {e}")
    CONFIG_AVAILABLE = False


class WorldRecorderConfig(WorldExtensionConfig if CONFIG_AVAILABLE else object):
    DEFAULTS = {
        'server_port': 8892,
        'server_host': 'localhost',
        'debug_mode': False,
        'verbose_logging': False,
        'auth_enabled': True,
        'startup_delay': 0.1,
        'shutdown_timeout': 5.0,
        'default_fps': 24,
        'max_recording_duration': 300,
        'output_directory': '/tmp/recordings',  # Will be overridden by OS-specific temp dir logic
        'auto_cleanup_recordings': False,
        'max_queue_size': 100,
        'hardware_encoding_preferred': True,
        'capture_depth_buffer': False,
    }

    def __init__(self):
        """Initialize WorldRecorder configuration."""
        if CONFIG_AVAILABLE:
            # Use unified config system
            super().__init__(extension_name='worldrecorder')
        else:
            # Fallback to basic config if unified system unavailable
            self._config = self.DEFAULTS.copy()
            logging.getLogger(__name__).warning("Using fallback configuration (unified system unavailable)")
    
    # Backward compatibility methods for existing WorldRecorder code
    def get(self, key: str, default=None):
        """Get configuration value with fallback support."""
        if CONFIG_AVAILABLE:
            return super().get(key, default)
        else:
            return self._config.get(key, default)

    # Convenience properties
    @property
    def server_port(self) -> int:
        return int(self.get('server_port', 8892))

    @property
    def server_host(self) -> str:
        return str(self.get('server_host', 'localhost'))

    @property
    def debug_mode(self) -> bool:
        return bool(self.get('debug_mode', False))

    @property
    def startup_delay(self) -> float:
        return float(self.get('startup_delay', 0.0))

    @property
    def shutdown_timeout(self) -> float:
        return float(self.get('shutdown_timeout', 5.0))

    @property
    def verbose_logging(self) -> bool:
        return bool(self.get('verbose_logging', False))

    @property
    def auth_enabled(self) -> bool:
        return bool(self.get('auth_enabled', True))

    @property
    def default_fps(self) -> int:
        return int(self.get('default_fps', 24))

    @property
    def max_recording_duration(self) -> int:
        return int(self.get('max_recording_duration', 300))

    @property
    def auto_cleanup_recordings(self) -> bool:
        return bool(self.get('auto_cleanup_recordings', False))

    @property
    def max_queue_size(self) -> int:
        return int(self.get('max_queue_size', 100))

    @property
    def hardware_encoding_preferred(self) -> bool:
        return bool(self.get('hardware_encoding_preferred', True))

    @property
    def capture_depth_buffer(self) -> bool:
        return bool(self.get('capture_depth_buffer', False))

    @property
    def output_directory(self) -> str:
        """Get output directory with cross-platform temp dir fallback."""
        configured_dir = str(self.get('output_directory', '/tmp/recordings'))
        # If it's the default Unix path, use OS-specific temp dir
        if configured_dir == '/tmp/recordings':
            return os.path.join(tempfile.gettempdir(), 'recordings')
        return configured_dir

    def get_server_url(self) -> str:
        """Get the full server URL."""
        return f"http://{self.server_host}:{self.server_port}"


# Module-level config instance (singleton pattern)
_config_instance = None


def get_config() -> WorldRecorderConfig:
    """Get the global configuration instance (singleton)."""
    global _config_instance
    if _config_instance is None:
        _config_instance = WorldRecorderConfig()
    return _config_instance

