"""
Bounds Calculator for WorldBuilder Extension

Handles USD geometry bounds calculation using Isaac Sim and Omniverse best practices.
"""

import logging
from typing import Optional, Dict, List, Any

logger = logging.getLogger(__name__)


class BoundsCalculator:
    """Calculate spatial bounds for USD prims with multiple fallback strategies."""
    
    def __init__(self):
        self._last_selection = []
        self._cached_bounds = None
    
    def calculate_selection_bounds(self, stage, prim_paths: List[str]) -> Optional[Dict[str, Any]]:
        """Calculate combined bounds using Isaac Sim and Omniverse best practices."""
        try:
            logger.info(f"Calculating bounds for {len(prim_paths)} selected prims: {prim_paths}")
            
            all_min = [float('inf')] * 3
            all_max = [float('-inf')] * 3
            valid_bounds_count = 0
            
            for prim_path in prim_paths:
                logger.info(f"Processing prim {prim_path}")
                
                # Method 1: Use Omniverse USD context (most reliable)
                bounds_data = self._try_omniverse_context_bounds(prim_path)
                if bounds_data:
                    min_pt, max_pt = bounds_data
                    for i in range(3):
                        all_min[i] = min(all_min[i], min_pt[i])
                        all_max[i] = max(all_max[i], max_pt[i])
                    valid_bounds_count += 1
                    logger.info(f"Omniverse context bounds success for {prim_path}: min={min_pt}, max={max_pt}")
                    continue
                
                # Method 2: Try Isaac Sim bounds utilities
                bounds_data = self._try_isaac_sim_bounds(prim_path)
                if bounds_data:
                    # bounds_data is numpy array [min_x, min_y, min_z, max_x, max_y, max_z]
                    min_pt = bounds_data[:3]
                    max_pt = bounds_data[3:]
                    for i in range(3):
                        all_min[i] = min(all_min[i], min_pt[i])
                        all_max[i] = max(all_max[i], max_pt[i])
                    valid_bounds_count += 1
                    logger.info(f"Isaac Sim bounds success for {prim_path}: min={min_pt}, max={max_pt}")
                    continue
                
                # Method 3: Standard USD Imageable approach
                prim = stage.GetPrimAtPath(prim_path)
                if prim and prim.IsValid():
                    bounds_data = self._try_usd_imageable_bounds(prim)
                    if bounds_data:
                        min_pt, max_pt = bounds_data
                        for i in range(3):
                            all_min[i] = min(all_min[i], min_pt[i])
                            all_max[i] = max(all_max[i], max_pt[i])
                        valid_bounds_count += 1
                        logger.info(f"USD Imageable bounds success for {prim_path}: min={min_pt}, max={max_pt}")
                        continue
                
                # Method 4: Fallback to transform position
                bounds_data = self._try_transform_position(stage, prim_path)
                if bounds_data:
                    pos = bounds_data
                    for i in range(3):
                        all_min[i] = min(all_min[i], pos[i])
                        all_max[i] = max(all_max[i], pos[i])
                    valid_bounds_count += 1
                    logger.info(f"Transform position fallback for {prim_path}: {pos}")
            
            if valid_bounds_count == 0:
                return None
            
            # Calculate center and size
            center = [(all_min[i] + all_max[i]) / 2 for i in range(3)]
            size = [all_max[i] - all_min[i] for i in range(3)]
            
            logger.info(f"Final bounds: center={center}, size={size}, min={all_min}, max={all_max}")
            
            return {
                'center': center,
                'size': size,
                'min': all_min,
                'max': all_max
            }
            
        except Exception as e:
            logger.error(f"Error calculating selection bounds: {e}")
            return None
    
    def _try_omniverse_context_bounds(self, prim_path: str):
        """Use Omniverse USD context bounds calculation (most reliable)."""
        try:
            import omni.usd
            context = omni.usd.get_context()
            if context:
                min_pt, max_pt = context.compute_path_world_bounding_box(prim_path)
                # Convert to regular tuples and check validity
                min_coords = (min_pt.x, min_pt.y, min_pt.z)
                max_coords = (max_pt.x, max_pt.y, max_pt.z)
                
                # Check if bounds are valid (not infinity)
                is_valid = all(abs(coord) < 1e30 for coord in min_coords + max_coords)
                if is_valid and any(min_coords[i] != max_coords[i] for i in range(3)):
                    return min_coords, max_coords
        except Exception as e:
            logger.debug(f"Omniverse context bounds failed for {prim_path}: {e}")
        return None
    
    def _try_isaac_sim_bounds(self, prim_path: str):
        """Use Isaac Sim bounds utilities."""
        try:
            # Try Isaac Sim bounds utilities
            from isaacsim.core.utils import bounds_utils
            cache = bounds_utils.create_bbox_cache()
            bounds = bounds_utils.compute_aabb(cache, prim_path)
            
            # bounds is numpy array [min_x, min_y, min_z, max_x, max_y, max_z]
            if bounds is not None and len(bounds) == 6:
                # Check if bounds are valid
                is_valid = all(abs(coord) < 1e30 for coord in bounds)
                if is_valid:
                    return bounds
        except Exception as e:
            logger.debug(f"Isaac Sim bounds failed for {prim_path}: {e}")
        return None
    
    def _try_usd_imageable_bounds(self, prim):
        """Use standard USD Imageable bounds calculation."""
        try:
            from pxr import UsdGeom, Usd, Gf
            
            imageable = UsdGeom.Imageable(prim)
            if imageable:
                time = Usd.TimeCode.Default()
                bound = imageable.ComputeWorldBound(time, UsdGeom.Tokens.default_)
                
                if bound:
                    bound_range = bound.ComputeAlignedBox()
                    if bound_range and not bound_range.IsEmpty():
                        min_pt = bound_range.GetMin()
                        max_pt = bound_range.GetMax()
                        
                        min_coords = (float(min_pt[0]), float(min_pt[1]), float(min_pt[2]))
                        max_coords = (float(max_pt[0]), float(max_pt[1]), float(max_pt[2]))
                        
                        # Check if bounds are valid
                        is_valid = all(abs(coord) < 1e30 for coord in min_coords + max_coords)
                        if is_valid:
                            return min_coords, max_coords
        except Exception as e:
            logger.debug(f"USD Imageable bounds failed for {prim.GetPath()}: {e}")
        return None
    
    def _try_transform_position(self, stage, prim_path: str):
        """Fallback: get transform position."""
        try:
            from pxr import UsdGeom
            
            prim = stage.GetPrimAtPath(prim_path)
            if prim and prim.IsValid():
                xformable = UsdGeom.Xformable(prim)
                if xformable:
                    world_transform = xformable.ComputeLocalToWorldTransform(0.0)
                    translation = world_transform.ExtractTranslation()
                    return (float(translation[0]), float(translation[1]), float(translation[2]))
        except Exception as e:
            logger.debug(f"Transform position failed for {prim_path}: {e}")
        return None

    
    def has_selection_changed(self, current_selection: List[str]) -> bool:
        """Check if selection has changed since last calculation."""
        if current_selection != self._last_selection:
            self._last_selection = current_selection[:]
            return True
        return False