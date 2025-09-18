"""
HTTP request handler for Agent WorldBuilder API endpoints (unified HTTP).
"""

import logging
import time
from datetime import datetime

from .scene_builder import SceneElement, SceneBatch, AssetPlacement, PrimitiveType

try:
    from agent_world_http import WorldHTTPHandler
    UNIFIED = True
except ImportError:
    from http.server import BaseHTTPRequestHandler as WorldHTTPHandler  # type: ignore
    UNIFIED = False

try:
    from agent_world_versions import get_version, get_service_name
    VERSION_AVAILABLE = True
except ImportError:
    get_version = get_service_name = None
    VERSION_AVAILABLE = False

# Optional Pydantic for request validation
try:
    from pydantic import BaseModel, Field, ValidationError, conlist
    PydanticAvailable = True
except Exception:
    PydanticAvailable = False

logger = logging.getLogger(__name__)



class WorldBuilderHTTPHandler(WorldHTTPHandler):
    """HTTP request handler for Agent WorldBuilder API endpoints (unified)."""

    api_interface = None

    def get_routes(self):  # type: ignore[override]
        """Return route mappings for unified HTTP handler."""
        return {
            'get_extension_stats': self._handle_stats,
            'stats': self._handle_stats,
            'add_element': self._handle_add_element,
            'create_batch': self._handle_create_batch,
            'place_asset': self._handle_place_asset,
            'transform_asset': self._handle_transform_asset,
            'batch_info': self._handle_batch_info,
            'list_batches': self._handle_list_batches,
            'request_status': self._handle_request_status,
            'remove_element': self._handle_remove_element,
            'clear_path': self._handle_clear_path,
            'get_scene': self._handle_get_scene,
            'scene_contents': self._handle_get_scene,
            'list_elements': self._handle_list_elements,
            'scene_status': self._handle_scene_status,
            'query/objects_by_type': self._handle_query_by_type,
            'query/objects_in_bounds': self._handle_query_in_bounds,
            'query/objects_near_point': self._handle_query_near_point,
            'calculate_bounds': self._handle_calculate_bounds,
            'find_ground_level': self._handle_find_ground_level,
            'align_objects': self._handle_align_objects,
            'transform/calculate_bounds': self._handle_calculate_bounds,
            'transform/find_ground_level': self._handle_find_ground_level,
            'transform/align_objects': self._handle_align_objects,
        }
    
    # HTTP request handlers - unified base handles parsing, auth, and dispatch
    
    def _handle_stats(self, method: str = 'GET', request_data: dict | None = None):
        """Handle stats request."""
        try:
            return {
                'success': True,
                'stats': self.api_interface._api_stats.copy(),
                'timestamp': datetime.now().isoformat()
            }
        except Exception as e:
            return {'success': False, 'error': f'Stats error: {e}'}
    
    def _handle_add_element(self, method: str, request_data: dict):
        """Handle add element request."""
        try:
            if method != 'POST':
                return {'success': False, 'error': 'add_element requires POST method'}
            
            # Validate with Pydantic if available
            element_data = request_data
            if PydanticAvailable:
                class AddElementModel(BaseModel):
                    name: str = None
                    element_type: str = Field(default='cube')
                    position: list = Field(default=[0.0, 0.0, 0.0])
                    rotation: list = Field(default=[0.0, 0.0, 0.0])
                    scale: list = Field(default=[1.0, 1.0, 1.0])
                    color: list = Field(default=[0.5, 0.5, 0.5])
                    parent_path: str = Field(default='/World')
                    metadata: dict = Field(default_factory=dict)
                    
                try:
                    element_data = AddElementModel(**request_data).model_dump()
                except ValidationError as ve:
                    return {'success': False, 'error': f'Validation error: {ve}'}
            
            logger.debug(f"🔍 HTTP Handler received parent_path: '{element_data.get('parent_path', 'NOT_PROVIDED')}'")
            element = SceneElement(
                name=element_data.get('name', f'element_{int(time.time())}'),
                primitive_type=PrimitiveType(element_data.get('element_type', 'cube')),
                position=tuple(element_data.get('position', [0.0, 0.0, 0.0])),
                rotation=tuple(element_data.get('rotation', [0.0, 0.0, 0.0])),
                scale=tuple(element_data.get('scale', [1.0, 1.0, 1.0])),
                color=tuple(element_data.get('color', [0.5, 0.5, 0.5])),
                parent_path=element_data.get('parent_path', '/World'),
                metadata=element_data.get('metadata', {})
            )
            logger.debug(f"🔍 HTTP Handler created SceneElement with parent_path: '{element.parent_path}'")
            
            # Add element directly to USD stage
            response = self.api_interface._scene_builder.add_element_to_stage(element)
            if response.get('success'):
                self.api_interface._api_stats['scene_elements_created'] += 1
            return response
            
        except Exception as e:
            return {'success': False, 'error': f'Add element error: {e}'}
    
    def _handle_health(self):
        """Handle health check request."""
        if VERSION_AVAILABLE:
            service_name = get_service_name('worldbuilder')
            version = get_version('worldbuilder', 'api_version')
        else:
            # Fallback if centralized versioning is not available
            service_name = 'Agent WorldBuilder API'
            version = '0.1.0'
            
        port = self.api_interface.get_port() if self.api_interface else 8899
        
        # Get scene object count for extension-specific status
        scene_object_count = 0
        try:
            stage = self.api_interface._scene_builder._usd_context.get_stage()
            if stage:
                world_prim = stage.GetPrimAtPath('/World')
                if world_prim:
                    scene_object_count = len(list(world_prim.GetAllChildren()))
        except Exception:
            pass
            
        return {
            'success': True,
            'service': service_name,
            'version': version,
            'url': f'http://localhost:{port}',
            'timestamp': time.time(),
            # Extension-specific status - ALWAYS LAST
            'scene_object_count': scene_object_count
        }
    
    def _handle_metrics(self, request_data: dict):
        """Handle metrics endpoint request."""
        try:
            # Get API stats from interface
            api_stats = {}
            if self.api_interface:
                api_stats = getattr(self.api_interface, '_api_stats', {})
            
            # Get scene object count
            scene_object_count = 0
            try:
                stage = self.api_interface._scene_builder._usd_context.get_stage()
                if stage:
                    world_prim = stage.GetPrimAtPath('/World')
                    if world_prim:
                        scene_object_count = len(list(world_prim.GetAllChildren()))
            except Exception:
                pass
            
            # Calculate uptime
            uptime = 0.0
            start_time = api_stats.get('start_time', 0)
            if start_time:
                import time
                from datetime import datetime
                try:
                    # Convert ISO string to timestamp
                    if isinstance(start_time, str):
                        start_timestamp = datetime.fromisoformat(start_time.replace('Z', '+00:00')).timestamp()
                    else:
                        start_timestamp = float(start_time)
                    uptime = time.time() - start_timestamp
                except (ValueError, TypeError):
                    uptime = 0.0
                
            metrics = {
                'requests_received': api_stats.get('requests_received', 0),
                'errors': api_stats.get('failed_requests', 0),
                'elements_created': api_stats.get('elements_created', 0),
                'batches_created': api_stats.get('batches_created', 0),
                'assets_placed': api_stats.get('assets_placed', 0),
                'objects_queried': api_stats.get('objects_queried', 0),
                'transformations_applied': api_stats.get('transformations_applied', 0),
                'uptime_seconds': uptime,
                'scene_object_count': scene_object_count,
                'server_running': True,
                'start_time': start_time
            }
            
            return {'success': True, 'metrics': metrics}
        except Exception as e:
            return {'success': False, 'error': f'Metrics error: {e}'}
    
    def _get_prometheus_metrics(self) -> str:
        """Get Prometheus formatted metrics."""
        try:
            # Get API stats
            api_stats = {}
            if self.api_interface:
                api_stats = getattr(self.api_interface, '_api_stats', {})
            
            # Get scene object count
            scene_object_count = 0
            try:
                stage = self.api_interface._scene_builder._usd_context.get_stage()
                if stage:
                    world_prim = stage.GetPrimAtPath('/World')
                    if world_prim:
                        scene_object_count = len(list(world_prim.GetAllChildren()))
            except Exception:
                pass
            
            # Calculate uptime
            uptime = 0.0
            start_time = api_stats.get('start_time', 0)
            if start_time:
                import time
                from datetime import datetime
                try:
                    # Convert ISO string to timestamp
                    if isinstance(start_time, str):
                        start_timestamp = datetime.fromisoformat(start_time.replace('Z', '+00:00')).timestamp()
                    else:
                        start_timestamp = float(start_time)
                    uptime = time.time() - start_timestamp
                except (ValueError, TypeError):
                    uptime = 0.0
            
            return "\n".join([
                "# HELP worldbuilder_requests_total Total number of requests",
                "# TYPE worldbuilder_requests_total counter", 
                f"worldbuilder_requests_total {int(api_stats.get('requests_received', 0))}",
                "# HELP worldbuilder_errors_total Total number of errors",
                "# TYPE worldbuilder_errors_total counter",
                f"worldbuilder_errors_total {int(api_stats.get('failed_requests', 0))}",
                "# HELP worldbuilder_uptime_seconds Server uptime in seconds", 
                "# TYPE worldbuilder_uptime_seconds gauge",
                f"worldbuilder_uptime_seconds {uptime}",
                "# HELP worldbuilder_scene_objects Total objects in scene",
                "# TYPE worldbuilder_scene_objects gauge", 
                f"worldbuilder_scene_objects {scene_object_count}",
                ""
            ])
        except Exception as e:
            return f"# Error generating metrics: {e}\n"
    
    # HTTP response helpers handled by unified base class
    def _handle_create_batch(self, method: str, request_data: dict):
        """Handle create batch request.""" 
        try:
            if method != 'POST':
                return {'success': False, 'error': 'create_batch requires POST method'}
            return self.api_interface._scene_builder.create_batch_in_scene(
                request_data.get('batch_name', 'default_batch'),
                request_data.get('elements', []),
                request_data.get('transform', {})
            )
        except Exception as e:
            return {'success': False, 'error': f'Create batch error: {e}'}
    
    def _handle_place_asset(self, method: str, request_data: dict):
        """Handle place asset request."""
        try:
            if method != 'POST':
                return {'success': False, 'error': 'place_asset requires POST method'}
            
            asset = AssetPlacement(
                name=request_data.get('name', 'unnamed_asset'),
                asset_path=request_data.get('asset_path', ''),
                prim_path=request_data.get('prim_path', request_data.get('name', 'unnamed_asset')),
                position=tuple(request_data.get('position', [0.0, 0.0, 0.0])),
                rotation=tuple(request_data.get('rotation', [0.0, 0.0, 0.0])),
                scale=tuple(request_data.get('scale', [1.0, 1.0, 1.0])),
                metadata=request_data.get('metadata', {})
            )
            return self.api_interface._scene_builder.place_asset_in_stage(asset)
        except Exception as e:
            return {'success': False, 'error': f'Place asset error: {e}'}
    
    # Add other handler methods as needed...
    def _handle_transform_asset(self, method: str, request_data: dict):
        """Handle asset transformation request."""
        try:
            if method != 'POST':
                return {'success': False, 'error': 'transform_asset requires POST method'}
            
            prim_path = request_data.get('prim_path', '')
            if not prim_path:
                return {'success': False, 'error': 'prim_path is required'}
            
            position = request_data.get('position', None)
            rotation = request_data.get('rotation', None) 
            scale = request_data.get('scale', None)
            
            # Convert lists to tuples if provided
            if position is not None:
                position = tuple(position)
            if rotation is not None:
                rotation = tuple(rotation)
            if scale is not None:
                scale = tuple(scale)
            
            return self.api_interface._scene_builder.transform_asset_in_stage(
                prim_path, position, rotation, scale
            )
        except Exception as e:
            return {'success': False, 'error': f'Transform asset error: {e}'}
    
    def _handle_batch_info(self, method: str, request_data: dict):
        """Handle batch info request."""
        try:
            batch_name = request_data.get('batch_name', None)
            if isinstance(batch_name, list):
                batch_name = batch_name[0] if batch_name else None
            if not batch_name:
                return {'success': False, 'error': 'batch_name is required'}
            
            return self.api_interface._scene_builder.get_batch_info(batch_name)
        except Exception as e:
            return {'success': False, 'error': f'Batch info error: {e}'}
    
    def _handle_list_batches(self, method: str, request_data: dict):
        """Handle list batches request using stage discovery."""
        try:
            if method != 'GET':
                return {'success': False, 'error': 'list_batches requires GET method'}
            
            return self.api_interface._scene_builder.list_batches()
        except Exception as e:
            return {'success': False, 'error': f'List batches error: {e}'}
    
    def _handle_request_status(self, method: str, request_data: dict):
        """Handle request status check."""
        try:
            request_id = request_data.get('request_id', '')
            if not request_id:
                return {'success': False, 'error': 'request_id is required'}
            
            return self.api_interface._scene_builder.get_request_status(request_id)
        except Exception as e:
            return {'success': False, 'error': f'Request status error: {e}'}
    
    def _handle_remove_element(self, method: str, request_data: dict):
        """Handle remove element request."""
        try:
            if method != 'POST':
                return {'success': False, 'error': 'remove_element requires POST method'}
            
            element_path = request_data.get('element_path', '') or request_data.get('usd_path', '')
            if not element_path:
                return {'success': False, 'error': 'element_path is required'}
            
            return self.api_interface._scene_builder.remove_element_from_stage(element_path)
        except Exception as e:
            return {'success': False, 'error': f'Remove element error: {e}'}
    
    def _handle_clear_path(self, method: str, request_data: dict):
        """Handle clear path request."""
        try:
            if method != 'POST':
                return {'success': False, 'error': 'clear_path requires POST method'}
            
            path = request_data.get('path', '')
            if not path:
                return {'success': False, 'error': 'path is required'}
            
            return self.api_interface._scene_builder.clear_stage_path(path)
        except Exception as e:
            return {'success': False, 'error': f'Clear path error: {e}'}
    
    def _handle_get_scene(self, method: str, request_data: dict):
        """Handle get scene request."""
        try:
            path = request_data.get('path', '/World')
            if isinstance(path, list):
                path = path[0] if path else '/World'
            return self.api_interface._scene_builder.get_scene_contents(path)
        except Exception as e:
            return {'success': False, 'error': f'Get scene error: {e}'}
    
    def _handle_list_elements(self, method: str, request_data: dict):
        """Handle list elements request."""
        try:
            path = request_data.get('path', '/World')
            if isinstance(path, list):
                path = path[0] if path else '/World'
            return self.api_interface._scene_builder.list_elements_at_path(path)
        except Exception as e:
            return {'success': False, 'error': f'List elements error: {e}'}
    
    def _handle_scene_status(self, method: str = 'GET', request_data: dict | None = None):
        """Handle scene status request."""
        try:
            return self._get_scene_status()
        except Exception as e:
            return {'success': False, 'error': f'Scene status error: {e}'}
    
    def _get_scene_status(self):
        """Get scene health and basic statistics."""
        try:
            stage = self.api_interface._scene_builder._usd_context.get_stage()
            if not stage:
                return {'success': False, 'error': 'No active stage'}
            
            # Count prims at /World
            world_prim = stage.GetPrimAtPath('/World')
            total_prims = 0
            if world_prim:
                for prim in world_prim.GetAllChildren():
                    total_prims += 1
            
            return {
                'success': True,
                'scene_health': 'healthy',
                'total_prims': total_prims,
                'active_batches': len(self.api_interface._scene_builder._current_batches),
                'queued_operations': self.api_interface._scene_builder._queue_manager.get_queue_status()['queue_lengths'],
                'timestamp': datetime.now().isoformat()
            }
        except Exception as e:
            return {'success': False, 'error': f'Scene status error: {e}'}
    
    def _handle_query_by_type(self, method: str, request_data: dict):
        """Handle query by type request."""
        try:
            object_type = request_data.get('type') or request_data.get('object_type', '')
            if isinstance(object_type, list):
                object_type = object_type[0] if object_type else ''
            if not object_type:
                return {'success': False, 'error': 'type parameter is required'}
            
            # Use the scene builder's query method if it exists, otherwise delegate to api_interface
            if hasattr(self.api_interface, '_query_objects_by_type'):
                return self.api_interface._query_objects_by_type(object_type)
            else:
                return {'success': False, 'error': 'Query by type not implemented in scene builder'}
        except Exception as e:
            return {'success': False, 'error': f'Query by type error: {e}'}
    
    def _handle_query_in_bounds(self, method: str, request_data: dict):
        """Handle query in bounds request."""
        try:
            min_bounds = request_data.get('min') or request_data.get('min_bounds')
            max_bounds = request_data.get('max') or request_data.get('max_bounds')
            
            if not min_bounds or not max_bounds:
                return {'success': False, 'error': 'min and max bounds are required'}
            
            # Parse bounds parameters (handle both list and comma-separated string)
            if isinstance(min_bounds, list):
                min_bounds = min_bounds[0] if min_bounds else ''
            if isinstance(min_bounds, str):
                try:
                    min_bounds = [float(x.strip()) for x in min_bounds.split(',')]
                except ValueError:
                    return {'success': False, 'error': 'min bounds must be [x,y,z] coordinates or \'x,y,z\' string'}
            
            if isinstance(max_bounds, list):
                max_bounds = max_bounds[0] if max_bounds else ''
            if isinstance(max_bounds, str):
                try:
                    max_bounds = [float(x.strip()) for x in max_bounds.split(',')]
                except ValueError:
                    return {'success': False, 'error': 'max bounds must be [x,y,z] coordinates or \'x,y,z\' string'}
            
            if len(min_bounds) != 3 or len(max_bounds) != 3:
                return {'success': False, 'error': 'bounds must be [x,y,z] coordinates'}
            
            if hasattr(self.api_interface, '_query_objects_in_bounds'):
                return self.api_interface._query_objects_in_bounds(min_bounds, max_bounds)
            else:
                return {'success': False, 'error': 'Query in bounds not implemented in scene builder'}
        except Exception as e:
            return {'success': False, 'error': f'Query in bounds error: {e}'}
    
    def _handle_query_near_point(self, method: str, request_data: dict):
        """Handle query near point request."""
        try:
            point = request_data.get('point')
            radius = request_data.get('radius', 5.0)
            
            if not point:
                return {'success': False, 'error': 'point parameter is required'}
            
            # Parse point parameter (handle both list and comma-separated string)
            if isinstance(point, list):
                point = point[0] if point else ''
            if isinstance(point, str):
                try:
                    point = [float(x.strip()) for x in point.split(',')]
                except ValueError:
                    return {'success': False, 'error': 'point must be [x,y,z] coordinates or \'x,y,z\' string'}
            
            if len(point) != 3:
                return {'success': False, 'error': 'point must be [x,y,z] coordinates'}
            
            # Ensure radius is float
            try:
                radius = float(radius[0] if isinstance(radius, list) else radius)
            except Exception:
                radius = 5.0
            
            if hasattr(self.api_interface, '_query_objects_near_point'):
                return self.api_interface._query_objects_near_point(point, radius)
            else:
                return {'success': False, 'error': 'Query near point not implemented in scene builder'}
        except Exception as e:
            return {'success': False, 'error': f'Query near point error: {e}'}
    
    def _handle_calculate_bounds(self, method: str, request_data: dict):
        """Handle calculate bounds request."""
        try:
            objects = request_data.get('objects', [])
            if not objects:
                return {'success': False, 'error': 'objects parameter is required'}
            
            if hasattr(self.api_interface, '_calculate_bounds'):
                return self.api_interface._calculate_bounds(objects)
            else:
                return {'success': False, 'error': 'Calculate bounds not implemented in scene builder'}
        except Exception as e:
            return {'success': False, 'error': f'Calculate bounds error: {e}'}
    
    def _handle_find_ground_level(self, method: str, request_data: dict):
        """Handle find ground level request."""
        try:
            position = request_data.get('position')
            search_radius = request_data.get('search_radius', 10.0)
            # Normalize inputs from GET query
            if isinstance(position, list) and position and isinstance(position[0], str):
                # Could be repeated params like position=0&position=0&position=5
                if len(position) == 3:
                    try:
                        position = [float(x) for x in position]
                    except Exception:
                        pass
                else:
                    # Or a single string '0,0,5'
                    position = position[0]
            if isinstance(position, str):
                try:
                    position = [float(x.strip()) for x in position.split(',')]
                except Exception:
                    return {'success': False, 'error': 'position must be [x,y,z] coordinates'}
            try:
                search_radius = float(search_radius[0] if isinstance(search_radius, list) else search_radius)
            except Exception:
                search_radius = 10.0
            
            if not position or len(position) != 3:
                return {'success': False, 'error': 'position parameter is required as [x, y, z]'}
            
            if hasattr(self.api_interface, '_find_ground_level'):
                return self.api_interface._find_ground_level(position, search_radius)
            else:
                return {'success': False, 'error': 'Find ground level not implemented in scene builder'}
        except Exception as e:
            return {'success': False, 'error': f'Find ground level error: {e}'}
    
    def _handle_align_objects(self, method: str, request_data: dict):
        """Handle align objects request."""
        try:
            if method != 'POST':
                return {'success': False, 'error': 'align_objects requires POST method'}
            
            objects = request_data.get('objects', [])
            axis = request_data.get('axis', 'x')
            alignment = request_data.get('alignment', 'center')
            spacing = request_data.get('spacing', None)
            
            if not objects:
                return {'success': False, 'error': 'objects parameter is required'}
            
            if hasattr(self.api_interface, '_align_objects'):
                return self.api_interface._align_objects(objects, axis, alignment, spacing)
            else:
                return {'success': False, 'error': 'Align objects not implemented in scene builder'}
        except Exception as e:
            return {'success': False, 'error': f'Align objects error: {e}'}

    def log_message(self, format, *args):
        """Override default HTTP server logging to use our logger with proper levels."""
        # Only log HTTP server messages when debug mode is enabled
        config = self.api_interface._config
        if config.debug_mode or config.verbose_logging:
            logger.info(f"HTTP {format % args}")
        # Otherwise, suppress the default logging to stderr
