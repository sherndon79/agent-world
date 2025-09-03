#!/usr/bin/env python3
"""
Lightweight CLI to call agenTW∞rld extension HTTP APIs with the same
auth behavior as MCP servers (HMAC/Bearer via MCPBaseClient).

Usage:
  # HTTP modes
  python mcpctl.py worldbuilder scene_status
  python mcpctl.py worldbuilder query_objects_near_point --point 5,0,2 --radius 10
  python mcpctl.py worldviewer get_asset_transform --usd-path /World/foo --calculation-mode auto
  python mcpctl.py worldbuilder GET /metrics.prom
  python mcpctl.py worldbuilder POST /add_element --json '{"element_type":"cube","name":"box","position":[0,0,1]}'

  # MCP stdio modes (client-side smoketests)
  python mcpctl.py mcp list-tools worldrecorder-server
  python mcpctl.py mcp call-tool worldrecorder-server worldrecorder_recording_status --json '{}'
  python mcpctl.py mcp smoke flows/worldrecorder_smoke.json
"""

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Dict


def load_dotenv() -> None:
    ".env loader (simple)"
    root = Path(__file__).resolve().parents[3]
    envp = root / '.env'
    if not envp.exists():
        return
    for line in envp.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        k, v = line.split('=', 1)
        k = k.strip()
        v = v.strip().strip('"').strip("'")
        os.environ.setdefault(k, v)


def add_shared_to_path():
    # Add shared client to path
    shared = Path(__file__).resolve().parents[2] / 'shared'
    sys.path.insert(0, str(shared))


async def run_worldbuilder(cmd: str, args: argparse.Namespace) -> None:
    from mcp_base_client import MCPBaseClient

    base = os.getenv('AGENT_WORLDBUILDER_BASE_URL') or os.getenv('WORLDBUILDER_API_URL') or 'http://localhost:8899'
    client = MCPBaseClient('WORLDBUILDER', base)
    await client.initialize()
    try:
        if cmd == 'scene_status':
            res = await client.get('/scene_status')
            print(json.dumps(res, indent=2))
        elif cmd == 'get_scene':
            res = await client.get('/get_scene')
            print(json.dumps(res, indent=2))
        elif cmd == 'query_objects_near_point':
            if not args.point:
                raise SystemExit('--point is required (e.g. 5,0,2)')
            params = {'point': args.point, 'radius': str(args.radius)}
            res = await client.get('/query/objects_near_point', params=params)
            print(json.dumps(res, indent=2))
        elif cmd in ('GET', 'POST'):
            path = args.path
            if not path or not path.startswith('/'):
                raise SystemExit('provide --path beginning with /')
            if cmd == 'GET':
                params = parse_kv(args.params)
                res = await client.get(path, params=params)
            else:
                payload = json.loads(args.json) if args.json else {}
                res = await client.post(path, json=payload)
            print(json.dumps(res, indent=2) if isinstance(res, dict) else str(res))
        else:
            raise SystemExit(f'Unknown worldbuilder command: {cmd}')
    finally:
        await client.close()


async def run_worldviewer(cmd: str, args: argparse.Namespace) -> None:
    from mcp_base_client import MCPBaseClient

    base = os.getenv('AGENT_WORLDVIEWER_BASE_URL') or os.getenv('WORLDVIEWER_API_URL') or 'http://localhost:8900'
    client = MCPBaseClient('WORLDVIEWER', base)
    await client.initialize()
    try:
        if cmd == 'get_asset_transform':
            if not args.usd_path:
                raise SystemExit('--usd-path is required')
            params = {'usd_path': args.usd_path, 'calculation_mode': args.calculation_mode}
            res = await client.get('/get_asset_transform', params=params)
            print(json.dumps(res, indent=2))
        elif cmd in ('GET', 'POST'):
            path = args.path
            if not path or not path.startswith('/'):
                raise SystemExit('provide --path beginning with /')
            if cmd == 'GET':
                params = parse_kv(args.params)
                res = await client.get(path, params=params)
            else:
                payload = json.loads(args.json) if args.json else {}
                res = await client.post(path, json=payload)
            print(json.dumps(res, indent=2) if isinstance(res, dict) else str(res))
        else:
            raise SystemExit(f'Unknown worldviewer command: {cmd}')
    finally:
        await client.close()


async def run_worldsurveyor(cmd: str, args: argparse.Namespace) -> None:
    from mcp_base_client import MCPBaseClient

    base = os.getenv('AGENT_WORLDSURVEYOR_BASE_URL') or os.getenv('WORLDSURVEYOR_API_URL') or 'http://localhost:8891'
    client = MCPBaseClient('WORLDSURVEYOR', base)
    await client.initialize()
    try:
        if cmd in ('GET', 'POST'):
            path = args.path
            if not path or not path.startswith('/'):
                raise SystemExit('provide --path beginning with /')
            if cmd == 'GET':
                params = parse_kv(args.params)
                res = await client.get(path, params=params)
            else:
                payload = json.loads(args.json) if args.json else {}
                res = await client.post(path, json=payload)
            print(json.dumps(res, indent=2) if isinstance(res, dict) else str(res))
        else:
            raise SystemExit(f'Unknown worldsurveyor command: {cmd}')
    finally:
        await client.close()


async def run_worldrecorder(cmd: str, args: argparse.Namespace) -> None:
    from mcp_base_client import MCPBaseClient

    base = os.getenv('AGENT_WORLDRECORDER_BASE_URL') or os.getenv('WORLDRECORDER_API_URL') or 'http://localhost:8892'
    client = MCPBaseClient('WORLDRECORDER', base)
    await client.initialize()
    try:
        if cmd in ('GET', 'POST'):
            path = args.path
            if not path or not path.startswith('/'):
                raise SystemExit('provide --path beginning with /')
            if cmd == 'GET':
                params = parse_kv(args.params)
                res = await client.get(path, params=params)
            else:
                payload = json.loads(args.json) if args.json else {}
                res = await client.post(path, json=payload)
            print(json.dumps(res, indent=2) if isinstance(res, dict) else str(res))
        else:
            raise SystemExit(f'Unknown worldrecorder command: {cmd}')
    finally:
        await client.close()


def parse_kv(items) -> Dict[str, str]:
    params: Dict[str, str] = {}
    if not items:
        return params
    for it in items:
        if '=' not in it:
            raise SystemExit(f'Invalid param "{it}" (expected key=value)')
        k, v = it.split('=', 1)
        params[k] = v
    return params


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description='agenTW∞rld extension HTTP CLI')
    sub = p.add_subparsers(dest='service', required=True)

    # WorldBuilder
    wb = sub.add_parser('worldbuilder', help='WorldBuilder API calls')
    wb_sub = wb.add_subparsers(dest='cmd', required=True)
    wb_sub.add_parser('scene_status', help='GET /scene_status')
    wb_sub.add_parser('get_scene', help='GET /get_scene')
    wb_qnp = wb_sub.add_parser('query_objects_near_point', help='GET /query/objects_near_point')
    wb_qnp.add_argument('--point', required=True, help='e.g. 5,0,2')
    wb_qnp.add_argument('--radius', type=float, default=10.0)
    wb_get = wb_sub.add_parser('GET', help='Generic GET')
    wb_get.add_argument('path', help='Endpoint path starting with /')
    wb_get.add_argument('--params', nargs='*', help='key=value pairs')
    wb_post = wb_sub.add_parser('POST', help='Generic POST')
    wb_post.add_argument('path', help='Endpoint path starting with /')
    wb_post.add_argument('--json', help='Raw JSON string payload')

    # WorldViewer
    wv = sub.add_parser('worldviewer', help='WorldViewer API calls')
    wv_sub = wv.add_subparsers(dest='cmd', required=True)
    wv_gat = wv_sub.add_parser('get_asset_transform', help='GET /get_asset_transform')
    wv_gat.add_argument('--usd-path', required=True)
    wv_gat.add_argument('--calculation-mode', default='auto')
    wv_get = wv_sub.add_parser('GET', help='Generic GET')
    wv_get.add_argument('path')
    wv_get.add_argument('--params', nargs='*')
    wv_post = wv_sub.add_parser('POST', help='Generic POST')
    wv_post.add_argument('path')
    wv_post.add_argument('--json')

    # WorldSurveyor
    ws = sub.add_parser('worldsurveyor', help='WorldSurveyor API calls')
    ws_sub = ws.add_subparsers(dest='cmd', required=True)
    ws_get = ws_sub.add_parser('GET')
    ws_get.add_argument('path')
    ws_get.add_argument('--params', nargs='*')
    ws_post = ws_sub.add_parser('POST')
    ws_post.add_argument('path')
    ws_post.add_argument('--json')

    # WorldRecorder
    wr = sub.add_parser('worldrecorder', help='WorldRecorder API calls')
    wr_sub = wr.add_subparsers(dest='cmd', required=True)
    wr_get = wr_sub.add_parser('GET')
    wr_get.add_argument('path')
    wr_get.add_argument('--params', nargs='*')
    wr_post = wr_sub.add_parser('POST')
    wr_post.add_argument('path')
    wr_post.add_argument('--json')

    return p


async def main_async():
    load_dotenv()
    add_shared_to_path()
    parser = build_parser()
    args = parser.parse_args()
    service = args.service
    cmd = args.cmd

    if service == 'worldbuilder':
        await run_worldbuilder(cmd, args)
    elif service == 'worldviewer':
        await run_worldviewer(cmd, args)
    elif service == 'worldsurveyor':
        await run_worldsurveyor(cmd, args)
    elif service == 'worldrecorder':
        await run_worldrecorder(cmd, args)
    else:
        raise SystemExit(f'Unknown service: {service}')


def main():
    asyncio.run(main_async())


if __name__ == '__main__':
    main()
