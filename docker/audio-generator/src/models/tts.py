"""
Text-to-Speech (TTS) model interface.

Focuses on free/open-source TTS backends:
- pyttsx3: Offline, system TTS (fast, basic quality)
- Coqui TTS: Open-source, neural TTS (good quality, free)
- Silero TTS: Fast, lightweight neural TTS (free)
"""

import logging
from typing import Dict, Any, Optional
import numpy as np
import tempfile
import soundfile as sf
import os

from .base import BaseAudioModel

logger = logging.getLogger(__name__)


class TTSModel(BaseAudioModel):
    """Text-to-Speech model implementation"""

    def __init__(self, backend: str = "pyttsx3", config: Dict[str, Any] = None):
        """
        Initialize TTS model.

        Args:
            backend: TTS backend (pyttsx3, coqui, chatterbox, silero)
            config: Model configuration
        """
        super().__init__(f"tts-{backend}", config)
        self.backend = backend
        self.sample_rate = config.get("sample_rate", 48000) if config else 48000

    async def initialize(self):
        """Initialize TTS model"""
        logger.info(f"Initializing TTS model: {self.backend}")

        if self.backend == "pyttsx3":
            # Fast, offline, basic quality
            import pyttsx3
            self.engine = pyttsx3.init()
            self.engine.setProperty('rate', self.config.get('rate', 150))
            self.engine.setProperty('volume', self.config.get('volume', 0.9))

        elif self.backend == "coqui":
            # Good quality, free, neural TTS
            # Lazy load - model will be initialized on first use
            logger.info("Coqui TTS backend selected (model will load on first use)")
            pass

        elif self.backend == "chatterbox":
            # Best quality, emotion control, MIT licensed
            # Lazy load - model will be initialized on first use
            logger.info("Chatterbox TTS backend selected (model will load on first use)")
            pass

        elif self.backend == "silero":
            # Fast, lightweight neural TTS
            # import torch
            # self.model, _ = torch.hub.load(repo_or_dir='snakers4/silero-models', model='silero_tts')
            logger.info("Silero TTS - will implement when needed")
            pass

        else:
            raise ValueError(f"Unknown TTS backend: {self.backend}")

        self._initialized = True
        logger.info(f"✅ TTS model initialized: {self.backend}")

    async def generate(
        self,
        text: str,
        voice: str = "default",
        emotion: str = "neutral",
        **kwargs
    ) -> np.ndarray:
        """
        Generate speech from text.

        Args:
            text: Text to synthesize
            voice: Voice identifier
            emotion: Emotion/tone (neutral, excited, mysterious, etc.)
            **kwargs: Additional model-specific parameters

        Returns:
            np.ndarray: Audio samples (float32, mono or stereo)
        """
        if not self._initialized:
            await self.initialize()

        logger.info(f"Generating TTS: '{text[:50]}...'")

        if self.backend == "pyttsx3":
            return await self._generate_pyttsx3(text, voice, emotion)
        elif self.backend == "coqui":
            return await self._generate_coqui(text, voice, emotion)
        elif self.backend == "chatterbox":
            return await self._generate_chatterbox(text, voice, emotion, **kwargs)
        elif self.backend == "silero":
            return await self._generate_silero(text, voice, emotion)
        else:
            # Fallback to silence
            duration_seconds = len(text) * 0.05
            num_samples = int(duration_seconds * self.sample_rate)
            return np.zeros(num_samples, dtype=np.float32)

    async def _generate_pyttsx3(self, text: str, voice: str, emotion: str) -> np.ndarray:
        """Generate audio using pyttsx3"""
        import asyncio

        # Create temporary file for audio output
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp:
            tmp_path = tmp.name

        try:
            # Run pyttsx3 in thread pool (it's blocking)
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self._save_pyttsx3, text, tmp_path)

            # Read the generated audio file
            audio, sr = sf.read(tmp_path, dtype='float32')

            # Resample if needed
            if sr != self.sample_rate:
                from scipy import signal
                num_samples = int(len(audio) * self.sample_rate / sr)
                audio = signal.resample(audio, num_samples)

            # Ensure mono
            if len(audio.shape) > 1:
                audio = audio.mean(axis=1)

            logger.info(f"Generated {len(audio) / self.sample_rate:.1f}s of TTS audio")
            return audio.astype(np.float32)

        finally:
            # Clean up temp file
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    def _save_pyttsx3(self, text: str, output_path: str):
        """Save pyttsx3 audio to file (blocking call)"""
        self.engine.save_to_file(text, output_path)
        self.engine.runAndWait()

    async def _generate_coqui(self, text: str, voice: str, emotion: str) -> np.ndarray:
        """Generate audio using Coqui TTS (XTTS-v2)"""
        import asyncio
        from TTS.api import TTS

        # Initialize Coqui TTS if not already done
        if not hasattr(self, 'tts'):
            # Use XTTS-v2 for high-quality, expressive, multi-speaker synthesis
            self.tts = TTS(model_name="tts_models/multilingual/multi-dataset/xtts_v2", gpu=True)
            logger.info("Coqui XTTS-v2 model loaded")

        # Create temporary file for audio output
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp:
            tmp_path = tmp.name

        try:
            # XTTS-v2 supports emotion through text and speaker variation
            # For now, use default English speaker
            # TODO: Add voice cloning from reference audio files
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: self.tts.tts_to_file(
                    text=text,
                    file_path=tmp_path,
                    language="en"
                )
            )

            # Read the generated audio file
            audio, sr = sf.read(tmp_path, dtype='float32')

            # Resample if needed
            if sr != self.sample_rate:
                from scipy import signal
                num_samples = int(len(audio) * self.sample_rate / sr)
                audio = signal.resample(audio, num_samples)

            # Ensure mono
            if len(audio.shape) > 1:
                audio = audio.mean(axis=1)

            logger.info(f"Generated {len(audio) / self.sample_rate:.1f}s of XTTS-v2 audio")
            return audio.astype(np.float32)

        finally:
            # Clean up temp file
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    async def _generate_chatterbox(self, text: str, voice: str, emotion: str, **kwargs) -> np.ndarray:
        """Generate audio using Chatterbox TTS with emotion control"""
        import asyncio
        import torch

        # Initialize Chatterbox TTS if not already done
        if not hasattr(self, 'chatterbox'):
            from chatterbox import ChatterboxTTS
            self.chatterbox = ChatterboxTTS()
            logger.info("Chatterbox model loaded")

        # Create temporary file for audio output
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp:
            tmp_path = tmp.name

        try:
            # Chatterbox parameters
            # emotion_exaggeration: 0.0 (flat) to 2.0 (very expressive), default 1.0
            emotion_exaggeration = kwargs.get('emotion_exaggeration', 1.0)

            # Map emotion names to exaggeration levels
            emotion_map = {
                'neutral': 0.5,
                'excited': 1.5,
                'mysterious': 1.2,
                'intense': 1.8,
                'calm': 0.3,
                'triumphant': 1.7
            }

            if emotion in emotion_map:
                emotion_exaggeration = emotion_map[emotion]

            # Run TTS in thread pool (blocking call)
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: self.chatterbox.tts(
                    text=text,
                    output_path=tmp_path,
                    emotion_exaggeration=emotion_exaggeration
                )
            )

            # Read the generated audio file
            audio, sr = sf.read(tmp_path, dtype='float32')

            # Resample if needed
            if sr != self.sample_rate:
                from scipy import signal
                num_samples = int(len(audio) * self.sample_rate / sr)
                audio = signal.resample(audio, num_samples)

            # Ensure mono
            if len(audio.shape) > 1:
                audio = audio.mean(axis=1)

            logger.info(f"Generated {len(audio) / self.sample_rate:.1f}s of Chatterbox TTS audio (emotion: {emotion}, exaggeration: {emotion_exaggeration})")
            return audio.astype(np.float32)

        finally:
            # Clean up temp file
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    async def _generate_silero(self, text: str, voice: str, emotion: str) -> np.ndarray:
        """Generate audio using Silero TTS (placeholder)"""
        logger.warning("Silero TTS not yet implemented, returning silence")
        duration_seconds = len(text) * 0.05
        num_samples = int(duration_seconds * self.sample_rate)
        return np.zeros(num_samples, dtype=np.float32)

    async def cleanup(self):
        """Cleanup TTS model resources"""
        logger.info(f"Cleaning up TTS model: {self.backend}")

        if self.backend == "pyttsx3" and hasattr(self, 'engine'):
            self.engine.stop()

        self._initialized = False
