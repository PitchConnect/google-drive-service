"""
Version management for Google Drive Service.
"""

import os
from datetime import datetime

# Current version - update this for releases
__version__ = "2025.08.2"


def get_version():
    """Get the current version of the service."""
    return __version__


def get_version_info():
    """Get detailed version information."""
    return {
        "version": __version__,
        "build_date": datetime.now().isoformat(),
        "environment": os.environ.get("FLASK_ENV", "production"),
        "service": "google-drive-service",
    }


def get_next_patch_version():
    """Calculate the next patch version."""
    parts = __version__.split(".")
    if len(parts) == 3:
        year, month, patch = parts
        return f"{year}.{month}.{int(patch) + 1}"
    return __version__


def get_next_minor_version():
    """Calculate the next minor version (monthly release)."""
    now = datetime.now()
    current_parts = __version__.split(".")

    # If we're already in the current month, increment patch
    if len(current_parts) == 3:
        current_year, current_month, current_patch = current_parts
        target_version = f"{now.year}.{now.month:02d}.0"

        # If the target version would be the same as current, increment patch instead
        if target_version == f"{current_year}.{current_month}.0":
            return f"{current_year}.{current_month}.{int(current_patch) + 1}"

    return f"{now.year}.{now.month:02d}.0"


def get_next_version_safe():
    """Get the next safe version that won't conflict with existing tags."""
    import subprocess

    try:
        # Try to get the latest tag
        result = subprocess.run(
            ["git", "describe", "--tags", "--abbrev=0"],
            capture_output=True,
            text=True,
            cwd=os.path.dirname(__file__) if __file__ else "."
        )

        if result.returncode == 0:
            latest_tag = result.stdout.strip().lstrip('v')
            tag_parts = latest_tag.split('.')

            if len(tag_parts) == 3:
                tag_year, tag_month, tag_patch = tag_parts
                current_parts = __version__.split('.')

                if len(current_parts) == 3:
                    curr_year, curr_month, curr_patch = current_parts

                    # If current version is behind the latest tag, sync to tag + 1
                    if (curr_year, curr_month, int(curr_patch)) <= (tag_year, tag_month, int(tag_patch)):
                        return f"{tag_year}.{tag_month}.{int(tag_patch) + 1}"

        # Fallback to normal patch increment
        return get_next_patch_version()

    except Exception:
        # If git operations fail, fallback to normal patch increment
        return get_next_patch_version()
