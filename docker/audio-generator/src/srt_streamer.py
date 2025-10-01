"""
SRT (Secure Reliable Transport) streaming utilities.

Handles streaming audio to OBS via SRT protocol using FFmpeg subprocess.
"""

import asyncio
import logging
import subprocess
from typing import Optional
import numpy as np

logger = logging.getLogger(__name__)


class SRTStreamer:
    """SRT audio streamer using FFmpeg"""

    def __init__(
        self,
        port: int,
        sample_rate: int = 48000,
        channels: int = 2,
        bitrate: int = 160000
    ):
        """
        Initialize SRT streamer.

        Args:
            port: SRT port number
            sample_rate: Audio sample rate (Hz)
            channels: Number of audio channels (1=mono, 2=stereo)
            bitrate: Audio bitrate (bits/second)
        """
        self.port = port
        self.sample_rate = sample_rate
        self.channels = channels
        self.bitrate = bitrate
        self.process: Optional[subprocess.Popen] = None
        self.running = False

    async def start(self):
        """Start SRT streaming process"""
        if self.running:
            logger.warning(f"SRT stream on port {self.port} already running")
            return

        # FFmpeg command for SRT streaming
        # Input: raw audio from stdin
        # Output: AAC encoded audio over SRT
        ffmpeg_cmd = [
            'ffmpeg',
            '-f', 'f32le',  # Input format: 32-bit float PCM
            '-ar', str(self.sample_rate),  # Sample rate
            '-ac', str(self.channels),  # Channel count
            '-i', 'pipe:0',  # Read from stdin
            '-c:a', 'aac',  # AAC codec
            '-b:a', str(self.bitrate),  # Bitrate
            '-f', 'mpegts',  # MPEG-TS container
            f'srt://0.0.0.0:{self.port}?mode=listener&latency=200'  # SRT output
        ]

        try:
            self.process = subprocess.Popen(
                ffmpeg_cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE
            )
            self.running = True
            logger.info(
                f"✅ SRT stream started on port {self.port} "
                f"({self.sample_rate}Hz, {self.channels}ch, {self.bitrate}bps)"
            )
        except Exception as e:
            logger.error(f"Failed to start SRT stream on port {self.port}: {e}")
            raise

    async def write(self, audio: np.ndarray):
        """
        Write audio data to SRT stream.

        Args:
            audio: Audio samples (float32, shape: (samples,) or (samples, channels))
        """
        if not self.running or not self.process:
            logger.warning(f"SRT stream on port {self.port} not running, skipping write")
            return

        try:
            # Ensure audio is float32
            if audio.dtype != np.float32:
                audio = audio.astype(np.float32)

            # Ensure correct shape for stereo/mono
            if self.channels == 2 and audio.ndim == 1:
                # Convert mono to stereo by duplicating
                audio = np.stack([audio, audio], axis=-1)
            elif self.channels == 1 and audio.ndim == 2:
                # Convert stereo to mono by averaging
                audio = audio.mean(axis=-1)

            # Write to FFmpeg stdin
            audio_bytes = audio.tobytes()
            self.process.stdin.write(audio_bytes)
            self.process.stdin.flush()

            logger.debug(f"Wrote {len(audio_bytes)} bytes to SRT port {self.port}")

        except BrokenPipeError:
            logger.error(f"SRT stream on port {self.port} broken pipe")
            self.running = False
        except Exception as e:
            logger.error(f"Error writing to SRT stream on port {self.port}: {e}")

    async def stop(self):
        """Stop SRT streaming process"""
        if not self.running or not self.process:
            return

        try:
            # Close stdin to signal end of stream
            if self.process.stdin:
                self.process.stdin.close()

            # Wait for process to terminate
            self.process.wait(timeout=5)

            self.running = False
            self.process = None

            logger.info(f"SRT stream on port {self.port} stopped")

        except subprocess.TimeoutExpired:
            logger.warning(f"SRT stream on port {self.port} did not stop gracefully, killing")
            self.process.kill()
            self.running = False
            self.process = None

        except Exception as e:
            logger.error(f"Error stopping SRT stream on port {self.port}: {e}")

    def is_running(self) -> bool:
        """Check if stream is running"""
        return self.running and self.process is not None

    def get_status(self) -> dict:
        """Get stream status"""
        return {
            "port": self.port,
            "running": self.running,
            "sample_rate": self.sample_rate,
            "channels": self.channels,
            "bitrate": self.bitrate
        }
