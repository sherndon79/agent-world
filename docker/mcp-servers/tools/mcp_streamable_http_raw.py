#!/usr/bin/env python3
"""
Raw MCP Streamable HTTP check using httpx + httpx_sse (async).

Performs:
  1) initialize (reads SSE event)
  2) notifications/initialized
  3) optional tools/list
  4) optional tools/call with JSON args

Usage examples:
  # Call a tool via explicit URL
  python tools/mcp_streamable_http_raw.py --url http://127.0.0.1:8701/mcp \
    --call worldviewer_get_camera_status

  # List tools
  python tools/mcp_streamable_http_raw.py --url http://127.0.0.1:8703/mcp --list-tools
"""

from __future__ import annotations

import argparse
import asyncio
import json
from typing import Any, Dict, Optional

import httpx
from httpx_sse import EventSource


def build_url(host: str, port: int, path: str) -> str:
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
    init_req = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2025-06-18",
            "capabilities": {"sampling": None, "elicitation": None, "experimental": None, "roots": None},
            "clientInfo": {"name": "raw-probe", "version": "0.0.1"},
        },
    }
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }
    async with client.stream("POST", url, json=init_req, headers=headers) as resp:
        resp.raise_for_status()
        msg = await _read_first_message(resp)
        sid = resp.headers.get("mcp-session-id", "")
        print(f"Initialized OK. session={sid} message={msg.get('result', {})}")
        return sid


async def send_initialized(client: httpx.AsyncClient, url: str, sid: str) -> None:
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
        "mcp-session-id": sid,
    }
    payload = {"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}}
    resp = await client.post(url, headers=headers, json=payload)
    resp.raise_for_status()


async def tools_list(client: httpx.AsyncClient, url: str, sid: str) -> None:
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
        "mcp-session-id": sid,
    }
    payload = {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}
    async with client.stream("POST", url, headers=headers, json=payload) as resp:
        resp.raise_for_status()
        msg = await _read_first_message(resp)
        print("tools/list:", json.dumps(msg, indent=2))


async def tools_call(client: httpx.AsyncClient, url: str, sid: str, name: str, args: Optional[Dict[str, Any]]) -> None:
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
        "mcp-session-id": sid,
    }
    payload = {
        "jsonrpc": "2.0",
        "id": 3,
        "method": "tools/call",
        "params": {"name": name, "arguments": args or {}},
    }
    async with client.stream("POST", url, headers=headers, json=payload) as resp:
        resp.raise_for_status()
        msg = await _read_first_message(resp)
        print("tools/call:", json.dumps(msg, indent=2))


async def run(url: str, list_tools_flag: bool, call: Optional[str], args_json: Optional[str], timeout: float) -> int:
    limits = httpx.Limits(max_keepalive_connections=5, max_connections=10)
    async with httpx.AsyncClient(timeout=timeout, limits=limits) as client:
        sid = await initialize(client, url)
        await send_initialized(client, url, sid)
        if list_tools_flag:
            await tools_list(client, url, sid)
        if call:
            args = json.loads(args_json) if args_json else None
            await tools_call(client, url, sid, call, args)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Raw MCP Streamable HTTP check")
    ap.add_argument("--url", help="Full URL to MCP endpoint (e.g., http://127.0.0.1:8701/mcp)")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int)
    ap.add_argument("--path", default="/mcp")
    ap.add_argument("--list-tools", action="store_true")
    ap.add_argument("--call")
    ap.add_argument("--args")
    ap.add_argument("--timeout", type=float, default=15.0)
    args = ap.parse_args()

    url = args.url or build_url(args.host, args.port, args.path)
    return asyncio.run(run(url, args.list_tools, args.call, args.args, args.timeout))


if __name__ == "__main__":
    raise SystemExit(main())

