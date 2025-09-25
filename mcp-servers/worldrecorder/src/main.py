#!/usr/bin/env python3
"""
Isaac Sim Worldrecorder MCP Server (Stdio)

Provides Claude Code with direct Isaac Sim worldrecorder capabilities through MCP tools.
Interfaces with the Agent Worldrecorder Extension HTTP API.

Uses stdio transport for direct MCP protocol communication.
"""

import asyncio
import logging
import os
import sys
from mcp.server.stdio import stdio_server
from mcp.server.models import InitializationOptions
from mcp.types import ServerCapabilities, ToolsCapability

# Add shared modules to path
shared_path = os.path.join(os.path.dirname(__file__), '..', '..', 'shared')
if shared_path not in sys.path:
    sys.path.insert(0, shared_path)

from logging_setup import setup_logging

# Import local modules
from config import config
from client import initialize_client, close_client
from server_stdio import create_stdio_server

logger = logging.getLogger("worldrecorder")


async def main():
    """Main entry point for the Worldrecorder MCP server."""
    # Setup logging for stdio MCP - disable console to avoid stdout contamination
    os.environ.setdefault('AGENT_LOG_FILE', '/tmp/worldrecorder_mcp.log')
    os.environ.setdefault('AGENT_LOG_LEVEL', 'INFO')
    setup_logging('worldrecorder')

    # Remove all handlers that write to stdout/stderr for stdio MCP
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        if isinstance(handler, logging.StreamHandler) and handler.stream in (sys.stdout, sys.stderr):
            root_logger.removeHandler(handler)
    logger.info("🚀 Starting Isaac Sim Worldrecorder MCP Server (Stdio - Modular)")

    # Initialize client
    await initialize_client()

    # Create the stdio server
    server = create_stdio_server()
    logger.info("Worldrecorder MCP Server ready for stdio communication")
    logger.info("Using traditional MCP stdio transport (Modular)")

    try:
        # Run stdio server
        async with stdio_server() as (read_stream, write_stream):
            await server.run(
                read_stream,
                write_stream,
                InitializationOptions(
                    server_name="worldrecorder",
                    server_version="1.0.0",
                    capabilities=ServerCapabilities(
                        tools=ToolsCapability(list_changed=False)
                    )
                )
            )
    finally:
        # Cleanup
        await close_client()
        logger.info("Worldrecorder MCP Server shutdown complete")


if __name__ == "__main__":
    asyncio.run(main())