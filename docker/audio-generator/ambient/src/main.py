"""
Ambient Audio Service

Standalone microservice for procedural ambient audio generation.
Generates environment soundscapes based on scene parameters.
"""

import asyncio
import logging
import tempfile
import os
from typing import List, Optional

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

app = FastAPI(title="Ambient Audio Service")


class AmbientRequest(BaseModel):
    """Ambient audio generation request"""
    environment: str = "forest"
    time_of_day: str = "day"
    weather: str = "clear"
    special_effects: List[str] = []


async def generate_ambient(
    environment: str,
    time_of_day: str,
    weather: str,
    special_effects: List[str]
) -> np.ndarray:
    """
    Generate procedural ambient audio.

    Args:
        environment: Environment type (forest, city, ocean, etc.)
        time_of_day: Time of day (day, night, dawn, dusk)
        weather: Weather condition (clear, rain, storm, etc.)
        special_effects: Additional effects to layer

    Returns:
        np.ndarray: Audio samples (float32, mono, 48kHz)
    """
    logger.info(f"Generating ambient: {environment}, {time_of_day}, {weather}")

    # Generate 5 seconds of procedural ambient audio
    sample_rate = 48000
    duration = 5.0
    num_samples = int(duration * sample_rate)

    # Base layer: environment-specific tone
    t = np.linspace(0, duration, num_samples, dtype=np.float32)

    # Environment-based frequency ranges
    env_freqs = {
        "forest": (100, 300),      # Birds, rustling
        "city": (200, 500),        # Urban hum
        "ocean": (50, 150),        # Waves, deep sounds
        "cave": (80, 200),         # Reverberant low tones
        "desert": (150, 250),      # Wind, sparse sounds
        "space": (20, 100),        # Eerie low frequencies
    }

    freq_range = env_freqs.get(environment, (100, 300))
    base_freq = np.random.uniform(freq_range[0], freq_range[1])

    # Generate base ambient tone with pink noise characteristics
    audio = np.zeros(num_samples, dtype=np.float32)

    # Layer 1: Low frequency rumble
    audio += 0.1 * np.sin(2 * np.pi * base_freq * t)
    audio += 0.05 * np.sin(2 * np.pi * (base_freq * 1.5) * t)

    # Layer 2: Pink noise (1/f noise)
    white_noise = np.random.randn(num_samples).astype(np.float32)
    from scipy import signal
    b, a = signal.butter(1, 0.1, btype='low')
    pink_noise = signal.filtfilt(b, a, white_noise)
    audio += 0.15 * pink_noise

    # Layer 3: Weather effects
    if weather == "rain":
        # Add rain-like high-frequency noise
        rain_noise = np.random.randn(num_samples).astype(np.float32) * 0.2
        b, a = signal.butter(2, 0.4, btype='high')
        rain = signal.filtfilt(b, a, rain_noise)
        audio += rain

    elif weather == "storm":
        # Rain + occasional thunder
        rain_noise = np.random.randn(num_samples).astype(np.float32) * 0.3
        b, a = signal.butter(2, 0.4, btype='high')
        rain = signal.filtfilt(b, a, rain_noise)
        audio += rain

        # Add thunder rumble
        if np.random.random() < 0.3:
            thunder_start = np.random.randint(0, num_samples - sample_rate)
            thunder_dur = int(sample_rate * 2)
            thunder_t = np.linspace(0, 2, thunder_dur, dtype=np.float32)
            thunder = 0.4 * np.sin(2 * np.pi * 40 * thunder_t) * np.exp(-thunder_t)
            audio[thunder_start:thunder_start + thunder_dur] += thunder

    # Layer 4: Time of day modulation
    if time_of_day == "night":
        # Reduce overall amplitude, add quiet cricket-like chirps
        audio *= 0.5
        chirp_freq = 3000
        chirps = 0.02 * np.sin(2 * np.pi * chirp_freq * t) * (np.random.rand(num_samples) > 0.95)
        audio += chirps.astype(np.float32)

    # Layer 5: Special effects
    for effect in special_effects:
        if effect == "wind":
            wind = 0.15 * np.random.randn(num_samples).astype(np.float32)
            b, a = signal.butter(1, 0.05, btype='low')
            wind = signal.filtfilt(b, a, wind)
            audio += wind
        elif effect == "birds":
            # Random bird chirps
            bird_chirps = np.zeros(num_samples, dtype=np.float32)
            num_chirps = np.random.randint(3, 8)
            for _ in range(num_chirps):
                chirp_start = np.random.randint(0, num_samples - 1000)
                chirp_dur = np.random.randint(100, 500)
                chirp_freq = np.random.uniform(2000, 4000)
                chirp_t = np.linspace(0, chirp_dur / sample_rate, chirp_dur, dtype=np.float32)
                chirp = 0.05 * np.sin(2 * np.pi * chirp_freq * chirp_t)
                bird_chirps[chirp_start:chirp_start + chirp_dur] = chirp
            audio += bird_chirps

    # Normalize to prevent clipping
    max_val = np.abs(audio).max()
    if max_val > 0:
        audio = audio / max_val * 0.7

    logger.info(f"Generated {duration}s of ambient audio")

    return audio


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "ambient-audio",
        "model": "procedural"
    }


@app.post("/generate")
async def generate(request: AmbientRequest):
    """
    Generate ambient audio.

    Returns audio as WAV file in response body.
    """
    try:
        # Generate audio
        audio = await generate_ambient(
            environment=request.environment,
            time_of_day=request.time_of_day,
            weather=request.weather,
            special_effects=request.special_effects
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
        logger.error(f"Ambient generation failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.on_event("startup")
async def startup_event():
    """Initialize on startup"""
    logger.info("🌲 Ambient Audio Service starting...")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    logger.info("Ambient Audio Service shutting down...")


if __name__ == "__main__":
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8083,
        log_level="info"
    )
