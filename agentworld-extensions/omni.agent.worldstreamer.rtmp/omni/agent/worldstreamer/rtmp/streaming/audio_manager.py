"""
Audio Manager for WorldStreamer Multi-Channel Audio

Manages multi-channel audio input configuration for RTMP streaming.
Supports SRT audio sources with individual volume control and mixing.
"""

import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class ChannelStatus(Enum):
    """Audio channel status states."""
    INACTIVE = "inactive"
    ACTIVE = "active"
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    ERROR = "error"


@dataclass
class AudioChannel:
    """
    Represents a single audio input channel.

    Attributes:
        channel_id: Unique channel identifier (1-based)
        name: Human-readable channel name
        srt_port: SRT listener port for this channel
        default_volume: Default volume level (0.0 to 1.0)
        enabled: Whether channel is enabled
        volume: Current volume level (0.0 to 1.0)
        status: Current channel status
    """
    channel_id: int
    name: str
    srt_port: int
    default_volume: float = 1.0
    enabled: bool = True
    volume: float = None
    status: ChannelStatus = ChannelStatus.INACTIVE

    def __post_init__(self):
        """Initialize volume to default if not set."""
        if self.volume is None:
            self.volume = self.default_volume

        # Validate volume range
        if not 0.0 <= self.volume <= 1.0:
            logger.warning(f"Channel {self.channel_id} volume {self.volume} out of range, clamping to [0.0, 1.0]")
            self.volume = max(0.0, min(1.0, self.volume))

        if not 0.0 <= self.default_volume <= 1.0:
            logger.warning(f"Channel {self.channel_id} default_volume {self.default_volume} out of range, clamping to [0.0, 1.0]")
            self.default_volume = max(0.0, min(1.0, self.default_volume))

    def set_volume(self, volume: float) -> bool:
        """
        Set channel volume.

        Args:
            volume: Volume level (0.0 to 1.0)

        Returns:
            True if volume set successfully, False otherwise
        """
        if not 0.0 <= volume <= 1.0:
            logger.error(f"Invalid volume {volume} for channel {self.channel_id}, must be 0.0-1.0")
            return False

        self.volume = volume
        logger.info(f"Channel {self.channel_id} ({self.name}) volume set to {volume}")
        return True

    def enable(self) -> bool:
        """
        Enable this audio channel.

        Returns:
            True if enabled successfully
        """
        self.enabled = True
        logger.info(f"Channel {self.channel_id} ({self.name}) enabled")
        return True

    def disable(self) -> bool:
        """
        Disable this audio channel.

        Returns:
            True if disabled successfully
        """
        self.enabled = False
        self.status = ChannelStatus.INACTIVE
        logger.info(f"Channel {self.channel_id} ({self.name}) disabled")
        return True

    def set_status(self, status: ChannelStatus):
        """Set channel status."""
        self.status = status

    def is_connected(self) -> bool:
        """Check if channel is connected."""
        return self.status == ChannelStatus.CONNECTED

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert channel to dictionary representation.

        Returns:
            Dict with channel information
        """
        return {
            'id': self.channel_id,
            'name': self.name,
            'srt_port': self.srt_port,
            'volume': self.volume,
            'default_volume': self.default_volume,
            'enabled': self.enabled,
            'status': self.status.value,
            'connected': self.is_connected()
        }


class AudioManager:
    """
    Manages multi-channel audio configuration and status.

    Handles audio channel configuration, volume control, and
    status tracking for WorldStreamer RTMP streaming.
    """

    def __init__(self, channels: Optional[List[Dict[str, Any]]] = None):
        """
        Initialize audio manager.

        Args:
            channels: List of channel configuration dictionaries
        """
        self._channels: Dict[int, AudioChannel] = {}
        self._enabled = False

        # Initialize channels from configuration
        if channels:
            for ch_config in channels:
                try:
                    channel = AudioChannel(
                        channel_id=ch_config['id'],
                        name=ch_config['name'],
                        srt_port=ch_config['srt_port'],
                        default_volume=ch_config.get('default_volume', 1.0),
                        enabled=ch_config.get('enabled', True)
                    )
                    self._channels[channel.channel_id] = channel
                    logger.info(f"Initialized audio channel {channel.channel_id}: {channel.name} (port {channel.srt_port})")
                except Exception as e:
                    logger.error(f"Failed to initialize audio channel from config: {e}")

        # Enable audio manager if we have channels
        self._enabled = len(self._channels) > 0

        if self._enabled:
            logger.info(f"AudioManager initialized with {len(self._channels)} channels")
        else:
            logger.info("AudioManager initialized with no channels (audio disabled)")

    def is_enabled(self) -> bool:
        """Check if audio manager is enabled."""
        return self._enabled and len(self._channels) > 0

    def get_channel(self, channel_id: int) -> Optional[AudioChannel]:
        """
        Get audio channel by ID.

        Args:
            channel_id: Channel identifier

        Returns:
            AudioChannel if found, None otherwise
        """
        return self._channels.get(channel_id)

    def get_all_channels(self) -> List[AudioChannel]:
        """
        Get all audio channels.

        Returns:
            List of AudioChannel objects
        """
        return list(self._channels.values())

    def get_enabled_channels(self) -> List[AudioChannel]:
        """
        Get all enabled audio channels.

        Returns:
            List of enabled AudioChannel objects
        """
        return [ch for ch in self._channels.values() if ch.enabled]

    def get_channel_count(self) -> int:
        """Get total number of channels."""
        return len(self._channels)

    def get_enabled_channel_count(self) -> int:
        """Get number of enabled channels."""
        return len(self.get_enabled_channels())

    def get_channel_status(self, channel_id: int) -> Dict[str, Any]:
        """
        Get status for specific channel.

        Args:
            channel_id: Channel identifier

        Returns:
            Dict with channel status, or error dict if not found
        """
        channel = self.get_channel(channel_id)
        if not channel:
            return {
                'success': False,
                'error': f'Channel {channel_id} not found'
            }

        return {
            'success': True,
            'channel': channel.to_dict()
        }

    def get_all_channels_status(self) -> Dict[str, Any]:
        """
        Get status for all channels.

        Returns:
            Dict with all channels status
        """
        return {
            'success': True,
            'enabled': self.is_enabled(),
            'total_channels': self.get_channel_count(),
            'enabled_channels': self.get_enabled_channel_count(),
            'channels': [ch.to_dict() for ch in self._channels.values()]
        }

    def set_channel_volume(self, channel_id: int, volume: float) -> Dict[str, Any]:
        """
        Set volume for specific channel.

        Args:
            channel_id: Channel identifier
            volume: Volume level (0.0 to 1.0)

        Returns:
            Dict with operation result
        """
        channel = self.get_channel(channel_id)
        if not channel:
            return {
                'success': False,
                'error': f'Channel {channel_id} not found'
            }

        if channel.set_volume(volume):
            return {
                'success': True,
                'message': f'Channel {channel_id} volume set to {volume}',
                'channel': channel.to_dict()
            }
        else:
            return {
                'success': False,
                'error': f'Failed to set volume for channel {channel_id}'
            }

    def enable_channel(self, channel_id: int) -> Dict[str, Any]:
        """
        Enable specific channel.

        Args:
            channel_id: Channel identifier

        Returns:
            Dict with operation result
        """
        channel = self.get_channel(channel_id)
        if not channel:
            return {
                'success': False,
                'error': f'Channel {channel_id} not found'
            }

        if channel.enable():
            return {
                'success': True,
                'message': f'Channel {channel_id} enabled',
                'channel': channel.to_dict()
            }
        else:
            return {
                'success': False,
                'error': f'Failed to enable channel {channel_id}'
            }

    def disable_channel(self, channel_id: int) -> Dict[str, Any]:
        """
        Disable specific channel.

        Args:
            channel_id: Channel identifier

        Returns:
            Dict with operation result
        """
        channel = self.get_channel(channel_id)
        if not channel:
            return {
                'success': False,
                'error': f'Channel {channel_id} not found'
            }

        if channel.disable():
            return {
                'success': True,
                'message': f'Channel {channel_id} disabled',
                'channel': channel.to_dict()
            }
        else:
            return {
                'success': False,
                'error': f'Failed to disable channel {channel_id}'
            }

    def update_channel_status(self, channel_id: int, status: ChannelStatus) -> bool:
        """
        Update channel connection status.

        Args:
            channel_id: Channel identifier
            status: New channel status

        Returns:
            True if updated successfully
        """
        channel = self.get_channel(channel_id)
        if not channel:
            logger.warning(f"Cannot update status for non-existent channel {channel_id}")
            return False

        channel.set_status(status)
        logger.debug(f"Channel {channel_id} status updated to {status.value}")
        return True

    def get_gstreamer_audio_elements(self) -> List[str]:
        """
        Generate GStreamer pipeline elements for enabled audio channels.

        Returns:
            List of GStreamer pipeline element strings for audio mixing
        """
        enabled_channels = self.get_enabled_channels()

        if not enabled_channels:
            logger.info("No enabled audio channels, returning empty pipeline elements")
            return []

        elements = []

        # Build audio source elements for each enabled channel
        for channel in enabled_channels:
            # SRT source for this channel
            srt_uri = f"srt://0.0.0.0:{channel.srt_port}?mode=listener"

            # Channel pipeline: srtsrc → decode → convert → resample → volume → mixer
            channel_elements = [
                f'srtsrc uri="{srt_uri}"',
                'decodebin',
                'audioconvert',
                'audioresample',
                f'volume volume={channel.volume}',
                'audio/x-raw,channels=2,rate=48000',
                'mix.'
            ]

            elements.append(' ! '.join(channel_elements))
            logger.debug(f"Added GStreamer elements for channel {channel.channel_id} ({channel.name})")

        logger.info(f"Generated GStreamer audio pipeline for {len(enabled_channels)} enabled channels")
        return elements

    def get_gstreamer_mixer_element(self) -> str:
        """
        Get GStreamer audio mixer element.

        Returns:
            Audio mixer element string
        """
        if not self.get_enabled_channels():
            return ""

        # Audio mixer with AAC encoding
        return "audiomixer name=mix ! audioconvert ! voaacenc bitrate=160000 ! aacparse ! mux."

    def validate_configuration(self) -> Dict[str, Any]:
        """
        Validate audio manager configuration.

        Returns:
            Dict with validation results
        """
        errors = []
        warnings = []

        # Check for duplicate ports
        ports = [ch.srt_port for ch in self._channels.values()]
        if len(ports) != len(set(ports)):
            errors.append("Duplicate SRT ports detected in audio channels")

        # Check for valid port ranges
        for channel in self._channels.values():
            if not 1024 <= channel.srt_port <= 65535:
                warnings.append(f"Channel {channel.channel_id} port {channel.srt_port} outside recommended range (1024-65535)")

        # Check for enabled channels
        if not self.get_enabled_channels():
            warnings.append("No audio channels enabled")

        return {
            'valid': len(errors) == 0,
            'errors': errors,
            'warnings': warnings,
            'total_channels': self.get_channel_count(),
            'enabled_channels': self.get_enabled_channel_count()
        }

    def reset(self):
        """Reset all channels to default state."""
        for channel in self._channels.values():
            channel.volume = channel.default_volume
            channel.status = ChannelStatus.INACTIVE

        logger.info("AudioManager reset to default state")

    def get_health_status(self) -> Dict[str, Any]:
        """
        Get audio manager health status.

        Returns:
            Dict with health information
        """
        return {
            'functional': True,
            'enabled': self.is_enabled(),
            'total_channels': self.get_channel_count(),
            'enabled_channels': self.get_enabled_channel_count(),
            'connected_channels': len([ch for ch in self._channels.values() if ch.is_connected()]),
            'channels': [ch.to_dict() for ch in self._channels.values()]
        }