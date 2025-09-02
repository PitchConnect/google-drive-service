"""Google Drive utilities module.

This module provides utility functions for interacting with the Google Drive API,
including authentication, file operations, and folder management.

Key features:
- OAuth 2.0 authentication with token management
- Retry logic with exponential backoff for API calls
- Rate limiting to respect Google API quotas
- Circuit breaker pattern for fault tolerance
- Comprehensive error handling and logging

The module supports both web application and installed application OAuth flows,
with automatic token refresh and error recovery.
"""

import logging
import os
from typing import Any, Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload

# Import enhanced logging and error handling
try:
    from src.core import (
        get_logger,
        handle_drive_operations,
        safe_drive_operation,
        validate_drive_parameters,
        DriveAuthenticationError,
        DriveAPIError,
        DriveFileError,
        DriveFolderError,
        log_drive_metrics,
    )
    HAS_ENHANCED_LOGGING = True
except ImportError:
    HAS_ENHANCED_LOGGING = False

from retry_utils import circuit_breaker, detailed_error_response, rate_limit, retry

SCOPES = [
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/contacts",
]
CREDENTIALS_PATH = os.getenv("GOOGLE_CREDENTIALS_PATH", "/app/credentials/google-credentials.json")
TOKEN_PATH = os.getenv("GOOGLE_TOKEN_PATH", "/app/data/google-drive-token.json")
# Use loopback IP address for OAuth redirect (replaces deprecated OOB flow)
REDIRECT_URI = "http://localhost:9085/oauth/callback"

# Configure enhanced logging
if HAS_ENHANCED_LOGGING:
    logger = get_logger(__name__, 'drive_utils')
else:
    # Fallback to basic logging
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    logger = logging.getLogger(__name__)

# Constants for error handling
MAX_RETRIES = 3
INITIAL_RETRY_DELAY = 1.0
MAX_RETRY_DELAY = 15.0
BACKOFF_FACTOR = 2.0

# Rate limiting constants
API_CALLS_PER_SECOND = 5.0  # Maximum 5 calls per second to avoid quota issues
MAX_BURST = 10  # Allow bursts of up to 10 calls


def check_token_exists():
    """Checks if token.json exists."""
    return os.path.exists(TOKEN_PATH)


def generate_authorization_url():
    """Generates the Google Drive authorization URL."""
    try:
        # Use Flow for web application credentials (supports both "web" and "installed" formats)
        flow = Flow.from_client_secrets_file(CREDENTIALS_PATH, SCOPES, redirect_uri=REDIRECT_URI)
        authorization_url, _ = flow.authorization_url(
            prompt="consent", access_type="offline", include_granted_scopes="true"
        )
        return authorization_url
    except Exception as e:
        logger.exception(f"Error generating authorization URL: {e}")
        return None


def exchange_code_for_tokens(code):
    """Exchanges the authorization code for access and refresh tokens and saves them."""
    try:
        # Use Flow for web application credentials (supports both "web" and "installed" formats)
        flow = Flow.from_client_secrets_file(CREDENTIALS_PATH, SCOPES, redirect_uri=REDIRECT_URI)

        # Exchange the authorization code for tokens
        # Using multi-scope approach to match shared OAuth client configuration
        flow.fetch_token(code=code)

        creds = flow.credentials
        if creds and creds.valid:
            with open(TOKEN_PATH, "w") as token:
                token.write(creds.to_json())
            logger.info("Successfully exchanged authorization code for tokens")
            return True  # Success
        else:
            logger.error("Failed to get valid credentials from authorization code")
            return False  # Failed to get valid credentials
    except Exception as e:
        logger.exception(f"Error exchanging authorization code for tokens: {e}")
        return False  # Exchange failed


def _load_existing_credentials() -> Optional[Credentials]:
    """Load existing credentials from token file.

    Returns:
        Credentials object if successful, None otherwise.
    """
    if not os.path.exists(TOKEN_PATH):
        return None

    try:
        return Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)
    except Exception as e:
        logger.error(f"Error loading credentials from {TOKEN_PATH}: {e}")
        return None


def _refresh_credentials(creds: Credentials) -> Optional[Credentials]:
    """Refresh expired credentials and save them.

    Args:
        creds: Expired credentials to refresh.

    Returns:
        Refreshed credentials if successful, None otherwise.
    """
    try:
        logger.info("Refreshing expired credentials")
        creds.refresh(Request())
        # Save the refreshed credentials
        with open(TOKEN_PATH, "w") as token:
            token.write(creds.to_json())
        logger.info("Credentials refreshed successfully")
        return creds
    except Exception as e:
        logger.exception(f"Error refreshing credentials: {e}")
        # Only remove the token file if it's definitely invalid
        if "invalid_grant" in str(e).lower() or "invalid_token" in str(e).lower():
            logger.warning(f"Removing invalid token file: {TOKEN_PATH}")
            os.remove(TOKEN_PATH)
        return None


def _build_drive_service(creds: Credentials) -> Optional[Any]:
    """Build and test Google Drive service.

    Args:
        creds: Valid credentials.

    Returns:
        Google Drive service object if successful, None otherwise.

    Raises:
        Exception: If API call fails after retries.
    """
    try:
        logger.debug("Building Google Drive service")
        service = build("drive", "v3", credentials=creds)
        # Test the service with a simple request
        service.files().list(pageSize=1).execute()
        logger.info("Google Drive authentication successful")
        return service
    except HttpError as error:
        error_details = detailed_error_response(error)
        logger.error(f"Google Drive API error during authentication: {error_details}")
        # If it's a credentials issue, force re-auth
        if error.resp.status in [401, 403]:
            logger.warning("Authentication error, credentials may be invalid")
            return None
        # For other errors, let the retry mechanism handle it
        raise
    except Exception as e:
        logger.exception(f"Unexpected error during authentication: {e}")
        raise


@retry(max_retries=MAX_RETRIES, initial_delay=INITIAL_RETRY_DELAY, max_delay=MAX_RETRY_DELAY)
@handle_drive_operations("authenticate_google_drive", "auth") if HAS_ENHANCED_LOGGING else lambda f: f
def authenticate_google_drive() -> Optional[Any]:
    """Authenticates with Google Drive API using existing tokens if available with enhanced logging.

    Returns:
        Google Drive service object if authentication is successful, None otherwise.

    Raises:
        Exception: If authentication fails after retries.
    """
    # Load existing credentials
    creds = _load_existing_credentials()

    # Handle invalid or expired credentials
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds = _refresh_credentials(creds)
            if not creds:
                return None  # Refresh failed
        else:
            logger.info("No valid credentials available, authorization required")
            return None  # No valid credentials available, force authorization flow

    # Build and test the service
    return _build_drive_service(creds)


@retry(max_retries=MAX_RETRIES, initial_delay=INITIAL_RETRY_DELAY, max_delay=MAX_RETRY_DELAY)
@handle_drive_operations("create_folder_if_not_exists", "folder_ops") if HAS_ENHANCED_LOGGING else lambda f: f
def create_folder_if_not_exists(drive_service: Any, folder_path: str) -> Optional[str]:
    """Creates folders in Google Drive if they don't exist with enhanced logging.

    Handles nested folders as well.

    Args:
        drive_service: The Google Drive service instance.
        folder_path: Path of folders to create, separated by '/'.

    Returns:
        The ID of the last folder created (or existing folder), or None if creation fails.

    Raises:
        Exception: If folder creation fails after retries.
    """
    if not drive_service:
        logger.error("Cannot create folder: drive_service is None")
        return None

    parent_folder_id = "root"  # Start at the root of Drive
    folders = folder_path.strip("/").split("/")  # Split path into folder names

    # Skip empty folder names
    folders = [f for f in folders if f]
    if not folders:
        return parent_folder_id

    try:
        for folder_name in folders:
            logger.debug(f"Processing folder: {folder_name} (parent: {parent_folder_id})")
            folder_id = find_folder_id(drive_service, folder_name, parent_folder_id)
            if not folder_id:
                logger.info(f"Folder '{folder_name}' not found, creating it")
                folder_id = create_folder(drive_service, folder_name, parent_folder_id)
                if not folder_id:
                    logger.error(f"Failed to create folder '{folder_name}'")
                    return None
                logger.info(f"Created folder '{folder_name}' with ID: {folder_id}")
            else:
                logger.debug(f"Found existing folder '{folder_name}' with ID: {folder_id}")
            parent_folder_id = folder_id  # Next folder will be inside this one

        return parent_folder_id  # Return the ID of the final folder
    except Exception as e:
        logger.exception(f"Error creating folder path '{folder_path}': {e}")
        raise


@retry(max_retries=MAX_RETRIES, initial_delay=INITIAL_RETRY_DELAY, max_delay=MAX_RETRY_DELAY)
@rate_limit(calls_per_second=API_CALLS_PER_SECOND, max_burst=MAX_BURST)
def find_folder_id(drive_service: Any, folder_name: str, parent_id: str) -> Optional[str]:
    """Finds a folder ID by name within a parent folder.

    Args:
        drive_service: The Google Drive service instance.
        folder_name: Name of the folder to find.
        parent_id: ID of the parent folder to search in.

    Returns:
        The ID of the found folder, or None if not found.

    Raises:
        Exception: If the API call fails after retries.
    """
    if not drive_service:
        logger.error("Cannot find folder: drive_service is None")
        return None

    # Escape single quotes in folder name for the query
    safe_folder_name = folder_name.replace("'", "\\'") if folder_name else ""

    if not safe_folder_name:
        logger.warning("Empty folder name provided to find_folder_id")
        return None

    try:
        logger.debug(f"Searching for folder '{safe_folder_name}' in parent '{parent_id}'")
        results = (
            drive_service.files()
            .list(
                q=f"mimeType='application/vnd.google-apps.folder' and name='{safe_folder_name}' and "
                f"'{parent_id}' in parents and trashed=false",
                fields="files(id,name)",
                pageSize=1,  # We only need the first match
            )
            .execute()
        )

        items = results.get("files", [])
        if items:
            folder_id = items[0]["id"]
            logger.debug(f"Found folder '{safe_folder_name}' with ID: {folder_id}")
            return folder_id
        else:
            logger.debug(f"Folder '{safe_folder_name}' not found in parent '{parent_id}'")
            return None  # Folder not found
    except HttpError as error:
        error_details = detailed_error_response(error)
        logger.error(f"Google Drive API error while finding folder: {error_details}")
        raise
    except Exception as e:
        logger.exception(f"Unexpected error while finding folder '{safe_folder_name}': {e}")
        raise


@retry(max_retries=MAX_RETRIES, initial_delay=INITIAL_RETRY_DELAY, max_delay=MAX_RETRY_DELAY)
@rate_limit(calls_per_second=API_CALLS_PER_SECOND, max_burst=MAX_BURST)
def create_folder(drive_service: Any, folder_name: str, parent_id: str) -> Optional[str]:
    """Creates a folder in Google Drive.

    Args:
        drive_service: The Google Drive service instance.
        folder_name: Name of the folder to create.
        parent_id: ID of the parent folder.

    Returns:
        The ID of the created folder, or None if creation fails.

    Raises:
        Exception: If the API call fails after retries.
    """
    if not drive_service:
        logger.error("Cannot create folder: drive_service is None")
        return None

    if not folder_name:
        logger.error("Cannot create folder: folder_name is empty")
        return None

    file_metadata = {"name": folder_name, "mimeType": "application/vnd.google-apps.folder", "parents": [parent_id]}

    try:
        logger.debug(f"Creating folder '{folder_name}' in parent '{parent_id}'")
        file = drive_service.files().create(body=file_metadata, fields="id,name").execute()

        folder_id = file.get("id")
        logger.info(f"Created folder '{folder_name}' with ID: {folder_id}")
        return folder_id
    except HttpError as error:
        error_details = detailed_error_response(error)
        logger.error(f"Google Drive API error while creating folder: {error_details}")
        raise
    except Exception as e:
        logger.exception(f"Unexpected error while creating folder '{folder_name}': {e}")
        raise


@retry(max_retries=MAX_RETRIES, initial_delay=INITIAL_RETRY_DELAY, max_delay=MAX_RETRY_DELAY)
@rate_limit(calls_per_second=API_CALLS_PER_SECOND, max_burst=MAX_BURST)
def find_file_id(drive_service: Any, file_name: str, folder_id: str) -> Optional[str]:
    """Finds a file ID by name within a parent folder.

    Args:
        drive_service: The Google Drive service instance.
        file_name: Name of the file to find.
        folder_id: ID of the folder to search in.

    Returns:
        The ID of the found file, or None if not found.

    Raises:
        Exception: If the API call fails after retries.
    """
    if not drive_service:
        logger.error("Cannot find file: drive_service is None")
        return None

    # Escape single quotes in file name for the query
    safe_file_name = file_name.replace("'", "\\'") if file_name else ""

    if not safe_file_name:
        logger.warning("Empty file name provided to find_file_id")
        return None

    try:
        logger.debug(f"Searching for file '{safe_file_name}' in folder '{folder_id}'")
        results = (
            drive_service.files()
            .list(
                q=f"name='{safe_file_name}' and '{folder_id}' in parents and trashed=false",
                fields="files(id,name)",
                pageSize=1,  # We only need the first match
            )
            .execute()
        )

        items = results.get("files", [])
        if items:
            file_id = items[0]["id"]
            logger.debug(f"Found file '{safe_file_name}' with ID: {file_id}")
            return file_id
        else:
            logger.debug(f"File '{safe_file_name}' not found in folder '{folder_id}'")
            return None  # File not found
    except HttpError as error:
        error_details = detailed_error_response(error)
        logger.error(f"Google Drive API error while finding file: {error_details}")
        raise
    except Exception as e:
        logger.exception(f"Unexpected error while finding file '{safe_file_name}': {e}")
        raise


@retry(max_retries=MAX_RETRIES, initial_delay=INITIAL_RETRY_DELAY, max_delay=MAX_RETRY_DELAY)
@rate_limit(calls_per_second=API_CALLS_PER_SECOND, max_burst=MAX_BURST)
def delete_file_by_id(drive_service: Any, file_id: str) -> bool:
    """Deletes a file in Google Drive by its file ID.

    Args:
        drive_service: The Google Drive service instance.
        file_id: ID of the file to delete.

    Returns:
        True if deletion was successful, False otherwise.

    Raises:
        Exception: If the API call fails after retries.
    """
    if not drive_service:
        logger.error("Cannot delete file: drive_service is None")
        return False

    if not file_id:
        logger.error("Cannot delete file: file_id is empty")
        return False

    try:
        logger.debug(f"Deleting file with ID: {file_id}")
        drive_service.files().delete(fileId=file_id).execute()
        logger.info(f"Successfully deleted file with ID: {file_id}")
        return True  # Deletion successful
    except HttpError as error:
        # If the file doesn't exist (404), consider it a success
        if error.resp.status == 404:
            logger.warning(f"File with ID {file_id} not found (already deleted)")
            return True

        error_details = detailed_error_response(error)
        logger.error(f"Google Drive API error while deleting file: {error_details}")

        # For permission errors, don't retry
        if error.resp.status == 403:
            logger.error(f"Permission denied when deleting file with ID: {file_id}")
            return False

        raise
    except Exception as e:
        logger.exception(f"Unexpected error while deleting file with ID {file_id}: {e}")
        raise


def _validate_upload_parameters(drive_service: Any, file_path: str, folder_id: str) -> bool:
    """Validate upload parameters.

    Args:
        drive_service: The Google Drive service instance.
        file_path: Path to the file to upload.
        folder_id: ID of the folder to upload to.

    Returns:
        True if all parameters are valid, False otherwise.
    """
    if not drive_service:
        logger.error("Cannot upload file: drive_service is None")
        return False

    if not os.path.exists(file_path):
        logger.error(f"Cannot upload file: file '{file_path}' does not exist")
        return False

    if not folder_id:
        logger.error("Cannot upload file: folder_id is empty")
        return False

    return True


def _handle_existing_file(drive_service: Any, file_name: str, folder_id: str, overwrite: bool) -> None:
    """Handle existing file based on overwrite setting.

    Args:
        drive_service: The Google Drive service instance.
        file_name: Name of the file to check.
        folder_id: ID of the folder to search in.
        overwrite: Whether to overwrite existing files.
    """
    if not overwrite:
        return

    try:
        existing_file_id = find_file_id(drive_service, file_name, folder_id)
        if existing_file_id:
            logger.info(f"Found existing file '{file_name}' with ID {existing_file_id}. Deleting it before upload.")
            delete_success = delete_file_by_id(drive_service, existing_file_id)
            if not delete_success:
                logger.warning(f"Failed to delete existing file '{file_name}'. Proceeding with upload anyway.")
    except Exception as e:
        logger.warning(f"Error checking for existing file: {e}. Proceeding with upload anyway.")


def _perform_resumable_upload(drive_service: Any, file_path: str, file_name: str, folder_id: str) -> Optional[str]:
    """Perform the actual file upload with resumable upload and progress tracking.

    Args:
        drive_service: The Google Drive service instance.
        file_path: Path to the file to upload.
        file_name: Name of the file.
        folder_id: ID of the folder to upload to.

    Returns:
        The webViewLink of the uploaded file, or None if upload failed.

    Raises:
        Exception: If the API call fails after retries.
    """
    try:
        # Use resumable upload for all files to handle network interruptions
        media = MediaFileUpload(file_path, resumable=True, chunksize=1024 * 1024)  # 1MB chunks
        file_metadata = {"name": file_name, "parents": [folder_id]}

        logger.debug(f"Starting upload of file '{file_name}'")
        request = drive_service.files().create(body=file_metadata, media_body=media, fields="id,name,webViewLink,size")

        # Use resumable upload with progress tracking
        response = None
        last_progress = 0
        while response is None:
            status, response = request.next_chunk()
            if status:
                progress = int(status.progress() * 100)
                # Only log if progress has increased by at least 20%
                if progress - last_progress >= 20:
                    logger.info(f"Upload of '{file_name}' in progress: {progress}%")
                    last_progress = progress

        logger.info(f"File '{file_name}' uploaded successfully. File ID: {response.get('id')}")
        return response.get("webViewLink")  # Return the webViewLink (shareable link)
    except HttpError as error:
        error_details = detailed_error_response(error)
        logger.error(f"Google Drive API error during file upload: {error_details}")
        raise
    except Exception as e:
        logger.exception(f"Unexpected error during file upload: {e}")
        raise


@retry(max_retries=MAX_RETRIES, initial_delay=INITIAL_RETRY_DELAY, max_delay=MAX_RETRY_DELAY)
@circuit_breaker(failure_threshold=5, reset_timeout=60.0)
@handle_drive_operations("upload_file_to_drive", "file_ops") if HAS_ENHANCED_LOGGING else lambda f: f
def upload_file_to_drive(drive_service: Any, file_path: str, folder_id: str, overwrite: bool = True) -> Optional[str]:
    """Uploads a file to Google Drive in the specified folder with enhanced logging.

    Args:
        drive_service: The Google Drive service instance.
        file_path: Path to the file to upload.
        folder_id: ID of the folder to upload to.
        overwrite: If True, overwrites existing file with the same name. If False, keeps both files.

    Returns:
        The webViewLink (shareable link) of the uploaded file, or None if upload failed.

    Raises:
        Exception: If the API call fails after retries.
    """
    # Validate parameters
    if not _validate_upload_parameters(drive_service, file_path, folder_id):
        return None

    file_name = os.path.basename(file_path)
    file_size = os.path.getsize(file_path)

    logger.info(f"Preparing to upload file '{file_name}' ({file_size} bytes) to folder '{folder_id}'")

    # Handle existing file based on overwrite setting
    _handle_existing_file(drive_service, file_name, folder_id, overwrite)

    # Perform the upload
    return _perform_resumable_upload(drive_service, file_path, file_name, folder_id)


@retry(max_retries=MAX_RETRIES, initial_delay=INITIAL_RETRY_DELAY, max_delay=MAX_RETRY_DELAY)
def get_folder_id_by_path(drive_service: Any, folder_path: str) -> Optional[str]:
    """Gets the ID of a folder given its full path.

    Args:
        drive_service: The Google Drive service instance.
        folder_path: Path of folders, separated by '/'.

    Returns:
        The ID of the folder at the end of the path, or None if the folder path does not exist.

    Raises:
        Exception: If the API call fails after retries.
    """
    if not drive_service:
        logger.error("Cannot get folder ID: drive_service is None")
        return None

    parent_folder_id = "root"  # Start at the root of Drive
    folders = folder_path.strip("/").split("/")

    # Skip empty folder names
    folders = [f for f in folders if f]
    if not folders:
        return parent_folder_id

    current_folder_id = parent_folder_id

    try:
        logger.debug(f"Looking up folder path: {folder_path}")
        for folder_name in folders:
            folder_id = find_folder_id(drive_service, folder_name, current_folder_id)
            if folder_id:
                current_folder_id = folder_id
                logger.debug(f"Found folder '{folder_name}' with ID: {folder_id}")
            else:
                logger.info(f"Folder '{folder_name}' not found in path '{folder_path}'")
                return None  # Folder path not found

        logger.info(f"Found folder path '{folder_path}' with ID: {current_folder_id}")
        return current_folder_id  # Return the ID of the final folder in the path
    except Exception as e:
        logger.exception(f"Error getting folder ID for path '{folder_path}': {e}")
        raise


@retry(max_retries=MAX_RETRIES, initial_delay=INITIAL_RETRY_DELAY, max_delay=MAX_RETRY_DELAY)
@rate_limit(calls_per_second=API_CALLS_PER_SECOND, max_burst=MAX_BURST)
def delete_folder_by_id(drive_service: Any, folder_id: str) -> bool:
    """Deletes a folder in Google Drive by its folder ID.

    Args:
        drive_service: The Google Drive service instance.
        folder_id: ID of the folder to delete.

    Returns:
        True if deletion was successful, False otherwise.

    Raises:
        Exception: If the API call fails after retries.
    """
    if not drive_service:
        logger.error("Cannot delete folder: drive_service is None")
        return False

    if not folder_id:
        logger.error("Cannot delete folder: folder_id is empty")
        return False

    # Don't allow deleting the root folder
    if folder_id == "root":
        logger.error("Cannot delete the root folder")
        return False

    try:
        logger.debug(f"Deleting folder with ID: {folder_id}")
        drive_service.files().delete(fileId=folder_id).execute()
        logger.info(f"Successfully deleted folder with ID: {folder_id}")
        return True  # Deletion successful
    except HttpError as error:
        # If the folder doesn't exist (404), consider it a success
        if error.resp.status == 404:
            logger.warning(f"Folder with ID {folder_id} not found (already deleted)")
            return True

        error_details = detailed_error_response(error)
        logger.error(f"Google Drive API error while deleting folder: {error_details}")

        # For permission errors, don't retry
        if error.resp.status == 403:
            logger.error(f"Permission denied when deleting folder with ID: {folder_id}")
            return False

        raise
    except Exception as e:
        logger.exception(f"Unexpected error while deleting folder with ID {folder_id}: {e}")
        raise


@retry(max_retries=MAX_RETRIES, initial_delay=INITIAL_RETRY_DELAY, max_delay=MAX_RETRY_DELAY)
@handle_drive_operations("delete_folder_by_path", "folder_ops") if HAS_ENHANCED_LOGGING else lambda f: f
def delete_folder_by_path(drive_service: Any, folder_path: str) -> bool:
    """Deletes a folder in Google Drive given its full path with enhanced logging.

    Args:
        drive_service: The Google Drive service instance.
        folder_path: Path of the folder to delete, separated by '/'.

    Returns:
        True if deletion was successful, False otherwise.

    Raises:
        Exception: If the API call fails after retries.
    """
    if not drive_service:
        logger.error("Cannot delete folder: drive_service is None")
        return False

    if not folder_path:
        logger.error("Cannot delete folder: folder_path is empty")
        return False

    try:
        logger.info(f"Attempting to delete folder at path: {folder_path}")
        folder_id = get_folder_id_by_path(drive_service, folder_path)
        if folder_id:
            logger.debug(f"Found folder at path '{folder_path}' with ID: {folder_id}")
            result = delete_folder_by_id(drive_service, folder_id)  # Delete by ID if found
            if result:
                logger.info(f"Successfully deleted folder at path: {folder_path}")
            return result
        else:
            logger.warning(f"Folder path '{folder_path}' not found, cannot delete.")
            return False  # Folder path not found, cannot delete
    except Exception as e:
        logger.exception(f"Error deleting folder at path '{folder_path}': {e}")
        raise
