"""
Tests for version module.
"""

import os
import unittest
from datetime import datetime
from unittest.mock import patch

from version import __version__, get_next_patch_version, get_version, get_version_info


class TestVersionModule(unittest.TestCase):
    """Test the version module functions."""

    def test_get_version(self):
        """Test get_version returns the current version."""
        version = get_version()
        self.assertEqual(version, __version__)
        self.assertIsInstance(version, str)
        self.assertTrue(len(version) > 0)

    def test_get_version_info_structure(self):
        """Test get_version_info returns correct structure."""
        version_info = get_version_info()

        # Check that all required keys are present
        required_keys = ["version", "build_date", "environment", "service"]
        for key in required_keys:
            self.assertIn(key, version_info)

        # Check data types
        self.assertIsInstance(version_info["version"], str)
        self.assertIsInstance(version_info["build_date"], str)
        self.assertIsInstance(version_info["environment"], str)
        self.assertIsInstance(version_info["service"], str)

        # Check specific values
        self.assertEqual(version_info["version"], __version__)
        self.assertEqual(version_info["service"], "google-drive-service")

    def test_get_version_info_build_date_format(self):
        """Test that build_date is in ISO format."""
        version_info = get_version_info()
        build_date = version_info["build_date"]

        # Should be able to parse as ISO format
        try:
            parsed_date = datetime.fromisoformat(build_date.replace("Z", "+00:00"))
            self.assertIsInstance(parsed_date, datetime)
        except ValueError:
            self.fail(f"build_date '{build_date}' is not in valid ISO format")

    @patch.dict(os.environ, {"FLASK_ENV": "development"})
    def test_get_version_info_environment_development(self):
        """Test get_version_info with development environment."""
        version_info = get_version_info()
        self.assertEqual(version_info["environment"], "development")

    @patch.dict(os.environ, {"FLASK_ENV": "testing"})
    def test_get_version_info_environment_testing(self):
        """Test get_version_info with testing environment."""
        version_info = get_version_info()
        self.assertEqual(version_info["environment"], "testing")

    @patch.dict(os.environ, {}, clear=True)
    def test_get_version_info_environment_default(self):
        """Test get_version_info with default environment."""
        version_info = get_version_info()
        self.assertEqual(version_info["environment"], "production")

    def test_get_next_patch_version_valid_format(self):
        """Test get_next_patch_version with valid version format."""
        # Mock the current version to test the function
        with patch("version.__version__", "2025.01.5"):
            next_version = get_next_patch_version()
            self.assertEqual(next_version, "2025.01.6")

    def test_get_next_patch_version_zero_patch(self):
        """Test get_next_patch_version with zero patch number."""
        with patch("version.__version__", "2025.01.0"):
            next_version = get_next_patch_version()
            self.assertEqual(next_version, "2025.01.1")

    def test_get_next_patch_version_large_patch(self):
        """Test get_next_patch_version with large patch number."""
        with patch("version.__version__", "2025.12.99"):
            next_version = get_next_patch_version()
            self.assertEqual(next_version, "2025.12.100")

    def test_get_next_patch_version_invalid_format(self):
        """Test get_next_patch_version with invalid version format."""
        with patch("version.__version__", "invalid.version"):
            next_version = get_next_patch_version()
            self.assertEqual(next_version, "invalid.version")

    def test_get_next_patch_version_two_parts(self):
        """Test get_next_patch_version with only two version parts."""
        with patch("version.__version__", "2025.01"):
            next_version = get_next_patch_version()
            self.assertEqual(next_version, "2025.01")

    def test_get_next_patch_version_four_parts(self):
        """Test get_next_patch_version with four version parts."""
        with patch("version.__version__", "2025.01.5.beta"):
            next_version = get_next_patch_version()
            self.assertEqual(next_version, "2025.01.5.beta")

    def test_version_format_consistency(self):
        """Test that the version follows expected format."""
        version = get_version()

        # Should follow YYYY.MM.P format where P is patch number
        parts = version.split(".")
        self.assertEqual(len(parts), 3, f"Version {version} should have 3 parts")

        # First part should be a 4-digit year
        year = parts[0]
        self.assertEqual(len(year), 4, f"Year part {year} should be 4 digits")
        self.assertTrue(year.isdigit(), f"Year part {year} should be numeric")
        self.assertGreaterEqual(int(year), 2020, f"Year {year} should be reasonable")

        # Second part should be month (01-12)
        month = parts[1]
        self.assertEqual(len(month), 2, f"Month part {month} should be 2 digits")
        self.assertTrue(month.isdigit(), f"Month part {month} should be numeric")
        month_int = int(month)
        self.assertGreaterEqual(month_int, 1, f"Month {month} should be >= 1")
        self.assertLessEqual(month_int, 12, f"Month {month} should be <= 12")

        # Third part should be patch number
        patch = parts[2]
        self.assertTrue(patch.isdigit(), f"Patch part {patch} should be numeric")
        self.assertGreaterEqual(int(patch), 0, f"Patch {patch} should be >= 0")

    def test_version_immutability(self):
        """Test that version functions return consistent values."""
        version1 = get_version()
        version2 = get_version()
        self.assertEqual(version1, version2)

        # Version info should have same version but different build_date
        info1 = get_version_info()
        info2 = get_version_info()
        self.assertEqual(info1["version"], info2["version"])
        self.assertEqual(info1["service"], info2["service"])
        # build_date might be different due to timing

    def test_module_constants(self):
        """Test that module constants are properly defined."""
        # __version__ should be defined and be a string
        self.assertIsInstance(__version__, str)
        self.assertTrue(len(__version__) > 0)

        # Should match what get_version() returns
        self.assertEqual(__version__, get_version())


if __name__ == "__main__":
    unittest.main()
