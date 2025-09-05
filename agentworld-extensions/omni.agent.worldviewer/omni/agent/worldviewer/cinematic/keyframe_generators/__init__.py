"""
Keyframe generators package for WorldViewer cinematic camera movements.

This package contains modular keyframe generators for different shot types:
- BaseKeyframeGenerator: Abstract base class with common functionality
- SmoothMoveGenerator: Linear smooth movements
- ArcShotGenerator: Curved Bezier path movements
- OrbitShotGenerator: Basic orbital movements
- CinematicOrbitGenerator: Advanced cinematic orbital movements  
- DollyShotGenerator: Dolly movements with style variations
- PanTiltGenerator: Rotation-based movements

Usage:
    from keyframe_generators import KeyframeGeneratorFactory
    
    factory = KeyframeGeneratorFactory(camera_controller)
    keyframes = factory.generate_keyframes('smooth_move', params)
"""

from .base_generator import BaseKeyframeGenerator, KeyframeGeneratorFactory

# Individual generators will be imported by the factory to avoid circular imports
# from .smooth_move import SmoothMoveGenerator
# from .arc_shot import ArcShotGenerator
# from .orbit_shot import OrbitShotGenerator, CinematicOrbitGenerator
# from .dolly_shot import DollyShotGenerator
# from .pan_tilt import PanTiltGenerator

__all__ = [
    'BaseKeyframeGenerator',
    'KeyframeGeneratorFactory',
    # Individual generators available via factory
    # 'SmoothMoveGenerator',
    # 'ArcShotGenerator', 
    # 'OrbitShotGenerator',
    # 'CinematicOrbitGenerator',
    # 'DollyShotGenerator',
    # 'PanTiltGenerator'
]

__version__ = '1.0.0'