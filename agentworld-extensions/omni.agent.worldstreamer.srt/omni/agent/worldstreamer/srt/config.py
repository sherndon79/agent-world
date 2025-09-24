"""
WorldStreamer Configuration using Unified Agent World Config System.

Focused configuration for streaming control only - no external application logic.
Follows the established modular pattern from WorldViewer/WorldBuilder.
"""

import sys
import logging
from pathlib import Path


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


_ensure_core_path()


# Import the unified config system from agentworld-core
try:
    from agentworld_core.config import WorldExtensionConfig
    CONFIG_AVAILABLE = True
except ImportError:
    if _ensure_core_path():
        try:
            from agentworld_core.config import WorldExtensionConfig
            CONFIG_AVAILABLE = True
        except ImportError as exc:  # pragma: no cover
            logging.getLogger(__name__).warning(f"Could not import unified config system: {exc}")
            CONFIG_AVAILABLE = False
    else:
        logging.getLogger(__name__).warning("Could not locate agentworld-core/src for unified config system")
        CONFIG_AVAILABLE = False


class WorldStreamerConfig(WorldExtensionConfig if CONFIG_AVAILABLE else object):
    """
    WorldStreamer configuration using unified Agent World config system.
    
    Uses agent-world-config.json for all configuration - no code-based defaults.
    Maintains clean separation of concerns.
    """
    
    # WorldStreamer-specific defaults (extends base WorldExtensionConfig.DEFAULTS)
    DEFAULTS = {
        **getattr(WorldExtensionConfig, 'DEFAULTS', {}),  # Include base defaults
        'server_port': 8908,  # WorldStreamer SRT default port
        'rtmp_port': 1935,
        'srt_host': '127.0.0.1',
        'srt_port': 9999,
        'server_timeout': 1.0,
        'server_ready_timeout': 5.0,
        'health_check_interval': 10.0,
        'metrics_collection_enabled': True,
    } if CONFIG_AVAILABLE else {
        # Fallback standalone defaults when unified config unavailable
        'server_port': 8908,
        'rtmp_port': 1935,
        'srt_host': '127.0.0.1',
        'srt_port': 9999,
        'server_timeout': 1.0,
        'server_ready_timeout': 5.0,
        'health_check_interval': 10.0,
        'metrics_collection_enabled': True,
    }
    
    def __init__(self, config_file: str = "worldstreamer_config.json"):
        """
        Initialize WorldStreamer configuration.
        
        Args:
            config_file: Configuration file name (optional)
        """
        if CONFIG_AVAILABLE:
            super().__init__(
                extension_name="worldstreamer.srt",
                config_file=config_file
            )
        else:
            # Fallback configuration if unified system unavailable
            self._config = self.DEFAULTS.copy()
            logging.getLogger(__name__).warning("Using fallback configuration - unified system unavailable")
    
    def get_streaming_config(self) -> dict:
        """
        Get streaming-specific configuration for Isaac Sim 5.0.
        
        Returns:
            Dict with streaming configuration parameters
        """
        if CONFIG_AVAILABLE:
            return {
                'rtmp_port': self.get('rtmp_port'),
                'stream_timeout': self.get('stream_timeout'),
                'ip_detection_timeout': self.get('ip_detection_timeout'),
                'max_concurrent_streams': self.get('max_concurrent_streams'),
            }
        else:
            return {
                'rtmp_port': self._config['rtmp_port'],
                'stream_timeout': self._config['stream_timeout'],
                'ip_detection_timeout': self._config['ip_detection_timeout'],
                'max_concurrent_streams': self._config['max_concurrent_streams'],
            }
    
    def get_encoder_config(self) -> dict:
        """
        Get encoder-specific configuration for SRT streaming.
        
        Returns:
            Dict with encoder configuration settings
        """
        if CONFIG_AVAILABLE:
            return {
                'hardware_encoding_preferred': self.get('hardware_encoding_preferred', True),
                'encoder_type': self.get('encoder_type', 'auto'),  # auto, nvenc, vaapi, x264
                'encoding_bitrate': self.get('encoding_bitrate', 2000),  # kbps
                'encoding_fps': self.get('encoding_fps', 24),
            }
        else:
            return {
                'hardware_encoding_preferred': True,
                'encoder_type': 'auto',
                'encoding_bitrate': 2000,
                'encoding_fps': 24,
            }


# Global configuration instance
_config_instance = None


def get_config() -> WorldStreamerConfig:
    """
    Get the global WorldStreamer configuration instance.
    
    Returns:
        WorldStreamerConfig instance
    """
    global _config_instance
    if _config_instance is None:
        _config_instance = WorldStreamerConfig()
    return _config_instance


def reload_config() -> WorldStreamerConfig:
    """
    Reload the global configuration instance.
    
    Returns:
        New WorldStreamerConfig instance
    """
    global _config_instance
    _config_instance = WorldStreamerConfig()
    return _config_instance
