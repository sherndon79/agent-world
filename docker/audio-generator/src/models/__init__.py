"""
AI Model interfaces for audio generation.

This module provides abstract base classes and implementations
for TTS, ambient audio, and music generation models.
"""

from .base import BaseAudioModel
from .tts import TTSModel
from .ambient import AmbientAudioModel
from .music import MusicGenerationModel

__all__ = [
    'BaseAudioModel',
    'TTSModel',
    'AmbientAudioModel',
    'MusicGenerationModel'
]
