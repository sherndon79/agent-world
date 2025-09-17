"""
Batch management for WorldBuilder scene operations.

Provides hierarchical batch creation, management, and tracking operations with proper USD handling.
"""

import logging
import time
from typing import Dict, Any, List, Optional, Tuple
from pxr import Usd, UsdGeom, Gf

from .scene_types import SceneElement, SceneBatch, PrimitiveType

logger = logging.getLogger(__name__)


class BatchManager:
    """Manager for USD batch operations, hierarchy management, and batch lifecycle."""
    
    def __init__(self, usd_context, element_factory):
        """Initialize batch manager with USD context and element factory."""
        self._usd_context = usd_context
        self._element_factory = element_factory
        self._current_batches: Dict[str, SceneBatch] = {}
    
    def create_batch(self, batch_name: str, elements: List[Dict], 
                    batch_transform: Optional[Dict[str, Tuple[float, float, float]]] = None) -> Dict[str, Any]:
        """
        Create batch in scene - MUST run on main thread for USD operations.
        Uses modular element factory for individual element creation.
        
        Args:
            batch_name: Name of the batch to create
            elements: List of element definitions
            batch_transform: Optional transform dict with position, rotation, scale
            
        Returns:
            Result dictionary with batch creation details
        """
        try:
            # Get USD stage
            stage = self._usd_context.get_stage()
            if not stage:
                return {
                    'success': False,
                    'error': "No USD stage available. Please create or open a stage first."
                }

            # Validate batch request using centralized validation
            validation_result = self.validate_batch_request(batch_name, elements)
            if not validation_result['valid']:
                return {
                    'success': False,
                    'error': '; '.join(validation_result['errors'])
                }

            batch_path = f"/World/{self._sanitize_usd_name(batch_name)}"
            
            # Parse elements from request data
            scene_elements = []
            for elem_data in elements:
                try:
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
                except Exception as e:
                    logger.warning(f"⚠️ Invalid element data in batch '{batch_name}': {e}")
                    continue
            
            if not scene_elements:
                return {
                    'success': False,
                    'error': f"No valid elements provided for batch '{batch_name}'"
                }
            
            # Set default batch transform
            batch_position = (0.0, 0.0, 0.0)
            batch_rotation = (0.0, 0.0, 0.0) 
            batch_scale = (1.0, 1.0, 1.0)
            
            # Apply batch transform if provided
            if batch_transform:
                batch_position = batch_transform.get('position', batch_position)
                batch_rotation = batch_transform.get('rotation', batch_rotation)
                batch_scale = batch_transform.get('scale', batch_scale)
            
            # Create batch Xform parent with improved error handling
            try:
                batch_xform = UsdGeom.Xform.Define(stage, batch_path)
                if not batch_xform or not batch_xform.GetPrim().IsValid():
                    return {
                        'success': False,
                        'error': f"Invalid batch name '{batch_name}' - contains unsupported characters"
                    }
            except Exception as e:
                return {
                    'success': False,
                    'error': f"USD stage error creating batch '{batch_name}': {str(e)}"
                }
            
            # Add batch identification metadata to USD
            self._add_batch_metadata(batch_xform, batch_name, scene_elements)
            
            # Apply batch transform
            self._set_batch_transform(batch_xform, batch_position, batch_rotation, batch_scale)
            
            # Create all elements in the batch using element factory
            created_elements = []
            failed_elements = []
            
            for element in scene_elements:
                # Temporarily adjust element name to include batch path
                original_name = element.name
                element.name = f"{self._sanitize_usd_name(batch_name)}/{original_name}"
                
                try:
                    # Use element factory to create the element
                    result = self._element_factory.create_element(element)
                    
                    if result['success']:
                        created_elements.append({
                            'name': original_name,
                            'type': element.primitive_type.value,
                            'path': result['usd_path'],
                            'position': element.position
                        })
                        logger.debug(f"✅ Created element '{original_name}' in batch '{batch_name}'")
                    else:
                        failed_elements.append({
                            'name': original_name,
                            'error': result.get('error', 'Unknown error')
                        })
                        logger.warning(f"⚠️ Failed to create element '{original_name}' in batch: {result.get('error')}")
                
                except Exception as e:
                    failed_elements.append({
                        'name': original_name,
                        'error': str(e)
                    })
                    logger.error(f"❌ Exception creating element '{original_name}' in batch: {e}")
                
                finally:
                    # Restore original name
                    element.name = original_name
            
            # USD stage metadata is now the single source of truth
            # No memory tracking needed - all batch info stored as USD metadata
            
            logger.info(f"🎯 Created batch '{batch_name}' with {len(created_elements)} elements at {batch_path}")
            
            result = {
                'success': True,
                'batch_name': batch_name,
                'batch_path': batch_path,
                'elements_created': len(created_elements),
                'elements_failed': len(failed_elements),
                'elements': created_elements,
                'message': f"Created batch '{batch_name}' with {len(created_elements)} elements"
            }
            
            if failed_elements:
                result['failed_elements'] = failed_elements
                result['message'] += f" ({len(failed_elements)} failed)"
            
            return result
            
        except Exception as e:
            logger.error(f"❌ Error in batch creation: {e}")
            return {
                'success': False,
                'error': str(e),
                'batch_name': batch_name
            }
    
    def get_batch_info(self, batch_name: str) -> Dict[str, Any]:
        """
        Get detailed information about a specific batch.
        
        Args:
            batch_name: Name of the batch to inspect
            
        Returns:
            Batch information dictionary
        """
        try:
            # First try stage discovery for persistent batches
            discovered_batches = self.discover_batches_from_stage()
            if batch_name in discovered_batches:
                batch_info = discovered_batches[batch_name]
                return {
                    'success': True,
                    'batch_name': batch_info['name'],
                    'element_count': batch_info['element_count'],
                    'batch_path': batch_info['path'],
                    'created_at': batch_info['created_at'],
                    'element_names': batch_info['element_names'],
                    'child_elements': batch_info['child_elements'],
                    'metadata': batch_info['metadata'],
                    'source': 'stage_discovery'
                }
            
            # Fallback to in-memory tracking for compatibility
            if batch_name not in self._current_batches:
                return {
                    'success': False,
                    'error': f"Batch '{batch_name}' not found in stage or memory tracking"
                }
            
            batch = self._current_batches[batch_name]
            return {
                'success': True,
                'batch_name': batch.batch_name,
                'element_count': len(batch.elements),
                'batch_position': batch.batch_position,
                'batch_rotation': batch.batch_rotation,
                'batch_scale': batch.batch_scale,
                'elements': [
                    {
                        'name': element.name,
                        'type': element.primitive_type.value,
                        'position': element.position,
                        'rotation': element.rotation,
                        'scale': element.scale,
                        'color': element.color
                    }
                    for element in batch.elements
                ],
                'metadata': batch.metadata,
                'source': 'memory_tracking'
            }
            
        except Exception as e:
            logger.error(f"❌ Error getting batch info for '{batch_name}': {e}")
            return {
                'success': False,
                'error': str(e),
                'batch_name': batch_name
            }
    
    def list_batches(self) -> Dict[str, Any]:
        """
        List all current batches with summary information using stage discovery.
        
        Returns:
            Dictionary with batch listing
        """
        try:
            # Use stage discovery as primary source
            discovered_batches = self.discover_batches_from_stage()
            batch_summaries = []
            
            for batch_name, batch_info in discovered_batches.items():
                summary = {
                    'batch_name': batch_name,
                    'element_count': batch_info['element_count'],
                    'batch_path': batch_info['path'],
                    'created_at': batch_info['created_at'],
                    'element_names': batch_info['element_names'],
                    'source': 'stage_discovery'
                }
                batch_summaries.append(summary)
            
            # Add any memory-tracked batches that weren't found in stage discovery
            for batch_name, batch in self._current_batches.items():
                if batch_name not in discovered_batches:
                    summary = {
                        'batch_name': batch_name,
                        'element_count': len(batch.elements),
                        'batch_path': batch.metadata.get('path', f"/World/{batch_name}"),
                        'created_at': batch.metadata.get('created_at'),
                        'created_elements': batch.metadata.get('created_elements', 0),
                        'failed_elements': batch.metadata.get('failed_elements', 0),
                        'source': 'memory_tracking'
                    }
                    batch_summaries.append(summary)
            
            return {
                'success': True,
                'batch_count': len(batch_summaries),
                'stage_discovered': len(discovered_batches),
                'memory_tracked': len(self._current_batches),
                'batches': batch_summaries
            }
            
        except Exception as e:
            logger.error(f"❌ Error listing batches: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    # remove_batch method removed - batch removal now handled by USD stage operations  
    # Use clear_path("/World/batch_name") which automatically reflects in stage discovery
    
    def clear_all_batches(self) -> Dict[str, Any]:
        """
        Clear all batch tracking (does not affect USD scene).
        
        Returns:
            Result dictionary
        """
        try:
            batch_count = len(self._current_batches)
            self._current_batches.clear()
            
            logger.info(f"🧹 Cleared all {batch_count} batches from tracking")
            
            return {
                'success': True,
                'cleared_count': batch_count,
                'message': f"Cleared {batch_count} batches from tracking"
            }
            
        except Exception as e:
            logger.error(f"❌ Error clearing batches: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_batch_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about current batches.
        
        Returns:
            Statistics dictionary
        """
        try:
            if not self._current_batches:
                return {
                    'total_batches': 0,
                    'total_elements': 0,
                    'average_elements_per_batch': 0.0,
                    'batch_names': []
                }
            
            total_elements = sum(len(batch.elements) for batch in self._current_batches.values())
            
            return {
                'total_batches': len(self._current_batches),
                'total_elements': total_elements,
                'average_elements_per_batch': total_elements / len(self._current_batches),
                'batch_names': list(self._current_batches.keys())
            }
            
        except Exception as e:
            logger.error(f"❌ Error getting batch statistics: {e}")
            return {
                'total_batches': 0,
                'total_elements': 0,
                'error': str(e)
            }
    
    def validate_batch_request(self, batch_name: str, elements: List[Dict]) -> Dict[str, Any]:
        """
        Validate batch creation request before processing.
        
        Args:
            batch_name: Name of the batch to validate
            elements: List of element definitions to validate
            
        Returns:
            Validation result dictionary
        """
        errors = []
        warnings = []
        
        # Check batch name
        if not batch_name or not batch_name.strip():
            errors.append("Batch name cannot be empty")

        # Check if batch path already exists in USD stage
        stage = self._usd_context.get_stage()
        if stage:
            batch_path = f"/World/{self._sanitize_usd_name(batch_name)}"
            existing_prim = stage.GetPrimAtPath(batch_path)
            if existing_prim and existing_prim.IsValid():
                errors.append(f"Batch '{batch_name}' already exists at path '{batch_path}'")
        
        # Check elements
        if not elements:
            errors.append("No elements provided for batch")
        elif len(elements) > 100:  # Reasonable limit
            warnings.append(f"Large batch with {len(elements)} elements may affect performance")
        
        # Validate individual elements
        valid_elements = 0
        for i, elem_data in enumerate(elements):
            if not isinstance(elem_data, dict):
                errors.append(f"Element {i} is not a valid dictionary")
                continue
            
            # Check required fields
            element_type = elem_data.get('element_type')
            if not element_type:
                errors.append(f"Element {i} missing element_type")
                continue
            
            # Validate element type
            try:
                PrimitiveType(element_type)
                valid_elements += 1
            except ValueError:
                errors.append(f"Element {i} has invalid element_type: {element_type}")
        
        return {
            'valid': len(errors) == 0,
            'errors': errors,
            'warnings': warnings,
            'valid_elements': valid_elements,
            'total_elements': len(elements)
        }
    
    def _sanitize_usd_name(self, name: str) -> str:
        """Sanitize name for USD path compatibility."""
        import re
        sanitized = re.sub(r'[^a-zA-Z0-9_\-]', '_', name)
        if sanitized and sanitized[0].isdigit():
            sanitized = f"_{sanitized}"
        return sanitized
    
    def _add_batch_metadata(self, batch_xform: UsdGeom.Xform, batch_name: str, scene_elements: List[SceneElement]):
        """Add batch identification metadata to USD Xform."""
        try:
            from pxr import Sdf
            prim = batch_xform.GetPrim()
            
            # Add WorldBuilder batch identification attributes using correct USD types
            prim.CreateAttribute("worldbuilder:is_batch", Sdf.ValueTypeNames.Bool).Set(True)
            prim.CreateAttribute("worldbuilder:batch_name", Sdf.ValueTypeNames.String).Set(batch_name)
            prim.CreateAttribute("worldbuilder:batch_created_at", Sdf.ValueTypeNames.Double).Set(time.time())
            prim.CreateAttribute("worldbuilder:batch_element_count", Sdf.ValueTypeNames.Int).Set(len(scene_elements))
            
            # Store element names for quick reference
            element_names = [element.name for element in scene_elements]
            prim.CreateAttribute("worldbuilder:batch_element_names", Sdf.ValueTypeNames.StringArray).Set(element_names)
            
            logger.info(f"✅ Added batch metadata to {prim.GetPath()}")
            
        except Exception as e:
            logger.error(f"❌ Error adding batch metadata: {e}")
    
    def discover_batches_from_stage(self) -> Dict[str, Dict[str, Any]]:
        """Discover all batches by examining USD stage hierarchy."""
        try:
            stage = self._usd_context.get_stage()
            if not stage:
                return {}
            
            batches = {}
            world_prim = stage.GetPrimAtPath("/World")
            if not world_prim:
                return {}
            
            # Traverse all children of /World looking for batch Xforms
            for child in world_prim.GetChildren():
                if child.GetTypeName() == "Xform":
                    # Check if this Xform has batch metadata
                    is_batch_attr = child.GetAttribute("worldbuilder:is_batch")
                    if is_batch_attr and is_batch_attr.Get():
                        batch_info = self._extract_batch_info_from_prim(child)
                        if batch_info:
                            batches[batch_info['name']] = batch_info
            
            logger.debug(f"🔍 Discovered {len(batches)} batches from USD stage")
            return batches
            
        except Exception as e:
            logger.error(f"❌ Error discovering batches from stage: {e}")
            return {}
    
    def _extract_batch_info_from_prim(self, batch_prim: Usd.Prim) -> Optional[Dict[str, Any]]:
        """Extract batch information from USD prim with metadata."""
        try:
            # Get batch metadata attributes
            batch_name = batch_prim.GetAttribute("worldbuilder:batch_name").Get()
            created_at = batch_prim.GetAttribute("worldbuilder:batch_created_at").Get()
            element_count = batch_prim.GetAttribute("worldbuilder:batch_element_count").Get()
            element_names_attr = batch_prim.GetAttribute("worldbuilder:batch_element_names").Get()
            
            # Convert USD StringArray to Python list for JSON serialization
            element_names = list(element_names_attr) if element_names_attr else []
            
            # Get child elements from USD hierarchy
            child_elements = []
            for child in batch_prim.GetChildren():
                if child.IsValid() and child.GetTypeName() in ["Cube", "Sphere", "Cylinder", "Cone"]:
                    child_elements.append({
                        'name': child.GetName(),
                        'type': child.GetTypeName(),
                        'path': str(child.GetPath())
                    })
            
            return {
                'name': batch_name or batch_prim.GetName(),
                'path': str(batch_prim.GetPath()),
                'created_at': created_at or time.time(),
                'element_count': element_count or len(child_elements),
                'element_names': element_names or [e['name'] for e in child_elements],
                'child_elements': child_elements,
                'metadata': {
                    'source': 'stage_discovery',
                    'discovered_at': time.time()
                }
            }
            
        except Exception as e:
            logger.error(f"❌ Error extracting batch info from {batch_prim.GetPath()}: {e}")
            return None
    
    def _set_batch_transform(self, xformable: UsdGeom.Xformable, 
                            position: Tuple[float, float, float],
                            rotation: Tuple[float, float, float],
                            scale: Tuple[float, float, float]):
        """Apply transform operations to a batch USD Xformable prim."""
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
            logger.error(f"❌ Error setting batch transform: {e}")
    
    # Properties for external access
    @property
    def current_batches(self) -> Dict[str, SceneBatch]:
        """Get current batches (read-only access)."""
        return self._current_batches.copy()
    
    @property
    def batch_count(self) -> int:
        """Get current batch count."""
        return len(self._current_batches)
    
    @property
    def total_elements_in_batches(self) -> int:
        """Get total element count across all batches."""
        return sum(len(batch.elements) for batch in self._current_batches.values())