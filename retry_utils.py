"""Utility functions for implementing retry logic and error handling."""

import functools
import logging
import time
from typing import Any, Callable, Dict, List, Optional, TypeVar

from googleapiclient.errors import HttpError

logger = logging.getLogger(__name__)

# Type variable for generic function return type
T = TypeVar("T")

# Define common HTTP status codes that should trigger retries
RETRYABLE_STATUS_CODES = [
    429,  # Too Many Requests
    500,  # Internal Server Error
    502,  # Bad Gateway
    503,  # Service Unavailable
    504,  # Gateway Timeout
]

# Define Google API errors that should trigger retries
RETRYABLE_GOOGLE_ERRORS = [
    "rateLimitExceeded",
    "userRateLimitExceeded",
    "quotaExceeded",
    "backendError",
    "internalError",
    "transientError",
]


class RetryableError(Exception):
    """Exception class for errors that should trigger a retry."""

    pass


def is_retryable_error(error: Exception) -> bool:
    """
    Determine if an error should trigger a retry.

    Args:
        error: The exception that was raised

    Returns:
        True if the error should trigger a retry, False otherwise
    """
    # Check if it's an HttpError with a retryable status code
    if isinstance(error, HttpError):
        if error.resp.status in RETRYABLE_STATUS_CODES:
            return True

        # Check for specific Google API error reasons
        try:
            error_content = error.content.decode("utf-8")
            for retryable_error in RETRYABLE_GOOGLE_ERRORS:
                if retryable_error in error_content:
                    return True
        except Exception:  # nosec B110 - Broad exception handling is intentional here
            pass

    # Check if it's our custom RetryableError
    if isinstance(error, RetryableError):
        return True

    # Check for network-related errors that might be transient
    if any(
        network_err in str(error).lower() for network_err in ["connection", "timeout", "reset", "refused", "network"]
    ):
        return True

    return False


def retry(
    max_retries: int = 3,
    initial_delay: float = 1.0,
    max_delay: float = 60.0,
    backoff_factor: float = 2.0,
    jitter: bool = True,
    retryable_exceptions: Optional[List[type]] = None,
) -> Callable:
    """
    Decorator that retries a function if it raises specified exceptions.

    Args:
        max_retries: Maximum number of retries before giving up
        initial_delay: Initial delay between retries in seconds
        max_delay: Maximum delay between retries in seconds
        backoff_factor: Multiplicative factor for exponential backoff
        jitter: Whether to add random jitter to delay times
        retryable_exceptions: List of exception types that should trigger a retry
                             (if None, uses is_retryable_error function)

    Returns:
        Decorated function with retry logic
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            delay = initial_delay
            last_exception = None

            for retry_count in range(max_retries + 1):  # +1 for the initial attempt
                try:
                    if retry_count > 0:
                        logger.info(f"Retry {retry_count}/{max_retries} for {func.__name__} after {delay:.2f}s delay")

                    return func(*args, **kwargs)

                except Exception as e:
                    last_exception = e

                    # Determine if we should retry
                    should_retry = False
                    if retryable_exceptions:
                        should_retry = any(isinstance(e, exc_type) for exc_type in retryable_exceptions)
                    else:
                        should_retry = is_retryable_error(e)

                    # If not retryable or we've exhausted retries, re-raise
                    if not should_retry or retry_count >= max_retries:
                        logger.warning(f"Not retrying {func.__name__}: {str(e)}")
                        raise

                    # Calculate delay with exponential backoff and optional jitter
                    if jitter:
                        # Use time-based jitter instead of random for non-cryptographic purposes
                        jitter_factor = 0.5 + (time.time() % 1) * 0.5  # 0.5 to 1.0 based on current time
                        delay = min(max_delay, delay * backoff_factor * jitter_factor)
                    else:
                        delay = min(max_delay, delay * backoff_factor)

                    logger.warning(
                        f"Retryable error in {func.__name__}: {str(e)}. "
                        f"Retrying in {delay:.2f}s ({retry_count + 1}/{max_retries})"
                    )

                    # Wait before retrying
                    time.sleep(delay)

            # This should never happen, but just in case
            if last_exception:
                raise last_exception
            raise RuntimeError("Unexpected error in retry logic")

        return wrapper

    return decorator


def rate_limit(calls_per_second: float = 1.0, max_burst: int = 1) -> Callable:
    """
    Decorator that rate limits a function to a maximum number of calls per second.

    Args:
        calls_per_second: Maximum number of calls per second
        max_burst: Maximum number of calls allowed in a burst

    Returns:
        Decorated function with rate limiting
    """
    last_called = [0.0]  # Use a list for mutable closure
    tokens = [max_burst]  # Token bucket

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            current_time = time.time()
            time_since_last = current_time - last_called[0]

            # Add tokens based on time elapsed (up to max_burst)
            new_tokens = time_since_last * calls_per_second
            tokens[0] = min(max_burst, tokens[0] + new_tokens)

            # If we have less than 1 token, wait until we have at least 1
            if tokens[0] < 1.0:
                wait_time = (1.0 - tokens[0]) / calls_per_second
                logger.debug(f"Rate limiting {func.__name__}, waiting {wait_time:.2f}s")
                time.sleep(wait_time)
                tokens[0] = 1.0  # Now we have exactly 1 token

            # Consume 1 token and call the function
            tokens[0] -= 1.0
            last_called[0] = time.time()

            return func(*args, **kwargs)

        return wrapper

    return decorator


def circuit_breaker(
    failure_threshold: int = 5, reset_timeout: float = 60.0, half_open_timeout: float = 30.0
) -> Callable:
    """
    Decorator that implements the circuit breaker pattern.

    Args:
        failure_threshold: Number of consecutive failures before opening the circuit
        reset_timeout: Time in seconds before attempting to close the circuit
        half_open_timeout: Time in seconds to wait in half-open state before fully closing

    Returns:
        Decorated function with circuit breaker logic
    """
    # Circuit state: 0 = closed, 1 = open, 2 = half-open
    state = {"status": 0, "failures": 0, "last_failure": 0, "last_success": 0}

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            current_time = time.time()

            # Check if circuit is open
            if state["status"] == 1:
                if current_time - state["last_failure"] > reset_timeout:
                    # Transition to half-open
                    logger.info(f"Circuit for {func.__name__} transitioning from open to half-open")
                    state["status"] = 2
                else:
                    # Circuit is open, fail fast
                    logger.warning(f"Circuit for {func.__name__} is open, failing fast")
                    raise RetryableError(f"Circuit breaker for {func.__name__} is open")

            try:
                result = func(*args, **kwargs)

                # Success, update state
                if state["status"] == 2 and current_time - state["last_success"] > half_open_timeout:
                    # In half-open state, check if we should close the circuit
                    logger.info(f"Circuit for {func.__name__} transitioning from half-open to closed")
                    state["status"] = 0
                    state["failures"] = 0

                state["last_success"] = current_time
                return result

            except Exception:
                # Failure, update state
                state["failures"] += 1
                state["last_failure"] = current_time

                if state["status"] == 0 and state["failures"] >= failure_threshold:
                    # Transition to open
                    logger.warning(
                        f"Circuit for {func.__name__} transitioning from closed to open "
                        f"after {state['failures']} consecutive failures"
                    )
                    state["status"] = 1

                if state["status"] == 2:
                    # In half-open state, any failure reopens the circuit
                    logger.warning(f"Circuit for {func.__name__} transitioning from half-open to open after failure")
                    state["status"] = 1

                raise

        return wrapper

    return decorator


def detailed_error_response(error: Exception) -> Dict[str, Any]:
    """Generate a detailed error response dictionary from an exception.

    Args:
        error: The exception to convert to a response

    Returns:
        Dictionary with error details
    """
    response = {"error": {"type": error.__class__.__name__, "message": str(error)}}

    # Add more details for HttpError
    if isinstance(error, HttpError):
        response["error"]["status_code"] = error.resp.status
        try:
            response["error"]["details"] = error.content.decode("utf-8")
        except Exception:  # nosec B110 - Broad exception handling is intentional here
            pass

    return response
