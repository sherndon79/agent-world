#!/usr/bin/env python3
"""
OpenAPI Parity Checker for MCP Servers

Compares the HTTP endpoints used by an MCP server implementation against the
OpenAPI spec exposed by the corresponding Isaac Sim extension.

Usage examples:
  python openapi_parity_check.py \
    --mcp-file ../worldsurveyor/src/mcp_worldsurveyor.py \
    --openapi-url http://localhost:8891/openapi.json

  python openapi_parity_check.py \
    --mcp-file ../worldbuilder/src/mcp_agent_worldbuilder.py \
    --openapi-url http://localhost:8899/openapi.json

Exit status is non-zero if there are mismatches.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Set, Tuple


FSTRING_ENDPOINT_RE = re.compile(r"\{self\.base_url\}/([A-Za-z0-9_.\-/]+)")
REQUEST_FUNC_RE = re.compile(r"_request\(\s*['\"](?:GET|POST)['\"]\s*,\s*['\"]([^'\"]+)['\"]")
MAKE_REQUEST_RE = re.compile(r"_make_request\(\s*['\"][A-Z]+['\"]\s*,\s*['\"]([^'\"]+)['\"]")


def parse_mcp_endpoints(mcp_source: str) -> Set[str]:
    """Extract endpoint paths used by the MCP source file.

    Supports patterns:
      - f"{self.base_url}/path"
      - _request("GET|POST", "path")
      - _make_request("GET|POST", "/path")
    """
    endpoints: Set[str] = set()

    # f"{self.base_url}/endpoint"
    for m in FSTRING_ENDPOINT_RE.finditer(mcp_source):
        endpoints.add(m.group(1).lstrip('/'))

    # _request("METHOD", "endpoint")
    for m in REQUEST_FUNC_RE.finditer(mcp_source):
        endpoints.add(m.group(1).lstrip('/'))

    # _make_request("METHOD", "/endpoint")
    for m in MAKE_REQUEST_RE.finditer(mcp_source):
        endpoints.add(m.group(1).lstrip('/'))

    return endpoints


def load_openapi_paths(openapi_json: dict) -> Set[str]:
    paths = openapi_json.get('paths', {})
    return {p.lstrip('/') for p in paths.keys()}


def fetch_openapi(url: str) -> dict:
    try:
        import requests  # type: ignore
    except Exception as e:
        print(f"ERROR: requests is required to fetch OpenAPI: {e}", file=sys.stderr)
        sys.exit(2)
    resp = requests.get(url, timeout=10)
    resp.raise_for_status()
    return resp.json()


def main() -> int:
    ap = argparse.ArgumentParser(description="OpenAPI parity checker for MCP servers")
    ap.add_argument('--mcp-file', required=True, help='Path to MCP server Python file to analyze')
    ap.add_argument('--openapi-url', help='URL to /openapi.json')
    ap.add_argument('--openapi-file', help='Path to a local openapi.json file')
    ap.add_argument('--fail-on-extra-openapi', action='store_true', help='Fail if OpenAPI has endpoints unused by MCP')
    args = ap.parse_args()

    mcp_path = Path(args.mcp_file)
    if not mcp_path.exists():
        print(f"ERROR: MCP file not found: {mcp_path}", file=sys.stderr)
        return 2

    source = mcp_path.read_text(encoding='utf-8', errors='replace')
    mcp_endpoints = parse_mcp_endpoints(source)

    if not (args.openapi_url or args.openapi_file):
        print("ERROR: Provide --openapi-url or --openapi-file", file=sys.stderr)
        return 2

    if args.openapi_file:
        openapi_json = json.loads(Path(args.openapi_file).read_text(encoding='utf-8'))
    else:
        openapi_json = fetch_openapi(args.openapi_url)

    openapi_paths = load_openapi_paths(openapi_json)

    missing_in_openapi = sorted(ep for ep in mcp_endpoints if ep not in openapi_paths)
    extra_in_openapi = sorted(ep for ep in openapi_paths if ep not in mcp_endpoints)

    print("MCP endpoints used (parsed):", *sorted(mcp_endpoints), sep='\n  - ')
    print("\nOpenAPI endpoints:", *sorted(openapi_paths), sep='\n  - ')

    status = 0
    if missing_in_openapi:
        status = 1
        print("\nERROR: Endpoints used by MCP but missing in OpenAPI:")
        for ep in missing_in_openapi:
            print(f"  - {ep}")

    if args.fail_on_extra_openapi and extra_in_openapi:
        status = 1
        print("\nERROR: Endpoints present in OpenAPI but unused by MCP:")
        for ep in extra_in_openapi:
            print(f"  - {ep}")
    else:
        if extra_in_openapi:
            print("\nNote: Endpoints present in OpenAPI but unused by MCP (informational):")
            for ep in extra_in_openapi:
                print(f"  - {ep}")

    if status == 0:
        print("\nParity check passed ✅")
    else:
        print("\nParity check failed ❌")
    return status


if __name__ == '__main__':
    raise SystemExit(main())
