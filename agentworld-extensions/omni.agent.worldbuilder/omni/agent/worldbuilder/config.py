"""
WorldBuilder Configuration using Unified Agent World Config System.

This replaces the old duplicated config logic with the unified system,
eliminating code duplication while maintaining identical functionality and interface.
"""

import logging

# Import the unified config system from agentworld-extensions root
try:
    from agent_world_config import WorldExtensionConfig
    CONFIG_AVAILABLE = True
except ImportError as e:
    logging.getLogger(__name__).warning(f"Could not import unified config system: {e}")
    CONFIG_AVAILABLE = False


class WorldBuilderConfig(WorldExtensionConfig if CONFIG_AVAILABLE else object):
    """
    WorldBuilder configuration using unified Agent World config system.
    
    Maintains exact same interface as old WorldBuilderConfig while eliminating
    all the duplicated configuration loading logic.
    """
    
    # WorldBuilder-specific configuration defaults
    DEFAULTS = {
        # Server configuration  
        'server_port': 8899,
        'server_host': 'localhost',
        'server_ports_to_try': [8899, 8898, 8897, 8896, 8895],
        'server_timeout': 1.0,
        'server_ready_timeout': 5.0,
        
        # General settings
        'debug_mode': False,
        'verbose_logging': False,
        'log_request_details': False,
        'auth_enabled': True,
        
        # Asset limits
        'max_scene_elements': 1000,
        'max_element_name_length': 100,
        'max_batch_size': 100,
        'max_asset_file_size': 104857600,  # 100MB
        'max_completed_requests': 100,
        'max_operations_per_cycle': 5,
        
        # Feature flags
        'enable_batch_operations': True,
        'enable_asset_validation': True,
        'enable_scene_persistence': False,
        'enable_real_time_updates': True,
        'enable_debug_visualization': False,
        'enable_performance_monitoring': True,
        
        # Performance settings
        'scene_update_interval': 0.1,
        'batch_processing_delay': 0.05,
        'asset_loading_timeout': 30.0,
        'scene_validation_interval': 5.0,
        'startup_delay': 0.1,  # Extension startup delay
        'shutdown_timeout': 5.0,  # Extension shutdown timeout
        
        # Asset management
        'auto_save_scene': False,
        'scene_backup_enabled': False,
        'asset_cache_size': 50,
        'texture_quality': 'medium',
        
        # Spatial settings
        'default_element_scale': [1.0, 1.0, 1.0],
        'default_element_color': [0.5, 0.5, 0.5],
        'world_bounds_min': [-100.0, -100.0, -100.0],
        'world_bounds_max': [100.0, 100.0, 100.0],
        
        # USD settings
        'usd_stage_units': 'meters',
        'usd_up_axis': 'Y',
        'usd_linear_units': 1.0,
        'usd_time_codes_per_second': 24.0
    }
    
    def __init__(self, config_file: str = None):
        """Initialize WorldBuilder configuration."""
        if CONFIG_AVAILABLE:
            # Use unified config system
            super().__init__(
                extension_name='worldbuilder',
                config_file=config_file or 'worldbuilder_config.json'
            )
        else:
            # Fallback to basic config if unified system unavailable
            self._config = self.DEFAULTS.copy()
            logging.getLogger(__name__).warning("Using fallback configuration (unified system unavailable)")
    
    # Backward compatibility methods for existing WorldBuilder code
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
    
    # Backward compatibility properties for existing WorldBuilder code
    @property
    def server_host(self) -> str:
        return self.get('server_host', 'localhost')
    
    @property
    def server_ports_to_try(self) -> list:
        return self.get('server_ports_to_try', [8899, 8898, 8897, 8896, 8895])
    
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
    def max_scene_elements(self) -> int:
        return self.get('max_scene_elements', 1000)
    
    @property
    def max_element_name_length(self) -> int:
        return self.get('max_element_name_length', 100)
    
    @property
    def max_batch_size(self) -> int:
        return self.get('max_batch_size', 100)
    
    @property
    def max_asset_file_size(self) -> int:
        return self.get('max_asset_file_size', 104857600)
    
    @property
    def max_completed_requests(self) -> int:
        return self.get('max_completed_requests', 100)
    
    @property
    def max_operations_per_cycle(self) -> int:
        return self.get('max_operations_per_cycle', 5)
    
    @property
    def enable_batch_operations(self) -> bool:
        return self.get('enable_batch_operations', True)
    
    @property
    def enable_asset_validation(self) -> bool:
        return self.get('enable_asset_validation', True)
    
    @property
    def enable_scene_persistence(self) -> bool:
        return self.get('enable_scene_persistence', False)
    
    @property
    def enable_real_time_updates(self) -> bool:
        return self.get('enable_real_time_updates', True)
    
    @property
    def enable_debug_visualization(self) -> bool:
        return self.get('enable_debug_visualization', False)
    
    @property
    def enable_performance_monitoring(self) -> bool:
        return self.get('enable_performance_monitoring', True)
    
    @property
    def scene_update_interval(self) -> float:
        return self.get('scene_update_interval', 0.1)
    
    @property
    def batch_processing_delay(self) -> float:
        return self.get('batch_processing_delay', 0.05)
    
    @property
    def asset_loading_timeout(self) -> float:
        return self.get('asset_loading_timeout', 30.0)
    
    @property
    def scene_validation_interval(self) -> float:
        return self.get('scene_validation_interval', 5.0)
    
    @property
    def auto_save_scene(self) -> bool:
        return self.get('auto_save_scene', False)
    
    @property
    def scene_backup_enabled(self) -> bool:
        return self.get('scene_backup_enabled', False)
    
    @property
    def asset_cache_size(self) -> int:
        return self.get('asset_cache_size', 50)
    
    @property
    def texture_quality(self) -> str:
        return self.get('texture_quality', 'medium')
    
    @property
    def default_element_scale(self) -> list:
        return self.get('default_element_scale', [1.0, 1.0, 1.0])
    
    @property
    def default_element_color(self) -> list:
        return self.get('default_element_color', [0.5, 0.5, 0.5])
    
    @property
    def world_bounds_min(self) -> list:
        return self.get('world_bounds_min', [-100.0, -100.0, -100.0])
    
    @property
    def world_bounds_max(self) -> list:
        return self.get('world_bounds_max', [100.0, 100.0, 100.0])
    
    @property
    def usd_stage_units(self) -> str:
        return self.get('usd_stage_units', 'meters')
    
    @property
    def usd_up_axis(self) -> str:
        return self.get('usd_up_axis', 'Y')
    
    @property
    def usd_linear_units(self) -> float:
        return self.get('usd_linear_units', 1.0)
    
    @property
    def usd_time_codes_per_second(self) -> float:
        return self.get('usd_time_codes_per_second', 24.0)
    
    @property
    def log_request_details(self) -> bool:
        return self.get('log_request_details', False)
    
    # startup_delay, server_host, and get_server_url are now provided by unified base class


# Global config instance for backward compatibility
_global_config_instance = None

def get_config() -> WorldBuilderConfig:
    """
    Get global WorldBuilder configuration instance.
    
    Maintains backward compatibility with existing code that expects:
    from .config import get_config
    config = get_config()
    """
    global _global_config_instance
    if _global_config_instance is None:
        _global_config_instance = WorldBuilderConfig()
    return _global_config_instance
