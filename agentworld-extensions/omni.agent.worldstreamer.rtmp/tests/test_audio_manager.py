"""
Unit tests for AudioManager and AudioChannel classes.

Tests multi-channel audio configuration, volume control, and status tracking.
"""

import pytest
from omni.agent.worldstreamer.rtmp.streaming.audio_manager import (
    AudioChannel,
    AudioManager,
    ChannelStatus
)


class TestAudioChannel:
    """Test AudioChannel class."""

    def test_create_channel(self):
        """Test creating an audio channel."""
        channel = AudioChannel(
            channel_id=1,
            name="test_channel",
            srt_port=9001,
            default_volume=0.8,
            enabled=True
        )

        assert channel.channel_id == 1
        assert channel.name == "test_channel"
        assert channel.srt_port == 9001
        assert channel.volume == 0.8
        assert channel.enabled is True
        assert channel.status == ChannelStatus.INACTIVE

    def test_volume_validation(self):
        """Test volume validation and clamping."""
        # Volume too high
        channel = AudioChannel(
            channel_id=1,
            name="test",
            srt_port=9001,
            default_volume=1.5
        )
        assert channel.volume == 1.0

        # Volume too low
        channel = AudioChannel(
            channel_id=1,
            name="test",
            srt_port=9001,
            default_volume=-0.5
        )
        assert channel.volume == 0.0

    def test_set_volume(self):
        """Test setting channel volume."""
        channel = AudioChannel(
            channel_id=1,
            name="test",
            srt_port=9001
        )

        # Valid volume
        assert channel.set_volume(0.5) is True
        assert channel.volume == 0.5

        # Invalid volume (too high)
        assert channel.set_volume(1.5) is False
        assert channel.volume == 0.5  # Unchanged

        # Invalid volume (too low)
        assert channel.set_volume(-0.1) is False
        assert channel.volume == 0.5  # Unchanged

    def test_enable_disable(self):
        """Test enabling and disabling channel."""
        channel = AudioChannel(
            channel_id=1,
            name="test",
            srt_port=9001,
            enabled=False
        )

        assert channel.enabled is False

        # Enable
        assert channel.enable() is True
        assert channel.enabled is True

        # Disable
        assert channel.disable() is True
        assert channel.enabled is False
        assert channel.status == ChannelStatus.INACTIVE

    def test_status_tracking(self):
        """Test channel status tracking."""
        channel = AudioChannel(
            channel_id=1,
            name="test",
            srt_port=9001
        )

        # Initial status
        assert channel.status == ChannelStatus.INACTIVE
        assert channel.is_connected() is False

        # Set connected
        channel.set_status(ChannelStatus.CONNECTED)
        assert channel.is_connected() is True

        # Set disconnected
        channel.set_status(ChannelStatus.DISCONNECTED)
        assert channel.is_connected() is False

    def test_to_dict(self):
        """Test channel serialization to dict."""
        channel = AudioChannel(
            channel_id=1,
            name="narration",
            srt_port=9001,
            default_volume=0.8,
            enabled=True
        )
        channel.set_status(ChannelStatus.CONNECTED)

        data = channel.to_dict()

        assert data['id'] == 1
        assert data['name'] == "narration"
        assert data['srt_port'] == 9001
        assert data['volume'] == 0.8
        assert data['enabled'] is True
        assert data['status'] == "connected"
        assert data['connected'] is True


class TestAudioManager:
    """Test AudioManager class."""

    @pytest.fixture
    def sample_config(self):
        """Sample audio configuration."""
        return [
            {
                'id': 1,
                'name': 'narration',
                'srt_port': 9001,
                'default_volume': 0.8,
                'enabled': True
            },
            {
                'id': 2,
                'name': 'background',
                'srt_port': 9002,
                'default_volume': 0.3,
                'enabled': True
            },
            {
                'id': 3,
                'name': 'commentary',
                'srt_port': 9003,
                'default_volume': 1.0,
                'enabled': False  # Disabled
            },
            {
                'id': 4,
                'name': 'music',
                'srt_port': 9004,
                'default_volume': 0.4,
                'enabled': True
            }
        ]

    def test_initialize_manager(self, sample_config):
        """Test initializing audio manager."""
        manager = AudioManager(sample_config)

        assert manager.is_enabled() is True
        assert manager.get_channel_count() == 4
        assert manager.get_enabled_channel_count() == 3

    def test_get_channel(self, sample_config):
        """Test getting individual channels."""
        manager = AudioManager(sample_config)

        # Valid channel
        channel = manager.get_channel(1)
        assert channel is not None
        assert channel.name == "narration"
        assert channel.srt_port == 9001

        # Invalid channel
        channel = manager.get_channel(99)
        assert channel is None

    def test_get_enabled_channels(self, sample_config):
        """Test getting only enabled channels."""
        manager = AudioManager(sample_config)

        enabled = manager.get_enabled_channels()
        assert len(enabled) == 3

        # Check that commentary (disabled) is not in list
        names = [ch.name for ch in enabled]
        assert "narration" in names
        assert "background" in names
        assert "music" in names
        assert "commentary" not in names

    def test_set_channel_volume(self, sample_config):
        """Test setting channel volume."""
        manager = AudioManager(sample_config)

        # Valid volume change
        result = manager.set_channel_volume(1, 0.5)
        assert result['success'] is True
        assert manager.get_channel(1).volume == 0.5

        # Invalid channel
        result = manager.set_channel_volume(99, 0.5)
        assert result['success'] is False

        # Invalid volume
        result = manager.set_channel_volume(1, 1.5)
        assert result['success'] is False

    def test_enable_disable_channel(self, sample_config):
        """Test enabling and disabling channels."""
        manager = AudioManager(sample_config)

        # Enable disabled channel
        result = manager.enable_channel(3)
        assert result['success'] is True
        assert manager.get_enabled_channel_count() == 4

        # Disable enabled channel
        result = manager.disable_channel(1)
        assert result['success'] is True
        assert manager.get_enabled_channel_count() == 3

    def test_get_all_channels_status(self, sample_config):
        """Test getting status for all channels."""
        manager = AudioManager(sample_config)

        status = manager.get_all_channels_status()

        assert status['success'] is True
        assert status['enabled'] is True
        assert status['total_channels'] == 4
        assert status['enabled_channels'] == 3
        assert len(status['channels']) == 4

    def test_validate_configuration(self, sample_config):
        """Test configuration validation."""
        manager = AudioManager(sample_config)

        result = manager.validate_configuration()

        assert result['valid'] is True
        assert len(result['errors']) == 0
        assert result['total_channels'] == 4
        assert result['enabled_channels'] == 3

    def test_duplicate_ports_validation(self):
        """Test validation catches duplicate ports."""
        config = [
            {'id': 1, 'name': 'ch1', 'srt_port': 9001, 'default_volume': 1.0, 'enabled': True},
            {'id': 2, 'name': 'ch2', 'srt_port': 9001, 'default_volume': 1.0, 'enabled': True}  # Duplicate
        ]

        manager = AudioManager(config)
        result = manager.validate_configuration()

        assert result['valid'] is False
        assert any('Duplicate' in err for err in result['errors'])

    def test_gstreamer_audio_elements(self, sample_config):
        """Test generating GStreamer audio pipeline elements."""
        manager = AudioManager(sample_config)

        elements = manager.get_gstreamer_audio_elements()

        # Should have 3 enabled channels (commentary is disabled)
        assert len(elements) == 3

        # Check that SRT URIs are included
        assert any('srt://0.0.0.0:9001' in elem for elem in elements)
        assert any('srt://0.0.0.0:9002' in elem for elem in elements)
        assert any('srt://0.0.0.0:9004' in elem for elem in elements)

        # Check that volume settings are included
        assert any('volume=0.8' in elem for elem in elements)
        assert any('volume=0.3' in elem for elem in elements)
        assert any('volume=0.4' in elem for elem in elements)

    def test_gstreamer_mixer_element(self, sample_config):
        """Test generating GStreamer mixer element."""
        manager = AudioManager(sample_config)

        mixer = manager.get_gstreamer_mixer_element()

        assert 'audiomixer' in mixer
        assert 'voaacenc' in mixer
        assert 'bitrate=160000' in mixer

    def test_empty_manager(self):
        """Test manager with no channels."""
        manager = AudioManager([])

        assert manager.is_enabled() is False
        assert manager.get_channel_count() == 0
        assert manager.get_enabled_channel_count() == 0

        elements = manager.get_gstreamer_audio_elements()
        assert len(elements) == 0

        mixer = manager.get_gstreamer_mixer_element()
        assert mixer == ""

    def test_reset(self, sample_config):
        """Test resetting audio manager."""
        manager = AudioManager(sample_config)

        # Change some volumes
        manager.set_channel_volume(1, 0.5)
        manager.set_channel_volume(2, 0.6)

        # Reset
        manager.reset()

        # Should be back to defaults
        assert manager.get_channel(1).volume == 0.8
        assert manager.get_channel(2).volume == 0.3
        assert manager.get_channel(1).status == ChannelStatus.INACTIVE

    def test_health_status(self, sample_config):
        """Test health status reporting."""
        manager = AudioManager(sample_config)

        # Mark some channels as connected
        manager.update_channel_status(1, ChannelStatus.CONNECTED)
        manager.update_channel_status(2, ChannelStatus.CONNECTED)

        health = manager.get_health_status()

        assert health['functional'] is True
        assert health['enabled'] is True
        assert health['total_channels'] == 4
        assert health['enabled_channels'] == 3
        assert health['connected_channels'] == 2


if __name__ == '__main__':
    pytest.main([__file__, '-v'])