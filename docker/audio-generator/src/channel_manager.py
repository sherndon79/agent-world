"""
Channel Manager for multi-channel audio generation.

Coordinates 4 audio channels (narration, ambient, music, commentary)
and routes story updates to appropriate AI models for generation.
"""

import asyncio
import logging
from typing import Dict, Any, Optional
from datetime import datetime
from collections import deque
import uuid

logger = logging.getLogger(__name__)


class AudioChannel:
    """Represents a single audio channel"""

    def __init__(
        self,
        channel_id: str,
        port: int,
        model_name: str = "placeholder"
    ):
        """
        Initialize audio channel.

        Args:
            channel_id: Channel identifier (narration, ambient, music, commentary)
            port: SRT output port
            model_name: AI model name for this channel
        """
        self.id = channel_id
        self.port = port
        self.model_name = model_name
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

    async def initialize(self):
        """Initialize all audio channels"""
        if self._initialized:
            return

        logger.info("Initializing audio channels...")

        # Create 4 audio channels
        self.channels = {
            "narration": AudioChannel("narration", 9001, "chatterbox"),
            "ambient": AudioChannel("ambient", 9002, "elevenlabs"),
            "music": AudioChannel("music", 9003, "mubert"),
            "commentary": AudioChannel("commentary", 9004, "elevenlabs")
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
        Generate audio for a request.

        Args:
            channel: AudioChannel processing the request
            request: Request data
        """
        start_time = datetime.now()
        request_id = request["id"]
        data = request["data"]

        logger.info(f"[{channel.id}] Generating audio for request {request_id}")

        try:
            # TODO: Call actual AI model here
            # For now, simulate generation
            await asyncio.sleep(0.5)  # Simulate processing time

            # Simulate successful generation
            generation_time = (datetime.now() - start_time).total_seconds() * 1000

            result = {
                "success": True,
                "duration_ms": 4500,  # Simulated audio duration
                "generation_time_ms": generation_time,
                "model": channel.model_name,
                "output_size_bytes": 360000  # Simulated size
            }

            logger.info(
                f"[{channel.id}] Audio generated successfully in {generation_time:.0f}ms"
            )

            # TODO: Stream to SRT port
            # await self._stream_to_srt(channel, audio_data)

            # Mark as complete
            channel.status = "idle"
            channel.current_task = None

            # Return result for status reporting
            return result

        except Exception as e:
            logger.error(f"[{channel.id}] Generation failed: {e}", exc_info=True)
            channel.status = "error"
            raise

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
