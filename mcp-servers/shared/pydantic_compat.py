#!/usr/bin/env python3
"""
Pydantic v1/v2 Compatibility Layer for MCP Servers

This module provides utilities to generate JSON schemas compatible with both
Pydantic v1 (used in Isaac Sim extensions) and Pydantic v2 (used in MCP servers).

The main issue is that Pydantic v1 doesn't support minItems/maxItems constraints
on arrays, which causes validation errors in Isaac Sim extensions.
"""

import sys
from typing import Dict, Any, List, Optional, Union


def detect_pydantic_version() -> int:
    """
    Detect which version of Pydantic is available.
    
    Returns:
        1 or 2 based on Pydantic version, or 1 as fallback
    """
    try:
        import pydantic
        if hasattr(pydantic, 'VERSION'):
            # Pydantic v1 has VERSION attribute
            return 1
        elif hasattr(pydantic, '__version__'):
            # Pydantic v2 has __version__ attribute
            version = pydantic.__version__
            if version.startswith('2.'):
                return 2
            else:
                return 1
        else:
            return 1
    except ImportError:
        return 1


def create_compatible_array_schema(
    item_type: str = "number",
    length: Optional[int] = None,
    min_length: Optional[int] = None,
    max_length: Optional[int] = None,
    description: str = "Array field",
    item_constraints: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Create array schema compatible with both Pydantic v1 and v2.
    
    Args:
        item_type: Type of array items ("number", "string", etc.)
        length: Exact length required (e.g., 3 for [x, y, z])
        min_length: Minimum array length (alternative to length)
        max_length: Maximum array length (alternative to length)
        description: Field description
        item_constraints: Additional constraints for array items (e.g., {"minimum": 0})
        
    Returns:
        JSON schema dict compatible with both Pydantic versions
    """
    # Base schema without v2-specific constraints
    schema = {
        "type": "array",
        "description": description
    }
    
    # Item schema
    item_schema = {"type": item_type}
    if item_constraints:
        item_schema.update(item_constraints)
    
    schema["items"] = item_schema
    
    # For exact length (like [x, y, z] coordinates), use v1-compatible approach
    if length is not None:
        # Pydantic v1 compatible: don't use minItems/maxItems
        # Instead, rely on manual validation in the endpoint
        schema["description"] += f" (exactly {length} items required)"
        
        # Add a custom property that our validation can check
        schema["_expected_length"] = length
        
    elif min_length is not None or max_length is not None:
        # For flexible lengths, add to description but don't use constraints
        constraints = []
        if min_length is not None:
            constraints.append(f"min {min_length}")
            schema["_min_length"] = min_length
        if max_length is not None:
            constraints.append(f"max {max_length}")
            schema["_max_length"] = max_length
            
        if constraints:
            schema["description"] += f" ({', '.join(constraints)} items)"
    
    return schema


def create_compatible_position_schema(description: str = "XYZ position [x, y, z]") -> Dict[str, Any]:
    """Create a 3D position array schema compatible with both Pydantic versions."""
    return create_compatible_array_schema(
        item_type="number",
        length=3,
        description=description
    )


def create_compatible_color_schema(description: str = "RGB color [r, g, b] values between 0-1") -> Dict[str, Any]:
    """Create an RGB color array schema compatible with both Pydantic versions."""
    return create_compatible_array_schema(
        item_type="number",
        length=3,
        description=description,
        item_constraints={"minimum": 0, "maximum": 1}
    )


def create_compatible_scale_schema(description: str = "XYZ scale [x, y, z] multipliers") -> Dict[str, Any]:
    """Create a 3D scale array schema compatible with both Pydantic versions."""
    return create_compatible_array_schema(
        item_type="number", 
        length=3,
        description=description,
        item_constraints={"minimum": 0.1}
    )


def create_compatible_rotation_schema(description: str = "XYZ rotation [rx, ry, rz] in degrees") -> Dict[str, Any]:
    """Create a 3D rotation array schema compatible with both Pydantic versions."""
    return create_compatible_array_schema(
        item_type="number",
        length=3,
        description=description
    )


def validate_array_length(data: List[Any], expected_length: int, field_name: str) -> bool:
    """
    Manual validation helper for array length since we can't use schema constraints.
    
    Args:
        data: Array data to validate
        expected_length: Expected array length
        field_name: Field name for error messages
        
    Returns:
        True if valid, raises ValueError if invalid
    """
    if not isinstance(data, list):
        raise ValueError(f"{field_name} must be an array")
    
    if len(data) != expected_length:
        raise ValueError(f"{field_name} must have exactly {expected_length} items, got {len(data)}")
    
    return True


def validate_position(position: List[float]) -> bool:
    """Validate 3D position array."""
    return validate_array_length(position, 3, "position")


def validate_color(color: List[float]) -> bool:
    """Validate RGB color array."""
    validate_array_length(color, 3, "color")
    
    for i, value in enumerate(color):
        if not isinstance(value, (int, float)):
            raise ValueError(f"color[{i}] must be a number")
        if not 0 <= value <= 1:
            raise ValueError(f"color[{i}] must be between 0 and 1, got {value}")
    
    return True


def validate_scale(scale: List[float]) -> bool:
    """Validate 3D scale array."""
    validate_array_length(scale, 3, "scale")
    
    for i, value in enumerate(scale):
        if not isinstance(value, (int, float)):
            raise ValueError(f"scale[{i}] must be a number")
        if value < 0.1:
            raise ValueError(f"scale[{i}] must be at least 0.1, got {value}")
    
    return True


def sanitize_schema_for_v1(schema: Dict[str, Any]) -> Dict[str, Any]:
    """
    Remove Pydantic v2-specific constraints from a schema to make it v1 compatible.
    
    Args:
        schema: JSON schema dict that may contain v2-specific constraints
        
    Returns:
        Modified schema with v1-incompatible constraints removed
    """
    # Create a deep copy to avoid modifying original
    import copy
    cleaned_schema = copy.deepcopy(schema)
    
    def clean_recursive(obj):
        if isinstance(obj, dict):
            # Remove v2-specific constraints
            v2_constraints = ['minItems', 'maxItems', 'minLength', 'maxLength']
            for constraint in v2_constraints:
                if constraint in obj:
                    del obj[constraint]
            
            # Recursively clean nested objects
            for value in obj.values():
                clean_recursive(value)
                
        elif isinstance(obj, list):
            for item in obj:
                clean_recursive(item)
    
    clean_recursive(cleaned_schema)
    return cleaned_schema


# Export key functions
__all__ = [
    'detect_pydantic_version',
    'create_compatible_array_schema',
    'create_compatible_position_schema', 
    'create_compatible_color_schema',
    'create_compatible_scale_schema',
    'create_compatible_rotation_schema',
    'validate_array_length',
    'validate_position',
    'validate_color', 
    'validate_scale',
    'sanitize_schema_for_v1'
]


# Module initialization - detect environment
PYDANTIC_VERSION = detect_pydantic_version()
IS_ISAAC_SIM_ENVIRONMENT = PYDANTIC_VERSION == 1

if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO)
    logging.info(f"Detected Pydantic version: {PYDANTIC_VERSION}")
    logging.info(f"Isaac Sim environment: {IS_ISAAC_SIM_ENVIRONMENT}")
    
    # Test schema generation
    pos_schema = create_compatible_position_schema()
    logging.info(f"Position schema: {pos_schema}")
    
    color_schema = create_compatible_color_schema()
    logging.info(f"Color schema: {color_schema}")
