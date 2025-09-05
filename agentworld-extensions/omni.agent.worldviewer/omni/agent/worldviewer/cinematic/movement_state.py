"""
Movement state data structures for cinematic camera control.
"""

import math
from enum import Enum
from dataclasses import dataclass
from typing import Dict, List


class EasingType(Enum):
    """Easing function types for smooth movement"""
    LINEAR = "linear"
    EASE_IN = "ease_in"
    EASE_OUT = "ease_out"
    EASE_IN_OUT = "ease_in_out"
    BOUNCE = "bounce"
    ELASTIC = "elastic"


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


class EasingFunctions:
    """Collection of easing functions for smooth animations"""
    
    @staticmethod
    def linear(t: float) -> float:
        return t
    
    @staticmethod
    def ease_in(t: float) -> float:
        return t * t
    
    @staticmethod
    def ease_out(t: float) -> float:
        return 1 - (1 - t) * (1 - t)
    
    @staticmethod
    def ease_in_out(t: float) -> float:
        if t < 0.5:
            return 2 * t * t
        return 1 - pow(-2 * t + 2, 2) / 2
    
    @staticmethod
    def bounce(t: float) -> float:
        if t < 1/2.75:
            return 7.5625 * t * t
        elif t < 2/2.75:
            t -= 1.5/2.75
            return 7.5625 * t * t + 0.75
        elif t < 2.5/2.75:
            t -= 2.25/2.75
            return 7.5625 * t * t + 0.9375
        else:
            t -= 2.625/2.75
            return 7.5625 * t * t + 0.984375
    
    @staticmethod
    def elastic(t: float) -> float:
        if t == 0 or t == 1:
            return t
        return -(2**(-10 * t)) * math.sin((t - 0.1) * (2 * math.pi) / 0.4) + 1


def get_easing_function(easing_type: EasingType) -> callable:
    """Get the easing function for a given easing type"""
    easing_map = {
        EasingType.LINEAR: EasingFunctions.linear,
        EasingType.EASE_IN: EasingFunctions.ease_in,
        EasingType.EASE_OUT: EasingFunctions.ease_out,
        EasingType.EASE_IN_OUT: EasingFunctions.ease_in_out,
        EasingType.BOUNCE: EasingFunctions.bounce,
        EasingType.ELASTIC: EasingFunctions.elastic,
    }
    return easing_map.get(easing_type, EasingFunctions.ease_in_out)