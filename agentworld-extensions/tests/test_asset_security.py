"""
Security tests for asset path validation.

Tests the secure asset path validation system to ensure it prevents
directory traversal attacks while allowing legitimate asset access.
"""

import pytest
import tempfile
import os
from pathlib import Path
from unittest.mock import Mock

from agent_world_asset_security import AssetPathValidator, create_asset_validator


class TestAssetPathValidator:
    """Test suite for secure asset path validation."""

    def setup_method(self):
        """Set up test environment with temporary directories and mock config."""
        # Create temporary directories for testing
        self.temp_dir = tempfile.mkdtemp()
        self.assets_dir = os.path.join(self.temp_dir, 'assets')
        self.models_dir = os.path.join(self.temp_dir, 'models')

        os.makedirs(self.assets_dir)
        os.makedirs(self.models_dir)

        # Create test assets
        self.test_asset = os.path.join(self.assets_dir, 'test_model.usd')
        with open(self.test_asset, 'w') as f:
            f.write('# Test USD file')

        # Create nested directory structure
        nested_dir = os.path.join(self.assets_dir, 'demo', 'Food')
        os.makedirs(nested_dir)
        self.nested_asset = os.path.join(nested_dir, 'mac_and_cheese.usdz')
        with open(self.nested_asset, 'w') as f:
            f.write('# Test nested USD file')

        # Mock configuration
        self.mock_config = Mock()
        self.mock_config.get.side_effect = self._mock_config_get

        self.validator = AssetPathValidator(self.mock_config)

    def teardown_method(self):
        """Clean up temporary directories."""
        import shutil
        shutil.rmtree(self.temp_dir)

    def _mock_config_get(self, key, default=None):
        """Mock configuration getter."""
        config_values = {
            'asset_search_paths': [self.assets_dir, self.models_dir],
            'allow_absolute_asset_paths': False,
            'validate_asset_paths': True,
            'max_asset_file_size_mb': 1,  # 1MB limit for testing
            'log_asset_access': False,
            'allowed_asset_extensions': ['.usd', '.usdz', '.usda']
        }
        return config_values.get(key, default)

    def test_valid_asset_paths(self):
        """Test that valid asset paths are accepted."""
        valid_paths = [
            'test_model.usd',
            'demo/Food/mac_and_cheese.usdz'
        ]

        for path in valid_paths:
            assert self.validator.asset_exists(path), f"Valid path rejected: {path}"

    def test_path_traversal_prevention(self):
        """Test that path traversal attempts are blocked."""
        dangerous_paths = [
            '../../../etc/passwd',
            '..\\..\\..\\windows\\system32\\config\\sam',
            'assets/../../../etc/shadow',
            'demo/../../etc/hosts',
            '../outside_asset.usd'
        ]

        for path in dangerous_paths:
            with pytest.raises(ValueError, match="Path traversal detected"):
                self.validator.validate_asset_path(path)

    def test_absolute_path_prevention(self):
        """Test that absolute paths are blocked when not allowed."""
        absolute_paths = [
            '/etc/passwd',
            '/home/user/secret.usd',
            '/tmp/malicious.usd'
        ]

        for path in absolute_paths:
            with pytest.raises(ValueError, match="Absolute paths not allowed"):
                self.validator.validate_asset_path(path)

        # Test Windows path separately
        windows_path = 'C:\\Windows\\System32\\drivers\\etc\\hosts'
        with pytest.raises(ValueError, match="Drive letters not allowed"):
            self.validator.validate_asset_path(windows_path)

    def test_null_byte_prevention(self):
        """Test that null bytes in paths are blocked."""
        malicious_paths = [
            'test\x00.usd',
            'demo/Food/mac\x00_and_cheese.usdz'
        ]

        for path in malicious_paths:
            with pytest.raises(ValueError, match="Null bytes not allowed"):
                self.validator.validate_asset_path(path)

    def test_file_extension_validation(self):
        """Test file extension validation when enabled."""
        # Create a file with disallowed extension
        bad_extension_file = os.path.join(self.assets_dir, 'script.py')
        with open(bad_extension_file, 'w') as f:
            f.write('# Malicious script')

        with pytest.raises(ValueError, match="File extension .py not allowed"):
            self.validator.validate_asset_path('script.py')

    def test_file_size_limits(self):
        """Test that large files are rejected."""
        # Create a large file (2MB, over our 1MB limit)
        large_file = os.path.join(self.assets_dir, 'large_model.usd')
        with open(large_file, 'wb') as f:
            f.write(b'x' * (2 * 1024 * 1024))  # 2MB

        assert not self.validator.asset_exists('large_model.usd')

    def test_get_asset_full_path(self):
        """Test getting full path to valid assets."""
        full_path = self.validator.get_asset_full_path('test_model.usd')
        assert full_path == self.test_asset

        # Test with nested path
        full_path = self.validator.get_asset_full_path('demo/Food/mac_and_cheese.usdz')
        assert full_path == self.nested_asset

        # Test with invalid path
        full_path = self.validator.get_asset_full_path('../../../etc/passwd')
        assert full_path is None

    def test_list_available_assets(self):
        """Test listing available assets."""
        assets = self.validator.list_available_assets()
        asset_names = [os.path.basename(path) for path in assets]

        assert 'test_model.usd' in asset_names
        assert 'mac_and_cheese.usdz' in asset_names

        # Test with path prefix
        food_assets = self.validator.list_available_assets('demo/Food')
        assert any('mac_and_cheese.usdz' in path for path in food_assets)

    def test_absolute_paths_when_allowed(self):
        """Test absolute paths when explicitly allowed."""
        # Update config to allow absolute paths
        def mock_config_with_absolute(key, default=None):
            if key == 'allow_absolute_asset_paths':
                return True
            return self._mock_config_get(key, default)

        self.mock_config.get.side_effect = mock_config_with_absolute

        # Create new validator with updated config
        validator = AssetPathValidator(self.mock_config)

        # Test that absolute path to our test file works
        assert validator.asset_exists(self.test_asset)

    def test_validation_disabled(self):
        """Test behavior when validation is disabled."""
        def mock_config_no_validation(key, default=None):
            if key == 'validate_asset_paths':
                return False
            return self._mock_config_get(key, default)

        self.mock_config.get.side_effect = mock_config_no_validation

        validator = AssetPathValidator(self.mock_config)

        # Path traversal should still return the path (but not validate existence)
        dangerous_path = '../../../etc/passwd'
        sanitized = validator.validate_asset_path(dangerous_path)
        assert sanitized == dangerous_path  # Validation disabled

    def test_nonexistent_search_paths(self):
        """Test behavior with nonexistent search paths."""
        def mock_config_bad_paths(key, default=None):
            if key == 'asset_search_paths':
                return ['/nonexistent/path', '/another/fake/path']
            return self._mock_config_get(key, default)

        self.mock_config.get.side_effect = mock_config_bad_paths

        validator = AssetPathValidator(self.mock_config)

        # Should handle gracefully
        assert not validator.asset_exists('any_asset.usd')
        assert validator.list_available_assets() == []

    def test_create_asset_validator_factory(self):
        """Test the factory function."""
        validator = create_asset_validator(self.mock_config)
        assert isinstance(validator, AssetPathValidator)

    def test_get_search_paths(self):
        """Test getting configured search paths."""
        paths = self.validator.get_search_paths()
        assert self.assets_dir in paths
        assert self.models_dir in paths


class TestAssetManagerIntegration:
    """Integration tests for AssetManager with secure validation."""

    def test_asset_manager_with_secure_validation(self):
        """Test that AssetManager properly uses secure validation."""
        # This would require mocking USD context and other Isaac Sim components
        # For now, we'll test the basic integration points

        from agent_world_config import create_worldbuilder_config

        config = create_worldbuilder_config()

        # Verify that security settings are present in config
        assert config.get('validate_asset_paths') is True
        assert config.get('allow_absolute_asset_paths') is False
        assert isinstance(config.get('asset_search_paths'), list)
        assert len(config.get('asset_search_paths')) > 0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])