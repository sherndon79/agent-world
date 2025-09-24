"""
WorldSurveyor Configuration using Unified Agent World Config System.

This replaces the old duplicated config logic with the unified system,
eliminating code duplication while maintaining identical functionality and interface.
"""

import sys
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional


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


# Ensure shared core modules are importable before attempting imports.
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
            logging.getLogger(__name__).warning("Using fallback configuration (unified system unavailable)")

        # Load waypoint types configuration
        self._waypoint_types = self._load_waypoint_types()
    
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

    # Waypoint Types Configuration
    def _load_waypoint_types(self) -> List[Dict]:
        """Load waypoint types from external JSON configuration file."""
        logger = logging.getLogger(__name__)

        # Get the config directory relative to this file
        config_dir = Path(__file__).parent / 'config'
        waypoint_types_file = config_dir / 'waypoint_types.json'

        try:
            if waypoint_types_file.exists():
                with open(waypoint_types_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    waypoint_types = data.get('waypoint_types', [])
                    logger.info(f"Loaded {len(waypoint_types)} waypoint types from {waypoint_types_file}")
                    return waypoint_types
            else:
                logger.warning(f"Waypoint types file not found: {waypoint_types_file}")
        except Exception as e:
            logger.error(f"Error loading waypoint types from {waypoint_types_file}: {e}")

        # Fallback to hardcoded defaults
        logger.info("Using fallback hardcoded waypoint types")
        return self._get_fallback_waypoint_types()

    def _get_fallback_waypoint_types(self) -> List[Dict]:
        """Fallback waypoint types if JSON file can't be loaded."""
        return [
            {
                "id": "camera_position",
                "name": "Camera Position",
                "description": "Capture current camera view",
                "color": [0.2, 0.6, 1.0],
                "icon": "📷",
                "behavior": "camera",
                "marker_size": 20
            },
            {
                "id": "directional_lighting",
                "name": "Directional Lighting",
                "description": "Light source position and direction",
                "color": [1.0, 0.9, 0.3],
                "icon": "💡",
                "behavior": "camera",
                "marker_size": 20
            },
            {
                "id": "point_of_interest",
                "name": "Point of Interest",
                "description": "Mark interesting location",
                "color": [0.0, 0.8, 0.0],
                "icon": "📍",
                "behavior": "crosshair",
                "marker_size": 15
            },
            {
                "id": "observation_point",
                "name": "Observation Point",
                "description": "Good viewing position",
                "color": [0.8, 0.4, 0.8],
                "icon": "👁️",
                "behavior": "crosshair",
                "marker_size": 12
            },
            {
                "id": "target_location",
                "name": "Target Location",
                "description": "Goal or destination",
                "color": [1.0, 0.2, 0.2],
                "icon": "🎯",
                "behavior": "crosshair",
                "marker_size": 12
            },
            {
                "id": "walkable_area",
                "name": "Walkable Area",
                "description": "Navigable space",
                "color": [0.0, 0.8, 0.8],
                "icon": "🚶",
                "behavior": "crosshair",
                "marker_size": 12
            }
        ]

    @property
    def waypoint_types(self) -> List[Dict]:
        """Get all available waypoint types."""
        return self._waypoint_types.copy()

    def get_waypoint_type_info(self, type_id: str) -> Optional[Dict]:
        """Get information for a specific waypoint type."""
        for waypoint_type in self._waypoint_types:
            if waypoint_type["id"] == type_id:
                return waypoint_type.copy()
        return None

    def get_waypoint_behavior(self, type_id: str) -> str:
        """Get the behavior (camera/crosshair) for a waypoint type."""
        type_info = self.get_waypoint_type_info(type_id)
        return type_info.get("behavior", "crosshair") if type_info else "crosshair"

    def get_waypoint_color(self, type_id: str) -> List[float]:
        """Get the color for a waypoint type."""
        type_info = self.get_waypoint_type_info(type_id)
        return type_info.get("color", [0.5, 0.5, 0.5]) if type_info else [0.5, 0.5, 0.5]

    def get_waypoint_icon(self, type_id: str) -> str:
        """Get the icon for a waypoint type."""
        type_info = self.get_waypoint_type_info(type_id)
        return type_info.get("icon", "📍") if type_info else "📍"

    def get_waypoint_marker_size(self, type_id: str) -> int:
        """Get the marker size for a waypoint type."""
        type_info = self.get_waypoint_type_info(type_id)
        return type_info.get("marker_size", 12) if type_info else 12

    def is_valid_waypoint_type(self, type_id: str) -> bool:
        """Check if a waypoint type ID is valid."""
        return any(wtype["id"] == type_id for wtype in self._waypoint_types)

    def get_waypoint_type_ids(self) -> List[str]:
        """Get all waypoint type IDs."""
        return [wtype["id"] for wtype in self._waypoint_types]

    def get_default_waypoint_type_id(self) -> str:
        """Get the default waypoint type ID."""
        return self._waypoint_types[0]["id"] if self._waypoint_types else "point_of_interest"

    def reload_waypoint_types(self):
        """Reload waypoint types from configuration file."""
        self._waypoint_types = self._load_waypoint_types()
        logging.getLogger(__name__).info("Waypoint types configuration reloaded")


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
