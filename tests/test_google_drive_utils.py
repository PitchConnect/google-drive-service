import unittest
from unittest.mock import MagicMock, patch
import os
import tempfile
from googleapiclient.errors import HttpError

# Import the functions to test
from google_drive_utils import (
    find_file_id, delete_file_by_id, upload_file_to_drive,
    find_folder_id, create_folder, create_folder_if_not_exists,
    get_folder_id_by_path, delete_folder_by_id, delete_folder_by_path
)


class TestGoogleDriveUtils(unittest.TestCase):
    
    def setUp(self):
        """Set up test fixtures before each test method."""
        # Create mock drive service
        self.mock_drive_service = MagicMock()
        
        # Create a temporary test file
        self.test_file_fd, self.test_file_path = tempfile.mkstemp(suffix='.txt')
        with os.fdopen(self.test_file_fd, 'w') as f:
            f.write('Test content')
    
    def tearDown(self):
        """Tear down test fixtures after each test method."""
        # Remove test file
        if os.path.exists(self.test_file_path):
            os.remove(self.test_file_path)
    
    def test_find_file_id_found(self):
        """Test finding a file ID when the file exists."""
        # Mock the files().list().execute() response
        mock_list = MagicMock()
        mock_execute = MagicMock(return_value={'files': [{'id': 'test_file_id'}]})
        mock_list.execute = mock_execute
        self.mock_drive_service.files().list.return_value = mock_list
        
        # Test the function
        result = find_file_id(self.mock_drive_service, 'test_file.txt', 'folder_id')
        
        # Verify the result
        self.assertEqual(result, 'test_file_id')
        
        # Verify the correct query was used
        self.mock_drive_service.files().list.assert_called_once()
        call_args = self.mock_drive_service.files().list.call_args[1]
        self.assertIn("name='test_file.txt'", call_args['q'])
        self.assertIn("'folder_id' in parents", call_args['q'])
        
    def test_find_file_id_not_found(self):
        """Test finding a file ID when the file doesn't exist."""
        # Mock the files().list().execute() response
        mock_list = MagicMock()
        mock_execute = MagicMock(return_value={'files': []})
        mock_list.execute = mock_execute
        self.mock_drive_service.files().list.return_value = mock_list
        
        # Test the function
        result = find_file_id(self.mock_drive_service, 'test_file.txt', 'folder_id')
        
        # Verify the result
        self.assertIsNone(result)
    
    def test_find_file_id_error(self):
        """Test finding a file ID when an error occurs."""
        # Mock the files().list().execute() to raise an HttpError
        mock_list = MagicMock()
        mock_execute = MagicMock(side_effect=HttpError(resp=MagicMock(status=500), content=b'Error'))
        mock_list.execute = mock_execute
        self.mock_drive_service.files().list.return_value = mock_list
        
        # Test the function
        result = find_file_id(self.mock_drive_service, 'test_file.txt', 'folder_id')
        
        # Verify the result
        self.assertIsNone(result)
    
    def test_delete_file_by_id_success(self):
        """Test deleting a file by ID when successful."""
        # Mock the files().delete().execute() response
        mock_delete = MagicMock()
        mock_execute = MagicMock()
        mock_delete.execute = mock_execute
        self.mock_drive_service.files().delete.return_value = mock_delete
        
        # Test the function
        result = delete_file_by_id(self.mock_drive_service, 'test_file_id')
        
        # Verify the result
        self.assertTrue(result)
        
        # Verify the correct file ID was used
        self.mock_drive_service.files().delete.assert_called_once_with(fileId='test_file_id')
    
    def test_delete_file_by_id_error(self):
        """Test deleting a file by ID when an error occurs."""
        # Mock the files().delete().execute() to raise an HttpError
        mock_delete = MagicMock()
        mock_execute = MagicMock(side_effect=HttpError(resp=MagicMock(status=500), content=b'Error'))
        mock_delete.execute = mock_execute
        self.mock_drive_service.files().delete.return_value = mock_delete
        
        # Test the function
        result = delete_file_by_id(self.mock_drive_service, 'test_file_id')
        
        # Verify the result
        self.assertFalse(result)
    
    @patch('google_drive_utils.find_file_id')
    @patch('google_drive_utils.delete_file_by_id')
    @patch('google_drive_utils.MediaFileUpload')
    def test_upload_file_to_drive_new_file(self, mock_media_upload, mock_delete_file, mock_find_file):
        """Test uploading a new file (no existing file with same name)."""
        # Configure mocks
        mock_find_file.return_value = None  # No existing file
        mock_media = MagicMock()
        mock_media_upload.return_value = mock_media
        
        # Mock the files().create().execute() response
        mock_create = MagicMock()
        mock_execute = MagicMock(return_value={'id': 'new_file_id', 'webViewLink': 'https://drive.google.com/file/d/new_file_id'})
        mock_create.execute = mock_execute
        self.mock_drive_service.files().create.return_value = mock_create
        
        # Test the function
        result = upload_file_to_drive(self.mock_drive_service, self.test_file_path, 'folder_id')
        
        # Verify the result
        self.assertEqual(result, 'https://drive.google.com/file/d/new_file_id')
        
        # Verify find_file_id was called
        mock_find_file.assert_called_once_with(self.mock_drive_service, os.path.basename(self.test_file_path), 'folder_id')
        
        # Verify delete_file_by_id was not called (no existing file)
        mock_delete_file.assert_not_called()
        
        # Verify create was called with correct parameters
        self.mock_drive_service.files().create.assert_called_once()
        call_args = self.mock_drive_service.files().create.call_args[1]
        self.assertEqual(call_args['body']['name'], os.path.basename(self.test_file_path))
        self.assertEqual(call_args['body']['parents'], ['folder_id'])
        self.assertEqual(call_args['media_body'], mock_media)
    
    @patch('google_drive_utils.find_file_id')
    @patch('google_drive_utils.delete_file_by_id')
    @patch('google_drive_utils.MediaFileUpload')
    def test_upload_file_to_drive_overwrite(self, mock_media_upload, mock_delete_file, mock_find_file):
        """Test uploading a file with overwrite=True when a file with same name exists."""
        # Configure mocks
        mock_find_file.return_value = 'existing_file_id'  # Existing file
        mock_delete_file.return_value = True  # Deletion successful
        mock_media = MagicMock()
        mock_media_upload.return_value = mock_media
        
        # Mock the files().create().execute() response
        mock_create = MagicMock()
        mock_execute = MagicMock(return_value={'id': 'new_file_id', 'webViewLink': 'https://drive.google.com/file/d/new_file_id'})
        mock_create.execute = mock_execute
        self.mock_drive_service.files().create.return_value = mock_create
        
        # Test the function
        result = upload_file_to_drive(self.mock_drive_service, self.test_file_path, 'folder_id', overwrite=True)
        
        # Verify the result
        self.assertEqual(result, 'https://drive.google.com/file/d/new_file_id')
        
        # Verify find_file_id was called
        mock_find_file.assert_called_once_with(self.mock_drive_service, os.path.basename(self.test_file_path), 'folder_id')
        
        # Verify delete_file_by_id was called with the existing file ID
        mock_delete_file.assert_called_once_with(self.mock_drive_service, 'existing_file_id')
    
    @patch('google_drive_utils.find_file_id')
    @patch('google_drive_utils.delete_file_by_id')
    @patch('google_drive_utils.MediaFileUpload')
    def test_upload_file_to_drive_no_overwrite(self, mock_media_upload, mock_delete_file, mock_find_file):
        """Test uploading a file with overwrite=False when a file with same name exists."""
        # Configure mocks
        mock_find_file.return_value = 'existing_file_id'  # Existing file
        mock_media = MagicMock()
        mock_media_upload.return_value = mock_media
        
        # Mock the files().create().execute() response
        mock_create = MagicMock()
        mock_execute = MagicMock(return_value={'id': 'new_file_id', 'webViewLink': 'https://drive.google.com/file/d/new_file_id'})
        mock_create.execute = mock_execute
        self.mock_drive_service.files().create.return_value = mock_create
        
        # Test the function
        result = upload_file_to_drive(self.mock_drive_service, self.test_file_path, 'folder_id', overwrite=False)
        
        # Verify the result
        self.assertEqual(result, 'https://drive.google.com/file/d/new_file_id')
        
        # Verify find_file_id was not called (overwrite=False)
        mock_find_file.assert_not_called()
        
        # Verify delete_file_by_id was not called
        mock_delete_file.assert_not_called()
    
    @patch('google_drive_utils.find_file_id')
    @patch('google_drive_utils.delete_file_by_id')
    @patch('google_drive_utils.MediaFileUpload')
    def test_upload_file_to_drive_error(self, mock_media_upload, mock_delete_file, mock_find_file):
        """Test uploading a file when an error occurs."""
        # Configure mocks
        mock_find_file.return_value = None  # No existing file
        mock_media = MagicMock()
        mock_media_upload.return_value = mock_media
        
        # Mock the files().create().execute() to raise an HttpError
        mock_create = MagicMock()
        mock_execute = MagicMock(side_effect=HttpError(resp=MagicMock(status=500), content=b'Error'))
        mock_create.execute = mock_execute
        self.mock_drive_service.files().create.return_value = mock_create
        
        # Test the function
        result = upload_file_to_drive(self.mock_drive_service, self.test_file_path, 'folder_id')
        
        # Verify the result
        self.assertIsNone(result)
    
    # Additional tests for folder-related functions
    def test_find_folder_id(self):
        """Test finding a folder ID."""
        # Mock the files().list().execute() response
        mock_list = MagicMock()
        mock_execute = MagicMock(return_value={'files': [{'id': 'folder_id'}]})
        mock_list.execute = mock_execute
        self.mock_drive_service.files().list.return_value = mock_list
        
        # Test the function
        result = find_folder_id(self.mock_drive_service, 'test_folder', 'parent_id')
        
        # Verify the result
        self.assertEqual(result, 'folder_id')
        
        # Verify the correct query was used
        self.mock_drive_service.files().list.assert_called_once()
        call_args = self.mock_drive_service.files().list.call_args[1]
        self.assertIn("mimeType='application/vnd.google-apps.folder'", call_args['q'])
        self.assertIn("name='test_folder'", call_args['q'])
        self.assertIn("'parent_id' in parents", call_args['q'])
    
    def test_create_folder(self):
        """Test creating a folder."""
        # Mock the files().create().execute() response
        mock_create = MagicMock()
        mock_execute = MagicMock(return_value={'id': 'new_folder_id'})
        mock_create.execute = mock_execute
        self.mock_drive_service.files().create.return_value = mock_create
        
        # Test the function
        result = create_folder(self.mock_drive_service, 'test_folder', 'parent_id')
        
        # Verify the result
        self.assertEqual(result, 'new_folder_id')
        
        # Verify create was called with correct parameters
        self.mock_drive_service.files().create.assert_called_once()
        call_args = self.mock_drive_service.files().create.call_args[1]
        self.assertEqual(call_args['body']['name'], 'test_folder')
        self.assertEqual(call_args['body']['mimeType'], 'application/vnd.google-apps.folder')
        self.assertEqual(call_args['body']['parents'], ['parent_id'])
    
    @patch('google_drive_utils.find_folder_id')
    @patch('google_drive_utils.create_folder')
    def test_create_folder_if_not_exists_existing(self, mock_create_folder, mock_find_folder):
        """Test creating a folder if it doesn't exist, when it already exists."""
        # Configure mocks
        mock_find_folder.return_value = 'existing_folder_id'  # Folder exists
        
        # Test the function
        result = create_folder_if_not_exists(self.mock_drive_service, 'test_folder')
        
        # Verify the result
        self.assertEqual(result, 'existing_folder_id')
        
        # Verify find_folder_id was called
        mock_find_folder.assert_called_once_with(self.mock_drive_service, 'test_folder', 'root')
        
        # Verify create_folder was not called
        mock_create_folder.assert_not_called()
    
    @patch('google_drive_utils.find_folder_id')
    @patch('google_drive_utils.create_folder')
    def test_create_folder_if_not_exists_new(self, mock_create_folder, mock_find_folder):
        """Test creating a folder if it doesn't exist, when it doesn't exist."""
        # Configure mocks
        mock_find_folder.return_value = None  # Folder doesn't exist
        mock_create_folder.return_value = 'new_folder_id'  # New folder created
        
        # Test the function
        result = create_folder_if_not_exists(self.mock_drive_service, 'test_folder')
        
        # Verify the result
        self.assertEqual(result, 'new_folder_id')
        
        # Verify find_folder_id was called
        mock_find_folder.assert_called_once_with(self.mock_drive_service, 'test_folder', 'root')
        
        # Verify create_folder was called
        mock_create_folder.assert_called_once_with(self.mock_drive_service, 'test_folder', 'root')
    
    @patch('google_drive_utils.find_folder_id')
    def test_get_folder_id_by_path(self, mock_find_folder):
        """Test getting a folder ID by path."""
        # Configure mocks to simulate a path with two folders
        mock_find_folder.side_effect = ['folder1_id', 'folder2_id']
        
        # Test the function
        result = get_folder_id_by_path(self.mock_drive_service, 'folder1/folder2')
        
        # Verify the result
        self.assertEqual(result, 'folder2_id')
        
        # Verify find_folder_id was called twice
        self.assertEqual(mock_find_folder.call_count, 2)
        mock_find_folder.assert_any_call(self.mock_drive_service, 'folder1', 'root')
        mock_find_folder.assert_any_call(self.mock_drive_service, 'folder2', 'folder1_id')
    
    def test_delete_folder_by_id(self):
        """Test deleting a folder by ID."""
        # Mock the files().delete().execute() response
        mock_delete = MagicMock()
        mock_execute = MagicMock()
        mock_delete.execute = mock_execute
        self.mock_drive_service.files().delete.return_value = mock_delete
        
        # Test the function
        result = delete_folder_by_id(self.mock_drive_service, 'folder_id')
        
        # Verify the result
        self.assertTrue(result)
        
        # Verify the correct folder ID was used
        self.mock_drive_service.files().delete.assert_called_once_with(fileId='folder_id')
    
    @patch('google_drive_utils.get_folder_id_by_path')
    @patch('google_drive_utils.delete_folder_by_id')
    def test_delete_folder_by_path(self, mock_delete_folder, mock_get_folder_id):
        """Test deleting a folder by path."""
        # Configure mocks
        mock_get_folder_id.return_value = 'folder_id'  # Folder exists
        mock_delete_folder.return_value = True  # Deletion successful
        
        # Test the function
        result = delete_folder_by_path(self.mock_drive_service, 'folder1/folder2')
        
        # Verify the result
        self.assertTrue(result)
        
        # Verify get_folder_id_by_path was called
        mock_get_folder_id.assert_called_once_with(self.mock_drive_service, 'folder1/folder2')
        
        # Verify delete_folder_by_id was called
        mock_delete_folder.assert_called_once_with(self.mock_drive_service, 'folder_id')


if __name__ == '__main__':
    unittest.main()
