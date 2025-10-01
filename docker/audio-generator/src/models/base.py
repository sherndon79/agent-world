"""
Base audio model interface.

Defines the abstract interface that all audio generation models must implement.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
import numpy as np


class BaseAudioModel(ABC):
    """Abstract base class for audio generation models"""

    def __init__(self, model_name: str, config: Dict[str, Any] = None):
        """
        Initialize base audio model.

        Args:
            model_name: Name/identifier of the model
            config: Model configuration dictionary
        """
        self.model_name = model_name
        self.config = config or {}
        self._initialized = False

    @abstractmethod
    async def initialize(self):
        """Initialize the model (load weights, connect to API, etc.)"""
        pass

    @abstractmethod
    async def generate(self, *args, **kwargs) -> np.ndarray:
        """
        Generate audio.

        Returns:
            np.ndarray: Audio samples (float32, shape depends on model)
        """
        pass

    @abstractmethod
    async def cleanup(self):
        """Cleanup model resources"""
        pass

    def is_initialized(self) -> bool:
        """Check if model is initialized"""
        return self._initialized

    def get_info(self) -> Dict[str, Any]:
        """Get model information"""
        return {
            "model_name": self.model_name,
            "initialized": self._initialized,
            "config": self.config
        }
