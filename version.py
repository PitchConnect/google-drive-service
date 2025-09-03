"""
Version management for Google Drive Service.
"""

import os
import re
import shutil
import subprocess  # nosec B404 - controlled use to query git tags (no shell, constant args)
from datetime import datetime

# Current version - update this for releases
__version__ = "2025.09.2"


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
    try:
        # Resolve full path to git to avoid partial path issues (Bandit B607)
        git_executable = shutil.which("git")
        if not git_executable:
            # If git is not available, fall back safely
            return get_next_patch_version()

        # Get ALL tags and find the highest version
        result = subprocess.run(  # nosec B603 - constant args, no user input, shell not used
            [git_executable, "tag", "-l"],
            capture_output=True,
            text=True,
            cwd=os.path.dirname(__file__) if __file__ else ".",
        )

        if result.returncode == 0:
            all_tags = result.stdout.strip().split("\n")
            version_tags = []

            # Filter and parse version tags
            for tag in all_tags:
                if tag.startswith("v") and re.match(r"^v\d{4}\.\d{1,2}\.\d+$", tag):
                    version_str = tag.lstrip("v")
                    parts = version_str.split(".")
                    if len(parts) == 3:
                        try:
                            year, month, patch = int(parts[0]), int(parts[1]), int(parts[2])
                            version_tags.append((year, month, patch, version_str))
                        except ValueError:
                            continue

            if version_tags:
                # Sort by version (year, month, patch) and get the highest
                version_tags.sort(reverse=True)
                highest_year, highest_month, highest_patch, highest_version = version_tags[0]

                # Get current version parts
                current_parts = __version__.split(".")
                if len(current_parts) == 3:
                    try:
                        curr_year, curr_month, curr_patch = (
                            int(current_parts[0]),
                            int(current_parts[1]),
                            int(current_parts[2]),
                        )

                        # Find the next safe version
                        if (curr_year, curr_month, curr_patch) <= (highest_year, highest_month, highest_patch):
                            # Current version is behind or equal to highest tag, increment from highest tag
                            return f"{highest_year}.{highest_month:02d}.{highest_patch + 1}"
                        else:
                            # Current version is ahead, use current + 1
                            return f"{curr_year}.{curr_month:02d}.{curr_patch + 1}"
                    except ValueError:
                        pass

        # Fallback to normal patch increment
        return get_next_patch_version()

    except Exception as e:
        # If git operations fail, fallback to normal patch increment
        print(f"Warning: Git operation failed in get_next_version_safe: {e}")
        return get_next_patch_version()
