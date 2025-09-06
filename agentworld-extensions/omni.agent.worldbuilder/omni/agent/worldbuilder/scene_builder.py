"""
Scene Builder Service

Batch scene creation system for programmatic USD scene construction.
Allows adding individual elements and creating complete batches with proper USD hierarchy.
"""

import logging
import time
from typing import Dict, Any, List, Optional, Tuple
from collections import OrderedDict
import sys
import os

# Add shared modules to path
shared_path = os.path.join(os.path.dirname(__file__), '..', '..', '..', '..', '..', 'shared')
if shared_path not in sys.path:
    sys.path.insert(0, shared_path)

try:
    from .config import get_config
    config = get_config()
except ImportError:
    # Fallback if shared config not available
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

logger = logging.getLogger(__name__)



class SceneBuilder:
    """
    Batch scene creation service for programmatic USD scene construction.
    
    Provides high-level API for creating complex scenes with proper USD hierarchy.
    """

    def __init__(self):
        """Initialize scene builder with modular queue-based processing."""
        self._usd_context = omni.usd.get_context()
        self._current_batches: Dict[str, SceneBatch] = {}
        
        # Modular queue manager
        self._queue_manager = WorldBuilderQueueManager()
        
        logger.info("🏗️ Scene Builder initialized with modular queue-based processing")
    
    def _sanitize_usd_name(self, name: str) -> str:
        """Sanitize name for USD path compatibility by replacing invalid characters."""
        import re
        # Replace spaces and other problematic characters with underscores
        sanitized = re.sub(r'[^a-zA-Z0-9_\-]', '_', name)
        # Ensure it doesn't start with a number
        if sanitized and sanitized[0].isdigit():
            sanitized = f"_{sanitized}"
        return sanitized
    

    def add_element_to_stage(self, element: SceneElement) -> Dict[str, Any]:
        """
        Queue an element for creation on Isaac Sim's main thread.
        Returns immediately - actual USD creation happens asynchronously.
        
        Args:
            element: SceneElement to queue for creation
            
        Returns:
            Result dictionary with request ID for status tracking
        """
        return self._queue_manager.add_element_request(element)

    def place_asset_in_stage(self, asset: AssetPlacement) -> Dict[str, Any]:
        """
        Queue an asset for placement on Isaac Sim's main thread via USD reference.
        Returns immediately - actual USD reference creation happens asynchronously.
        
        Args:
            asset: AssetPlacement to queue for placement
            
        Returns:
            Result dictionary with request ID for status tracking
        """
        return self._queue_manager.add_asset_request(asset, 'asset')

    def remove_element_from_stage(self, element_path: str) -> Dict[str, Any]:
        """
        Queue an element for removal from the USD stage.
        Returns immediately - actual USD removal happens asynchronously.
        
        Args:
            element_path: USD path of element to remove (e.g., "/World/my_cube")
            
        Returns:
            Result dictionary with request ID for status tracking
        """
        return self._queue_manager.add_removal_request('remove_element', element_path=element_path)

    def clear_stage_path(self, path: str) -> Dict[str, Any]:
        """
        Queue removal of all elements under a USD path.
        Useful for clearing entire batches or sections.
        
        Args:
            path: USD path to clear (e.g., "/World/my_batch" or "/World")
            
        Returns:
            Result dictionary with request ID for status tracking
        """
        return self._queue_manager.add_removal_request('clear_path', path=path)

    def process_queued_requests(self) -> Dict[str, Any]:
        """
        Process queued requests on Isaac Sim's main thread using modular queue manager.
        This should be called regularly from the main thread (e.g., via timer).
        
        Returns:
            Processing statistics
        """
        return self._queue_manager.process_queues(
            element_processor=self._create_element_on_main_thread,
            batch_processor=self._create_batch_on_main_thread,
            asset_processor=self._process_asset_request,
            removal_processor=self._process_removal_request
        )

    def _create_element_on_main_thread(self, element: SceneElement) -> Dict[str, Any]:
        """Create element safely on Isaac Sim's main thread."""
        try:
            # Get USD stage
            stage = self._usd_context.get_stage()
            if not stage:
                return {
                    'success': False,
                    'error': "No USD stage available. Please create or open a stage first."
                }
            
            # Create element directly in /World/
            element_path = f"/World/{element.name}"
            
            # Create primitive based on type
            prim = self._create_primitive(stage, element_path, element.primitive_type)
            if not prim:
                return {
                    'success': False,
                    'error': f"Failed to create {element.primitive_type.value} primitive"
                }
            
            # Set element transform
            if hasattr(prim, 'GetXformOpOrderAttr'):  # It's an Xformable
                self._set_transform(prim, element.position, element.rotation, element.scale)
            
            # Set color
            self._set_color(prim, element.color)
            
            return {
                'success': True,
                'element_name': element.name,
                'element_type': element.primitive_type.value,
                'usd_path': element_path,
                'position': element.position,
                'message': f"Created {element.name} in USD stage"
            }
            
        except Exception as e:
            logger.error(f"❌ Error in main thread element creation: {e}")
            return {
                'success': False,
                'error': str(e),
                'element_name': element.name
            }

    def _place_asset_on_main_thread(self, asset: AssetPlacement) -> Dict[str, Any]:
        """Place asset via USD reference safely on Isaac Sim's main thread."""
        try:
            # Get USD stage
            stage = self._usd_context.get_stage()
            if not stage:
                return {
                    'success': False,
                    'error': "No USD stage available. Please create or open a stage first."
                }
            
            # Validate asset path exists
            if not self._validate_asset_path(asset.asset_path):
                return {
                    'success': False,
                    'error': f"Asset file not found: {asset.asset_path}"
                }
            
            # Create USD reference prim
            prim_path = asset.prim_path if asset.prim_path.startswith('/') else f"/World/{asset.prim_path}"
            
            # Define the reference prim
            prim = stage.DefinePrim(prim_path)
            if not prim:
                return {
                    'success': False,
                    'error': f"Failed to create prim at path: {prim_path}"
                }
            
            # Add USD reference
            references = prim.GetReferences()
            references.AddReference(asset.asset_path)
            
            # Apply transforms to the container prim (not the referenced content)
            if any(asset.position) or any(asset.rotation) or any(v != 1.0 for v in asset.scale):
                try:
                    # Make the container prim transformable (correct approach for references)
                    xformable = UsdGeom.Xformable(prim)
                    
                    # Clear any existing transforms on the container
                    xformable.ClearXformOpOrder()
                    
                    # Add transform operations in proper order: Translate, Rotate, Scale
                    if any(asset.position):
                        translate_op = xformable.AddTranslateOp()
                        translate_op.Set(Gf.Vec3d(asset.position))
                    
                    if any(asset.rotation):
                        # Use RotateXYZ for Euler angles in degrees
                        rotate_op = xformable.AddRotateXYZOp()
                        rotate_op.Set(Gf.Vec3f(asset.rotation))
                    
                    if any(v != 1.0 for v in asset.scale):
                        scale_op = xformable.AddScaleOp()
                        scale_op.Set(Gf.Vec3f(asset.scale))
                        
                    logger.info(f"✅ Applied transforms to reference container: pos{asset.position}, rot{asset.rotation}, scale{asset.scale}")
                        
                except Exception as transform_error:
                    logger.warning(f"⚠️ Could not apply transform to asset '{asset.name}': {transform_error}")
                    # Continue without transforms - asset placement still succeeds
            
            return {
                'success': True,
                'asset_name': asset.name,
                'asset_path': asset.asset_path,
                'prim_path': prim_path,
                'position': asset.position,
                'message': f"Placed asset '{asset.name}' via USD reference"
            }
            
        except Exception as e:
            logger.error(f"❌ Error in main thread asset placement: {e}")
            return {
                'success': False,
                'error': str(e),
                'asset_name': asset.name
            }

    def transform_asset_in_stage(self, prim_path: str, position: Optional[Tuple[float, float, float]] = None, 
                                rotation: Optional[Tuple[float, float, float]] = None, 
                                scale: Optional[Tuple[float, float, float]] = None) -> Dict[str, Any]:
        """
        Queue an existing asset for transformation on Isaac Sim's main thread.
        Returns immediately - actual USD transform happens asynchronously.
        
        Args:
            prim_path: Path to existing prim to transform
            position: Optional new position [x, y, z]
            rotation: Optional new rotation [rx, ry, rz] in degrees
            scale: Optional new scale [sx, sy, sz]
            
        Returns:
            Result dictionary with request ID for status tracking
        """
        return self._queue_manager.add_transform_request(
            prim_path, 
            list(position) if position else None,
            list(rotation) if rotation else None, 
            list(scale) if scale else None
        )

    def _transform_asset_on_main_thread(self, prim_path: str, position: Optional[Tuple[float, float, float]] = None, 
                                       rotation: Optional[Tuple[float, float, float]] = None, 
                                       scale: Optional[Tuple[float, float, float]] = None) -> Dict[str, Any]:
        """Transform existing asset safely on Isaac Sim's main thread."""
        try:
            # Get USD stage
            stage = self._usd_context.get_stage()
            if not stage:
                return {
                    'success': False,
                    'error': "No USD stage available. Please create or open a stage first."
                }
            
            # Check if prim exists
            prim = stage.GetPrimAtPath(prim_path)
            if not prim.IsValid():
                return {
                    'success': False,
                    'error': f"Prim not found at path: {prim_path}"
                }
            
            # Make prim transformable
            xformable = UsdGeom.Xformable(prim)
            if not xformable:
                return {
                    'success': False,
                    'error': f"Prim at '{prim_path}' is not transformable"
                }
            
            # Clear existing transforms and apply new ones
            xformable.ClearXformOpOrder()
            
            # Apply transforms in order: Translate, Rotate, Scale
            if position is not None:
                translate_op = xformable.AddTranslateOp()
                translate_op.Set(Gf.Vec3d(position))
            
            if rotation is not None:
                rotate_op = xformable.AddRotateXYZOp()
                rotate_op.Set(Gf.Vec3f(rotation))
            
            if scale is not None:
                scale_op = xformable.AddScaleOp()
                scale_op.Set(Gf.Vec3f(scale))
            
            return {
                'success': True,
                'prim_path': prim_path,
                'position': position,
                'rotation': rotation,
                'scale': scale,
                'message': f"Transformed asset at '{prim_path}'"
            }
            
        except Exception as e:
            logger.error(f"❌ Error in main thread asset transform: {e}")
            return {
                'success': False,
                'error': str(e),
                'prim_path': prim_path
            }

    def _remove_element_on_main_thread(self, element_path: str) -> Dict[str, Any]:
        """Remove a single element safely on main thread."""
        try:
            # Get USD stage
            stage = self._usd_context.get_stage()
            if not stage:
                return {
                    'success': False,
                    'error': "No USD stage available."
                }
            
            # Get the prim to remove
            prim = stage.GetPrimAtPath(element_path)
            if not prim.IsValid():
                return {
                    'success': False,
                    'error': f"Element at path '{element_path}' not found or invalid."
                }
            
            # Remove the prim
            stage.RemovePrim(element_path)
            
            return {
                'success': True,
                'element_path': element_path,
                'removed_count': 1,
                'message': f"Removed element at {element_path}"
            }
            
        except Exception as e:
            logger.error(f"❌ Error removing element {element_path}: {e}")
            return {
                'success': False,
                'error': str(e),
                'element_path': element_path
            }

    def _clear_path_on_main_thread(self, path: str) -> Dict[str, Any]:
        """Clear all elements under a USD path safely on main thread."""
        try:
            # Get USD stage
            stage = self._usd_context.get_stage()
            if not stage:
                return {
                    'success': False,
                    'error': "No USD stage available."
                }
            
            # Get the prim to clear
            prim = stage.GetPrimAtPath(path)
            if not prim.IsValid():
                return {
                    'success': False,
                    'error': f"Path '{path}' not found or invalid."
                }
            
            # Count children before removal
            children = list(prim.GetChildren())
            removed_count = len(children)
            
            # If it's a batch/group, remove all children
            if path != "/World":  # Safety check - don't remove the entire world
                stage.RemovePrim(path)
                removed_count += 1  # Include the parent prim itself
            else:
                # If clearing /World, remove all its children but keep /World itself
                for child in children:
                    stage.RemovePrim(child.GetPath())
            
            return {
                'success': True,
                'path': path,
                'removed_count': removed_count,
                'message': f"Cleared {removed_count} elements from {path}"
            }
            
        except Exception as e:
            logger.error(f"❌ Error clearing path {path}: {e}")
            return {
                'success': False,
                'error': str(e),
                'path': path
            }
    
    def _process_asset_request(self, request_type: str, request_data) -> Dict[str, Any]:
        """Process asset-related requests for the queue manager."""
        if request_type == 'place':
            return self._place_asset_on_main_thread(request_data)
        elif request_type == 'transform':
            return self._transform_asset_on_main_thread(
                request_data['prim_path'], 
                request_data.get('position'), 
                request_data.get('rotation'), 
                request_data.get('scale')
            )
        else:
            return {'success': False, 'error': f"Unknown asset request type: {request_type}"}
    
    def _process_removal_request(self, request_data: Dict) -> Dict[str, Any]:
        """Process removal requests for the queue manager."""
        request_type = request_data['type']
        if request_type == 'remove_element':
            return self._remove_element_on_main_thread(request_data['element_path'])
        elif request_type == 'clear_path':
            return self._clear_path_on_main_thread(request_data['path'])
        else:
            return {'success': False, 'error': f"Unknown removal type: {request_type}"}



    def create_batch_in_scene(self, batch_name: str, elements: List[Dict], 
                                  batch_transform: Optional[Dict[str, Tuple[float, float, float]]] = None) -> Dict[str, Any]:
        """
        Create a complete USD batch Xform with all its child elements.
        Queued approach using modular queue manager.
        
        Args:
            batch_name: Name of the batch Xform to create
            elements: List of element definitions to create as children
            batch_transform: Optional transform for the batch Xform
                           {'position': (x,y,z), 'rotation': (rx,ry,rz), 'scale': (sx,sy,sz)}
            
        Returns:
            Result dictionary with USD creation details
        """
        return self._queue_manager.add_batch_request(batch_name, elements, batch_transform)

    def _create_batch_on_main_thread(self, batch_name: str, elements: List[Dict], 
                                     batch_transform: Optional[Dict[str, Tuple[float, float, float]]] = None) -> Dict[str, Any]:
        """
        Create batch in scene - MUST run on main thread for USD operations.
        """
        try:
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
                if 'position' in batch_transform:
                    batch_position = tuple(batch_transform['position'])
                if 'rotation' in batch_transform:
                    batch_rotation = tuple(batch_transform['rotation'])
                if 'scale' in batch_transform:
                    batch_scale = tuple(batch_transform['scale'])
            
            # Get USD stage
            stage = self._usd_context.get_stage()
            if not stage:
                return {
                    'success': False,
                    'error': "No USD stage available. Please create or open a stage first."
                }
            
            # Sanitize batch name for USD path compatibility
            sanitized_batch_name = self._sanitize_usd_name(batch_name)
            if sanitized_batch_name != batch_name:
                logger.info(f"📝 Sanitized batch name '{batch_name}' → '{sanitized_batch_name}' for USD compatibility")
            
            # Create batch Xform
            batch_path = f"/World/{sanitized_batch_name}"
            batch_xform = UsdGeom.Xform.Define(stage, batch_path)
            
            # Set batch transform
            self._set_transform(batch_xform, batch_position, batch_rotation, batch_scale)
            
            # Create all elements in the batch
            created_elements = []
            for element in scene_elements:
                element_path = f"{batch_path}/{element.name}"
                
                # Create primitive based on type
                prim = self._create_primitive(stage, element_path, element.primitive_type)
                if prim:
                    # Set element transform
                    if hasattr(prim, 'GetXformOpOrderAttr'):  # It's an Xformable
                        self._set_transform(prim, element.position, element.rotation, element.scale)
                    
                    # Set color
                    self._set_color(prim, element.color)
                    
                    created_elements.append({
                        'name': element.name,
                        'type': element.primitive_type.value,
                        'path': element_path,
                        'position': element.position
                    })
                    
            
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
                'batch_transform': {
                    'position': batch_position,
                    'rotation': batch_rotation,
                    'scale': batch_scale
                }
            }
            
        except Exception as e:
            logger.error(f"❌ Error in main thread batch creation: {e}")
            return {
                'success': False,
                'error': str(e),
                'batch_name': batch_name
            }

    def _create_primitive(self, stage: Usd.Stage, path: str, prim_type: PrimitiveType) -> Optional[UsdGeom.Gprim]:
        """Create a USD primitive of the specified type."""
        try:
            if prim_type == PrimitiveType.CUBE:
                return UsdGeom.Cube.Define(stage, path)
            elif prim_type == PrimitiveType.SPHERE:
                return UsdGeom.Sphere.Define(stage, path)
            elif prim_type == PrimitiveType.CYLINDER:
                return UsdGeom.Cylinder.Define(stage, path)
            elif prim_type == PrimitiveType.PLANE:
                # Create a flattened cube for plane
                plane = UsdGeom.Cube.Define(stage, path)
                # Set very thin in Y direction to make it plane-like
                return plane
            elif prim_type == PrimitiveType.CONE:
                return UsdGeom.Cone.Define(stage, path)
            else:
                logger.error(f"Unknown primitive type: {prim_type}")
                return None
                
        except Exception as e:
            logger.error(f"Error creating {prim_type.value} at {path}: {e}")
            return None

    def _set_transform(self, xformable: UsdGeom.Xformable, 
                      position: Tuple[float, float, float],
                      rotation: Tuple[float, float, float],
                      scale: Tuple[float, float, float]):
        """Set transform on an Xformable prim."""
        try:
            # Clear existing transform ops
            xformable.ClearXformOpOrder()
            
            # Add transform operations in TRS order
            translate_op = xformable.AddTranslateOp()
            rotate_xyz_op = xformable.AddRotateXYZOp()
            scale_op = xformable.AddScaleOp()
            
            # Set values
            translate_op.Set(Gf.Vec3d(position[0], position[1], position[2]))
            rotate_xyz_op.Set(Gf.Vec3f(rotation[0], rotation[1], rotation[2]))
            scale_op.Set(Gf.Vec3f(scale[0], scale[1], scale[2]))
            
        except Exception as e:
            logger.error(f"Error setting transform: {e}")

    def _set_color(self, prim: UsdGeom.Gprim, color: Tuple[float, float, float]):
        """Set display color on a geometric primitive."""
        try:
            if hasattr(prim, 'GetDisplayColorAttr'):
                color_attr = prim.GetDisplayColorAttr()
                if not color_attr:
                    color_attr = prim.CreateDisplayColorAttr()
                color_attr.Set([Gf.Vec3f(color[0], color[1], color[2])])
                
        except Exception as e:
            logger.error(f"Error setting color: {e}")

    def _validate_asset_path(self, asset_path: str) -> bool:
        """
        Validate that an asset path is accessible for USD reference creation.
        Handles both local filesystem paths and omniverse:// URLs.
        
        Args:
            asset_path: Path to asset file (local or omniverse://)
            
        Returns:
            True if asset is accessible, False otherwise
        """
        try:
            if asset_path.startswith('omniverse://'):
                # For omniverse URLs, use USD layer validation
                try:
                    # Attempt to open the layer - this validates Nucleus connectivity and file existence
                    layer = Sdf.Layer.FindOrOpen(asset_path)
                    if layer:
                        logger.info(f"✅ Validated omniverse asset: {asset_path}")
                        return True
                    else:
                        logger.warning(f"⚠️ Cannot access omniverse asset: {asset_path}")
                        return False
                except Exception as e:
                    logger.error(f"❌ Omniverse asset validation failed for {asset_path}: {e}")
                    return False
            else:
                # For local paths, use filesystem check
                from pathlib import Path
                exists = Path(asset_path).exists()
                if exists:
                    logger.info(f"✅ Validated local asset: {asset_path}")
                else:
                    logger.warning(f"⚠️ Local asset not found: {asset_path}")
                return exists
                
        except Exception as e:
            logger.error(f"❌ Asset validation error for {asset_path}: {e}")
            return False

    def get_batch_info(self, batch_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Get information about current batches.
        
        Args:
            batch_name: Specific batch name, or None for all batches
            
        Returns:
            Batch information dictionary
        """
        try:
            if batch_name:
                if batch_name in self._current_batches:
                    batch = self._current_batches[batch_name]
                    return {
                        'success': True,
                        'batch_name': batch_name,
                        'element_count': len(batch.elements),
                        'elements': [
                            {
                                'name': elem.name,
                                'type': elem.primitive_type.value,
                                'position': elem.position,
                                'color': elem.color
                            }
                            for elem in batch.elements
                        ]
                    }
                else:
                    return {
                        'success': False,
                        'error': f"Batch '{batch_name}' not found",
                        'available_batches': list(self._current_batches.keys())
                    }
            else:
                # Return all batches
                return {
                    'success': True,
                    'batch_count': len(self._current_batches),
                    'batches': {
                        name: {
                            'element_count': len(batch.elements),
                            'elements': [elem.name for elem in batch.elements]
                        }
                        for name, batch in self._current_batches.items()
                    },
                    'statistics': self._stats
                }
                
        except Exception as e:
            logger.error(f"Error getting batch info: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    def clear_batch(self, batch_name: str) -> Dict[str, Any]:
        """Clear a specific batch without creating it in the scene."""
        try:
            if batch_name in self._current_batches:
                del self._current_batches[batch_name]
                return {
                    'success': True,
                    'message': f"Cleared batch '{batch_name}'"
                }
            else:
                return {
                    'success': False,
                    'error': f"Batch '{batch_name}' not found",
                    'available_batches': list(self._current_batches.keys())
                }
                
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }

    def get_scene_contents(self, path: str = "/World") -> Dict[str, Any]:
        """
        Get contents of the USD stage at a specific path.
        
        Args:
            path: USD path to inspect (default: "/World")
            
        Returns:
            Dictionary with scene contents and structure
        """
        try:
            # Get USD stage
            stage = self._usd_context.get_stage()
            if not stage:
                return {
                    'success': False,
                    'error': "No USD stage available."
                }
            
            # Get the root prim
            root_prim = stage.GetPrimAtPath(path)
            if not root_prim.IsValid():
                return {
                    'success': False,
                    'error': f"Path '{path}' not found or invalid."
                }
            
            # Debug: Check if root prim has children
            children = list(root_prim.GetChildren())
            logger.info(f"🔍 Debug: Root prim '{path}' has {len(children)} children")
            for child in children:
                logger.info(f"  - Child: {child.GetPath()} (Type: {child.GetTypeName()})")
            
            # Recursively gather scene structure
            scene_data = self._inspect_prim_recursive(root_prim, max_depth=5)
            logger.info(f"🔍 Debug: Scene data structure: {scene_data}")
            
            return {
                'success': True,
                'path': path,
                'contents': scene_data,
                'total_prims': self._count_prims_recursive(root_prim),
                'timestamp': time.time()
            }
            
        except Exception as e:
            logger.error(f"❌ Error getting scene contents: {e}")
            return {
                'success': False,
                'error': str(e),
                'path': path
            }

    def _inspect_prim_recursive(self, prim, current_depth: int = 0, max_depth: int = 5) -> Dict[str, Any]:
        """Recursively inspect a USD prim and its children."""
        if current_depth > max_depth:
            return {'name': prim.GetName(), 'type': 'max_depth_reached', 'children_count': len(list(prim.GetChildren()))}
        
        prim_data = {
            'name': prim.GetName(),
            'path': str(prim.GetPath()),
            'type': prim.GetTypeName(),
            'is_active': prim.IsActive(),
            'children': []
        }
        
        # Add transform info if available
        try:
            if prim.HasAPI('UsdGeom.Xformable'):
                from pxr import UsdGeom
                xformable = UsdGeom.Xformable(prim)
                # Get local transform
                transform_matrix = xformable.GetLocalTransformation()
                if transform_matrix:
                    # Extract translation from matrix
                    translation = transform_matrix.ExtractTranslation()
                    prim_data['position'] = [float(translation[0]), float(translation[1]), float(translation[2])]
        except Exception:
            pass  # Skip transform info if not available
        
        # Add geometry info if it's a geometric primitive
        try:
            if prim.GetTypeName() in ['Cube', 'Sphere', 'Cylinder', 'Cone', 'Plane']:
                from pxr import UsdGeom
                gprim = UsdGeom.Gprim(prim)
                # Get display color if available
                color_attr = gprim.GetDisplayColorAttr()
                if color_attr:
                    colors = color_attr.Get()
                    if colors:
                        color = colors[0]
                        prim_data['color'] = [float(color[0]), float(color[1]), float(color[2])]
        except Exception:
            pass  # Skip color info if not available
        
        # Recursively add children
        children = list(prim.GetChildren())
        for child in children:
            prim_data['children'].append(self._inspect_prim_recursive(child, current_depth + 1, max_depth))
        
        return prim_data

    def _count_prims_recursive(self, prim) -> int:
        """Count total prims recursively."""
        count = 1  # Count this prim
        for child in prim.GetChildren():
            count += self._count_prims_recursive(child)
        return count

    def list_elements_at_path(self, path: str = "/World") -> Dict[str, Any]:
        """
        Get a flat list of all elements at a specific path (non-recursive).
        
        Args:
            path: USD path to list (default: "/World")
            
        Returns:
            Dictionary with list of direct children
        """
        try:
            # Get USD stage
            stage = self._usd_context.get_stage()
            if not stage:
                return {
                    'success': False,
                    'error': "No USD stage available."
                }
            
            # Get the root prim
            root_prim = stage.GetPrimAtPath(path)
            if not root_prim.IsValid():
                return {
                    'success': False,
                    'error': f"Path '{path}' not found or invalid."
                }
            
            # Get direct children only
            elements = []
            for child in root_prim.GetChildren():
                element_info = {
                    'name': child.GetName(),
                    'path': str(child.GetPath()),
                    'type': child.GetTypeName(),
                    'is_active': child.IsActive(),
                    'has_children': len(list(child.GetChildren())) > 0
                }
                
                # Add position if available
                try:
                    if child.HasAPI('UsdGeom.Xformable'):
                        from pxr import UsdGeom
                        xformable = UsdGeom.Xformable(child)
                        transform_matrix = xformable.GetLocalTransformation()
                        if transform_matrix:
                            translation = transform_matrix.ExtractTranslation()
                            element_info['position'] = [float(translation[0]), float(translation[1]), float(translation[2])]
                except Exception:
                    pass
                
                elements.append(element_info)
            
            return {
                'success': True,
                'path': path,
                'elements': elements,
                'count': len(elements),
                'timestamp': time.time()
            }
            
        except Exception as e:
            logger.error(f"❌ Error listing elements: {e}")
            return {
                'success': False,
                'error': str(e),
                'path': path
            }

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