#!/usr/bin/env python3
"""
Functional MCP client check against StreamableHTTP servers.

Connects to an MCP server over HTTP, performs initialize, lists tools,
and optionally calls a tool with JSON arguments.

Examples:
  # List tools on WorldSurveyor (8703)
  python tools/mcp_functional_check.py --port 8703 --path /mcp --list-tools

  # Call a tool with no args
  python tools/mcp_functional_check.py --port 8703 --path /mcp --call worldsurveyor_health

  # Call with arguments (JSON)
  python tools/mcp_functional_check.py --port 8703 --path /mcp \
    --call worldsurveyor_list_waypoints --args '{"waypoint_type": "point_of_interest"}'

Tip: Use test venv to run without system Python:
  /home/sherndon/agent-adventures/docker/mcp-servers/test_venv/bin/python \
    tools/mcp_functional_check.py --port 8703 --list-tools
"""

from __future__ import annotations

import argparse
import asyncio
import json
from datetime import timedelta
from typing import Any, Dict, List, Optional

from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamablehttp_client


async def run_check(host: str, port: int, path: str, list_tools: bool, call: Optional[str], args_json: Optional[str]) -> int:
    # Ensure path begins with '/'
    if not path.startswith('/'):
        path = '/' + path
    url = f"http://{host}:{port}{path}"
    async with streamablehttp_client(url, timeout=15, sse_read_timeout=300) as (read_stream, write_stream, _get_sid):
        session = ClientSession(read_stream, write_stream, read_timeout_seconds=timedelta(seconds=30))
        init = await session.initialize()
        print(f"Initialized. protocol={init.protocolVersion} server={init.serverInfo.name} {init.serverInfo.version}")

        if list_tools:
            tools = await session.list_tools()
            print(f"Tools: count={len(tools.tools)}")
            for t in tools.tools[:50]:
                print(f"- {t.name}")

        if call:
            call_args: Dict[str, Any] = {}
            if args_json:
                call_args = json.loads(args_json)
            print(f"Calling tool: {call} with args={call_args}")
            result = await session.call_tool(call, call_args or None)
            if result.isError:
                print(f"Tool error: {result.error.code} {result.error.message}")
            else:
                # Prefer text content if present
                texts: List[str] = []
                if result.content:
                    for c in result.content:
                        if getattr(c, 'type', '') == 'text':
                            texts.append(getattr(c, 'text', ''))
                if texts:
                    joined = "\n\n".join(texts)
                    print("Result (text):\n" + joined)
                elif result.structuredContent is not None:
                    print("Result (structured):\n" + json.dumps(result.structuredContent, indent=2))
                else:
                    print("Result: (no content)")

    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="MCP StreamableHTTP functional check")
    ap.add_argument("--host", default="127.0.0.1", help="Host to connect (default 127.0.0.1)")
    ap.add_argument("--port", type=int, required=True, help="Port to connect (e.g., 8703)")
    ap.add_argument("--path", default="/mcp", help="Endpoint path (default /mcp)")
    ap.add_argument("--list-tools", action="store_true", help="List available tools")
    ap.add_argument("--call", help="Tool name to call")
    ap.add_argument("--args", help="JSON object with tool arguments")
    args = ap.parse_args()

    return asyncio.run(run_check(args.host, args.port, args.path, args.list_tools, args.call, args.args))


if __name__ == "__main__":
    raise SystemExit(main())
