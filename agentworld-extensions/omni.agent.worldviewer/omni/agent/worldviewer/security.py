"""
Security and rate limiting for WorldViewer API.
"""
import hashlib
import hmac
import os
import time
from collections import defaultdict, deque
from typing import Dict
from pathlib import Path
import json


class RateLimiter:
    def __init__(self, max_requests: int = 100, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests = defaultdict(deque)

    def is_allowed(self, client_ip: str) -> bool:
        now = time.time()
        dq = self.requests[client_ip]
        while dq and dq[0] < now - self.window_seconds:
            dq.popleft()
        if len(dq) < self.max_requests:
            dq.append(now)
            return True
        return False


class SecurityManager:
    def __init__(self, settings_path: str = "/exts/omni.agent.worldviewer/auth_enabled",
                 bearer_env: str = 'AGENT_WORLDVIEWER_AUTH_TOKEN',
                 hmac_env: str = 'AGENT_WORLDVIEWER_HMAC_SECRET'):
        self.settings_path = settings_path
        self.bearer_env = bearer_env
        self.hmac_env = hmac_env
        self._sec = self._load_security_config()
        rl = self._sec.get('rate_limiting', {})
        self.rate_limiter = RateLimiter(
            max_requests=int(rl.get('requests_per_minute', 60)),
            window_seconds=60
        )
        authc = self._sec.get('authentication', {})
        self.bearer_header = authc.get('bearer_token_header', 'Authorization')
        self.token_prefix = authc.get('token_prefix', 'Bearer ')

    def check_rate_limit(self, client_ip: str) -> bool:
        return self.rate_limiter.is_allowed(client_ip)

    def check_auth(self, method: str, headers: Dict, path: str) -> bool:
        try:
            if (os.getenv('AGENT_EXT_AUTH_ENABLED') or '').lower() in ('0', 'false', 'no', 'off'):
                return True
            try:
                import carb
                cs = carb.settings.get_settings()
                enabled = cs.get(self.settings_path)
                if enabled is False:
                    return True
            except Exception:
                pass
            bearer = os.getenv(self.bearer_env) or os.getenv('AGENT_EXT_AUTH_TOKEN')
            secret = os.getenv(self.hmac_env) or os.getenv('AGENT_EXT_HMAC_SECRET')
            if not bearer and not secret:
                return True
            auth = headers.get(self.bearer_header, '')
            if bearer and auth == f"{self.token_prefix}{bearer}":
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

    def _load_security_config(self) -> Dict:
        try:
            current = Path(__file__).resolve()
            for _ in range(10):
                cfg = current / 'agent-world-security.json'
                if cfg.exists():
                    return json.loads(cfg.read_text(encoding='utf-8'))
                if current.parent == current:
                    break
                current = current.parent
        except Exception:
            pass
        return {
            'global_settings': {'auth_enabled': True},
            'rate_limiting': {'requests_per_minute': 60},
            'authentication': {'bearer_token_header': 'Authorization', 'token_prefix': 'Bearer '}
        }
