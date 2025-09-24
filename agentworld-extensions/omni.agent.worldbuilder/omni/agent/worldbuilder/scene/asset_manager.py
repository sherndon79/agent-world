"""
USD asset management for WorldBuilder scene operations.

Provides asset placement, transformation, and validation operations with proper USD reference handling.
"""

import logging
import os
import sys
from typing import Dict, Any, Optional, Tuple, List
from pxr import Usd, UsdGeom, Gf

from .scene_types import AssetPlacement

logger = logging.getLogger(__name__)

# Add path for centralized security modules (relative to this file)
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
AGENTWORLD_EXTENSIONS_PATH = os.path.join(CURRENT_DIR, "..", "..", "..", "..", "..", "agentworld-extensions")
AGENTWORLD_EXTENSIONS_PATH = os.path.abspath(AGENTWORLD_EXTENSIONS_PATH)

if AGENTWORLD_EXTENSIONS_PATH not in sys.path:
    sys.path.insert(0, AGENTWORLD_EXTENSIONS_PATH)

# Try to import centralized asset security validator
try:
    from agent_world_asset_security import AssetPathValidator
    CENTRALIZED_SECURITY_AVAILABLE = True
    logger.info("✅ Centralized asset security module loaded")
except ImportError as e:
    logger.warning(f"⚠️ Could not import centralized asset security: {e}")
    CENTRALIZED_SECURITY_AVAILABLE = False


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
            
            # Create USD reference container prim
            # Use the asset name as the container (e.g., 'test_mug' -> '/World/test_mug')
            container_path = asset.prim_path if asset.prim_path.startswith('/') else f"/World/{asset.name}"

            # Define the container prim as an Xform (transformable container)
            container_prim = stage.DefinePrim(container_path, "Xform")
            if not container_prim:
                return {
                    'success': False,
                    'error': f"Failed to create container prim at path: {container_path}"
                }

            # Add USD reference to the container
            references = container_prim.GetReferences()
            references.AddReference(asset.asset_path)

            logger.info(f"📦 Created USD reference container at {container_path}")
            
            # Apply transforms to the container prim (not the referenced content)
            if any(asset.position) or any(asset.rotation) or any(v != 1.0 for v in asset.scale):
                try:
                    # Make the container prim transformable (correct approach for references)
                    xformable = UsdGeom.Xformable(container_prim)
                    
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
            
            logger.info(f"✅ Placed asset '{asset.name}' via USD reference at {container_path}")

            return {
                'success': True,
                'asset_name': asset.name,
                'asset_path': asset.asset_path,
                'prim_path': container_path,
                'position': asset.position,
                'rotation': asset.rotation,
                'scale': asset.scale,
                'message': f"Placed asset '{asset.name}' in USD scene via reference container"
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
    
    def _get_safe_asset_paths(self) -> List[str]:
        """Get safe asset search paths with proper fallback logic."""
        # Calculate agent-world assets path once
        agent_world_root = os.path.join(CURRENT_DIR, "..", "..", "..", "..", "..")
        agent_world_assets = os.path.abspath(os.path.join(agent_world_root, "assets"))

        # Return list of safe asset paths
        safe_paths = []
        if os.path.exists(agent_world_assets):
            safe_paths.append(agent_world_assets)

        return safe_paths

    def _validate_usd_file_content(self, file_path: str) -> bool:
        """Validate that file content matches USD format expectations."""
        try:
            with open(file_path, 'rb') as f:
                header = f.read(16)

                # Check for USD binary format
                if header.startswith(b'PXR-USDC'):
                    return True

                # Check for USD ASCII format
                if header.startswith(b'#usda'):
                    return True

                # For USDZ (ZIP format), check ZIP signature
                if header.startswith(b'PK'):
                    return True

                # Sometimes USDA files don't start with #usda, check for USD-like content
                try:
                    header_text = header.decode('utf-8', errors='ignore')
                    if 'usda' in header_text.lower() or 'def ' in header_text:
                        return True
                except:
                    pass

            return False
        except Exception as e:
            logger.warning(f"Could not validate file content for {file_path}: {e}")
            return False

    def validate_asset_path(self, asset_path: str) -> bool:
        """
        Validate asset file exists and is readable.
        Fast path for Isaac Sim USD formats with content validation.
        """
        try:
            if not asset_path or not asset_path.strip():
                return False

            # Fast path: Isaac Sim directly usable formats (USD family only)
            isaac_sim_extensions = ['.usd', '.usda', '.usdz']
            if any(asset_path.lower().endswith(ext) for ext in isaac_sim_extensions):
                # Verify file exists
                if not (os.path.exists(asset_path) and os.path.isfile(asset_path)):
                    logger.error(f"❌ USD asset file not found: {asset_path}")
                    return False

                # Validate file content matches expected format
                if not self._validate_usd_file_content(asset_path):
                    logger.error(f"❌ File does not contain valid USD content: {asset_path}")
                    return False

                logger.debug(f"✅ USD asset validated (fast path): {asset_path}")
                return True

            # For non-USD files, reject them - only directly loadable formats allowed
            logger.error(f"❌ Unsupported file type for direct asset placement: {asset_path}")
            logger.error("Only USD formats (.usd, .usda, .usdz) are supported for direct asset placement")
            return False

        except Exception as e:
            logger.error(f"❌ Error validating asset path {asset_path}: {e}")
            return False

    def _fallback_validate_asset_path(self, asset_path: str) -> bool:
        """Simple fallback asset validation when centralized validation is unavailable."""
        if not asset_path or not asset_path.strip():
            return False

        # Security check: prevent path traversal attacks
        if '..' in asset_path:
            logger.warning(f"Path traversal attempt blocked: {asset_path}")
            return False

        # Get safe search paths
        search_paths = self._get_safe_asset_paths()

        # For absolute paths, check against allowed directories
        if os.path.isabs(asset_path):
            for allowed_path in search_paths:
                if asset_path.startswith(allowed_path):
                    real_asset_path = os.path.realpath(asset_path)
                    real_allowed_path = os.path.realpath(allowed_path)
                    if real_asset_path.startswith(real_allowed_path + os.sep):
                        return os.path.exists(asset_path) and os.path.isfile(asset_path)
            return False

        # For relative paths, search in safe directories
        for search_path in search_paths:
            full_path = os.path.join(search_path, asset_path)
            if os.path.exists(full_path) and os.path.isfile(full_path):
                return True

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