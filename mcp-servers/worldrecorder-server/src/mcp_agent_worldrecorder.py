#!/usr/bin/env python3
"""
MCP Server for Agent WorldRecorder Extension

Provides Model Context Protocol interface to the Agent WorldRecorder extension
for video recording and frame capture in Isaac Sim.
"""

import asyncio
import json
import sys
import os
from typing import Any, Dict, List, Optional
from datetime import datetime
import hashlib
import hmac
import time

import httpx
from mcp.server import Server
from mcp.server.models import InitializationOptions
from mcp.server.stdio import stdio_server
from mcp.server.lowlevel import NotificationOptions
from mcp.types import Resource, Tool, TextContent, ImageContent, EmbeddedResource
import mcp.types as types


class WorldRecorderResponseFormatter:
    """Unified response formatting for world recorder operations"""
    
    SUCCESS_TEMPLATES = {
        'start_video': "🎥 Video recording started: {output_path}",
        'stop_video': "⏹️ Video recording stopped",
        'capture_frame': "📸 Frame capture started",
        'get_status': "📊 WorldRecorder Status",
        'health_check': "✅ Extension Health: {status}"
    }
    
    ERROR_TEMPLATE = "❌ {operation} failed: {error}"
    
    # User-friendly troubleshooting hints for common errors
    TROUBLESHOOTING_HINTS = {
        "Could not connect": "💡 Troubleshooting:\n• Ensure Isaac Sim is running\n• Check that WorldRecorder extension is enabled\n• Verify extension HTTP API is active on port 8892",
        "timed out": "💡 Troubleshooting:\n• Isaac Sim may be busy processing\n• Try reducing video resolution or frame rate\n• Check Isaac Sim console for errors",
        "Session not found": "💡 Troubleshooting:\n• Check if recording was started properly\n• Use /video/status to check current session\n• Recording may have already stopped or timed out",
        "Path not found": "💡 Troubleshooting:\n• Verify the output directory exists\n• Check file path permissions\n• Ensure sufficient disk space available",
        "HTTP 500": "💡 Troubleshooting:\n• Isaac Sim internal error occurred\n• Check Isaac Sim console logs\n• Try reloading the WorldRecorder extension\n• Restart Isaac Sim if issues persist"
    }
    
    @classmethod
    def format_success(cls, operation: str, response: Dict, **template_vars) -> str:
        """Format successful operation response"""
        template = cls.SUCCESS_TEMPLATES.get(operation, "✅ Operation successful")
        
        # Merge response data with template variables
        format_vars = {**template_vars, **response}
        
        try:
            message = template.format(**format_vars)
        except KeyError:
            # Fallback if template variables don't match
            message = template
        
        # Add additional details for specific operations
        if operation == 'start_video':
            if 'session_id' in response:
                message += f"\n• Session ID: {response['session_id']}"
            if 'fps' in response:
                message += f"\n• FPS: {response['fps']}"
            if 'duration_sec' in response:
                message += f"\n• Duration: {response['duration_sec']}s"
            if 'file_type' in response:
                message += f"\n• Format: {response['file_type']}"
        elif operation == 'stop_video':
            if 'duration' in response:
                message += f"\n• Duration: {response['duration']:.2f}s"
            if 'frames_captured' in response:
                message += f"\n• Frames captured: {response['frames_captured']}"
        elif operation == 'capture_frame':
            capture_mode = response.get('capture_mode', 'single')
            if capture_mode == 'sequence':
                message += f"\n• Session ID: {response.get('session_id', 'Unknown')}"
                if 'session_directory' in response:
                    message += f"\n• Session Directory: {response['session_directory']}"
                if 'duration_sec' in response:
                    message += f"\n• Duration: {response['duration_sec']}s"
                if 'interval_sec' in response:
                    message += f"\n• Interval: {response['interval_sec']}s"
                if 'estimated_frame_count' in response:
                    message += f"\n• Expected Frames: {response['estimated_frame_count']}"
                if 'frame_pattern' in response:
                    message += f"\n• Frame Pattern: {response['frame_pattern']}"
            else:
                if 'outputs' in response and response['outputs']:
                    message += f"\n• Output: {response['outputs'][0]}"
            if 'file_type' in response:
                message += f"\n• Format: {response['file_type']}"
        elif operation == 'get_status':
            status = response.get('status') or response
            message = "📊 WorldRecorder Status:\n"
            recording = status.get('recording', False)
            message += f"• Recording: {'🔴 Active' if recording else '⚪ Stopped'}\n"
            
            if status.get('session_id'):
                message += f"• Session ID: {status['session_id']}\n"
            if status.get('output_path'):
                message += f"• Output: {status['output_path']}\n"
            if status.get('duration'):
                message += f"• Duration: {status['duration']:.2f}s\n"
            if status.get('fps'):
                message += f"• FPS: {status['fps']}\n"
        
        return message
    
    @classmethod
    def format_error(cls, operation: str, error: str) -> str:
        """Format error response with troubleshooting hints"""
        message = cls.ERROR_TEMPLATE.format(operation=operation, error=error)
        
        # Add troubleshooting hints if available
        for hint_key, hint_text in cls.TROUBLESHOOTING_HINTS.items():
            if hint_key.lower() in error.lower():
                message += f"\n\n{hint_text}"
                break
        
        return message


class WorldRecorderMCP:
    """MCP Server for Isaac Sim WorldRecorder Extension"""
    
    def __init__(self, base_url: Optional[str] = None):
        """Initialize the MCP server with connection settings"""
        env_base = os.getenv("AGENT_WORLDRECORDER_BASE_URL")
        self.base_url = env_base or base_url or "http://localhost:8892"
        self.formatter = WorldRecorderResponseFormatter()
        
        # Authentication configuration
        self.auth_token = os.getenv("AGENT_WORLDRECORDER_AUTH_TOKEN") or os.getenv("AGENT_EXT_AUTH_TOKEN")
        self.hmac_secret = os.getenv("AGENT_WORLDRECORDER_HMAC_SECRET") or os.getenv("AGENT_EXT_HMAC_SECRET")
        
        # HTTP client configuration
        self._client_lock = asyncio.Lock()
        self._http_client: Optional[httpx.AsyncClient] = None
        
        # Timeouts configuration
        self.timeouts = {
            'standard': 30.0,  # Standard operations
            'video_start': 60.0,  # Video start can take longer
            'video_stop': 90.0,  # Video finalization can be slow
            'frame_capture': 45.0,  # Frame capture with processing
        }
        
        # Retry configuration
        self.retry_attempts = 3
        
        # Server instance
        self.server = Server("worldrecorder")
        
        # Setup tools
        self._setup_tools()
    
    async def _get_http_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client with connection pooling"""
        async with self._client_lock:
            if self._http_client is None:
                limits = httpx.Limits(
                    max_keepalive_connections=5,
                    max_connections=10,
                    keepalive_expiry=30.0
                )
                self._http_client = httpx.AsyncClient(
                    base_url=self.base_url,
                    limits=limits,
                    follow_redirects=True
                )
        return self._http_client
    
    async def _close_http_client(self):
        """Close HTTP client and cleanup connections"""
        async with self._client_lock:
            if self._http_client:
                await self._http_client.aclose()
                self._http_client = None
    
    def _get_timeout(self, operation: str) -> float:
        """Get timeout for specific operation"""
        return self.timeouts.get(operation, self.timeouts['standard'])
    
    def _get_auth_headers(self, method: str, endpoint: str) -> Dict[str, str]:
        """Generate authentication headers for requests"""
        headers = {}
        
        # Check if auth is disabled for troubleshooting
        auth_disabled = os.getenv('AGENT_EXT_AUTH_ENABLED', '1').lower() in ('0', 'false', 'no', 'off')
        if auth_disabled:
            return headers
        
        # Add Bearer token if available
        if self.auth_token:
            headers["Authorization"] = f"Bearer {self.auth_token}"
        
        # Add HMAC signature if secret is available
        if self.hmac_secret:
            timestamp = str(time.time())
            message = f"{method.upper()}|{endpoint}|{timestamp}".encode('utf-8')
            signature = hmac.new(
                self.hmac_secret.encode('utf-8'), 
                message, 
                hashlib.sha256
            ).hexdigest()
            
            headers.update({
                "X-Timestamp": timestamp,
                "X-Signature": signature
            })
        
        return headers
    
    async def _make_request(
        self, 
        method: str, 
        endpoint: str, 
        data: Optional[Dict] = None,
        timeout_key: str = 'standard'
    ) -> Dict:
        """Make HTTP request with retry logic and proper error handling"""
        client = await self._get_http_client()
        timeout = httpx.Timeout(self._get_timeout(timeout_key))
        
        # Generate authentication headers
        auth_headers = self._get_auth_headers(method, endpoint)
        
        for attempt in range(self.retry_attempts):
            try:
                if method.upper() == 'GET':
                    response = await client.get(endpoint, headers=auth_headers, timeout=timeout)
                elif method.upper() == 'POST':
                    response = await client.post(endpoint, headers=auth_headers, json=data, timeout=timeout)
                else:
                    raise ValueError(f"Unsupported HTTP method: {method}")
                
                response.raise_for_status()
                
                # Handle different content types
                content_type = response.headers.get('content-type', '').lower()
                if 'application/json' in content_type:
                    return response.json()
                else:
                    return {"response": response.text, "status_code": response.status_code}
            
            except httpx.ConnectError as e:
                if attempt == self.retry_attempts - 1:
                    raise httpx.ConnectError(f"Could not connect to WorldRecorder extension at {self.base_url}. "
                                           f"Ensure Isaac Sim is running and WorldRecorder extension is enabled.")
                await asyncio.sleep(0.5 * (attempt + 1))
            
            except httpx.TimeoutException as e:
                if attempt == self.retry_attempts - 1:
                    raise httpx.TimeoutException(f"Request timed out after {timeout.read}s")
                await asyncio.sleep(1.0 * (attempt + 1))
            
            except httpx.HTTPStatusError as e:
                # Don't retry on client errors (4xx)
                if 400 <= e.response.status_code < 500:
                    raise
                # Retry on server errors (5xx)
                if attempt == self.retry_attempts - 1:
                    raise
                await asyncio.sleep(1.0 * (attempt + 1))
    
    def _setup_tools(self):
        """Register all MCP tools"""
        
        # Register tool schemas
        @self.server.list_tools()
        async def handle_list_tools() -> List[Tool]:
            """List all available WorldRecorder tools."""
            return [
                Tool(
                    name="worldrecorder_health_check",
                    description="Check WorldRecorder extension health and connectivity",
                    inputSchema={
                        "type": "object",
                        "properties": {},
                        "required": []
                    }
                ),
                Tool(
                    name="worldrecorder_start_video",
                    description="Start continuous video recording in Isaac Sim viewport",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "output_path": {
                                "type": "string",
                                "description": "File path for video output (e.g., '/tmp/my_video.mp4')"
                            },
                            "fps": {
                                "type": "number",
                                "description": "Frames per second for recording",
                                "default": 30,
                                "minimum": 1,
                                "maximum": 120
                            },
                            "duration_sec": {
                                "type": "number", 
                                "description": "Recording duration in seconds",
                                "minimum": 0.1,
                                "maximum": 86400
                            },
                            "width": {
                                "type": "integer",
                                "description": "Video width in pixels (optional, uses viewport width if not specified)",
                                "minimum": 64,
                                "maximum": 7680
                            },
                            "height": {
                                "type": "integer", 
                                "description": "Video height in pixels (optional, uses viewport height if not specified)",
                                "minimum": 64,
                                "maximum": 4320
                            },
                            "file_type": {
                                "type": "string",
                                "enum": [".mp4", ".avi", ".mov"],
                                "description": "Video file format (auto-detected from output_path extension, fallback if no extension)",
                                "default": ".mp4"
                            },
                            "session_id": {
                                "type": "string",
                                "description": "Optional unique session identifier for tracking"
                            },
                            "show_progress": {
                                "type": "boolean",
                                "description": "Show progress UI during recording",
                                "default": False
                            }
                        },
                        "required": ["output_path", "duration_sec"]
                    }
                ),
                Tool(
                    name="worldrecorder_stop_video",
                    description="Stop current video recording and finalize output file",
                    inputSchema={
                        "type": "object",
                        "properties": {},
                        "required": []
                    }
                ),
                Tool(
                    name="worldrecorder_capture_frame",
                    description="Capture a single frame or frame sequence from Isaac Sim viewport",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "output_path": {
                                "type": "string",
                                "description": "File path for image output (single frame) or base directory for frame sequences (e.g., '/tmp/frame.png' or '/tmp/experiment_frames/')"
                            },
                            "duration_sec": {
                                "type": "number",
                                "description": "Total capture duration for sequences (optional - if provided with interval_sec or frame_count, captures frame sequence)",
                                "minimum": 0.1,
                                "maximum": 86400
                            },
                            "interval_sec": {
                                "type": "number", 
                                "description": "Time between frames for sequences (optional - mutually exclusive with frame_count)",
                                "minimum": 0.1,
                                "maximum": 3600
                            },
                            "frame_count": {
                                "type": "integer",
                                "description": "Total number of frames to capture over duration (optional - mutually exclusive with interval_sec)",
                                "minimum": 1,
                                "maximum": 100000
                            },
                            "width": {
                                "type": "integer",
                                "description": "Image width in pixels (optional, uses viewport width if not specified)",
                                "minimum": 64,
                                "maximum": 7680
                            },
                            "height": {
                                "type": "integer",
                                "description": "Image height in pixels (optional, uses viewport height if not specified)", 
                                "minimum": 64,
                                "maximum": 4320
                            },
                            "file_type": {
                                "type": "string",
                                "enum": [".png", ".jpg", ".jpeg", ".bmp", ".tiff"],
                                "description": "Image file format (auto-detected from output_path extension, fallback if no extension)",
                                "default": ".png"
                            }
                        },
                        "required": ["output_path"]
                    }
                ),
                Tool(
                    name="worldrecorder_get_status",
                    description="Get current video recording status and session information",
                    inputSchema={
                        "type": "object",
                        "properties": {},
                        "required": []
                    }
                ),
                Tool(
                    name="worldrecorder_get_metrics",
                    description="Get WorldRecorder extension performance metrics and statistics", 
                    inputSchema={
                        "type": "object",
                        "properties": {},
                        "required": []
                    }
                )
            ]
        
        @self.server.call_tool()
        async def handle_call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
            """Handle tool calls and route to appropriate WorldRecorder API endpoints."""
            
            try:
                if name == "worldrecorder_health_check":
                    return await self._health_check(arguments)
                elif name == "worldrecorder_start_video":
                    return await self._start_video(arguments)
                elif name == "worldrecorder_stop_video":
                    return await self._stop_video(arguments)
                elif name == "worldrecorder_capture_frame":
                    return await self._capture_frame(arguments)
                elif name == "worldrecorder_get_status":
                    return await self._get_status(arguments)
                elif name == "worldrecorder_get_metrics":
                    return await self._get_metrics(arguments)
                else:
                    return [TextContent(
                        type="text",
                        text=f"❌ Unknown tool: {name}"
                    )]
                    
            except Exception as e:
                return [TextContent(
                    type="text",
                    text=f"❌ Error executing {name}: {str(e)}"
                )]
    
    async def _health_check(self, arguments: Dict[str, Any]) -> List[TextContent]:
        """Check WorldRecorder extension health and connectivity"""
        try:
            response = await self._make_request("GET", "/health")
            if response.get('success'):
                return [TextContent(
                    type="text",
                    text=f"✅ WorldRecorder Health\n" +
                         f"• Service: {response.get('service', 'Unknown')}\n" +
                         f"• Version: {response.get('version', 'Unknown')}\n" +
                         f"• URL: {response.get('url', 'Unknown')}\n" +
                         f"• Timestamp: {response.get('timestamp', 'Unknown')}\n" +
                         f"• Recording Active: {response.get('recording_active', False)}"
                )]
            else:
                return [TextContent(type="text", text=f"❌ {response.get('error', 'Unknown error')}")]
        
        except httpx.RequestError as e:
            return [TextContent(
                type="text",
                text=f"❌ Connection error: {str(e)}"
            )]
        except Exception as e:
            return [TextContent(
                type="text",
                text=f"❌ Unexpected error: {str(e)}"
            )]
    
    async def _start_video(self, arguments: Dict[str, Any]) -> List[TextContent]:
        """Start video recording in Isaac Sim viewport"""
        try:
            # Validate required parameters
            if not arguments.get("output_path"):
                return [TextContent(
                    type="text",
                    text="❌ Missing required parameter: output_path"
                )]
            
            response = await self._make_request("POST", "/video/start", arguments, "video_start")
            return [TextContent(
                type="text", 
                text=self.formatter.format_success("start_video", response, **arguments)
            )]
        
        except httpx.RequestError as e:
            return [TextContent(
                type="text",
                text=self.formatter.format_error("start_video", str(e))
            )]
        except Exception as e:
            return [TextContent(
                type="text",
                text=self.formatter.format_error("start_video", f"Unexpected error: {str(e)}")
            )]
    
    async def _stop_video(self, arguments: Dict[str, Any]) -> List[TextContent]:
        """Stop current video recording and finalize output file"""
        try:
            response = await self._make_request("POST", "/video/stop", arguments, "video_stop")
            return [TextContent(
                type="text",
                text=self.formatter.format_success("stop_video", response)
            )]
        
        except httpx.RequestError as e:
            return [TextContent(
                type="text",
                text=self.formatter.format_error("stop_video", str(e))
            )]
        except Exception as e:
            return [TextContent(
                type="text",
                text=self.formatter.format_error("stop_video", f"Unexpected error: {str(e)}")
            )]
    
    async def _capture_frame(self, arguments: Dict[str, Any]) -> List[TextContent]:
        """Capture a single frame from Isaac Sim viewport"""
        try:
            # Validate required parameters
            if not arguments.get("output_path"):
                return [TextContent(
                    type="text",
                    text="❌ Missing required parameter: output_path"
                )]
            
            response = await self._make_request("POST", "/viewport/capture_frame", arguments, "frame_capture")
            return [TextContent(
                type="text",
                text=self.formatter.format_success("capture_frame", response, **arguments)
            )]
        
        except httpx.RequestError as e:
            return [TextContent(
                type="text",
                text=self.formatter.format_error("capture_frame", str(e))
            )]
        except Exception as e:
            return [TextContent(
                type="text",
                text=self.formatter.format_error("capture_frame", f"Unexpected error: {str(e)}")
            )]
    
    async def _get_status(self, arguments: Dict[str, Any]) -> List[TextContent]:
        """Get current video recording status and session information"""
        try:
            response = await self._make_request("GET", "/status")
            if response.get('success'):
                return [TextContent(
                    type="text",
                    text=f"📹 WorldRecorder Status\n" +
                         f"• Status: {response.get('status', 'Unknown')}\n" +
                         f"• Extension: {response.get('extension', 'Unknown')}\n" +
                         f"• Timestamp: {response.get('timestamp', 'Unknown')}"
                )]
            else:
                return [TextContent(type="text", text=f"❌ {response.get('error', 'Unknown error')}")]
        
        except httpx.RequestError as e:
            return [TextContent(
                type="text",
                text=self.formatter.format_error("get_status", str(e))
            )]
        except Exception as e:
            return [TextContent(
                type="text",
                text=self.formatter.format_error("get_status", f"Unexpected error: {str(e)}")
            )]
    
    async def _get_metrics(self, arguments: Dict[str, Any]) -> List[TextContent]:
        """Get WorldRecorder extension performance metrics and statistics"""
        try:
            response = await self._make_request("GET", "/metrics")
            
            # Format metrics nicely
            if isinstance(response, dict):
                metrics_text = "📊 WorldRecorder Metrics:\n"
                for key, value in response.items():
                    if isinstance(value, dict):
                        metrics_text += f"\n• {key}:\n"
                        for sub_key, sub_value in value.items():
                            metrics_text += f"  - {sub_key}: {sub_value}\n"
                    else:
                        metrics_text += f"• {key}: {value}\n"
            else:
                metrics_text = str(response)
            
            return [TextContent(
                type="text",
                text=metrics_text
            )]
        
        except httpx.RequestError as e:
            return [TextContent(
                type="text",
                text=self.formatter.format_error("get_metrics", str(e))
            )]
        except Exception as e:
            return [TextContent(
                type="text",
                text=self.formatter.format_error("get_metrics", f"Unexpected error: {str(e)}")
            )]
    
    async def run(self):
        """Run the MCP server"""
        # Handle server lifecycle
        @self.server.set_logging_level()
        async def set_logging_level(level):
            import logging
            logging.getLogger().setLevel(getattr(logging, level.upper()))
        
        # Cleanup on shutdown
        async def cleanup():
            """Cleanup resources and close connections."""
            try:
                await self._close_http_client()
            except Exception as e:
                print(f"Error during cleanup: {e}", file=sys.stderr)
        
        try:
            # Initialize and run server
            async with stdio_server() as (read_stream, write_stream):
                await self.server.run(
                    read_stream,
                    write_stream,
                    InitializationOptions(
                        server_name="worldrecorder",
                        server_version="1.0.0",
                        capabilities=self.server.get_capabilities(
                            notification_options=NotificationOptions(),
                            experimental_capabilities={}
                        )
                    )
                )
        except KeyboardInterrupt:
            print("Server interrupted, shutting down...", file=sys.stderr)
        except Exception as e:
            print(f"Server error: {e}", file=sys.stderr)
        finally:
            await cleanup()


async def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description="MCP Server for Isaac Sim WorldRecorder Extension")
    parser.add_argument(
        "--base-url", 
        default=None,
        help="Base URL for WorldRecorder extension API (default: http://localhost:8892)"
    )
    
    args = parser.parse_args()
    
    # Create and run server
    server = WorldRecorderMCP(base_url=args.base_url)
    await server.run()


if __name__ == "__main__":
    asyncio.run(main())