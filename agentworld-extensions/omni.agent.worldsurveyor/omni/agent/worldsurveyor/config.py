"""
WorldSurveyor Configuration using Unified Agent World Config System.

This replaces the old duplicated config logic with the unified system,
eliminating code duplication while maintaining identical functionality and interface.
"""

import sys
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
    print(f"Warning: Could not import unified config system: {e}")
    CONFIG_AVAILABLE = False


class WorldSurveyorConfig(WorldExtensionConfig if CONFIG_AVAILABLE else object):
    """
    WorldSurveyor configuration using unified Agent World config system.
    
    Maintains exact same interface as old WorldSurveyorConfig while eliminating
    all the duplicated configuration loading logic.
    """
    
    # WorldSurveyor-specific configuration defaults
    DEFAULTS = {
        # Server configuration  
        'server_port': 8891,
        'server_host': 'localhost',
        'server_ports_to_try': [8891, 8892, 8893, 8894, 8895, 8896],
        'server_timeout': 1.0,
        'server_ready_timeout': 5.0,
        
        # General settings
        'debug_mode': False,
        'verbose_logging': False,
        'auth_enabled': True,
        'startup_delay': 0.1,
        
        # Waypoint limits
        'max_waypoints': 100,
        
        # Rate limiting
        'rate_limit_max_requests': 100,
        'rate_limit_window_seconds': 60,
        
        # Timeouts and delays
        'shutdown_timeout': 5.0,
        'toolbar_cleanup_timeout': 1.0,
        
        # Logging and debug
        'log_thread_info': False,
        'log_request_details': False,
        
        # Security
        'cors_enabled': True,
        'cors_origin': '*',
        
        # Integration
        'worldviewer_port': 8900,
        'worldviewer_host': 'localhost',
        
        # UI
        'toolbar_enabled': True,
        'hotkey_enabled': False,
        
        # Waypoint positioning
        'waypoint_distance_min': 0.1,      # Minimum distance from camera
        'waypoint_distance_max': 5.0,      # Maximum distance from camera  
        'waypoint_distance_default': 1.0,  # Default slider value
        'waypoint_distance_interval': 0.1, # Distance increment step for slider
        
        # Waypoint visualization
        'auto_load_waypoints': True,       # Auto-load stored waypoints on startup
        
        # Database
        'database_path': None,             # Database file path (None = use default)
    }
    
    def __init__(self, config_file: str = None):
        """Initialize WorldSurveyor configuration."""
        if CONFIG_AVAILABLE:
            # Use unified config system
            super().__init__(
                extension_name='worldsurveyor',
                config_file=config_file or 'worldsurveyor_config.json'
            )
        else:
            # Fallback to basic config if unified system unavailable
            self._config = self.DEFAULTS.copy()
            print("Warning: Using fallback configuration (unified system unavailable)")
    
    # Backward compatibility methods for existing WorldSurveyor code
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
    
    # Backward compatibility properties for existing WorldSurveyor code
    @property
    def server_port(self) -> int:
        return int(self.get('server_port', 8891))

    @property
    def debug_mode(self) -> bool:
        return bool(self.get('debug_mode', False))

    @property
    def verbose_logging(self) -> bool:
        return bool(self.get('verbose_logging', False))

    @property
    def auth_enabled(self) -> bool:
        return bool(self.get('auth_enabled', True))

    @property
    def startup_delay(self) -> float:
        return float(self.get('startup_delay', 0.1))
    @property
    def server_host(self) -> str:
        return self.get('server_host', 'localhost')
    
    @property
    def server_ports_to_try(self) -> list:
        return self.get('server_ports_to_try', [8891, 8892, 8893, 8894, 8895, 8896])
    
    @property
    def server_timeout(self) -> float:
        return self.get('server_timeout', 1.0)
    
    @property 
    def server_ready_timeout(self) -> float:
        return self.get('server_ready_timeout', 5.0)
    
    @property
    def shutdown_timeout(self) -> float:
        return self.get('shutdown_timeout', 5.0)
    
    @property
    def toolbar_cleanup_timeout(self) -> float:
        return self.get('toolbar_cleanup_timeout', 1.0)
    
    # Waypoint-specific properties
    @property
    def max_waypoints(self) -> int:
        return self.get('max_waypoints', 100)
    
    # Rate limiting properties
    @property
    def rate_limit_max_requests(self) -> int:
        return self.get('rate_limit_max_requests', 100)
    
    @property
    def rate_limit_window_seconds(self) -> int:
        return self.get('rate_limit_window_seconds', 60)
    
    # Logging properties
    @property
    def log_thread_info(self) -> bool:
        return self.get('log_thread_info', False)
    
    @property
    def log_request_details(self) -> bool:
        return self.get('log_request_details', False)
    
    # Security properties
    @property
    def cors_enabled(self) -> bool:
        return self.get('cors_enabled', True)
    
    @property
    def cors_origin(self) -> str:
        return self.get('cors_origin', '*')
    
    # Integration properties
    @property
    def worldviewer_port(self) -> int:
        return self.get('worldviewer_port', 8900)
    
    @property
    def worldviewer_host(self) -> str:
        return self.get('worldviewer_host', 'localhost')
    
    # UI properties
    @property
    def toolbar_enabled(self) -> bool:
        return self.get('toolbar_enabled', True)
    
    @property
    def hotkey_enabled(self) -> bool:
        return self.get('hotkey_enabled', True)
    
    # Waypoint positioning properties
    @property
    def waypoint_distance_min(self) -> float:
        return self.get('waypoint_distance_min', 0.1)
    
    @property
    def waypoint_distance_max(self) -> float:
        return self.get('waypoint_distance_max', 5.0)
    
    @property
    def waypoint_distance_default(self) -> float:
        return self.get('waypoint_distance_default', 1.0)
    
    @property
    def waypoint_distance_interval(self) -> float:
        return self.get('waypoint_distance_interval', 0.1)
    
    # Waypoint visualization properties
    @property
    def auto_load_waypoints(self) -> bool:
        return self.get('auto_load_waypoints', True)
    
    # Database properties
    @property
    def database_path(self):
        return self.get('database_path', None)


# Global config instance for backward compatibility
_global_config_instance = None

def get_config() -> WorldSurveyorConfig:
    """
    Get global WorldSurveyor configuration instance.
    
    Maintains backward compatibility with existing code that expects:
    from .config import get_config
    config = get_config()
    """
    global _global_config_instance
    if _global_config_instance is None:
        _global_config_instance = WorldSurveyorConfig()
    return _global_config_instance
