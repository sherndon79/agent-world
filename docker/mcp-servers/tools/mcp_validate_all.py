#!/usr/bin/env python3
"""
Validate all MCP servers (health + metrics) in one pass.

Performs MCP Streamable HTTP handshake to each server and calls:
  - <service>_health_check
  - JSON metrics tool (if available)
  - Prometheus metrics tool (if available)

Outputs a compact summary per service plus optional verbose details.

Usage:
  python tools/mcp_validate_all.py
  python tools/mcp_validate_all.py --verbose
  python tools/mcp_validate_all.py --host 127.0.0.1 --ports 8700 8701
"""

from __future__ import annotations

import argparse
import asyncio
import json
from typing import Any, Dict, List, Optional, Tuple

import httpx
from httpx_sse import EventSource


def build_url(host: str, port: int, path: str = "/mcp") -> str:
    if not path.startswith('/'):
        path = '/' + path
    return f"http://{host}:{port}{path}"


async def _read_first_message(resp: httpx.Response) -> Dict[str, Any]:
    es = EventSource(resp)
    async for sse in es.aiter_sse():
        if sse.event == "message" and sse.data:
            return json.loads(sse.data)
    return {}


async def initialize(client: httpx.AsyncClient, url: str) -> str:
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2025-06-18",
            "capabilities": {"sampling": None, "elicitation": None, "experimental": None, "roots": None},
            "clientInfo": {"name": "mcp-validate-all", "version": "0.1.0"},
        },
    }
    headers = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}
    async with client.stream("POST", url, json=payload, headers=headers) as resp:
        resp.raise_for_status()
        await _read_first_message(resp)
        sid = resp.headers.get("mcp-session-id", "")
        return sid


async def notify_initialized(client: httpx.AsyncClient, url: str, sid: str) -> None:
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
        "mcp-session-id": sid,
    }
    payload = {"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}}
    resp = await client.post(url, headers=headers, json=payload)
    resp.raise_for_status()


async def tools_call(client: httpx.AsyncClient, url: str, sid: str, name: str, args: Optional[Dict[str, Any]] = None) -> Tuple[bool, Dict[str, Any]]:
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
        "mcp-session-id": sid,
    }
    payload = {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": name, "arguments": args or {}}}
    async with client.stream("POST", url, headers=headers, json=payload) as resp:
        resp.raise_for_status()
        msg = await _read_first_message(resp)
        result = msg.get("result") or {}
        is_error = bool(msg.get("error")) or bool(result.get("isError"))
        return (not is_error, result)


SERVICES = {
    "worldbuilder": {
        "port": 8700,
        "health": "worldbuilder_health_check",
        "metrics_json": ("worldbuilder_get_metrics", {"format": "json"}),
        "metrics_prom": ("worldbuilder_metrics_prometheus", {}),
    },
    "worldviewer": {
        "port": 8701,
        "health": "worldviewer_health_check",
        "metrics_json": ("worldviewer_get_metrics", {"format": "json"}),
        "metrics_prom": ("worldviewer_metrics_prometheus", {}),
    },
    "worldstreamer": {
        "port": 8702,
        "health": "worldstreamer_health_check",
        # no metrics tools for streamer
    },
    "worldsurveyor": {
        "port": 8703,
        "health": "worldsurveyor_health_check",
        "metrics_json": ("worldsurveyor_get_metrics", {"format": "json"}),
        "metrics_prom": ("worldsurveyor_metrics_prometheus", {}),
    },
    "worldrecorder": {
        "port": 8704,
        "health": "worldrecorder_health_check",
        "metrics_json": ("worldrecorder_get_metrics", {}),
        "metrics_prom": ("worldrecorder_metrics_prometheus", {}),
    },
}


async def validate_service(name: str, host: str, port: int, path: str, verbose: bool) -> Dict[str, Any]:
    url = build_url(host, port, path)
    summary: Dict[str, Any] = {"service": name, "port": port}
    limits = httpx.Limits(max_keepalive_connections=5, max_connections=10)
    async with httpx.AsyncClient(timeout=15.0, limits=limits) as client:
        try:
            sid = await initialize(client, url)
            await notify_initialized(client, url, sid)
            # Health
            ok, res = await tools_call(client, url, sid, SERVICES[name]["health"], {})
            summary["health_ok"] = ok
            if verbose:
                summary["health_result"] = res
            # Metrics JSON
            if "metrics_json" in SERVICES[name]:
                tool, args = SERVICES[name]["metrics_json"]
                ok, res = await tools_call(client, url, sid, tool, args)
                summary["metrics_json_ok"] = ok
                if verbose:
                    summary["metrics_json_result"] = res
            # Metrics Prom
            if "metrics_prom" in SERVICES[name]:
                tool, args = SERVICES[name]["metrics_prom"]
                ok, res = await tools_call(client, url, sid, tool, args)
                summary["metrics_prom_ok"] = ok
                if verbose:
                    summary["metrics_prom_result"] = res
        except Exception as e:
            summary["error"] = str(e)
    return summary


async def main_async(host: str, path: str, ports: Optional[List[int]], only: Optional[List[str]], verbose: bool) -> int:
    targets: List[Tuple[str, int]] = []
    if only:
        for name in only:
            cfg = SERVICES.get(name)
            if cfg:
                targets.append((name, cfg["port"]))
    elif ports:
        # Map ports back to known names
        port_to_name = {cfg["port"]: name for name, cfg in SERVICES.items()}
        for p in ports:
            targets.append((port_to_name.get(p, f"port-{p}"), p))
    else:
        targets = [(name, cfg["port"]) for name, cfg in SERVICES.items()]

    results: List[Dict[str, Any]] = []
    for name, port in targets:
        summary = await validate_service(name, host, port, path, verbose)
        results.append(summary)

    # Print compact summary
    print("\n=== MCP Validation Summary ===")
    for s in results:
        name = s.get("service")
        port = s.get("port")
        health = "OK" if s.get("health_ok") else "FAIL"
        mj = s.get("metrics_json_ok")
        mp = s.get("metrics_prom_ok")
        mj_text = " N/A" if mj is None else (" OK" if mj else " FAIL")
        mp_text = " N/A" if mp is None else (" OK" if mp else " FAIL")
        err = s.get("error")
        line = f"- {name} ({port}) -> health:{health} metrics(json):{mj_text} metrics(prom):{mp_text}"
        if err:
            line += f" error={err}"
        print(line)

    if verbose:
        print("\nDetailed Results:")
        print(json.dumps(results, indent=2))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Validate all MCP servers (health + metrics)")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--path", default="/mcp")
    ap.add_argument("--ports", nargs="*", type=int, help="Optional list of ports to validate")
    ap.add_argument("--only", nargs="*", choices=list(SERVICES.keys()), help="Validate only specific services")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()
    return asyncio.run(main_async(args.host, args.path, args.ports, args.only, args.verbose))


if __name__ == "__main__":
    raise SystemExit(main())

