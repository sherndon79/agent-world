#!/usr/bin/env python3
"""
MCP Server for Agent WorldRecorder Extension

Provides Model Context Protocol interface to the Agent WorldRecorder extension
for video recording and frame capture in Isaac Sim.
"""

import asyncio
import sys
import os
import logging
from typing import Any, Dict, List, Optional
from datetime import datetime

import aiohttp

# Add shared modules to path
shared_path = os.path.join(os.path.dirname(__file__), '..', '..', 'shared')
if shared_path not in sys.path:
    sys.path.insert(0, shared_path)

# Import shared modules
from logging_setup import setup_logging
from mcp_base_client import MCPBaseClient

# Add agentworld-extensions to path for unified config
extensions_path = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'agentworld-extensions')
if os.path.exists(extensions_path) and extensions_path not in sys.path:
    sys.path.insert(0, extensions_path)

try:
    from agent_world_config import create_worldrecorder_config
    config = create_worldrecorder_config()
except ImportError:
    # Fallback if unified config not available
    config = None
from mcp.server import Server
from mcp.server.models import InitializationOptions
from mcp.server.stdio import stdio_server
from mcp.server.lowlevel import NotificationOptions
from mcp.types import Tool, TextContent


class WorldRecorderResponseFormatter:
    """Unified response formatting for world recorder operations"""
    
    SUCCESS_TEMPLATES = {
        'start_video': "🎥 Video recording started: {output_path}",
        'cancel_video': "⏹️ Video recording cancelled",
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
            # Support both legacy {status: {...}} and new flat schema
            status = response.get('status') or response
            message = "📊 WorldRecorder Status:\n"

            # Determine recording/active state from available fields
            if 'recording' in status:
                recording = bool(status.get('recording'))
                message += f"• Recording: {'🔴 Active' if recording else '⚪ Stopped'}\n"
            elif 'done' in status:
                done = bool(status.get('done'))
                sid = status.get('session_id')
                recording = bool(sid) and not done
                message += f"• Recording: {'🔴 Active' if recording else '⚪ Stopped'}\n"
                message += f"• Done: {done}\n"
            
            # Common fields across versions
            if status.get('session_id'):
                message += f"• Session ID: {status['session_id']}\n"
            if status.get('last_session_id'):
                message += f"• Last Session ID: {status['last_session_id']}\n"
            if status.get('output_path'):
                message += f"• Output: {status['output_path']}\n"
            
            # Outputs list (new API)
            outputs = status.get('outputs')
            if isinstance(outputs, list) and outputs:
                if len(outputs) == 1:
                    message += f"• Output: {outputs[0]}\n"
                else:
                    message += f"• Outputs ({len(outputs)}):\n"
                    for p in outputs[:5]:
                        message += f"  - {p}\n"
                    if len(outputs) > 5:
                        message += f"  - ... and {len(outputs) - 5} more\n"
            
            # Timing/telemetry if provided
            if status.get('duration') is not None:
                try:
                    message += f"• Duration: {float(status['duration']):.2f}s\n"
                except Exception:
                    pass
            if status.get('fps') is not None:
                message += f"• FPS: {status['fps']}\n"
            if status.get('timestamp') is not None:
                try:
                    from datetime import datetime
                    ts = float(status['timestamp'])
                    message += f"• Timestamp: {datetime.fromtimestamp(ts).isoformat()}\n"
                except Exception:
                    message += f"• Timestamp: {status['timestamp']}\n"
        
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
        
        # Initialize unified auth client
        self.client = MCPBaseClient("WORLDRECORDER", self.base_url)
        
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
    
    async def _initialize_client(self):
        """Initialize the unified auth client"""
        if not self.client._initialized:
            await self.client.initialize()
    
    async def __aenter__(self):
        """Async context manager entry"""
        await self._initialize_client()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.client.close()
    
    
    def _get_timeout(self, operation: str) -> float:
        """Get timeout for specific operation"""
        return self.timeouts.get(operation, self.timeouts['standard'])
    
    # (Auth headers handled by MCPBaseClient)
    
    async def _make_request(
        self, 
        method: str, 
        endpoint: str, 
        data: Optional[Dict] = None,
        timeout_key: str = 'standard'
    ) -> Dict:
        """Make HTTP request using unified auth client"""
        try:
            await self._initialize_client()
            
            if method.upper() == 'GET':
                return await self.client.get(endpoint)
            elif method.upper() == 'POST':
                return await self.client.post(endpoint, json=data)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
                
        except aiohttp.ClientError as e:
            raise aiohttp.ClientError(f"Could not connect to WorldRecorder extension at {self.base_url}. "
                                    f"Ensure Isaac Sim is running and WorldRecorder extension is enabled.")
        except Exception as e:
            raise Exception(f"Request failed: {str(e)}")
    
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
                    name="worldrecorder_metrics_prometheus", 
                    description="Get WorldRecorder metrics in Prometheus format for monitoring systems",
                    inputSchema={
                        "type": "object",
                        "properties": {},
                        "required": []
                    }
                ),
                Tool(
                    name="worldrecorder_cleanup_frames",
                    description="Manually clean up temporary frame directories for a session or output path",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "session_id": {
                                "type": "string",
                                "description": "Session ID to clean up (will use session's output path)"
                            },
                            "output_path": {
                                "type": "string", 
                                "description": "Direct output path to clean up frame directories for"
                            }
                        },
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
                            },
                            "cleanup_frames": {
                                "type": "boolean",
                                "description": "Automatically clean up temporary frame directories after recording",
                                "default": True
                            }
                        },
                        "required": ["output_path", "duration_sec"]
                    }
                ),
                Tool(
                    name="worldrecorder_start_recording",
                    description="Start recording via recording/* API (alias of video/start)",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "output_path": {"type": "string", "description": "Output file path"},
                            "fps": {"type": "number", "default": 30, "minimum": 1, "maximum": 120},
                            "duration_sec": {"type": "number", "minimum": 0.1, "maximum": 86400},
                            "width": {"type": "integer", "minimum": 64, "maximum": 7680},
                            "height": {"type": "integer", "minimum": 64, "maximum": 4320},
                            "file_type": {"type": "string", "enum": [".mp4", ".avi", ".mov"], "default": ".mp4"},
                            "session_id": {"type": "string"},
                            "show_progress": {"type": "boolean", "default": False},
                            "cleanup_frames": {"type": "boolean", "description": "Automatically clean up temporary frame directories after recording", "default": True}
                        },
                        "required": ["output_path", "duration_sec"]
                    }
                ),
                Tool(
                    name="worldrecorder_cancel_recording",
                    description="Cancel recording via recording/* API - stops capture without encoding",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "session_id": {"type": "string", "description": "Optional session id"}
                        },
                        "required": []
                    }
                ),
                Tool(
                    name="worldrecorder_recording_status",
                    description="Get recording status via recording/* API",
                    inputSchema={
                        "type": "object",
                        "properties": {},
                        "required": []
                    }
                ),
                Tool(
                    name="worldrecorder_cancel_video",
                    description="Cancel current video recording - stops capture without encoding",
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
                elif name == "worldrecorder_cancel_video":
                    return await self._cancel_video(arguments)
                elif name == "worldrecorder_capture_frame":
                    return await self._capture_frame(arguments)
                elif name == "worldrecorder_get_status":
                    return await self._get_status(arguments)
                elif name == "worldrecorder_get_metrics":
                    return await self._get_metrics(arguments)
                elif name == "worldrecorder_metrics_prometheus":
                    return await self._metrics_prometheus(arguments)
                elif name == "worldrecorder_cleanup_frames":
                    return await self._cleanup_frames(arguments)
                elif name == "worldrecorder_start_recording":
                    return await self._start_recording(arguments)
                elif name == "worldrecorder_cancel_recording":
                    return await self._cancel_recording(arguments)
                elif name == "worldrecorder_recording_status":
                    return await self._recording_status(arguments)
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
        
        except aiohttp.ClientError as e:
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
        
        except aiohttp.ClientError as e:
            return [TextContent(
                type="text",
                text=self.formatter.format_error("start_video", str(e))
            )]
        except Exception as e:
            return [TextContent(
                type="text",
                text=self.formatter.format_error("start_video", f"Unexpected error: {str(e)}")
            )]
    
    async def _cancel_video(self, arguments: Dict[str, Any]) -> List[TextContent]:
        """Cancel current video recording - stops capture without encoding"""
        try:
            response = await self._make_request("POST", "/video/cancel", arguments, "video_cancel")
            return [TextContent(
                type="text",
                text=self.formatter.format_success("cancel_video", response)
            )]
        
        except aiohttp.ClientError as e:
            return [TextContent(
                type="text",
                text=self.formatter.format_error("cancel_video", str(e))
            )]
        except Exception as e:
            return [TextContent(
                type="text",
                text=self.formatter.format_error("cancel_video", f"Unexpected error: {str(e)}")
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
        
        except aiohttp.ClientError as e:
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
            response = await self._make_request("GET", "/video/status")
            if response.get('success'):
                return [TextContent(
                    type="text",
                    text=self.formatter.format_success("get_status", response)
                )]
            else:
                return [TextContent(type="text", text=f"❌ {response.get('error', 'Unknown error')}")]
        
        except aiohttp.ClientError as e:
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
        
        except aiohttp.ClientError as e:
            return [TextContent(
                type="text",
                text=self.formatter.format_error("get_metrics", str(e))
            )]
        except Exception as e:
            return [TextContent(
                type="text",
                text=self.formatter.format_error("get_metrics", f"Unexpected error: {str(e)}")
            )]

    async def _metrics_prometheus(self, arguments: Dict[str, Any]) -> List[TextContent]:
        """Get WorldRecorder metrics in Prometheus format"""
        try:
            response = await self._make_request("GET", "/metrics.prom")
            # Response is raw text; if dict, stringify
            if isinstance(response, dict) and 'prometheus_metrics' in response:
                prom_text = response.get('prometheus_metrics')
            elif isinstance(response, dict) and '_raw_text' in response:
                prom_text = response.get('_raw_text')
            else:
                prom_text = str(response)
            return [TextContent(type="text", text=f"📊 **WorldRecorder Prometheus Metrics**\n\n```\n{prom_text}\n```")]
        except aiohttp.ClientError as e:
            return [TextContent(type="text", text=self.formatter.format_error("get_metrics", str(e)))]
        except Exception as e:
            return [TextContent(type="text", text=self.formatter.format_error("get_metrics", f"Unexpected error: {str(e)}"))]

    async def _start_recording(self, arguments: Dict[str, Any]) -> List[TextContent]:
        """Start recording via recording/* API"""
        try:
            response = await self._make_request("POST", "/recording/start", arguments, "video_start")
            return [TextContent(type="text", text=self.formatter.format_success("start_video", response, **arguments))]
        except aiohttp.ClientError as e:
            return [TextContent(type="text", text=self.formatter.format_error("start_video", str(e)))]
        except Exception as e:
            return [TextContent(type="text", text=self.formatter.format_error("start_video", f"Unexpected error: {str(e)}"))]

    async def _cancel_recording(self, arguments: Dict[str, Any]) -> List[TextContent]:
        """Cancel recording via recording/* API - stops capture without encoding"""
        try:
            response = await self._make_request("POST", "/recording/cancel", arguments, "video_cancel")
            return [TextContent(type="text", text=self.formatter.format_success("cancel_video", response))]
        except aiohttp.ClientError as e:
            return [TextContent(type="text", text=self.formatter.format_error("cancel_video", str(e)))]
        except Exception as e:
            return [TextContent(type="text", text=self.formatter.format_error("cancel_video", f"Unexpected error: {str(e)}"))]

    async def _recording_status(self, arguments: Dict[str, Any]) -> List[TextContent]:
        """Get recording status via recording/* API"""
        try:
            response = await self._make_request("GET", "/recording/status")
            if response.get('success'):
                return [TextContent(type="text", text=self.formatter.format_success("get_status", response))]
            else:
                return [TextContent(type="text", text=f"❌ {response.get('error', 'Unknown error')}")]
        except aiohttp.ClientError as e:
            return [TextContent(type="text", text=self.formatter.format_error("get_status", str(e)))]
        except Exception as e:
            return [TextContent(type="text", text=self.formatter.format_error("get_status", f"Unexpected error: {str(e)}"))]

    async def _cleanup_frames(self, arguments: Dict[str, Any]) -> List[TextContent]:
        """Manually clean up temporary frame directories"""
        try:
            response = await self._make_request("POST", "/cleanup/frames", arguments, "cleanup")
            if response.get('success'):
                count = response.get('count', 0)
                if count > 0:
                    cleaned_dirs = response.get('cleaned_directories', [])
                    message = f"🧹 Cleaned up {count} frame director{'y' if count == 1 else 'ies'}"
                    if len(cleaned_dirs) <= 3:
                        message += f":\n• " + "\n• ".join(cleaned_dirs)
                    else:
                        message += f":\n• " + "\n• ".join(cleaned_dirs[:3]) + f"\n• ... and {len(cleaned_dirs)-3} more"
                else:
                    message = "🧹 No frame directories found to clean up"
                return [TextContent(type="text", text=message)]
            else:
                error_msg = response.get('error', 'Unknown error')
                return [TextContent(type="text", text=f"❌ Cleanup failed: {error_msg}")]
        except aiohttp.ClientError as e:
            return [TextContent(type="text", text=self.formatter.format_error("cleanup", str(e)))]
        except Exception as e:
            return [TextContent(type="text", text=self.formatter.format_error("cleanup", f"Unexpected error: {str(e)}"))]
    
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
                await self.client.close()
            except Exception as e:
                logging.getLogger(__name__).error(f"Error during cleanup: {e}")
        
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
            logging.getLogger(__name__).info("Server interrupted, shutting down...")
        except Exception as e:
            logging.getLogger(__name__).error(f"Server error: {e}")
        finally:
            await cleanup()


async def main():
    """Main entry point"""
    setup_logging('worldrecorder')
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
