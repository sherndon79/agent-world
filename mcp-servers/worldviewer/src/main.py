#!/usr/bin/env python3
"""
Isaac Sim Worldviewer MCP Server (Stdio)

Provides Claude Code with direct Isaac Sim worldviewer capabilities through MCP tools.
Interfaces with the Agent Worldviewer Extension HTTP API.

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

logger = logging.getLogger("worldviewer")


async def main():
    """Main entry point for the Worldviewer MCP server."""
    # Setup logging
    setup_logging('worldviewer')
    logger.info("🚀 Starting Isaac Sim Worldviewer MCP Server (Stdio - Modular)")

    # Initialize client
    await initialize_client()

    # Create the stdio server
    server = create_stdio_server()
    logger.info("Worldviewer MCP Server ready for stdio communication")
    logger.info("Using traditional MCP stdio transport (Modular)")

    try:
        # Run stdio server
        async with stdio_server() as (read_stream, write_stream):
            await server.run(
                read_stream,
                write_stream,
                InitializationOptions(
                    server_name="worldviewer",
                    server_version="1.0.0",
                    capabilities=ServerCapabilities(
                        tools=ToolsCapability(list_changed=False)
                    )
                )
            )
    finally:
        # Cleanup
        await close_client()
        logger.info("Worldviewer MCP Server shutdown complete")


if __name__ == "__main__":
    asyncio.run(main())