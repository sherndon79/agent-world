"""
Music Generation Service

Standalone microservice for AI music generation using MusicGen small.
Generates dynamic music based on text prompts with tension, intensity, and genre control.
"""

import asyncio
import logging
import tempfile
import os
from typing import Optional
import torch

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

app = FastAPI(title="Music Generation Service")

# Global MusicGen model instance (lazy loaded)
musicgen_model = None


class MusicRequest(BaseModel):
    """Music generation request"""
    tension_level: str = "neutral"
    intensity: float = 0.5
    genre: str = "orchestral"
    tempo: str = "moderate"
    duration: float = 10.0  # Duration in seconds


async def initialize_model():
    """Initialize MusicGen model (lazy load)"""
    global musicgen_model

    if musicgen_model is not None:
        return

    logger.info("Loading MusicGen small model...")

    try:
        from transformers import AutoProcessor, MusicgenForConditionalGeneration

        # Load MusicGen small model with CUDA
        loop = asyncio.get_event_loop()

        def _load():
            processor = AutoProcessor.from_pretrained("facebook/musicgen-small")
            model = MusicgenForConditionalGeneration.from_pretrained("facebook/musicgen-small")

            # Move to GPU if available
            if torch.cuda.is_available():
                model = model.to("cuda")

            return {"processor": processor, "model": model}

        musicgen_model = await loop.run_in_executor(None, _load)

        logger.info("✅ MusicGen small loaded successfully (CUDA)")

    except Exception as e:
        logger.error(f"Failed to load MusicGen model: {e}", exc_info=True)
        raise


def build_music_prompt(
    tension_level: str,
    intensity: float,
    genre: str,
    tempo: str
) -> str:
    """
    Build text prompt for MusicGen based on parameters.

    Args:
        tension_level: Tension level (low, neutral, high, climax)
        intensity: Overall intensity (0.0 to 1.0)
        genre: Music genre
        tempo: Tempo (slow, moderate, fast)

    Returns:
        str: Text prompt for MusicGen
    """
    # Map parameters to descriptive terms
    tension_map = {
        "low": "calm, peaceful, relaxed",
        "neutral": "steady, balanced",
        "high": "tense, dramatic, building",
        "climax": "epic, intense, climactic, powerful"
    }

    intensity_map = {
        0.0: "very subtle, quiet",
        0.3: "gentle, soft",
        0.5: "moderate",
        0.7: "energetic, strong",
        1.0: "very powerful, loud"
    }

    tempo_map = {
        "slow": "slow tempo, 60 bpm",
        "moderate": "moderate tempo, 100 bpm",
        "fast": "fast tempo, 140 bpm"
    }

    # Find closest intensity descriptor
    intensity_desc = min(intensity_map.items(), key=lambda x: abs(x[0] - intensity))[1]

    # Build comprehensive prompt
    tension_desc = tension_map.get(tension_level, "balanced")
    tempo_desc = tempo_map.get(tempo, "moderate tempo")

    prompt = f"{genre} music, {tension_desc}, {intensity_desc}, {tempo_desc}, instrumental, seamless loop"

    return prompt


async def generate_music(
    tension_level: str,
    intensity: float,
    genre: str,
    tempo: str,
    duration: float = 10.0
) -> np.ndarray:
    """
    Generate AI music using MusicGen.

    Args:
        tension_level: Tension level (low, neutral, high, climax)
        intensity: Overall intensity (0.0 to 1.0)
        genre: Music genre (orchestral, electronic, ambient, rock)
        tempo: Tempo (slow, moderate, fast)
        duration: Duration in seconds

    Returns:
        np.ndarray: Audio samples (float32, stereo, 48kHz)
    """
    # Ensure model is loaded
    await initialize_model()

    # Build text prompt
    prompt = build_music_prompt(tension_level, intensity, genre, tempo)
    logger.info(f"Generating music with prompt: '{prompt}' ({duration}s)")

    try:
        processor = musicgen_model["processor"]
        model = musicgen_model["model"]

        # Generate music (blocking call)
        loop = asyncio.get_event_loop()

        def _generate():
            with torch.no_grad():
                # Process text prompt
                inputs = processor(
                    text=[prompt],
                    padding=True,
                    return_tensors="pt"
                )

                # Move inputs to GPU if available
                if torch.cuda.is_available():
                    inputs = {k: v.to("cuda") for k, v in inputs.items()}

                # Calculate max_new_tokens based on duration
                # MusicGen generates 50 tokens per second of audio at 32kHz
                max_new_tokens = int(duration * 50)

                # Generate audio
                audio_values = model.generate(**inputs, max_new_tokens=max_new_tokens)

                # Move to CPU and convert to numpy
                return audio_values.cpu().numpy()

        audio = await loop.run_in_executor(None, _generate)

        # Extract audio: [batch, channels, samples] -> [channels, samples]
        audio = audio[0]  # Remove batch dimension

        # Convert to [samples, channels] or [samples] depending on channel count
        if audio.shape[0] == 1:
            # Mono: [1, samples] -> [samples]
            audio = audio[0]
        else:
            # Multi-channel: [channels, samples] -> [samples, channels]
            audio = audio.T

        # MusicGen outputs 32kHz, resample to 48kHz
        # Simple 1.5x upsampling (32kHz -> 48kHz)
        ratio = 48000 / 32000
        indices = np.arange(0, len(audio), 1/ratio)

        if audio.ndim == 1:
            # Mono audio
            audio_resampled = np.interp(indices, np.arange(len(audio)), audio)
            # Convert to stereo by duplicating
            audio = np.stack([audio_resampled, audio_resampled], axis=-1)
        else:
            # Stereo audio
            audio = np.array([
                np.interp(indices, np.arange(len(audio)), audio[:, 0]),
                np.interp(indices, np.arange(len(audio)), audio[:, 1])
            ]).T

        # Ensure float32
        audio = audio.astype(np.float32)

        logger.info(f"Generated {len(audio) / 48000:.1f}s of {genre} music")

        return audio

    except Exception as e:
        logger.error(f"Music generation failed: {e}", exc_info=True)
        raise


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "music-generation",
        "model": "musicgen-small",
        "model_loaded": musicgen_model is not None
    }


@app.post("/generate")
async def generate(request: MusicRequest):
    """
    Generate music.

    Returns audio as WAV file in response body.
    """
    try:
        # Generate audio
        audio = await generate_music(
            tension_level=request.tension_level,
            intensity=request.intensity,
            genre=request.genre,
            tempo=request.tempo,
            duration=request.duration
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
        logger.error(f"Music generation failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.on_event("startup")
async def startup_event():
    """Initialize on startup"""
    logger.info("🎵 Music Generation Service starting...")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    logger.info("Music Generation Service shutting down...")


if __name__ == "__main__":
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8084,
        log_level="info"
    )
