"""
Version management for Google Drive Service.
"""

import os
from datetime import datetime

# Current version - update this for releases
__version__ = "2025.01.0"

def get_version():
    """Get the current version of the service."""
    return __version__

def get_version_info():
    """Get detailed version information."""
    return {
        "version": __version__,
        "build_date": datetime.now().isoformat(),
        "environment": os.environ.get('FLASK_ENV', 'production'),
        "service": "google-drive-service"
    }

def get_next_patch_version():
    """Calculate the next patch version."""
    parts = __version__.split('.')
    if len(parts) == 3:
        year, month, patch = parts
        return f"{year}.{month}.{int(patch) + 1}"
    return __version__

def get_next_minor_version():
    """Calculate the next minor version (monthly release)."""
    now = datetime.now()
    return f"{now.year}.{now.month:02d}.0"
