"""
Base MCP Client with Automatic Authentication

Provides a base class for MCP servers that need to communicate with
Isaac Sim extensions using automatic auth negotiation.
"""

import asyncio
import logging
from typing import Dict, Any, Optional
import aiohttp
from urllib.parse import urljoin

from auth_negotiator import AuthNegotiator

logger = logging.getLogger(__name__)

class MCPBaseClient:
    """
    Base client for MCP servers with automatic authentication.
    
    Handles:
    - Automatic auth negotiation on startup
    - Authenticated HTTP requests
    - Error handling and retries
    - Connection management
    """
    
    def __init__(self, service_name: str, base_url: str):
        self.service_name = service_name
        self.base_url = base_url
        self.auth_negotiator: Optional[AuthNegotiator] = None
        self._session: Optional[aiohttp.ClientSession] = None
        self._initialized = False
    
    async def initialize(self):
        """Initialize the client and negotiate authentication."""
        if self._initialized:
            return
        
        self._session = aiohttp.ClientSession()
        
        # Initialize auth negotiator
        self.auth_negotiator = AuthNegotiator(self.service_name, self.base_url)
        self.auth_negotiator._session = self._session  # Share session
        
        # Negotiate auth requirements
        auth_config = await self.auth_negotiator.negotiate_auth()
        
        if auth_config.required:
            logger.info(f"{self.service_name}: Using {auth_config.method} authentication")
        else:
            logger.info(f"{self.service_name}: No authentication required")
        
        self._initialized = True
    
    async def close(self):
        """Close the client and cleanup resources."""
        if self._session:
            await self._session.close()
            self._session = None
        self._initialized = False
    
    async def __aenter__(self):
        """Async context manager entry."""
        await self.initialize()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()
    
    async def get(self, endpoint: str, **kwargs) -> Dict[str, Any]:
        """Make authenticated GET request."""
        return await self._request('GET', endpoint, **kwargs)
    
    async def post(self, endpoint: str, **kwargs) -> Dict[str, Any]:
        """Make authenticated POST request."""
        return await self._request('POST', endpoint, **kwargs)
    
    async def put(self, endpoint: str, **kwargs) -> Dict[str, Any]:
        """Make authenticated PUT request."""
        return await self._request('PUT', endpoint, **kwargs)
    
    async def delete(self, endpoint: str, **kwargs) -> Dict[str, Any]:
        """Make authenticated DELETE request."""
        return await self._request('DELETE', endpoint, **kwargs)
    
    async def _request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        """
        Make an authenticated HTTP request with error handling.
        
        Args:
            method: HTTP method
            endpoint: API endpoint
            **kwargs: Additional request arguments
            
        Returns:
            JSON response data
            
        Raises:
            aiohttp.ClientError: On HTTP errors
            ValueError: On invalid JSON response
        """
        if not self._initialized:
            await self.initialize()
        
        try:
            async with await self.auth_negotiator.authenticated_request(
                method, endpoint, **kwargs
            ) as response:
                
                # Handle auth challenges on individual requests
                if response.status == 401:
                    logger.info(f"{self.service_name}: Re-negotiating authentication")
                    # Reset auth config to force re-negotiation
                    self.auth_negotiator.auth_config = None
                    await self.auth_negotiator.negotiate_auth()
                    
                    # Retry request with new auth
                    async with await self.auth_negotiator.authenticated_request(
                        method, endpoint, **kwargs
                    ) as retry_response:
                        return await self._parse_response(retry_response)
                
                return await self._parse_response(response)
                
        except aiohttp.ClientError as e:
            logger.error(f"{self.service_name}: Request failed: {e}")
            raise
        except Exception as e:
            logger.error(f"{self.service_name}: Unexpected error: {e}")
            raise
    
    async def _parse_response(self, response: aiohttp.ClientResponse) -> Dict[str, Any]:
        """Parse HTTP response to JSON."""
        response.raise_for_status()
        
        try:
            return await response.json()
        except ValueError as e:
            logger.error(f"{self.service_name}: Invalid JSON response: {e}")
            # Return text response as fallback
            text = await response.text()
            return {"raw_response": text, "status": response.status}
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform health check on the service."""
        try:
            return await self.get('/health')
        except Exception as e:
            return {
                "healthy": False,
                "error": str(e),
                "service": self.service_name
            }
    
    def is_authenticated(self) -> bool:
        """Check if client is configured for authentication."""
        return (
            self.auth_negotiator and 
            self.auth_negotiator.auth_config and 
            self.auth_negotiator.auth_config.required
        )
    
    def get_auth_info(self) -> Dict[str, Any]:
        """Get current authentication configuration info."""
        if not self.auth_negotiator or not self.auth_negotiator.auth_config:
            return {"auth_required": False}
        
        config = self.auth_negotiator.auth_config
        return {
            "auth_required": config.required,
            "auth_method": config.method,
            "realm": config.realm,
            "has_credentials": bool(config.hmac_secret and config.auth_token)
        }
