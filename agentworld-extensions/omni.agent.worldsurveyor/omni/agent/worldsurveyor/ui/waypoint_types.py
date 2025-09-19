"""
Waypoint type definitions and registry for WorldSurveyor.

This module provides waypoint type definitions and utility functions loaded from
external configuration files for user extensibility and customization.
Extracted from monolithic waypoint_toolbar.py for better feature separation.
"""

from typing import Dict, List, Optional
from ..config import get_config


class WaypointTypeRegistry:
    """
    Registry of waypoint types with descriptions and metadata.

    Loads waypoint type definitions from external JSON configuration files,
    allowing users to customize types, colors, behaviors, and icons.
    """
    
    @classmethod
    def get_all_types(cls) -> List[Dict[str, str]]:
        """
        Get all available waypoint types from configuration.

        Returns:
            List of waypoint type dictionaries with id, name, description, color, icon, behavior
        """
        config = get_config()
        return config.waypoint_types

    @classmethod
    def get_type_info(cls, type_id: str) -> Optional[Dict[str, str]]:
        """
        Get information for a specific waypoint type.

        Args:
            type_id: The waypoint type identifier

        Returns:
            Dictionary with type information or None if not found
        """
        config = get_config()
        return config.get_waypoint_type_info(type_id)

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
    def get_type_color(cls, type_id: str) -> List[float]:
        """
        Get the color for a waypoint type.

        Args:
            type_id: The waypoint type identifier

        Returns:
            RGB color array [r, g, b] with values 0-1
        """
        config = get_config()
        return config.get_waypoint_color(type_id)

    @classmethod
    def get_type_icon(cls, type_id: str) -> str:
        """
        Get the icon for a waypoint type.

        Args:
            type_id: The waypoint type identifier

        Returns:
            Unicode icon string
        """
        config = get_config()
        return config.get_waypoint_icon(type_id)

    @classmethod
    def get_type_behavior(cls, type_id: str) -> str:
        """
        Get the behavior for a waypoint type.

        Args:
            type_id: The waypoint type identifier

        Returns:
            Behavior type: "camera" or "crosshair"
        """
        config = get_config()
        return config.get_waypoint_behavior(type_id)

    @classmethod
    def get_type_marker_size(cls, type_id: str) -> int:
        """
        Get the marker size for a waypoint type.

        Args:
            type_id: The waypoint type identifier

        Returns:
            Marker size in pixels
        """
        config = get_config()
        return config.get_waypoint_marker_size(type_id)

    @classmethod
    def is_valid_type(cls, type_id: str) -> bool:
        """
        Check if a waypoint type ID is valid.

        Args:
            type_id: The waypoint type identifier to check

        Returns:
            True if the type ID is valid, False otherwise
        """
        config = get_config()
        return config.is_valid_waypoint_type(type_id)

    @classmethod
    def get_type_ids(cls) -> List[str]:
        """
        Get all waypoint type IDs.

        Returns:
            List of waypoint type identifiers
        """
        config = get_config()
        return config.get_waypoint_type_ids()

    @classmethod
    def get_default_type_id(cls) -> str:
        """
        Get the default waypoint type ID.

        Returns:
            The ID of the first waypoint type
        """
        config = get_config()
        return config.get_default_waypoint_type_id()

    @classmethod
    def get_next_type_id(cls, current_type_id: str) -> str:
        """
        Get the next waypoint type ID in sequence (for cycling through types).

        Args:
            current_type_id: The current waypoint type ID

        Returns:
            The next type ID in the sequence, or the first if current not found
        """
        type_ids = cls.get_type_ids()
        try:
            current_index = type_ids.index(current_type_id)
            next_index = (current_index + 1) % len(type_ids)
            return type_ids[next_index]
        except (ValueError, IndexError):
            return cls.get_default_type_id()

    @classmethod
    def get_previous_type_id(cls, current_type_id: str) -> str:
        """
        Get the previous waypoint type ID in sequence (for cycling through types).

        Args:
            current_type_id: The current waypoint type ID

        Returns:
            The previous type ID in the sequence, or the last if current not found
        """
        type_ids = cls.get_type_ids()
        try:
            current_index = type_ids.index(current_type_id)
            previous_index = (current_index - 1) % len(type_ids)
            return type_ids[previous_index]
        except (ValueError, IndexError):
            return cls.get_default_type_id()


# Convenience functions for backward compatibility and ease of use
def get_all_waypoint_types() -> List[Dict[str, str]]:
    """Get all available waypoint types (convenience function)."""
    return WaypointTypeRegistry.get_all_types()


def get_waypoint_type_name(type_id: str) -> str:
    """Get display name for waypoint type (convenience function)."""
    return WaypointTypeRegistry.get_type_name(type_id)


def get_waypoint_type_color(type_id: str) -> List[float]:
    """Get color for waypoint type (convenience function)."""
    return WaypointTypeRegistry.get_type_color(type_id)


def get_waypoint_type_icon(type_id: str) -> str:
    """Get icon for waypoint type (convenience function)."""
    return WaypointTypeRegistry.get_type_icon(type_id)


def get_waypoint_type_behavior(type_id: str) -> str:
    """Get behavior for waypoint type (convenience function)."""
    return WaypointTypeRegistry.get_type_behavior(type_id)


def get_waypoint_type_marker_size(type_id: str) -> int:
    """Get marker size for waypoint type (convenience function)."""
    return WaypointTypeRegistry.get_type_marker_size(type_id)


def is_valid_waypoint_type(type_id: str) -> bool:
    """Check if waypoint type is valid (convenience function)."""
    return WaypointTypeRegistry.is_valid_type(type_id)