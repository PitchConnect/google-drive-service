"""
Tests for retry_utils module.
"""

import unittest
from unittest.mock import MagicMock, patch

from googleapiclient.errors import HttpError

from retry_utils import (
    RETRYABLE_GOOGLE_ERRORS,
    RETRYABLE_STATUS_CODES,
    RetryableError,
    circuit_breaker,
    detailed_error_response,
    is_retryable_error,
    rate_limit,
    retry,
)


class TestRetryableError(unittest.TestCase):
    """Test the RetryableError exception class."""

    def test_retryable_error_creation(self):
        """Test creating a RetryableError."""
        error = RetryableError("Test error message")
        self.assertEqual(str(error), "Test error message")
        self.assertIsInstance(error, Exception)


class TestIsRetryableError(unittest.TestCase):
    """Test the is_retryable_error function."""

    def test_http_error_retryable_status_codes(self):
        """Test that HttpError with retryable status codes returns True."""
        for status_code in RETRYABLE_STATUS_CODES:
            mock_response = MagicMock()
            mock_response.status = status_code

            error = HttpError(mock_response, b'{"error": "test"}')
            self.assertTrue(is_retryable_error(error))

    def test_http_error_non_retryable_status_code(self):
        """Test that HttpError with non-retryable status codes returns False."""
        mock_response = MagicMock()
        mock_response.status = 404  # Not Found - not retryable

        error = HttpError(mock_response, b'{"error": "test"}')
        self.assertFalse(is_retryable_error(error))

    def test_http_error_retryable_google_errors(self):
        """Test that HttpError with retryable Google error messages returns True."""
        for retryable_error in RETRYABLE_GOOGLE_ERRORS:
            mock_response = MagicMock()
            mock_response.status = 400  # Non-retryable status code

            error_content = f'{{"error": "{retryable_error}"}}'
            error = HttpError(mock_response, error_content.encode("utf-8"))
            self.assertTrue(is_retryable_error(error))

    def test_retryable_error_instance(self):
        """Test that RetryableError instances return True."""
        error = RetryableError("Test error")
        self.assertTrue(is_retryable_error(error))

    def test_non_retryable_error(self):
        """Test that non-retryable errors return False."""
        error = ValueError("Test error")
        self.assertFalse(is_retryable_error(error))

    def test_http_error_invalid_content(self):
        """Test HttpError with invalid content doesn't crash."""
        mock_response = MagicMock()
        mock_response.status = 400

        error = HttpError(mock_response, b"\xff\xfe")  # Invalid UTF-8
        self.assertFalse(is_retryable_error(error))


class TestRetryDecorator(unittest.TestCase):
    """Test the retry decorator."""

    def test_retry_success_first_attempt(self):
        """Test that successful function calls don't retry."""
        call_count = 0

        @retry(max_retries=3)
        def test_function():
            nonlocal call_count
            call_count += 1
            return "success"

        result = test_function()
        self.assertEqual(result, "success")
        self.assertEqual(call_count, 1)

    def test_retry_success_after_retries(self):
        """Test that function succeeds after retries."""
        call_count = 0

        @retry(max_retries=3, initial_delay=0.01)
        def test_function():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise RetryableError("Temporary error")
            return "success"

        result = test_function()
        self.assertEqual(result, "success")
        self.assertEqual(call_count, 3)

    def test_retry_exhausted(self):
        """Test that function fails after exhausting retries."""
        call_count = 0

        @retry(max_retries=2, initial_delay=0.01)
        def test_function():
            nonlocal call_count
            call_count += 1
            raise RetryableError("Persistent error")

        with self.assertRaises(RetryableError):
            test_function()

        self.assertEqual(call_count, 3)  # Initial attempt + 2 retries

    def test_retry_non_retryable_error(self):
        """Test that non-retryable errors are not retried."""
        call_count = 0

        @retry(max_retries=3)
        def test_function():
            nonlocal call_count
            call_count += 1
            raise ValueError("Non-retryable error")

        with self.assertRaises(ValueError):
            test_function()

        self.assertEqual(call_count, 1)  # No retries

    def test_retry_with_custom_exceptions(self):
        """Test retry with custom retryable exceptions."""
        call_count = 0

        @retry(max_retries=2, initial_delay=0.01, retryable_exceptions=[ValueError])
        def test_function():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("Custom retryable error")
            return "success"

        result = test_function()
        self.assertEqual(result, "success")
        self.assertEqual(call_count, 3)

    @patch("retry_utils.time.sleep")
    def test_retry_delay_calculation(self, mock_sleep):
        """Test that retry delays are calculated correctly."""
        call_count = 0

        @retry(max_retries=2, initial_delay=1.0, backoff_factor=2.0, jitter=False)
        def test_function():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise RetryableError("Test error")
            return "success"

        test_function()

        # Should have called sleep twice with exponential backoff
        self.assertEqual(mock_sleep.call_count, 2)
        # First delay: 1.0 * 2.0 = 2.0
        # Second delay: 2.0 * 2.0 = 4.0
        mock_sleep.assert_any_call(2.0)
        mock_sleep.assert_any_call(4.0)


class TestRateLimit(unittest.TestCase):
    """Test the rate_limit decorator."""

    @patch("retry_utils.time.time")
    @patch("retry_utils.time.sleep")
    def test_rate_limit_basic(self, mock_sleep, mock_time):
        """Test basic rate limiting functionality."""
        # Mock time to return predictable values
        mock_time.side_effect = [0, 0.5, 1.0, 1.5]

        @rate_limit(calls_per_second=2, max_burst=2)
        def test_function():
            return "success"

        # First two calls should not sleep (within burst limit)
        result1 = test_function()
        result2 = test_function()

        self.assertEqual(result1, "success")
        self.assertEqual(result2, "success")
        self.assertEqual(mock_sleep.call_count, 0)


class TestCircuitBreaker(unittest.TestCase):
    """Test the circuit_breaker decorator."""

    def test_circuit_breaker_success(self):
        """Test circuit breaker with successful calls."""

        @circuit_breaker(failure_threshold=3, reset_timeout=1.0)
        def test_function():
            return "success"

        # Multiple successful calls should work
        for _ in range(5):
            result = test_function()
            self.assertEqual(result, "success")

    def test_circuit_breaker_failure_threshold(self):
        """Test circuit breaker opens after failure threshold."""
        call_count = 0

        @circuit_breaker(failure_threshold=2, reset_timeout=0.1)
        def test_function():
            nonlocal call_count
            call_count += 1
            raise Exception("Test error")

        # First two calls should raise the original exception
        with self.assertRaises(Exception):
            test_function()
        with self.assertRaises(Exception):
            test_function()

        # Third call should raise CircuitBreakerOpenError
        with self.assertRaises(Exception):
            test_function()

        # The circuit should be open now
        self.assertEqual(call_count, 2)  # Function only called twice


class TestDetailedErrorResponse(unittest.TestCase):
    """Test the detailed_error_response function."""

    def test_detailed_error_response_http_error(self):
        """Test detailed error response for HttpError."""
        mock_response = MagicMock()
        mock_response.status = 404
        mock_response.reason = "Not Found"

        error = HttpError(mock_response, b'{"error": {"message": "File not found"}}')

        response = detailed_error_response(error)

        self.assertIn("error", response)
        self.assertEqual(response["error"]["type"], "HttpError")
        self.assertEqual(response["error"]["status_code"], 404)
        self.assertIn("details", response["error"])

    def test_detailed_error_response_generic_error(self):
        """Test detailed error response for generic errors."""
        error = ValueError("Test error message")

        response = detailed_error_response(error)

        self.assertIn("error", response)
        self.assertEqual(response["error"]["type"], "ValueError")
        self.assertEqual(response["error"]["message"], "Test error message")


if __name__ == "__main__":
    unittest.main()
