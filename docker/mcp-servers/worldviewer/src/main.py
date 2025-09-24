#!/usr/bin/env python3
"""
Isaac Sim WorldViewer MCP Server (Modular)

Provides Claude Code with direct Isaac Sim camera control and cinematography capabilities through MCP tools.
Interfaces with the Agent WorldViewer Extension HTTP API.

Uses FastMCP with Streamable HTTP transport (modern MCP protocol).
"""

import asyncio
import logging
import os
import sys
import uvicorn
from mcp.server.fastmcp import FastMCP

# Add shared modules to path
shared_path = os.path.join(os.path.dirname(__file__), '..', '..', 'shared')
if shared_path not in sys.path:
    sys.path.insert(0, shared_path)

from logging_setup import setup_logging

# Import local modules
from config import config
from client import initialize_client, close_client
from tools import register_tools

# Initialize FastMCP
mcp = FastMCP("worldviewer")
logger = logging.getLogger("worldviewer")


async def main():
    """Main entry point for the WorldViewer MCP server."""
    # Setup logging
    setup_logging('worldviewer')
    logger.info("🚀 Starting Isaac Sim WorldViewer MCP Server (FastMCP - Modular)")

    # Initialize client
    await initialize_client()

    # Register all tools
    tool_names = register_tools(mcp)
    logger.info(f"Registered {len(tool_names)} WorldViewer tools")

    # Get port from environment variable
    port = config.server_port

    # Create the FastMCP ASGI application for Streamable HTTP transport
    app = mcp.streamable_http_app

    logger.info(f"WorldViewer MCP Server starting on http://0.0.0.0:{port}")
    logger.info("Using modern FastMCP with Streamable HTTP transport (Modular)")

    try:
        # Run with uvicorn
        config_obj = uvicorn.Config(app, host="0.0.0.0", port=port, log_level="info")
        server = uvicorn.Server(config_obj)
        await server.serve()
    finally:
        # Cleanup
        await close_client()
        logger.info("WorldViewer MCP Server shutdown complete")


if __name__ == "__main__":
    asyncio.run(main())