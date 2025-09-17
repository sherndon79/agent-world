"""
Foundation data types and enums for WorldBuilder scene operations.

Provides core data structures used across all scene building modules.
"""

from typing import Dict, Any, List, Tuple
from dataclasses import dataclass, field
from enum import Enum


class PrimitiveType(Enum):
    """Supported primitive types for scene creation."""
    CUBE = "cube"
    SPHERE = "sphere"
    CYLINDER = "cylinder"
    PLANE = "plane"
    CONE = "cone"


@dataclass
class SceneElement:
    """Represents a single element to be added to the scene."""
    name: str
    primitive_type: PrimitiveType
    position: Tuple[float, float, float] = (0.0, 0.0, 0.0)
    rotation: Tuple[float, float, float] = (0.0, 0.0, 0.0)  # Euler angles in degrees
    scale: Tuple[float, float, float] = (1.0, 1.0, 1.0)
    color: Tuple[float, float, float] = (0.5, 0.5, 0.5)  # RGB 0-1
    parent_path: str = "/World"  # USD parent path for hierarchical placement
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SceneBatch:
    """Represents a batch of elements under a common Xform."""
    batch_name: str
    elements: List[SceneElement] = field(default_factory=list)
    batch_position: Tuple[float, float, float] = (0.0, 0.0, 0.0)
    batch_rotation: Tuple[float, float, float] = (0.0, 0.0, 0.0)
    batch_scale: Tuple[float, float, float] = (1.0, 1.0, 1.0)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AssetPlacement:
    """Represents a USD asset to be placed in the scene via reference."""
    name: str
    asset_path: str  # Path to USD asset file
    prim_path: str   # Target prim path in scene
    position: Tuple[float, float, float] = (0.0, 0.0, 0.0)
    rotation: Tuple[float, float, float] = (0.0, 0.0, 0.0)  # Euler angles in degrees
    scale: Tuple[float, float, float] = (1.0, 1.0, 1.0)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass 
class RequestStatus:
    """Tracks the status of a processing request."""
    request_id: str
    request_type: str  # 'element', 'batch', 'asset', 'removal'
    status: str       # 'queued', 'processing', 'completed', 'failed'
    created_at: float
    completed_at: float = 0.0
    error_message: str = ""
    result: Dict[str, Any] = field(default_factory=dict)


class RequestState(Enum):
    """Valid request states for tracking."""
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class RequestType(Enum):
    """Types of requests that can be processed."""
    ELEMENT = "element"
    BATCH = "batch"
    ASSET = "asset"
    REMOVAL = "removal"
    CLEAR = "clear"