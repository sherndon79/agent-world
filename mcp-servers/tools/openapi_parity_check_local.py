#!/usr/bin/env python3
"""
OpenAPI Parity Checker (Local Module)

Compares the HTTP endpoints used by an MCP server implementation against the
OpenAPI spec built from the local extension's openapi_spec.py (no network).

Usage examples:
  python openapi_parity_check_local.py \
    --service worldsurveyor \
    --mcp-file ../worldsurveyor/src/mcp_worldsurveyor.py

  python openapi_parity_check_local.py \
    --service worldviewer \
    --mcp-file ../worldviewer/src/mcp_agent_worldviewer.py \
    --port 8900

Exit status is non-zero if there are mismatches.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sys
from pathlib import Path
from typing import Dict, Set


FSTRING_ENDPOINT_RE = re.compile(r"\{self\.base_url\}/([A-Za-z0-9_.\-/]+)")
REQUEST_FUNC_RE = re.compile(r"_request\(\s*['\"](?:GET|POST)['\"]\s*,\s*['\"]([^'\"]+)['\"]")
MAKE_REQUEST_RE = re.compile(r"_make_request\(\s*['\"][A-Z]+['\"]\s*,\s*['\"]([^'\"]+)['\"]")


DEFAULT_PORTS: Dict[str, int] = {
    'worldbuilder': 8899,
    'worldviewer': 8900,
    'worldsurveyor': 8891,
    'worldrecorder': 8901,
}


def parse_mcp_endpoints(mcp_source: str) -> Set[str]:
    endpoints: Set[str] = set()

    for m in FSTRING_ENDPOINT_RE.finditer(mcp_source):
        endpoints.add(m.group(1).lstrip('/'))
    for m in REQUEST_FUNC_RE.finditer(mcp_source):
        endpoints.add(m.group(1).lstrip('/'))
    for m in MAKE_REQUEST_RE.finditer(mcp_source):
        endpoints.add(m.group(1).lstrip('/'))

    return endpoints


def load_openapi_from_module(service: str, repo_root: Path, port: int) -> Dict:
    """Load openapi_spec.py directly by file path to avoid importing extension package."""
    spec_path = repo_root / 'agentworld-extensions' / f'omni.agent.{service}' / 'omni' / 'agent' / service / 'openapi_spec.py'
    if not spec_path.exists():
        raise FileNotFoundError(f"OpenAPI spec not found: {spec_path}")
    module_name = f'openapi_spec_{service}'
    spec = importlib.util.spec_from_file_location(module_name, str(spec_path))
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load module from {spec_path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore
    if not hasattr(mod, 'build_openapi_spec'):
        raise RuntimeError(f"Module {spec_path} missing build_openapi_spec")
    return mod.build_openapi_spec(port)


def load_openapi_paths(openapi_json: dict) -> Set[str]:
    paths = openapi_json.get('paths', {})
    return {p.lstrip('/') for p in paths.keys()}


def main() -> int:
    ap = argparse.ArgumentParser(description="OpenAPI parity checker (local module)")
    ap.add_argument('--service', required=True, choices=['worldbuilder', 'worldviewer', 'worldsurveyor', 'worldrecorder'])
    ap.add_argument('--mcp-file', required=True, help='Path to MCP server Python file to analyze')
    ap.add_argument('--repo-root', help='Path to repo root (default: auto-detect)')
    ap.add_argument('--port', type=int, help='Port to use when building OpenAPI (default per service)')
    ap.add_argument('--fail-on-extra-openapi', action='store_true', help='Fail if OpenAPI has endpoints unused by MCP')
    args = ap.parse_args()

    mcp_path = Path(args.mcp_file)
    if not mcp_path.exists():
        print(f"ERROR: MCP file not found: {mcp_path}", file=sys.stderr)
        return 2

    # Detect repo root (two levels up from tools dir if not provided)
    if args.repo_root:
        repo_root = Path(args.repo_root)
    else:
        repo_root = Path(__file__).resolve().parents[2]

    port = args.port or DEFAULT_PORTS[args.service]

    source = mcp_path.read_text(encoding='utf-8', errors='replace')
    mcp_endpoints = parse_mcp_endpoints(source)

    spec = load_openapi_from_module(args.service, repo_root, port)
    openapi_paths = load_openapi_paths(spec)

    missing_in_openapi = sorted(ep for ep in mcp_endpoints if ep not in openapi_paths)
    extra_in_openapi = sorted(ep for ep in openapi_paths if ep not in mcp_endpoints)

    print(f"Service: {args.service}")
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
