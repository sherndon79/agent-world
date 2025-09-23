"""
Centralized input validation framework for Agent World Extensions.

Provides standardized validation for common input types used across
all extensions to ensure consistent security and data integrity.

Usage:
    from agent_world_validation import InputValidator, ValidationError

    validator = InputValidator()
    safe_width = validator.validate_dimension('width', user_input, min_val=1, max_val=7680)
    safe_url = validator.validate_url(user_input, allowed_schemes=['http', 'https'])
"""

import re
import json
import logging
from typing import Any, List, Dict, Union, Optional, Tuple
from urllib.parse import urlparse
from pathlib import Path
import ipaddress

logger = logging.getLogger(__name__)


class ValidationError(ValueError):
    """Raised when input validation fails."""
    pass


class InputValidator:
    """Centralized input validation with security-focused checks."""

    # Common regex patterns for validation
    PATTERNS = {
        'alphanumeric': r'^[a-zA-Z0-9]+$',
        'alphanumeric_underscore': r'^[a-zA-Z0-9_]+$',
        'alphanumeric_dash': r'^[a-zA-Z0-9\-]+$',
        'numeric': r'^\d+$',
        'float': r'^-?\d+\.?\d*$',
        'fraction': r'^\d+/\d+$',
        'boolean_string': r'^(true|false)$',
        'uuid': r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$',
        'hex_color': r'^#[0-9a-fA-F]{6}$',
        'safe_filename': r'^[a-zA-Z0-9._\-]+$',
        'safe_directory': r'^[a-zA-Z0-9._/\-]+$',
        'usd_path': r'^/[a-zA-Z0-9_/]+$',
        'ip_address': r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$',
        'port': r'^([1-9]\d{0,3}|[1-5]\d{4}|6[0-4]\d{3}|65[0-4]\d{2}|655[0-2]\d|6553[0-5])$'
    }

    # Dangerous characters for different contexts
    DANGEROUS_CHARS = {
        'shell': ['&', '|', ';', '`', '$', '(', ')', '<', '>', '\n', '\r', '\\'],
        'path': ['..', '~', '$', '`', ';', '&', '|', '\n', '\r'],
        'sql': ["'", '"', ';', '--', '/*', '*/', 'xp_', 'sp_'],
        'xss': ['<script', '</script', 'javascript:', 'data:', 'vbscript:', 'onload=', 'onerror='],
        'url': ['|', ';', '`', '$', '(', ')', '<', '>', '\n', '\r', '\\']  # Allow & for query params
    }

    def __init__(self, config: Dict[str, Any] = None):
        """
        Initialize validator with optional configuration.

        Args:
            config: Optional configuration dictionary
        """
        self.config = config or {}
        self.strict_mode = self.config.get('strict_validation', True)

    def validate_string(self, field_name: str, value: Any,
                       pattern: str = None,
                       min_length: int = 0,
                       max_length: int = 1000,
                       allow_empty: bool = False,
                       dangerous_chars: str = None) -> str:
        """
        Validate string input with pattern matching and safety checks.

        Args:
            field_name: Name of the field being validated
            value: Value to validate
            pattern: Regex pattern to match (use PATTERNS keys or custom regex)
            min_length: Minimum string length
            max_length: Maximum string length
            allow_empty: Whether empty strings are allowed
            dangerous_chars: Type of dangerous characters to check ('shell', 'path', 'sql', 'xss')

        Returns:
            Validated string value

        Raises:
            ValidationError: If validation fails
        """
        # Type check
        if not isinstance(value, str):
            try:
                value = str(value)
            except Exception:
                raise ValidationError(f"{field_name} must be a string, got {type(value).__name__}")

        # Empty check
        if not value:
            if allow_empty:
                return value
            raise ValidationError(f"{field_name} cannot be empty")

        # Length check
        if len(value) < min_length:
            raise ValidationError(f"{field_name} must be at least {min_length} characters, got {len(value)}")

        if len(value) > max_length:
            raise ValidationError(f"{field_name} must be at most {max_length} characters, got {len(value)}")

        # Dangerous character check
        if dangerous_chars and dangerous_chars in self.DANGEROUS_CHARS:
            for char in self.DANGEROUS_CHARS[dangerous_chars]:
                if char in value:
                    raise ValidationError(f"{field_name} contains dangerous character: {char}")

        # Pattern check
        if pattern:
            # Use predefined pattern if it exists, otherwise use as regex
            regex_pattern = self.PATTERNS.get(pattern, pattern)
            if not re.match(regex_pattern, value, re.IGNORECASE if pattern in ['uuid', 'hex_color'] else 0):
                raise ValidationError(f"{field_name} does not match required pattern: {pattern}")

        return value

    def validate_numeric(self, field_name: str, value: Any,
                        min_val: Union[int, float] = None,
                        max_val: Union[int, float] = None,
                        integer_only: bool = False) -> Union[int, float]:
        """
        Validate numeric input with range checks.

        Args:
            field_name: Name of the field being validated
            value: Value to validate
            min_val: Minimum allowed value
            max_val: Maximum allowed value
            integer_only: Whether to enforce integer type

        Returns:
            Validated numeric value

        Raises:
            ValidationError: If validation fails
        """
        # Type conversion
        try:
            if integer_only:
                if isinstance(value, str) and not re.match(r'^-?\d+$', value):
                    raise ValidationError(f"{field_name} must be a valid integer, got {value}")
                num_value = int(value)
            else:
                if isinstance(value, str) and not re.match(r'^-?\d+\.?\d*$', value):
                    raise ValidationError(f"{field_name} must be a valid number, got {value}")
                num_value = float(value)
        except (ValueError, TypeError) as e:
            raise ValidationError(f"{field_name} must be a valid {'integer' if integer_only else 'number'}, got {value}")

        # Range check
        if min_val is not None and num_value < min_val:
            raise ValidationError(f"{field_name} must be at least {min_val}, got {num_value}")

        if max_val is not None and num_value > max_val:
            raise ValidationError(f"{field_name} must be at most {max_val}, got {num_value}")

        return num_value

    def validate_dimension(self, field_name: str, value: Any,
                          min_val: int = 1, max_val: int = 7680) -> int:
        """Validate video/image dimension (width/height)."""
        return int(self.validate_numeric(field_name, value, min_val, max_val, integer_only=True))

    def validate_fps(self, field_name: str, value: Any,
                     min_val: int = 1, max_val: int = 120) -> int:
        """Validate frames per second value."""
        return int(self.validate_numeric(field_name, value, min_val, max_val, integer_only=True))

    def validate_bitrate(self, field_name: str, value: Any,
                        min_val: int = 100, max_val: int = 100000) -> int:
        """Validate bitrate value in kbps."""
        return int(self.validate_numeric(field_name, value, min_val, max_val, integer_only=True))

    def validate_boolean(self, field_name: str, value: Any) -> bool:
        """
        Validate boolean input with multiple accepted formats.

        Args:
            field_name: Name of the field being validated
            value: Value to validate

        Returns:
            Boolean value

        Raises:
            ValidationError: If validation fails
        """
        if isinstance(value, bool):
            return value

        if isinstance(value, str):
            lower_val = value.lower()
            if lower_val in ['true', '1', 'yes', 'on']:
                return True
            elif lower_val in ['false', '0', 'no', 'off']:
                return False

        if isinstance(value, (int, float)):
            return bool(value)

        raise ValidationError(f"{field_name} must be a boolean value, got {value}")

    def validate_url(self, field_name: str, value: Any,
                     allowed_schemes: List[str] = None,
                     allow_localhost: bool = True,
                     allow_private_ips: bool = False) -> str:
        """
        Validate URL with scheme and security checks.

        Args:
            field_name: Name of the field being validated
            value: URL to validate
            allowed_schemes: List of allowed URL schemes
            allow_localhost: Whether localhost URLs are allowed
            allow_private_ips: Whether private IP addresses are allowed

        Returns:
            Validated URL

        Raises:
            ValidationError: If validation fails
        """
        url_str = self.validate_string(field_name, value, dangerous_chars='url', max_length=2048)

        if allowed_schemes is None:
            allowed_schemes = ['http', 'https', 'srt', 'rtmp']

        try:
            parsed = urlparse(url_str)
        except Exception as e:
            raise ValidationError(f"{field_name} is not a valid URL: {e}")

        # Scheme validation
        if parsed.scheme not in allowed_schemes:
            raise ValidationError(f"{field_name} scheme must be one of {allowed_schemes}, got {parsed.scheme}")

        # Host validation
        if parsed.hostname:
            # Check for localhost
            if not allow_localhost and parsed.hostname.lower() in ['localhost', '127.0.0.1', '::1']:
                raise ValidationError(f"{field_name} localhost URLs not allowed")

            # Check for private IPs
            if not allow_private_ips:
                try:
                    ip = ipaddress.ip_address(parsed.hostname)
                    if ip.is_private:
                        raise ValidationError(f"{field_name} private IP addresses not allowed")
                except ValueError:
                    # Not an IP address, continue with hostname validation
                    pass

        return url_str

    def validate_color(self, field_name: str, value: Any) -> List[float]:
        """
        Validate color input in various formats.

        Args:
            field_name: Name of the field being validated
            value: Color value (hex, rgb list, or rgb tuple)

        Returns:
            RGB color as list of floats [0.0-1.0]

        Raises:
            ValidationError: If validation fails
        """
        if isinstance(value, str):
            # Hex color validation
            hex_color = self.validate_string(field_name, value, pattern='hex_color')
            # Convert hex to RGB
            hex_color = hex_color.lstrip('#')
            r = int(hex_color[0:2], 16) / 255.0
            g = int(hex_color[2:4], 16) / 255.0
            b = int(hex_color[4:6], 16) / 255.0
            return [r, g, b]

        elif isinstance(value, (list, tuple)):
            if len(value) != 3:
                raise ValidationError(f"{field_name} RGB color must have 3 components, got {len(value)}")

            rgb = []
            for i, component in enumerate(value):
                comp_val = self.validate_numeric(f"{field_name}[{i}]", component, 0.0, 1.0)
                rgb.append(float(comp_val))
            return rgb

        else:
            raise ValidationError(f"{field_name} must be hex string or RGB list/tuple, got {type(value).__name__}")

    def validate_position(self, field_name: str, value: Any,
                         dimension: int = 3) -> List[float]:
        """
        Validate position/coordinate input.

        Args:
            field_name: Name of the field being validated
            value: Position as list or tuple
            dimension: Expected number of dimensions (2D or 3D)

        Returns:
            Position as list of floats

        Raises:
            ValidationError: If validation fails
        """
        if not isinstance(value, (list, tuple)):
            raise ValidationError(f"{field_name} must be a list or tuple, got {type(value).__name__}")

        if len(value) != dimension:
            raise ValidationError(f"{field_name} must have {dimension} components, got {len(value)}")

        position = []
        for i, coord in enumerate(value):
            coord_val = self.validate_numeric(f"{field_name}[{i}]", coord)
            position.append(float(coord_val))

        return position

    def validate_usd_path(self, field_name: str, value: Any) -> str:
        """
        Validate USD scene path.

        Args:
            field_name: Name of the field being validated
            value: USD path to validate

        Returns:
            Validated USD path

        Raises:
            ValidationError: If validation fails
        """
        path_str = self.validate_string(field_name, value, max_length=500, dangerous_chars='path')

        # USD paths should start with /
        if not path_str.startswith('/'):
            raise ValidationError(f"{field_name} USD path must start with '/', got {path_str}")

        # Check for valid USD path characters
        if not re.match(r'^/[a-zA-Z0-9_/]+$', path_str):
            raise ValidationError(f"{field_name} contains invalid USD path characters: {path_str}")

        return path_str

    def validate_file_path(self, field_name: str, value: Any,
                          allowed_extensions: List[str] = None,
                          check_exists: bool = False) -> str:
        """
        Validate file path with security checks.

        Args:
            field_name: Name of the field being validated
            value: File path to validate
            allowed_extensions: List of allowed file extensions
            check_exists: Whether to check if file exists

        Returns:
            Validated file path

        Raises:
            ValidationError: If validation fails
        """
        path_str = self.validate_string(field_name, value, max_length=1000, dangerous_chars='path')

        # Path traversal check
        if '..' in path_str:
            raise ValidationError(f"{field_name} contains path traversal: {path_str}")

        # Extension validation
        if allowed_extensions:
            path_obj = Path(path_str)
            if path_obj.suffix.lower() not in allowed_extensions:
                raise ValidationError(f"{field_name} must have extension in {allowed_extensions}, got {path_obj.suffix}")

        # Existence check
        if check_exists:
            path_obj = Path(path_str)
            if not path_obj.exists():
                raise ValidationError(f"{field_name} file does not exist: {path_str}")

        return path_str

    def validate_json(self, field_name: str, value: Any) -> Dict[str, Any]:
        """
        Validate JSON input.

        Args:
            field_name: Name of the field being validated
            value: JSON string or dict to validate

        Returns:
            Parsed JSON as dictionary

        Raises:
            ValidationError: If validation fails
        """
        if isinstance(value, dict):
            return value

        if isinstance(value, str):
            try:
                return json.loads(value)
            except json.JSONDecodeError as e:
                raise ValidationError(f"{field_name} is not valid JSON: {e}")

        raise ValidationError(f"{field_name} must be JSON string or dict, got {type(value).__name__}")

    def validate_enum(self, field_name: str, value: Any,
                     allowed_values: List[Any]) -> Any:
        """
        Validate enum/choice input.

        Args:
            field_name: Name of the field being validated
            value: Value to validate
            allowed_values: List of allowed values

        Returns:
            Validated value

        Raises:
            ValidationError: If validation fails
        """
        if value not in allowed_values:
            raise ValidationError(f"{field_name} must be one of {allowed_values}, got {value}")

        return value

    def validate_batch(self, validations: List[Tuple[str, Any, str, Dict[str, Any]]]) -> Dict[str, Any]:
        """
        Validate multiple fields in batch.

        Args:
            validations: List of (field_name, value, validator_method, kwargs) tuples

        Returns:
            Dictionary of validated values

        Raises:
            ValidationError: If any validation fails
        """
        results = {}
        errors = []

        for field_name, value, method_name, kwargs in validations:
            try:
                method = getattr(self, method_name)
                results[field_name] = method(field_name, value, **kwargs)
            except ValidationError as e:
                errors.append(str(e))

        if errors:
            raise ValidationError(f"Validation failed: {'; '.join(errors)}")

        return results


# Factory functions for common validation patterns
def create_gstreamer_validator() -> InputValidator:
    """Create validator configured for GStreamer parameters."""
    return InputValidator({
        'strict_validation': True
    })


def create_web_validator() -> InputValidator:
    """Create validator configured for web input."""
    return InputValidator({
        'strict_validation': True
    })


def create_asset_validator() -> InputValidator:
    """Create validator configured for asset management."""
    return InputValidator({
        'strict_validation': True
    })