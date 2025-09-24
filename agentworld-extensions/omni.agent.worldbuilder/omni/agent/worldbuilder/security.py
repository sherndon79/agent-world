"""
WorldBuilder Security Module

Authentication and security for WorldBuilder API.
Uses unified agent_world authentication system for consistency.
"""

import logging
import sys
from pathlib import Path
from typing import Optional, Dict, Any


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


# Import unified authentication system
try:
    from agentworld_core.auth import SecurityManager, is_bearer_auth_enabled
    AUTH_AVAILABLE = True
except ImportError as e:
    logging.getLogger(__name__).warning(f"Could not import unified auth system: {e}")
    AUTH_AVAILABLE = False

logger = logging.getLogger(__name__)


class WorldBuilderAuth:
    """
    Authentication handler for WorldBuilder API.
    
    Provides consistent authentication using the unified agent_world system.
    """
    
    def __init__(self, config=None):
        """
        Initialize authentication handler.
        
        Args:
            config: Extension config object for rate limiting settings
        """
        self._security_manager = None
        
        if AUTH_AVAILABLE:
            try:
                self._security_manager = SecurityManager('worldbuilder', config=config)
                logger.info("WorldBuilder authentication initialized with unified SecurityManager")
            except Exception as e:
                logger.error(f"Failed to initialize WorldBuilder authentication: {e}")
        else:
            logger.warning("WorldBuilder authentication unavailable - unified auth system not found")
    
    def is_enabled(self) -> bool:
        """
        Check if authentication is enabled.
        
        Returns:
            True if authentication is enabled and available
        """
        return AUTH_AVAILABLE and self._security_manager is not None and self._security_manager.is_auth_enabled()
    
    def validate_request(self, headers: Dict[str, str], 
                        client_ip: str = "127.0.0.1",
                        method: str = "GET", 
                        path: str = "/") -> tuple[bool, Optional[str]]:
        """
        Validate authentication for an incoming request.
        
        Args:
            headers: Request headers dictionary
            client_ip: Client IP address for rate limiting
            method: HTTP method for HMAC validation
            path: Request path for HMAC validation
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        # If auth system unavailable, deny requests
        if not AUTH_AVAILABLE or not self._security_manager:
            return False, "Authentication system unavailable"
        
        # Use SecurityManager for comprehensive validation
        try:
            return self._security_manager.validate_request(headers, client_ip, method, path)
        except Exception as e:
            logger.error(f"Authentication validation error: {e}")
            return False, "Authentication validation failed"
    
    def check_auth(self, method: str, headers: Dict[str, str], path: str) -> bool:
        """
        Legacy compatibility method for unified HTTP handler.
        
        Args:
            method: HTTP method
            headers: Request headers
            path: Request path
            
        Returns:
            True if authentication passes, False otherwise
        """
        is_valid, error_msg = self.validate_request(headers, "127.0.0.1", method, path)
        return is_valid
    
    def check_rate_limit(self, client_ip: str) -> bool:
        """
        Legacy compatibility method for unified HTTP handler rate limiting.
        
        Args:
            client_ip: Client IP address
            
        Returns:
            True if request is allowed, False if rate limited
        """
        if not AUTH_AVAILABLE or not self._security_manager:
            return True  # Allow if auth system unavailable
        
        try:
            # The unified SecurityManager handles rate limiting internally
            # For compatibility, we'll always return True since rate limiting
            # is already handled in validate_request()
            return True
        except Exception as e:
            logger.error(f"Rate limit check error: {e}")
            return True  # Allow on error to avoid blocking legitimate requests
    
    def get_auth_requirements(self) -> Dict[str, Any]:
        """
        Get authentication requirements for API documentation.
        
        Returns:
            Dict with authentication scheme information
        """
        if not self.is_enabled():
            return {
                'auth_required': False,
                'auth_scheme': None
            }
        
        # Check if Bearer auth is explicitly enabled
        bearer_enabled = AUTH_AVAILABLE and is_bearer_auth_enabled('worldbuilder')
        
        schemes = ['HMAC signature (recommended)']
        if bearer_enabled:
            schemes.append('Bearer token (testing only)')
        
        return {
            'auth_required': True,
            'auth_schemes': schemes,
            'primary_scheme': 'HMAC',
            'hmac_headers': ['X-Timestamp', 'X-Signature'],
            'bearer_enabled': bearer_enabled,
            'auth_description': 'HMAC signature authentication (preferred) or Bearer token (testing only if enabled)'
        }
    
    def get_health_status(self) -> Dict[str, Any]:
        """
        Get authentication system health status.
        
        Returns:
            Dict with auth health information
        """
        return {
            'auth_available': AUTH_AVAILABLE,
            'security_manager_initialized': self._security_manager is not None,
            'auth_functional': self.is_enabled(),
            'bearer_auth_enabled': AUTH_AVAILABLE and is_bearer_auth_enabled('worldbuilder'),
            'extension_name': 'worldbuilder'
        }
