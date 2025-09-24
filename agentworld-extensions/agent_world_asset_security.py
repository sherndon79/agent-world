"""
Secure Asset Path Validation for agenTW∞rld Extensions.

Provides centralized, configurable asset path security to prevent path traversal attacks
while allowing flexible asset organization within approved directories.

Usage:
    from agent_world_asset_security import AssetPathValidator

    validator = AssetPathValidator(config)
    safe_path = validator.validate_asset_path("demo/Food/mac_and_cheese.usdz")
    if validator.asset_exists(safe_path):
        # Use the asset safely
"""

import os
import logging
from pathlib import Path
from typing import List, Optional, Tuple, Any

from agent_world_validation import InputValidator, ValidationError, create_asset_validator as create_input_validator

logger = logging.getLogger(__name__)


class AssetPathValidator:
    """Secure asset path validator with configurable search paths."""

    def __init__(self, config: Any):
        """
        Initialize asset path validator with configuration.

        Args:
            config: Extension configuration object with asset security settings
        """
        self.config = config
        self.input_validator = create_input_validator()
        self._validate_config()

    def _validate_config(self):
        """Validate the asset security configuration."""
        search_paths = self.config.get('asset_search_paths', [])
        if not search_paths:
            logger.warning("No asset search paths configured - asset access may be limited")

        # Validate that search paths exist and are directories
        valid_paths = []
        for path in search_paths:
            expanded_path = os.path.expanduser(os.path.expandvars(path))
            abs_path = os.path.abspath(expanded_path)

            if os.path.exists(abs_path) and os.path.isdir(abs_path):
                valid_paths.append(abs_path)
                logger.debug(f"Asset search path configured: {abs_path}")
            else:
                logger.warning(f"Asset search path does not exist or is not a directory: {abs_path}")

        self._search_paths = valid_paths

    def validate_asset_path(self, asset_path: str) -> str:
        """
        Validate and sanitize asset path to prevent directory traversal.

        Args:
            asset_path: User-provided asset path

        Returns:
            Sanitized asset path safe for use

        Raises:
            ValueError: If path is invalid or contains security violations
        """
        # Check if validation is enabled
        if not self.config.get('validate_asset_paths', True):
            logger.warning("Asset path validation is disabled - security risk!")
            return asset_path

        # Use centralized validation for basic path security
        try:
            # Validate as file path with basic security checks
            allowed_extensions = self.config.get('allowed_asset_extensions')
            normalized = self.input_validator.validate_file_path(
                "asset_path",
                asset_path,
                allowed_extensions=allowed_extensions,
                check_exists=False
            )
        except ValidationError as e:
            raise ValueError(str(e))

        # Additional absolute path check based on configuration
        if os.path.isabs(normalized):
            if not self.config.get('allow_absolute_asset_paths', False):
                raise ValueError(f"Absolute paths not allowed: {asset_path}")

        # Additional security checks for Windows paths (even on Linux)
        if ':' in normalized and not self.config.get('allow_absolute_asset_paths', False):
            raise ValueError(f"Drive letters not allowed: {asset_path}")

        return normalized

    def asset_exists(self, asset_path: str) -> bool:
        """
        Check if asset exists within configured safe directories.

        Args:
            asset_path: Pre-validated asset path

        Returns:
            True if asset exists and is accessible, False otherwise
        """
        try:
            # Sanitize the path first
            safe_asset_path = self.validate_asset_path(asset_path)

            # Handle absolute paths if allowed
            if os.path.isabs(safe_asset_path):
                if self.config.get('allow_absolute_asset_paths', False):
                    return self._check_file_validity(safe_asset_path)
                else:
                    return False

            # Search in configured search paths
            for search_path in self._search_paths:
                full_path = os.path.join(search_path, safe_asset_path)

                # Double-check: ensure resolved path is within search directory
                real_full_path = os.path.realpath(full_path)
                real_search_path = os.path.realpath(search_path)

                # Ensure the resolved path is within the search directory
                if not real_full_path.startswith(real_search_path + os.sep):
                    logger.warning(f"Asset {asset_path} resolves outside safe directory {search_path}")
                    continue

                if self._check_file_validity(full_path):
                    # Log asset access if configured
                    if self.config.get('log_asset_access', False):
                        logger.info(f"Asset accessed: {asset_path} -> {full_path}")
                    return True

            return False

        except ValueError as e:
            logger.warning(f"Invalid asset path {asset_path}: {e}")
            return False
        except Exception as e:
            logger.error(f"Error checking asset existence {asset_path}: {e}")
            return False

    def _check_file_validity(self, full_path: str) -> bool:
        """
        Check if file exists and meets security requirements.

        Args:
            full_path: Full path to the file

        Returns:
            True if file is valid and accessible
        """
        if not os.path.exists(full_path):
            return False

        if not os.path.isfile(full_path):
            logger.warning(f"Asset path is not a file: {full_path}")
            return False

        # Check file size limits
        max_size_mb = self.config.get('max_asset_file_size_mb', 100)
        if max_size_mb > 0:
            try:
                file_size = os.path.getsize(full_path)
                max_size_bytes = max_size_mb * 1024 * 1024
                if file_size > max_size_bytes:
                    logger.warning(f"Asset exceeds size limit ({file_size} > {max_size_bytes}): {full_path}")
                    return False
            except OSError as e:
                logger.error(f"Cannot check file size for {full_path}: {e}")
                return False

        # Check file permissions
        if not os.access(full_path, os.R_OK):
            logger.warning(f"Asset is not readable: {full_path}")
            return False

        return True

    def get_asset_full_path(self, asset_path: str) -> Optional[str]:
        """
        Get the full path to an asset if it exists and is valid.

        Args:
            asset_path: User-provided asset path

        Returns:
            Full path to asset if valid, None if not found or invalid
        """
        try:
            safe_asset_path = self.validate_asset_path(asset_path)

            # Handle absolute paths if allowed
            if os.path.isabs(safe_asset_path):
                if self.config.get('allow_absolute_asset_paths', False):
                    if self._check_file_validity(safe_asset_path):
                        return safe_asset_path
                return None

            # Search in configured search paths
            for search_path in self._search_paths:
                full_path = os.path.join(search_path, safe_asset_path)

                # Security check: ensure resolved path is within search directory
                real_full_path = os.path.realpath(full_path)
                real_search_path = os.path.realpath(search_path)

                if not real_full_path.startswith(real_search_path + os.sep):
                    continue

                if self._check_file_validity(full_path):
                    return full_path

            return None

        except ValueError:
            return None
        except Exception as e:
            logger.error(f"Error getting asset full path {asset_path}: {e}")
            return None

    def list_available_assets(self, path_prefix: str = "") -> List[str]:
        """
        List available assets matching a path prefix.

        Args:
            path_prefix: Optional path prefix to filter results

        Returns:
            List of relative asset paths available
        """
        assets = []

        try:
            # Validate the prefix
            if path_prefix:
                self.validate_asset_path(path_prefix)

            for search_path in self._search_paths:
                search_dir = os.path.join(search_path, path_prefix) if path_prefix else search_path

                if not os.path.exists(search_dir) or not os.path.isdir(search_dir):
                    continue

                for root, dirs, files in os.walk(search_dir):
                    # Calculate relative path from search_path
                    rel_root = os.path.relpath(root, search_path)
                    if rel_root == '.':
                        rel_root = ''

                    for file in files:
                        rel_path = os.path.join(rel_root, file) if rel_root else file
                        # Normalize path separators
                        rel_path = rel_path.replace('\\', '/')

                        # Check if file meets validity requirements
                        full_path = os.path.join(root, file)
                        if self._check_file_validity(full_path):
                            if rel_path not in assets:  # Avoid duplicates
                                assets.append(rel_path)

        except Exception as e:
            logger.error(f"Error listing assets with prefix {path_prefix}: {e}")

        return sorted(assets)

    def get_search_paths(self) -> List[str]:
        """Get the list of configured search paths."""
        return self._search_paths.copy()


def create_asset_validator(config: Any) -> AssetPathValidator:
    """
    Factory function to create an asset path validator.

    Args:
        config: Extension configuration object

    Returns:
        Configured AssetPathValidator instance
    """
    return AssetPathValidator(config)