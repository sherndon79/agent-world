#!/usr/bin/env python3
from __future__ import annotations

"""
MCP Streamable HTTP functional check.

Connects to an MCP server over Streamable HTTP, performs initialize,
optionally lists tools, and optionally calls a tool.

Examples:
  # WorldViewer on port 8701 (default path /mcp)
  python tools/mcp_streamable_check.py --port 8701 --call worldviewer_get_camera_status

  # Explicit URL
  python tools/mcp_streamable_check.py --url http://127.0.0.1:8703/mcp --list-tools
"""

import argparse
import asyncio
import json
from datetime import timedelta
from typing import Any, Dict, List, Optional

from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamablehttp_client


def build_url(host: str, port: int, path: str) -> str:
    if not path.startswith('/'):
        path = '/' + path
    return f"http://{host}:{port}{path}"


async def run_check(
    url: str,
    list_tools: bool,
    call: Optional[str],
    args_json: Optional[str],
    timeout: float,
    verbose: bool,
) -> int:
    if verbose:
        print(f"Connecting to {url} (timeout={timeout}s)")
    try:
        async with streamablehttp_client(
            url,
            timeout=timeout,
            sse_read_timeout=max(timeout * 10, 60),
        ) as (read_stream, write_stream, _get_sid):
            session = ClientSession(
                read_stream,
                write_stream,
                read_timeout_seconds=timedelta(seconds=max(timeout, 10)),
            )
            init = await session.initialize()
            print(
                f"Initialized. protocol={init.protocolVersion} "
                f"server={init.serverInfo.name} {init.serverInfo.version}"
            )

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
                    texts: List[str] = []
                    if result.content:
                        for c in result.content:
                            if getattr(c, 'type', '') == 'text':
                                texts.append(getattr(c, 'text', ''))
                    if texts:
                        print("Result (text):\n" + "\n\n".join(texts))
                    elif result.structuredContent is not None:
                        print(
                            "Result (structured):\n"
                            + json.dumps(result.structuredContent, indent=2)
                        )
                    else:
                        print("Result: (no content)")
        return 0
    except Exception as e:
        print(f"Error: {e}")
        return 2


def main() -> int:
    ap = argparse.ArgumentParser(description="MCP StreamableHTTP functional check")
    ap.add_argument("--url", help="Full URL to MCP endpoint (e.g., http://127.0.0.1:8701/mcp)")
    ap.add_argument("--host", default="127.0.0.1", help="Host (default 127.0.0.1)")
    ap.add_argument("--port", type=int, help="Port (e.g., 8701)")
    ap.add_argument("--path", default="/mcp", help="Endpoint path (default /mcp)")
    ap.add_argument("--list-tools", action="store_true", help="List available tools")
    ap.add_argument("--call", help="Tool name to call")
    ap.add_argument("--args", help="JSON object with tool arguments")
    ap.add_argument("--timeout", type=float, default=10.0, help="HTTP timeout seconds (default 10)")
    ap.add_argument("--verbose", action="store_true", help="Verbose output")
    args = ap.parse_args()

    if args.url:
        url = args.url
    else:
        if args.port is None:
            ap.error("Specify --url or --port")
        url = build_url(args.host, args.port, args.path)

    return asyncio.run(
        run_check(url, args.list_tools, args.call, args.args, args.timeout, args.verbose)
    )


if __name__ == "__main__":
    raise SystemExit(main())

