"""Secure subprocess execution helpers for Agent World streaming services."""

from __future__ import annotations

import logging
import re
import subprocess
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from .validation import InputValidator, ValidationError, create_gstreamer_validator

logger = logging.getLogger(__name__)


class CommandInjectionError(ValueError):
    """Raised when command injection is detected."""


class GStreamerSecurityValidator:
    """Security validator for GStreamer pipeline elements and properties."""

    ALLOWED_ELEMENTS = {
        "gst-launch-1.0",
        "gst-inspect-1.0",
        "fdsrc",
        "rawvideoparse",
        "videoconvert",
        "queue",
        "nvh264enc",
        "vaapih264enc",
        "x264enc",
        "h264parse",
        "flvmux",
        "mpegtsmux",
        "srtsink",
        "rtmpsink",
        "video/x-raw",
        "capsfilter",
        # Audio elements
        "srtsrc",
        "decodebin",
        "audioconvert",
        "audioresample",
        "audiomixer",
        "volume",
        "voaacenc",
        "aacparse",
        "audio/x-raw",
    }

    ALLOWED_PROPERTIES = {
        "width": r"^\d{1,5}$",
        "height": r"^\d{1,5}$",
        "format": r"^[a-zA-Z0-9]+$",
        "framerate": r"^\d+/\d+$",
        "bitrate": r"^\d{1,8}$",
        "preset": r"^[a-z-]+$",
        "quality-level": r"^\d{1,2}$",
        "speed-preset": r"^[a-z-]+$",
        "tune": r"^[a-z-]+$",
        "key-int-max": r"^\d{1,4}$",
        "bframes": r"^\d{1,2}$",
        "config-interval": r"^-?\d{1,2}$",
        "max-size-buffers": r"^\d{1,4}$",
        "leaky": r"^[a-z-]+$",
        "do-timestamp": r"^(true|false)$",
        "sync": r"^(true|false)$",
        "async": r"^(true|false)$",
        "streamable": r"^(true|false)$",
        "uri": r"^[a-zA-Z0-9:/.\-_?&=]+$",
        "location": r"^[a-zA-Z0-9:/.\-_?&=]+$",
        # Audio properties
        "volume": r"^[0-9]*\.?[0-9]+$",  # Float 0.0-1.0
        "channels": r"^\d{1,2}$",
        "rate": r"^\d{4,6}$",
        "name": r"^[a-zA-Z0-9_-]+$",
    }

    @classmethod
    def validate_element(cls, element: str) -> str:
        if element not in cls.ALLOWED_ELEMENTS:
            raise CommandInjectionError(f"GStreamer element not allowed: {element}")
        return element

    @classmethod
    def validate_property(cls, prop_name: str, prop_value: str) -> str:
        if prop_name not in cls.ALLOWED_PROPERTIES:
            raise CommandInjectionError(f"GStreamer property not allowed: {prop_name}")

        pattern = cls.ALLOWED_PROPERTIES[prop_name]
        if not re.match(pattern, str(prop_value)):
            raise CommandInjectionError(
                f"Invalid value for property {prop_name}: {prop_value}"
            )

        return str(prop_value)

    @classmethod
    def validate_url(cls, url: str, allowed_schemes: Optional[List[str]] = None) -> str:
        allowed = allowed_schemes or ["srt", "rtmp"]
        parsed = urlparse(url)

        if parsed.scheme not in allowed:
            raise CommandInjectionError(
                f"URL scheme not allowed: {parsed.scheme}. Allowed: {allowed}"
            )

        for pattern in ("&&", "||"):
            if pattern in url:
                raise CommandInjectionError(f"Invalid characters in URL: {url}")

        for char in ["|", ";", "`", "$", "(", ")", "<", ">", "\n", "\r"]:
            if char in url:
                raise CommandInjectionError(f"Invalid characters in URL: {url}")

        return url


class GStreamerPipelineBuilder:
    """Build secure GStreamer pipelines for local streaming transports."""

    def __init__(self):
        self.validator = create_gstreamer_validator()
        self.input_validator = InputValidator()

    def create_srt_pipeline(
        self,
        width: int,
        height: int,
        fps: int,
        bitrate_kbps: int,
        srt_url: str,
        encoder_type: str = "x264",
    ) -> List[str]:
        try:
            width = self.input_validator.validate_dimension("width", width, min_val=1, max_val=7680)
            height = self.input_validator.validate_dimension("height", height, min_val=1, max_val=4320)
            fps = self.input_validator.validate_fps("fps", fps)
            bitrate_kbps = self.input_validator.validate_bitrate("bitrate_kbps", bitrate_kbps)
            srt_url = self.input_validator.validate_url("srt_url", srt_url, allowed_schemes=["srt"])
            encoder_type = self.input_validator.validate_enum(
                "encoder_type", encoder_type, ["nvenc", "vaapi", "x264"]
            )
        except ValidationError as exc:
            raise CommandInjectionError(str(exc))

        GStreamerSecurityValidator.validate_url(srt_url, ["srt"])

        pipeline_args = [
            "gst-launch-1.0",
            "fdsrc",
            "do-timestamp=true",
            "!",
            "rawvideoparse",
            f"width={width}",
            f"height={height}",
            "format=rgb",
            f"framerate={fps}/1",
            "!",
            "videoconvert",
            "!",
        ]

        if encoder_type == "nvenc":
            pipeline_args.extend([
                "nvh264enc",
                f"bitrate={bitrate_kbps}",
                "preset=low-latency-hq",
                "aud=true",
                "strict-gop=true",
                "gop-size=48",
                "zerolatency=true",
            ])
        elif encoder_type == "vaapi":
            pipeline_args.extend([
                "vaapih264enc",
                f"bitrate={bitrate_kbps}",
                "quality-level=7",
            ])
        else:
            pipeline_args.extend([
                "x264enc",
                f"bitrate={bitrate_kbps}",
                "speed-preset=ultrafast",
                "tune=zerolatency",
                "key-int-max=24",
                "bframes=0",
            ])

        pipeline_args.extend([
            "!",
            "h264parse",
            "config-interval=1",
            "!",
            "mpegtsmux",
            "!",
            "srtsink",
            f"uri={srt_url}",
            "sync=false",
            "async=false",
        ])

        return pipeline_args

    def create_rtmp_pipeline(
        self,
        width: int,
        height: int,
        fps: int,
        bitrate_kbps: int,
        rtmp_url: str,
        encoder_type: str = "x264",
    ) -> List[str]:
        try:
            width = self.input_validator.validate_dimension("width", width, min_val=1, max_val=7680)
            height = self.input_validator.validate_dimension("height", height, min_val=1, max_val=4320)
            fps = self.input_validator.validate_fps("fps", fps)
            bitrate_kbps = self.input_validator.validate_bitrate("bitrate_kbps", bitrate_kbps)
            rtmp_url = self.input_validator.validate_url("rtmp_url", rtmp_url, allowed_schemes=["rtmp"])
            encoder_type = self.input_validator.validate_enum(
                "encoder_type", encoder_type, ["nvenc", "vaapi", "x264"]
            )
        except ValidationError as exc:
            raise CommandInjectionError(str(exc))

        GStreamerSecurityValidator.validate_url(rtmp_url, ["rtmp"])

        pipeline_args = [
            "gst-launch-1.0",
            "fdsrc",
            "do-timestamp=true",
            "!",
            "rawvideoparse",
            f"width={width}",
            f"height={height}",
            "format=rgb",
            f"framerate={fps}/1",
            "!",
            "videoconvert",
            "!",
            "queue",
            "max-size-buffers=1",
            "leaky=downstream",
            "!",
            "video/x-raw,format=NV12",
            "!",
        ]

        if encoder_type == "nvenc":
            pipeline_args.extend([
                "nvh264enc",
                f"bitrate={bitrate_kbps}",
                "preset=low-latency-hq",
                "aud=true",
                "strict-gop=true",
                "gop-size=48",
                "zerolatency=true",
            ])
        elif encoder_type == "vaapi":
            pipeline_args.extend([
                "vaapih264enc",
                f"bitrate={bitrate_kbps}",
                "quality-level=7",
            ])
        else:
            pipeline_args.extend([
                "x264enc",
                f"bitrate={bitrate_kbps}",
                "speed-preset=ultrafast",
                "tune=zerolatency",
                "key-int-max=24",
                "bframes=0",
            ])

        pipeline_args.extend([
            "!",
            "h264parse",
            "config-interval=1",
            "!",
            "flvmux",
            "streamable=true",
            "!",
            "rtmpsink",
            f"location={rtmp_url}",
            "sync=false",
            "async=false",
        ])

        return pipeline_args

    def create_rtmp_pipeline_with_audio(
        self,
        width: int,
        height: int,
        fps: int,
        video_bitrate_kbps: int,
        rtmp_url: str,
        encoder_type: str = "x264",
        audio_channels: Optional[List[Dict[str, Any]]] = None,
        audio_bitrate_kbps: int = 160,
    ) -> List[str]:
        """
        Create secure RTMP pipeline with multi-channel audio mixing.

        Args:
            width: Video width
            height: Video height
            fps: Frame rate
            video_bitrate_kbps: Video bitrate in kbps
            rtmp_url: RTMP destination URL
            encoder_type: Video encoder type (nvenc, vaapi, x264)
            audio_channels: List of audio channel configs with srt_port and volume
            audio_bitrate_kbps: Audio bitrate in kbps

        Returns:
            List of pipeline command arguments

        Raises:
            CommandInjectionError: If validation fails
        """
        # Validate video parameters
        try:
            width = self.input_validator.validate_dimension("width", width, min_val=1, max_val=7680)
            height = self.input_validator.validate_dimension("height", height, min_val=1, max_val=4320)
            fps = self.input_validator.validate_fps("fps", fps)
            video_bitrate_kbps = self.input_validator.validate_bitrate("video_bitrate_kbps", video_bitrate_kbps)
            rtmp_url = self.input_validator.validate_url("rtmp_url", rtmp_url, allowed_schemes=["rtmp"])
            encoder_type = self.input_validator.validate_enum(
                "encoder_type", encoder_type, ["nvenc", "vaapi", "x264"]
            )
            audio_bitrate_kbps = self.input_validator.validate_bitrate("audio_bitrate_kbps", audio_bitrate_kbps)
        except ValidationError as exc:
            raise CommandInjectionError(str(exc))

        GStreamerSecurityValidator.validate_url(rtmp_url, ["rtmp"])

        # Start with video pipeline
        pipeline_args = [
            "gst-launch-1.0",
            "fdsrc",
            "do-timestamp=true",
            "!",
            "rawvideoparse",
            f"width={width}",
            f"height={height}",
            "format=rgb",
            f"framerate={fps}/1",
            "!",
            "videoconvert",
            "!",
            "queue",
            "max-size-buffers=1",
            "leaky=downstream",
            "!",
            "video/x-raw,format=NV12",
            "!",
        ]

        # Video encoder
        if encoder_type == "nvenc":
            pipeline_args.extend([
                "nvh264enc",
                f"bitrate={video_bitrate_kbps}",
                "preset=low-latency-hq",
                "aud=true",
                "strict-gop=true",
                "gop-size=48",
                "zerolatency=true",
            ])
        elif encoder_type == "vaapi":
            pipeline_args.extend([
                "vaapih264enc",
                f"bitrate={video_bitrate_kbps}",
                "quality-level=7",
            ])
        else:
            pipeline_args.extend([
                "x264enc",
                f"bitrate={video_bitrate_kbps}",
                "speed-preset=ultrafast",
                "tune=zerolatency",
                "key-int-max=24",
                "bframes=0",
            ])

        pipeline_args.extend([
            "!",
            "h264parse",
            "config-interval=1",
            "!",
            "mux.",
        ])

        # Add audio channels if provided
        if audio_channels and len(audio_channels) > 0:
            for channel in audio_channels:
                # Validate channel parameters
                srt_port = channel.get('srt_port')
                volume = channel.get('volume', 1.0)

                if not isinstance(srt_port, int) or not (1024 <= srt_port <= 65535):
                    raise CommandInjectionError(f"Invalid SRT port: {srt_port}")

                if not isinstance(volume, (int, float)) or not (0.0 <= volume <= 1.0):
                    raise CommandInjectionError(f"Invalid volume: {volume}")

                # SRT audio source pipeline
                srt_uri = f"srt://0.0.0.0:{srt_port}?mode=listener"
                GStreamerSecurityValidator.validate_url(srt_uri, ["srt"])

                pipeline_args.extend([
                    "srtsrc",
                    f"uri={srt_uri}",
                    "!",
                    "decodebin",
                    "!",
                    "audioconvert",
                    "!",
                    "audioresample",
                    "!",
                    "volume",
                    f"volume={volume}",
                    "!",
                    "audio/x-raw,channels=2,rate=48000",
                    "!",
                    "mix.",
                ])

            # Audio mixer and encoder
            pipeline_args.extend([
                "audiomixer",
                "name=mix",
                "!",
                "audioconvert",
                "!",
                "voaacenc",
                f"bitrate={audio_bitrate_kbps * 1000}",  # voaacenc expects bits, not kbps
                "!",
                "aacparse",
                "!",
                "mux.",
            ])

        # FLV muxer and RTMP sink
        pipeline_args.extend([
            "flvmux",
            "name=mux",
            "streamable=true",
            "!",
            "rtmpsink",
            f"location={rtmp_url}",
            "sync=false",
            "async=false",
        ])

        return pipeline_args


def safe_subprocess_run(cmd_args: List[str], timeout: int = 30, **kwargs) -> subprocess.CompletedProcess:
    dangerous_chars = ["&", "|", ";", "`", "$", "\n", "\r"]

    for arg in cmd_args:
        if any(char in str(arg) for char in dangerous_chars):
            raise CommandInjectionError(f"Dangerous characters in command argument: {arg}")

    kwargs.setdefault("shell", False)
    kwargs.setdefault("timeout", timeout)

    logger.debug("Executing safe subprocess: %s", " ".join(map(str, cmd_args)))
    return subprocess.run(cmd_args, **kwargs)


def validate_gstreamer_element_availability(element: str) -> bool:
    try:
        GStreamerSecurityValidator.validate_element("gst-inspect-1.0")
        validated = GStreamerSecurityValidator.validate_element(element)
        cmd = ["gst-inspect-1.0", validated]
        result = safe_subprocess_run(cmd, timeout=5, capture_output=True)
        return result.returncode == 0
    except (CommandInjectionError, subprocess.TimeoutExpired, Exception):
        return False


def create_secure_srt_pipeline(
    width: int,
    height: int,
    fps: int,
    bitrate_kbps: int,
    srt_url: str,
    encoder_type: str = "x264",
) -> List[str]:
    builder = GStreamerPipelineBuilder()
    return builder.create_srt_pipeline(width, height, fps, bitrate_kbps, srt_url, encoder_type)


def create_secure_rtmp_pipeline(
    width: int,
    height: int,
    fps: int,
    bitrate_kbps: int,
    rtmp_url: str,
    encoder_type: str = "x264",
) -> List[str]:
    builder = GStreamerPipelineBuilder()
    return builder.create_rtmp_pipeline(width, height, fps, bitrate_kbps, rtmp_url, encoder_type)


def create_secure_rtmp_pipeline_with_audio(
    width: int,
    height: int,
    fps: int,
    video_bitrate_kbps: int,
    rtmp_url: str,
    encoder_type: str = "x264",
    audio_channels: Optional[List[Dict[str, Any]]] = None,
    audio_bitrate_kbps: int = 160,
) -> List[str]:
    """
    Create secure RTMP pipeline with multi-channel audio mixing.

    Args:
        width: Video width
        height: Video height
        fps: Frame rate
        video_bitrate_kbps: Video bitrate in kbps
        rtmp_url: RTMP destination URL
        encoder_type: Video encoder type (nvenc, vaapi, x264)
        audio_channels: List of audio channel configs with srt_port and volume
        audio_bitrate_kbps: Audio bitrate in kbps

    Returns:
        List of secure pipeline command arguments

    Example:
        >>> audio_channels = [
        ...     {'srt_port': 9001, 'volume': 0.8},  # Narration
        ...     {'srt_port': 9002, 'volume': 0.3},  # Background
        ... ]
        >>> pipeline = create_secure_rtmp_pipeline_with_audio(
        ...     1920, 1080, 24, 4500,
        ...     "rtmp://a.rtmp.youtube.com/live2/KEY",
        ...     encoder_type="nvenc",
        ...     audio_channels=audio_channels
        ... )
    """
    builder = GStreamerPipelineBuilder()
    return builder.create_rtmp_pipeline_with_audio(
        width, height, fps, video_bitrate_kbps, rtmp_url,
        encoder_type, audio_channels, audio_bitrate_kbps
    )


__all__ = [
    "CommandInjectionError",
    "GStreamerSecurityValidator",
    "GStreamerPipelineBuilder",
    "safe_subprocess_run",
    "validate_gstreamer_element_availability",
    "create_secure_srt_pipeline",
    "create_secure_rtmp_pipeline",
    "create_secure_rtmp_pipeline_with_audio",
]
