"""
Easing functions for smooth cinematic camera movements.

This module provides mathematical easing functions that create natural-looking
motion curves for camera movements. Each function takes a time parameter t
(0.0 to 1.0) and returns an eased value.
"""

import math
from typing import Callable, Dict
from .movement_state import EasingType


class EasingFunctions:
    """Collection of easing functions for smooth animations"""
    
    @staticmethod
    def linear(t: float) -> float:
        """Linear interpolation - constant speed"""
        return t
    
    @staticmethod
    def ease_in(t: float) -> float:
        """Ease in - slow start, accelerating"""
        return t * t
    
    @staticmethod
    def ease_out(t: float) -> float:
        """Ease out - fast start, decelerating"""
        return 1 - (1 - t) * (1 - t)
    
    @staticmethod
    def ease_in_out(t: float) -> float:
        """Ease in/out - slow start and end, fast middle"""
        if t < 0.5:
            return 2 * t * t
        return 1 - pow(-2 * t + 2, 2) / 2
    
    @staticmethod
    def bounce(t: float) -> float:
        """Bounce - simulates bouncing motion at end"""
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
        """Elastic - simulates elastic oscillation"""
        if t == 0 or t == 1:
            return t
        return -(2**(-10 * t)) * math.sin((t - 0.1) * (2 * math.pi) / 0.4) + 1


def get_easing_function(easing_type: EasingType) -> Callable[[float], float]:
    """Get the easing function for a given easing type"""
    return EASING_FUNCTION_MAP.get(easing_type, EasingFunctions.ease_in_out)


def get_easing_function_by_name(easing_name: str) -> Callable[[float], float]:
    """Get easing function by string name"""
    try:
        easing_type = EasingType(easing_name)
        return get_easing_function(easing_type)
    except ValueError:
        # Fallback to ease_in_out for unknown names
        return EasingFunctions.ease_in_out


# Function lookup map for performance
EASING_FUNCTION_MAP: Dict[EasingType, Callable[[float], float]] = {
    EasingType.LINEAR: EasingFunctions.linear,
    EasingType.EASE_IN: EasingFunctions.ease_in,
    EasingType.EASE_OUT: EasingFunctions.ease_out,
    EasingType.EASE_IN_OUT: EasingFunctions.ease_in_out,
    EasingType.BOUNCE: EasingFunctions.bounce,
    EasingType.ELASTIC: EasingFunctions.elastic,
}