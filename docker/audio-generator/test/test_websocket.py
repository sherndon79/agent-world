#!/usr/bin/env python3
"""
Test script to verify audio container WebSocket functionality.

Usage:
    python test_websocket.py
"""

import asyncio
import json
import sys

async def test_audio_container():
    """Test audio container endpoints"""
    import aiohttp

    base_url = "http://localhost:8080"

    print("🧪 Testing Audio Generator Container...")
    print()

    # Test 1: Health check
    print("1️⃣  Testing health endpoint...")
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{base_url}/health") as resp:
                data = await resp.json()
                print(f"   ✅ Health: {data}")
                print()
    except Exception as e:
        print(f"   ❌ Health check failed: {e}")
        print()
        return False

    # Test 2: Status check
    print("2️⃣  Testing status endpoint...")
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{base_url}/status") as resp:
                data = await resp.json()
                print(f"   ✅ Status:")
                print(f"      - WebSocket connected: {data.get('ws_connected')}")
                print(f"      - Client ID: {data.get('client_id')}")
                print(f"      - Channels: {len(data.get('channels', []))}")
                print()
    except Exception as e:
        print(f"   ❌ Status check failed: {e}")
        print()
        return False

    # Test 3: Trigger narration
    print("3️⃣  Testing narration API...")
    try:
        async with aiohttp.ClientSession() as session:
            payload = {
                "data": {
                    "text": "Testing narration from API",
                    "voice": "default",
                    "emotion": "neutral"
                },
                "metadata": {
                    "test": True
                }
            }
            async with session.post(f"{base_url}/api/narration", json=payload) as resp:
                data = await resp.json()
                print(f"   ✅ Narration: {data}")
                print()
    except Exception as e:
        print(f"   ❌ Narration test failed: {e}")
        print()
        return False

    # Test 4: Trigger ambient update
    print("4️⃣  Testing ambient API...")
    try:
        async with aiohttp.ClientSession() as session:
            payload = {
                "data": {
                    "environment": "forest",
                    "time_of_day": "evening",
                    "weather": "calm"
                }
            }
            async with session.post(f"{base_url}/api/ambient", json=payload) as resp:
                data = await resp.json()
                print(f"   ✅ Ambient: {data}")
                print()
    except Exception as e:
        print(f"   ❌ Ambient test failed: {e}")
        print()
        return False

    print("✨ All tests passed!")
    return True

if __name__ == "__main__":
    try:
        result = asyncio.run(test_audio_container())
        sys.exit(0 if result else 1)
    except KeyboardInterrupt:
        print("\n⚠️  Test interrupted")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Test failed: {e}")
        sys.exit(1)
