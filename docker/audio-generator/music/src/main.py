"""
Music Generation Service

Standalone microservice for procedural music generation.
Generates dynamic music based on tension, intensity, and genre.
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

app = FastAPI(title="Music Generation Service")


class MusicRequest(BaseModel):
    """Music generation request"""
    tension_level: str = "neutral"
    intensity: float = 0.5
    genre: str = "orchestral"
    tempo: str = "moderate"


async def generate_music(
    tension_level: str,
    intensity: float,
    genre: str,
    tempo: str
) -> np.ndarray:
    """
    Generate procedural music.

    Args:
        tension_level: Tension level (low, neutral, high, climax)
        intensity: Overall intensity (0.0 to 1.0)
        genre: Music genre (orchestral, electronic, ambient, rock)
        tempo: Tempo (slow, moderate, fast)

    Returns:
        np.ndarray: Audio samples (float32, stereo, 48kHz)
    """
    logger.info(f"Generating music: {genre}, tension={tension_level}, intensity={intensity}, tempo={tempo}")

    # Generate 5 seconds of procedural music
    sample_rate = 48000
    duration = 5.0
    num_samples = int(duration * sample_rate)

    t = np.linspace(0, duration, num_samples, dtype=np.float32)

    # Tempo to BPM mapping
    tempo_bpm = {
        "slow": 60,
        "moderate": 100,
        "fast": 140
    }
    bpm = tempo_bpm.get(tempo, 100)
    beat_freq = bpm / 60.0  # Beats per second

    # Tension to harmonic complexity
    tension_harmonics = {
        "low": [1, 2, 3],           # Simple consonant
        "neutral": [1, 2, 3, 4, 5], # Moderate
        "high": [1, 2, 3, 4, 5, 6, 7],  # Complex
        "climax": [1, 2, 3, 4, 5, 6, 7, 8]  # Very complex
    }
    harmonics = tension_harmonics.get(tension_level, [1, 2, 3, 4, 5])

    # Genre base frequency
    genre_freq = {
        "orchestral": 110.0,    # A2 (low strings)
        "electronic": 220.0,    # A3
        "ambient": 55.0,        # A1 (very low)
        "rock": 165.0           # E3 (guitar)
    }
    base_freq = genre_freq.get(genre, 110.0)

    # Initialize stereo output
    left = np.zeros(num_samples, dtype=np.float32)
    right = np.zeros(num_samples, dtype=np.float32)

    # Layer 1: Bassline (fundamental + low harmonics)
    for harmonic in harmonics[:3]:
        freq = base_freq * harmonic
        amplitude = 0.2 / harmonic * intensity
        phase_offset = np.random.uniform(0, 2 * np.pi)
        left += amplitude * np.sin(2 * np.pi * freq * t + phase_offset)
        right += amplitude * np.sin(2 * np.pi * freq * t + phase_offset + 0.1)

    # Layer 2: Melody (higher harmonics with rhythm)
    beat_envelope = np.abs(np.sin(2 * np.pi * beat_freq * t))
    for harmonic in harmonics[2:]:
        freq = base_freq * harmonic
        amplitude = 0.15 / harmonic * intensity
        phase_offset = np.random.uniform(0, 2 * np.pi)
        melody = amplitude * np.sin(2 * np.pi * freq * t + phase_offset) * beat_envelope
        left += melody
        # Slight stereo spread
        right += amplitude * np.sin(2 * np.pi * freq * t + phase_offset + 0.2) * beat_envelope

    # Layer 3: Rhythm/percussion (noise bursts on beats)
    if genre in ["rock", "electronic"]:
        beat_times = np.arange(0, duration, 1.0 / beat_freq)
        for beat_time in beat_times:
            beat_sample = int(beat_time * sample_rate)
            if beat_sample < num_samples - 1000:
                # Kick drum (low frequency burst)
                kick_dur = int(sample_rate * 0.05)
                kick_t = np.linspace(0, 0.05, kick_dur, dtype=np.float32)
                kick = 0.3 * intensity * np.sin(2 * np.pi * 60 * kick_t) * np.exp(-kick_t * 20)
                left[beat_sample:beat_sample + kick_dur] += kick
                right[beat_sample:beat_sample + kick_dur] += kick

                # Hi-hat (noise burst)
                if np.random.random() < 0.7:
                    hat_dur = int(sample_rate * 0.02)
                    hat = 0.05 * intensity * np.random.randn(hat_dur).astype(np.float32)
                    left[beat_sample:beat_sample + hat_dur] += hat
                    right[beat_sample:beat_sample + hat_dur] += hat

    # Layer 4: Genre-specific characteristics
    if genre == "orchestral":
        # Add string-like vibrato
        vibrato_freq = 5.0
        vibrato = 1.0 + 0.02 * np.sin(2 * np.pi * vibrato_freq * t)
        left *= vibrato
        right *= vibrato

    elif genre == "electronic":
        # Add LFO modulation
        lfo_freq = 0.5
        lfo = 1.0 + 0.3 * intensity * np.sin(2 * np.pi * lfo_freq * t)
        left *= lfo
        right *= lfo

    elif genre == "ambient":
        # Reduce rhythmic elements, add reverb-like effect
        from scipy import signal
        b, a = signal.butter(1, 0.1, btype='low')
        left = signal.filtfilt(b, a, left)
        right = signal.filtfilt(b, a, right)

    # Layer 5: Dynamic envelope (fade in/out)
    fade_duration = int(sample_rate * 0.5)
    fade_in = np.linspace(0, 1, fade_duration, dtype=np.float32)
    fade_out = np.linspace(1, 0, fade_duration, dtype=np.float32)

    left[:fade_duration] *= fade_in
    right[:fade_duration] *= fade_in
    left[-fade_duration:] *= fade_out
    right[-fade_duration:] *= fade_out

    # Normalize to prevent clipping
    stereo = np.stack([left, right], axis=-1)
    max_val = np.abs(stereo).max()
    if max_val > 0:
        stereo = stereo / max_val * 0.7

    logger.info(f"Generated {duration}s of {genre} music")

    return stereo


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "music-generation",
        "model": "procedural"
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
            tempo=request.tempo
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
