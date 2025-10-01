"""
AI Model interfaces for audio generation.

This module provides abstract base classes and implementations
for TTS, ambient audio, and music generation models.
"""

from .base import BaseAudioModel
from .tts import TTSModel
from .ambient import AmbientModel
from .music import MusicModel

__all__ = [
    'BaseAudioModel',
    'TTSModel',
    'AmbientModel',
    'MusicModel'
]
