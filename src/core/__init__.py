"""
Core modules for Google Drive service.

This package contains the enhanced logging and error handling infrastructure
following the v2.1.0 standard, specifically designed for Google Drive API operations.
"""

from .error_handling import (
    ConfigurationError,
    DriveAPIError,
    DriveAuthenticationError,
    DriveCircuitBreaker,
    DriveFileError,
    DriveFolderError,
    DriveOperationError,
    DriveQuotaError,
    DriveRateLimitError,
    handle_api_errors,
    handle_drive_operations,
    reset_circuit_breaker,
    safe_drive_operation,
    validate_drive_parameters,
)
from .logging_config import configure_logging, get_logger, log_drive_metrics, log_error_context

__all__ = [
    # Error handling
    "ConfigurationError",
    "DriveAPIError",
    "DriveAuthenticationError",
    "DriveCircuitBreaker",
    "DriveFileError",
    "DriveFolderError",
    "DriveOperationError",
    "DriveQuotaError",
    "DriveRateLimitError",
    "handle_api_errors",
    "handle_drive_operations",
    "reset_circuit_breaker",
    "safe_drive_operation",
    "validate_drive_parameters",
    # Logging
    "configure_logging",
    "get_logger",
    "log_drive_metrics",
    "log_error_context",
]
