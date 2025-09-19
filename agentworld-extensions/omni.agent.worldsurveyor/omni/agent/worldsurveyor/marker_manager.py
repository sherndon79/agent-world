"""
Visual marker management for waypoints in 3D scene.
"""

import logging
from typing import Any, Dict, Tuple

from isaacsim.util.debug_draw import _debug_draw
from .models import Waypoint
from .ui.waypoint_types import get_waypoint_type_behavior, get_waypoint_type_color, get_waypoint_type_marker_size

logger = logging.getLogger(__name__)


class WaypointMarkerManager:
    """Manages visual debug markers for waypoints in 3D scene."""
    
    def __init__(self):
        self._markers = {}  # waypoint_id -> marker info
        self._debug_draw = None
        self._markers_visible = True
        self._hidden_markers = set()  # Track individually hidden markers
        self._selective_mode = False  # Track if we're in selective visibility mode
        self._visible_markers = set()  # Track individually visible markers in selective mode
        
    def _get_debug_draw(self):
        """Get debug draw interface lazily with caching."""
        if self._debug_draw is None:
            try:
                self._debug_draw = _debug_draw.acquire_debug_draw_interface()
            except Exception as e:
                logger.debug(f"Could not get debug draw interface: {e}")
        return self._debug_draw
    
    def add_waypoint_marker(self, waypoint_id: str, position: Tuple[float, float, float], waypoint_type: str):
        """Add a visual marker for a waypoint."""
        debug_draw = self._get_debug_draw()
        if not debug_draw:
            return
            
        try:
            # Get color from waypoint type configuration
            rgb_color = get_waypoint_type_color(waypoint_type)
            # Convert RGB [0-1] to RGBA tuple for debug draw
            color = (rgb_color[0], rgb_color[1], rgb_color[2], 1.0)

            # Draw points with configurable sizes
            marker_size = get_waypoint_type_marker_size(waypoint_type)
            debug_draw.draw_points([position], [color], [marker_size])
                
            # Store marker info
            self._markers[waypoint_id] = {
                'position': position,
                'type': waypoint_type,
                'color': color
            }
            
            logger.info(f"Added debug marker for waypoint {waypoint_id} at {position}")
            
        except Exception as e:
            logger.error(f"Failed to add waypoint marker: {e}")
    
    def remove_waypoint_marker(self, waypoint_id: str):
        """Remove a waypoint marker (markers auto-expire, so just remove from tracking)."""
        if waypoint_id in self._markers:
            del self._markers[waypoint_id]
            logger.info(f"Removed marker tracking for waypoint {waypoint_id}")
    
    def refresh_all_markers_batched(self, waypoints: Dict[str, 'Waypoint']):
        """Refresh all waypoint markers with batched drawing for better performance."""
        debug_draw = self._get_debug_draw()
        if not debug_draw:
            return
            
        # Clear existing debug points first
        try:
            debug_draw.clear_points()
        except Exception as e:
            logger.debug(f"Error clearing debug points: {e}")
            
        # Clear tracking and prepare batch data
        self._markers.clear()
        
        if not self._markers_visible:
            return
            
        # Batch data for drawing
        positions = []
        colors = []
        sizes = []

        for waypoint_id, waypoint in waypoints.items():
            should_show = False

            if self._selective_mode:
                should_show = waypoint_id in self._visible_markers
            else:
                should_show = waypoint_id not in self._hidden_markers

            if should_show:
                positions.append(waypoint.position)

                # Get color from waypoint type configuration
                rgb_color = get_waypoint_type_color(waypoint.waypoint_type)
                color = (rgb_color[0], rgb_color[1], rgb_color[2], 1.0)
                colors.append(color)

                # Get size from waypoint type configuration
                size = get_waypoint_type_marker_size(waypoint.waypoint_type)
                sizes.append(size)
                
                # Store marker info for tracking
                self._markers[waypoint_id] = {
                    'position': waypoint.position,
                    'type': waypoint.waypoint_type,
                    'color': color
                }
        
        # Single batched draw call for all markers
        if positions:
            try:
                debug_draw.draw_points(positions, colors, sizes)
                logger.info(f"Batched draw of {len(positions)} waypoint markers")
            except Exception as e:
                logger.error(f"Failed to draw batched markers: {e}")
    
    def set_markers_visible(self, visible: bool):
        """Show or hide all waypoint markers."""
        self._markers_visible = visible
        
        # Reset to normal mode when using global show/hide
        if visible:
            self.exit_selective_mode()
            # Also clear individually hidden markers when showing all
            self._hidden_markers.clear()
        
        debug_draw = self._get_debug_draw()
        if not debug_draw:
            return
            
        if not visible:
            # Clear all debug points when hiding
            try:
                debug_draw.clear_points()
                logger.info("Waypoint markers hidden - all debug points cleared")
            except Exception as e:
                logger.error(f"Error hiding markers: {e}")
        else:
            # When showing, we need to refresh to redraw all visible markers
            logger.info("Waypoint markers shown - will redraw when refresh is called")
    
    def are_markers_visible(self) -> bool:
        """Check if waypoint markers are currently visible."""
        return self._markers_visible
    
    def get_debug_draw_status(self) -> Dict[str, Any]:
        """Get status of debug draw system."""
        debug_draw = self._get_debug_draw()
        if not debug_draw:
            return {"available": False, "error": "Debug draw interface not available"}
        
        try:
            num_points = debug_draw.get_num_points()
            return {
                "available": True,
                "num_points": num_points,
                "markers_visible": self._markers_visible,
                "tracked_markers": len(self._markers)
            }
        except Exception as e:
            return {"available": False, "error": str(e)}
    
    def set_individual_marker_visible(self, waypoint_id: str, visible: bool):
        """Show or hide a specific waypoint marker."""
        if visible:
            if self._selective_mode:
                # In selective mode, add to visible set
                self._visible_markers.add(waypoint_id)
            else:
                # In normal mode, remove from hidden set
                self._hidden_markers.discard(waypoint_id)
        else:
            if self._selective_mode:
                # In selective mode, remove from visible set
                self._visible_markers.discard(waypoint_id)
            else:
                # In normal mode, add to hidden set
                self._hidden_markers.add(waypoint_id)
        
        logger.info(f"Individual marker visibility changed for {waypoint_id}: {'shown' if visible else 'hidden'}")
        
        # Note: Caller must call refresh_all_markers_batched() to apply the change
        # This is a limitation of debug_draw - we have to redraw everything
    
    def is_individual_marker_visible(self, waypoint_id: str) -> bool:
        """Check if a specific waypoint marker is visible."""
        if self._selective_mode:
            return waypoint_id in self._visible_markers
        else:
            return waypoint_id not in self._hidden_markers
    
    def get_hidden_markers(self) -> set:
        """Get set of individually hidden marker IDs."""
        return self._hidden_markers.copy()
    
    def enter_selective_mode(self, visible_waypoint_ids: set):
        """Enter selective mode where only specified waypoints are visible."""
        self._selective_mode = True
        self._visible_markers = visible_waypoint_ids.copy()
        logger.info(f"Entered selective mode with {len(visible_waypoint_ids)} visible markers")
    
    def exit_selective_mode(self):
        """Exit selective mode and return to normal show/hide behavior."""
        self._selective_mode = False
        self._visible_markers.clear()
        logger.info("Exited selective mode")