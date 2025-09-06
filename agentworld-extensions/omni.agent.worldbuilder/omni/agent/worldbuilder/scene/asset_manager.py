"""
USD asset management for WorldBuilder scene operations.

Provides asset placement, transformation, and validation operations with proper USD reference handling.
"""

import logging
import os
from typing import Dict, Any, Optional, Tuple, List
from pxr import Usd, UsdGeom, Gf

from .scene_types import AssetPlacement

logger = logging.getLogger(__name__)


class AssetManager:
    """Manager for USD asset placement, transformation, and lifecycle operations."""
    
    def __init__(self, usd_context):
        """Initialize asset manager with USD context."""
        self._usd_context = usd_context
    
    def place_asset(self, asset: AssetPlacement) -> Dict[str, Any]:
        """
        Place asset via USD reference safely on Isaac Sim's main thread.
        
        Args:
            asset: AssetPlacement with all placement parameters
            
        Returns:
            Result dictionary with placement details
        """
        try:
            # Get USD stage
            stage = self._usd_context.get_stage()
            if not stage:
                return {
                    'success': False,
                    'error': "No USD stage available. Please create or open a stage first."
                }
            
            # Validate asset path exists
            if not self.validate_asset_path(asset.asset_path):
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
                        translate_op.Set(Gf.Vec3d(*asset.position))
                    
                    if any(asset.rotation):
                        rotate_op = xformable.AddRotateXYZOp()
                        rotate_op.Set(Gf.Vec3f(*asset.rotation))  # USD expects degrees
                    
                    if any(s != 1.0 for s in asset.scale):
                        scale_op = xformable.AddScaleOp()
                        scale_op.Set(Gf.Vec3f(*asset.scale))
                        
                except Exception as transform_error:
                    logger.warning(f"⚠️ Failed to apply transforms to asset reference: {transform_error}")
                    # Continue with asset placement even if transforms fail
            
            logger.info(f"✅ Placed asset '{asset.name}' via USD reference at {prim_path}")
            
            return {
                'success': True,
                'asset_name': asset.name,
                'asset_path': asset.asset_path,
                'prim_path': prim_path,
                'position': asset.position,
                'rotation': asset.rotation,
                'scale': asset.scale,
                'message': f"Placed asset '{asset.name}' in USD scene via reference"
            }
            
        except Exception as e:
            logger.error(f"❌ Error placing asset {asset.name}: {e}")
            return {
                'success': False,
                'error': str(e),
                'asset_name': asset.name
            }
    
    def transform_asset(self, prim_path: str, position: Optional[Tuple[float, float, float]] = None, 
                       rotation: Optional[Tuple[float, float, float]] = None, 
                       scale: Optional[Tuple[float, float, float]] = None) -> Dict[str, Any]:
        """
        Transform existing asset safely on Isaac Sim's main thread.
        
        Args:
            prim_path: Path to existing prim to transform
            position: Optional new position [x, y, z]
            rotation: Optional new rotation [rx, ry, rz] in degrees
            scale: Optional new scale [sx, sy, sz]
            
        Returns:
            Result dictionary with transformation details
        """
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
                    'error': f"Prim at path '{prim_path}' not found or invalid."
                }
            
            # Make the prim transformable
            xformable = UsdGeom.Xformable(prim)
            if not xformable:
                return {
                    'success': False,
                    'error': f"Prim at '{prim_path}' is not transformable."
                }
            
            # Clear existing transform operations to avoid conflicts
            xformable.ClearXformOpOrder()
            
            # Apply new transforms in TRS order
            transforms_applied = []
            
            if position is not None:
                translate_op = xformable.AddTranslateOp()
                translate_op.Set(Gf.Vec3d(*position))
                transforms_applied.append(f"position={position}")
            
            if rotation is not None:
                rotate_op = xformable.AddRotateXYZOp()
                rotate_op.Set(Gf.Vec3f(*rotation))  # USD expects degrees for Euler
                transforms_applied.append(f"rotation={rotation}")
            
            if scale is not None:
                scale_op = xformable.AddScaleOp()
                scale_op.Set(Gf.Vec3f(*scale))
                transforms_applied.append(f"scale={scale}")
            
            if not transforms_applied:
                return {
                    'success': False,
                    'error': "No transform parameters provided"
                }
            
            logger.info(f"✅ Transformed asset at '{prim_path}': {', '.join(transforms_applied)}")
            
            return {
                'success': True,
                'prim_path': prim_path,
                'position': position,
                'rotation': rotation,
                'scale': scale,
                'transforms_applied': transforms_applied,
                'message': f"Transformed asset at '{prim_path}'"
            }
            
        except Exception as e:
            logger.error(f"❌ Error transforming asset at {prim_path}: {e}")
            return {
                'success': False,
                'error': str(e),
                'prim_path': prim_path
            }
    
    def validate_asset_path(self, asset_path: str) -> bool:
        """Validate that an asset file exists and is readable."""
        try:
            if not asset_path:
                return False
            
            # Handle both absolute and relative paths
            if not os.path.isabs(asset_path):
                # Try common asset directories
                search_paths = [
                    os.getcwd(),
                    "/World/assets",
                    "../assets",
                ]
                
                for search_path in search_paths:
                    full_path = os.path.join(search_path, asset_path)
                    if os.path.exists(full_path) and os.path.isfile(full_path):
                        return True
                return False
            
            return os.path.exists(asset_path) and os.path.isfile(asset_path)
            
        except Exception as e:
            logger.error(f"❌ Error validating asset path {asset_path}: {e}")
            return False
    
    def get_asset_info(self, prim_path: str) -> Dict[str, Any]:
        """
        Get detailed information about an asset in the scene.
        
        Args:
            prim_path: USD path to the asset
            
        Returns:
            Asset information dictionary
        """
        try:
            stage = self._usd_context.get_stage()
            if not stage:
                return {'success': False, 'error': "No USD stage available"}
            
            prim = stage.GetPrimAtPath(prim_path)
            if not prim.IsValid():
                return {'success': False, 'error': f"Prim at '{prim_path}' not found"}
            
            info = {
                'success': True,
                'prim_path': prim_path,
                'prim_type': prim.GetTypeName(),
                'is_active': prim.IsActive(),
                'has_children': bool(prim.GetChildren())
            }
            
            # Get transform information if transformable
            xformable = UsdGeom.Xformable(prim)
            if xformable:
                try:
                    # Get local transformation matrix
                    local_matrix = xformable.GetLocalTransformation()
                    
                    # Extract components (this is approximate for display purposes)
                    info['transform'] = {
                        'has_transform': True,
                        'matrix': str(local_matrix)
                    }
                except:
                    info['transform'] = {'has_transform': False}
            
            # Check for references
            references = prim.GetReferences()
            ref_list = references.GetAddedOrExplicitItems()
            if ref_list:
                info['references'] = [str(ref.assetPath) for ref in ref_list]
            
            return info
            
        except Exception as e:
            logger.error(f"❌ Error getting asset info for {prim_path}: {e}")
            return {'success': False, 'error': str(e)}
    
    def list_assets_in_scene(self) -> Dict[str, Any]:
        """
        List all assets (prims with references) in the current scene.
        
        Returns:
            Dictionary with asset listing
        """
        try:
            stage = self._usd_context.get_stage()
            if not stage:
                return {'success': False, 'error': "No USD stage available"}
            
            assets = []
            
            # Traverse all prims in the scene
            for prim in stage.Traverse():
                if not prim.IsValid():
                    continue
                
                # Check if prim has references (indicating it's an asset)
                references = prim.GetReferences()
                ref_list = references.GetAddedOrExplicitItems()
                
                if ref_list:
                    asset_info = {
                        'prim_path': str(prim.GetPath()),
                        'prim_type': prim.GetTypeName(),
                        'references': [str(ref.assetPath) for ref in ref_list],
                        'is_active': prim.IsActive()
                    }
                    
                    # Get basic transform info if available
                    xformable = UsdGeom.Xformable(prim)
                    if xformable:
                        try:
                            local_matrix = xformable.GetLocalTransformation()
                            # Extract translation component for quick reference
                            translation = local_matrix.ExtractTranslation()
                            asset_info['position'] = [translation[0], translation[1], translation[2]]
                        except:
                            asset_info['position'] = None
                    
                    assets.append(asset_info)
            
            return {
                'success': True,
                'asset_count': len(assets),
                'assets': assets
            }
            
        except Exception as e:
            logger.error(f"❌ Error listing assets in scene: {e}")
            return {'success': False, 'error': str(e)}
    
    def validate_asset_placement(self, asset: AssetPlacement) -> Dict[str, Any]:
        """
        Validate asset placement parameters before processing.
        
        Args:
            asset: AssetPlacement to validate
            
        Returns:
            Validation result dictionary
        """
        errors = []
        
        # Check required fields
        if not asset.name or not asset.name.strip():
            errors.append("Asset name cannot be empty")
        
        if not asset.asset_path or not asset.asset_path.strip():
            errors.append("Asset path cannot be empty")
        
        if not asset.prim_path or not asset.prim_path.strip():
            errors.append("Prim path cannot be empty")
        
        # Validate asset file exists
        if asset.asset_path and not self.validate_asset_path(asset.asset_path):
            errors.append(f"Asset file not found or not accessible: {asset.asset_path}")
        
        # Validate scale values
        if any(s <= 0.0 for s in asset.scale):
            errors.append("Scale values must be positive")
        
        # Validate prim path format
        if asset.prim_path and not asset.prim_path.startswith('/'):
            # This is a warning, not an error - we can prepend /World/
            pass
        
        return {
            'valid': len(errors) == 0,
            'errors': errors
        }