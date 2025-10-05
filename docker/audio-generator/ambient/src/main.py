"""
Ambient Audio Service

Standalone microservice for procedural ambient audio generation.
Generates environment soundscapes based on scene parameters.
Also provides access to ambient sample libraries.
"""

import asyncio
import logging
import tempfile
import os
import json
from pathlib import Path
from typing import List, Optional, Dict, Any

import numpy as np
import soundfile as sf
from fastapi import FastAPI, HTTPException, Query
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

# Library configuration
LIBRARY_ROOT = Path("/app/assets/ambient/library")
library_cache: Dict[str, Dict[str, Any]] = {}


class AmbientRequest(BaseModel):
    """Ambient audio generation request"""
    environment: str = "forest"
    time_of_day: str = "day"
    weather: str = "clear"
    special_effects: List[str] = []


class AmbientSampleRequest(BaseModel):
    """Request to play a specific ambient sample from library"""
    sample_id: str  # e.g., "sonniss2024/forest/forest_001.wav"
    fade_out_after: float  # REQUIRED: Seconds after which to fade out (based on narration/music duration)
    fade_duration: float = 3.0  # Fade out duration in seconds
    loop_if_short: bool = False  # If sample is shorter than fade_out_after, loop it


def load_library_manifests():
    """Load all ambient library manifests into memory"""
    global library_cache

    if not LIBRARY_ROOT.exists():
        logger.warning(f"Library root not found: {LIBRARY_ROOT}")
        return

    for pack_dir in LIBRARY_ROOT.iterdir():
        if not pack_dir.is_dir():
            continue

        manifest_path = pack_dir / "manifest.json"
        if not manifest_path.exists():
            logger.warning(f"No manifest found for pack: {pack_dir.name}")
            continue

        try:
            with open(manifest_path, 'r') as f:
                manifest = json.load(f)

            # Support both array and object formats
            clips = manifest if isinstance(manifest, list) else manifest.get('clips', [])

            # Build indexes for fast lookup
            by_category = {}
            tags_set = set()

            for clip in clips:
                category = clip.get('category', 'misc')
                if category not in by_category:
                    by_category[category] = []
                by_category[category].append(clip)

                for tag in clip.get('tags', []):
                    tags_set.add(tag)

            library_cache[pack_dir.name] = {
                'name': pack_dir.name,
                'slug': pack_dir.name,
                'manifest_path': str(manifest_path),
                'clips': clips,
                'categories': list(by_category.keys()),
                'category_map': by_category,
                'tags': sorted(list(tags_set))
            }

            logger.info(f"Loaded ambient pack: {pack_dir.name} ({len(clips)} clips, {len(by_category)} categories)")

        except Exception as e:
            logger.error(f"Failed to load manifest for {pack_dir.name}: {e}")


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
        "space": (40, 80),         # Spaceship engine hum
    }

    freq_range = env_freqs.get(environment, (100, 300))
    base_freq = np.random.uniform(freq_range[0], freq_range[1])

    # Generate base ambient tone with pink noise characteristics
    audio = np.zeros(num_samples, dtype=np.float32)

    # Special handling for space environment
    if environment == "space":
        # Layer 1: Deep engine hum (40-60 Hz range)
        engine_freq = 50.0  # Deep engine rumble
        audio += 0.12 * np.sin(2 * np.pi * engine_freq * t)
        audio += 0.06 * np.sin(2 * np.pi * (engine_freq * 1.5) * t)

        # Layer 2: Electrical hum (120 Hz - common electrical frequency)
        electrical_hum = 0.04 * np.sin(2 * np.pi * 120 * t)
        audio += electrical_hum

        # Layer 3: Subtle higher harmonics for spaceship systems
        audio += 0.03 * np.sin(2 * np.pi * 240 * t)
        audio += 0.02 * np.sin(2 * np.pi * 180 * t)

        # Layer 4: Very low pink noise for air circulation/life support
        white_noise = np.random.randn(num_samples).astype(np.float32)
        from scipy import signal
        b, a = signal.butter(2, 0.05, btype='low')
        air_noise = signal.filtfilt(b, a, white_noise)
        audio += 0.08 * air_noise
    else:
        # Layer 1: Low frequency rumble for other environments
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


def apply_fade_out(audio: np.ndarray, fade_duration: float, sample_rate: int = 48000) -> np.ndarray:
    """
    Apply fade out to audio.

    Args:
        audio: Audio samples (stereo or mono)
        fade_duration: Fade duration in seconds
        sample_rate: Sample rate in Hz

    Returns:
        np.ndarray: Audio with fade out applied
    """
    fade_samples = int(fade_duration * sample_rate)

    if fade_samples >= len(audio):
        # If fade is longer than audio, fade entire clip
        fade_samples = len(audio)

    # Create fade curve
    fade_curve = np.linspace(1.0, 0.0, fade_samples)

    # Apply fade (works for both mono and stereo)
    result = audio.copy()
    if audio.ndim == 1:  # Mono
        result[-fade_samples:] *= fade_curve
    else:  # Stereo
        result[-fade_samples:, :] *= fade_curve[:, np.newaxis]

    return result


@app.post("/play_sample")
async def play_sample(request: AmbientSampleRequest):
    """
    Play a specific ambient sample from the library.

    Supports:
    - Automatic fade-out after specified duration
    - Maximum duration limiting
    - Intelligent fade timing based on narration/music sync

    Returns audio as WAV file in response body.
    """
    try:
        # Parse sample ID to find the file
        sample_id = request.sample_id
        parts = sample_id.split('/')
        if len(parts) < 2:
            raise HTTPException(status_code=400, detail="Invalid sample_id format. Expected: 'pack_name/category/filename.wav'")

        pack_name = parts[0]
        relative_path = '/'.join(parts[1:])

        # Find the sample file
        sample_path = LIBRARY_ROOT / pack_name / relative_path

        if not sample_path.exists():
            raise HTTPException(status_code=404, detail=f"Sample not found: {sample_id}")

        logger.info(f"Playing ambient sample: {sample_id}")

        # Load the audio file
        audio_data, sample_rate = sf.read(str(sample_path), dtype='float32')

        # Get original duration
        original_duration = len(audio_data) / sample_rate
        logger.info(f"Loaded sample: {original_duration:.2f}s @ {sample_rate}Hz, channels: {audio_data.shape if audio_data.ndim > 1 else 'mono'}")

        # Determine target duration (fade_out_after + fade_duration)
        fade_duration = request.fade_duration
        fade_out_after = request.fade_out_after
        target_duration = fade_out_after + fade_duration

        logger.info(f"Original: {original_duration:.2f}s, Target: {target_duration:.2f}s (fade at {fade_out_after:.2f}s)")

        # Handle samples that are too short - loop with crossfading for seamless transitions
        if original_duration < target_duration:
            # Loop the sample to reach the target duration (fade_out_after + fade_duration)
            times_to_loop = int(np.ceil(target_duration / original_duration)) + 1

            # Use crossfade looping for seamless transitions
            crossfade_duration = 0.1  # 100ms crossfade at loop points
            crossfade_samples = int(crossfade_duration * sample_rate)

            # Build looped audio with crossfades
            looped_parts = []
            for i in range(times_to_loop):
                if i == 0:
                    # First iteration - full sample
                    looped_parts.append(audio_data)
                else:
                    # Subsequent iterations - crossfade with previous end
                    if crossfade_samples > 0 and len(looped_parts[-1]) >= crossfade_samples:
                        # Extract crossfade regions
                        prev_end = looped_parts[-1][-crossfade_samples:]
                        curr_start = audio_data[:crossfade_samples] if len(audio_data) > crossfade_samples else audio_data

                        # Create crossfade
                        fade_out = np.linspace(1.0, 0.0, len(prev_end))
                        fade_in = np.linspace(0.0, 1.0, len(curr_start))

                        if audio_data.ndim == 1:  # Mono
                            crossfaded = prev_end * fade_out + curr_start * fade_in
                        else:  # Stereo
                            crossfaded = prev_end * fade_out[:, np.newaxis] + curr_start * fade_in[:, np.newaxis]

                        # Replace end of previous part with crossfade, append rest of current
                        looped_parts[-1] = looped_parts[-1][:-crossfade_samples]
                        looped_parts.append(crossfaded)
                        if len(audio_data) > crossfade_samples:
                            looped_parts.append(audio_data[crossfade_samples:])
                    else:
                        looped_parts.append(audio_data)

            # Concatenate all parts
            if audio_data.ndim == 1:
                audio_data = np.concatenate(looped_parts)
            else:
                audio_data = np.vstack(looped_parts)

            logger.info(f"Looped sample {times_to_loop}x with crossfading to reach target duration ({original_duration:.2f}s -> {len(audio_data)/sample_rate:.2f}s)")

        # Trim to exact target duration
        target_samples = int(target_duration * sample_rate)
        if len(audio_data) > target_samples:
            audio_data = audio_data[:target_samples]
            logger.info(f"Trimmed to exact target duration: {target_duration:.2f}s")

        # Apply fade-out at the specified time
        fade_start_sample = int(fade_out_after * sample_rate)

        if fade_start_sample < len(audio_data):
            # Create fade region
            fade_region_start = fade_start_sample
            fade_region_end = min(len(audio_data), fade_start_sample + int(fade_duration * sample_rate))
            fade_samples = fade_region_end - fade_region_start

            if fade_samples > 0:
                fade_curve = np.linspace(1.0, 0.0, fade_samples)

                if audio_data.ndim == 1:  # Mono
                    audio_data[fade_region_start:fade_region_end] *= fade_curve
                else:  # Stereo
                    audio_data[fade_region_start:fade_region_end, :] *= fade_curve[:, np.newaxis]

                logger.info(f"Applied {fade_duration:.2f}s fade-out starting at {fade_out_after:.2f}s")

        # Resample to 48kHz if needed (for consistency with other services)
        if sample_rate != 48000:
            import scipy.signal as signal
            num_samples = int(len(audio_data) * 48000 / sample_rate)
            if audio_data.ndim == 1:
                audio_data = signal.resample(audio_data, num_samples)
            else:
                audio_data = signal.resample(audio_data, num_samples, axis=0)
            sample_rate = 48000
            logger.info(f"Resampled to 48kHz")

        # Ensure stereo output (match other services)
        if audio_data.ndim == 1:
            audio_data = np.column_stack([audio_data, audio_data])

        # Peak normalization with soft limiting
        # Normalize peaks to -12dB (0.251 linear) for headroom while preserving dynamics
        current_peak = np.max(np.abs(audio_data))
        target_peak = 0.251  # -12dB headroom

        if current_peak > 0:
            # Peak normalize
            normalization_factor = target_peak / current_peak
            audio_data = audio_data * normalization_factor

            # Soft limiting for any peaks above threshold (gentle compression)
            threshold = 0.8  # Start soft limiting at -1.94dB
            above_threshold = np.abs(audio_data) > threshold
            if np.any(above_threshold):
                # Apply soft knee compression above threshold
                excess = np.abs(audio_data) - threshold
                compressed_excess = excess * 0.3  # Compress excess by 70%
                audio_data = np.where(
                    above_threshold,
                    np.sign(audio_data) * (threshold + compressed_excess),
                    audio_data
                )

            final_peak = np.max(np.abs(audio_data))
            logger.info(f"Peak normalized: {current_peak:.4f} -> {final_peak:.4f} (factor: {normalization_factor:.2f}x)")

        # Convert to WAV bytes
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp:
            tmp_path = tmp.name

        try:
            sf.write(tmp_path, audio_data, sample_rate, format='WAV', subtype='PCM_16')

            with open(tmp_path, 'rb') as f:
                wav_bytes = f.read()

            final_duration = len(audio_data) / sample_rate

            return Response(
                content=wav_bytes,
                media_type="audio/wav",
                headers={
                    "X-Duration": str(final_duration),
                    "X-Samples": str(len(audio_data)),
                    "X-Sample-Rate": str(sample_rate),
                    "X-Original-Duration": str(original_duration),
                    "X-Sample-ID": sample_id
                }
            )

        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Sample playback failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/library/packs")
async def list_packs():
    """
    List all available ambient library packs.

    Returns summary information about each pack including clip count,
    categories, and available tags.
    """
    return [
        {
            'name': pack['name'],
            'slug': pack['slug'],
            'clipCount': len(pack['clips']),
            'categories': pack['categories'],
            'tags': pack['tags']
        }
        for pack in library_cache.values()
    ]


@app.get("/library/packs/{pack_name}")
async def get_pack(pack_name: str):
    """
    Get detailed information about a specific pack.

    Returns the pack metadata including all clips.
    """
    if pack_name not in library_cache:
        raise HTTPException(status_code=404, detail=f"Pack not found: {pack_name}")

    return library_cache[pack_name]


@app.get("/library/packs/{pack_name}/categories")
async def list_pack_categories(pack_name: str):
    """List all categories available in a specific pack"""
    if pack_name not in library_cache:
        raise HTTPException(status_code=404, detail=f"Pack not found: {pack_name}")

    return library_cache[pack_name]['categories']


@app.get("/library/clips")
async def find_clips(
    pack: str = Query(..., description="Pack name to search in"),
    category: Optional[str] = Query(None, description="Filter by category"),
    tags: Optional[str] = Query(None, description="Comma-separated tags to filter by"),
    limit: int = Query(20, ge=1, le=100, description="Maximum number of results"),
    max_duration: Optional[float] = Query(None, ge=0, description="Maximum clip duration in seconds"),
    include_metadata: bool = Query(False, description="Include full metadata")
):
    """
    Search for clips in a library pack.

    Supports filtering by category, tags, and duration.
    Agent-adventures can use this to find appropriate ambient samples.
    """
    if pack not in library_cache:
        raise HTTPException(status_code=404, detail=f"Pack not found: {pack}")

    pack_data = library_cache[pack]
    candidates = pack_data['clips']

    # Filter by category
    if category:
        if category not in pack_data['category_map']:
            return []
        candidates = pack_data['category_map'][category]

    # Filter by tags
    if tags:
        tag_list = [t.strip().lower() for t in tags.split(',')]
        tag_set = set(tag_list)
        candidates = [
            clip for clip in candidates
            if any(tag.lower() in tag_set for tag in clip.get('tags', []))
        ]

    # Filter by max duration
    if max_duration is not None:
        candidates = [
            clip for clip in candidates
            if clip.get('duration_seconds', 0) <= max_duration
        ]

    # Limit results
    selected = candidates[:limit]

    # Return format
    if include_metadata:
        return selected

    return [
        {
            'id': clip['id'],
            'category': clip.get('category', 'misc'),
            'duration_seconds': clip.get('duration_seconds'),
            'tags': clip.get('tags', [])
        }
        for clip in selected
    ]


@app.on_event("startup")
async def startup_event():
    """Initialize on startup"""
    logger.info("🌲 Ambient Audio Service starting...")
    load_library_manifests()
    logger.info(f"✅ Loaded {len(library_cache)} ambient library packs")


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
