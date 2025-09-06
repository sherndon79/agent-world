"""
Scene Builder Service - Modular Architecture

Batch scene creation system for programmatic USD scene construction.
Allows adding individual elements and creating complete batches with proper USD hierarchy.

This is the clean, modular version using factory patterns and specialized managers.
"""

import logging
import time
from typing import Dict, Any, List, Optional, Tuple
from collections import OrderedDict

try:
    from .config import get_config
    config = get_config()
except ImportError:
    config = None

import omni.usd
import omni.kit.app
from pxr import Usd, UsdGeom, Gf, Sdf

from .scene.scene_types import (
    PrimitiveType, 
    SceneElement, 
    SceneBatch, 
    AssetPlacement,
    RequestStatus,
    RequestState,
    RequestType
)
from .scene.queue_manager import WorldBuilderQueueManager
from .scene.element_factory import ElementFactory
from .scene.asset_manager import AssetManager
from .scene.cleanup_operations import CleanupOperations

logger = logging.getLogger(__name__)


class SceneBuilder:
    """
    Modular batch scene creation service for programmatic USD scene construction.
    
    Provides high-level API for creating complex scenes with proper USD hierarchy
    using specialized managers and factory patterns.
    """

    def __init__(self):
        """Initialize scene builder with modular architecture."""
        self._usd_context = omni.usd.get_context()
        self._current_batches: Dict[str, SceneBatch] = {}
        
        # Initialize modular components
        self._queue_manager = WorldBuilderQueueManager()
        self._element_factory = ElementFactory(self._usd_context)
        self._asset_manager = AssetManager(self._usd_context)
        self._cleanup_operations = CleanupOperations(self._usd_context)
        
        logger.info("🏗️ Scene Builder initialized with modular architecture")
    
    def _sanitize_usd_name(self, name: str) -> str:
        """Sanitize name for USD path compatibility by replacing invalid characters."""
        import re
        # Replace spaces and other problematic characters with underscores
        sanitized = re.sub(r'[^a-zA-Z0-9_\-]', '_', name)
        # Ensure it doesn't start with a number
        if sanitized and sanitized[0].isdigit():
            sanitized = f"_{sanitized}"
        return sanitized
    
    # =============================================================================
    # PUBLIC API METHODS - Queue-based operations
    # =============================================================================
    
    def add_element_to_stage(self, element: SceneElement) -> Dict[str, Any]:
        """
        Queue an element for creation on Isaac Sim's main thread.
        Returns immediately - actual USD creation happens asynchronously.
        """
        return self._queue_manager.add_element_request(element)

    def place_asset_in_stage(self, asset: AssetPlacement) -> Dict[str, Any]:
        """
        Queue an asset for placement on Isaac Sim's main thread via USD reference.
        Returns immediately - actual USD reference creation happens asynchronously.
        """
        return self._queue_manager.add_asset_request(asset, 'asset')

    def remove_element_from_stage(self, element_path: str) -> Dict[str, Any]:
        """
        Queue an element for removal from the USD stage.
        Returns immediately - actual USD removal happens asynchronously.
        """
        return self._queue_manager.add_removal_request('remove_element', element_path=element_path)

    def clear_stage_path(self, path: str) -> Dict[str, Any]:
        """
        Queue removal of all elements under a USD path.
        Useful for clearing entire batches or sections.
        """
        return self._queue_manager.add_removal_request('clear_path', path=path)

    def transform_asset_in_stage(self, prim_path: str, position: Optional[Tuple[float, float, float]] = None, 
                                rotation: Optional[Tuple[float, float, float]] = None, 
                                scale: Optional[Tuple[float, float, float]] = None) -> Dict[str, Any]:
        """
        Queue an existing asset for transformation on Isaac Sim's main thread.
        Returns immediately - actual USD transform happens asynchronously.
        """
        return self._queue_manager.add_transform_request(
            prim_path, 
            list(position) if position else None,
            list(rotation) if rotation else None, 
            list(scale) if scale else None
        )

    def create_batch_in_scene(self, batch_name: str, elements: List[Dict], 
                              batch_transform: Optional[Dict[str, Tuple[float, float, float]]] = None) -> Dict[str, Any]:
        """
        Create a complete USD batch Xform with all its child elements.
        Queued approach using modular queue manager.
        """
        return self._queue_manager.add_batch_request(batch_name, elements, batch_transform)

    def process_queued_requests(self) -> Dict[str, Any]:
        """
        Process queued requests on Isaac Sim's main thread using modular queue manager.
        This should be called regularly from the main thread (e.g., via timer).
        """
        return self._queue_manager.process_queues(
            element_processor=self._element_factory.create_element,
            batch_processor=self._create_batch_on_main_thread,
            asset_processor=self._process_asset_request,
            removal_processor=self._process_removal_request
        )
    
    # =============================================================================
    # PROCESSOR METHODS - Used by queue manager
    # =============================================================================
    
    def _process_asset_request(self, request_type: str, request_data) -> Dict[str, Any]:
        """Process asset-related requests for the queue manager using modular managers."""
        if request_type == 'place':
            return self._asset_manager.place_asset(request_data)
        elif request_type == 'transform':
            return self._asset_manager.transform_asset(
                request_data['prim_path'], 
                request_data.get('position'), 
                request_data.get('rotation'), 
                request_data.get('scale')
            )
        else:
            return {'success': False, 'error': f"Unknown asset request type: {request_type}"}
    
    def _process_removal_request(self, request_data: Dict) -> Dict[str, Any]:
        """Process removal requests for the queue manager using modular cleanup operations."""
        request_type = request_data['type']
        if request_type == 'remove_element':
            return self._cleanup_operations.remove_element(request_data['element_path'])
        elif request_type == 'clear_path':
            return self._cleanup_operations.clear_path(request_data['path'])
        else:
            return {'success': False, 'error': f"Unknown removal type: {request_type}"}

    def _create_batch_on_main_thread(self, batch_name: str, elements: List[Dict], 
                                     batch_transform: Optional[Dict[str, Tuple[float, float, float]]] = None) -> Dict[str, Any]:
        """
        Create batch in scene - MUST run on main thread for USD operations.
        Uses modular element factory for individual element creation.
        """
        try:
            # Get USD stage
            stage = self._usd_context.get_stage()
            if not stage:
                return {
                    'success': False,
                    'error': "No USD stage available. Please create or open a stage first."
                }
            
            # Parse elements from request data
            scene_elements = []
            for elem_data in elements:
                element = SceneElement(
                    name=elem_data.get('name', f'element_{int(time.time())}'),
                    primitive_type=PrimitiveType(elem_data.get('element_type', 'cube')),
                    position=tuple(elem_data.get('position', [0.0, 0.0, 0.0])),
                    rotation=tuple(elem_data.get('rotation', [0.0, 0.0, 0.0])),
                    scale=tuple(elem_data.get('scale', [1.0, 1.0, 1.0])),
                    color=tuple(elem_data.get('color', [0.5, 0.5, 0.5])),
                    metadata=elem_data.get('metadata', {})
                )
                scene_elements.append(element)
            
            # Set default batch transform
            batch_position = (0.0, 0.0, 0.0)
            batch_rotation = (0.0, 0.0, 0.0) 
            batch_scale = (1.0, 1.0, 1.0)
            
            # Apply batch transform if provided
            if batch_transform:
                batch_position = batch_transform.get('position', batch_position)
                batch_rotation = batch_transform.get('rotation', batch_rotation)
                batch_scale = batch_transform.get('scale', batch_scale)
            
            # Create batch Xform parent
            batch_path = f"/World/{self._sanitize_usd_name(batch_name)}"
            batch_xform = UsdGeom.Xform.Define(stage, batch_path)
            if not batch_xform:
                return {
                    'success': False,
                    'error': f"Failed to create batch Xform at {batch_path}"
                }
            
            # Apply batch transform
            self._set_transform(batch_xform, batch_position, batch_rotation, batch_scale)
            
            # Create all elements in the batch using element factory
            created_elements = []
            for element in scene_elements:
                # Temporarily adjust element name to include batch path
                original_name = element.name
                element.name = f"{self._sanitize_usd_name(batch_name)}/{original_name}"
                
                # Use element factory to create the element
                result = self._element_factory.create_element(element)
                
                # Restore original name
                element.name = original_name
                
                if result['success']:
                    created_elements.append({
                        'name': original_name,
                        'type': element.primitive_type.value,
                        'path': result['usd_path'],
                        'position': element.position
                    })
                else:
                    logger.warning(f"⚠️ Failed to create element '{original_name}' in batch: {result.get('error')}")
            
            # Create SceneBatch object and store in _current_batches for tracking
            scene_batch = SceneBatch(
                batch_name=batch_name,
                elements=scene_elements,
                batch_position=batch_position,
                batch_rotation=batch_rotation,
                batch_scale=batch_scale,
                metadata={'path': batch_path, 'created_at': time.time()}
            )
            self._current_batches[batch_name] = scene_batch
            
            logger.info(f"🎯 Created batch '{batch_name}' with {len(created_elements)} elements at {batch_path}")
            
            return {
                'success': True,
                'batch_name': batch_name,
                'batch_path': batch_path,
                'elements_created': len(created_elements),
                'elements': created_elements,
                'message': f"Created batch '{batch_name}' with {len(created_elements)} elements"
            }
            
        except Exception as e:
            logger.error(f"❌ Error in batch creation: {e}")
            return {
                'success': False,
                'error': str(e),
                'batch_name': batch_name
            }
    
    def _set_transform(self, xformable: UsdGeom.Xformable, 
                      position: Tuple[float, float, float],
                      rotation: Tuple[float, float, float],
                      scale: Tuple[float, float, float]):
        """Apply transform operations to a USD Xformable prim."""
        try:
            # Clear existing transforms to ensure clean state
            xformable.ClearXformOpOrder()
            
            # Add transform operations in TRS order (Translate, Rotate, Scale)
            if any(position):
                translate_op = xformable.AddTranslateOp()
                translate_op.Set(Gf.Vec3d(*position))
            
            if any(rotation):
                rotate_op = xformable.AddRotateXYZOp()
                rotate_op.Set(Gf.Vec3f(*rotation))  # USD expects degrees for Euler rotations
            
            if any(s != 1.0 for s in scale):
                scale_op = xformable.AddScaleOp()
                scale_op.Set(Gf.Vec3f(*scale))
                
        except Exception as e:
            logger.error(f"❌ Error setting transform: {e}")

    # =============================================================================
    # SCENE INSPECTION AND STATISTICS
    # =============================================================================

    def get_scene_contents(self, include_metadata: bool = True) -> Dict[str, Any]:
        """
        Get comprehensive scene contents using traversal.
        This method should be called from main thread for USD stage access.
        """
        try:
            # Get USD stage
            stage = self._usd_context.get_stage()
            if not stage:
                return {
                    'success': False,
                    'error': "No USD stage available. Cannot inspect scene contents."
                }
            
            # Get world prim as root
            world_prim = stage.GetPrimAtPath("/World")
            if not world_prim.IsValid():
                return {
                    'success': False, 
                    'error': "/World prim not found in scene"
                }
            
            # Inspect scene hierarchy
            scene_data = self._inspect_prim_recursive(world_prim, 0, max_depth=10)
            
            # Generate statistics
            stats = self._generate_scene_statistics(world_prim)
            
            result = {
                'success': True,
                'scene_root': '/World',
                'hierarchy': scene_data,
                'statistics': stats,
                'timestamp': time.time()
            }
            
            if include_metadata:
                result['metadata'] = {
                    'current_batches': len(self._current_batches),
                    'batch_names': list(self._current_batches.keys())
                }
            
            return result
            
        except Exception as e:
            logger.error(f"❌ Error getting scene contents: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    def _inspect_prim_recursive(self, prim: Usd.Prim, depth: int, max_depth: int = 5) -> Dict[str, Any]:
        """Recursively inspect a USD prim and its children."""
        if depth > max_depth:
            return {'name': prim.GetName(), 'truncated': True}
        
        prim_data = {
            'name': prim.GetName(),
            'path': str(prim.GetPath()),
            'type': prim.GetTypeName(),
            'active': prim.IsActive(),
            'children': []
        }
        
        # Add geometric info for geometric prims
        if prim.IsA(UsdGeom.Gprim):
            try:
                gprim = UsdGeom.Gprim(prim)
                # Get bounding box if possible
                bbox = gprim.ComputeWorldBound(Usd.TimeCode.Default(), UsdGeom.Tokens.default_)
                if bbox:
                    prim_data['bounds'] = {
                        'min': list(bbox.GetRange().GetMin()),
                        'max': list(bbox.GetRange().GetMax())
                    }
            except:
                pass  # Bounds calculation can fail, that's ok
        
        # Recursively inspect children
        current_depth = depth + 1
        for child in prim.GetChildren():
            prim_data['children'].append(self._inspect_prim_recursive(child, current_depth, max_depth))
        
        return prim_data

    def _generate_scene_statistics(self, world_prim: Usd.Prim) -> Dict[str, Any]:
        """Generate scene statistics from USD traversal."""
        stats = {
            'total_prims': 0,
            'active_prims': 0,
            'prim_types': {},
            'geometric_prims': 0
        }
        
        # Traverse and count
        for prim in world_prim.GetAllDescendants():
            stats['total_prims'] += 1
            
            if prim.IsActive():
                stats['active_prims'] += 1
            
            prim_type = prim.GetTypeName()
            stats['prim_types'][prim_type] = stats['prim_types'].get(prim_type, 0) + 1
            
            if prim.IsA(UsdGeom.Gprim):
                stats['geometric_prims'] += 1
        
        return stats

    def list_elements_in_scene(self, filter_type: str = "") -> Dict[str, Any]:
        """List all elements in the scene with optional type filtering."""
        try:
            stage = self._usd_context.get_stage()
            if not stage:
                return {'success': False, 'error': "No USD stage available"}
            
            elements = []
            world_prim = stage.GetPrimAtPath("/World")
            if not world_prim.IsValid():
                return {'success': False, 'error': "/World prim not found"}
            
            # Traverse and collect elements
            for prim in world_prim.GetAllDescendants():
                if not prim.IsActive():
                    continue
                    
                prim_type = prim.GetTypeName()
                if filter_type and prim_type != filter_type:
                    continue
                
                element_info = {
                    'name': prim.GetName(),
                    'path': str(prim.GetPath()),
                    'type': prim_type,
                    'is_geometric': prim.IsA(UsdGeom.Gprim)
                }
                
                # Get transform info if it's an Xformable
                if prim.IsA(UsdGeom.Xformable):
                    try:
                        xformable = UsdGeom.Xformable(prim)
                        local_matrix = xformable.GetLocalTransformation()
                        translation = local_matrix.ExtractTranslation()
                        element_info['position'] = [translation[0], translation[1], translation[2]]
                    except:
                        element_info['position'] = None
                
                elements.append(element_info)
            
            return {
                'success': True,
                'element_count': len(elements),
                'filter_type': filter_type or "all",
                'elements': elements
            }
            
        except Exception as e:
            logger.error(f"❌ Error listing scene elements: {e}")
            return {'success': False, 'error': str(e)}

    def get_request_status(self, request_id: str) -> Dict[str, Any]:
        """Get status of a queued request using modular queue manager."""
        try:
            result = self._queue_manager.get_request_status(request_id)
            if result:
                return {
                    'success': True,
                    'request_id': request_id,
                    'status': 'completed',
                    'completed_time': result['completed_time'],
                    'result': result['result']
                }
            else:
                return {
                    'success': False,
                    'request_id': request_id,
                    'status': 'not_found',
                    'error': f'Request {request_id} not found'
                }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }

    def get_statistics(self) -> Dict[str, Any]:
        """Get scene builder statistics using modular queue manager."""
        queue_status = self._queue_manager.get_queue_status()
        return {
            **queue_status['statistics'],
            'pending_batches': len(self._current_batches),
            'pending_elements': sum(len(batch.elements) for batch in self._current_batches.values()),
            'queue_status': queue_status['queue_lengths']
        }