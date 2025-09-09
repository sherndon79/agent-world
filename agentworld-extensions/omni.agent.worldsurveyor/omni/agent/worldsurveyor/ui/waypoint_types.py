"""
Waypoint type definitions and registry for WorldSurveyor.

This module contains all waypoint type definitions, metadata, and utility functions
for managing different waypoint types. Extracted from monolithic waypoint_toolbar.py
for better feature separation and maintainability.
"""

from typing import Dict, List, Optional


class WaypointTypeRegistry:
    """
    Registry of waypoint types with descriptions and metadata.
    
    Provides a centralized location for waypoint type definitions and utility
    functions for type management, selection, and metadata retrieval.
    """
    
    WAYPOINT_TYPES = [
        {"id": "camera_position", "name": "Camera Position", "description": "Capture current camera view"},
        {"id": "directional_lighting", "name": "Directional Lighting", "description": "Light source position and direction"},
        {"id": "point_of_interest", "name": "Point of Interest", "description": "Mark interesting location"},
        {"id": "observation_point", "name": "Observation Point", "description": "Good viewing position"},
        {"id": "target_location", "name": "Target Location", "description": "Goal or destination"},
        {"id": "walkable_area", "name": "Walkable Area", "description": "Navigable space"}
    ]
    
    @classmethod
    def get_all_types(cls) -> List[Dict[str, str]]:
        """
        Get all available waypoint types.
        
        Returns:
            List of waypoint type dictionaries with id, name, and description
        """
        return cls.WAYPOINT_TYPES.copy()
    
    @classmethod
    def get_type_info(cls, type_id: str) -> Optional[Dict[str, str]]:
        """
        Get information for a specific waypoint type.
        
        Args:
            type_id: The waypoint type identifier
            
        Returns:
            Dictionary with type information or None if not found
        """
        for waypoint_type in cls.WAYPOINT_TYPES:
            if waypoint_type["id"] == type_id:
                return waypoint_type.copy()
        return None
    
    @classmethod
    def get_type_name(cls, type_id: str) -> str:
        """
        Get the display name for a waypoint type.
        
        Args:
            type_id: The waypoint type identifier
            
        Returns:
            The display name or "Unknown" if type not found
        """
        type_info = cls.get_type_info(type_id)
        return type_info["name"] if type_info else "Unknown"
    
    @classmethod
    def get_type_description(cls, type_id: str) -> str:
        """
        Get the description for a waypoint type.
        
        Args:
            type_id: The waypoint type identifier
            
        Returns:
            The description or empty string if type not found
        """
        type_info = cls.get_type_info(type_id)
        return type_info["description"] if type_info else ""
    
    @classmethod
    def is_valid_type(cls, type_id: str) -> bool:
        """
        Check if a waypoint type ID is valid.
        
        Args:
            type_id: The waypoint type identifier to check
            
        Returns:
            True if the type ID is valid, False otherwise
        """
        return any(wtype["id"] == type_id for wtype in cls.WAYPOINT_TYPES)
    
    @classmethod
    def get_type_ids(cls) -> List[str]:
        """
        Get all waypoint type IDs.
        
        Returns:
            List of waypoint type identifiers
        """
        return [wtype["id"] for wtype in cls.WAYPOINT_TYPES]
    
    @classmethod
    def get_default_type_id(cls) -> str:
        """
        Get the default waypoint type ID.
        
        Returns:
            The ID of the first waypoint type (camera_position)
        """
        return cls.WAYPOINT_TYPES[0]["id"] if cls.WAYPOINT_TYPES else ""
    
    @classmethod
    def get_next_type_id(cls, current_type_id: str) -> str:
        """
        Get the next waypoint type ID in sequence (for cycling through types).
        
        Args:
            current_type_id: The current waypoint type ID
            
        Returns:
            The next type ID in the sequence, or the first if current not found
        """
        current_index = next((i for i, wtype in enumerate(cls.WAYPOINT_TYPES) 
                            if wtype["id"] == current_type_id), -1)
        
        if current_index == -1:
            return cls.get_default_type_id()
            
        next_index = (current_index + 1) % len(cls.WAYPOINT_TYPES)
        return cls.WAYPOINT_TYPES[next_index]["id"]
    
    @classmethod
    def get_previous_type_id(cls, current_type_id: str) -> str:
        """
        Get the previous waypoint type ID in sequence (for cycling through types).
        
        Args:
            current_type_id: The current waypoint type ID
            
        Returns:
            The previous type ID in the sequence, or the last if current not found
        """
        current_index = next((i for i, wtype in enumerate(cls.WAYPOINT_TYPES) 
                            if wtype["id"] == current_type_id), -1)
        
        if current_index == -1:
            return cls.get_default_type_id()
            
        previous_index = (current_index - 1) % len(cls.WAYPOINT_TYPES)
        return cls.WAYPOINT_TYPES[previous_index]["id"]


# Convenience functions for backward compatibility and ease of use
def get_all_waypoint_types() -> List[Dict[str, str]]:
    """Get all available waypoint types (convenience function)."""
    return WaypointTypeRegistry.get_all_types()


def get_waypoint_type_name(type_id: str) -> str:
    """Get display name for waypoint type (convenience function)."""
    return WaypointTypeRegistry.get_type_name(type_id)


def is_valid_waypoint_type(type_id: str) -> bool:
    """Check if waypoint type is valid (convenience function)."""
    return WaypointTypeRegistry.is_valid_type(type_id)