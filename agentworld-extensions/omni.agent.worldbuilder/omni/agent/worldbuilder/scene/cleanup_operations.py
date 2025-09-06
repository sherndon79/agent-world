"""
USD cleanup operations for WorldBuilder scene operations.

Provides element removal, path clearing, and scene cleanup operations with proper USD handling.
"""

import logging
from typing import Dict, Any, List
from pxr import Usd

logger = logging.getLogger(__name__)


class CleanupOperations:
    """Manager for USD scene cleanup, removal, and clearing operations."""
    
    def __init__(self, usd_context):
        """Initialize cleanup operations with USD context."""
        self._usd_context = usd_context
    
    def remove_element(self, element_path: str) -> Dict[str, Any]:
        """
        Remove a single element from the USD stage safely on main thread.
        
        Args:
            element_path: USD path to the element to remove
            
        Returns:
            Result dictionary with removal details
        """
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
            
            logger.info(f"✅ Removed element at {element_path}")
            
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
    
    def clear_path(self, path: str) -> Dict[str, Any]:
        """
        Clear all elements under a USD path safely on main thread.
        
        Args:
            path: USD path to clear (e.g., "/World/my_batch" or "/World")
            
        Returns:
            Result dictionary with clearing details
        """
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
            
            # Count children for statistics
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
            
            logger.info(f"✅ Cleared {removed_count} elements from {path}")
            
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
    
    def clear_by_type(self, prim_type: str, parent_path: str = "/World") -> Dict[str, Any]:
        """
        Clear all elements of a specific type under a parent path.
        
        Args:
            prim_type: USD prim type to remove (e.g., "Cube", "Sphere")
            parent_path: Parent path to search within
            
        Returns:
            Result dictionary with clearing details
        """
        try:
            stage = self._usd_context.get_stage()
            if not stage:
                return {
                    'success': False,
                    'error': "No USD stage available."
                }
            
            parent_prim = stage.GetPrimAtPath(parent_path)
            if not parent_prim.IsValid():
                return {
                    'success': False,
                    'error': f"Parent path '{parent_path}' not found or invalid."
                }
            
            # Find and remove all prims of the specified type
            removed_paths = []
            
            def _traverse_and_remove(prim):
                # Check children first (depth-first to avoid iterator invalidation)
                children_to_check = list(prim.GetChildren())
                for child in children_to_check:
                    _traverse_and_remove(child)
                
                # Check current prim
                if prim.GetTypeName() == prim_type and prim != parent_prim:
                    removed_paths.append(str(prim.GetPath()))
                    stage.RemovePrim(prim.GetPath())
            
            _traverse_and_remove(parent_prim)
            
            logger.info(f"✅ Removed {len(removed_paths)} elements of type '{prim_type}' from {parent_path}")
            
            return {
                'success': True,
                'prim_type': prim_type,
                'parent_path': parent_path,
                'removed_count': len(removed_paths),
                'removed_paths': removed_paths,
                'message': f"Removed {len(removed_paths)} elements of type '{prim_type}'"
            }
            
        except Exception as e:
            logger.error(f"❌ Error clearing elements of type {prim_type}: {e}")
            return {
                'success': False,
                'error': str(e),
                'prim_type': prim_type,
                'parent_path': parent_path
            }
    
    def clear_by_pattern(self, name_pattern: str, parent_path: str = "/World") -> Dict[str, Any]:
        """
        Clear all elements whose names match a pattern.
        
        Args:
            name_pattern: Name pattern to match (simple string matching)
            parent_path: Parent path to search within
            
        Returns:
            Result dictionary with clearing details
        """
        try:
            stage = self._usd_context.get_stage()
            if not stage:
                return {
                    'success': False,
                    'error': "No USD stage available."
                }
            
            parent_prim = stage.GetPrimAtPath(parent_path)
            if not parent_prim.IsValid():
                return {
                    'success': False,
                    'error': f"Parent path '{parent_path}' not found or invalid."
                }
            
            # Find and remove all prims matching the pattern
            removed_paths = []
            
            def _traverse_and_remove(prim):
                # Check children first (depth-first to avoid iterator invalidation)
                children_to_check = list(prim.GetChildren())
                for child in children_to_check:
                    _traverse_and_remove(child)
                
                # Check current prim name
                prim_name = prim.GetName()
                if name_pattern in prim_name and prim != parent_prim:
                    removed_paths.append(str(prim.GetPath()))
                    stage.RemovePrim(prim.GetPath())
            
            _traverse_and_remove(parent_prim)
            
            logger.info(f"✅ Removed {len(removed_paths)} elements matching pattern '{name_pattern}' from {parent_path}")
            
            return {
                'success': True,
                'name_pattern': name_pattern,
                'parent_path': parent_path,
                'removed_count': len(removed_paths),
                'removed_paths': removed_paths,
                'message': f"Removed {len(removed_paths)} elements matching pattern '{name_pattern}'"
            }
            
        except Exception as e:
            logger.error(f"❌ Error clearing elements matching pattern {name_pattern}: {e}")
            return {
                'success': False,
                'error': str(e),
                'name_pattern': name_pattern,
                'parent_path': parent_path
            }
    
    def get_cleanup_preview(self, path: str) -> Dict[str, Any]:
        """
        Preview what would be removed by a cleanup operation without actually removing.
        
        Args:
            path: USD path to preview cleanup for
            
        Returns:
            Preview information dictionary
        """
        try:
            stage = self._usd_context.get_stage()
            if not stage:
                return {
                    'success': False,
                    'error': "No USD stage available."
                }
            
            prim = stage.GetPrimAtPath(path)
            if not prim.IsValid():
                return {
                    'success': False,
                    'error': f"Path '{path}' not found or invalid."
                }
            
            # Gather information about what would be removed
            preview_info = {
                'success': True,
                'path': path,
                'prim_type': prim.GetTypeName(),
                'children': []
            }
            
            # Count and categorize children
            child_types = {}
            for child in prim.GetChildren():
                child_type = child.GetTypeName()
                child_types[child_type] = child_types.get(child_type, 0) + 1
                
                preview_info['children'].append({
                    'name': child.GetName(),
                    'path': str(child.GetPath()),
                    'type': child_type,
                    'has_children': bool(child.GetChildren())
                })
            
            preview_info['child_type_summary'] = child_types
            preview_info['total_children'] = len(preview_info['children'])
            
            # Estimate total removal count
            if path == "/World":
                preview_info['estimated_removal_count'] = len(preview_info['children'])
            else:
                preview_info['estimated_removal_count'] = 1 + len(preview_info['children'])
            
            return preview_info
            
        except Exception as e:
            logger.error(f"❌ Error getting cleanup preview for {path}: {e}")
            return {
                'success': False,
                'error': str(e),
                'path': path
            }
    
    def validate_removal_path(self, path: str) -> Dict[str, Any]:
        """
        Validate that a path is safe for removal operations.
        
        Args:
            path: USD path to validate
            
        Returns:
            Validation result dictionary
        """
        warnings = []
        errors = []
        
        # Check for critical paths that should not be removed
        critical_paths = ["/", ""]
        if path in critical_paths:
            errors.append("Cannot remove root paths")
        
        # Check for system paths
        system_paths = ["/World/Render", "/World/Environment", "/World/PhysicsScene"]
        if path in system_paths:
            warnings.append(f"Removing system path '{path}' may affect scene functionality")
        
        # Check path format
        if not path.startswith('/'):
            errors.append("Path must start with '/'")
        
        # Try to access the path
        try:
            stage = self._usd_context.get_stage()
            if stage:
                prim = stage.GetPrimAtPath(path)
                if not prim.IsValid():
                    warnings.append(f"Path '{path}' does not exist in current stage")
        except Exception as e:
            errors.append(f"Error accessing path: {str(e)}")
        
        return {
            'valid': len(errors) == 0,
            'errors': errors,
            'warnings': warnings,
            'safe_to_remove': len(errors) == 0 and len(warnings) == 0
        }