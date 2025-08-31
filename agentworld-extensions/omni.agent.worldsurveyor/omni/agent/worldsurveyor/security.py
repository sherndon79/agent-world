"""
Security management for WorldSurveyor API.
"""

import hashlib
import hmac
import logging
import os
import time
from collections import defaultdict, deque
from typing import Dict

import carb

from .config import get_config

logger = logging.getLogger(__name__)


class RateLimiter:
    """Simple rate limiter using sliding window."""
    
    def __init__(self, max_requests: int = 100, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests = defaultdict(deque)  # client_ip -> deque of timestamps
    
    def is_allowed(self, client_ip: str) -> bool:
        """Check if request is allowed for client."""
        now = time.time()
        client_requests = self.requests[client_ip]
        
        # Remove old requests outside the window
        while client_requests and client_requests[0] < now - self.window_seconds:
            client_requests.popleft()
        
        # Check if under limit
        if len(client_requests) < self.max_requests:
            client_requests.append(now)
            return True
        
        return False


class SecurityManager:
    """Manages authentication and rate limiting for WorldSurveyor API."""
    
    def __init__(self):
        self._config = get_config()
        self.rate_limiter = RateLimiter(
            max_requests=self._config.rate_limit_max_requests,
            window_seconds=self._config.rate_limit_window_seconds
        )
        
    def check_rate_limit(self, client_ip: str) -> bool:
        """Check if client is within rate limits."""
        return self.rate_limiter.is_allowed(client_ip)
    
    def check_auth(self, method: str, headers: Dict, path: str) -> bool:
        """Check if request is authenticated."""
        try:
            # Honor central setting toggle
            try:
                cs = carb.settings.get_settings()
                enabled = cs.get("/exts/omni.agent.worldsurveyor/auth_enabled")
                if enabled is False:
                    return True
            except Exception:
                pass
            
            # Global env override to disable auth
            if (os.getenv('AGENT_EXT_AUTH_ENABLED') or '').lower() in ('0','false','no','off'):
                return True
            
            bearer = os.getenv('AGENT_WORLDSURVEYOR_AUTH_TOKEN') or os.getenv('AGENT_EXT_AUTH_TOKEN')
            secret = os.getenv('AGENT_WORLDSURVEYOR_HMAC_SECRET') or os.getenv('AGENT_EXT_HMAC_SECRET')
            
            if not bearer and not secret:
                return True
            
            auth = headers.get('Authorization', '')
            if bearer and auth == f"Bearer {bearer}":
                return True
            
            if secret:
                ts = headers.get('X-Timestamp')
                sig = headers.get('X-Signature')
                if ts and sig:
                    try:
                        tsf = float(ts)
                        if abs(time.time() - tsf) > 60.0:
                            return False
                    except Exception:
                        return False
                    msg = f"{method}|{path}|{ts}".encode('utf-8')
                    expected = hmac.new(secret.encode('utf-8'), msg, hashlib.sha256).hexdigest()
                    if hmac.compare_digest(expected, sig):
                        return True
            
            return False
        except Exception:
            return False