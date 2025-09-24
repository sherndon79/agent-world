#!/usr/bin/env python3
"""
World* Extensions Naming Consistency Audit

Checks for uniform naming patterns across all extensions to ensure
consistent user experience and cognitive load reduction.
"""

import re
import os
from pathlib import Path
from typing import Dict, List, Set

def extract_http_endpoints_detailed(file_path):
    """Extract HTTP endpoints with full routing details."""
    endpoints = {}
    try:
        with open(file_path, 'r') as f:
            content = f.read()
        
        # Find all routing patterns
        route_patterns = [
            r"elif endpoint == '([^']+)':",
            r'elif endpoint == "([^"]+)":',
            r"endpoint == '([^']+)'",
            r'endpoint == "([^"]+)"'
        ]
        
        for pattern in route_patterns:
            matches = re.findall(pattern, content)
            for match in matches:
                if match not in ['docs', 'openapi.json']:  # Skip meta endpoints
                    endpoints[match] = 'http'
        
        return endpoints
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
        return {}

def extract_mcp_tools_detailed(file_path):
    """Extract MCP tools with naming patterns."""
    tools = {}
    try:
        with open(file_path, 'r') as f:
            content = f.read()
        
        # Find tool definitions with descriptions
        tool_pattern = r'name="([^"]+)",\s*description="([^"]*)"'
        matches = re.findall(tool_pattern, content, re.MULTILINE | re.DOTALL)
        
        for name, desc in matches:
            tools[name] = desc.split('\n')[0]  # First line of description
        
        return tools
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
        return {}

def analyze_naming_patterns():
    """Analyze naming consistency across extensions."""

    # Resolve repo root dynamically so the script works from any clone path
    base_path = Path(__file__).resolve().parents[2]
    
    extensions = {
        'worldsurveyor': {
            'http': base_path / "isaac-sim-host-5.0.0/isaac-extension/omni.agent.worldsurveyor/omni/agent/worldsurveyor/http_handler.py",
            'mcp': base_path / "mcp-servers/worldsurveyor/src/mcp_worldsurveyor.py",
            'prefix': 'worldsurveyor'
        },
        'worldbuilder': {
            'http': base_path / "isaac-sim-host-5.0.0/isaac-extension/omni.agent.worldbuilder/omni/agent/worldbuilder/http_handler.py", 
            'mcp': base_path / "mcp-servers/worldbuilder/src/mcp_agent_worldbuilder.py",
            'prefix': 'worldbuilder'  # Now consistent!
        },
        'worldviewer': {
            'http': base_path / "isaac-sim-host-5.0.0/isaac-extension/omni.agent.worldviewer/omni/agent/worldviewer/http_handler.py",
            'mcp': base_path / "mcp-servers/worldviewer/src/mcp_agent_worldviewer.py",
            'prefix': 'worldviewer'
        },
        'worldrecorder': {
            'http': base_path / "isaac-sim-host-5.0.0/isaac-extension/omni.agent.worldrecorder/omni/agent/worldrecorder/http_handler.py",
            'mcp': base_path / "mcp-servers/worldrecorder-server/src/mcp_agent_worldrecorder.py",
            'prefix': 'worldrecorder'
        }
    }
    
    print("🔍 **NAMING CONSISTENCY AUDIT**")
    print("=" * 50)
    
    # Check MCP tool naming prefixes
    print("\n📋 **MCP Tool Prefixes:**")
    prefix_consistency = True
    for ext_name, paths in extensions.items():
        if paths['mcp'].exists():
            tools = extract_mcp_tools_detailed(paths['mcp'])
            actual_prefix = None
            
            for tool_name in tools.keys():
                if '_' in tool_name:
                    actual_prefix = tool_name.split('_')[0]
                    break
            
            expected_prefix = paths['prefix'] 
            status = "✅" if actual_prefix == expected_prefix else "❌"
            if actual_prefix != expected_prefix:
                prefix_consistency = False
                
            print(f"{status} {ext_name}: {actual_prefix} (expected: {expected_prefix})")
    
    # Check common endpoint patterns
    print(f"\n📋 **Common Endpoints Consistency:**")
    common_endpoints = ['health', 'metrics', 'scene_status', 'get_scene']
    
    for endpoint in common_endpoints:
        print(f"\n• **{endpoint}** endpoint:")
        
        for ext_name, paths in extensions.items():
            if not paths['http'].exists() or not paths['mcp'].exists():
                continue
                
            http_endpoints = extract_http_endpoints_detailed(paths['http'])
            mcp_tools = extract_mcp_tools_detailed(paths['mcp'])
            
            # Check HTTP endpoint
            has_http = endpoint in http_endpoints
            
            # Check MCP tool (with prefix)
            expected_mcp = f"{paths['prefix']}_{endpoint}"
            has_mcp = expected_mcp in mcp_tools
            
            # Alternative naming patterns
            alternatives = [
                f"{paths['prefix']}_extension_health" if endpoint == 'health' else None,
                f"{paths['prefix']}_get_metrics" if endpoint == 'metrics' else None,
            ]
            
            alt_match = any(alt in mcp_tools for alt in alternatives if alt)
            
            http_status = "✅" if has_http else "❌"
            mcp_status = "✅" if has_mcp or alt_match else "❌"
            
            if alt_match and not has_mcp:
                alt_name = next(alt for alt in alternatives if alt and alt in mcp_tools)
                mcp_status += f" ({alt_name})"
                
            print(f"  {ext_name}: HTTP {http_status} | MCP {mcp_status}")
    
    # Summary
    print(f"\n📊 **CONSISTENCY SUMMARY**")
    print("=" * 30)
    print(f"MCP Prefix Consistency: {'✅ Perfect' if prefix_consistency else '❌ Issues Found'}")
    
    if not prefix_consistency:
        print(f"\n🎯 **CRITICAL ISSUE:** WorldBuilder uses 'isaac_' prefix while others use extension names")
        print(f"   This creates cognitive load for users who must remember different patterns")
        print(f"   **Recommendation:** Standardize all extensions to use extension name prefix")

if __name__ == "__main__":
    analyze_naming_patterns()
