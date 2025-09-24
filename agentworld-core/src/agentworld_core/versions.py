"""
Centralized version management for agenTW∞rld Extensions.

Provides consistent versioning across all world* extensions with support for:
- Default versions with per-extension overrides
- API version tracking separate from extension versions
- Service name consistency
- Environment variable overrides for CI/CD

Usage:
    from agentworld_core.versions import get_version, get_service_name
    
    version = get_version('worldbuilder')
    service = get_service_name('worldviewer')
"""

import json
import os
import logging
from pathlib import Path
from typing import Dict, Optional, Any

# Cache for version config to avoid repeated file reads
_version_config_cache: Optional[Dict[str, Any]] = None
logger = logging.getLogger(__name__)
_config_file_path = Path(__file__).parent / "agent-world-versions.json"


def _load_version_config() -> Dict[str, Any]:
    """Load version configuration with caching."""
    global _version_config_cache
    
    if _version_config_cache is None:
        try:
            with open(_config_file_path, 'r') as f:
                _version_config_cache = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            # Fallback to default configuration
            _version_config_cache = {
                "default_version": "0.1.0",
                "suite_version": "1.0.0-alpha",
                "extensions": {}
            }
            logger.warning(f"Could not load version config ({e}), using defaults")
    
    return _version_config_cache


def get_version(extension_name: str, version_type: str = "version") -> str:
    """
    Get version for a specific extension.
    
    Args:
        extension_name: Name of extension (e.g., 'worldbuilder', 'worldviewer')
        version_type: Type of version ('version', 'api_version')
    
    Returns:
        Version string, with environment override support
    
    Environment Variables:
        AGENT_WORLD_VERSION: Override for all extensions
        AGENT_WORLD_{EXTENSION}_VERSION: Override for specific extension
    """
    # Check environment overrides first
    env_override = os.getenv(f"AGENT_WORLD_{extension_name.upper()}_VERSION")
    if env_override:
        return env_override
    
    global_override = os.getenv("AGENT_WORLD_VERSION")
    if global_override:
        return global_override
    
    # Load configuration
    config = _load_version_config()
    
    # Get extension-specific version or fallback to default
    extension_config = config.get("extensions", {}).get(extension_name, {})
    version = extension_config.get(version_type, config.get("default_version", "0.1.0"))
    
    return version


def get_service_name(extension_name: str) -> str:
    """
    Get service name for a specific extension.
    
    Args:
        extension_name: Name of extension
        
    Returns:
        Service name string
    """
    # Check environment override
    env_override = os.getenv(f"AGENT_WORLD_{extension_name.upper()}_SERVICE")
    if env_override:
        return env_override
    
    config = _load_version_config()
    extension_config = config.get("extensions", {}).get(extension_name, {})
    
    return extension_config.get(
        "service_name", 
        f"Agent {extension_name.title()} API"
    )


def get_suite_version() -> str:
    """Get the overall Agent World suite version."""
    env_override = os.getenv("AGENT_WORLD_SUITE_VERSION")
    if env_override:
        return env_override
        
    config = _load_version_config()
    return config.get("suite_version", "1.0.0-alpha")


def get_all_extension_info() -> Dict[str, Dict[str, str]]:
    """Get version info for all extensions."""
    config = _load_version_config()
    result = {}
    
    for ext_name, ext_config in config.get("extensions", {}).items():
        result[ext_name] = {
            "version": get_version(ext_name, "version"),
            "api_version": get_version(ext_name, "api_version"), 
            "service_name": get_service_name(ext_name)
        }
    
    return result


def refresh_config():
    """Force reload of version configuration (useful for testing)."""
    global _version_config_cache
    _version_config_cache = None


# Convenience exports
def worldbuilder_version() -> str:
    return get_version("worldbuilder")

def worldviewer_version() -> str:
    return get_version("worldviewer")

def worldsurveyor_version() -> str:
    return get_version("worldsurveyor")

def worldrecorder_version() -> str:
    return get_version("worldrecorder")


if __name__ == "__main__":
    # CLI utility for version checking
    import sys
    logging.basicConfig(level=logging.INFO)
    
    if len(sys.argv) > 1:
        extension = sys.argv[1]
        logger.info(f"{extension}: {get_version(extension)}")
        logger.info(f"Service: {get_service_name(extension)}")
    else:
        logger.info("agenTW∞rld Extensions Version Info:")
        logger.info(f"Suite Version: {get_suite_version()}")
        
        for name, info in get_all_extension_info().items():
            logger.info(f"{name}:")
            logger.info(f"  Version: {info['version']}")
            logger.info(f"  API Version: {info['api_version']}")
            logger.info(f"  Service: {info['service_name']}")
