"""
Scene Builder Service - Modular Architecture

Batch scene creation system for programmatic USD scene construction.
Allows adding individual elements and creating complete batches with proper USD hierarchy.

This is the clean, modular version using factory patterns and specialized managers.
"""

import logging
import time
from typing import Dict, Any, List, Optional, Tuple, TYPE_CHECKING
from collections import OrderedDict

if TYPE_CHECKING:  # pragma: no cover - import only for type hints
    from .config import WorldBuilderConfig

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
from .scene.batch_manager import BatchManager

logger = logging.getLogger(__name__)


class SceneBuilder:
    """
    Modular batch scene creation service for programmatic USD scene construction.
    
    Provides high-level API for creating complex scenes with proper USD hierarchy
    using specialized managers and factory patterns.
    """

    def __init__(self, config: Optional['WorldBuilderConfig'] = None):
        """Initialize scene builder with modular architecture."""
        if config is None:
            try:
                from .config import get_config  # Local import to avoid cycles
                config = get_config()
            except ImportError:
                config = None

        self._config = config
        self._usd_context = omni.usd.get_context()
        
        # Initialize modular components
        self._queue_manager = WorldBuilderQueueManager(config=self._config)
        self._element_factory = ElementFactory(self._usd_context)
        self._asset_manager = AssetManager(self._usd_context)
        self._cleanup_operations = CleanupOperations(self._usd_context)
        self._batch_manager = BatchManager(self._usd_context, self._element_factory)
        
        logger.info("🏗️ Scene Builder initialized with modular architecture")
    
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
        Create batch in scene using modular batch manager.
        """
        return self._batch_manager.create_batch(batch_name, elements, batch_transform)
    
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

    def get_scene_contents(self, path: str = "/World", include_metadata: bool = True) -> Dict[str, Any]:
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
            
            # Get root prim at specified path
            root_prim = stage.GetPrimAtPath(path)
            if not root_prim.IsValid():
                return {
                    'success': False, 
                    'error': f"Path '{path}' not found in scene"
                }
            
            # Debug: Check if root prim has children
            children = list(root_prim.GetChildren())
            logger.debug(f"🔍 Debug: Root prim '{path}' has {len(children)} children")
            for child in children:
                logger.debug(f"  - Child: {child.GetPath()} (Type: {child.GetTypeName()})")
            
            # Inspect scene hierarchy
            scene_data = self._inspect_prim_recursive(root_prim, 0, max_depth=10)
            logger.debug(f"🔍 Debug: Scene data structure: {scene_data}")
            
            # Generate statistics
            stats = self._generate_scene_statistics(root_prim)
            
            result = {
                'success': True,
                'scene_root': path,
                'hierarchy': scene_data,
                'statistics': stats,
                'timestamp': time.time()
            }
            
            if include_metadata:
                # Use stage discovery instead of dual-state tracking
                discovered_batches = self._batch_manager.discover_batches_from_stage()
                result['metadata'] = {
                    'current_batches': len(discovered_batches),
                    'batch_names': list(discovered_batches.keys()),
                    'stage_based_discovery': True
                }
            
            return result
            
        except Exception as e:
            logger.error(f"❌ Error getting scene contents: {e}")
            import traceback
            logger.error(f"❌ Traceback: {traceback.format_exc()}")
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
        
        # Check if this Xform is a batch by looking for WorldBuilder metadata
        if prim.GetTypeName() == "Xform":
            is_batch_attr = prim.GetAttribute("worldbuilder:is_batch")
            if is_batch_attr and is_batch_attr.Get():
                prim_data['is_batch'] = True
                batch_name_attr = prim.GetAttribute("worldbuilder:batch_name")
                if batch_name_attr:
                    prim_data['batch_name'] = batch_name_attr.Get()
                created_at_attr = prim.GetAttribute("worldbuilder:batch_created_at") 
                if created_at_attr:
                    prim_data['batch_created_at'] = created_at_attr.Get()
                element_count_attr = prim.GetAttribute("worldbuilder:batch_element_count")
                if element_count_attr:
                    prim_data['batch_element_count'] = element_count_attr.Get()
        
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

    def _generate_scene_statistics(self, root_prim: Usd.Prim) -> Dict[str, Any]:
        """Generate scene statistics from USD traversal."""
        stats = {
            'total_prims': 0,
            'active_prims': 0,
            'prim_types': {},
            'geometric_prims': 0
        }
        
        # Traverse and count
        for child in root_prim.GetChildren():
            stats['total_prims'] += 1
            
            if child.IsActive():
                stats['active_prims'] += 1
            
            prim_type = child.GetTypeName()
            stats['prim_types'][prim_type] = stats['prim_types'].get(prim_type, 0) + 1
            
            if child.IsA(UsdGeom.Gprim):
                stats['geometric_prims'] += 1
        
        return stats

    def list_elements_in_scene(self, filter_type: str = "", *, start: int = 0, limit: Optional[int] = None) -> Dict[str, Any]:
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
            children = list(world_prim.GetChildren())
            total_children = len(children)
            slice_start = start if start >= 0 else 0
            slice_end = total_children if limit is None else min(total_children, slice_start + max(limit, 0))
            for child in children[slice_start:slice_end]:
                if not child.IsActive():
                    continue
                    
                prim_type = child.GetTypeName()
                if filter_type and prim_type != filter_type:
                    continue
                
                element_info = {
                    'name': child.GetName(),
                    'path': str(child.GetPath()),
                    'type': prim_type,
                    'is_geometric': child.IsA(UsdGeom.Gprim)
                }
                
                # Get transform info if it's an Xformable
                if child.IsA(UsdGeom.Xformable):
                    try:
                        xformable = UsdGeom.Xformable(child)
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

    def get_batch_info(self, batch_name: str) -> Dict[str, Any]:
        """Get detailed information about a specific batch using modular batch manager."""
        return self._batch_manager.get_batch_info(batch_name)
    
    def discover_batches_from_stage(self) -> Dict[str, Any]:
        """Discover all batches from USD stage metadata."""
        try:
            discovered_batches = self._batch_manager.discover_batches_from_stage()
            return {
                'success': True,
                'discovered_batches': discovered_batches,
                'batch_count': len(discovered_batches),
                'batch_names': list(discovered_batches.keys())
            }
        except Exception as e:
            logger.error(f"❌ Error discovering batches from stage: {e}")
            return {
                'success': False,
                'error': str(e),
                'discovered_batches': {},
                'batch_count': 0
            }
    
    def list_batches(self) -> Dict[str, Any]:
        """List all batches using stage discovery with fallback to memory tracking."""
        return self._batch_manager.list_batches()
    
    # clear_batch method removed - use clear_path("/World/batch_name") instead
    # This eliminates dual-state complexity and uses USD stage as single source of truth
    
    @property
    def _current_batches(self):
        """Property for backward compatibility with http_handler."""
        return self._batch_manager.current_batches
    
    def list_elements_at_path(self, path: str = "/World") -> Dict[str, Any]:
        """List elements at path using modular scene inspection."""
        return self.list_elements_in_scene()

    def get_statistics(self) -> Dict[str, Any]:
        """Get scene builder statistics using modular managers."""
        queue_status = self._queue_manager.get_queue_status()
        batch_stats = self._batch_manager.get_batch_statistics()
        
        return {
            **queue_status['statistics'],
            'pending_batches': batch_stats['total_batches'],
            'pending_elements': batch_stats['total_elements'],
            'queue_status': queue_status['queue_lengths'],
            'batch_statistics': batch_stats
        }
