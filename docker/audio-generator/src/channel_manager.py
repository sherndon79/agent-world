"""
Channel Manager for multi-channel audio generation.

Coordinates 4 audio channels (narration, ambient, music, commentary)
and routes story updates to appropriate microservices for generation.

Microservice Architecture:
- Narration: Kokoro TTS (native PyTorch) on port 8081
- Commentary: Kokoro TTS (native PyTorch) on port 8082
- Ambient: Procedural audio on port 8083
- Music: Procedural music on port 8084
"""

import asyncio
import logging
import os
from typing import Dict, Any, Optional
from datetime import datetime
from collections import deque
import uuid

import aiohttp
import soundfile as sf
import numpy as np
import tempfile

from srt_streamer import SRTStreamer

logger = logging.getLogger(__name__)


class AudioChannel:
    """Represents a single audio channel with microservice backend"""

    def __init__(
        self,
        channel_id: str,
        port: int,
        model_name: str = "placeholder",
        service_url: Optional[str] = None,
        streamer: Optional[SRTStreamer] = None
    ):
        """
        Initialize audio channel.

        Args:
            channel_id: Channel identifier (narration, ambient, music, commentary)
            port: SRT output port
            model_name: AI model name for this channel
            service_url: Microservice URL (e.g., http://narration:8081)
            streamer: SRT streamer instance
        """
        self.id = channel_id
        self.port = port
        self.model_name = model_name
        self.service_url = service_url
        self.streamer = streamer
        self.status = "idle"
        self.queue = deque(maxlen=100)  # Request queue
        self.current_task: Optional[Dict[str, Any]] = None
        self.srt_connected = False
        self.srt_clients = 0

    def get_status(self) -> Dict[str, Any]:
        """Get channel status"""
        status = {
            "id": self.id,
            "port": self.port,
            "status": self.status,
            "model": self.model_name,
            "queue_depth": len(self.queue),
            "srt_connection": {
                "connected": self.srt_connected,
                "clients": self.srt_clients
            }
        }

        if self.current_task:
            status["current"] = self.current_task

        return status

    async def enqueue(self, data: Dict[str, Any], metadata: Dict[str, Any]) -> str:
        """
        Enqueue audio generation request.

        Args:
            data: Request data (text, scene description, etc.)
            metadata: Request metadata (scene_id, story_beat, etc.)

        Returns:
            str: Request ID
        """
        request_id = str(uuid.uuid4())
        request = {
            "id": request_id,
            "data": data,
            "metadata": metadata,
            "queued_at": datetime.now().isoformat()
        }
        self.queue.append(request)
        logger.debug(f"[{self.id}] Enqueued request {request_id}, queue depth: {len(self.queue)}")
        return request_id

    async def process_next(self) -> Optional[Dict[str, Any]]:
        """
        Process next item in queue.

        Returns:
            Optional[Dict]: Processed request or None if queue empty
        """
        if not self.queue:
            return None

        request = self.queue.popleft()
        self.current_task = request
        self.status = "processing"
        return request

    def clear_queue(self):
        """Clear all queued requests"""
        self.queue.clear()
        logger.info(f"[{self.id}] Queue cleared")


class ChannelManager:
    """Manages all audio channels and routes requests"""

    def __init__(self):
        """Initialize channel manager"""
        self.channels: Dict[str, AudioChannel] = {}
        self.processing_tasks: Dict[str, asyncio.Task] = {}
        self._initialized = False

        # Sync group coordination
        self.sync_groups: Dict[str, Dict[str, Any]] = {}  # sync_id -> {channels: set, ready_audio: dict, event: asyncio.Event}

        # Auto-ducking configuration
        self.ducking_config = {
            "enabled": True,
            "duck_ratio": 0.20,  # Reduce background to 20% when foreground plays
            "fade_duration": 0.05,  # 50ms fade in/out
            "foreground_channels": {"narration", "commentary"},  # These trigger ducking
            "background_channels": {"music", "ambient"}  # These get ducked
        }

        # Track active foreground audio
        self.active_foreground: set = set()  # Set of currently playing foreground channels
        self.ducking_lock = asyncio.Lock()

    async def initialize(self):
        """Initialize all audio channels with microservice backends"""
        if self._initialized:
            return

        logger.info("Initializing audio channels with microservices...")

        # Get service URLs from environment variables
        narration_url = os.getenv("NARRATION_SERVICE_URL", "http://localhost:8081")
        commentary_url = os.getenv("COMMENTARY_SERVICE_URL", "http://localhost:8082")
        ambient_url = os.getenv("AMBIENT_SERVICE_URL", "http://localhost:8083")
        music_url = os.getenv("MUSIC_SERVICE_URL", "http://localhost:8084")

        # Create SRT streamers for each channel
        narration_streamer = SRTStreamer(port=9001, sample_rate=48000)
        await narration_streamer.start()

        ambient_streamer = SRTStreamer(port=9002, sample_rate=48000)
        await ambient_streamer.start()

        music_streamer = SRTStreamer(port=9003, sample_rate=48000)
        await music_streamer.start()

        commentary_streamer = SRTStreamer(port=9004, sample_rate=48000)
        await commentary_streamer.start()

        # Create 4 audio channels with microservice backends
        self.channels = {
            "narration": AudioChannel("narration", 9001, "kokoro", narration_url, narration_streamer),
            "ambient": AudioChannel("ambient", 9002, "procedural", ambient_url, ambient_streamer),
            "music": AudioChannel("music", 9003, "procedural", music_url, music_streamer),
            "commentary": AudioChannel("commentary", 9004, "kokoro", commentary_url, commentary_streamer)
        }

        # Start processing loops for each channel
        for channel_id, channel in self.channels.items():
            task = asyncio.create_task(self._process_channel_loop(channel))
            self.processing_tasks[channel_id] = task

        self._initialized = True
        logger.info("✅ All audio channels initialized")

    async def _process_channel_loop(self, channel: AudioChannel):
        """
        Continuous processing loop for a channel.

        Args:
            channel: AudioChannel to process
        """
        while True:
            try:
                # Process next queued request
                request = await channel.process_next()

                if request:
                    await self._generate_audio(channel, request)
                else:
                    # No requests, set to idle and wait
                    channel.status = "idle"
                    channel.current_task = None
                    await asyncio.sleep(0.1)

            except Exception as e:
                logger.error(f"[{channel.id}] Processing error: {e}", exc_info=True)
                channel.status = "error"
                await asyncio.sleep(1)

    async def _generate_audio(self, channel: AudioChannel, request: Dict[str, Any]):
        """
        Generate audio for a request by calling microservice.

        Args:
            channel: AudioChannel processing the request
            request: Request data
        """
        start_time = datetime.now()
        request_id = request["id"]
        data = request["data"]
        metadata = request.get("metadata", {})
        sync_id = metadata.get("sync_id")

        logger.info(f"[{channel.id}] Generating audio for request {request_id} via {channel.service_url}")

        try:
            # Prepare request payload based on channel type
            payload = {}

            if channel.id in ("narration", "commentary"):
                # TTS request
                payload = {
                    "text": data.get("text", ""),
                    "voice": data.get("voice", "default"),
                    "emotion": data.get("emotion", "neutral"),
                    "emotion_exaggeration": data.get("emotion_exaggeration")
                }

            elif channel.id == "ambient":
                # Ambient audio request - check if using library sample or procedural
                if "sample_id" in data:
                    # Use play_sample endpoint for library samples
                    endpoint = "/play_sample"
                    payload = {
                        "sample_id": data["sample_id"],
                        "fade_out_after": data.get("fade_out_after", 30),
                        "fade_duration": data.get("fade_duration", 3.0),
                        "loop_if_short": data.get("loop_if_short", False)
                    }
                else:
                    # Use procedural generation endpoint
                    endpoint = "/generate"
                    payload = {
                        "environment": data.get("environment", "forest"),
                        "time_of_day": data.get("time_of_day", "day"),
                        "weather": data.get("weather", "clear"),
                        "special_effects": data.get("special_effects", [])
                    }

            elif channel.id == "music":
                # Music generation request
                payload = {
                    "tension_level": data.get("tension_level", "neutral"),
                    "intensity": data.get("intensity", 0.5),
                    "genre": data.get("genre", "orchestral"),
                    "tempo": data.get("tempo", "moderate"),
                    "duration": data.get("duration", 10.0)  # Default 10 seconds
                }

            # Call microservice
            # Determine endpoint (ambient might use /play_sample)
            service_endpoint = "/generate"
            if channel.id == "ambient" and "sample_id" in data:
                service_endpoint = "/play_sample"

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{channel.service_url}{service_endpoint}",
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        raise Exception(f"Microservice returned {response.status}: {error_text}")

                    # Read WAV audio from response
                    wav_bytes = await response.read()

            # Load WAV from bytes
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp:
                tmp_path = tmp.name
                tmp.write(wav_bytes)

            try:
                audio_data, sr = sf.read(tmp_path, dtype='float32')

                # Ensure mono for TTS, keep stereo for music
                if channel.id == "music" and len(audio_data.shape) == 2:
                    # Keep stereo, but we'll need to stream it properly
                    # For now, convert to mono for SRT compatibility
                    audio_data = audio_data.mean(axis=1)
                elif len(audio_data.shape) > 1:
                    audio_data = audio_data.mean(axis=1)

            finally:
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)

            # Apply volume adjustment
            volume = data.get("volume", 1.0)
            if volume != 1.0:
                audio_data = audio_data * volume
                audio_data = np.clip(audio_data, -1.0, 1.0).astype(np.float32)
                logger.info(f"[{channel.id}] Applied volume: {volume:.2f}")

            generation_time = (datetime.now() - start_time).total_seconds() * 1000

            # Handle sync group coordination
            if sync_id:
                await self._wait_for_sync_group(sync_id, channel.id, audio_data)
            else:
                # Stream immediately if not part of a sync group
                if channel.streamer:
                    await channel.streamer.send_audio(audio_data)
                    logger.info(f"[{channel.id}] Streamed {len(audio_data)} samples to SRT port {channel.port}")

            result = {
                "success": True,
                "duration_ms": len(audio_data) / 48,
                "generation_time_ms": generation_time,
                "model": channel.model_name,
                "output_size_bytes": len(audio_data) * 4
            }

            logger.info(
                f"[{channel.id}] Audio generated successfully in {generation_time:.0f}ms"
            )

            # Mark as complete
            channel.status = "idle"
            channel.current_task = None

            return result

        except Exception as e:
            logger.error(f"[{channel.id}] Generation failed: {e}", exc_info=True)
            channel.status = "error"
            raise

    async def _apply_sync_ducking(self, ready_audio: Dict[str, np.ndarray]):
        """
        Apply ducking to background channels when foreground channels are present.

        Args:
            ready_audio: Dictionary of channel_id -> audio_data
        """
        foreground_present = any(
            ch_id in self.ducking_config["foreground_channels"]
            for ch_id in ready_audio.keys()
        )

        if not foreground_present:
            logger.debug("No foreground audio - skipping ducking")
            return

        # Calculate max duration of foreground audio
        max_foreground_duration = 0
        for ch_id in ready_audio.keys():
            if ch_id in self.ducking_config["foreground_channels"]:
                duration = len(ready_audio[ch_id]) / 48000  # Assuming 48kHz
                max_foreground_duration = max(max_foreground_duration, duration)

        # Apply ducking to background channels
        for ch_id in ready_audio.keys():
            if ch_id in self.ducking_config["background_channels"]:
                original_audio = ready_audio[ch_id]
                audio_duration = len(original_audio) / 48000

                # Duck the portion that overlaps with foreground
                if audio_duration > 0:
                    # Calculate how much of the background to duck
                    duck_samples = int(min(max_foreground_duration, audio_duration) * 48000)

                    if duck_samples > 0:
                        ducked = self._apply_ducking(
                            original_audio[:duck_samples],
                            self.ducking_config["duck_ratio"],
                            self.ducking_config["fade_duration"]
                        )

                        # Replace ducked portion
                        ready_audio[ch_id] = np.concatenate([
                            ducked,
                            original_audio[duck_samples:]
                        ])

                        logger.info(
                            f"🔉 Ducked [{ch_id}] to {self.ducking_config['duck_ratio']*100:.0f}% "
                            f"for {max_foreground_duration:.1f}s (foreground audio present)"
                        )

    def _apply_ducking(self, audio_data: np.ndarray, duck_ratio: float, fade_duration: float) -> np.ndarray:
        """
        Apply volume ducking with fade in/out.

        Args:
            audio_data: Audio samples to duck
            duck_ratio: Target volume ratio (0.0 - 1.0)
            fade_duration: Fade duration in seconds

        Returns:
            np.ndarray: Ducked audio with fades
        """
        ducked = audio_data.copy()
        fade_samples = int(self.channels["music"].streamer.sample_rate * fade_duration)

        # Create fade curve (smooth transition)
        fade_in = np.linspace(duck_ratio, 1.0, fade_samples)
        fade_out = np.linspace(1.0, duck_ratio, fade_samples)

        # Apply fade out at start
        if len(ducked) >= fade_samples:
            ducked[:fade_samples] *= fade_out

        # Apply fade in at end
        if len(ducked) >= fade_samples:
            ducked[-fade_samples:] *= fade_in

        # Apply constant ducking to middle section
        if len(ducked) > 2 * fade_samples:
            ducked[fade_samples:-fade_samples] *= duck_ratio

        return ducked.astype(np.float32)

    async def _wait_for_sync_group(self, sync_id: str, channel_id: str, audio_data: np.ndarray):
        """
        Wait for all channels in a sync group to be ready, then stream all together.

        Args:
            sync_id: Sync group identifier
            channel_id: This channel's ID
            audio_data: Generated audio data
        """
        # Initialize sync group if needed
        if sync_id not in self.sync_groups:
            self.sync_groups[sync_id] = {
                "channels": set(),
                "ready_audio": {},
                "event": asyncio.Event()
            }

        sync_group = self.sync_groups[sync_id]

        # Mark this channel as ready
        sync_group["ready_audio"][channel_id] = audio_data
        logger.info(f"[{channel_id}] Ready for sync group '{sync_id}' ({len(sync_group['ready_audio'])}/{len(sync_group['channels'])} ready)")

        # Check if all expected channels are ready
        if sync_group["channels"] and sync_group["ready_audio"].keys() == sync_group["channels"]:
            # All channels ready - trigger simultaneous streaming
            logger.info(f"🎬 Sync group '{sync_id}' complete - streaming all channels simultaneously")

            # Apply auto-ducking if enabled
            if self.ducking_config["enabled"]:
                await self._apply_sync_ducking(sync_group["ready_audio"])

            # Stream all channels at the same time
            stream_tasks = []
            for ch_id, audio in sync_group["ready_audio"].items():
                if ch_id in self.channels and self.channels[ch_id].streamer:
                    stream_tasks.append(self.channels[ch_id].streamer.send_audio(audio))

            await asyncio.gather(*stream_tasks)
            logger.info(f"✅ Sync group '{sync_id}' streaming complete")

            # Signal waiting channels and clean up
            sync_group["event"].set()
            del self.sync_groups[sync_id]
        else:
            # Wait for other channels
            logger.info(f"[{channel_id}] Waiting for other channels in sync group '{sync_id}'...")
            await sync_group["event"].wait()

    def register_sync_group(self, sync_id: str, channel_ids: list, metadata: Optional[Dict[str, Any]] = None):
        """
        Register a new sync group with expected channels.

        Args:
            sync_id: Unique sync group identifier
            channel_ids: List of channel IDs that should sync together
            metadata: Additional sync metadata
        """
        self.sync_groups[sync_id] = {
            "channels": set(channel_ids),
            "ready_audio": {},
            "event": asyncio.Event(),
            "metadata": metadata or {}
        }
        logger.info(f"Registered sync group '{sync_id}' with channels: {channel_ids}")

    async def generate_narration(
        self,
        data: Dict[str, Any],
        metadata: Dict[str, Any] = None
    ) -> str:
        """
        Generate narration audio.

        Args:
            data: Narration data (text, voice, emotion)
            metadata: Request metadata

        Returns:
            str: Request ID
        """
        text = data.get("text", "")
        voice = data.get("voice", "narrator_default")
        emotion = data.get("emotion", "neutral")
        interrupt = data.get("interrupt", False)

        logger.info(f"[narration] Request: '{text[:50]}...' (voice={voice}, emotion={emotion})")

        if interrupt:
            # Clear queue and process immediately
            self.channels["narration"].clear_queue()

        return await self.channels["narration"].enqueue(data, metadata or {})

    async def update_ambient(
        self,
        data: Dict[str, Any],
        metadata: Dict[str, Any] = None
    ) -> str:
        """
        Update ambient scene audio.

        Args:
            data: Scene data (environment, weather, time_of_day, etc.)
            metadata: Request metadata

        Returns:
            str: Request ID
        """
        environment = data.get("environment", "unknown")
        time_of_day = data.get("time_of_day", "day")
        weather = data.get("weather", "clear")

        logger.info(
            f"[ambient] Scene update: {environment} at {time_of_day}, {weather}"
        )

        return await self.channels["ambient"].enqueue(data, metadata or {})

    async def update_music(
        self,
        data: Dict[str, Any],
        metadata: Dict[str, Any] = None
    ) -> str:
        """
        Update music intensity/style.

        Args:
            data: Music data (tension_level, intensity, genre, tempo)
            metadata: Request metadata

        Returns:
            str: Request ID
        """
        tension = data.get("tension_level", "neutral")
        intensity = data.get("intensity", 0.5)
        genre = data.get("genre", "orchestral")

        logger.info(
            f"[music] Update: tension={tension}, intensity={intensity}, genre={genre}"
        )

        return await self.channels["music"].enqueue(data, metadata or {})

    async def generate_commentary(
        self,
        data: Dict[str, Any],
        metadata: Dict[str, Any] = None
    ) -> str:
        """
        Generate commentary audio.

        Args:
            data: Commentary data (text, voice)
            metadata: Request metadata

        Returns:
            str: Request ID
        """
        text = data.get("text", "")
        voice = data.get("voice", "host_enthusiastic")

        logger.info(f"[commentary] Request: '{text}'")

        return await self.channels["commentary"].enqueue(data, metadata or {})

    async def pause_channel(self, channel_id: str, params: Dict[str, Any] = None):
        """
        Pause a specific channel.

        Args:
            channel_id: Channel to pause (or "all")
            params: Pause parameters (fade_out_ms, etc.)
        """
        if channel_id == "all":
            for channel in self.channels.values():
                channel.status = "paused"
            logger.info("All channels paused")
        elif channel_id in self.channels:
            self.channels[channel_id].status = "paused"
            logger.info(f"[{channel_id}] Channel paused")

    async def resume_channel(self, channel_id: str, params: Dict[str, Any] = None):
        """
        Resume a paused channel.

        Args:
            channel_id: Channel to resume (or "all")
            params: Resume parameters (fade_in_ms, etc.)
        """
        if channel_id == "all":
            for channel in self.channels.values():
                if channel.status == "paused":
                    channel.status = "idle"
            logger.info("All channels resumed")
        elif channel_id in self.channels:
            if self.channels[channel_id].status == "paused":
                self.channels[channel_id].status = "idle"
                logger.info(f"[{channel_id}] Channel resumed")

    async def clear_queue(self, channel_id: str):
        """
        Clear queue for a specific channel.

        Args:
            channel_id: Channel to clear
        """
        if channel_id in self.channels:
            self.channels[channel_id].clear_queue()

    async def get_status(self) -> list:
        """
        Get status of all channels.

        Returns:
            list: List of channel status dictionaries
        """
        return [channel.get_status() for channel in self.channels.values()]

    async def shutdown(self):
        """Shutdown all channels gracefully"""
        logger.info("Shutting down channel manager...")

        # Cancel all processing tasks
        for task in self.processing_tasks.values():
            task.cancel()

        # Wait for tasks to complete
        await asyncio.gather(*self.processing_tasks.values(), return_exceptions=True)

        logger.info("✅ Channel manager shutdown complete")
