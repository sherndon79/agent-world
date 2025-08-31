#!/usr/bin/env python3
"""
Test script to verify videocapture server works with authentication disabled
"""
import os
import sys
import asyncio

# Disable authentication for testing
os.environ['AGENT_EXT_AUTH_ENABLED'] = '0'

# Add src to path
sys.path.insert(0, 'src')

from mcp_agent_videocapture import MCPAgentVideoCapture

async def test_auth_disabled():
    """Test that authentication headers are empty when disabled"""
    server = MCPAgentVideoCapture()
    
    # Test auth header generation
    headers = server._get_auth_headers("GET", "/health")
    
    print("🔍 Testing authentication disabled...")
    print(f"AGENT_EXT_AUTH_ENABLED = {os.environ.get('AGENT_EXT_AUTH_ENABLED', 'not set')}")
    print(f"Auth headers: {headers}")
    
    if not headers:
        print("✅ Authentication correctly disabled - no auth headers generated")
        return True
    else:
        print("❌ Authentication still enabled - headers present")
        return False

if __name__ == "__main__":
    success = asyncio.run(test_auth_disabled())
    sys.exit(0 if success else 1)