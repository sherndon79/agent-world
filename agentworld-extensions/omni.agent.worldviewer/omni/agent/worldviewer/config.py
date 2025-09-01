"""
WorldViewer Configuration using Unified Agent World Config System.

This replaces the old duplicated config logic with the unified system,
eliminating code duplication while maintaining identical functionality and interface.
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


class WorldViewerConfig(WorldExtensionConfig if CONFIG_AVAILABLE else object):
    """
    WorldViewer configuration using unified Agent World config system.
    
    Maintains exact same interface as old WorldViewerConfig while eliminating
    all the duplicated configuration loading logic.
    """
    
    # WorldViewer-specific configuration defaults
    DEFAULTS = {
        # Server configuration  
        'server_port': 8900,
        'server_host': 'localhost',
        'server_ports_to_try': [8900, 8901, 8902, 8903, 8904],
        'server_timeout': 1.0,
        'server_ready_timeout': 5.0,
        
        # General settings
        'debug_mode': False,
        'verbose_logging': False,
        'auth_enabled': True,
        'startup_delay': 0.1,
        
        # Camera and viewport
        'default_camera_distance': 10.0,
        'min_camera_distance': 0.1,
        'max_camera_distance': 1000.0,
        'default_orbit_elevation': 15.0,
        'cache_duration_ms': 500,
        
        # Cinematic movements
        'default_movement_duration': 3.0,
        'max_movement_duration': 60.0,
        'min_movement_duration': 0.1,
        'default_easing': 'ease_in_out',
        
        # Rate limiting
        'rate_limit_max_requests': 100,
        'rate_limit_window_seconds': 60,
        
        # Timeouts and delays
        'shutdown_timeout': 5.0,
        'processing_interval_ms': 100,
        'ui_update_frequency_ms': 500,
        
        # Logging and debug
        'log_thread_info': False,
        'log_request_details': False,
        'log_camera_operations': False,
        
        # Security
        'cors_enabled': True,
        'cors_origin': '*',
        
        # Integration with other extensions
        'worldbuilder_port': 8899,
        'worldbuilder_host': 'localhost',
        'worldselector_port': 8891,
        'worldselector_host': 'localhost',
        'worldmind_port': 8892,
        'worldmind_host': 'localhost',
        
        # UI and interaction
        'quick_positions_enabled': True,
        'manual_controls_enabled': True,
        'hotkey_enabled': True,
        
        # Performance
        'enable_frame_limiting': True,
        'max_concurrent_movements': 1,
        'movement_queue_enabled': True,
    }
    
    def __init__(self, config_file: str = None):
        """Initialize WorldViewer configuration."""
        if CONFIG_AVAILABLE:
            # Use unified config system
            super().__init__(
                extension_name='worldviewer',
                config_file=config_file or 'worldviewer_config.json'
            )
        else:
            # Fallback to basic config if unified system unavailable
            self._config = self.DEFAULTS.copy()
            logging.getLogger(__name__).warning("Using fallback configuration (unified system unavailable)")
    
    # Backward compatibility methods for existing WorldViewer code
    def get(self, key: str, default=None):
        """Get configuration value - maintains old interface."""
        if CONFIG_AVAILABLE:
            return super().get(key, default)
        else:
            return self._config.get(key, default)
    
    def get_all(self):
        """Get all config values - maintains old interface.""" 
        if CONFIG_AVAILABLE:
            return super().get_all()
        else:
            return self._config.copy()
    
    # Backward compatibility properties for existing WorldViewer code
    @property
    def server_host(self) -> str:
        return self.get('server_host', 'localhost')
    
    @property
    def server_ports_to_try(self) -> list:
        return self.get('server_ports_to_try', [8900, 8901, 8902, 8903, 8904])
    
    @property
    def server_timeout(self) -> float:
        return self.get('server_timeout', 1.0)
    
    @property 
    def server_ready_timeout(self) -> float:
        return self.get('server_ready_timeout', 5.0)
    
    @property
    def shutdown_timeout(self) -> float:
        return self.get('shutdown_timeout', 5.0)
    
    # Camera and viewport properties
    @property
    def default_camera_distance(self) -> float:
        return self.get('default_camera_distance', 10.0)
    
    @property
    def min_camera_distance(self) -> float:
        return self.get('min_camera_distance', 0.1)
    
    @property
    def max_camera_distance(self) -> float:
        return self.get('max_camera_distance', 1000.0)
    
    @property
    def default_orbit_elevation(self) -> float:
        return self.get('default_orbit_elevation', 15.0)
    
    @property
    def cache_duration_ms(self) -> int:
        return self.get('cache_duration_ms', 500)
    
    # Cinematic movement properties
    @property
    def default_movement_duration(self) -> float:
        return self.get('default_movement_duration', 3.0)
    
    @property
    def max_movement_duration(self) -> float:
        return self.get('max_movement_duration', 60.0)
    
    @property
    def min_movement_duration(self) -> float:
        return self.get('min_movement_duration', 0.1)
    
    @property
    def default_easing(self) -> str:
        return self.get('default_easing', 'ease_in_out')
    
    # Rate limiting properties
    @property
    def rate_limit_max_requests(self) -> int:
        return self.get('rate_limit_max_requests', 100)
    
    @property
    def rate_limit_window_seconds(self) -> int:
        return self.get('rate_limit_window_seconds', 60)
    
    # Timing properties
    @property
    def processing_interval_ms(self) -> int:
        return self.get('processing_interval_ms', 100)
    
    @property
    def ui_update_frequency_ms(self) -> int:
        return self.get('ui_update_frequency_ms', 500)
    
    # Logging properties
    @property
    def log_thread_info(self) -> bool:
        return self.get('log_thread_info', False)
    
    @property
    def log_request_details(self) -> bool:
        return self.get('log_request_details', False)
    
    @property
    def log_camera_operations(self) -> bool:
        return self.get('log_camera_operations', False)
    
    # Security properties
    @property
    def cors_enabled(self) -> bool:
        return self.get('cors_enabled', True)
    
    @property
    def cors_origin(self) -> str:
        return self.get('cors_origin', '*')
    
    # Integration properties
    @property
    def worldbuilder_port(self) -> int:
        return self.get('worldbuilder_port', 8899)
    
    @property
    def worldbuilder_host(self) -> str:
        return self.get('worldbuilder_host', 'localhost')
    
    @property
    def worldselector_port(self) -> int:
        return self.get('worldselector_port', 8891)
    
    @property
    def worldselector_host(self) -> str:
        return self.get('worldselector_host', 'localhost')
    
    @property
    def worldmind_port(self) -> int:
        return self.get('worldmind_port', 8892)
    
    @property
    def worldmind_host(self) -> str:
        return self.get('worldmind_host', 'localhost')
    
    # UI and interaction properties
    @property
    def quick_positions_enabled(self) -> bool:
        return self.get('quick_positions_enabled', True)
    
    @property
    def manual_controls_enabled(self) -> bool:
        return self.get('manual_controls_enabled', True)
    
    @property
    def hotkey_enabled(self) -> bool:
        return self.get('hotkey_enabled', True)
    
    # Performance properties
    @property
    def enable_frame_limiting(self) -> bool:
        return self.get('enable_frame_limiting', True)
    
    @property
    def max_concurrent_movements(self) -> int:
        return self.get('max_concurrent_movements', 1)
    
    @property
    def movement_queue_enabled(self) -> bool:
        return self.get('movement_queue_enabled', True)


# Global config instance for backward compatibility
_global_config_instance = None

def get_config() -> WorldViewerConfig:
    """
    Get global WorldViewer configuration instance.
    
    Maintains backward compatibility with existing code that expects:
    from .config import get_config
    config = get_config()
    """
    global _global_config_instance
    if _global_config_instance is None:
        _global_config_instance = WorldViewerConfig()
    return _global_config_instance
