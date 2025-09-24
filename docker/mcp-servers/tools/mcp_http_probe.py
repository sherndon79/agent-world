#!/usr/bin/env python3
"""
Quick HTTP probe for MCP servers using FastMCP + Uvicorn.

This does NOT speak the MCP protocol. It simply verifies that each
server's ASGI app is reachable on its expected port and reports the
HTTP status for a few common paths.

Usage examples:

  # Probe all default MCP ports on localhost
  python tools/mcp_http_probe.py --all

  # Probe just worldsurveyor
  python tools/mcp_http_probe.py --port 8703 --name worldsurveyor

  # Custom host
  python tools/mcp_http_probe.py --host 127.0.0.1 --all

Tip: Use the provided test venv to run without touching system Python:
  /home/sherndon/agent-adventures/docker/mcp-servers/test_venv/bin/python \
    tools/mcp_http_probe.py --all
"""

from __future__ import annotations

import argparse
import sys
from typing import Iterable, List, Tuple

import httpx


DEFAULT_PORTS = {
    8700: "worldbuilder",
    8701: "worldviewer",
    8702: "worldstreamer",
    8703: "worldsurveyor",
    8704: "worldrecorder",
}

PATHS = ["/", "/sse", "/health", "/metrics", "/spec", "/tools", "/openapi.json"]


def probe_endpoint(client: httpx.Client, base: str, path: str) -> Tuple[str, int, str]:
    url = base + path
    try:
        resp = client.get(url, timeout=3.0)
        server = resp.headers.get("server", "")
        return (path, resp.status_code, server)
    except Exception as e:
        return (path, -1, f"ERR: {e}")


def run_probe(host: str, port: int, name: str | None, paths: Iterable[str]) -> List[Tuple[str, int, str]]:
    base = f"http://{host}:{port}"
    results: List[Tuple[str, int, str]] = []
    headers = {"User-Agent": "mcp-http-probe/1.0"}
    with httpx.Client(headers=headers) as client:
        for p in paths:
            results.append(probe_endpoint(client, base, p))
    return results


def main(argv: List[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Probe MCP HTTP servers for liveness")
    ap.add_argument("--host", default="127.0.0.1", help="Host to probe (default 127.0.0.1)")
    ap.add_argument("--port", type=int, help="Single port to probe")
    ap.add_argument("--name", help="Optional name label for the single port")
    ap.add_argument("--all", action="store_true", help="Probe all default MCP ports")
    ap.add_argument("--paths", nargs="*", default=PATHS, help="Paths to query")
    args = ap.parse_args(argv)

    targets: List[Tuple[int, str | None]] = []
    if args.all:
        targets.extend((p, DEFAULT_PORTS.get(p)) for p in sorted(DEFAULT_PORTS))
    elif args.port:
        targets.append((args.port, args.name))
    else:
        ap.error("Specify --all or --port <PORT>")

    any_ok = False
    for port, label in targets:
        label_text = f" ({label})" if label else ""
        print(f"\n=== Probing {args.host}:{port}{label_text} ===")
        results = run_probe(args.host, port, label, args.paths)
        for path, status, server in results:
            if status == -1:
                print(f"{path:16} -> CONNECTION ERROR [{server}]")
            else:
                print(f"{path:16} -> {status} (server={server})")
                any_ok = True

    if not any_ok:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

