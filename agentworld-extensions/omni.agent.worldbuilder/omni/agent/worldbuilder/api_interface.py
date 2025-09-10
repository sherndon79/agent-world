"""
HTTP API interface for WorldBuilder communication.
"""

import sys
import logging
from pathlib import Path
import socket
import struct
import threading
import time
from datetime import datetime
from http.server import ThreadingHTTPServer
from typing import Optional

# Import unified systems from agentworld-extensions root
try:
    current = Path(__file__).resolve()
    for _ in range(10):
        if current.name == 'agentworld-extensions':
            sys.path.insert(0, str(current))
            break
        current = current.parent
    
    from agent_world_metrics import setup_worldbuilder_metrics
    METRICS_AVAILABLE = True
except ImportError as e:
    logging.getLogger(__name__).warning(f"Could not import unified metrics system: {e}")
    METRICS_AVAILABLE = False

from .config import get_config
from agent_world_logging import setup_logging
from .http_handler import WorldBuilderHTTPHandler
from .scene_builder import SceneBuilder
from .security import WorldBuilderAuth

logger = logging.getLogger(__name__)


class HTTPAPIInterface:
    """HTTP API interface for WorldBuilder communication."""
    
    def __init__(self, port: Optional[int] = None):
        # Initialize unified logging once
        setup_logging('worldbuilder')
        self._config = get_config()
        self._port = port or self._config.server_port
        self._server = None
        self._server_thread = None
        self.security_manager = WorldBuilderAuth(config=self._config)
        
        # Initialize scene builder
        self._scene_builder = SceneBuilder()
        
        # Thread coordination
        self._main_thread_id = threading.get_ident()
        self._shutdown_requested = threading.Event()
        
        # Always initialize _api_stats for backward compatibility
        self._api_stats = {
            'requests_received': 0,
            'successful_requests': 0,
            'failed_requests': 0,
            'server_running': False,
            'start_time': None,
            'scene_elements_created': 0
        }
        
        # Initialize unified metrics system (thread-safe)
        if METRICS_AVAILABLE:
            self.metrics = setup_worldbuilder_metrics()
            # Note: Don't register USD-dependent gauges here - do it after server starts
            # to avoid threading issues with USD context access
        
        # Add server ready synchronization
        self._server_ready = threading.Event()
        
        # Start the HTTP server immediately with error protection
        try:
            if self._config.debug_mode:
                logger.info(f"WorldBuilder API initializing on port {self._port}")
            self._start_server()
        except Exception as e:
            logger.error(f"WorldBuilder API startup failed: {e}")
            # Don't re-raise - allow object creation (protected constructor pattern)
    
    def _start_server(self):
        """Start the HTTP server."""
        try:
            # Create handler class using unified factory method
            handler_class = WorldBuilderHTTPHandler.create_handler_class(self, 'worldbuilder')
            
            # Try multiple ports if configured
            ports_to_try = self._config.server_ports_to_try if hasattr(self._config, 'server_ports_to_try') else [self._port]
            server_started = False
            
            for port in ports_to_try:
                try:
                    # Start server with socket reuse
                    self._server = ThreadingHTTPServer((self._config.server_host, port), handler_class)
                    self._server.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                    self._server.socket.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack('ii', 1, 0))
                    self._port = port  # Update port if different from default
                    server_started = True
                    break
                except OSError as e:
                    if e.errno == 98:  # Address already in use
                        logger.warning(f"Port {port} already in use, trying next port...")
                        if self._server:
                            try:
                                self._server.server_close()
                            except Exception:
                                pass
                        continue
                    else:
                        raise
            
            if not server_started:
                raise RuntimeError("Could not bind to any available port")
            
            # Start server thread
            self._server_thread = threading.Thread(
                target=self._run_server,
                name=f"WorldBuilder-HTTP-{self._port}",
                daemon=True
            )
            self._server_thread.start()
            
            # Wait for server readiness
            if self._server_ready.wait(timeout=5):
                logger.info(f"WorldBuilder HTTP API server started on port {self._port}")
            else:
                logger.warning("WorldBuilder HTTP API server start timeout")
                
        except Exception as e:
            logger.error(f"Failed to start WorldBuilder HTTP server: {e}")
            raise
    
    def _run_server(self):
        """Run the HTTP server in background thread."""
        try:
            # Start metrics system
            if METRICS_AVAILABLE:
                self.metrics.start_server()
                # Register USD-dependent gauges after server starts (main thread safe)
                try:
                    self.metrics.register_gauge(
                        'scene_objects',
                        'Objects in current scene', 
                        lambda: self._get_scene_object_count()
                    )
                except Exception as e:
                    if self._config.debug_mode:
                        logger.warning(f"Could not register scene objects gauge: {e}")
            else:
                self._api_stats['server_running'] = True
                self._api_stats['start_time'] = time.time()
                
            self._server_ready.set()
            
            if self._config.debug_mode:
                logger.info(f"WorldBuilder HTTP server thread started on port {self._port}")
            
            self._server.serve_forever()
            
        except Exception as e:
            if not self._shutdown_requested.is_set():
                logger.error(f"WorldBuilder HTTP server error: {e}")
        finally:
            # Stop metrics system
            if METRICS_AVAILABLE:
                self.metrics.stop_server()
            else:
                self._api_stats['server_running'] = False
                
            if self._config.debug_mode:
                logger.info("WorldBuilder HTTP server thread stopped")
    
    def is_running(self) -> bool:
        """Check if the server is running."""
        if METRICS_AVAILABLE:
            return hasattr(self, 'metrics') and self.metrics.get_stats_dict().get('server_running', False)
        else:
            return self._api_stats.get('server_running', False)
    
    def _get_scene_object_count(self) -> int:
        """Get current number of objects in scene for metrics."""
        try:
            if self._scene_builder and hasattr(self._scene_builder, '_usd_context'):
                stage = self._scene_builder._usd_context.get_stage()
                if stage:
                    world_prim = stage.GetPrimAtPath('/World')
                    if world_prim:
                        return len(list(world_prim.GetAllChildren()))
        except Exception:
            pass
        return 0
    
    def get_port(self):
        """Get the server port (for health endpoint compatibility)."""
        return self._port
    
    def increment_request_counter(self):
        """Increment request counter - backward compatibility."""
        if METRICS_AVAILABLE and hasattr(self, 'metrics'):
            self.metrics.increment_requests()
        else:
            self._api_stats['requests_received'] += 1
    
    def increment_error_counter(self):
        """Increment error counter - backward compatibility."""
        if METRICS_AVAILABLE and hasattr(self, 'metrics'):
            self.metrics.increment_errors()
        else:
            self._api_stats['failed_requests'] += 1
    
    def get_stats(self):
        """Get statistics - backward compatibility."""
        if METRICS_AVAILABLE and hasattr(self, 'metrics'):
            return self.metrics.get_stats_dict()
        else:
            return self._api_stats.copy()
    
    def process_queued_operations(self):
        """Process any queued operations from the scene builder."""
        if self._scene_builder:
            self._scene_builder.process_queued_requests()
    
    def shutdown(self):
        """Shutdown the HTTP server and cleanup."""
        try:
            self._shutdown_requested.set()
            
            # Stop metrics system
            if METRICS_AVAILABLE and hasattr(self, 'metrics'):
                self.metrics.stop_server()
            else:
                self._api_stats['server_running'] = False
            
            if self._server:
                if self._config.debug_mode:
                    logger.info("Shutting down WorldBuilder HTTP server")
                self._server.shutdown()
                self._server.server_close()
                
            if self._server_thread and self._server_thread.is_alive():
                self._server_thread.join(timeout=2)
                
            logger.info("WorldBuilder HTTP API shutdown complete")
            
        except Exception as e:
            logger.error(f"Error during WorldBuilder HTTP shutdown: {e}")
        finally:
            self._server = None
            self._server_thread = None

    # Query methods restored from backup
    def _query_objects_by_type(self, object_type: str):
        """Query objects by semantic type (e.g., 'furniture', 'cube', 'sphere')."""
        try:
            import omni.usd
            from pxr import Usd, UsdGeom
            
            context = omni.usd.get_context()
            stage = context.get_stage()
            
            if not stage:
                return {'success': False, 'error': 'No USD stage available'}
            
            matching_objects = []
            object_type_lower = object_type.lower()
            
            # Traverse stage to find matching objects
            for prim in stage.Traverse():
                if not prim.IsValid():
                    continue
                
                # Check by USD type name
                type_name = prim.GetTypeName().lower()
                if object_type_lower in type_name:
                    obj_info = self._extract_object_info(prim)
                    if obj_info:
                        matching_objects.append(obj_info)
                    continue
                
                # Check by name contains type
                prim_name = prim.GetName().lower()
                if object_type_lower in prim_name:
                    obj_info = self._extract_object_info(prim)
                    if obj_info:
                        matching_objects.append(obj_info)
                    continue
                
                # Check semantic keywords
                if self._matches_semantic_type(prim_name, type_name, object_type_lower):
                    obj_info = self._extract_object_info(prim)
                    if obj_info:
                        matching_objects.append(obj_info)
            
            return {
                'success': True,
                'objects': matching_objects,
                'count': len(matching_objects),
                'query_type': object_type,
                'timestamp': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error querying objects by type: {e}")
            return {
                'success': False,
                'error': str(e),
                'timestamp': datetime.utcnow().isoformat()
            }

    def _query_objects_in_bounds(self, min_bounds: list, max_bounds: list):
        """Query objects within spatial bounds."""
        try:
            import omni.usd
            from pxr import Usd, UsdGeom
            
            context = omni.usd.get_context()
            stage = context.get_stage()
            
            if not stage:
                return {'success': False, 'error': 'No USD stage available'}
            
            matching_objects = []
            min_x, min_y, min_z = min_bounds
            max_x, max_y, max_z = max_bounds
            
            # Traverse stage to find objects within bounds
            for prim in stage.Traverse():
                if not prim.IsValid() or not self._is_geometric_object(prim):
                    continue
                
                # Get object position
                position = self._get_object_position(prim)
                if not position:
                    continue
                
                x, y, z = position
                
                # Check if position is within bounds
                if (min_x <= x <= max_x and 
                    min_y <= y <= max_y and 
                    min_z <= z <= max_z):
                    
                    obj_info = self._extract_object_info(prim)
                    if obj_info:
                        matching_objects.append(obj_info)
            
            return {
                'success': True,
                'objects': matching_objects,
                'count': len(matching_objects),
                'bounds': {'min': min_bounds, 'max': max_bounds},
                'timestamp': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error querying objects in bounds: {e}")
            return {
                'success': False,
                'error': str(e),
                'timestamp': datetime.utcnow().isoformat()
            }

    def _query_objects_near_point(self, point: list, radius: float):
        """Query objects near a specific point within radius."""
        try:
            import omni.usd
            from pxr import Usd, UsdGeom
            import math
            
            context = omni.usd.get_context()
            stage = context.get_stage()
            
            if not stage:
                return {'success': False, 'error': 'No USD stage available'}
            
            matching_objects = []
            px, py, pz = point
            
            # Traverse stage to find objects near point
            for prim in stage.Traverse():
                if not prim.IsValid() or not self._is_geometric_object(prim):
                    continue
                
                # Get object position
                position = self._get_object_position(prim)
                if not position:
                    continue
                
                x, y, z = position
                
                # Calculate distance from point
                distance = math.sqrt((x - px)**2 + (y - py)**2 + (z - pz)**2)
                
                if distance <= radius:
                    obj_info = self._extract_object_info(prim)
                    if obj_info:
                        obj_info['distance_from_point'] = distance
                        matching_objects.append(obj_info)
            
            # Sort by distance (closest first)
            matching_objects.sort(key=lambda obj: obj.get('distance_from_point', float('inf')))
            
            return {
                'success': True,
                'objects': matching_objects,
                'count': len(matching_objects),
                'query_point': point,
                'radius': radius,
                'timestamp': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error querying objects near point: {e}")
            return {
                'success': False,
                'error': str(e),
                'timestamp': datetime.utcnow().isoformat()
            }

    # Utility functions restored from backup
    def _calculate_bounds(self, object_paths: list):
        """Calculate combined bounding box using the reliable BoundsCalculator."""
        try:
            import omni.usd
            from .bounds_calculator import BoundsCalculator
            
            context = omni.usd.get_context()
            stage = context.get_stage()
            
            if not stage:
                return {'success': False, 'error': 'No USD stage available'}
            
            if not object_paths:
                return {'success': False, 'error': 'No objects provided'}
            
            # Use the same reliable bounds calculation as the UI
            bounds_calculator = BoundsCalculator()
            bounds_data = bounds_calculator.calculate_selection_bounds(stage, object_paths)
            
            if not bounds_data:
                return {
                    'success': False,
                    'error': 'No valid objects with bounds found',
                    'timestamp': datetime.utcnow().isoformat()
                }
            
            # Format results to match expected API format
            combined_bounds = {
                'min': bounds_data['min'],
                'max': bounds_data['max'], 
                'center': bounds_data['center'],
                'size': bounds_data['size'],
                'volume': bounds_data['size'][0] * bounds_data['size'][1] * bounds_data['size'][2]
            }
            
            return {
                'success': True,
                'bounds': combined_bounds,
                'objects_processed': object_paths,
                'object_count': len(object_paths),
                'timestamp': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error calculating bounds: {e}")
            return {
                'success': False,
                'error': str(e),
                'timestamp': datetime.utcnow().isoformat()
            }

    def _find_ground_level(self, position: list, search_radius: float = 10.0):
        """Find ground level at position using consensus algorithm."""
        try:
            import omni.usd
            from pxr import Usd, UsdGeom
            import math
            
            context = omni.usd.get_context()
            stage = context.get_stage()
            
            if not stage:
                return {'success': False, 'error': 'No USD stage available'}
            
            px, py, pz = position
            
            # Find all objects within search radius
            objects_in_area = []
            lowest_points = []
            
            for prim in stage.Traverse():
                if not prim.IsValid() or not self._is_geometric_object(prim):
                    continue
                
                # Get object position
                obj_position = self._get_object_position(prim)
                if not obj_position:
                    continue
                
                x, y, z = obj_position
                
                # Check if object is within search radius (2D distance from position)
                distance = math.sqrt((x - px)**2 + (z - pz)**2)
                
                if distance <= search_radius:
                    try:
                        # Get object's lowest point
                        bbox_cache = UsdGeom.BBoxCache(Usd.TimeCode.Default(), ['default'])
                        bound = bbox_cache.ComputeWorldBound(prim)
                        
                        # Check if bounding box is empty using USD API
                        if not bound.GetRange().IsEmpty():
                            bbox_range = bound.ComputeAlignedRange()
                            min_point = bbox_range.GetMin()
                            lowest_y = float(min_point[1])  # Y is up in Isaac Sim
                            lowest_points.append(lowest_y)
                            objects_in_area.append({
                                'path': str(prim.GetPath()),
                                'name': prim.GetName(),
                                'type': prim.GetTypeName(),
                                'position': [float(x), float(y), float(z)],
                                'distance': distance,
                                'lowest_y': lowest_y
                            })
                    
                    except Exception as e:
                        logger.debug(f"Error processing object {prim.GetPath()}: {e}")
                        # Fallback: use object center Y as lowest point
                        lowest_points.append(float(y))
                        objects_in_area.append({
                            'path': str(prim.GetPath()),
                            'name': prim.GetName(),
                            'type': prim.GetTypeName(),
                            'position': [float(x), float(y), float(z)],
                            'distance': distance,
                            'lowest_y': float(y)
                        })
            
            if not lowest_points:
                return {
                    'success': True,
                    'ground_level': 0.0,  # Default ground level if no objects found
                    'method': 'default_level',
                    'search_position': position,
                    'search_radius': search_radius,
                    'objects_analyzed': 0,
                    'timestamp': datetime.utcnow().isoformat()
                }
            
            # Calculate ground level as the lowest point found
            ground_level = min(lowest_points)
            
            return {
                'success': True,
                'ground_level': ground_level,
                'absolute_minimum': ground_level,
                'method': 'absolute_minimum',
                'search_position': position,
                'search_radius': search_radius,
                'objects_analyzed': len(objects_in_area),
                'objects_in_area': objects_in_area[:10],  # Limit for response size
                'timestamp': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error finding ground level: {e}")
            return {
                'success': False,
                'error': str(e),
                'timestamp': datetime.utcnow().isoformat()
            }

    def _align_objects(self, object_paths: list, axis: str, alignment: str = 'center', spacing: float = None):
        """Align objects along specified axis with optional uniform spacing."""
        try:
            import omni.usd
            from pxr import Usd, UsdGeom
            
            context = omni.usd.get_context()
            stage = context.get_stage()
            
            if not stage:
                return {'success': False, 'error': 'No USD stage available'}
            
            if len(object_paths) < 2:
                return {'success': False, 'error': 'At least 2 objects required for alignment'}
            
            # Valid axes
            if axis not in ['x', 'y', 'z']:
                return {'success': False, 'error': "axis must be 'x', 'y', or 'z'"}
            
            # Get object information using proper Omniverse USD methods
            objects = []
            for obj_path in object_paths:
                prim = stage.GetPrimAtPath(obj_path)
                if not prim or not prim.IsValid():
                    logger.warning(f"Invalid object path: {obj_path}")
                    continue
                
                try:
                    # Use Omniverse-specific method (most reliable)
                    world_transform = omni.usd.get_world_transform_matrix(prim)
                    translation = world_transform.ExtractTranslation()
                    
                    objects.append({
                        'path': obj_path,
                        'prim': prim,
                        'position': [float(translation[0]), float(translation[1]), float(translation[2])],
                        'world_transform': world_transform
                    })
                    logger.info(f"Got position for {obj_path}: {[float(translation[0]), float(translation[1]), float(translation[2])]}")
                    
                except Exception as e:
                    logger.warning(f"Could not get transform for object {obj_path}: {e}")
                    continue
            
            if len(objects) < 2:
                logger.warning(f"Only found {len(objects)} valid objects out of {len(object_paths)} provided")
                return {'success': False, 'error': f'Not enough valid objects found for alignment. Found {len(objects)} out of {len(object_paths)} objects.'}
            
            # Use first object as reference
            reference_pos = objects[0]['position']
            axis_index = {'x': 0, 'y': 1, 'z': 2}[axis]
            
            # Apply alignment
            alignment_results = []
            
            for i, obj in enumerate(objects):
                current_pos = obj['position'].copy()
                new_pos = current_pos.copy()
                
                # Align to reference object's axis position
                new_pos[axis_index] = reference_pos[axis_index]
                
                # Apply spacing if specified
                if spacing is not None and i > 0:
                    new_pos[axis_index] += spacing * i
                
                # Apply transformation if position changed
                if new_pos != current_pos:
                    try:
                        # Use scene builder to transform the object
                        transform_result = self._scene_builder.transform_asset_in_stage(
                            obj['path'], tuple(new_pos), None, None
                        )
                        
                        transform_success = transform_result.get('success', False)
                        logger.info(f"Transform result for {obj['path']}: {transform_result}")
                        logger.info(f"Transform success: {transform_success}")
                        
                        alignment_results.append({
                            'object': obj['path'],
                            'old_position': current_pos,
                            'new_position': new_pos,
                            'transformed': transform_success
                        })
                    
                    except Exception as e:
                        logger.error(f"Error transforming object {obj['path']}: {e}")
                        alignment_results.append({
                            'object': obj['path'],
                            'old_position': current_pos,
                            'new_position': new_pos,
                            'transformed': False,
                            'error': str(e)
                        })
                else:
                    alignment_results.append({
                        'object': obj['path'],
                        'old_position': current_pos,
                        'new_position': new_pos,
                        'transformed': True,
                        'note': 'Already aligned'
                    })
            
            successful_alignments = sum(1 for result in alignment_results if result.get('transformed', False))
            
            return {
                'success': True,
                'axis': axis,
                'spacing': spacing,
                'objects_processed': len(alignment_results),
                'successful_alignments': successful_alignments,
                'alignment_results': alignment_results,
                'timestamp': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error aligning objects: {e}")
            return {
                'success': False,
                'error': str(e),
                'timestamp': datetime.utcnow().isoformat()
            }

    # Helper methods for query operations
    def _matches_semantic_type(self, prim_name: str, type_name: str, query_type: str) -> bool:
        """Check if object matches semantic type based on naming patterns."""
        # Define semantic mappings
        semantic_mappings = {
            'furniture': ['chair', 'table', 'desk', 'sofa', 'bed', 'cabinet', 'shelf'],
            'lighting': ['lamp', 'light', 'fixture', 'bulb', 'chandelier'],
            'decoration': ['plant', 'vase', 'picture', 'art', 'frame', 'ornament'],
            'architecture': ['wall', 'door', 'window', 'column', 'beam', 'floor', 'ceiling'],
            'vehicle': ['car', 'truck', 'bike', 'motorcycle', 'boat', 'plane'],
            'primitive': ['cube', 'sphere', 'cylinder', 'cone', 'plane', 'mesh']
        }
        
        if query_type in semantic_mappings:
            keywords = semantic_mappings[query_type]
            return any(keyword in prim_name or keyword in type_name for keyword in keywords)
        
        return False

    def _is_geometric_object(self, prim) -> bool:
        """Check if prim represents a geometric object using USD proper API."""
        try:
            from pxr import UsdGeom
            
            # Use USD's built-in geometric primitive detection
            # UsdGeomGprim is the base class for all geometric primitives
            return prim.IsA(UsdGeom.Gprim)
        except Exception:
            return False

    def _get_object_position(self, prim):
        """Get object world position using multiple USD methods."""
        try:
            from pxr import UsdGeom, Usd
            
            # Primary method: Try Xformable API
            if prim.HasAPI(UsdGeom.Xformable):
                xformable = UsdGeom.Xformable(prim)
                transform_matrix = xformable.ComputeLocalToWorldTransform(Usd.TimeCode.Default())
                translation = transform_matrix.ExtractTranslation()
                return (float(translation[0]), float(translation[1]), float(translation[2]))
            
            # Fallback method: Check for transform attributes directly
            if prim.IsA(UsdGeom.Gprim):
                for attr_name in ['xformOp:translate', 'translate']:
                    if prim.HasAttribute(attr_name):
                        attr = prim.GetAttribute(attr_name)
                        if attr.IsValid():
                            value = attr.Get()
                            if value:
                                return (float(value[0]), float(value[1]), float(value[2]))
            
            return None
            
        except Exception:
            return None

    def _extract_object_info(self, prim):
        """Extract basic object information for query results."""
        try:
            from pxr import UsdGeom, Usd
            
            path = str(prim.GetPath())
            name = prim.GetName()
            type_name = prim.GetTypeName()
            
            # Get position
            position = self._get_object_position(prim)
            if not position:
                position = (0.0, 0.0, 0.0)
            
            # Get basic bounding box info if available
            bounds = None
            try:
                bbox_cache = UsdGeom.BBoxCache(Usd.TimeCode.Default(), ['default'])
                bound = bbox_cache.ComputeWorldBound(prim)
                # Check if bounding box is empty using USD API
                if not bound.GetRange().IsEmpty():
                    bbox_range = bound.ComputeAlignedRange()
                    min_point = bbox_range.GetMin()
                    max_point = bbox_range.GetMax()
                    bounds = {
                        'min': [float(min_point[0]), float(min_point[1]), float(min_point[2])],
                        'max': [float(max_point[0]), float(max_point[1]), float(max_point[2])]
                    }
            except Exception:
                pass
            
            return {
                'path': path,
                'name': name,
                'type': type_name,
                'position': list(position),
                'bounds': bounds
            }
            
        except Exception as e:
            logger.debug(f"Error extracting object info: {e}")
            return None
