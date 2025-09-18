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

# Add shared modules to path
shared_path = os.path.join(os.path.dirname(__file__), '..', '..', 'shared')
if shared_path not in sys.path:
    sys.path.insert(0, shared_path)

# Import shared modules
from logging_setup import setup_logging
from mcp_base_client import MCPBaseClient
from mcp.server import Server
from mcp.server.models import InitializationOptions
from mcp.server.stdio import stdio_server
from mcp.server.lowlevel import NotificationOptions
from mcp.types import Tool, TextContent

try:
    from agent_world_transport import normalize_transport_response
except ImportError:  # pragma: no cover - fallback when extensions not available
    def normalize_transport_response(operation: str, response: Any, *, default_error_code: str) -> Dict[str, Any]:
        if isinstance(response, dict):
            response.setdefault('success', True)
            if response['success'] is False:
                response.setdefault('error_code', default_error_code)
                response.setdefault('error', 'An unknown error occurred')
            return response
        return {
            'success': False,
            'error_code': 'INVALID_RESPONSE',
            'error': 'Service returned unexpected response type',
            'details': {'operation': operation, 'type': type(response).__name__},
        }

try:
    from omni.agent.worldviewer.errors import error_response
except ImportError:  # pragma: no cover - fallback when extension package unavailable
    def error_response(code: str, message: str, *, details: Dict[str, Any] | None = None) -> Dict[str, Any]:
        payload = {'success': False, 'error_code': code, 'error': message}
        if details:
            payload['details'] = details
        return payload


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


shared_compat_path = os.path.join(os.path.dirname(__file__), '..', '..', 'shared')
if shared_compat_path not in sys.path:
    sys.path.insert(0, shared_compat_path)

# Add agentworld-extensions to path for unified config
extensions_path = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'agentworld-extensions')
if os.path.exists(extensions_path) and extensions_path not in sys.path:
    sys.path.insert(0, extensions_path)

try:
    from agent_world_config import create_worldviewer_config
    config = create_worldviewer_config()
except ImportError:
    # Fallback if unified config not available
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
            self.base_url = env_base or config.get_server_url()
            self.timeout = config.get('mcp_timeout', 10.0)
            self.retry_attempts = config.get('mcp_retry_attempts', 3)
        else:
            self.base_url = env_base or "http://localhost:8900"
            self.timeout = 10.0
            self.retry_attempts = 3
        
        # Initialize unified auth client
        self.client = MCPBaseClient("WORLDVIEWER", self.base_url)
        
        # Response formatter
        
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
                                    "description": "Starting look-at target [x, y, z] (required for practical cinematography, overridden by start_rotation)"
                                },
                                "end_target": {
                                    "type": "array",
                                    "items": {"type": "number"},
                                    "minItems": 3,
                                    "maxItems": 3,
                                    "description": "Ending look-at target [x, y, z] (required for practical cinematography)"
                                },
                                "speed": {
                                    "type": "number",
                                    "minimum": 0.1,
                                    "maximum": 100.0,
                                    "description": "Average speed in units per second (alternative to duration)"
                                },
                                "duration": {
                                    "type": "number",
                                    "minimum": 0.1,
                                    "maximum": 60.0,
                                    "description": "Duration in seconds (overrides speed if provided)"
                                },
                                "easing_type": {
                                    "type": "string",
                                    "enum": ["linear", "ease_in", "ease_out", "ease_in_out", "bounce", "elastic"],
                                    "default": "ease_in_out",
                                    "description": "Movement easing function"
                                },
                                "execution_mode": {
                                    "type": "string",
                                    "enum": ["auto", "manual"],
                                    "default": "auto",
                                    "description": "Execution mode: auto (execute immediately in sequence) or manual (wait for play command)"
                                }
                            },
                            "required": ["start_position", "end_position", "start_target", "end_target"]
                        }
                    ),
                    
                    Tool(
                        name="worldviewer_arc_shot",
                        description="Cinematic arc shot with curved Bezier path between two camera positions",
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
                                "start_target": {
                                    "type": "array",
                                    "items": {"type": "number"},
                                    "minItems": 3,
                                    "maxItems": 3,
                                    "description": "Starting look-at target [x, y, z] (required for practical cinematography)"
                                },
                                "end_target": {
                                    "type": "array",
                                    "items": {"type": "number"},
                                    "minItems": 3,
                                    "maxItems": 3,
                                    "description": "Ending look-at target [x, y, z] (required for practical cinematography)"
                                },
                                "speed": {
                                    "type": "number",
                                    "minimum": 0.1,
                                    "maximum": 100.0,
                                    "description": "Average speed in units per second (alternative to duration)"
                                },
                                "duration": {
                                    "type": "number",
                                    "minimum": 0.1,
                                    "maximum": 60.0,
                                    "description": "Duration in seconds (overrides speed if provided)"
                                },
                                "movement_style": {
                                    "type": "string",
                                    "enum": ["standard"],
                                    "default": "standard",
                                    "description": "Arc movement style"
                                },
                                "execution_mode": {
                                    "type": "string",
                                    "enum": ["auto", "manual"],
                                    "default": "auto",
                                    "description": "Execution mode: auto (execute immediately in sequence) or manual (wait for play command)"
                                }
                            },
                            "required": ["start_position", "end_position", "start_target", "end_target"]
                        }
                    ),
                    
                    Tool(
                        name="worldviewer_stop_movement",
                        description="Stop an active cinematic movement",
                        inputSchema={
                            "type": "object",
                            "properties": {},
                            "additionalProperties": False
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
                    ),
                    
                    Tool(
                        name="worldviewer_get_queue_status",
                        description="Get comprehensive shot queue status with timing information and queue state",
                        inputSchema={
                            "type": "object",
                            "properties": {},
                            "additionalProperties": False
                        }
                    ),
                    
                    Tool(
                        name="worldviewer_play_queue",
                        description="Start/resume queue processing",
                        inputSchema={
                            "type": "object",
                            "properties": {},
                            "additionalProperties": False
                        }
                    ),
                    
                    Tool(
                        name="worldviewer_pause_queue",
                        description="Pause queue processing (current movement continues, no new movements start)",
                        inputSchema={
                            "type": "object",
                            "properties": {},
                            "additionalProperties": False
                        }
                    ),
                    
                    Tool(
                        name="worldviewer_stop_queue",
                        description="Stop and clear entire queue",
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
                elif name == "worldviewer_arc_shot":
                    return await self._arc_shot(arguments)
                elif name == "worldviewer_stop_movement":
                    return await self._stop_movement(arguments)
                elif name == "worldviewer_movement_status":
                    return await self._movement_status(arguments)
                
                # Get metrics
                elif name == "worldviewer_get_metrics":
                    return await self._get_metrics(arguments)
                elif name == "worldviewer_metrics_prometheus":
                    return await self._metrics_prometheus(arguments)
                elif name == "worldviewer_get_queue_status":
                    return await self._get_queue_status(arguments)
                elif name == "worldviewer_play_queue":
                    return await self._play_queue(arguments)
                elif name == "worldviewer_pause_queue":
                    return await self._pause_queue(arguments)
                elif name == "worldviewer_stop_queue":
                    return await self._stop_queue(arguments)
                
                else:
                    return self._wrap_response(
                        error_response('UNKNOWN_TOOL', f'Unknown tool: {name}', details={'tool': name})
                    )

            except aiohttp.ClientError as exc:
                return self._wrap_response(
                    error_response('CONNECTION_ERROR', f'Connection error: {exc}', details={'tool': name})
                )
            except Exception as exc:
                return self._wrap_response(
                    error_response('TOOL_EXECUTION_FAILED', str(exc), details={'tool': name})
                )
    
    
    
    
    async def _execute_camera_operation(
        self,
        operation: str,
        method: str,
        endpoint: str,
        *,
        data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
        timeout_type: str = 'standard',
        default_error_code: str,
    ) -> Dict[str, Any]:
        """Execute HTTP operation and normalise the response payload."""
        try:
            await self._initialize_client()
            timeout = self._get_timeout(timeout_type)

            if method.upper() == 'GET':
                response = await self.client.get(endpoint, params=params, timeout=timeout)
            elif method.upper() == 'POST':
                response = await self.client.post(endpoint, json=data, timeout=timeout)
            else:
                raise ValueError(f'Unsupported method: {method}')

            return normalize_transport_response(
                operation,
                response,
                default_error_code=default_error_code,
            )

        except asyncio.TimeoutError:
            return error_response(
                'REQUEST_TIMEOUT',
                'Request timed out - Isaac Sim may be busy',
                details={'operation': operation},
            )
        except aiohttp.ClientError as exc:
            return error_response(
                'CONNECTION_ERROR',
                f'Connection error: {exc}',
                details={'operation': operation},
            )
        except Exception as exc:
            return error_response(
                default_error_code,
                str(exc),
                details={'operation': operation},
            )

    @staticmethod
    def _wrap_response(payload: Dict[str, Any]) -> List[TextContent]:
        """Convert response payload into MCP text content."""
        return [TextContent(type="text", text=json.dumps(payload, indent=2, sort_keys=True))]
    
    async def _set_camera_position(self, args: Dict[str, Any]) -> List[TextContent]:
        """Set camera position."""

        position = args.get('position')
        target = args.get('target')
        up_vector = args.get('up_vector')

        try:
            if HAS_COMPAT:
                validate_position(position)
                if target:
                    validate_position(target)
                if up_vector:
                    validate_position(up_vector)
            else:
                if not isinstance(position, list) or len(position) != 3:
                    raise ValueError('position must be an array of exactly 3 numbers')
                if target and (not isinstance(target, list) or len(target) != 3):
                    raise ValueError('target must be an array of exactly 3 numbers')
                if up_vector and (not isinstance(up_vector, list) or len(up_vector) != 3):
                    raise ValueError('up_vector must be an array of exactly 3 numbers')
        except ValueError as exc:
            return self._wrap_response(error_response('VALIDATION_ERROR', str(exc)))

        request_data = {'position': position}
        if target:
            request_data['target'] = target
        if up_vector:
            request_data['up_vector'] = up_vector

        response = await self._execute_camera_operation(
            'set_camera_position',
            'POST',
            '/camera/set_position',
            data=request_data,
            default_error_code='SET_CAMERA_POSITION_FAILED',
        )
        return self._wrap_response(response)
    
    async def _frame_object(self, args: Dict[str, Any]) -> List[TextContent]:
        """Frame object in viewport."""

        object_path = args.get('object_path')
        distance = args.get('distance')

        if not object_path:
            return self._wrap_response(
                error_response('MISSING_PARAMETER', 'object_path is required', details={'parameter': 'object_path'})
            )

        request_data = {'object_path': object_path}
        if distance is not None:
            request_data['distance'] = distance

        response = await self._execute_camera_operation(
            'frame_object',
            'POST',
            '/camera/frame_object',
            data=request_data,
            default_error_code='FRAME_OBJECT_FAILED',
        )
        return self._wrap_response(response)
    
    async def _orbit_camera(self, args: Dict[str, Any]) -> List[TextContent]:
        """Position camera in orbit."""

        center = args.get('center')
        distance = args.get('distance')
        elevation = args.get('elevation')
        azimuth = args.get('azimuth')

        try:
            if HAS_COMPAT:
                validate_position(center)
            else:
                if not isinstance(center, list) or len(center) != 3:
                    raise ValueError('center must be an array of exactly 3 numbers')
        except ValueError as exc:
            return self._wrap_response(error_response('VALIDATION_ERROR', str(exc)))

        request_data = {
            'center': center,
            'distance': distance,
            'elevation': elevation,
            'azimuth': azimuth,
        }

        response = await self._execute_camera_operation(
            'orbit_camera',
            'POST',
            '/camera/orbit',
            data=request_data,
            default_error_code='ORBIT_CAMERA_FAILED',
        )
        return self._wrap_response(response)
    
    async def _get_camera_status(self, args: Dict[str, Any]) -> List[TextContent]:
        """Get camera status."""
        response = await self._execute_camera_operation(
            'get_camera_status',
            'GET',
            '/camera/status',
            default_error_code='CAMERA_STATUS_FAILED',
        )
        return self._wrap_response(response)
    
    async def _get_asset_transform(self, args: Dict[str, Any]) -> List[TextContent]:
        """Get asset transform information for camera operations."""

        usd_path = args.get('usd_path')
        calculation_mode = args.get('calculation_mode', 'auto')

        if not usd_path:
            return self._wrap_response(error_response('MISSING_PARAMETER', 'usd_path is required', details={'parameter': 'usd_path'}))

        response = await self._execute_camera_operation(
            'asset_transform',
            'GET',
            '/get_asset_transform',
            params={'usd_path': usd_path, 'calculation_mode': calculation_mode},
            default_error_code='ASSET_TRANSFORM_FAILED',
        )
        return self._wrap_response(response)
    
    async def _extension_health(self, args: Dict[str, Any]) -> List[TextContent]:
        """Check extension health."""
        response = await self._execute_camera_operation(
            'get_health',
            'GET',
            '/health',
            timeout_type='simple',
            default_error_code='HEALTH_FAILED',
        )
        return self._wrap_response(response)
    
    # =====================================================================
    # CINEMATIC MOVEMENT TOOL HANDLERS
    # =====================================================================
    
    async def _smooth_move(self, args: Dict[str, Any]) -> List[TextContent]:
        """Execute smooth camera movement."""

        if 'start_position' not in args or 'end_position' not in args:
            return self._wrap_response(
                error_response(
                    'MISSING_PARAMETER',
                    'start_position and end_position are required',
                    details={'required': ['start_position', 'end_position']},
                )
            )

        response = await self._execute_camera_operation(
            'smooth_move',
            'POST',
            '/camera/smooth_move',
            data=args,
            timeout_type='complex',
            default_error_code='SMOOTH_MOVE_FAILED',
        )
        return self._wrap_response(response)
    
    async def _arc_shot(self, args: Dict[str, Any]) -> List[TextContent]:
        """Execute arc shot cinematic movement with curved path."""

        if 'start_position' not in args:
            return self._wrap_response(
                error_response('MISSING_PARAMETER', 'start_position is required', details={'parameter': 'start_position'})
            )

        response = await self._execute_camera_operation(
            'arc_shot',
            'POST',
            '/camera/arc_shot',
            data=args,
            timeout_type='complex',
            default_error_code='ARC_SHOT_FAILED',
        )
        return self._wrap_response(response)
    
    async def _stop_movement(self, args: Dict[str, Any]) -> List[TextContent]:
        """Stop all active cinematic movements."""
        response = await self._execute_camera_operation(
            'stop_movement',
            'POST',
            '/camera/stop_movement',
            data={},
            default_error_code='STOP_MOVEMENT_FAILED',
        )
        return self._wrap_response(response)
    
    async def _movement_status(self, args: Dict[str, Any]) -> List[TextContent]:
        """Get status of a cinematic movement."""
        movement_id = args.get('movement_id')
        if not movement_id:
            return self._wrap_response(
                error_response('MISSING_PARAMETER', 'movement_id is required', details={'parameter': 'movement_id'})
            )

        response = await self._execute_camera_operation(
            'movement_status',
            'GET',
            '/camera/movement_status',
            params={'movement_id': movement_id},
            default_error_code='MOVEMENT_STATUS_FAILED',
        )
        return self._wrap_response(response)
    
    async def _get_metrics(self, args: Dict[str, Any]) -> List[TextContent]:
        """Get performance metrics and statistics from WorldViewer extension."""
        format_type = args.get('format', 'json').lower()

        if format_type not in {'json', 'prom'}:
            return self._wrap_response(
                error_response('INVALID_PARAMETER', "format must be 'json' or 'prom'", details={'format': format_type})
            )

        if format_type == 'prom':
            response = await self._execute_camera_operation(
                'get_prometheus_metrics',
                'GET',
                '/metrics.prom',
                timeout_type='simple',
                default_error_code='PROMETHEUS_METRICS_FAILED',
            )
        else:
            response = await self._execute_camera_operation(
                'get_metrics',
                'GET',
                '/metrics',
                timeout_type='simple',
                default_error_code='METRICS_FAILED',
            )

        return self._wrap_response(response)
    
    async def _metrics_prometheus(self, args: Dict[str, Any]) -> List[TextContent]:
        """Get WorldViewer metrics in Prometheus format."""
        response = await self._execute_camera_operation(
            'get_prometheus_metrics',
            'GET',
            '/metrics.prom',
            timeout_type='simple',
            default_error_code='PROMETHEUS_METRICS_FAILED',
        )
        return self._wrap_response(response)

    async def _get_queue_status(self, args: Dict[str, Any]) -> List[TextContent]:
        """Get comprehensive shot queue status with timing information."""
        response = await self._execute_camera_operation(
            'shot_queue_status',
            'GET',
            '/camera/shot_queue_status',
            timeout_type='standard',
            default_error_code='QUEUE_STATUS_FAILED',
        )
        return self._wrap_response(response)

    async def _play_queue(self, args: Dict[str, Any]) -> List[TextContent]:
        """Start or resume queue processing."""
        response = await self._execute_camera_operation(
            'queue_play',
            'POST',
            '/camera/queue/play',
            data={},
            default_error_code='QUEUE_PLAY_FAILED',
        )
        return self._wrap_response(response)

    async def _pause_queue(self, args: Dict[str, Any]) -> List[TextContent]:
        """Pause queue processing."""
        response = await self._execute_camera_operation(
            'queue_pause',
            'POST',
            '/camera/queue/pause',
            data={},
            default_error_code='QUEUE_PAUSE_FAILED',
        )
        return self._wrap_response(response)

    async def _stop_queue(self, args: Dict[str, Any]) -> List[TextContent]:
        """Stop and clear entire queue."""
        response = await self._execute_camera_operation(
            'queue_stop',
            'POST',
            '/camera/queue/stop',
            data={},
            default_error_code='QUEUE_STOP_FAILED',
        )
        return self._wrap_response(response)
    
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
