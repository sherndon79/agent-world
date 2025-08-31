"""
HTTP 401 Challenge Authentication Negotiator

Implements RFC 7235 compliant authentication negotiation for MCP servers.
Automatically detects and handles HMAC authentication requirements.
"""

import os
import hashlib
import hmac
import json
import logging
from typing import Optional, Dict, Tuple, Any
from dataclasses import dataclass
import aiohttp
from urllib.parse import urljoin

logger = logging.getLogger(__name__)

@dataclass
class AuthConfig:
    """Authentication configuration detected from 401 challenges."""
    required: bool = False
    method: Optional[str] = None
    realm: Optional[str] = None
    hmac_secret: Optional[str] = None
    auth_token: Optional[str] = None

class AuthNegotiator:
    """
    Handles automatic authentication negotiation using HTTP 401 challenges.
    
    Flow:
    1. Try request without auth
    2. If 401, parse WWW-Authenticate header
    3. Retry with appropriate auth method
    4. Cache auth config for session
    """
    
    def __init__(self, service_name: str, base_url: str):
        self.service_name = service_name.upper()
        self.base_url = base_url
        self.auth_config: Optional[AuthConfig] = None
        self._session: Optional[aiohttp.ClientSession] = None
    
    async def __aenter__(self):
        """Async context manager entry."""
        self._session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self._session:
            await self._session.close()
    
    async def negotiate_auth(self) -> AuthConfig:
        """
        Negotiate authentication requirements with the service.
        
        Returns:
            AuthConfig with detected authentication requirements
        """
        if self.auth_config:
            return self.auth_config
        
        try:
            # Try a simple health check without auth first
            health_url = urljoin(self.base_url, '/health')
            
            async with self._session.get(health_url) as response:
                if response.status == 200:
                    # No auth required
                    self.auth_config = AuthConfig(required=False)
                    logger.info(f"{self.service_name}: No authentication required")
                    
                elif response.status == 401:
                    # Parse auth challenge
                    self.auth_config = self._parse_auth_challenge(response.headers)
                    logger.info(f"{self.service_name}: Auth required - {self.auth_config.method}")
                    
                else:
                    # Service might be down or other issue
                    logger.warning(f"{self.service_name}: Unexpected response {response.status}")
                    self.auth_config = AuthConfig(required=False)  # Default to no auth
                    
        except Exception as e:
            logger.error(f"{self.service_name}: Auth negotiation failed: {e}")
            # Fallback to environment variables
            self.auth_config = self._get_env_auth_config()
        
        return self.auth_config
    
    def _parse_auth_challenge(self, headers: Dict[str, str]) -> AuthConfig:
        """
        Parse WWW-Authenticate header to determine auth requirements.
        
        Expected format: 'HMAC-SHA256 realm="isaac-sim"'
        """
        www_auth = headers.get('WWW-Authenticate', '')
        
        if 'HMAC-SHA256' in www_auth:
            # Parse realm if present
            realm = None
            if 'realm=' in www_auth:
                realm_start = www_auth.find('realm="') + 7
                realm_end = www_auth.find('"', realm_start)
                if realm_end > realm_start:
                    realm = www_auth[realm_start:realm_end]
            
            # Get credentials from environment
            hmac_secret = self._get_env_var('HMAC_SECRET')
            auth_token = self._get_env_var('AUTH_TOKEN')
            
            return AuthConfig(
                required=True,
                method='HMAC-SHA256',
                realm=realm,
                hmac_secret=hmac_secret,
                auth_token=auth_token
            )
        
        # Default: assume no auth or unknown method
        return AuthConfig(required=False)
    
    def _get_env_auth_config(self) -> AuthConfig:
        """Fallback to environment variable configuration."""
        auth_enabled = os.getenv('AGENT_EXT_AUTH_ENABLED', '0') == '1'
        
        if auth_enabled:
            return AuthConfig(
                required=True,
                method='HMAC-SHA256',
                hmac_secret=self._get_env_var('HMAC_SECRET'),
                auth_token=self._get_env_var('AUTH_TOKEN')
            )
        
        return AuthConfig(required=False)
    
    def _get_env_var(self, suffix: str) -> Optional[str]:
        """
        Get environment variable with service-specific fallback.
        
        Tries:
        1. AGENT_{SERVICE}_{SUFFIX}
        2. AGENT_EXT_{SUFFIX}
        """
        service_var = f"AGENT_{self.service_name}_{suffix}"
        global_var = f"AGENT_EXT_{suffix}"
        
        return os.getenv(service_var) or os.getenv(global_var)
    
    def create_auth_headers(self, method: str, url: str, body: str = "") -> Dict[str, str]:
        """
        Create authentication headers for HMAC-SHA256.
        
        Args:
            method: HTTP method (GET, POST, etc.)
            url: Full request URL
            body: Request body (for POST requests)
            
        Returns:
            Dictionary of headers to add to request
        """
        if not self.auth_config or not self.auth_config.required:
            return {}
        
        if self.auth_config.method != 'HMAC-SHA256':
            logger.warning(f"Unsupported auth method: {self.auth_config.method}")
            return {}
        
        if not self.auth_config.hmac_secret or not self.auth_config.auth_token:
            logger.error("Missing HMAC secret or auth token")
            return {}
        
        # Create timestamp and signature for Isaac Sim HMAC format
        import time
        timestamp = str(time.time())
        signature = self._create_hmac_signature(
            method, url, timestamp,
            self.auth_config.hmac_secret,
            self.auth_config.auth_token
        )
        
        return {
            'X-Timestamp': timestamp,
            'X-Signature': signature
        }
    
    def _create_hmac_signature(self, method: str, url: str, timestamp: str, 
                              secret: str, token: str) -> str:
        """Create HMAC-SHA256 signature for request using Isaac Sim format."""
        # Isaac Sim expects: "METHOD|PATH|TIMESTAMP" format
        # Extract path from full URL
        from urllib.parse import urlparse
        parsed_url = urlparse(url)
        path = parsed_url.path
        
        string_to_sign = f"{method.upper()}|{path}|{timestamp}"
        
        signature = hmac.new(
            secret.encode('utf-8'),
            string_to_sign.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        return signature
    
    async def authenticated_request(self, method: str, endpoint: str, 
                                  **kwargs) -> aiohttp.ClientResponse:
        """
        Make an authenticated HTTP request.
        
        Args:
            method: HTTP method
            endpoint: API endpoint (relative to base_url)
            **kwargs: Additional arguments for aiohttp request
            
        Returns:
            aiohttp.ClientResponse
        """
        if not self.auth_config:
            await self.negotiate_auth()
        
        url = urljoin(self.base_url, endpoint)
        body = kwargs.get('json', {})
        body_str = json.dumps(body) if body else ""
        
        # Add auth headers
        headers = kwargs.get('headers', {})
        auth_headers = self.create_auth_headers(method.upper(), url, body_str)
        headers.update(auth_headers)
        kwargs['headers'] = headers
        
        # Make request
        return await self._session.request(method, url, **kwargs)


async def create_negotiator(service_name: str, base_url: str) -> AuthNegotiator:
    """
    Factory function to create and initialize an AuthNegotiator.
    
    Args:
        service_name: Name of the service (worldbuilder, worldviewer, etc.)
        base_url: Base URL of the service API
        
    Returns:
        Configured AuthNegotiator instance
    """
    negotiator = AuthNegotiator(service_name, base_url)
    async with negotiator:
        await negotiator.negotiate_auth()
    return negotiator