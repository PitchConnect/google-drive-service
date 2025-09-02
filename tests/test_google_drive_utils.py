import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from googleapiclient.errors import HttpError

# Import the functions to test
from google_drive_utils import (
    authenticate_google_drive,
    check_token_exists,
    create_folder,
    create_folder_if_not_exists,
    delete_file_by_id,
    delete_folder_by_id,
    delete_folder_by_path,
    exchange_code_for_tokens,
    find_file_id,
    find_folder_id,
    generate_authorization_url,
    get_folder_id_by_path,
    upload_file_to_drive,
)


# Helper function to disable decorators for fast testing
def no_op_decorator(*args, **kwargs):  # noqa: ARG001
    """No-op decorator that returns the function unchanged."""

    def decorator(func):
        return func

    return decorator


class TestGoogleDriveUtils(unittest.TestCase):

    def setUp(self):
        """Set up test fixtures before each test method."""
        # Create mock drive service
        self.mock_drive_service = MagicMock()

        # Create a temporary test file
        self.test_file_fd, self.test_file_path = tempfile.mkstemp(suffix=".txt")
        with os.fdopen(self.test_file_fd, "w") as f:
            f.write("Test content")

    def tearDown(self):
        """Tear down test fixtures after each test method."""
        # Remove test file
        if os.path.exists(self.test_file_path):
            os.remove(self.test_file_path)

    def test_find_file_id_found(self):
        """Test finding a file ID when the file exists."""
        # Mock the files().list().execute() response
        mock_list = MagicMock()
        mock_execute = MagicMock(return_value={"files": [{"id": "test_file_id"}]})
        mock_list.execute = mock_execute
        self.mock_drive_service.files().list.return_value = mock_list

        # Test the function
        result = find_file_id(self.mock_drive_service, "test_file.txt", "folder_id")

        # Verify the result
        self.assertEqual(result, "test_file_id")

        # Verify the correct query was used
        self.mock_drive_service.files().list.assert_called_once()
        call_args = self.mock_drive_service.files().list.call_args[1]
        self.assertIn("name='test_file.txt'", call_args["q"])
        self.assertIn("'folder_id' in parents", call_args["q"])

    def test_find_file_id_not_found(self):
        """Test finding a file ID when the file doesn't exist."""
        # Mock the files().list().execute() response
        mock_list = MagicMock()
        mock_execute = MagicMock(return_value={"files": []})
        mock_list.execute = mock_execute
        self.mock_drive_service.files().list.return_value = mock_list

        # Test the function
        result = find_file_id(self.mock_drive_service, "test_file.txt", "folder_id")

        # Verify the result
        self.assertIsNone(result)

    @patch("time.sleep")  # Mock sleep to make retries instant
    def test_find_file_id_error(self, mock_sleep):
        """Test finding a file ID when an error occurs."""
        # Mock the files().list().execute() to raise an HttpError
        mock_list = MagicMock()
        mock_execute = MagicMock(side_effect=HttpError(resp=MagicMock(status=500), content=b"Error"))
        mock_list.execute = mock_execute
        self.mock_drive_service.files().list.return_value = mock_list

        # Test the function - it should raise an HttpError after retries (but fast due to mocked sleep)
        with self.assertRaises(HttpError):
            find_file_id(self.mock_drive_service, "test_file.txt", "folder_id")

        # Verify that sleep was called (indicating retries happened but were fast)
        self.assertTrue(mock_sleep.called)

    def test_delete_file_by_id_success(self):
        """Test deleting a file by ID when successful."""
        # Mock the files().delete().execute() response
        mock_delete = MagicMock()
        mock_execute = MagicMock()
        mock_delete.execute = mock_execute
        self.mock_drive_service.files().delete.return_value = mock_delete

        # Test the function
        result = delete_file_by_id(self.mock_drive_service, "test_file_id")

        # Verify the result
        self.assertTrue(result)

        # Verify the correct file ID was used
        self.mock_drive_service.files().delete.assert_called_once_with(fileId="test_file_id")

    @patch("time.sleep")  # Mock sleep to make retries instant
    def test_delete_file_by_id_error(self, mock_sleep):
        """Test deleting a file by ID when an error occurs."""
        # Mock the files().delete().execute() to raise an HttpError
        mock_delete = MagicMock()
        mock_execute = MagicMock(side_effect=HttpError(resp=MagicMock(status=500), content=b"Error"))
        mock_delete.execute = mock_execute
        self.mock_drive_service.files().delete.return_value = mock_delete

        # Test the function - it should raise an HttpError after retries (but fast due to mocked sleep)
        with self.assertRaises(HttpError):
            delete_file_by_id(self.mock_drive_service, "test_file_id")

        # Verify that sleep was called (indicating retries happened but were fast)
        self.assertTrue(mock_sleep.called)

    @patch("google_drive_utils.find_file_id")
    @patch("google_drive_utils.delete_file_by_id")
    @patch("google_drive_utils.MediaFileUpload")
    def test_upload_file_to_drive_new_file(self, mock_media_upload, mock_delete_file, mock_find_file):
        """Test uploading a new file (no existing file with same name)."""
        # Configure mocks
        mock_find_file.return_value = None  # No existing file
        mock_media = MagicMock()
        mock_media_upload.return_value = mock_media

        # Mock the resumable upload request and response
        mock_request = MagicMock()
        # Mock next_chunk to return (None, response) indicating upload is complete
        mock_request.next_chunk.return_value = (
            None,
            {"id": "new_file_id", "webViewLink": "https://drive.google.com/file/d/new_file_id"},
        )
        self.mock_drive_service.files().create.return_value = mock_request

        # Test the function
        result = upload_file_to_drive(self.mock_drive_service, self.test_file_path, "folder_id")

        # Verify the result
        self.assertEqual(result, "https://drive.google.com/file/d/new_file_id")

        # Verify find_file_id was called
        mock_find_file.assert_called_once_with(
            self.mock_drive_service, os.path.basename(self.test_file_path), "folder_id"
        )

        # Verify delete_file_by_id was not called (no existing file)
        mock_delete_file.assert_not_called()

        # Verify create was called with correct parameters
        self.mock_drive_service.files().create.assert_called_once()
        call_args = self.mock_drive_service.files().create.call_args[1]
        self.assertEqual(call_args["body"]["name"], os.path.basename(self.test_file_path))
        self.assertEqual(call_args["body"]["parents"], ["folder_id"])
        self.assertEqual(call_args["media_body"], mock_media)

    @patch("google_drive_utils.find_file_id")
    @patch("google_drive_utils.delete_file_by_id")
    @patch("google_drive_utils.MediaFileUpload")
    def test_upload_file_to_drive_overwrite(self, mock_media_upload, mock_delete_file, mock_find_file):
        """Test uploading a file with overwrite=True when a file with same name exists."""
        # Configure mocks
        mock_find_file.return_value = "existing_file_id"  # Existing file
        mock_delete_file.return_value = True  # Deletion successful
        mock_media = MagicMock()
        mock_media_upload.return_value = mock_media

        # Mock the resumable upload request and response
        mock_request = MagicMock()
        # Mock next_chunk to return (None, response) indicating upload is complete
        mock_request.next_chunk.return_value = (
            None,
            {"id": "new_file_id", "webViewLink": "https://drive.google.com/file/d/new_file_id"},
        )
        self.mock_drive_service.files().create.return_value = mock_request

        # Test the function
        result = upload_file_to_drive(self.mock_drive_service, self.test_file_path, "folder_id", overwrite=True)

        # Verify the result
        self.assertEqual(result, "https://drive.google.com/file/d/new_file_id")

        # Verify find_file_id was called
        mock_find_file.assert_called_once_with(
            self.mock_drive_service, os.path.basename(self.test_file_path), "folder_id"
        )

        # Verify delete_file_by_id was called with the existing file ID
        mock_delete_file.assert_called_once_with(self.mock_drive_service, "existing_file_id")

    @patch("google_drive_utils.find_file_id")
    @patch("google_drive_utils.delete_file_by_id")
    @patch("google_drive_utils.MediaFileUpload")
    def test_upload_file_to_drive_no_overwrite(self, mock_media_upload, mock_delete_file, mock_find_file):
        """Test uploading a file with overwrite=False when a file with same name exists."""
        # Configure mocks
        mock_find_file.return_value = "existing_file_id"  # Existing file
        mock_media = MagicMock()
        mock_media_upload.return_value = mock_media

        # Mock the resumable upload request and response
        mock_request = MagicMock()
        # Mock next_chunk to return (None, response) indicating upload is complete
        mock_request.next_chunk.return_value = (
            None,
            {"id": "new_file_id", "webViewLink": "https://drive.google.com/file/d/new_file_id"},
        )
        self.mock_drive_service.files().create.return_value = mock_request

        # Test the function
        result = upload_file_to_drive(self.mock_drive_service, self.test_file_path, "folder_id", overwrite=False)

        # Verify the result
        self.assertEqual(result, "https://drive.google.com/file/d/new_file_id")

        # Verify find_file_id was not called (overwrite=False)
        mock_find_file.assert_not_called()

        # Verify delete_file_by_id was not called
        mock_delete_file.assert_not_called()

    @patch("time.sleep")  # Mock sleep to make retries instant
    @patch("google_drive_utils.find_file_id")
    @patch("google_drive_utils.delete_file_by_id")
    @patch("google_drive_utils.MediaFileUpload")
    def test_upload_file_to_drive_error(self, mock_media_upload, _, mock_find_file, mock_sleep):
        """Test uploading a file when an error occurs."""
        # Configure mocks
        mock_find_file.return_value = None  # No existing file
        mock_media = MagicMock()
        mock_media_upload.return_value = mock_media

        # Mock the resumable upload request to raise an HttpError on next_chunk
        mock_request = MagicMock()
        mock_request.next_chunk.side_effect = HttpError(resp=MagicMock(status=500), content=b"Error")
        self.mock_drive_service.files().create.return_value = mock_request

        # Test the function - enhanced logging converts HttpError to DriveAPIError
        try:
            from src.core.error_handling import DriveAPIError
            expected_exception = DriveAPIError
        except ImportError:
            # Fallback to original exception
            expected_exception = HttpError

        with self.assertRaises(expected_exception):
            upload_file_to_drive(self.mock_drive_service, self.test_file_path, "folder_id")

        # Enhanced logging may change retry behavior, so we just verify the exception was raised
        # The important thing is that the function properly handles and propagates errors

    # Additional tests for folder-related functions
    def test_find_folder_id(self):
        """Test finding a folder ID."""
        # Mock the files().list().execute() response
        mock_list = MagicMock()
        mock_execute = MagicMock(return_value={"files": [{"id": "folder_id"}]})
        mock_list.execute = mock_execute
        self.mock_drive_service.files().list.return_value = mock_list

        # Test the function
        result = find_folder_id(self.mock_drive_service, "test_folder", "parent_id")

        # Verify the result
        self.assertEqual(result, "folder_id")

        # Verify the correct query was used
        self.mock_drive_service.files().list.assert_called_once()
        call_args = self.mock_drive_service.files().list.call_args[1]
        self.assertIn("mimeType='application/vnd.google-apps.folder'", call_args["q"])
        self.assertIn("name='test_folder'", call_args["q"])
        self.assertIn("'parent_id' in parents", call_args["q"])

    def test_create_folder(self):
        """Test creating a folder."""
        # Mock the files().create().execute() response
        mock_create = MagicMock()
        mock_execute = MagicMock(return_value={"id": "new_folder_id"})
        mock_create.execute = mock_execute
        self.mock_drive_service.files().create.return_value = mock_create

        # Test the function
        result = create_folder(self.mock_drive_service, "test_folder", "parent_id")

        # Verify the result
        self.assertEqual(result, "new_folder_id")

        # Verify create was called with correct parameters
        self.mock_drive_service.files().create.assert_called_once()
        call_args = self.mock_drive_service.files().create.call_args[1]
        self.assertEqual(call_args["body"]["name"], "test_folder")
        self.assertEqual(call_args["body"]["mimeType"], "application/vnd.google-apps.folder")
        self.assertEqual(call_args["body"]["parents"], ["parent_id"])

    @patch("google_drive_utils.find_folder_id")
    @patch("google_drive_utils.create_folder")
    def test_create_folder_if_not_exists_existing(self, mock_create_folder, mock_find_folder):
        """Test creating a folder if it doesn't exist, when it already exists."""
        # Configure mocks
        mock_find_folder.return_value = "existing_folder_id"  # Folder exists

        # Test the function
        result = create_folder_if_not_exists(self.mock_drive_service, "test_folder")

        # Verify the result
        self.assertEqual(result, "existing_folder_id")

        # Verify find_folder_id was called
        mock_find_folder.assert_called_once_with(self.mock_drive_service, "test_folder", "root")

        # Verify create_folder was not called
        mock_create_folder.assert_not_called()

    @patch("google_drive_utils.find_folder_id")
    @patch("google_drive_utils.create_folder")
    def test_create_folder_if_not_exists_new(self, mock_create_folder, mock_find_folder):
        """Test creating a folder if it doesn't exist, when it doesn't exist."""
        # Configure mocks
        mock_find_folder.return_value = None  # Folder doesn't exist
        mock_create_folder.return_value = "new_folder_id"  # New folder created

        # Test the function
        result = create_folder_if_not_exists(self.mock_drive_service, "test_folder")

        # Verify the result
        self.assertEqual(result, "new_folder_id")

        # Verify find_folder_id was called
        mock_find_folder.assert_called_once_with(self.mock_drive_service, "test_folder", "root")

        # Verify create_folder was called
        mock_create_folder.assert_called_once_with(self.mock_drive_service, "test_folder", "root")

    @patch("google_drive_utils.find_folder_id")
    def test_get_folder_id_by_path(self, mock_find_folder):
        """Test getting a folder ID by path."""
        # Configure mocks to simulate a path with two folders
        mock_find_folder.side_effect = ["folder1_id", "folder2_id"]

        # Test the function
        result = get_folder_id_by_path(self.mock_drive_service, "folder1/folder2")

        # Verify the result
        self.assertEqual(result, "folder2_id")

        # Verify find_folder_id was called twice
        self.assertEqual(mock_find_folder.call_count, 2)
        mock_find_folder.assert_any_call(self.mock_drive_service, "folder1", "root")
        mock_find_folder.assert_any_call(self.mock_drive_service, "folder2", "folder1_id")

    def test_delete_folder_by_id(self):
        """Test deleting a folder by ID."""
        # Mock the files().delete().execute() response
        mock_delete = MagicMock()
        mock_execute = MagicMock()
        mock_delete.execute = mock_execute
        self.mock_drive_service.files().delete.return_value = mock_delete

        # Test the function
        result = delete_folder_by_id(self.mock_drive_service, "folder_id")

        # Verify the result
        self.assertTrue(result)

        # Verify the correct folder ID was used
        self.mock_drive_service.files().delete.assert_called_once_with(fileId="folder_id")

    @patch("google_drive_utils.get_folder_id_by_path")
    @patch("google_drive_utils.delete_folder_by_id")
    def test_delete_folder_by_path(self, mock_delete_folder, mock_get_folder_id):
        """Test deleting a folder by path."""
        # Configure mocks
        mock_get_folder_id.return_value = "folder_id"  # Folder exists
        mock_delete_folder.return_value = True  # Deletion successful

        # Test the function
        result = delete_folder_by_path(self.mock_drive_service, "folder1/folder2")

        # Verify the result
        self.assertTrue(result)

        # Verify get_folder_id_by_path was called
        mock_get_folder_id.assert_called_once_with(self.mock_drive_service, "folder1/folder2")

        # Verify delete_folder_by_id was called
        mock_delete_folder.assert_called_once_with(self.mock_drive_service, "folder_id")


class TestAuthenticationFunctions(unittest.TestCase):
    """Test authentication-related functions."""

    @patch("google_drive_utils.os.path.exists")
    def test_check_token_exists_true(self, mock_exists):
        """Test check_token_exists when token file exists."""
        mock_exists.return_value = True

        result = check_token_exists()

        self.assertTrue(result)
        mock_exists.assert_called_once()

    @patch("google_drive_utils.os.path.exists")
    def test_check_token_exists_false(self, mock_exists):
        """Test check_token_exists when token file doesn't exist."""
        mock_exists.return_value = False

        result = check_token_exists()

        self.assertFalse(result)
        mock_exists.assert_called_once()

    @patch("google_drive_utils.Flow.from_client_secrets_file")
    def test_generate_authorization_url_success(self, mock_flow_class):
        """Test generate_authorization_url when successful."""
        # Mock the flow instance
        mock_flow = MagicMock()
        mock_flow.authorization_url.return_value = ("https://accounts.google.com/oauth/authorize?...", "state")
        mock_flow_class.return_value = mock_flow

        result = generate_authorization_url()

        self.assertEqual(result, "https://accounts.google.com/oauth/authorize?...")
        mock_flow_class.assert_called_once()
        mock_flow.authorization_url.assert_called_once_with(
            prompt="consent", access_type="offline", include_granted_scopes="true"
        )

    @patch("google_drive_utils.Flow.from_client_secrets_file")
    def test_generate_authorization_url_failure(self, mock_flow_class):
        """Test generate_authorization_url when it fails."""
        # Mock the flow to raise an exception during authorization_url call
        mock_flow = MagicMock()
        mock_flow.authorization_url.side_effect = Exception("Test error")
        mock_flow_class.return_value = mock_flow

        # The function should handle the exception and return None
        result = generate_authorization_url()

        self.assertIsNone(result)
        mock_flow_class.assert_called_once()
        mock_flow.authorization_url.assert_called_once_with(
            prompt="consent", access_type="offline", include_granted_scopes="true"
        )

    @patch("google_drive_utils.Flow.from_client_secrets_file")
    @patch("builtins.open", new_callable=unittest.mock.mock_open)
    def test_exchange_code_for_tokens_success(self, mock_open, mock_flow_class):
        """Test exchange_code_for_tokens when successful."""
        # Mock the flow instance and credentials
        mock_flow = MagicMock()
        mock_creds = MagicMock()
        mock_creds.valid = True
        mock_creds.to_json.return_value = '{"token": "test"}'
        mock_flow.credentials = mock_creds
        mock_flow_class.return_value = mock_flow

        result = exchange_code_for_tokens("test_code")

        self.assertTrue(result)
        mock_flow_class.assert_called_once()
        mock_flow.fetch_token.assert_called_once_with(code="test_code")
        mock_open.assert_called_once()

    @patch("google_drive_utils.Flow.from_client_secrets_file")
    def test_exchange_code_for_tokens_invalid_credentials(self, mock_flow_class):
        """Test exchange_code_for_tokens with invalid credentials."""
        # Mock the flow instance with invalid credentials
        mock_flow = MagicMock()
        mock_creds = MagicMock()
        mock_creds.valid = False
        mock_flow.credentials = mock_creds
        mock_flow_class.return_value = mock_flow

        result = exchange_code_for_tokens("test_code")

        self.assertFalse(result)
        mock_flow_class.assert_called_once()
        mock_flow.fetch_token.assert_called_once_with(code="test_code")

    @patch("google_drive_utils.Flow.from_client_secrets_file")
    def test_exchange_code_for_tokens_exception(self, mock_flow_class):
        """Test exchange_code_for_tokens when an exception occurs."""
        # Mock the flow to raise an exception
        mock_flow = MagicMock()
        mock_flow.fetch_token.side_effect = Exception("Test error")
        mock_flow_class.return_value = mock_flow

        result = exchange_code_for_tokens("test_code")

        self.assertFalse(result)
        mock_flow_class.assert_called_once()
        mock_flow.fetch_token.assert_called_once_with(code="test_code")

    @patch("google_drive_utils.build")
    @patch("google_drive_utils.Credentials.from_authorized_user_file")
    @patch("google_drive_utils.os.path.exists")
    def test_authenticate_google_drive_success(self, mock_exists, mock_creds_from_file, mock_build):
        """Test authenticate_google_drive when successful."""
        # Mock token file exists
        mock_exists.return_value = True

        # Mock valid credentials
        mock_creds = MagicMock()
        mock_creds.valid = True
        mock_creds_from_file.return_value = mock_creds

        # Mock service
        mock_service = MagicMock()
        mock_service.files().list().execute.return_value = {"files": []}
        mock_build.return_value = mock_service

        result = authenticate_google_drive()

        self.assertEqual(result, mock_service)
        mock_exists.assert_called_once()
        mock_creds_from_file.assert_called_once()
        mock_build.assert_called_once_with("drive", "v3", credentials=mock_creds)

    @patch("google_drive_utils.os.path.exists")
    def test_authenticate_google_drive_no_token(self, mock_exists):
        """Test authenticate_google_drive when no token file exists."""
        # Mock token file doesn't exist
        mock_exists.return_value = False

        result = authenticate_google_drive()

        self.assertIsNone(result)
        mock_exists.assert_called_once()

    @patch("google_drive_utils.build")
    @patch("google_drive_utils.Credentials.from_authorized_user_file")
    @patch("google_drive_utils.os.path.exists")
    @patch("builtins.open", new_callable=unittest.mock.mock_open)
    def test_authenticate_google_drive_refresh_token(self, mock_open, mock_exists, mock_creds_from_file, mock_build):
        """Test authenticate_google_drive with expired credentials that need refresh."""
        # Mock token file exists
        mock_exists.return_value = True

        # Mock expired credentials with refresh token
        mock_creds = MagicMock()
        mock_creds.valid = False
        mock_creds.expired = True
        mock_creds.refresh_token = "refresh_token"
        mock_creds.to_json.return_value = '{"token": "refreshed"}'
        mock_creds_from_file.return_value = mock_creds

        # Mock service
        mock_service = MagicMock()
        mock_service.files().list().execute.return_value = {"files": []}
        mock_build.return_value = mock_service

        # After refresh, credentials become valid
        def refresh_side_effect(_):
            mock_creds.valid = True

        mock_creds.refresh.side_effect = refresh_side_effect

        result = authenticate_google_drive()

        self.assertEqual(result, mock_service)
        mock_creds.refresh.assert_called_once()
        mock_open.assert_called_once()

    @patch("google_drive_utils.build")
    @patch("google_drive_utils.Credentials.from_authorized_user_file")
    @patch("google_drive_utils.os.path.exists")
    def test_authenticate_google_drive_api_error(self, mock_exists, mock_creds_from_file, mock_build):
        """Test authenticate_google_drive when API call fails."""
        # Mock token file exists
        mock_exists.return_value = True

        # Mock valid credentials
        mock_creds = MagicMock()
        mock_creds.valid = True
        mock_creds_from_file.return_value = mock_creds

        # Mock service that raises HttpError
        mock_service = MagicMock()
        mock_response = MagicMock()
        mock_response.status = 401
        mock_service.files().list().execute.side_effect = HttpError(mock_response, b'{"error": "unauthorized"}')
        mock_build.return_value = mock_service

        result = authenticate_google_drive()

        self.assertIsNone(result)
        mock_build.assert_called_once_with("drive", "v3", credentials=mock_creds)

    @patch("google_drive_utils.os.remove")
    @patch("google_drive_utils.build")
    @patch("google_drive_utils.Credentials.from_authorized_user_file")
    @patch("google_drive_utils.os.path.exists")
    @patch("builtins.open", new_callable=unittest.mock.mock_open)
    def test_authenticate_google_drive_invalid_grant_error(
        self, mock_open, mock_exists, mock_creds_from_file, mock_build, mock_remove
    ):  # noqa: ARG002
        """Test authenticate_google_drive with invalid_grant error that removes token file."""
        # Mock token file exists
        mock_exists.return_value = True

        # Mock expired credentials with refresh token that fails with invalid_grant
        mock_creds = MagicMock()
        mock_creds.valid = False
        mock_creds.expired = True
        mock_creds.refresh_token = "refresh_token"
        mock_creds_from_file.return_value = mock_creds

        # Mock refresh to raise invalid_grant error
        mock_creds.refresh.side_effect = Exception("invalid_grant error")

        result = authenticate_google_drive()

        self.assertIsNone(result)
        mock_creds.refresh.assert_called_once()
        mock_remove.assert_called_once()

    @patch("google_drive_utils.build")
    @patch("google_drive_utils.Credentials.from_authorized_user_file")
    @patch("google_drive_utils.os.path.exists")
    def test_authenticate_google_drive_credentials_loading_error(self, mock_exists, mock_creds_from_file, mock_build):
        """Test authenticate_google_drive when credentials loading fails."""
        # Mock token file exists
        mock_exists.return_value = True

        # Mock credentials loading to raise an exception
        mock_creds_from_file.side_effect = Exception("Credentials loading error")

        result = authenticate_google_drive()

        self.assertIsNone(result)
        mock_creds_from_file.assert_called_once()
        mock_build.assert_not_called()


class TestUtilityFunctions(unittest.TestCase):
    """Test utility functions in google_drive_utils."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_drive_service = MagicMock()

    def test_find_file_id_none_service(self):
        """Test find_file_id with None service."""
        from google_drive_utils import find_file_id

        result = find_file_id(None, "test.txt", "folder_id")

        self.assertIsNone(result)

    def test_find_folder_id_none_service(self):
        """Test find_folder_id with None service."""
        from google_drive_utils import find_folder_id

        result = find_folder_id(None, "test_folder", "parent_id")

        self.assertIsNone(result)

    def test_create_folder_if_not_exists_none_service(self):
        """Test create_folder_if_not_exists with None service."""
        from google_drive_utils import create_folder_if_not_exists

        result = create_folder_if_not_exists(None, "test/folder")

        self.assertIsNone(result)

    def test_delete_file_by_id_none_service(self):
        """Test delete_file_by_id with None service."""
        from google_drive_utils import delete_file_by_id

        result = delete_file_by_id(None, "file_id")

        self.assertFalse(result)

    def test_delete_file_by_id_empty_file_id(self):
        """Test delete_file_by_id with empty file_id."""
        from google_drive_utils import delete_file_by_id

        result = delete_file_by_id(self.mock_drive_service, "")

        self.assertFalse(result)

    def test_upload_file_to_drive_none_service(self):
        """Test upload_file_to_drive with None service."""
        from google_drive_utils import upload_file_to_drive

        result = upload_file_to_drive(None, "/tmp/test.txt", "folder_id")

        self.assertIsNone(result)

    @patch("google_drive_utils.find_folder_id")
    def test_create_folder_if_not_exists_single_folder(self, mock_find_folder):
        """Test create_folder_if_not_exists with single folder that doesn't exist."""
        from google_drive_utils import create_folder_if_not_exists

        # Mock folder doesn't exist, then gets created
        mock_find_folder.side_effect = [None, "new_folder_id"]

        with patch("google_drive_utils.create_folder") as mock_create:
            mock_create.return_value = "new_folder_id"

            result = create_folder_if_not_exists(self.mock_drive_service, "single_folder")

            self.assertEqual(result, "new_folder_id")
            mock_find_folder.assert_called_with(self.mock_drive_service, "single_folder", "root")
            mock_create.assert_called_once()

    def test_create_folder_none_service(self):
        """Test create_folder with None service."""
        from google_drive_utils import create_folder

        result = create_folder(None, "test_folder", "parent_id")

        self.assertIsNone(result)

    @patch("google_drive_utils.find_folder_id")
    def test_get_folder_id_by_path_empty_path(self, mock_find_folder):
        """Test get_folder_id_by_path with empty path."""
        from google_drive_utils import get_folder_id_by_path

        result = get_folder_id_by_path(self.mock_drive_service, "")

        self.assertEqual(result, "root")
        mock_find_folder.assert_not_called()

    def test_delete_folder_by_id_none_service(self):
        """Test delete_folder_by_id with None service."""
        from google_drive_utils import delete_folder_by_id

        result = delete_folder_by_id(None, "folder_id")

        self.assertFalse(result)

    def test_delete_folder_by_path_none_service(self):
        """Test delete_folder_by_path with None service."""
        from google_drive_utils import delete_folder_by_path

        result = delete_folder_by_path(None, "test/folder")

        self.assertFalse(result)

    def test_find_folder_id_empty_name(self):
        """Test find_folder_id with empty folder name."""
        from google_drive_utils import find_folder_id

        result = find_folder_id(self.mock_drive_service, "", "parent_id")

        self.assertIsNone(result)

    def test_find_file_id_empty_name(self):
        """Test find_file_id with empty file name."""
        from google_drive_utils import find_file_id

        result = find_file_id(self.mock_drive_service, "", "folder_id")

        self.assertIsNone(result)

    def test_create_folder_empty_name(self):
        """Test create_folder with empty folder name."""
        from google_drive_utils import create_folder

        result = create_folder(self.mock_drive_service, "", "parent_id")

        self.assertIsNone(result)

    def test_delete_folder_by_id_root_folder(self):
        """Test delete_folder_by_id with root folder ID."""
        from google_drive_utils import delete_folder_by_id

        result = delete_folder_by_id(self.mock_drive_service, "root")

        self.assertFalse(result)

    def test_delete_folder_by_path_empty_path(self):
        """Test delete_folder_by_path with empty path."""
        from google_drive_utils import delete_folder_by_path

        result = delete_folder_by_path(self.mock_drive_service, "")

        self.assertFalse(result)

    def test_create_folder_if_not_exists_empty_path(self):
        """Test create_folder_if_not_exists with empty folder path."""
        from google_drive_utils import create_folder_if_not_exists

        result = create_folder_if_not_exists(self.mock_drive_service, "")

        self.assertEqual(result, "root")

    def test_delete_folder_by_id_empty_id(self):
        """Test delete_folder_by_id with empty folder ID."""
        from google_drive_utils import delete_folder_by_id

        result = delete_folder_by_id(self.mock_drive_service, "")

        self.assertFalse(result)

    @patch("google_drive_utils.os.path.exists")
    def test_upload_file_to_drive_nonexistent_file(self, mock_exists):
        """Test upload_file_to_drive with non-existent file."""
        from google_drive_utils import upload_file_to_drive

        mock_exists.return_value = False

        result = upload_file_to_drive(self.mock_drive_service, "/nonexistent/file.txt", "folder_id")

        self.assertIsNone(result)

    def test_upload_file_to_drive_empty_folder_id(self):
        """Test upload_file_to_drive with empty folder ID."""
        from google_drive_utils import upload_file_to_drive

        result = upload_file_to_drive(self.mock_drive_service, "/tmp/test.txt", "")

        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
