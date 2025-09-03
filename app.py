"""Google Drive Service - Main application module.

This module provides a Flask-based REST API for interacting with Google Drive,
including file uploads, folder management, and OAuth authentication.

The service supports:
- OAuth 2.0 web application flow for Google Drive authentication
- File upload with optional overwrite functionality
- Folder creation and deletion
- Health check endpoints
- Comprehensive error handling and logging
"""

import logging
import os
import tempfile
import time
import traceback
from typing import List, Optional, Tuple

from flask import Flask, Response, jsonify, render_template_string, request
from werkzeug.exceptions import HTTPException

# Import enhanced logging and error handling
try:
    from src.core import (
        ConfigurationError,
        DriveAuthenticationError,
        DriveOperationError,
        configure_logging,
        get_logger,
        handle_api_errors,
        validate_drive_parameters,
    )

    HAS_ENHANCED_LOGGING = True
except ImportError:
    HAS_ENHANCED_LOGGING = False

from google_drive_utils import (
    authenticate_google_drive,
    check_token_exists,
    create_folder_if_not_exists,
    delete_folder_by_path,
    exchange_code_for_tokens,
    generate_authorization_url,
    upload_file_to_drive,
)
from version import get_version, get_version_info

app = Flask(__name__)

# Configure enhanced logging early
if HAS_ENHANCED_LOGGING:
    configure_logging(
        log_level=os.environ.get("LOG_LEVEL", "INFO"),
        enable_console=os.environ.get("LOG_ENABLE_CONSOLE", "true").lower() == "true",
        enable_file=os.environ.get("LOG_ENABLE_FILE", "true").lower() == "true",
        enable_structured=os.environ.get("LOG_ENABLE_STRUCTURED", "true").lower() == "true",
        log_dir=os.environ.get("LOG_DIR", "logs"),
        log_file=os.environ.get("LOG_FILE", "google-drive-service.log"),
    )
    logger = get_logger(__name__, "app")
else:
    # Fallback to basic logging
    log_level = os.environ.get("LOG_LEVEL", "INFO").upper()
    logging.basicConfig(
        level=getattr(logging, log_level), format="%(asctime)s - %(levelname)s - %(name)s - %(message)s"
    )
    logger = logging.getLogger(__name__)

# Request tracking for debugging
request_count = 0


# Error handling and request tracking middleware
@app.before_request
def before_request() -> None:
    """Log and track incoming requests (excluding health checks)."""
    global request_count
    request_count += 1
    request.start_time = time.time()
    request.request_id = f"{int(time.time())}-{request_count}"

    # Skip logging for health check endpoints to reduce noise
    if request.path in ["/health", "/ping"]:
        return

    logger.info(f"Request {request.request_id} started: {request.method} {request.path} " f"[{request.remote_addr}]")

    # Log request data for debugging (excluding file uploads)
    if request.content_type and "multipart/form-data" not in request.content_type:
        logger.debug(f"Request {request.request_id} data: {request.get_data(as_text=True)}")


@app.after_request
def after_request(response: Response) -> Response:
    """Log response information (excluding health checks)."""
    # Skip logging for health check endpoints to reduce noise
    if request.path in ["/health", "/ping"]:
        return response

    if hasattr(request, "start_time") and hasattr(request, "request_id"):
        duration = time.time() - request.start_time
        logger.info(f"Request {request.request_id} completed: {response.status_code} " f"in {duration:.3f}s")
    return response


@app.errorhandler(Exception)
def handle_exception(e: Exception) -> Tuple[Response, int]:
    """Handle all unhandled exceptions."""
    # Log the exception with traceback
    logger.error(f"Unhandled exception: {str(e)}\n{traceback.format_exc()}")

    # Handle HTTP exceptions
    if isinstance(e, HTTPException):
        return (
            jsonify({"error": {"type": "HTTPException", "code": e.code, "name": e.name, "description": e.description}}),
            e.code,
        )

    # Handle all other exceptions
    return jsonify({"error": {"type": e.__class__.__name__, "message": str(e)}}), 500


# API Endpoints
@app.route("/authorize_gdrive", methods=["GET"])
@handle_api_errors("authorize_gdrive", "app") if HAS_ENHANCED_LOGGING else lambda f: f
def authorize_gdrive_endpoint() -> Tuple[Response, int]:
    """Endpoint to get the Google Drive authorization URL with enhanced logging."""
    try:
        logger.info("Generating Google Drive authorization URL")
        authorization_url = generate_authorization_url()

        if not authorization_url:
            logger.error("Failed to generate authorization URL")
            return (
                jsonify({"error": {"type": "AuthorizationError", "message": "Failed to generate authorization URL"}}),
                500,
            )

        logger.info("Successfully generated authorization URL")
        return jsonify({"status": "success", "authorization_url": authorization_url}), 200

    except Exception as e:
        logger.exception(f"Error generating authorization URL: {e}")
        return jsonify({"error": {"type": e.__class__.__name__, "message": str(e)}}), 500


@app.route("/submit_auth_code", methods=["POST"])
@handle_api_errors("submit_auth_code", "app") if HAS_ENHANCED_LOGGING else lambda f: f
def submit_auth_code_endpoint() -> Tuple[Response, int]:
    """Endpoint to submit the authorization code and obtain tokens with enhanced logging."""
    try:
        # Get authorization code from form data
        code = request.form.get("code")

        if not code:
            logger.warning("Authorization code is required but was not provided")
            return (
                jsonify(
                    {"error": {"type": "ValidationError", "message": "Authorization code is required", "field": "code"}}
                ),
                400,
            )

        logger.info("Exchanging authorization code for tokens")
        success = exchange_code_for_tokens(code)

        if success:
            logger.info("Successfully exchanged authorization code for tokens")
            return jsonify({"status": "success", "message": "Authorization successful"}), 200
        else:
            logger.error("Failed to exchange authorization code for tokens")
            return (
                jsonify(
                    {
                        "error": {
                            "type": "AuthorizationError",
                            "message": "Failed to exchange authorization code for tokens",
                        }
                    }
                ),
                500,
            )

    except Exception as e:
        logger.exception(f"Error exchanging authorization code: {e}")
        return jsonify({"error": {"type": e.__class__.__name__, "message": str(e)}}), 500


@app.route("/oauth/callback", methods=["GET"])
@handle_api_errors("oauth_callback", "app") if HAS_ENHANCED_LOGGING else lambda f: f
def oauth_callback() -> Tuple[Response, int]:
    """Handle OAuth callback endpoint to process authorization code from Google with enhanced logging."""
    try:
        # Get authorization code from query parameters
        code = request.args.get("code")
        error = request.args.get("error")

        if error:
            logger.error(f"OAuth authorization error: {error}")
            return (
                render_template_string(
                    """
            <!DOCTYPE html>
            <html>
            <head><title>Authorization Failed</title></head>
            <body>
                <h1>Authorization Failed</h1>
                <p>Error: {{ error }}</p>
                <p>Please try again by visiting <a href="/authorize_gdrive">/authorize_gdrive</a></p>
            </body>
            </html>
            """,
                    error=error,
                ),
                400,
            )

        if not code:
            logger.warning("No authorization code received in OAuth callback")
            return (
                render_template_string(
                    """
            <!DOCTYPE html>
            <html>
            <head><title>Authorization Failed</title></head>
            <body>
                <h1>Authorization Failed</h1>
                <p>No authorization code received.</p>
                <p>Please try again by visiting <a href="/authorize_gdrive">/authorize_gdrive</a></p>
            </body>
            </html>
            """
                ),
                400,
            )

        logger.info("Received authorization code via OAuth callback")
        success = exchange_code_for_tokens(code)

        if success:
            logger.info("Successfully exchanged authorization code for tokens via OAuth callback")
            return (
                render_template_string(
                    """
            <!DOCTYPE html>
            <html>
            <head><title>Authorization Successful</title></head>
            <body>
                <h1>Authorization Successful!</h1>
                <p>Google Drive access has been granted successfully.</p>
                <p>You can now close this window and return to your application.</p>
                <script>
                    // Auto-close window after 3 seconds
                    setTimeout(function() {
                        window.close();
                    }, 3000);
                </script>
            </body>
            </html>
            """
                ),
                200,
            )
        else:
            logger.error("Failed to exchange authorization code for tokens via OAuth callback")
            return (
                render_template_string(
                    """
            <!DOCTYPE html>
            <html>
            <head><title>Authorization Failed</title></head>
            <body>
                <h1>Authorization Failed</h1>
                <p>Failed to exchange authorization code for tokens.</p>
                <p>Please try again by visiting <a href="/authorize_gdrive">/authorize_gdrive</a></p>
            </body>
            </html>
            """
                ),
                500,
            )

    except Exception as e:
        logger.exception(f"Error in OAuth callback: {e}")
        return (
            render_template_string(
                """
        <!DOCTYPE html>
        <html>
        <head><title>Authorization Error</title></head>
        <body>
            <h1>Authorization Error</h1>
            <p>An unexpected error occurred: {{ error }}</p>
            <p>Please try again by visiting <a href="/authorize_gdrive">/authorize_gdrive</a></p>
        </body>
        </html>
        """,
                error=str(e),
            ),
            500,
        )


def _validate_upload_request() -> Tuple[Optional[list], Optional[str], Optional[bool]]:
    """Validate upload request parameters.

    Returns:
        Tuple of (validation_errors, folder_path, overwrite) or (errors, None, None) if invalid
    """
    validation_errors = []

    if "file" not in request.files:
        validation_errors.append({"field": "file", "message": "No file part"})
    else:
        file = request.files["file"]
        if file.filename == "":
            validation_errors.append({"field": "file", "message": "No selected file"})

    folder_path = request.form.get("folder_path")
    if not folder_path:
        validation_errors.append({"field": "folder_path", "message": "Folder path is required"})

    # Get overwrite parameter (default is True)
    overwrite_param = request.form.get("overwrite", "true").lower()
    overwrite = overwrite_param != "false"  # Only 'false' will disable overwriting

    if validation_errors:
        return validation_errors, None, None

    return None, folder_path, overwrite


def _handle_file_upload(file, folder_path: str, overwrite: bool) -> Tuple[Optional[str], Optional[str]]:
    """Handle the actual file upload process.

    Returns:
        Tuple of (file_url, temp_file_path) or (None, temp_file_path) if failed
    """
    # Authenticate with Google Drive
    logger.info(f"Authenticating with Google Drive for file upload: {file.filename}")
    drive_service = authenticate_google_drive()
    if not drive_service:
        logger.error("Google Drive authentication failed")
        return None, None

    # Create folder structure if needed
    logger.info(f"Creating folder structure: {folder_path}")
    folder_id = create_folder_if_not_exists(drive_service, folder_path)
    if not folder_id:
        logger.error(f"Failed to create folder structure: {folder_path}")
        return None, None

    # Save file to secure temporary location
    temp_dir = tempfile.gettempdir()  # Get system temp directory securely
    temp_file_path = os.path.join(temp_dir, f"gdrive_upload_{file.filename}")
    logger.debug(f"Saving uploaded file to temporary location: {temp_file_path}")
    file.save(temp_file_path)

    # Upload file to Google Drive
    logger.info(f"Uploading file to Google Drive: {file.filename} (overwrite={overwrite})")
    file_url = upload_file_to_drive(drive_service, temp_file_path, folder_id, overwrite=overwrite)

    return file_url, temp_file_path


def _create_auth_error_response() -> Tuple[Response, int]:
    """Create authentication error response."""
    return (
        jsonify(
            {
                "error": {
                    "type": "AuthenticationError",
                    "message": "Authorization required. Please visit /authorize_gdrive first and then "
                    "/submit_auth_code.",
                }
            }
        ),
        401,
    )


def _create_validation_error_response(validation_errors: List[str]) -> Tuple[Response, int]:
    """Create validation error response."""
    return (
        jsonify(
            {
                "error": {
                    "type": "ValidationError",
                    "message": "Invalid request parameters",
                    "details": validation_errors,
                }
            }
        ),
        400,
    )


def _create_upload_success_response(
    file_url: str, filename: str, folder_path: str, overwrite: bool
) -> Tuple[Response, int]:
    """Create successful upload response."""
    return (
        jsonify(
            {
                "status": "success",
                "file_url": file_url,
                "file_name": filename,
                "folder_path": folder_path,
                "overwrite_mode": "enabled" if overwrite else "disabled",
            }
        ),
        200,
    )


def _cleanup_temp_file(temp_file_path: str) -> None:
    """Clean up temporary file safely."""
    if temp_file_path and os.path.exists(temp_file_path):
        try:
            logger.debug(f"Removing temporary file: {temp_file_path}")
            os.remove(temp_file_path)
        except Exception as cleanup_error:
            logger.error(f"Failed to remove temporary file: {cleanup_error}")


@app.route("/upload_file", methods=["POST"])
@handle_api_errors("upload_file", "app") if HAS_ENHANCED_LOGGING else lambda f: f
def upload_file_endpoint() -> Tuple[Response, int]:
    """Endpoint to upload a file to Google Drive with enhanced logging.

    Optional form parameters:
    - overwrite: Set to 'false' to keep both files if a file with the same name exists.
                Default is 'true' (overwrite existing files).
    """
    temp_file_path = None

    try:
        # Check authentication
        if not check_token_exists():
            logger.warning("Upload attempted without authentication")
            return _create_auth_error_response()

        # Validate request parameters
        validation_errors, folder_path, overwrite = _validate_upload_request()
        if validation_errors:
            logger.warning(f"Validation errors in upload request: {validation_errors}")
            return _create_validation_error_response(validation_errors)

        file = request.files["file"]

        # Handle file upload
        file_url, temp_file_path = _handle_file_upload(file, folder_path, overwrite)

        if not file_url:
            # Handle specific error cases
            if temp_file_path is None:
                # Authentication or folder creation failed
                return (
                    jsonify(
                        {
                            "error": {
                                "type": "AuthenticationError",
                                "message": "Google Drive authentication failed (tokens invalid or missing). "
                                "Re-authorize.",
                            }
                        }
                    ),
                    500,
                )
            else:
                # Upload failed
                logger.error(f"File upload failed: {file.filename}")
                return jsonify({"error": {"type": "UploadError", "message": "File upload failed to Google Drive"}}), 500

        # Clean up temporary file
        _cleanup_temp_file(temp_file_path)

        # Success response
        logger.info(f"File uploaded successfully: {file.filename}")
        return _create_upload_success_response(file_url, file.filename, folder_path, overwrite)

    except Exception as e:
        logger.exception(f"Error during file upload: {e}")

        # Clean up temporary file if it exists
        _cleanup_temp_file(temp_file_path)

        return jsonify({"error": {"type": e.__class__.__name__, "message": str(e)}}), 500


@app.route("/delete_folder", methods=["POST"])
@handle_api_errors("delete_folder", "app") if HAS_ENHANCED_LOGGING else lambda f: f
def delete_folder_endpoint() -> Tuple[Response, int]:
    """Endpoint to delete a folder in Google Drive by path with enhanced logging."""
    try:
        # Validate request parameters
        folder_path = request.form.get("folder_path")  # Get folder path from form data

        if not folder_path:
            logger.warning("Delete folder request missing folder_path parameter")
            return (
                jsonify(
                    {"error": {"type": "ValidationError", "message": "Folder path is required", "field": "folder_path"}}
                ),
                400,
            )

        # Check authentication
        if not check_token_exists():
            logger.warning("Delete folder attempted without authentication")
            return (
                jsonify(
                    {
                        "error": {
                            "type": "AuthenticationError",
                            "message": "Authorization required. Please visit /authorize_gdrive first and then "
                            "/submit_auth_code.",
                        }
                    }
                ),
                401,
            )

        # Authenticate with Google Drive
        logger.info(f"Authenticating with Google Drive for folder deletion: {folder_path}")
        drive_service = authenticate_google_drive()
        if not drive_service:
            logger.error("Google Drive authentication failed")
            return (
                jsonify(
                    {
                        "error": {
                            "type": "AuthenticationError",
                            "message": "Google Drive authentication failed (tokens invalid or missing). Re-authorize.",
                        }
                    }
                ),
                500,
            )

        # Delete the folder
        logger.info(f"Deleting folder: {folder_path}")
        if delete_folder_by_path(drive_service, folder_path):
            logger.info(f"Successfully deleted folder: {folder_path}")
            return jsonify({"status": "success", "message": f'Folder "{folder_path}" deleted successfully'}), 200
        else:
            logger.warning(f"Failed to delete folder: {folder_path}")
            return (
                jsonify(
                    {
                        "error": {
                            "type": "DeletionError",
                            "message": f'Failed to delete folder "{folder_path}" or folder not found',
                        }
                    }
                ),
                404,
            )  # Using 404 is more appropriate when the resource is not found

    except Exception as e:
        logger.exception(f"Error during folder deletion: {e}")
        return jsonify({"error": {"type": e.__class__.__name__, "message": str(e)}}), 500


@app.route("/ping")
def ping() -> Tuple[Response, int]:
    """Ultra-lightweight health check for Docker and load balancers.

    This endpoint performs no authentication or external API calls.
    It only verifies that the Flask application is running and responsive.

    Returns:
        Simple "OK" response with 200 status code
    """
    return "OK", 200


@app.route("/health")
def health_check() -> Tuple[Response, int]:
    """Basic health check endpoint with minimal overhead.

    This endpoint checks service availability without performing authentication
    or external API calls. For authentication status, use /auth/status.
    For full service validation, use /service/status.

    Returns:
        JSON response with basic service health status
    """
    start_time = time.time()

    response = {
        "service": "google-drive-service",
        "timestamp": time.time(),
        "version": get_version(),
        "status": "healthy",
    }

    duration = time.time() - start_time
    logger.info(f"✅ Health check OK ({duration:.3f}s)")

    return jsonify(response), 200


@app.route("/auth/status")
def auth_status() -> Tuple[Response, int]:
    """Check authentication status without performing authentication.

    This endpoint only checks if authentication tokens exist on disk.
    It does not perform OAuth flows or make API calls to Google Drive.

    Returns:
        JSON response with authentication status
    """
    response = {"service": "google-drive-service", "timestamp": time.time(), "version": get_version()}

    # Check if token file exists (no authentication performed)
    token_exists = check_token_exists()
    response["auth_status"] = "authenticated" if token_exists else "unauthenticated"

    if token_exists:
        response["status"] = "authenticated"
        response["message"] = "Authentication tokens are available"
    else:
        response["status"] = "unauthenticated"
        response["message"] = "Authentication required. Visit /authorize_gdrive to authenticate."

    return jsonify(response), 200


@app.route("/service/status")
def service_status() -> Tuple[Response, int]:
    """Full service validation including authentication and API connectivity.

    This endpoint performs complete service validation including:
    - Authentication with Google Drive
    - API connectivity test
    - Full service functionality check

    Use this endpoint sparingly as it performs actual authentication and API calls.
    For regular health checks, use /health or /ping instead.

    Returns:
        JSON response with complete service status
    """
    response = {"service": "google-drive-service", "timestamp": time.time(), "version": get_version()}

    # Check if token file exists
    token_exists = check_token_exists()
    response["auth_status"] = "authenticated" if token_exists else "unauthenticated"

    # Perform full authentication and API connectivity check
    try:
        start_time = time.time()
        drive_service = authenticate_google_drive()
        api_response_time = time.time() - start_time
        response["api_response_time_ms"] = round(api_response_time * 1000, 2)

        if drive_service:
            # Try a simple API call to verify connectivity
            drive_service.files().list(pageSize=1).execute()
            response["status"] = "healthy"
            response["api_connectivity"] = True
            response["message"] = "Service is fully operational"
            return jsonify(response), 200
        else:
            response["status"] = "degraded"
            response["reason"] = "auth_required"
            response["api_connectivity"] = False
            response["message"] = "Authentication required. Visit /authorize_gdrive to authenticate."
            return jsonify(response), 200
    except Exception as e:
        response["status"] = "unhealthy"
        response["reason"] = str(e)
        response["api_connectivity"] = False
        response["error_type"] = e.__class__.__name__
        logger.error(f"Service status check failed: {e}")
        return jsonify(response), 500


# Add a route to get service information
@app.route("/info")
def service_info() -> Tuple[Response, int]:
    """Returns information about the service."""
    info = {
        "service": "google-drive-service",
        "description": "Service for interacting with Google Drive",
        "version": get_version(),
        "endpoints": [
            {"path": "/authorize_gdrive", "method": "GET", "description": "Get Google Drive authorization URL"},
            {
                "path": "/submit_auth_code",
                "method": "POST",
                "description": "Submit authorization code to obtain tokens",
            },
            {
                "path": "/oauth/callback",
                "method": "GET",
                "description": "OAuth callback endpoint (used automatically by Google)",
            },
            {"path": "/upload_file", "method": "POST", "description": "Upload a file to Google Drive"},
            {"path": "/delete_folder", "method": "POST", "description": "Delete a folder in Google Drive"},
            {"path": "/health", "method": "GET", "description": "Check service health"},
            {"path": "/info", "method": "GET", "description": "Get service information"},
        ],
        "environment": os.environ.get("FLASK_ENV", "production"),
    }
    return jsonify(info), 200


@app.route("/version")
def version_endpoint() -> Tuple[Response, int]:
    """Returns detailed version information."""
    return jsonify(get_version_info()), 200


if __name__ == "__main__":
    # Get debug mode from environment variable
    debug_mode = os.environ.get("FLASK_DEBUG", "false").lower() == "true"

    # Get port from environment variable or use default
    port = int(os.environ.get("PORT", 5000))

    # Get host from environment variable or use localhost for security
    host = os.environ.get("FLASK_HOST", "127.0.0.1")  # Default to localhost for security

    logger.info(f"Starting Google Drive Service on {host}:{port} (debug={debug_mode})")
    app.run(debug=debug_mode, host=host, port=port)
