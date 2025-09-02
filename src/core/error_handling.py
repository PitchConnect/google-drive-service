"""
Enhanced error handling for Google Drive service.

This module provides comprehensive error handling with circuit breaker patterns,
retry logic, and detailed error context for Google Drive API operations.
"""

import functools
import time
from typing import Any, Callable, Dict, Optional, Union

from googleapiclient.errors import HttpError

from .logging_config import get_logger, log_error_context


# Custom exception classes for Google Drive operations
class DriveOperationError(Exception):
    """Base exception for Google Drive operation errors."""

    pass


class DriveAuthenticationError(DriveOperationError):
    """Exception raised when Google Drive authentication fails."""

    pass


class DriveAPIError(DriveOperationError):
    """Exception raised when Google Drive API calls fail."""

    pass


class DriveFileError(DriveOperationError):
    """Exception raised when file operations fail."""

    pass


class DriveFolderError(DriveOperationError):
    """Exception raised when folder operations fail."""

    pass


class DriveQuotaError(DriveOperationError):
    """Exception raised when quota limits are exceeded."""

    pass


class DriveRateLimitError(DriveOperationError):
    """Exception raised when rate limits are exceeded."""

    pass


class ConfigurationError(DriveOperationError):
    """Exception raised when configuration is invalid."""

    pass


class DriveCircuitBreaker:
    """Circuit breaker for Google Drive operations."""

    def __init__(self, failure_threshold: int = 5, recovery_timeout: int = 60):
        """Initialize the circuit breaker.

        Args:
            failure_threshold: Number of failures before opening circuit
            recovery_timeout: Seconds to wait before attempting recovery
        """
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.last_failure_time = None
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN

    def call(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function with circuit breaker protection."""
        if self.state == "OPEN":
            if time.time() - self.last_failure_time > self.recovery_timeout:
                self.state = "HALF_OPEN"
            else:
                raise DriveOperationError("Circuit breaker is OPEN")

        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            raise e

    def _on_success(self):
        """Handle successful operation."""
        self.failure_count = 0
        self.state = "CLOSED"

    def _on_failure(self):
        """Handle failed operation."""
        self.failure_count += 1
        self.last_failure_time = time.time()

        if self.failure_count >= self.failure_threshold:
            self.state = "OPEN"


# Global circuit breaker instance - can be reset for testing
_circuit_breaker = DriveCircuitBreaker()


def reset_circuit_breaker():
    """Reset the circuit breaker state - useful for testing."""
    global _circuit_breaker
    _circuit_breaker = DriveCircuitBreaker()


def handle_drive_operations(operation_name: str, component: str = "drive_operations"):
    """
    Decorator for handling Google Drive operations with enhanced logging.

    Args:
        operation_name: Name of the operation being performed
        component: Component name for logging context
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            logger = get_logger(func.__module__, component)
            start_time = time.time()

            logger.info(f"Starting {operation_name}")

            try:
                # Execute with circuit breaker protection
                result = _circuit_breaker.call(func, *args, **kwargs)

                duration = time.time() - start_time
                logger.info(f"Successfully completed {operation_name} in {duration:.2f}s")

                return result

            except DriveOperationError as e:
                duration = time.time() - start_time
                context = {
                    "operation": operation_name,
                    "duration": duration,
                    "args_count": len(args),
                    "kwargs_keys": list(kwargs.keys()),
                }

                log_error_context(logger, e, operation_name, context)
                raise

            except HttpError as e:
                duration = time.time() - start_time
                context = {
                    "operation": operation_name,
                    "duration": duration,
                    "status_code": e.resp.status if e.resp else "unknown",
                    "args_count": len(args),
                    "kwargs_keys": list(kwargs.keys()),
                }

                # Convert HttpError to appropriate Drive exception
                drive_error = _convert_http_error(e, operation_name)
                log_error_context(logger, drive_error, operation_name, context)
                raise drive_error from e

            except Exception as e:
                duration = time.time() - start_time
                context = {
                    "operation": operation_name,
                    "duration": duration,
                    "args_count": len(args),
                    "kwargs_keys": list(kwargs.keys()),
                }

                # Wrap unexpected errors in DriveOperationError
                wrapped_error = DriveOperationError(f"Unexpected error in {operation_name}: {str(e)}")
                log_error_context(logger, wrapped_error, operation_name, context)
                raise wrapped_error from e

        return wrapper

    return decorator


def handle_api_errors(operation_name: str, component: str = "api"):
    """
    Decorator for handling API errors with enhanced logging.

    Args:
        operation_name: Name of the API operation being performed
        component: Component name for logging context
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            logger = get_logger(func.__module__, component)
            start_time = time.time()

            logger.info(f"Starting {operation_name}")

            try:
                result = func(*args, **kwargs)
                duration = time.time() - start_time
                logger.info(f"Successfully completed {operation_name} in {duration:.2f}s")
                return result

            except Exception as e:
                duration = time.time() - start_time
                context = {
                    "operation": operation_name,
                    "duration": duration,
                    "args_count": len(args),
                    "kwargs_keys": list(kwargs.keys()),
                }

                log_error_context(logger, e, operation_name, context)
                raise

        return wrapper

    return decorator


def safe_drive_operation(operation: Callable, *args, max_retries: int = 3, retry_delay: float = 1.0, **kwargs) -> Any:
    """
    Execute Google Drive operation with retry logic and error handling.

    Args:
        operation: Function to execute
        *args: Arguments for the operation
        max_retries: Maximum number of retry attempts
        retry_delay: Delay between retries in seconds
        **kwargs: Keyword arguments for the operation

    Returns:
        Result of the operation

    Raises:
        DriveOperationError: If operation fails after all retries
    """
    logger = get_logger(__name__, "safe_operation")

    for attempt in range(max_retries + 1):
        try:
            return operation(*args, **kwargs)
        except Exception as e:
            if attempt == max_retries:
                logger.error(f"Operation failed after {max_retries} retries: {str(e)}")
                raise DriveOperationError(f"Operation failed after {max_retries} retries") from e

            logger.warning(f"Operation attempt {attempt + 1} failed, retrying in {retry_delay}s: {str(e)}")
            time.sleep(retry_delay)


def validate_drive_parameters(
    file_path: Optional[str] = None,
    folder_path: Optional[str] = None,
    file_id: Optional[str] = None,
    folder_id: Optional[str] = None,
    service: Optional[Any] = None,
) -> None:
    """
    Validate Google Drive operation parameters.

    Args:
        file_path: File path for operations
        folder_path: Folder path for operations
        file_id: Google Drive file ID
        folder_id: Google Drive folder ID
        service: Google Drive service instance

    Raises:
        ConfigurationError: If parameters are invalid
    """
    if file_path is not None and (not isinstance(file_path, str) or not file_path.strip()):
        raise ConfigurationError("file_path must be a non-empty string")

    if folder_path is not None and (not isinstance(folder_path, str) or not folder_path.strip()):
        raise ConfigurationError("folder_path must be a non-empty string")

    if file_id is not None:
        if not isinstance(file_id, str) or not file_id.strip():
            raise ConfigurationError("file_id must be a non-empty string")
        if len(file_id) < 10:  # Google Drive IDs are typically much longer
            raise ConfigurationError("file_id appears to be invalid (too short)")

    if folder_id is not None:
        if not isinstance(folder_id, str) or not folder_id.strip():
            raise ConfigurationError("folder_id must be a non-empty string")
        if len(folder_id) < 10:  # Google Drive IDs are typically much longer
            raise ConfigurationError("folder_id appears to be invalid (too short)")

    if service is not None and not hasattr(service, "files"):
        raise ConfigurationError("service must be a valid Google Drive service instance")


def _convert_http_error(http_error: HttpError, operation: str) -> DriveOperationError:
    """Convert HttpError to appropriate Drive exception."""
    status_code = http_error.resp.status if http_error.resp else 0
    error_details = str(http_error)

    # Authentication errors
    if status_code == 401:
        return DriveAuthenticationError(f"Authentication failed in {operation}: {error_details}")

    # Rate limiting errors
    if status_code == 429:
        return DriveRateLimitError(f"Rate limit exceeded in {operation}: {error_details}")

    # Quota errors
    if status_code == 403 and "quota" in error_details.lower():
        return DriveQuotaError(f"Quota exceeded in {operation}: {error_details}")

    # File/folder not found
    if status_code == 404:
        return DriveFileError(f"File or folder not found in {operation}: {error_details}")

    # Server errors
    if 500 <= status_code < 600:
        return DriveAPIError(f"Google Drive API error in {operation}: {error_details}")

    # Generic API error
    return DriveAPIError(f"Google Drive API error in {operation}: {error_details}")
