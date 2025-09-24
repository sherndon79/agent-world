#!/usr/bin/env python3
"""Quick health/auth/rate-limit check for Agent World HTTP extensions.

Usage:
    python scripts/verify_extension_security.py [extension]

Environment variables consulted:
    - AGENT_<EXT>_BASE_URL, <EXT>_API_URL, AGENT_EXT_BASE_URL
    - AGENT_<EXT>_AUTH_TOKEN, AGENT_EXT_AUTH_TOKEN
    - AGENT_<EXT>_HMAC_SECRET, AGENT_EXT_HMAC_SECRET
    - SECURITY_TEST_RATE_LIMIT_ATTEMPTS (optional overrides, default 120)
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import sys
import time
from pathlib import Path
from typing import Dict, Optional, Tuple
from urllib import error, request

EXT_DEFAULT_PORTS: Dict[str, int] = {
    "worldbuilder": 8899,
    "worldviewer": 8900,
    "worldsurveyor": 8891,
    "worldrecorder": 8892,
    "worldstreamer": 8906,
}


def load_credentials_from_dotenv(extension: str) -> set[str]:
    """Populate required auth values from .env if they are not already exported."""
    env_path = Path(__file__).resolve().parents[1] / ".env"
    if not env_path.exists():
        return set()

    values: Dict[str, str] = {}
    try:
        with env_path.open("r", encoding="utf-8") as handle:
            for raw_line in handle:
                line = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, val = line.split("=", 1)
                values[key.strip()] = val.strip()
    except OSError as exc:
        print(f"⚠️  Unable to read {env_path}: {exc}")
        return set()

    targets = {
        f"AGENT_{extension.upper()}_AUTH_TOKEN",
        f"AGENT_{extension.upper()}_HMAC_SECRET",
        "AGENT_EXT_AUTH_TOKEN",
        "AGENT_EXT_HMAC_SECRET",
    }

    added: set[str] = set()
    for key in targets:
        if key in os.environ:
            continue
        if key in values:
            os.environ[key] = values[key]
            added.add(key)
    return added


def cleanup_env(keys: set[str]) -> None:
    for key in keys:
        os.environ.pop(key, None)


def resolve_extension() -> str:
    if len(sys.argv) > 1:
        return sys.argv[1].strip().lower()
    return os.getenv("AW_EXTENSION", "worldbuilder").strip().lower()


def env_lookup(extension: str, suffix: str) -> Optional[str]:
    ext_upper = extension.upper()
    candidates = [
        f"AGENT_{ext_upper}_{suffix}",
        f"AGENT_EXT_{suffix}",
        f"{ext_upper}_{suffix}",
    ]
    for key in candidates:
        value = os.getenv(key)
        if value:
            return value
    return None


def resolve_base_url(extension: str) -> str:
    ext_upper = extension.upper()
    candidates = [
        f"AGENT_{ext_upper}_BASE_URL",
        f"{ext_upper}_API_URL",
        "AGENT_EXT_BASE_URL",
    ]

    for key in candidates:
        value = os.getenv(key)
        if value:
            return value.rstrip("/")

    port = EXT_DEFAULT_PORTS.get(extension, 8899)
    return f"http://localhost:{port}"


def build_auth_headers(extension: str, method: str, path: str, *, use_auth: bool) -> Dict[str, str]:
    if not use_auth:
        return {}

    headers: Dict[str, str] = {}
    auth_token = env_lookup(extension, "AUTH_TOKEN")
    secret = env_lookup(extension, "HMAC_SECRET")

    timestamp = None
    signature = None

    if secret:
        timestamp = str(time.time())
        sign_target = f"{method.upper()}|{path}|{timestamp}".encode("utf-8")
        signature = hmac.new(secret.encode("utf-8"), sign_target, hashlib.sha256).hexdigest()
        headers["X-Timestamp"] = timestamp
        headers["X-Signature"] = signature

    if auth_token:
        headers["Authorization"] = f"Bearer {auth_token}"

    if not headers:
        raise RuntimeError(
            "No authentication credentials found; set AGENT_<EXT>_HMAC_SECRET and/or AGENT_<EXT>_AUTH_TOKEN."
        )

    return headers


def send_request(base_url: str, path: str, *, method: str = "GET", headers: Optional[Dict[str, str]] = None) -> Tuple[int, str]:
    url = f"{base_url}{path}"
    req = request.Request(url, method=method, headers=headers or {})
    try:
        with request.urlopen(req, timeout=10) as resp:
            return resp.getcode(), resp.read().decode("utf-8", errors="replace")
    except error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        return exc.code, body
    except error.URLError as exc:
        raise SystemExit(f"Failed to reach {url}: {exc}")


def pretty_print(label: str, status: int, body: str) -> None:
    try:
        parsed = json.loads(body)
        body_summary = json.dumps(parsed, indent=2)[:400]
    except json.JSONDecodeError:
        body_summary = body[:400]

    print(f"\n[{label}] status={status}\n{body_summary}\n")


def expect_status(label: str, actual: int, expected: int) -> None:
    if actual != expected:
        print(f"⚠️  Unexpected status for {label}: expected {expected}, got {actual}")
    else:
        print(f"✅ {label} returned {expected}")


def main() -> int:
    extension = resolve_extension()
    base_url = resolve_base_url(extension)

    print(f"Testing extension='{extension}' at base_url='{base_url}'")

    cleanup_keys = load_credentials_from_dotenv(extension)

    try:
        auth_headers = build_auth_headers(extension, "GET", "/health", use_auth=True)
    except RuntimeError as err:
        print(f"⚠️  {err}")
        cleanup_env(cleanup_keys)
        return 1

    # Happy path health check
    status, body = send_request(base_url, "/health", method="GET", headers=auth_headers)
    pretty_print("authorized /health", status, body)
    expect_status("Authorized health", status, 200)

    # Unauthorized check
    status, body = send_request(base_url, "/health", method="GET", headers={})
    pretty_print("unauthorized /health", status, body)
    expect_status("Unauthorized health", status, 401)

    # Rate limit burst
    attempts = int(os.getenv("SECURITY_TEST_RATE_LIMIT_ATTEMPTS", "120"))
    burst_path = "/metrics"
    first_failure = None
    for attempt in range(1, attempts + 1):
        headers = build_auth_headers(extension, "GET", burst_path, use_auth=True)
        status, _ = send_request(base_url, burst_path, method="GET", headers=headers)
        if status == 429:
            first_failure = attempt
            break
        if status >= 400:
            print(f"⚠️  Unexpected status {status} during rate limit burst at attempt {attempt}")
            break
        time.sleep(0.05)

    if first_failure:
        print(f"✅ Rate limit triggered after {first_failure} authenticated requests to {burst_path}")
    else:
        print("⚠️  Rate limit did not trigger; consider increasing SECURITY_TEST_RATE_LIMIT_ATTEMPTS or checking config")

    cleanup_env(cleanup_keys)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
