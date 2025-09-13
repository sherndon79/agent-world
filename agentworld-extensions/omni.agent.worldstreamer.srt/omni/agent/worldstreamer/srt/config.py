"""
WorldStreamer Configuration using Unified Agent World Config System.

Focused configuration for streaming control only - no external application logic.
Follows the established modular pattern from WorldViewer/WorldBuilder.
"""

import sys
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
        'server_timeout': 1.0,
        'server_ready_timeout': 5.0,
        'health_check_interval': 10.0,
        'metrics_collection_enabled': True,
    } if CONFIG_AVAILABLE else {
        # Fallback standalone defaults when unified config unavailable
        'server_port': 8908,
        'rtmp_port': 1935,
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
