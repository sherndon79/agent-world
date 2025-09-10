"""
Unified Authentication Module for agenTW∞rld Extensions.

Provides consistent authentication and security across all world* extensions with support for:
- Bearer token authentication from environment variables
- HMAC signature validation for secure requests
- Rate limiting for API protection
- Extension-specific and global token support
- Integration with .env file configuration

Usage:
    from agent_world_auth import SecurityManager, is_bearer_auth_enabled
    
    # Create security manager for extension
    security = SecurityManager('myextension', config=extension_config)
    
    # Validate request (includes both auth and rate limiting)
    valid, error = security.validate_request(headers, client_ip, method, path)
    
    # Check authentication requirements for API docs
    auth_requirements = security.get_auth_requirements()
"""

import hashlib
import hmac
import os
import time
import logging
from collections import defaultdict, deque
from pathlib import Path
from typing import Dict, Any, Optional, Tuple

logger = logging.getLogger(__name__)

# Try to import carb.settings, gracefully handle if not available
try:
    import carb.settings
    CARB_AVAILABLE = True
except ImportError:
    CARB_AVAILABLE = False
    logger.warning("carb.settings not available - Isaac Sim settings integration disabled")


class RateLimiter:
    """Rate limiting for API requests."""
    
    def __init__(self, max_requests: int = 100, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests = defaultdict(deque)

    def is_allowed(self, client_ip: str) -> bool:
        """Check if request from client IP is allowed."""
        now = time.time()
        dq = self.requests[client_ip]
        
        # Remove old requests outside the window
        while dq and dq[0] < now - self.window_seconds:
            dq.popleft()
        
        # Check if under limit
        if len(dq) < self.max_requests:
            dq.append(now)
            return True
        return False


class SecurityManager:
    """Unified security manager for all world* extensions."""
    
    def __init__(self, extension_name: str, 
                 settings_path: Optional[str] = None,
                 config: Optional[Any] = None):
        """
        Initialize security manager for extension.
        
        Args:
            extension_name: Extension name (e.g., 'worldstreamer', 'worldbuilder')
            settings_path: Isaac Sim carb settings path for auth enabled flag
            config: Extension config object to read rate limiting settings from
        """
        self.extension_name = extension_name
        self.settings_path = settings_path or f"/exts/omni.agent.{extension_name}/auth_enabled"
        
        # Load environment variables from .env file
        self._load_env_from_project_root()
        
        # Get rate limiting settings from config (with fallback defaults)
        if config:
            max_requests = getattr(config, 'rate_limit_requests_per_minute', 100)
            window_seconds = getattr(config, 'rate_limit_window_seconds', 60)
        else:
            max_requests = 100  # Fallback default
            window_seconds = 60  # Fallback default
        
        # Initialize rate limiter
        self.rate_limiter = RateLimiter(max_requests=max_requests, window_seconds=window_seconds)
        
        logger.info(f"SecurityManager initialized for {extension_name}")
    
    def _load_env_from_project_root(self):
        """Load environment variables from .env file in project root."""
        try:
            # Find agent-world directory (project root)
            current = Path(__file__).resolve()
            for _ in range(10):
                if current.name == 'agent-world':
                    env_file = current / '.env'
                    if env_file.exists():
                        self._load_env_file(env_file)
                        logger.debug(f"Loaded .env file from {env_file}")
                    break
                current = current.parent
        except Exception as e:
            logger.warning(f"Could not load .env file: {e}")
    
    def _load_env_file(self, env_file: Path):
        """Load environment variables from .env file."""
        try:
            with open(env_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        # Only set if not already in environment
                        if key.strip() not in os.environ:
                            os.environ[key.strip()] = value.strip()
        except Exception as e:
            logger.warning(f"Error reading .env file: {e}")
    
    def is_auth_enabled(self) -> bool:
        """Check if authentication is enabled for this extension."""
        # Check global disable first
        global_enabled = os.getenv('AGENT_EXT_AUTH_ENABLED', '1')
        if global_enabled.lower() in ('0', 'false', 'no', 'off'):
            return False
        
        # Check Isaac Sim carb settings if available
        if CARB_AVAILABLE:
            try:
                carb_settings = carb.settings.get_settings()
                setting_value = carb_settings.get(self.settings_path)
                if setting_value is False:
                    return False
            except Exception:
                pass
        
        return True
    
    def validate_request(self, headers: Dict[str, str], 
                        client_ip: str = "127.0.0.1",
                        method: str = "GET", 
                        path: str = "/") -> Tuple[bool, Optional[str]]:
        """
        Validate complete request including rate limiting and authentication.
        
        Default: HMAC signature authentication (secure)
        Optional: Bearer token authentication (less secure, for testing only)
        
        Args:
            headers: Request headers
            client_ip: Client IP address for rate limiting
            method: HTTP method for HMAC validation
            path: Request path for HMAC validation
        
        Returns:
            Tuple of (is_valid, error_message)
        """
        # Check rate limiting first
        if not self.rate_limiter.is_allowed(client_ip):
            return False, "Rate limit exceeded"
        
        # Check authentication if enabled
        if not self.is_auth_enabled():
            return True, None
        
        # Primary authentication: HMAC signature (secure)
        timestamp = headers.get('X-Timestamp')
        signature = headers.get('X-Signature')
        if timestamp and signature:
            if validate_hmac_signature(method, path, timestamp, signature, self.extension_name):
                return True, None
            else:
                return False, "Invalid HMAC signature"
        
        # Secondary authentication: Bearer token (only if explicitly enabled)
        if is_bearer_auth_enabled(self.extension_name):
            auth_header = headers.get('Authorization', '')
            if auth_header.startswith('Bearer '):
                if validate_auth_token(auth_header, self.extension_name):
                    logger.warning(f"Bearer token authentication used for {self.extension_name} - consider using HMAC for production")
                    return True, None
                else:
                    return False, "Invalid Bearer token"
        
        # No valid authentication found
        if timestamp or signature:
            return False, "Invalid HMAC signature - check timestamp and signature calculation"
        elif headers.get('Authorization'):
            if is_bearer_auth_enabled(self.extension_name):
                return False, "Invalid Bearer token"
            else:
                return False, "Bearer authentication disabled - use HMAC signature authentication"
        else:
            return False, "Missing authentication - provide X-Timestamp and X-Signature headers for HMAC auth"


# Standalone authentication functions
def is_auth_enabled() -> bool:
    """
    Check if authentication is globally enabled.
    
    Returns:
        True if authentication is enabled globally, False otherwise
    """
    global_enabled = os.getenv('AGENT_EXT_AUTH_ENABLED', '1')
    return global_enabled.lower() not in ('0', 'false', 'no', 'off')


def get_auth_token(extension_name: str = None) -> Optional[str]:
    """
    Get authentication token from environment variables.
    
    Args:
        extension_name: Extension name (e.g., 'worldbuilder', 'worldstreamer')
                       If None, uses global token
    
    Returns:
        Auth token string or None if not found
    """
    if extension_name:
        # Try extension-specific token first
        specific_token = os.getenv(f'AGENT_{extension_name.upper()}_AUTH_TOKEN')
        if specific_token:
            return specific_token
    
    # Fall back to global token
    return os.getenv('AGENT_EXT_AUTH_TOKEN')


def get_hmac_secret(extension_name: str = None) -> Optional[str]:
    """
    Get HMAC secret from environment variables.
    
    Args:
        extension_name: Extension name (e.g., 'worldbuilder', 'worldstreamer')
                       If None, uses global secret
    
    Returns:
        HMAC secret string or None if not found
    """
    if extension_name:
        # Try extension-specific secret first
        specific_secret = os.getenv(f'AGENT_{extension_name.upper()}_HMAC_SECRET')
        if specific_secret:
            return specific_secret
    
    # Fall back to global secret
    return os.getenv('AGENT_EXT_HMAC_SECRET')



def is_bearer_auth_enabled(extension_name: str = None) -> bool:
    """
    Check if Bearer token authentication is explicitly enabled.
    
    Bearer tokens are less secure than HMAC signatures and should only be used
    for testing/development. Production should use HMAC authentication.
    
    Args:
        extension_name: Extension name (e.g., 'worldstreamer')
                       If None, checks global setting
    
    Returns:
        True if Bearer auth is explicitly enabled, False otherwise
    """
    if extension_name:
        # Check extension-specific setting first
        specific_enabled = os.getenv(f'AGENT_{extension_name.upper()}_BEARER_AUTH_ENABLED')
        if specific_enabled is not None:
            return specific_enabled.lower() in ('1', 'true', 'yes', 'on')
    
    # Check global Bearer auth setting
    global_enabled = os.getenv('AGENT_EXT_BEARER_AUTH_ENABLED')
    if global_enabled is not None:
        return global_enabled.lower() in ('1', 'true', 'yes', 'on')
    
    # Default: Bearer auth is DISABLED (HMAC only)
    return False


def validate_auth_token(auth_header: str, extension_name: str = None) -> bool:
    """
    Validate authentication token from Authorization header.
    
    Args:
        auth_header: Authorization header value (e.g., 'Bearer token123')
        extension_name: Extension name for token lookup
    
    Returns:
        True if token is valid, False otherwise
    """
    if not is_auth_enabled():
        return True
    
    if not auth_header:
        return False
    
    # Get expected token
    expected_token = get_auth_token(extension_name)
    if not expected_token:
        # No token configured, authentication disabled
        return True
    
    # Validate Bearer token format
    if not auth_header.startswith('Bearer '):
        return False
    
    provided_token = auth_header[7:]  # Remove 'Bearer ' prefix
    
    # Secure comparison
    return hmac.compare_digest(provided_token, expected_token)


def validate_hmac_signature(method: str, path: str, timestamp: str, signature: str, extension_name: str = None) -> bool:
    """
    Validate HMAC signature for request.
    
    Args:
        method: HTTP method (GET, POST, etc.)
        path: Request path
        timestamp: Request timestamp
        signature: HMAC signature to validate
        extension_name: Extension name for secret lookup
    
    Returns:
        True if signature is valid, False otherwise
    """
    if not is_auth_enabled():
        return True
    
    # Get HMAC secret
    secret = get_hmac_secret(extension_name)
    if not secret:
        return False
    
    # Check timestamp (must be within 60 seconds)
    try:
        ts_float = float(timestamp)
        if abs(time.time() - ts_float) > 60.0:
            return False
    except (ValueError, TypeError):
        return False
    
    # Generate expected signature
    message = f"{method}|{path}|{timestamp}".encode('utf-8')
    expected_sig = hmac.new(secret.encode('utf-8'), message, hashlib.sha256).hexdigest()
    
    # Secure comparison
    return hmac.compare_digest(expected_sig, signature)

