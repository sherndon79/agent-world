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

    async def send_audio(self, audio: np.ndarray):
        """Send audio data to SRT stream (alias for write)"""
        await self.write(audio)

    async def write(self, audio: np.ndarray):
        """
        Write audio data to SRT stream at real-time speed.

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

            # Stream audio in chunks at real-time speed to prevent overwhelming the buffer
            # Chunk size: 0.1 seconds of audio (prevents buffering issues)
            chunk_samples = int(self.sample_rate * 0.1)  # 4800 samples @ 48kHz
            total_samples = len(audio) if audio.ndim == 1 else len(audio)

            for i in range(0, total_samples, chunk_samples):
                if not self.running:
                    break

                # Get chunk
                end_idx = min(i + chunk_samples, total_samples)
                if audio.ndim == 1:
                    chunk = audio[i:end_idx]
                else:
                    chunk = audio[i:end_idx, :]

                # Write chunk to FFmpeg stdin
                chunk_bytes = chunk.tobytes()
                self.process.stdin.write(chunk_bytes)
                self.process.stdin.flush()

                # Sleep for the duration of this chunk to maintain real-time pacing
                # This prevents FFmpeg from encoding faster than playback speed
                chunk_duration = len(chunk) / self.sample_rate if audio.ndim == 1 else len(chunk) / self.sample_rate
                await asyncio.sleep(chunk_duration)

            logger.debug(f"Wrote {total_samples} samples to SRT port {self.port} at real-time speed")

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
