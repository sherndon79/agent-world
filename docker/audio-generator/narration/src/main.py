"""
Narration TTS Service

Standalone microservice for narration text-to-speech using Chatterbox TTS.
Provides HTTP API for generating expressive speech with emotion control.
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

app = FastAPI(title="Narration TTS Service")

# Global model instance (lazy loaded)
chatterbox_model = None


class TTSRequest(BaseModel):
    """TTS generation request"""
    text: str
    voice: str = "default"
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
    """Initialize Kokoro TTS model (lazy load)"""
    global chatterbox_model

    if chatterbox_model is not None:
        return

    logger.info("Loading Kokoro TTS model...")

    try:
        from kokoro_onnx import Kokoro

        # Initialize Kokoro with GPU support (models mounted from host)
        model_path = "/root/.local/share/kokoro/kokoro-v1.0.onnx"
        voices_path = "/root/.local/share/kokoro/voices-v1.0.bin"

        loop = asyncio.get_event_loop()
        chatterbox_model = await loop.run_in_executor(
            None,
            lambda: Kokoro(model_path, voices_path)  # GPU via onnxruntime-gpu
        )

        logger.info("✅ Kokoro TTS model loaded successfully")

    except Exception as e:
        logger.error(f"Failed to load Kokoro TTS model: {e}", exc_info=True)
        raise


async def generate_tts(
    text: str,
    emotion: str = "neutral",
    emotion_exaggeration: Optional[float] = None
) -> np.ndarray:
    """
    Generate TTS audio using Kokoro.

    Args:
        text: Text to synthesize
        emotion: Emotion name (ignored for Kokoro)
        emotion_exaggeration: Custom exaggeration level (ignored for Kokoro)

    Returns:
        np.ndarray: Audio samples (float32, mono, 24kHz)
    """
    # Ensure model is loaded
    await initialize_model()

    logger.info(f"Generating TTS: '{text[:50]}...'")

    try:
        # Generate audio (blocking call)
        loop = asyncio.get_event_loop()

        def _synthesize():
            # Kokoro returns audio samples and sample rate
            return chatterbox_model.create(text, voice="af_sarah", speed=1.0, lang="en-us")

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
        "service": "narration-tts",
        "model": "kokoro",
        "model_loaded": chatterbox_model is not None
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
    logger.info("🎙️ Narration TTS Service starting...")
    # Model will be lazy-loaded on first request


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    logger.info("Narration TTS Service shutting down...")


if __name__ == "__main__":
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8081,
        log_level="info"
    )
