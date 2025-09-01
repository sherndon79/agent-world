#!/usr/bin/env python3
"""
MCP Server for Agent WorldViewer Extension

Provides Model Context Protocol interface to the Agent WorldViewer extension
for camera control and viewport management in Isaac Sim.
"""

import asyncio
import json
import sys
import os
from typing import Any, Dict, List, Optional

import aiohttp
from logging_setup import setup_logging

# Add shared modules to path
shared_path = os.path.join(os.path.dirname(__file__), '..', '..', 'shared')
if shared_path not in sys.path:
    sys.path.insert(0, shared_path)

# Import unified auth client
from mcp_base_client import MCPBaseClient
from mcp.server import Server
from mcp.server.models import InitializationOptions
from mcp.server.stdio import stdio_server
from mcp.server.lowlevel import NotificationOptions
from mcp.types import Tool, TextContent


def get_movement_style_schema(shot_type: str) -> Dict:
    """
    Generate movement_style schema property for a specific shot type.
    This dynamically creates the enum based on available styles for the shot.
    """
    # Style mappings for each shot type - these match CINEMATIC_STYLES in cinematic_controller_sync.py
    style_mappings = {}
    
    styles = style_mappings.get(shot_type, ["standard"])
    
    return {
        "type": "string",
        "enum": styles,
        "default": "standard",
        "description": f"Movement style for {shot_type.replace('_', ' ')} - affects timing, easing, and cinematic characteristics"
    }


class CameraResponseFormatter:
    """Unified response formatting for camera operations"""
    
    SUCCESS_TEMPLATES = {
        'set_position': "✅ Camera position set to {position}",
        'frame_object': "✅ Camera framed on object: {object_path}",
        'orbit_camera': "✅ Camera positioned in orbit around {center}",
        'get_status': "📷 Camera Status",
        'health_check': "✅ Extension Health: {status}"
    }
    
    ERROR_TEMPLATE = "❌ {operation} failed: {error}"
    
    # User-friendly troubleshooting hints for common errors
    TROUBLESHOOTING_HINTS = {
        "Could not connect": "💡 Troubleshooting:\n• Ensure Isaac Sim is running\n• Check that WorldViewer extension is enabled\n• Verify extension HTTP API is active on port 8900",
        "timed out": "💡 Troubleshooting:\n• Isaac Sim may be busy processing\n• Try reducing queue load or wait a moment\n• Check Isaac Sim console for errors",
        "Object not found": "💡 Troubleshooting:\n• Verify the USD path exists (e.g., '/World/my_object')\n• Check object spelling and case sensitivity\n• Use WorldBuilder MCP to list scene elements",
        "No viewport connection": "💡 Troubleshooting:\n• Ensure Isaac Sim viewport is active\n• Try reloading the WorldViewer extension\n• Check Isaac Sim camera setup",
        "HTTP 500": "💡 Troubleshooting:\n• Isaac Sim internal error occurred\n• Check Isaac Sim console logs\n• Try reloading the WorldViewer extension\n• Restart Isaac Sim if issues persist"
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
        if operation == 'set_position':
            if 'target' in format_vars and format_vars['target']:
                message += f" looking at {format_vars['target']}"
        elif operation == 'frame_object':
            if 'calculated_distance' in response:
                message += f" (distance: {response['calculated_distance']:.2f})"
        elif operation == 'orbit_camera':
            if all(k in format_vars for k in ['distance', 'elevation', 'azimuth']):
                message += f"\n• Distance: {format_vars['distance']}"
                message += f"\n• Elevation: {format_vars['elevation']}°"
                message += f"\n• Azimuth: {format_vars['azimuth']}°"
        elif operation == 'get_status':
            camera_status = response.get('camera_status') or response
            message = "📷 Camera Status:\n"
            connected = camera_status.get('connected', 'Unknown')
            message += f"• Connected: {connected}\n"
            
            if camera_status.get('position'):
                pos = camera_status['position']
                message += f"• Position: [{pos[0]:.2f}, {pos[1]:.2f}, {pos[2]:.2f}]\n"
            
            if camera_status.get('target'):
                target = camera_status['target']
                message += f"• Target: [{target[0]:.2f}, {target[1]:.2f}, {target[2]:.2f}]\n"
            
            if camera_status.get('forward_vector'):
                fwd = camera_status['forward_vector']
                message += f"• Forward: [{fwd[0]:.3f}, {fwd[1]:.3f}, {fwd[2]:.3f}]\n"
            
            if camera_status.get('right_vector'):
                right = camera_status['right_vector']
                message += f"• Right: [{right[0]:.3f}, {right[1]:.3f}, {right[2]:.3f}]\n"
                
            if camera_status.get('up_vector'):
                up = camera_status['up_vector']
                message += f"• Up: [{up[0]:.3f}, {up[1]:.3f}, {up[2]:.3f}]\n"
            
            if camera_status.get('camera_path'):
                message += f"• Camera Path: {camera_status['camera_path']}\n"
        elif operation == 'health_check':
            # Update for standardized health format
            message = "✅ WorldViewer Health\n"
            message += f"• Service: {response.get('service', 'Agent WorldViewer API')}\n"
            message += f"• Version: {response.get('version', '1.0.0')}\n"
            message += f"• URL: {response.get('url', 'Unknown')}\n"
            message += f"• Timestamp: {response.get('timestamp', 'unknown')}\n"
            # Add extension-specific status
            camera_position = response.get('camera_position', [0.0, 0.0, 0.0])
            message += f"• Camera Position: [{camera_position[0]:.2f}, {camera_position[1]:.2f}, {camera_position[2]:.2f}]"
        
        return message
    
    @classmethod
    def format_error(cls, operation: str, error: str) -> str:
        """Format error response with user-friendly operation name and troubleshooting hints"""
        friendly_operation = operation.replace('_', ' ').title()
        error_message = cls.ERROR_TEMPLATE.format(operation=friendly_operation, error=error)
        
        # Add troubleshooting hints for common error patterns
        for error_pattern, hint in cls.TROUBLESHOOTING_HINTS.items():
            if error_pattern.lower() in error.lower():
                error_message += f"\n\n{hint}"
                break
        
        return error_message

shared_compat_path = os.path.join(os.path.dirname(__file__), '..', '..', 'shared')
if shared_compat_path not in sys.path:
    sys.path.insert(0, shared_compat_path)

try:
    from worldviewer_config import get_config
    config = get_config()
except ImportError:
    config = None

try:
    from pydantic_compat import (
        create_compatible_position_schema,
        validate_position,
        PYDANTIC_VERSION
    )
    HAS_COMPAT = True
except ImportError:
    HAS_COMPAT = False
    PYDANTIC_VERSION = 1


def create_position_schema(description: str = "Camera position as [x, y, z]") -> Dict:
    """Create position schema compatible with target environment."""
    if HAS_COMPAT:
        return create_compatible_position_schema(description)
    else:
        # Fallback to basic schema without v2 constraints
        return {
            "type": "array",
            "items": {"type": "number"},
            "description": description + " (exactly 3 items required)"
        }


class WorldViewerMCP:
    """MCP Server for Agent WorldViewer Extension"""
    
    def __init__(self):
        self.server = Server("worldviewer")
        
        # Use configuration if available, otherwise fallback to defaults
        env_base = os.getenv("AGENT_WORLDVIEWER_BASE_URL") or os.getenv("WORLDVIEWER_API_URL")
        if config:
            self.base_url = env_base or config.base_url
            self.timeout = config.mcp_timeout
            self.retry_attempts = config.mcp_retry_attempts
        else:
            self.base_url = env_base or "http://localhost:8900"
            self.timeout = 10.0
            self.retry_attempts = 3
        
        # Initialize unified auth client
        self.client = MCPBaseClient("WORLDVIEWER", self.base_url)
        
        # Response formatter
        self.formatter = CameraResponseFormatter()
        
        # Register tool handlers
        self._register_tools()
    
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
    
    def _register_tools(self):
        """Register all MCP tools"""
        
        @self.server.list_tools()
        async def handle_list_tools() -> List[Tool]:
            """List available camera control tools"""
            return [
                    Tool(
                        name="worldviewer_set_camera_position",
                        description="Set camera position and optionally target in Isaac Sim viewport",
                        inputSchema={
                            "type": "object",
                            "properties": {
                                "position": create_position_schema("Camera position as [x, y, z]"),
                                "target": create_position_schema("Optional look-at target as [x, y, z]"),
                                "up_vector": create_position_schema("Optional up vector as [x, y, z]")
                            },
                            "required": ["position"]
                        }
                    ),
                    Tool(
                        name="worldviewer_frame_object",
                        description="Frame an object in the Isaac Sim viewport",
                        inputSchema={
                            "type": "object",
                            "properties": {
                                "object_path": {
                                    "type": "string",
                                    "description": "USD path to the object (e.g., '/World/my_cube')"
                                },
                                "distance": {
                                    "type": "number",
                                    "description": "Optional distance from object (auto-calculated if not provided)"
                                }
                            },
                            "required": ["object_path"]
                        }
                    ),
                    Tool(
                        name="worldviewer_orbit_camera",
                        description="Position camera in orbital coordinates around a center point",
                        inputSchema={
                            "type": "object",
                            "properties": {
                                "center": create_position_schema("Center point to orbit around as [x, y, z]"),
                                "distance": {
                                    "type": "number",
                                    "description": "Distance from center point"
                                },
                                "elevation": {
                                    "type": "number",
                                    "description": "Elevation angle in degrees (-90 to 90)"
                                },
                                "azimuth": {
                                    "type": "number", 
                                    "description": "Azimuth angle in degrees (0 = front, 90 = right)"
                                }
                            },
                            "required": ["center", "distance", "elevation", "azimuth"]
                        }
                    ),
                    Tool(
                        name="worldviewer_get_camera_status",
                        description="Get current camera status and position",
                        inputSchema={
                            "type": "object",
                            "properties": {},
                            "additionalProperties": False
                        }
                    ),
                    Tool(
                        name="worldviewer_get_asset_transform",
                        description="Get transform information (position, rotation, scale, bounds) for a specific asset in the scene",
                        inputSchema={
                            "type": "object",
                            "properties": {
                                "usd_path": {
                                    "type": "string",
                                    "description": "USD path to the asset (e.g., '/World/my_cube' or '/World/ProperCity')"
                                },
                                "calculation_mode": {
                                    "type": "string",
                                    "enum": ["auto", "center", "pivot", "bounds"],
                                    "default": "auto",
                                    "description": "How to calculate position for complex assets"
                                }
                            },
                            "required": ["usd_path"]
                        }
                    ),
                    Tool(
                        name="worldviewer_extension_health",
                        description="Check Agent WorldViewer extension health and API status",
                        inputSchema={
                            "type": "object",
                            "properties": {},
                            "additionalProperties": False
                        }
                    ),
                    
                    # Cinematic Movement Tools
                    Tool(
                        name="worldviewer_smooth_move",
                        description="Smooth camera movement between two camera states (position + rotation) with easing",
                        inputSchema={
                            "type": "object",
                            "properties": {
                                "start_position": {
                                    "type": "array",
                                    "items": {"type": "number"},
                                    "minItems": 3,
                                    "maxItems": 3,
                                    "description": "Starting camera position [x, y, z]"
                                },
                                "end_position": {
                                    "type": "array", 
                                    "items": {"type": "number"},
                                    "minItems": 3,
                                    "maxItems": 3,
                                    "description": "Ending camera position [x, y, z]"
                                },
                                "start_rotation": {
                                    "type": "array",
                                    "items": {"type": "number"},
                                    "minItems": 3,
                                    "maxItems": 3,
                                    "description": "Starting camera rotation [pitch, yaw, roll] in degrees (optional)"
                                },
                                "end_rotation": {
                                    "type": "array",
                                    "items": {"type": "number"},
                                    "minItems": 3,
                                    "maxItems": 3,
                                    "description": "Ending camera rotation [pitch, yaw, roll] in degrees (optional)"
                                },
                                "start_target": {
                                    "type": "array",
                                    "items": {"type": "number"},
                                    "minItems": 3,
                                    "maxItems": 3,
                                    "description": "Starting look-at target [x, y, z] (optional, overridden by start_rotation)"
                                },
                                "end_target": {
                                    "type": "array",
                                    "items": {"type": "number"},
                                    "minItems": 3,
                                    "maxItems": 3,
                                    "description": "Ending look-at target [x, y, z] (optional)"
                                },
                                "duration": {
                                    "type": "number",
                                    "minimum": 0.1,
                                    "maximum": 60.0,
                                    "default": 3.0,
                                    "description": "Duration in seconds"
                                },
                                "easing_type": {
                                    "type": "string",
                                    "enum": ["linear", "ease_in", "ease_out", "ease_in_out", "bounce", "elastic"],
                                    "default": "ease_in_out",
                                    "description": "Movement easing function"
                                }
                            },
                            "required": ["start_position", "end_position"]
                        }
                    ),
                    
                    Tool(
                        name="worldviewer_stop_movement",
                        description="Stop an active cinematic movement",
                        inputSchema={
                            "type": "object",
                            "properties": {
                                "movement_id": {
                                    "type": "string",
                                    "description": "ID of the movement to stop"
                                }
                            },
                            "required": ["movement_id"]
                        }
                    ),
                    
                    Tool(
                        name="worldviewer_movement_status",
                        description="Get status of a cinematic movement",
                        inputSchema={
                            "type": "object",
                            "properties": {
                                "movement_id": {
                                    "type": "string",
                                    "description": "ID of the movement to check"
                                }
                            },
                            "required": ["movement_id"]
                        }
                    ),
                    
                    Tool(
                        name="worldviewer_get_metrics",
                        description="Get performance metrics and statistics from WorldViewer extension",
                        inputSchema={
                            "type": "object",
                            "properties": {
                                "format": {
                                    "type": "string",
                                    "enum": ["json", "prom"],
                                    "description": "Output format: json for structured data, prom for Prometheus format",
                                    "default": "json"
                                }
                            }
                        }
                    ),
                    
                    Tool(
                        name="worldviewer_metrics_prometheus",
                        description="Get WorldViewer metrics in Prometheus format for monitoring systems",
                        inputSchema={
                            "type": "object",
                            "properties": {},
                            "additionalProperties": False
                        }
                    )
                ]
        
        @self.server.call_tool()
        async def handle_call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
            """Handle tool execution requests"""
            
            try:
                if name == "worldviewer_set_camera_position":
                    return await self._set_camera_position(arguments)
                elif name == "worldviewer_frame_object":
                    return await self._frame_object(arguments)
                elif name == "worldviewer_orbit_camera":
                    return await self._orbit_camera(arguments)
                elif name == "worldviewer_get_camera_status":
                    return await self._get_camera_status(arguments)
                elif name == "worldviewer_get_asset_transform":
                    return await self._get_asset_transform(arguments)
                elif name == "worldviewer_extension_health":
                    return await self._extension_health(arguments)
                
                # Cinematic movement tools
                elif name == "worldviewer_smooth_move":
                    return await self._smooth_move(arguments)
                elif name == "worldviewer_stop_movement":
                    return await self._stop_movement(arguments)
                elif name == "worldviewer_movement_status":
                    return await self._movement_status(arguments)
                
                # Get metrics
                elif name == "worldviewer_get_metrics":
                    return await self._get_metrics(arguments)
                elif name == "worldviewer_metrics_prometheus":
                    return await self._metrics_prometheus(arguments)
                
                else:
                    return [TextContent(type="text", text=f"Unknown tool: {name}")]
            
            except aiohttp.ClientError as e:
                return [TextContent(type="text", text=f"❌ Connection error: {str(e)}")]
            except Exception as e:
                return [TextContent(type="text", text=f"❌ Tool execution failed: {str(e)}")]
    
    
    
    
    async def _execute_camera_operation(self, operation: str, method: str, endpoint: str, 
                                       data: Optional[Dict] = None, **template_vars) -> List[TextContent]:
        """Unified camera operation execution with consistent response formatting"""
        try:
            await self._initialize_client()
            
            if method.upper() == "GET":
                response = await self.client.get(endpoint)
            elif method.upper() == "POST":
                response = await self.client.post(endpoint, json=data)
            else:
                raise ValueError(f"Unsupported method: {method}")
            
            if response.get("success"):
                message = self.formatter.format_success(operation, response, **template_vars)
                return [TextContent(type="text", text=message)]
            else:
                error_message = self.formatter.format_error(operation, response.get('error', 'Unknown error'))
                return [TextContent(type="text", text=error_message)]
        
        except aiohttp.ClientError as e:
            error_message = self.formatter.format_error(operation, f"Connection error: {str(e)}")
            return [TextContent(type="text", text=error_message)]
        except Exception as e:
            error_message = self.formatter.format_error(operation, f"Execution error: {str(e)}")
            return [TextContent(type="text", text=error_message)]
    
    async def _set_camera_position(self, args: Dict[str, Any]) -> List[TextContent]:
        """Set camera position"""
        
        position = args.get("position")
        target = args.get("target")
        up_vector = args.get("up_vector")
        
        # Manual validation for compatibility with Pydantic v1
        try:
            if HAS_COMPAT:
                validate_position(position)
                if target:
                    validate_position(target)
                if up_vector:
                    validate_position(up_vector)
            else:
                # Basic validation fallback
                if not isinstance(position, list) or len(position) != 3:
                    raise ValueError("position must be an array of exactly 3 numbers")
                if target and (not isinstance(target, list) or len(target) != 3):
                    raise ValueError("target must be an array of exactly 3 numbers")
                if up_vector and (not isinstance(up_vector, list) or len(up_vector) != 3):
                    raise ValueError("up_vector must be an array of exactly 3 numbers")
        except ValueError as e:
            return [TextContent(type="text", text=f"❌ Parameter validation error: {str(e)}")]
        
        request_data = {"position": position}
        if target:
            request_data["target"] = target
        if up_vector:
            request_data["up_vector"] = up_vector
        
        return await self._execute_camera_operation(
            "set_position", "POST", "/camera/set_position", 
            request_data, position=position, target=target
        )
    
    async def _frame_object(self, args: Dict[str, Any]) -> List[TextContent]:
        """Frame object in viewport"""
        
        object_path = args.get("object_path")
        distance = args.get("distance")
        
        request_data = {"object_path": object_path}
        if distance is not None:
            request_data["distance"] = distance
        
        return await self._execute_camera_operation(
            "frame_object", "POST", "/camera/frame_object", 
            request_data, object_path=object_path
        )
    
    async def _orbit_camera(self, args: Dict[str, Any]) -> List[TextContent]:
        """Position camera in orbit"""
        
        center = args.get("center")
        distance = args.get("distance")
        elevation = args.get("elevation")
        azimuth = args.get("azimuth")
        
        # Manual validation for compatibility with Pydantic v1
        try:
            if HAS_COMPAT:
                validate_position(center)
            else:
                if not isinstance(center, list) or len(center) != 3:
                    raise ValueError("center must be an array of exactly 3 numbers")
        except ValueError as e:
            return [TextContent(type="text", text=f"❌ Parameter validation error: {str(e)}")]
        
        request_data = {
            "center": center,
            "distance": distance,
            "elevation": elevation,
            "azimuth": azimuth
        }
        
        return await self._execute_camera_operation(
            "orbit_camera", "POST", "/camera/orbit", 
            request_data, center=center, distance=distance, elevation=elevation, azimuth=azimuth
        )
    
    async def _get_camera_status(self, args: Dict[str, Any]) -> List[TextContent]:
        """Get camera status"""
        return await self._execute_camera_operation(
            "get_status", "GET", "/camera/status"
        )
    
    async def _get_asset_transform(self, args: Dict[str, Any]) -> List[TextContent]:
        """Get asset transform information for camera operations"""
        usd_path = args.get("usd_path", "")
        calculation_mode = args.get("calculation_mode", "auto")
        
        if not usd_path:
            return [TextContent(type="text", text="❌ Error: usd_path is required")]
        
        try:
            await self._initialize_client()
            result = await self.client.get("/get_asset_transform", params={
                "usd_path": usd_path,
                "calculation_mode": calculation_mode
            })
            
            if result.get("success"):
                # Format the transform data nicely
                pos = result.get("position", [0, 0, 0])
                bounds = result.get("bounds", {})
                bounds_center = bounds.get("center", [0, 0, 0])
                asset_type = result.get("type", "unknown")
                child_count = result.get("child_count", 0)
                calc_mode = result.get("calculation_mode", "auto")
                
                transform_text = (
                    f"🔍 Asset Transform: {usd_path}\n"
                    f"• Type: {asset_type} ({child_count} children)\n"
                    f"• Position: [{pos[0]:.2f}, {pos[1]:.2f}, {pos[2]:.2f}]\n"
                    f"• Bounds Center: [{bounds_center[0]:.2f}, {bounds_center[1]:.2f}, {bounds_center[2]:.2f}]\n"
                    f"• Calculation Mode: {calc_mode}\n"
                    f"• Source: worldviewer"
                )
                
                # Add bounds info if available
                if bounds.get("min") and bounds.get("max"):
                    bounds_min = bounds["min"]
                    bounds_max = bounds["max"]
                    size = [bounds_max[i] - bounds_min[i] for i in range(3)]
                    transform_text += (
                        f"\n• Bounds Size: [{size[0]:.2f}, {size[1]:.2f}, {size[2]:.2f}]"
                        f"\n• Bounds Min: [{bounds_min[0]:.2f}, {bounds_min[1]:.2f}, {bounds_min[2]:.2f}]"
                        f"\n• Bounds Max: [{bounds_max[0]:.2f}, {bounds_max[1]:.2f}, {bounds_max[2]:.2f}]"
                    )
                
                return [TextContent(type="text", text=transform_text)]
            else:
                error_msg = result.get('error', 'Unknown error')
                return [TextContent(type="text", text=f"❌ Failed to get asset transform: {error_msg}")]
                    
        except aiohttp.ServerTimeoutError:
            return [TextContent(type="text", text="❌ Request timed out - Isaac Sim may be busy")]
        except Exception as e:
            return [TextContent(type="text", text=f"❌ Connection error: {str(e)}")]
    
    async def _extension_health(self, args: Dict[str, Any]) -> List[TextContent]:
        """Check extension health"""
        return await self._execute_camera_operation(
            "health_check", "GET", "/health", status="healthy"
        )
    
    # =====================================================================
    # CINEMATIC MOVEMENT TOOL HANDLERS
    # =====================================================================
    
    async def _smooth_move(self, args: Dict[str, Any]) -> List[TextContent]:
        """Execute smooth camera movement"""
        return await self._execute_camera_operation(
            "smooth_move", "POST", "/camera/smooth_move", args,
            start_position=args.get("start_position"),
            end_position=args.get("end_position"),
            duration=args.get("duration", 3.0)
        )
    
    async def _stop_movement(self, args: Dict[str, Any]) -> List[TextContent]:
        """Stop an active cinematic movement"""
        movement_id = args.get("movement_id")
        if not movement_id:
            return [TextContent(type="text", text="❌ Movement ID is required")]
        
        return await self._execute_camera_operation(
            "stop_movement", "POST", "/camera/stop_movement", args,
            movement_id=movement_id
        )
    
    async def _movement_status(self, args: Dict[str, Any]) -> List[TextContent]:
        """Get status of a cinematic movement"""
        movement_id = args.get("movement_id")
        if not movement_id:
            return [TextContent(type="text", text="❌ Movement ID is required")]
        
        return await self._execute_camera_operation(
            "movement_status", "GET", f"/camera/movement_status?movement_id={movement_id}", None,
            movement_id=movement_id
        )
    
    async def _get_metrics(self, args: Dict[str, Any]) -> List[TextContent]:
        """Get performance metrics and statistics from WorldViewer extension"""
        format_type = args.get("format", "json")
        
        try:
            if format_type == "prom":
                await self._initialize_client()
                response = await self.client.get("/metrics.prom")
            else:
                await self._initialize_client()
                response = await self.client.get("/metrics")
            
            # Handle Prometheus format special response
            if format_type == "prom" and "_raw_text" in response:
                prom_data = response["_raw_text"]
                return [TextContent(type="text", text=f"📊 **WorldViewer Metrics (Prometheus)**\n```\n{prom_data}\n```")]
            elif response.get("success"):
                if format_type == "json":
                    metrics_json = json.dumps(response.get("metrics", {}), indent=2)
                    return [TextContent(type="text", text=f"📊 **WorldViewer Metrics (JSON)**\n```json\n{metrics_json}\n```")]
                elif format_type == "prom":
                    prom_data = response.get("prometheus_metrics", "# No Prometheus metrics available")
                    return [TextContent(type="text", text=f"📊 **WorldViewer Metrics (Prometheus)**\n```\n{prom_data}\n```")]
                else:
                    return [TextContent(type="text", text="❌ Error: format must be 'json' or 'prom'")]
            else:
                error_msg = response.get('error', 'Unknown error')
                return [TextContent(type="text", text=f"❌ Failed to get WorldViewer metrics: {error_msg}")]
                
        except Exception as e:
            return [TextContent(type="text", text=f"❌ Error getting metrics: {str(e)}")]
    
    async def _metrics_prometheus(self, args: Dict[str, Any]) -> List[TextContent]:
        """Get WorldViewer metrics in Prometheus format."""
        try:
            await self._initialize_client()
            response = await self.client.get("/metrics.prom")
            
            # For Prometheus format, check for _raw_text field first (special response format)
            if "_raw_text" in response:
                prom_data = response["_raw_text"]
                return [TextContent(type="text", text=f"📊 **WorldViewer Prometheus Metrics**\n\n```\n{prom_data}\n```")]
            elif response.get("success"):
                # Fallback to prometheus_metrics field
                prom_data = response.get("prometheus_metrics", "# No Prometheus metrics available")
                return [TextContent(type="text", text=f"📊 **WorldViewer Prometheus Metrics**\n\n```\n{prom_data}\n```")]
            else:
                error_msg = response.get('error', 'Unknown error')
                return [TextContent(type="text", text=f"❌ Failed to get Prometheus metrics: {error_msg}")]
                
        except Exception as e:
            return [TextContent(type="text", text=f"❌ Error getting Prometheus metrics: {str(e)}")]
    
async def main():
    """Main entry point for the MCP server."""
    setup_logging('worldviewer')
    # Initialize MCP server
    mcp_server = WorldViewerMCP()
    
    try:
        # Run the server
        async with stdio_server() as (read_stream, write_stream):
            await mcp_server.server.run(
                read_stream,
                write_stream,
                InitializationOptions(
                    server_name="worldviewer",
                    server_version="0.1.0",
                    capabilities=mcp_server.server.get_capabilities(
                        notification_options=NotificationOptions(),
                        experimental_capabilities={}
                    ),
                ),
            )
    finally:
        # Cleanup unified auth client on shutdown
        await mcp_server.client.close()


if __name__ == "__main__":
    asyncio.run(main())
