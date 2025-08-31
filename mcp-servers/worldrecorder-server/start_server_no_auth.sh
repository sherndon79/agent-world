#!/bin/bash
"""
Start videocapture MCP server with authentication disabled
This can be used for testing or when the Isaac Sim extension doesn't have auth configured
"""

# Set environment to disable authentication
export AGENT_EXT_AUTH_ENABLED=0

# Start the MCP server
cd "$(dirname "$0")"
./venv/bin/python src/mcp_agent_videocapture.py "$@"