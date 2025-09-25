#!/usr/bin/env python3
"""
Run OpenAPI parity checks for all MCP servers in one go.

Usage:
  python check_all_openapi_parity.py [--fail-on-extra-openapi]

Environment overrides (optional):
  WORLDSURVEYOR_API_URL   (default http://localhost:8891)
  WORLDBUILDER_API_URL    (default http://localhost:8899)
  WORLDVIEWER_API_URL     (default http://localhost:8900)
  WORLDRECORDER_API_URL   (default http://localhost:8901)
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path


def build_openapi_url(env_var: str, default_base: str) -> str:
    base = os.getenv(env_var, default_base).rstrip('/')
    return f"{base}/openapi.json"


def main() -> int:
    ap = argparse.ArgumentParser(description="Run OpenAPI parity checks for all MCP servers")
    ap.add_argument('--fail-on-extra-openapi', action='store_true', help='Fail if OpenAPI has endpoints unused by MCP')
    args = ap.parse_args()

    tools_dir = Path(__file__).parent
    mcp_root = tools_dir.parent  # mcp-servers/

    checker = tools_dir / 'openapi_parity_check.py'
    if not checker.exists():
        print(f"ERROR: parity checker not found at {checker}", file=sys.stderr)
        return 2

    # Define services
    services = [
        {
            'name': 'worldsurveyor',
            'service': 'worldsurveyor',
            'mcp_file': mcp_root / 'worldsurveyor' / 'src' / 'main.py',
            'openapi_url': build_openapi_url('WORLDSURVEYOR_API_URL', 'http://localhost:8891'),
        },
        {
            'name': 'worldbuilder',
            'service': 'worldbuilder',
            'mcp_file': mcp_root / 'worldbuilder' / 'src' / 'main.py',
            'openapi_url': build_openapi_url('WORLDBUILDER_API_URL', 'http://localhost:8899'),
        },
        {
            'name': 'worldviewer',
            'service': 'worldviewer',
            'mcp_file': mcp_root / 'worldviewer' / 'src' / 'main.py',
            'openapi_url': build_openapi_url('WORLDVIEWER_API_URL', 'http://localhost:8900'),
        },
        {
            'name': 'worldrecorder',
            'service': 'worldrecorder',
            'mcp_file': mcp_root / 'worldrecorder' / 'src' / 'main.py',
            'openapi_url': build_openapi_url('WORLDRECORDER_API_URL', 'http://localhost:8892'),
        },
        {
            'name': 'worldstreamer-srt',
            'service': 'worldstreamer',
            'mcp_file': mcp_root / 'worldstreamer' / 'src' / 'main.py',
            'openapi_url': build_openapi_url('WORLDSTREAMER_SRT_API_URL', 'http://localhost:8908'),
        },
        {
            'name': 'worldstreamer-rtmp',
            'service': 'worldstreamer',
            'mcp_file': mcp_root / 'worldstreamer' / 'src' / 'main.py',
            'openapi_url': build_openapi_url('WORLDSTREAMER_RTMP_API_URL', 'http://localhost:8906'),
        },
    ]

    overall_rc = 0
    print("Running OpenAPI parity checks...\n")
    for svc in services:
        name = svc['name']
        mcp_file = svc['mcp_file']
        openapi_url = svc['openapi_url']
        if not mcp_file.exists():
            print(f"[{name}] SKIP: MCP file not found: {mcp_file}")
            continue
        cmd = [sys.executable, str(checker), '--mcp-file', str(mcp_file), '--openapi-url', openapi_url, '--service', svc.get('service', name)]
        if args.fail_on_extra_openapi:
            cmd.append('--fail-on-extra-openapi')
        print(f"[{name}] Checking {mcp_file} vs {openapi_url}")
        rc = subprocess.call(cmd)
        if rc != 0:
            overall_rc = 1
        print("\n" + "-" * 60 + "\n")

    if overall_rc == 0:
        print("All parity checks passed ✅")
    else:
        print("Some parity checks failed ❌")
    return overall_rc


if __name__ == '__main__':
    raise SystemExit(main())
