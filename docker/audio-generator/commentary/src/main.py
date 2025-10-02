"""
Commentary TTS Service

Standalone microservice for commentary text-to-speech using Kokoro's native
PyTorch pipeline (KPipeline). Provides HTTP API for generating expressive
speech with optional multi-voice blending.
"""

import asyncio
import logging
import tempfile
import os
from typing import Optional

import numpy as np
import soundfile as sf
from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
import uvicorn

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(title="Commentary TTS Service")

# Global Kokoro pipeline instance (lazy loaded)
kokoro_pipeline = None
# Cache for precomputed voice embeddings when blending
voice_embed_cache = {}

# Friendly aliases for legacy voice identifiers
VOICE_ALIASES = {
    "default": "af_sarah",
    "narrator_default": "af_sarah",
    "host_enthusiastic": "am_adam"
}


class TTSRequest(BaseModel):
    """TTS generation request"""
    text: str
    voice: str = "af_sarah"  # Single voice or blend (e.g., "af_sarah:60,am_adam:40")
    emotion: str = "neutral"
    emotion_exaggeration: Optional[float] = None


class TTSResponse(BaseModel):
    """TTS generation response"""
    success: bool
    duration_seconds: float
    sample_rate: int
    samples: int
    message: Optional[str] = None


def get_emotion_exaggeration(emotion: str, custom_value: Optional[float] = None) -> float:
    """
    Map emotion name to exaggeration level.

    Args:
        emotion: Emotion name
        custom_value: Custom exaggeration override

    Returns:
        float: Exaggeration level (0.0 to 2.0)
    """
    if custom_value is not None:
        return max(0.0, min(2.0, custom_value))

    emotion_map = {
        'neutral': 0.5,
        'excited': 1.5,
        'mysterious': 1.2,
        'intense': 1.8,
        'calm': 0.3,
        'triumphant': 1.7
    }

    return emotion_map.get(emotion, 1.0)


async def initialize_model():
    """Initialize Kokoro TTS pipeline (lazy load)"""
    global kokoro_pipeline

    if kokoro_pipeline is not None:
        return

    logger.info("Loading Kokoro native pipeline (PyTorch)...")

    try:
        from kokoro import KPipeline

        # Initialize Kokoro with CUDA support
        loop = asyncio.get_event_loop()
        kokoro_pipeline = await loop.run_in_executor(
            None,
            lambda: KPipeline(lang_code='a')  # 'a' for American English
        )

        logger.info("✅ Kokoro pipeline loaded successfully (PyTorch + CUDA)")

    except Exception as e:
        logger.error(f"Failed to load Kokoro pipeline: {e}", exc_info=True)
        raise


def normalize_voice_name(name: str) -> str:
    """Normalize voice identifiers to Kokoro voice names"""
    if not name:
        return "af_sarah"
    key = name.strip()
    return VOICE_ALIASES.get(key, key)


def parse_voice_blend(voice_spec: str) -> tuple:
    """
    Parse voice specification into blend components.

    Supports:
    - Single voice: "af_sarah"
    - Voice blend: "af_sarah:60,am_adam:40" (weights as percentages)

    Returns:
        tuple: (voices, weights) where weights sum to 1.0
    """
    if ',' not in voice_spec:
        # Single voice
        return ([normalize_voice_name(voice_spec)], [1.0])

    # Parse blend specification
    voices = []
    weights = []

    for component in voice_spec.split(','):
        if ':' in component:
            voice, weight = component.split(':')
            voices.append(normalize_voice_name(voice))
            weights.append(float(weight.strip()) / 100.0)  # Convert percentage to 0-1
        else:
            voices.append(normalize_voice_name(component))
            weights.append(1.0)

    # Normalize weights to sum to 1.0
    total = sum(weights)
    weights = [w / total for w in weights]

    return (voices, weights)


async def generate_tts(
    text: str,
    voice: str = "af_sarah",
    emotion: str = "neutral",
    emotion_exaggeration: Optional[float] = None
) -> np.ndarray:
    """
    Generate TTS audio using Kokoro with optional voice blending.

    Args:
        text: Text to synthesize
        voice: Voice name or blend spec (e.g., "af_sarah:60,am_adam:40")
        emotion: Emotion name (ignored for now)
        emotion_exaggeration: Custom exaggeration level (ignored for now)

    Returns:
        np.ndarray: Audio samples (float32, mono, 24kHz)
    """
    # Ensure model is loaded
    await initialize_model()

    logger.info(f"Generating TTS: '{text[:50]}...' with voice: {voice}")

    try:
        # Parse voice specification
        voices, weights = parse_voice_blend(voice)

        # Generate audio (blocking call)
        loop = asyncio.get_event_loop()

        def _synthesize():
            import torch

            if len(voices) == 1 and weights[0] == 1.0:
                voice_arg = voices[0]
            else:
                blend_key = '|'.join(f"{v}:{weight:.4f}" for v, weight in zip(voices, weights))
                if blend_key not in voice_embed_cache:
                    packs = []
                    for v in voices:
                        if v not in voice_embed_cache:
                            voice_embed_cache[v] = kokoro_pipeline.load_single_voice(v)
                        packs.append(voice_embed_cache[v])

                    blended_pack = torch.zeros_like(packs[0])
                    for pack, weight in zip(packs, weights):
                        blended_pack += pack * weight

                    voice_embed_cache[blend_key] = blended_pack.detach().cpu().float().contiguous()

                voice_arg = voice_embed_cache[blend_key]

            audio_chunks = []
            for result in kokoro_pipeline(text, voice=voice_arg, speed=1.0):
                if result.audio is not None:
                    audio_chunks.append(result.audio.detach().cpu())

            if not audio_chunks:
                return np.zeros(0, dtype=np.float32), 24000

            audio_tensor = torch.cat(audio_chunks, dim=-1)
            return audio_tensor.numpy(), 24000

        audio, sr = await loop.run_in_executor(None, _synthesize)

        # Convert to numpy if needed
        if not isinstance(audio, np.ndarray):
            audio = np.array(audio, dtype=np.float32)

        # Resample to 48kHz if needed (Kokoro outputs 24kHz = exactly 2x upsampling)
        if sr == 24000:
            # Simple 2x upsampling using linear interpolation (scipy-free)
            audio = np.repeat(audio, 2)
        elif sr != 48000:
            # For other sample rates, use ratio-based resampling
            ratio = 48000 / sr
            indices = np.arange(0, len(audio), 1/ratio)
            audio = np.interp(indices, np.arange(len(audio)), audio)

        # Ensure mono
        if len(audio.shape) > 1:
            audio = audio.mean(axis=1)

        logger.info(f"Generated {len(audio) / 48000:.1f}s of audio")

        return audio.astype(np.float32)

    except Exception as e:
        logger.error(f"TTS generation failed: {e}", exc_info=True)
        raise


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "commentary-tts",
        "model": "kokoro",
        "model_loaded": kokoro_pipeline is not None
    }


@app.get("/voices")
async def list_voices():
    """
    List all available voices.

    Returns:
        List of voice names and their descriptions
    """
    # Ensure model is loaded to get voice list
    await initialize_model()

    # Get available voices from Kokoro
    try:
        loop = asyncio.get_event_loop()
        voices = await loop.run_in_executor(
            None,
            lambda: kokoro_pipeline.get_voices()
        )

        return {
            "voices": voices,
            "total": len(voices),
            "blend_syntax": "voice1:weight1,voice2:weight2 (e.g., af_sarah:60,am_adam:40)"
        }
    except Exception as e:
        logger.error(f"Failed to get voices: {e}", exc_info=True)
        return {
            "voices": ["af_sarah", "am_adam"],  # Fallback
            "total": 2,
            "error": str(e)
        }


@app.post("/generate", response_model=TTSResponse)
async def generate(request: TTSRequest):
    """
    Generate TTS audio.

    Returns audio as WAV file in response body.
    """
    try:
        # Generate audio
        audio = await generate_tts(
            text=request.text,
            voice=request.voice,
            emotion=request.emotion,
            emotion_exaggeration=request.emotion_exaggeration
        )

        # Convert to WAV bytes
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp:
            tmp_path = tmp.name

        try:
            sf.write(tmp_path, audio, 48000, format='WAV')

            with open(tmp_path, 'rb') as f:
                wav_bytes = f.read()

            return Response(
                content=wav_bytes,
                media_type="audio/wav",
                headers={
                    "X-Duration": str(len(audio) / 48000),
                    "X-Samples": str(len(audio)),
                    "X-Sample-Rate": "48000"
                }
            )

        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    except Exception as e:
        logger.error(f"TTS generation failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.on_event("startup")
async def startup_event():
    """Initialize on startup"""
    logger.info("🎙️ Commentary TTS Service starting...")
    # Model will be lazy-loaded on first request


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    logger.info("Commentary TTS Service shutting down...")


if __name__ == "__main__":
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8082,
        log_level="info"
    )
