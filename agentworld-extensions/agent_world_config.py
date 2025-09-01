"""
Unified configuration management for Agent World Extensions.

Provides consistent configuration loading across all world* extensions with support for:
- JSON configuration files with comment support
- Isaac Sim carb.settings integration
- Environment variable overrides
- Hierarchical configuration precedence: Environment > Carb Settings > JSON > Defaults

Usage:
    from agent_world_config import WorldExtensionConfig
    
    class MyExtensionConfig(WorldExtensionConfig):
        DEFAULTS = {
            'server_port': 8891,
            'debug_mode': False,
            'my_custom_setting': 'default_value'
        }
        
        def __init__(self):
            super().__init__(
                extension_name='myextension',
                config_file='myextension_config.json'
            )
"""

import json
import os
import logging
from pathlib import Path
from typing import Dict, Any, Optional, Union

logger = logging.getLogger(__name__)

# Try to import carb.settings, gracefully handle if not available
try:
    import carb.settings
    CARB_AVAILABLE = True
except ImportError:
    CARB_AVAILABLE = False
    logger.warning("carb.settings not available - Isaac Sim settings integration disabled")


class WorldExtensionConfig:
    """
    Base configuration class for all World* extensions.
    
    Implements hierarchical configuration loading:
    1. Defaults (defined by subclass)
    2. JSON config file 
    3. Isaac Sim carb.settings
    4. Environment variables (highest priority)
    """
    
    # Subclasses must define their defaults
    DEFAULTS: Dict[str, Any] = {}
    
    def __init__(self, extension_name: str, config_file: Optional[str] = None):
        """
        Initialize unified configuration system.
        
        Args:
            extension_name: Name of extension (e.g., 'worldbuilder', 'worldviewer')
            config_file: Optional path to JSON config file (relative to extension directory)
        """
        self.extension_name = extension_name
        self._config: Dict[str, Any] = {}
        self._config_file = config_file
        self._extension_path = self._find_extension_path()
        
        # Load configuration in priority order
        self._load_configuration()
    
    def _find_extension_path(self) -> Optional[Path]:
        """Find the extension directory path."""
        try:
            # Start from current file and search up for extension directory
            current = Path(__file__).resolve().parent
            extension_dir_name = f"omni.agent.{self.extension_name}"
            
            # Search in current directory and parent directories
            for _ in range(5):  # Reasonable search limit
                extension_path = current / extension_dir_name
                if extension_path.exists():
                    return extension_path / "omni" / "agent" / self.extension_name
                current = current.parent
            
            logger.warning(f"Could not find extension directory for {self.extension_name}")
            return None
        except Exception as e:
            logger.warning(f"Error finding extension path: {e}")
            return None
    
    def _load_configuration(self):
        """Load configuration from all sources in priority order."""
        # Start with defaults
        if not self.DEFAULTS:
            logger.warning(f"{self.__class__.__name__} has no DEFAULTS defined")
        self._config = self.DEFAULTS.copy()
        
        # Load from JSON config file
        self._load_from_json_config()
        
        # Load from Isaac Sim settings (carb.settings)
        self._load_from_carb_settings()
        
        # Load from environment variables (highest priority)
        self._load_from_environment()
        
        # Validate configuration
        self._validate_config()
        
        if self.debug_mode:
            logger.info(f"{self.extension_name} configuration loaded successfully")
    
    def _load_from_json_config(self):
        """Load configuration from JSON config file."""
        if not self._config_file:
            return
        
        # Try monolithic config first, then extension-specific config
        isaac_extension_root = Path(__file__).parent
        monolithic_config_path = isaac_extension_root / "agent-world-config.json"
        extension_config_path = self._extension_path / self._config_file if self._extension_path else None
        
        config_path = None
        if monolithic_config_path.exists():
            config_path = monolithic_config_path
            logger.debug(f"Using monolithic config: {config_path}")
        elif extension_config_path and extension_config_path.exists():
            config_path = extension_config_path
            logger.debug(f"Using extension-specific config: {config_path}")
        else:
            logger.debug(f"No config file found (tried {monolithic_config_path} and {extension_config_path})")
            return
        
        try:
            with open(config_path, 'r') as f:
                json_config = json.load(f)
            
            # Handle both monolithic and extension-specific config files
            if self.extension_name in json_config:
                # Monolithic config - use extension-specific section
                extension_config = json_config[self.extension_name]
                logger.debug(f"Using {self.extension_name} section from monolithic config")
            else:
                # Extension-specific config - use entire file
                extension_config = json_config
                logger.debug(f"Using extension-specific config file")
            
            # Filter out comment keys (starting with _)
            filtered_config = {
                k: v for k, v in extension_config.items() 
                if not k.startswith('_')
            }
            
            # Update configuration with JSON values
            self._config.update(filtered_config)
            logger.debug(f"Loaded JSON config from {config_path}")
            
        except (json.JSONDecodeError, IOError) as e:
            logger.warning(f"Failed to load JSON config from {config_path}: {e}")
    
    def _load_from_carb_settings(self):
        """Load configuration from Isaac Sim carb.settings."""
        if not CARB_AVAILABLE:
            return
        
        try:
            cs = carb.settings.get_settings()
            settings_path = f"/exts/omni.agent.{self.extension_name}"
            
            # Get all settings under the extension path
            for key in self._config.keys():
                setting_key = f"{settings_path}/{key}"
                value = cs.get(setting_key)
                if value is not None:
                    self._config[key] = value
                    logger.debug(f"Loaded carb setting: {setting_key} = {value}")
        
        except Exception as e:
            logger.warning(f"Failed to load carb settings: {e}")
    
    def _load_from_environment(self):
        """Load configuration from environment variables."""
        env_prefix = f"{self.extension_name.upper()}_"
        
        for key in self._config.keys():
            env_key = f"{env_prefix}{key.upper()}"
            env_value = os.getenv(env_key)
            
            if env_value is not None:
                # Convert string environment values to appropriate types
                converted_value = self._convert_env_value(env_value, self._config[key])
                self._config[key] = converted_value
                logger.debug(f"Loaded environment variable: {env_key} = {converted_value}")
    
    def _convert_env_value(self, env_value: str, default_value: Any) -> Any:
        """Convert environment variable string to appropriate type."""
        if isinstance(default_value, bool):
            return env_value.lower() in ('true', '1', 'yes', 'on')
        elif isinstance(default_value, int):
            try:
                return int(env_value)
            except ValueError:
                logger.warning(f"Invalid integer value in environment: {env_value}")
                return default_value
        elif isinstance(default_value, float):
            try:
                return float(env_value)
            except ValueError:
                logger.warning(f"Invalid float value in environment: {env_value}")
                return default_value
        elif isinstance(default_value, list):
            # Support comma-separated lists
            return [item.strip() for item in env_value.split(',')]
        else:
            return env_value  # Keep as string
    
    def _validate_config(self):
        """Validate configuration values. Override in subclasses for custom validation."""
        # Port validation
        if 'server_port' in self._config:
            port = self._config['server_port']
            if not isinstance(port, int) or port < 1024 or port > 65535:
                logger.warning(f"Invalid port {port}, using 8900")
                self._config['server_port'] = 8900
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value."""
        return self._config.get(key, default)
    
    def set(self, key: str, value: Any):
        """Set configuration value (runtime only)."""
        self._config[key] = value
    
    def get_all(self) -> Dict[str, Any]:
        """Get all configuration values."""
        return self._config.copy()
    
    def reload(self):
        """Reload configuration from all sources."""
        self._load_configuration()
    
    # Property access for common settings
    @property
    def server_port(self) -> int:
        return self._config.get('server_port', 8900)
    
    @property
    def debug_mode(self) -> bool:
        return self._config.get('debug_mode', False)
    
    @property
    def verbose_logging(self) -> bool:
        return self._config.get('verbose_logging', False)
    
    @property
    def auth_enabled(self) -> bool:
        return self._config.get('auth_enabled', True)
    
    @property
    def startup_delay(self) -> float:
        """Common startup delay property needed by extensions."""
        return self._config.get('startup_delay', 0.1)
    
    @property
    def server_host(self) -> str:
        """Common server host property."""
        return self._config.get('server_host', 'localhost')
    
    def get_server_url(self, port: int = None) -> str:
        """Get server URL - common method needed by extensions."""
        port = port or self.server_port
        return f"http://{self.server_host}:{port}"
    
    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}({self.extension_name}): {len(self._config)} settings>"


# Convenience factory functions for each extension
def create_worldbuilder_config() -> WorldExtensionConfig:
    """Create WorldBuilder configuration instance."""
    from types import SimpleNamespace
    
    class WorldBuilderConfig(WorldExtensionConfig):
        DEFAULTS = {
            'server_port': 8899,
            'debug_mode': False,
            'verbose_logging': False,
            'auth_enabled': True,
            'enable_batch_operations': True,
            'max_elements_per_batch': 100,
            'auto_save_scene': False
        }
    
    return WorldBuilderConfig('worldbuilder', 'worldbuilder_config.json')


def create_worldviewer_config() -> WorldExtensionConfig:
    """Create WorldViewer configuration instance."""
    class WorldViewerConfig(WorldExtensionConfig):
        DEFAULTS = {
            'server_port': 8900,
            'debug_mode': False,
            'verbose_logging': False,
            'auth_enabled': True,
            'enable_cinematic_mode': True,
            'default_movement_duration': 3.0,
            'max_movement_duration': 60.0
        }
    
    return WorldViewerConfig('worldviewer', 'worldviewer_config.json')


def create_worldsurveyor_config() -> WorldExtensionConfig:
    """Create WorldSurveyor configuration instance."""
    class WorldSurveyorConfig(WorldExtensionConfig):
        DEFAULTS = {
            'server_port': 8891,
            'debug_mode': False,
            'verbose_logging': False,
            'auth_enabled': True,
            'enable_waypoint_persistence': True,
            'waypoint_marker_scale': 1.0,
            'auto_save_waypoints': True
        }
    
    return WorldSurveyorConfig('worldsurveyor', 'worldsurveyor_config.json')


def create_worldrecorder_config() -> WorldExtensionConfig:
    """Create WorldRecorder configuration instance."""
    class WorldRecorderConfig(WorldExtensionConfig):
        DEFAULTS = {
            'server_port': 8892,
            'debug_mode': False,
            'verbose_logging': False,
            'auth_enabled': True,
            'default_fps': 24,
            'max_recording_duration': 300,  # 5 minutes
            'output_directory': '/tmp/recordings'
        }
    
    return WorldRecorderConfig('worldrecorder', 'worldrecorder_config.json')


if __name__ == "__main__":
    # CLI utility for configuration testing
    import sys
    logging.basicConfig(level=logging.INFO)
    
    if len(sys.argv) > 1:
        extension_name = sys.argv[1]
        
        # Create config instance
        factory_map = {
            'worldbuilder': create_worldbuilder_config,
            'worldviewer': create_worldviewer_config,
            'worldsurveyor': create_worldsurveyor_config,
            'worldrecorder': create_worldrecorder_config
        }
        
        if extension_name in factory_map:
            config = factory_map[extension_name]()
            logger.info(f"{extension_name} Configuration:")
            for key, value in config.get_all().items():
                logger.info(f"  {key}: {value}")
        else:
            logger.error(f"Unknown extension: {extension_name}")
            logger.info(f"Available: {list(factory_map.keys())}")
    else:
        logger.info("Agent World Extensions Configuration")
        logger.info("Usage: python agent_world_config.py <extension_name>")
        logger.info("Extensions: worldbuilder, worldviewer, worldsurveyor, worldrecorder")
