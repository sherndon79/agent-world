"""
HTTP request handler for Agent WorldViewer API endpoints.
"""

import logging
import time
from pathlib import Path
from typing import Dict, List, Optional, Any

# Unified HTTP handler import with fallback
try:
    import sys as _sys
    from pathlib import Path as _P
    _cur = _P(__file__).resolve()
    for _ in range(10):
        if _cur.name == 'agentworld-extensions':
            _sys.path.insert(0, str(_cur))
            break
        _cur = _cur.parent
    from agent_world_http import WorldHTTPHandler
    UNIFIED = True
except Exception:
    from http.server import BaseHTTPRequestHandler as WorldHTTPHandler  # type: ignore
    UNIFIED = False

# Import centralized version management  
def _find_and_import_versions():
    """Find and import version management module using robust path resolution."""
    try:
        # Strategy 1: Search upward in directory tree for agentworld-extensions
        current = Path(__file__).resolve()
        for _ in range(10):  # Reasonable search limit
            if current.name == 'agentworld-extensions' or (current / 'agent_world_versions.py').exists():
                sys.path.insert(0, str(current))
                from agent_world_versions import get_version, get_service_name
                return get_version, get_service_name
            if current.parent == current:  # Reached filesystem root
                break
            current = current.parent
        
        # Strategy 2: Environment variable fallback
        env_path = os.getenv('AGENT_WORLD_VERSIONS_PATH')
        if env_path:
            sys.path.insert(0, env_path)
            from agent_world_versions import get_version, get_service_name
            return get_version, get_service_name
            
        return None, None
    except ImportError:
        return None, None

try:
    import sys
    import os
    get_version, get_service_name = _find_and_import_versions()
    VERSION_AVAILABLE = get_version is not None
except Exception:
    VERSION_AVAILABLE = False

logger = logging.getLogger(__name__)

class WorldViewerHTTPHandler(WorldHTTPHandler):
    """HTTP request handler for WorldViewer operations (unified)."""

    api_interface = None

    def get_routes(self):  # type: ignore[override]
        """Return route mappings for unified HTTP handler with (method, data) signatures."""
        return {
            'camera/status': self._route_camera_status,
            'camera/set_position': self._route_camera_set,
            'camera/frame_object': self._route_frame_object,
            'camera/orbit': self._route_camera_orbit,
            'camera/smooth_move': self._route_smooth_move,
            'camera/orbit_shot': self._route_orbit_shot,
            'camera/movement_status': self._route_movement_status,
            'movement/stop': self._route_stop_movement,
            'camera/stop_movement': self._route_stop_movement,
            'get_asset_transform': self._route_get_asset_transform,
            'request_status': self._route_request_status,
        }

    # Individual route handlers extracted from _handle_get_request/_handle_post_request
    def _handle_health(self):
        """Handle health check request."""
        if VERSION_AVAILABLE:
            service_name = get_service_name('worldviewer')
            version = get_version('worldviewer', 'api_version')
        else:
            service_name = 'Agent WorldViewer API'
            version = '0.1.0'
            
        port = self.api_interface.get_port() if self.api_interface else 8900
        
        # Get current camera position for extension-specific status
        camera_position = [0.0, 0.0, 0.0]  # Default
        try:
            camera_status = self._get_camera_status()
            if camera_status.get('success'):
                # Prefer top-level position; fallback to nested 'camera' if present
                if 'position' in camera_status and camera_status['position']:
                    camera_position = camera_status['position']
                elif 'camera' in camera_status and camera_status['camera'].get('position'):
                    camera_position = camera_status['camera']['position']
        except Exception:
            pass  # Use default position
        
        return {
            'success': True,
            'message': 'Agent WorldViewer API is healthy',
            'service': service_name,
            'version': version,
            'port': port,
            'timestamp': time.time(),
            'extension_specific': {
                'camera_position': camera_position,
                'api_endpoints': [
                    'camera/status', 'camera/set_position', 'camera/frame_object',
                    'camera/orbit', 'camera/smooth_move', 'get_asset_transform'
                ]
            }
        }

    # Unified route wrappers (accept method, data)
    def _route_camera_status(self, method: str, data: Dict[str, Any]) -> Dict[str, Any]:
        return self._get_camera_status()

    def _route_movement_status(self, method: str, data: Dict[str, Any]) -> Dict[str, Any]:
        movement_id = data.get('movement_id')
        if not movement_id:
            return {'success': False, 'error': 'movement_id parameter required'}
        return self._get_movement_status(movement_id)

    def _route_get_asset_transform(self, method: str, data: Dict[str, Any]) -> Dict[str, Any]:
        usd_path = data.get('usd_path')
        calculation_mode = data.get('calculation_mode', 'auto')
        # Normalize query params from parse_qs
        if isinstance(usd_path, list):
            usd_path = usd_path[0] if usd_path else ''
        if isinstance(calculation_mode, list):
            calculation_mode = calculation_mode[0] if calculation_mode else 'auto'
        if not usd_path:
            return {'success': False, 'error': 'usd_path parameter required'}
        return self._get_asset_transform(usd_path, calculation_mode)

    def _route_camera_set(self, method: str, data: Dict[str, Any]) -> Dict[str, Any]:
        position = data.get('position')
        target = data.get('target')
        up_vector = data.get('up_vector')
        if not position or len(position) != 3:
            return {'success': False, 'error': 'position must be [x, y, z] array'}
        return self._set_camera_position(position, target, up_vector)

    def _route_frame_object(self, method: str, data: Dict[str, Any]) -> Dict[str, Any]:
        object_path = data.get('object_path')
        distance = data.get('distance')
        if not object_path:
            return {'success': False, 'error': 'object_path is required'}
        return self._frame_object(object_path, distance)

    def _route_camera_orbit(self, method: str, data: Dict[str, Any]) -> Dict[str, Any]:
        center = data.get('center')
        distance = data.get('distance')
        elevation = data.get('elevation')
        azimuth = data.get('azimuth')
        if not all(x is not None for x in [center, distance, elevation, azimuth]):
            return {'success': False, 'error': 'center, distance, elevation, azimuth are required'}
        return self._orbit_camera(center, distance, elevation, azimuth)

    def _route_smooth_move(self, method: str, data: Dict[str, Any]) -> Dict[str, Any]:
        return self._handle_smooth_move(data)

    def _route_orbit_shot(self, method: str, data: Dict[str, Any]) -> Dict[str, Any]:
        return self._handle_orbit_shot(data)

    def _route_stop_movement(self, method: str, data: Dict[str, Any]) -> Dict[str, Any]:
        return self._handle_stop_movement(data)

    def _route_request_status(self, method: str, data: Dict[str, Any]) -> Dict[str, Any]:
        request_id = data.get('request_id')
        if not request_id:
            return {'success': False, 'error': 'request_id parameter required'}
        return self._get_request_status(request_id)

    # Unified base already serves docs/openapi using module import

    # POST method handlers
    def _handle_camera_set(self):
        """Handle camera set position request."""
        # This should extract position, target, up_vector from request data
        return {'success': False, 'error': 'position parameter required'}

    def _handle_frame_object(self):
        """Handle frame object request."""
        # This should extract object_path, distance from request data
        return {'success': False, 'error': 'object_path parameter required'}

    def _handle_camera_orbit(self):
        """Handle camera orbit request."""
        # This should extract center, distance, elevation, azimuth from request data
        return {'success': False, 'error': 'center, distance, elevation, azimuth parameters required'}

    def _handle_smooth_move(self):
        """Handle smooth move request."""
        # This should extract movement parameters from request data
        return {'success': False, 'error': 'start_position and end_position parameters required'}

    def _handle_orbit_shot(self):
        """Handle orbit shot request."""
        # This should extract orbit shot parameters from request data
        return {'success': False, 'error': 'orbit shot parameters required'}

    def _handle_stop_movement(self):
        """Handle stop movement request."""
        # This should extract movement_id from request data
        return {'success': False, 'error': 'movement_id parameter required'}

    # Removed legacy GET/POST handlers; unified base dispatches to route wrappers

    def _get_camera_status(self) -> Dict:
        """Get current camera status."""
        try:
            if not self.api_interface.camera_controller:
                return {'success': False, 'error': 'Camera controller not initialized'}
            
            # Get actual camera status from controller
            status = self.api_interface.camera_controller.get_status()
            return {
                'success': True,
                'connected': status.get('connected', True),
                'position': status.get('position', [0, 0, 0]),
                'target': status.get('target', [0, 0, 0]),
                'up_vector': status.get('up_vector', [0, 1, 0]),
                'camera_path': status.get('camera_path', '/OmniverseKit_Persp'),
                'timestamp': time.time()
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def _set_camera_position(self, position: List[float], target: Optional[List[float]], 
                           up_vector: Optional[List[float]]) -> Dict:
        """Set camera position."""
        try:
            # Queue the operation for main thread processing (USD operations must be on main thread)
            params = {
                'position': position,
                'target': target,
                'up_vector': up_vector
            }
            return self._queue_camera_operation('set_position', params)
                
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def _frame_object(self, object_path: str, distance: Optional[float]) -> Dict:
        """Frame camera on object."""
        try:
            # Queue the operation for main thread processing
            params = {
                'object_path': object_path,
                'distance': distance
            }
            return self._queue_camera_operation('frame_object', params)
                
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def _orbit_camera(self, center: List[float], distance: float, 
                     elevation: float, azimuth: float) -> Dict:
        """Position camera in orbit around center."""
        try:
            # Queue the operation for main thread processing
            params = {
                'center': center,
                'distance': distance,
                'elevation': elevation,
                'azimuth': azimuth
            }
            return self._queue_camera_operation('orbit_camera', params)
                
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def _handle_smooth_move(self, data: Dict) -> Dict:
        """Handle smooth camera movement."""
        try:
            # Queue the operation for main thread processing
            return self._queue_camera_operation('smooth_move', data)
                
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def _handle_orbit_shot(self, data: Dict) -> Dict:
        """Handle cinematic orbit shot around a target object or position."""
        try:
            # Queue the operation for main thread processing (cinematic controller generates keyframes)
            return self._queue_camera_operation('orbit_shot', data)
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def _handle_stop_movement(self, data: Dict) -> Dict:
        """Stop ongoing camera movement."""
        try:
            # Queue the operation for main thread processing
            return self._queue_camera_operation('stop_movement', data)
                
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def _get_movement_status(self, movement_id: str) -> Dict:
        """Get status of a cinematic movement."""
        try:
            if not self.api_interface or not self.api_interface.camera_controller:
                return {'success': False, 'error': 'Camera controller not initialized'}
            cinematic_controller = self.api_interface.camera_controller.get_cinematic_controller()
            if hasattr(cinematic_controller, 'get_movement_status'):
                return cinematic_controller.get_movement_status(movement_id)
            return {'success': False, 'error': 'Movement status not supported'}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def _get_asset_transform(self, usd_path: str, calculation_mode: str) -> Dict:
        """Get asset transform information."""
        try:
            if not self.api_interface.camera_controller:
                return {'success': False, 'error': 'Camera controller not initialized'}
                
            # Use camera controller to get asset transform
            result = self.api_interface.camera_controller.get_asset_transform(usd_path, calculation_mode)
            
            if result.get('success'):
                result.update({
                    'timestamp': time.time(),
                    'source': 'worldviewer'
                })
            
            return result
            
        except Exception as e:
            return {'success': False, 'error': str(e)}

    # Removed legacy metrics and direct send methods; base handles responses/metrics

    def _queue_camera_operation(self, operation: str, params: Dict) -> Dict:
        """Queue a camera operation for thread-safe processing on main thread."""
        import uuid
        request_id = f"camera_{operation}_{int(time.time() * 1000)}_{uuid.uuid4().hex[:8]}"
        
        # Create request object
        request = {
            'request_id': request_id,
            'operation': operation,
            'params': params,
            'timestamp': time.time(),
            'completed': False,
            'result': None,
            'error': None
        }
        
        # Add to queue
        with self.api_interface._queue_lock:
            self.api_interface._camera_queue.append(request)
            self.api_interface._request_tracking[request_id] = request
        
        return {
            'success': True,
            'request_id': request_id,
            'operation': operation,
            'status': 'queued',
            'timestamp': time.time()
        }

    def _get_request_status(self, request_id: str) -> Dict:
        """Get the status of a queued request."""
        try:
            with self.api_interface._queue_lock:
                if request_id in self.api_interface._request_tracking:
                    request = self.api_interface._request_tracking[request_id]
                    return {
                        'success': True,
                        'request_id': request_id,
                        'operation': request['operation'],
                        'completed': request['completed'],
                        'result': request.get('result'),
                        'error': request.get('error'),
                        'timestamp': request['timestamp']
                    }
                else:
                    return {'success': False, 'error': f'Request {request_id} not found'}
        except Exception as e:
            return {'success': False, 'error': str(e)}
