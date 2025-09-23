"""
Secure subprocess execution for agenTW∞rld Extensions.

Provides safe subprocess command construction and validation to prevent
command injection attacks in GStreamer pipelines and other subprocess calls.

Usage:
    from agent_world_subprocess_security import GStreamerPipelineBuilder, validate_gstreamer_element

    builder = GStreamerPipelineBuilder()
    pipeline = builder.create_srt_pipeline(
        width=1920, height=1080, fps=24,
        bitrate_kbps=2000, srt_url="srt://127.0.0.1:9999"
    )
"""

import re
import logging
import subprocess
from typing import List, Dict, Any, Optional
from urllib.parse import urlparse

from agent_world_validation import InputValidator, ValidationError, create_gstreamer_validator

logger = logging.getLogger(__name__)


class CommandInjectionError(ValueError):
    """Raised when command injection is detected."""
    pass


class GStreamerSecurityValidator:
    """Security validator for GStreamer pipeline elements and properties."""

    # Allowlist of safe GStreamer elements
    ALLOWED_ELEMENTS = {
        'gst-launch-1.0', 'gst-inspect-1.0',
        'fdsrc', 'rawvideoparse', 'videoconvert', 'queue',
        'nvh264enc', 'vaapih264enc', 'x264enc', 'h264parse',
        'mpegtsmux', 'flvmux', 'srtsink', 'rtmpsink',
        'video/x-raw', 'capsfilter'
    }

    # Allowlist of safe GStreamer properties and their validation patterns
    ALLOWED_PROPERTIES = {
        'width': r'^\d{1,5}$',                    # 1-99999
        'height': r'^\d{1,5}$',                   # 1-99999
        'format': r'^[a-zA-Z0-9]+$',              # alphanumeric only
        'framerate': r'^\d+/\d+$',                # fraction like 24/1
        'bitrate': r'^\d{1,8}$',                  # 1-99999999
        'preset': r'^[a-z-]+$',                   # lowercase with hyphens
        'quality-level': r'^\d{1,2}$',            # 1-99
        'speed-preset': r'^[a-z-]+$',             # lowercase with hyphens
        'tune': r'^[a-z-]+$',                     # lowercase with hyphens
        'key-int-max': r'^\d{1,4}$',              # 1-9999
        'bframes': r'^\d{1,2}$',                  # 0-99
        'config-interval': r'^\d{1,2}$',          # 1-99
        'alignment': r'^\d{1,2}$',                # 1-99
        'max-size-buffers': r'^\d{1,4}$',         # 1-9999
        'leaky': r'^[a-z-]+$',                    # lowercase
        'do-timestamp': r'^(true|false)$',        # boolean
        'sync': r'^(true|false)$',                # boolean
        'async': r'^(true|false)$',               # boolean
        'streamable': r'^(true|false)$',          # boolean
        'uri': r'^[a-zA-Z0-9:/.\-_?&=]+$',        # URL-safe characters
        'location': r'^[a-zA-Z0-9:/.\-_?&=]+$'    # URL-safe characters
    }

    @classmethod
    def validate_element(cls, element: str) -> str:
        """
        Validate GStreamer element name.

        Args:
            element: Element name to validate

        Returns:
            Validated element name

        Raises:
            CommandInjectionError: If element is not allowed
        """
        if element not in cls.ALLOWED_ELEMENTS:
            raise CommandInjectionError(f"GStreamer element not allowed: {element}")
        return element

    @classmethod
    def validate_property(cls, prop_name: str, prop_value: str) -> str:
        """
        Validate GStreamer property name and value.

        Args:
            prop_name: Property name
            prop_value: Property value

        Returns:
            Validated property value

        Raises:
            CommandInjectionError: If property is not allowed or value is invalid
        """
        if prop_name not in cls.ALLOWED_PROPERTIES:
            raise CommandInjectionError(f"GStreamer property not allowed: {prop_name}")

        pattern = cls.ALLOWED_PROPERTIES[prop_name]
        if not re.match(pattern, str(prop_value)):
            raise CommandInjectionError(
                f"Invalid value for property {prop_name}: {prop_value}"
            )

        return str(prop_value)

    @classmethod
    def validate_url(cls, url: str, allowed_schemes: List[str] = None) -> str:
        """
        Validate streaming URL.

        Args:
            url: URL to validate
            allowed_schemes: List of allowed URL schemes (default: ['srt', 'rtmp'])

        Returns:
            Validated URL

        Raises:
            CommandInjectionError: If URL is invalid or scheme not allowed
        """
        if allowed_schemes is None:
            allowed_schemes = ['srt', 'rtmp']

        try:
            parsed = urlparse(url)

            if parsed.scheme not in allowed_schemes:
                raise CommandInjectionError(
                    f"URL scheme not allowed: {parsed.scheme}. Allowed: {allowed_schemes}"
                )

            # Basic validation - no shell metacharacters (allow single & for query parameters)
            dangerous_chars = ['|', ';', '`', '$', '(', ')', '<', '>', '\n', '\r']
            dangerous_patterns = ['&&', '||']  # Multi-character patterns to check first

            # Check multi-character patterns first
            for pattern in dangerous_patterns:
                if pattern in url:
                    raise CommandInjectionError(f"Invalid characters in URL: {url}")

            # Then check single dangerous characters
            for char in dangerous_chars:
                if char in url:
                    raise CommandInjectionError(f"Invalid characters in URL: {url}")

            return url

        except Exception as e:
            raise CommandInjectionError(f"Invalid URL format: {url} - {e}")


class GStreamerPipelineBuilder:
    """Secure GStreamer pipeline builder with command injection prevention."""

    def __init__(self):
        self.validator = GStreamerSecurityValidator()
        self.input_validator = create_gstreamer_validator()

    def create_srt_pipeline(self, width: int, height: int, fps: int,
                           bitrate_kbps: int, srt_url: str,
                           encoder_type: str = "x264") -> List[str]:
        """
        Create a secure SRT streaming pipeline.

        Args:
            width: Video width (1-7680)
            height: Video height (1-4320)
            fps: Frames per second (1-120)
            bitrate_kbps: Bitrate in kbps (100-100000)
            srt_url: SRT streaming URL
            encoder_type: Encoder type (nvenc, vaapi, x264)

        Returns:
            List of validated command arguments

        Raises:
            CommandInjectionError: If any parameter is invalid
        """
        # Validate parameters using centralized validation
        try:
            width = self.input_validator.validate_dimension("width", width, min_val=1, max_val=7680)
            height = self.input_validator.validate_dimension("height", height, min_val=1, max_val=4320)
            fps = self.input_validator.validate_fps("fps", fps)
            bitrate_kbps = self.input_validator.validate_bitrate("bitrate_kbps", bitrate_kbps)
            srt_url = self.input_validator.validate_url("srt_url", srt_url, allowed_schemes=['srt'])
            encoder_type = self.input_validator.validate_enum("encoder_type", encoder_type, ['nvenc', 'vaapi', 'x264'])
        except ValidationError as e:
            raise CommandInjectionError(str(e))

        # Build pipeline with validated parameters
        pipeline_args = [
            'gst-launch-1.0',
            'fdsrc', 'do-timestamp=true', '!',
            'rawvideoparse', f'width={width}', f'height={height}',
            'format=rgb', f'framerate={fps}/1', '!',
            'videoconvert', '!',
            'queue', 'max-size-buffers=1', 'leaky=downstream', '!',
            'video/x-raw,format=NV12', '!'
        ]

        # Add encoder-specific elements
        if encoder_type == "nvenc":
            pipeline_args.extend([
                'nvh264enc', f'bitrate={bitrate_kbps}', 'preset=low-latency-hq', '!',
                'h264parse', 'config-interval=1', '!',
                'mpegtsmux', 'alignment=7', '!',
                'srtsink', f'uri={srt_url}', 'sync=false', 'async=false'
            ])
        elif encoder_type == "vaapi":
            pipeline_args.extend([
                'vaapih264enc', f'bitrate={bitrate_kbps}', 'quality-level=7', '!',
                'h264parse', 'config-interval=1', '!',
                'mpegtsmux', 'alignment=7', '!',
                'srtsink', f'uri={srt_url}', 'sync=false', 'async=false'
            ])
        else:  # x264
            pipeline_args.extend([
                'x264enc', f'bitrate={bitrate_kbps}', 'speed-preset=ultrafast',
                'tune=zerolatency', 'key-int-max=24', 'bframes=0', '!',
                'h264parse', 'config-interval=1', '!',
                'mpegtsmux', 'alignment=7', '!',
                'srtsink', f'uri={srt_url}', 'sync=false', 'async=false'
            ])

        return pipeline_args

    def create_rtmp_pipeline(self, width: int, height: int, fps: int,
                            bitrate_kbps: int, rtmp_url: str,
                            encoder_type: str = "x264") -> List[str]:
        """
        Create a secure RTMP streaming pipeline.

        Args:
            width: Video width (1-7680)
            height: Video height (1-4320)
            fps: Frames per second (1-120)
            bitrate_kbps: Bitrate in kbps (100-100000)
            rtmp_url: RTMP streaming URL
            encoder_type: Encoder type (nvenc, vaapi, x264)

        Returns:
            List of validated command arguments

        Raises:
            CommandInjectionError: If any parameter is invalid
        """
        # Validate parameters using centralized validation
        try:
            width = self.input_validator.validate_dimension("width", width, min_val=1, max_val=7680)
            height = self.input_validator.validate_dimension("height", height, min_val=1, max_val=4320)
            fps = self.input_validator.validate_fps("fps", fps)
            bitrate_kbps = self.input_validator.validate_bitrate("bitrate_kbps", bitrate_kbps)
            rtmp_url = self.input_validator.validate_url("rtmp_url", rtmp_url, allowed_schemes=['rtmp'])
            encoder_type = self.input_validator.validate_enum("encoder_type", encoder_type, ['nvenc', 'vaapi', 'x264'])
        except ValidationError as e:
            raise CommandInjectionError(str(e))

        # Build pipeline with validated parameters
        pipeline_args = [
            'gst-launch-1.0',
            'fdsrc', 'do-timestamp=true', '!',
            'rawvideoparse', f'width={width}', f'height={height}',
            'format=rgb', f'framerate={fps}/1', '!',
            'videoconvert', '!',
            'queue', 'max-size-buffers=1', 'leaky=downstream', '!',
            'video/x-raw,format=NV12', '!'
        ]

        # Add encoder-specific elements
        if encoder_type == "nvenc":
            pipeline_args.extend([
                'nvh264enc', f'bitrate={bitrate_kbps}', 'preset=low-latency-hq', '!',
                'h264parse', 'config-interval=1', '!',
                'flvmux', 'streamable=true', '!',
                'rtmpsink', f'location={rtmp_url}', 'sync=false', 'async=false'
            ])
        elif encoder_type == "vaapi":
            pipeline_args.extend([
                'vaapih264enc', f'bitrate={bitrate_kbps}', 'quality-level=7', '!',
                'h264parse', 'config-interval=1', '!',
                'flvmux', 'streamable=true', '!',
                'rtmpsink', f'location={rtmp_url}', 'sync=false', 'async=false'
            ])
        else:  # x264
            pipeline_args.extend([
                'x264enc', f'bitrate={bitrate_kbps}', 'speed-preset=ultrafast',
                'tune=zerolatency', 'key-int-max=24', 'bframes=0', '!',
                'h264parse', 'config-interval=1', '!',
                'flvmux', 'streamable=true', '!',
                'rtmpsink', f'location={rtmp_url}', 'sync=false', 'async=false'
            ])

        return pipeline_args


def safe_subprocess_run(cmd_args: List[str], timeout: int = 30, **kwargs) -> subprocess.CompletedProcess:
    """
    Safely execute subprocess with validated arguments.

    Args:
        cmd_args: List of command arguments (no shell metacharacters)
        timeout: Timeout in seconds
        **kwargs: Additional subprocess.run arguments

    Returns:
        CompletedProcess result

    Raises:
        CommandInjectionError: If command contains dangerous elements
    """
    # Validate each argument for shell metacharacters
    dangerous_chars = ['&', '|', ';', '`', '$', '\n', '\r']

    for arg in cmd_args:
        if any(char in str(arg) for char in dangerous_chars):
            raise CommandInjectionError(f"Dangerous characters in command argument: {arg}")

    # Execute with shell=False for security
    kwargs.setdefault('shell', False)
    kwargs.setdefault('timeout', timeout)

    logger.debug(f"Executing safe subprocess: {' '.join(map(str, cmd_args))}")

    try:
        return subprocess.run(cmd_args, **kwargs)
    except subprocess.TimeoutExpired:
        logger.error(f"Subprocess timed out after {timeout} seconds")
        raise
    except Exception as e:
        logger.error(f"Subprocess execution failed: {e}")
        raise


def validate_gstreamer_element_availability(element: str) -> bool:
    """
    Safely check if GStreamer element is available.

    Args:
        element: Element name to check

    Returns:
        True if element is available, False otherwise
    """
    try:
        # Validate element name first
        GStreamerSecurityValidator.validate_element('gst-inspect-1.0')
        validated_element = GStreamerSecurityValidator.validate_element(element)

        cmd = ['gst-inspect-1.0', validated_element]
        result = safe_subprocess_run(cmd, timeout=5, capture_output=True)
        return result.returncode == 0

    except (CommandInjectionError, subprocess.TimeoutExpired, Exception):
        return False


# Factory functions for easy use
def create_secure_srt_pipeline(width: int, height: int, fps: int,
                              bitrate_kbps: int, srt_url: str,
                              encoder_type: str = "x264") -> List[str]:
    """Factory function to create secure SRT pipeline."""
    builder = GStreamerPipelineBuilder()
    return builder.create_srt_pipeline(width, height, fps, bitrate_kbps, srt_url, encoder_type)


def create_secure_rtmp_pipeline(width: int, height: int, fps: int,
                               bitrate_kbps: int, rtmp_url: str,
                               encoder_type: str = "x264") -> List[str]:
    """Factory function to create secure RTMP pipeline."""
    builder = GStreamerPipelineBuilder()
    return builder.create_rtmp_pipeline(width, height, fps, bitrate_kbps, rtmp_url, encoder_type)