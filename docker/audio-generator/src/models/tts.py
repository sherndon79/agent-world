"""
Text-to-Speech (TTS) model interface.

Focuses on free/open-source TTS backends:
- pyttsx3: Offline, system TTS (fast, basic quality)
- Coqui TTS: Open-source, neural TTS (good quality, free)
- Kokoro TTS: Native PyTorch pipeline with expressive voice blending
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

VOICE_ALIASES = {
    "default": "af_sarah",
    "narrator_default": "af_sarah",
    "host_enthusiastic": "am_adam"
}


class TTSModel(BaseAudioModel):
    """Text-to-Speech model implementation"""

    def __init__(self, backend: str = "pyttsx3", config: Dict[str, Any] = None):
        """
        Initialize TTS model.

        Args:
            backend: TTS backend (pyttsx3, coqui, kokoro, silero)
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

        elif self.backend == "kokoro":
            # Native PyTorch pipeline with CUDA acceleration
            # Lazy load - pipeline will be initialized on first use
            logger.info("Kokoro TTS backend selected (pipeline loads on first use)")
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
        elif self.backend == "kokoro":
            return await self._generate_kokoro(text, voice, emotion, **kwargs)
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

    async def _generate_kokoro(self, text: str, voice: str, emotion: str, **kwargs) -> np.ndarray:
        """Generate audio using Kokoro's native PyTorch pipeline"""
        import asyncio

        # Initialize Kokoro pipeline if not already done
        if not hasattr(self, 'kokoro'):
            from kokoro import KPipeline
            lang_code = self.config.get('lang_code', 'a') if self.config else 'a'
            self.kokoro = KPipeline(lang_code=lang_code)
            logger.info("Kokoro pipeline loaded")

        # Determine emotion exaggeration (allows override)
        emotion_exaggeration = kwargs.get('emotion_exaggeration')
        if emotion_exaggeration is None:
            emotion_map = {
                'neutral': 0.5,
                'excited': 1.5,
                'mysterious': 1.2,
                'intense': 1.8,
                'calm': 0.3,
                'triumphant': 1.7
            }
            emotion_exaggeration = emotion_map.get(emotion, 1.0)

        loop = asyncio.get_event_loop()
        voices, weights = self._parse_voice_spec(voice)
        speed = kwargs.get('speed', self.config.get('speed', 1.0) if self.config else 1.0)

        def _synthesize():
            import torch

            pipeline = self.kokoro
            cache = getattr(self, '_kokoro_voice_cache', {})
            self._kokoro_voice_cache = cache

            if len(voices) == 1 and weights[0] == 1.0:
                voice_arg = voices[0]
            else:
                blend_key = '|'.join(f"{v}:{weight:.4f}" for v, weight in zip(voices, weights))
                if blend_key not in cache:
                    packs = []
                    for v in voices:
                        if v not in cache:
                            cache[v] = pipeline.load_single_voice(v)
                        packs.append(cache[v])

                    blended_pack = torch.zeros_like(packs[0])
                    for pack, weight in zip(packs, weights):
                        blended_pack += pack * weight

                    cache[blend_key] = blended_pack.detach().cpu().float().contiguous()

                voice_arg = cache[blend_key]

            audio_chunks = []
            for result in pipeline(text, voice=voice_arg, speed=speed):
                if result.audio is not None:
                    audio_chunks.append(result.audio.detach().cpu())

            if not audio_chunks:
                return np.zeros(0, dtype=np.float32), 24000

            audio_tensor = torch.cat(audio_chunks, dim=-1)
            return audio_tensor.numpy(), 24000

        audio, sr = await loop.run_in_executor(None, _synthesize)

        if audio.size == 0:
            return audio.astype(np.float32)

        if not isinstance(audio, np.ndarray):
            audio = np.array(audio, dtype=np.float32)

        if sr == 24000:
            audio = np.repeat(audio, 2)
            sr = 48000
        elif sr != self.sample_rate and sr > 0:
            from scipy import signal
            num_samples = int(len(audio) * self.sample_rate / sr)
            audio = signal.resample(audio, num_samples)
            sr = self.sample_rate

        if len(audio.shape) > 1:
            audio = audio.mean(axis=1)

        logger.info(
            f"Generated {len(audio) / self.sample_rate:.1f}s of Kokoro audio (emotion: {emotion}, exaggeration: {emotion_exaggeration})"
        )
        return audio.astype(np.float32)

    @staticmethod
    def _normalize_voice_name(name: str) -> str:
        if not name:
            return "af_sarah"
        key = name.strip()
        return VOICE_ALIASES.get(key, key)

    @staticmethod
    def _parse_voice_spec(voice_spec: str) -> tuple[list[str], list[float]]:
        """Parse a voice or blend spec (voice:weight) into components and weights"""
        if not voice_spec or ',' not in voice_spec:
            return [TTSModel._normalize_voice_name(voice_spec)], [1.0]

        voices = []
        weights = []
        for component in voice_spec.split(','):
            if ':' in component:
                voice_id, weight = component.split(':')
                voices.append(TTSModel._normalize_voice_name(voice_id))
                weights.append(float(weight.strip()) / 100.0)
            else:
                voices.append(TTSModel._normalize_voice_name(component))
                weights.append(1.0)

        total = sum(weights) or 1.0
        normalized = [w / total for w in weights]
        return voices, normalized

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
