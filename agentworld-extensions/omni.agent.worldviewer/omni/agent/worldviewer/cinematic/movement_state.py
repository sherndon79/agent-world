"""
Movement state data structures for cinematic camera control.

This module contains all the data structures used by the cinematic controller:
- EasingType: Easing function enumeration
- ShotType: Cinematic shot classifications  
- FramingStyle: Camera framing composition styles
- MovementState: Active movement state tracking
"""

from enum import Enum
from dataclasses import dataclass
from typing import Dict, List, Optional, Callable


class EasingType(Enum):
    """Easing function types for smooth movement"""
    LINEAR = "linear"
    EASE_IN = "ease_in"
    EASE_OUT = "ease_out"
    EASE_IN_OUT = "ease_in_out"
    BOUNCE = "bounce"
    ELASTIC = "elastic"


class ShotType(Enum):
    """Cinematic shot type classifications"""
    CLOSE_UP = "close_up"
    MEDIUM = "medium"
    WIDE = "wide"
    ESTABLISHING = "establishing"
    EXTREME_WIDE = "extreme_wide"


class FramingStyle(Enum):
    """Camera framing composition styles"""
    CENTER = "center"
    RULE_OF_THIRDS_LEFT = "rule_of_thirds_left"
    RULE_OF_THIRDS_RIGHT = "rule_of_thirds_right"
    LOW_ANGLE = "low_angle"
    HIGH_ANGLE = "high_angle"


@dataclass
class MovementState:
    """State of an active movement"""
    movement_id: str
    operation: str
    start_time: float
    duration: float
    keyframes: List[Dict]
    current_frame: int
    status: str
    params: Dict
    # Additional fields that may be used by the controller
    execution_mode: str = "auto"
    is_active: bool = False
    total_frames: Optional[int] = None
    camera_controller: Optional[object] = None
    completion_callback: Optional[Callable] = None
    manual_control: bool = False

