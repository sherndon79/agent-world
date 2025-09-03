"""
Core waypoint storage and management with thread safety.
"""

import logging
import threading
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import omni.kit.viewport.utility
import omni.usd
from pxr import Gf, UsdGeom

from .config import get_config
from .models import Waypoint
from .marker_manager import WaypointMarkerManager
from .waypoint_database import WaypointDatabase

logger = logging.getLogger(__name__)


class WaypointManager:
    """Core waypoint storage and management with thread safety."""
    
    def __init__(self):
        self._config = get_config()
        self._waypoints: Dict[str, Waypoint] = {}  # Keep for backward compatibility
        self._session_id = str(uuid.uuid4())[:8]
        self._marker_manager = WaypointMarkerManager()
        
        # Thread safety lock for waypoint operations
        self._lock = threading.RLock()
        
        # Initialize SQLite database backend
        self._database = WaypointDatabase()
        
        # Migration: Move existing in-memory waypoints to database on first run
        self._migrate_to_database_if_needed()
        
    def create_waypoint(
        self, 
        position: Tuple[float, float, float],
        waypoint_type: str = "point_of_interest",
        name: Optional[str] = None,
        target: Optional[Tuple[float, float, float]] = None,
        metadata: Optional[Dict] = None,
        group_ids: Optional[List[str]] = None
    ) -> str:
        """Create a new waypoint with thread safety and database persistence."""
        with self._lock:
            # Create in database (handles max waypoints check internally)
            waypoint_id = self._database.create_waypoint(
                position=position,
                waypoint_type=waypoint_type,
                name=name,
                target=target,
                metadata=metadata,
                group_ids=group_ids,
                session_id=self._session_id
            )
            
            # Update in-memory cache for backward compatibility
            waypoint = self._database.get_waypoint(waypoint_id)
            if waypoint:
                self._waypoints[waypoint_id] = waypoint
                
                # Add visual marker for the waypoint
                self._marker_manager.add_waypoint_marker(waypoint_id, position, waypoint_type)
            
            return waypoint_id
    
    def get_waypoint(self, waypoint_id: str) -> Optional[Waypoint]:
        """Get waypoint by ID with thread safety."""
        with self._lock:
            # Try database first, fallback to in-memory cache
            waypoint = self._database.get_waypoint(waypoint_id)
            if waypoint:
                # Update cache
                self._waypoints[waypoint_id] = waypoint
                return waypoint
            return self._waypoints.get(waypoint_id)
    
    def list_waypoints(self, waypoint_type: Optional[str] = None, group_id: Optional[str] = None) -> List[Waypoint]:
        """List waypoints with optional filtering and thread safety."""
        with self._lock:
            # Use database for listing with enhanced filtering
            waypoints = self._database.list_waypoints(
                waypoint_type=waypoint_type,
                group_id=group_id,
                session_id=None  # Don't filter by session to get all waypoints
            )
            
            # Update cache with retrieved waypoints
            for wp in waypoints:
                self._waypoints[wp.id] = wp
            
            return waypoints
    
    def get_waypoint_count(self) -> int:
        """Get the number of waypoints currently stored with thread safety."""
        with self._lock:
            # Use database count for accuracy
            stats = self._database.get_statistics()
            return stats['total_waypoints']

    def get_visible_marker_count(self) -> int:
        """Get the number of currently visible markers."""
        return len(self._marker_manager._markers)
    
    def remove_waypoint(self, waypoint_id: str) -> bool:
        """Remove waypoint by ID with thread safety."""
        with self._lock:
            # Remove from database
            removed = self._database.remove_waypoint(waypoint_id)
            
            if removed:
                # Remove from in-memory cache
                self._waypoints.pop(waypoint_id, None)
                
                # Remove from marker tracking
                self._marker_manager.remove_waypoint_marker(waypoint_id)
                
                # Force full refresh to sync debug markers with waypoint data
                self._marker_manager.refresh_all_markers_batched(self._waypoints)
                
                return True
            return False
    
    def remove_waypoints(self, waypoint_ids: List[str]) -> int:
        """Remove multiple waypoints by IDs with thread safety."""
        with self._lock:
            removed_count = 0
            removed_ids = []
            
            for waypoint_id in waypoint_ids:
                # Remove from database
                removed = self._database.remove_waypoint(waypoint_id)
                
                if removed:
                    removed_count += 1
                    removed_ids.append(waypoint_id)
                    
                    # Remove from in-memory cache
                    self._waypoints.pop(waypoint_id, None)
                    
                    # Remove from marker tracking
                    self._marker_manager.remove_waypoint_marker(waypoint_id)
            
            if removed_count > 0:
                # Force full refresh to sync debug markers with waypoint data
                self._marker_manager.refresh_all_markers_batched(self._waypoints)
                logger.info(f"Removed {removed_count} waypoints: {removed_ids}")
            
            return removed_count
    
    def clear_waypoints(self) -> int:
        """Clear all waypoints with thread safety."""
        with self._lock:
            # Clear from database
            count = self._database.clear_waypoints()
            
            # Clear in-memory cache
            self._waypoints.clear()
            
            # Clear all visual markers
            self._marker_manager.refresh_all_markers_batched({})
            
            logger.info(f"Cleared {count} waypoints")
            return count
    
    def refresh_waypoint_markers(self):
        """Refresh all waypoint visual markers with batched operations."""
        with self._lock:
            # Get current waypoints from database to ensure markers are in sync
            current_waypoints = self._database.list_waypoints()
            waypoint_dict = {wp.id: wp for wp in current_waypoints}
            
            # Update in-memory cache
            self._waypoints.update(waypoint_dict)
            
            # Refresh markers using database data
            self._marker_manager.refresh_all_markers_batched(waypoint_dict)
            logger.info("Refreshed all waypoint markers")
    
    def set_markers_visible(self, visible: bool):
        """Show or hide waypoint markers."""
        self._marker_manager.set_markers_visible(visible)
        if visible:
            # Refresh markers when showing with thread safety
            with self._lock:
                self._marker_manager.refresh_all_markers_batched(self._waypoints)
    
    def are_markers_visible(self) -> bool:
        """Check if waypoint markers are visible."""
        return self._marker_manager.are_markers_visible()
    
    def get_debug_status(self) -> Dict[str, Any]:
        """Get debug draw system status."""
        return self._marker_manager.get_debug_draw_status()
    
    def set_individual_marker_visible(self, waypoint_id: str, visible: bool):
        """Show or hide a specific waypoint marker with thread safety."""
        with self._lock:
            if waypoint_id not in self._waypoints:
                raise ValueError(f"Waypoint {waypoint_id} not found")
            
            self._marker_manager.set_individual_marker_visible(waypoint_id, visible)
            # Refresh to apply the change
            self._marker_manager.refresh_all_markers_batched(self._waypoints)
    
    def is_individual_marker_visible(self, waypoint_id: str) -> bool:
        """Check if a specific waypoint marker is visible."""
        return self._marker_manager.is_individual_marker_visible(waypoint_id)
    
    def get_hidden_markers(self) -> List[str]:
        """Get list of individually hidden marker IDs."""
        return list(self._marker_manager.get_hidden_markers())
    
    def set_selective_visibility(self, visible_waypoint_ids: set):
        """Set selective visibility mode - only show specified waypoints with thread safety."""
        with self._lock:
            self._marker_manager.enter_selective_mode(visible_waypoint_ids)
            # Refresh to apply the selective visibility
            self._marker_manager.refresh_all_markers_batched(self._waypoints)
    
    def update_waypoint(self, waypoint_id: str, **updates) -> bool:
        """Update waypoint fields like name, notes, metadata with thread safety."""
        with self._lock:
            # Handle special metadata updates
            for field, value in updates.items():
                if field == 'notes':
                    # Update metadata in database
                    waypoint = self._database.get_waypoint(waypoint_id)
                    if waypoint:
                        metadata = waypoint.metadata.copy()
                        metadata['notes'] = value
                        updates['metadata'] = metadata
                    
            # Update in database
            updated = self._database.update_waypoint(waypoint_id, **updates)
            
            if updated:
                # Update in-memory cache
                waypoint = self._database.get_waypoint(waypoint_id)
                if waypoint:
                    self._waypoints[waypoint_id] = waypoint
                
                logger.info(f"Updated waypoint {waypoint_id} with fields: {list(updates.keys())}")
                return True
            
            return False

    # =============================
    # Group management (encapsulated)
    # =============================
    def create_group(self, name: str, description: Optional[str] = None,
                     parent_group_id: Optional[str] = None, color: str = "#4A90E2") -> str:
        with self._lock:
            return self._database.create_group(name=name, description=description,
                                               parent_group_id=parent_group_id, color=color)

    def list_groups(self, parent_group_id: Optional[str] = None) -> List[Dict[str, Any]]:
        with self._lock:
            return self._database.list_groups(parent_group_id)

    def get_group(self, group_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            return self._database.get_group(group_id)

    def get_group_hierarchy(self) -> Dict[str, Any]:
        with self._lock:
            return self._database.get_group_hierarchy()

    def remove_group(self, group_id: str, cascade: bool = False) -> bool:
        with self._lock:
            return self._database.remove_group(group_id, cascade)

    def add_waypoint_to_groups(self, waypoint_id: str, group_ids: List[str]) -> int:
        with self._lock:
            return self._database.add_waypoint_to_groups(waypoint_id, group_ids)

    def remove_waypoint_from_groups(self, waypoint_id: str, group_ids: List[str]) -> int:
        with self._lock:
            return self._database.remove_waypoint_from_groups(waypoint_id, group_ids)

    def get_waypoint_groups(self, waypoint_id: str) -> List[Dict[str, Any]]:
        with self._lock:
            return self._database.get_waypoint_groups(waypoint_id)

    def get_group_waypoints(self, group_id: str, include_nested: bool = False) -> List[Waypoint]:
        with self._lock:
            return self._database.get_group_waypoints(group_id, include_nested)

    def export_waypoints(self, include_groups: bool = True) -> Dict[str, Any]:
        with self._lock:
            return self._database.export_to_json(include_groups)

    def import_waypoints(self, data: Dict[str, Any], merge_mode: str = "replace") -> Dict[str, int]:
        with self._lock:
            return self._database.import_from_json(data, merge_mode)
    
    def get_camera_position_and_target(self) -> Tuple[Tuple[float, float, float], Tuple[float, float, float]]:
        """Get current viewport camera position and target point."""
        try:
            viewport_window = omni.kit.viewport.utility.get_active_viewport_window()
            if not viewport_window:
                raise RuntimeError("No active viewport found")
                
            # Get camera path from viewport API
            if not hasattr(viewport_window, 'viewport_api') or not viewport_window.viewport_api:
                raise RuntimeError("No viewport API available")
                
            camera_path = viewport_window.viewport_api.camera_path
            if not camera_path:
                raise RuntimeError("No active camera path found")
                
            stage = omni.usd.get_context().get_stage()
            if not stage:
                raise RuntimeError("No USD stage found")
                
            camera_prim = stage.GetPrimAtPath(camera_path)
            if not camera_prim:
                raise RuntimeError(f"Camera prim not found at {camera_path}")
                
            # Get world transform using UsdGeom
            xform_cache = UsdGeom.XformCache()
            world_transform = xform_cache.GetLocalToWorldTransform(camera_prim)
            
            # Extract position
            translation = world_transform.ExtractTranslation()
            position = (float(translation[0]), float(translation[1]), float(translation[2]))
            
            # Calculate target point using camera's forward direction
            # This is the same method WorldViewer uses in get_camera_status
            try:
                from pxr import Gf
                
                # Get camera forward direction (-Z axis in Isaac Sim camera convention)
                forward = world_transform.TransformDir(Gf.Vec3d(0, 0, -1))
                
                # Calculate target at reasonable distance (same as WorldViewer uses)
                target_distance = 10.0
                target_position = (
                    float(translation[0] + forward[0] * target_distance),
                    float(translation[1] + forward[1] * target_distance),
                    float(translation[2] + forward[2] * target_distance)
                )
                
                logger.info(f"Captured camera: position={position}, target={target_position}")
                
            except Exception as target_error:
                logger.warning(f"Could not calculate target, using default: {target_error}")
                # Default target 10 units forward in world coordinates
                target_position = (position[0], position[1], position[2] - 10.0)
            
            return position, target_position
            
        except Exception as e:
            logger.error(f"Error getting camera position: {e}")
            raise
    
    def _migrate_to_database_if_needed(self):
        """Migrate existing in-memory waypoints to database on first run."""
        try:
            # Check if database is empty and we have in-memory waypoints
            stats = self._database.get_statistics()
            if stats['total_waypoints'] == 0 and self._waypoints:
                logger.info(f"Migrating {len(self._waypoints)} waypoints to database")
                migrated = self._database.migrate_from_memory(self._waypoints)
                logger.info(f"Successfully migrated {migrated} waypoints to database")
                
                # Clear old in-memory data after successful migration
                self._waypoints.clear()
                
        except Exception as e:
            logger.error(f"Migration error: {e}")
            # Keep in-memory data as fallback if migration fails
