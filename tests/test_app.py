import unittest
from unittest.mock import patch, MagicMock
import json
import os
import io
import tempfile
from app import app


class TestApp(unittest.TestCase):
    
    def setUp(self):
        """Set up test fixtures before each test method."""
        app.config['TESTING'] = True
        self.client = app.test_client()
        
        # Create a test file
        self.test_file_content = b'Test file content'
    
    def test_health_check_healthy(self):
        """Test the health check endpoint when the service is healthy."""
        with patch('app.authenticate_google_drive') as mock_auth:
            # Configure mock to return a valid service
            mock_auth.return_value = MagicMock()
            
            # Make request
            response = self.client.get('/health')
            
            # Check response
            self.assertEqual(response.status_code, 200)
            response_data = json.loads(response.data)
            self.assertEqual(response_data['status'], 'healthy')
    
    def test_health_check_degraded(self):
        """Test the health check endpoint when authentication is required."""
        with patch('app.authenticate_google_drive') as mock_auth:
            # Configure mock to return None (auth required)
            mock_auth.return_value = None
            
            # Make request
            response = self.client.get('/health')
            
            # Check response
            self.assertEqual(response.status_code, 200)
            response_data = json.loads(response.data)
            self.assertEqual(response_data['status'], 'degraded')
            self.assertEqual(response_data['reason'], 'auth_required')
    
    def test_health_check_unhealthy(self):
        """Test the health check endpoint when an error occurs."""
        with patch('app.authenticate_google_drive') as mock_auth:
            # Configure mock to raise an exception
            mock_auth.side_effect = Exception('Test error')
            
            # Make request
            response = self.client.get('/health')
            
            # Check response
            self.assertEqual(response.status_code, 500)
            response_data = json.loads(response.data)
            self.assertEqual(response_data['status'], 'unhealthy')
            self.assertEqual(response_data['reason'], 'Test error')
    
    def test_authorize_gdrive_success(self):
        """Test the authorize_gdrive endpoint when successful."""
        with patch('app.generate_authorization_url') as mock_gen_url:
            # Configure mock to return a URL
            mock_gen_url.return_value = 'https://accounts.google.com/o/oauth2/auth?...'
            
            # Make request
            response = self.client.get('/authorize_gdrive')
            
            # Check response
            self.assertEqual(response.status_code, 200)
            response_data = json.loads(response.data)
            self.assertEqual(response_data['authorization_url'], 'https://accounts.google.com/o/oauth2/auth?...')
    
    def test_authorize_gdrive_failure(self):
        """Test the authorize_gdrive endpoint when it fails."""
        with patch('app.generate_authorization_url') as mock_gen_url:
            # Configure mock to return None (failure)
            mock_gen_url.return_value = None
            
            # Make request
            response = self.client.get('/authorize_gdrive')
            
            # Check response
            self.assertEqual(response.status_code, 500)
            response_data = json.loads(response.data)
            self.assertIn('error', response_data)
    
    def test_submit_auth_code_missing_code(self):
        """Test the submit_auth_code endpoint when the code is missing."""
        # Make request without code
        response = self.client.post('/submit_auth_code')
        
        # Check response
        self.assertEqual(response.status_code, 400)
        response_data = json.loads(response.data)
        self.assertIn('error', response_data)
    
    def test_submit_auth_code_success(self):
        """Test the submit_auth_code endpoint when successful."""
        with patch('app.exchange_code_for_tokens') as mock_exchange:
            # Configure mock to return success
            mock_exchange.return_value = True
            
            # Make request
            response = self.client.post('/submit_auth_code', data={'code': 'test_code'})
            
            # Check response
            self.assertEqual(response.status_code, 200)
            response_data = json.loads(response.data)
            self.assertEqual(response_data['status'], 'authorization_successful')
    
    def test_submit_auth_code_failure(self):
        """Test the submit_auth_code endpoint when it fails."""
        with patch('app.exchange_code_for_tokens') as mock_exchange:
            # Configure mock to return failure
            mock_exchange.return_value = False
            
            # Make request
            response = self.client.post('/submit_auth_code', data={'code': 'test_code'})
            
            # Check response
            self.assertEqual(response.status_code, 500)
            response_data = json.loads(response.data)
            self.assertIn('error', response_data)
    
    def test_upload_file_no_auth(self):
        """Test the upload_file endpoint when not authenticated."""
        with patch('app.check_token_exists') as mock_check_token:
            # Configure mock to return False (not authenticated)
            mock_check_token.return_value = False
            
            # Make request
            response = self.client.post('/upload_file')
            
            # Check response
            self.assertEqual(response.status_code, 401)
            response_data = json.loads(response.data)
            self.assertIn('error', response_data)
    
    def test_upload_file_no_file(self):
        """Test the upload_file endpoint when no file is provided."""
        with patch('app.check_token_exists') as mock_check_token:
            # Configure mock to return True (authenticated)
            mock_check_token.return_value = True
            
            # Make request without file
            response = self.client.post('/upload_file')
            
            # Check response
            self.assertEqual(response.status_code, 400)
            response_data = json.loads(response.data)
            self.assertIn('error', response_data)
            self.assertEqual(response_data['error'], 'No file part')
    
    def test_upload_file_no_folder_path(self):
        """Test the upload_file endpoint when no folder path is provided."""
        with patch('app.check_token_exists') as mock_check_token:
            # Configure mock to return True (authenticated)
            mock_check_token.return_value = True
            
            # Create test data with file but no folder path
            data = {
                'file': (io.BytesIO(self.test_file_content), 'test_file.txt')
            }
            
            # Make request
            response = self.client.post('/upload_file', 
                                       data=data,
                                       content_type='multipart/form-data')
            
            # Check response
            self.assertEqual(response.status_code, 400)
            response_data = json.loads(response.data)
            self.assertIn('error', response_data)
            self.assertEqual(response_data['error'], 'Folder path is required')
    
    @patch('app.check_token_exists')
    @patch('app.authenticate_google_drive')
    @patch('app.create_folder_if_not_exists')
    @patch('app.upload_file_to_drive')
    @patch('os.path.join')
    @patch('os.remove')
    def test_upload_file_success(self, mock_remove, mock_join, mock_upload, mock_create_folder, mock_auth, mock_check_token):
        """Test the upload_file endpoint when successful."""
        # Configure mocks
        mock_check_token.return_value = True
        mock_auth.return_value = MagicMock()
        mock_create_folder.return_value = 'folder_id'
        mock_upload.return_value = 'https://drive.google.com/file/d/123'
        mock_join.return_value = '/tmp/test_file.txt'
        
        # Create test data
        data = {
            'folder_path': 'test/folder',
            'file': (io.BytesIO(self.test_file_content), 'test_file.txt')
        }
        
        # Make request
        response = self.client.post('/upload_file', 
                                   data=data,
                                   content_type='multipart/form-data')
        
        # Check response
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.data)
        self.assertEqual(response_data['status'], 'success')
        self.assertEqual(response_data['file_url'], 'https://drive.google.com/file/d/123')
        self.assertEqual(response_data['overwrite_mode'], 'enabled')
        
        # Verify temp file was removed
        mock_remove.assert_called_once_with('/tmp/test_file.txt')
    
    @patch('app.check_token_exists')
    @patch('app.authenticate_google_drive')
    @patch('app.create_folder_if_not_exists')
    @patch('app.upload_file_to_drive')
    @patch('os.path.join')
    @patch('os.remove')
    def test_upload_file_with_overwrite_false(self, mock_remove, mock_join, mock_upload, mock_create_folder, mock_auth, mock_check_token):
        """Test the upload_file endpoint with overwrite=false."""
        # Configure mocks
        mock_check_token.return_value = True
        mock_auth.return_value = MagicMock()
        mock_create_folder.return_value = 'folder_id'
        mock_upload.return_value = 'https://drive.google.com/file/d/123'
        mock_join.return_value = '/tmp/test_file.txt'
        
        # Create test data
        data = {
            'folder_path': 'test/folder',
            'overwrite': 'false',
            'file': (io.BytesIO(self.test_file_content), 'test_file.txt')
        }
        
        # Make request
        response = self.client.post('/upload_file', 
                                   data=data,
                                   content_type='multipart/form-data')
        
        # Check response
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.data)
        self.assertEqual(response_data['status'], 'success')
        self.assertEqual(response_data['file_url'], 'https://drive.google.com/file/d/123')
        self.assertEqual(response_data['overwrite_mode'], 'disabled')
        
        # Verify upload_file_to_drive was called with overwrite=False
        mock_upload.assert_called_once_with(mock_auth.return_value, '/tmp/test_file.txt', 'folder_id', overwrite=False)
    
    @patch('app.check_token_exists')
    @patch('app.authenticate_google_drive')
    def test_upload_file_auth_failed(self, mock_auth, mock_check_token):
        """Test the upload_file endpoint when authentication fails."""
        # Configure mocks
        mock_check_token.return_value = True
        mock_auth.return_value = None  # Auth failed
        
        # Create test data
        data = {
            'folder_path': 'test/folder',
            'file': (io.BytesIO(self.test_file_content), 'test_file.txt')
        }
        
        # Make request
        response = self.client.post('/upload_file', 
                                   data=data,
                                   content_type='multipart/form-data')
        
        # Check response
        self.assertEqual(response.status_code, 500)
        response_data = json.loads(response.data)
        self.assertIn('error', response_data)
        self.assertIn('Google Drive authentication failed', response_data['error'])
    
    def test_delete_folder_no_folder_path(self):
        """Test the delete_folder endpoint when no folder path is provided."""
        # Make request without folder path
        response = self.client.post('/delete_folder')
        
        # Check response
        self.assertEqual(response.status_code, 400)
        response_data = json.loads(response.data)
        self.assertIn('error', response_data)
        self.assertEqual(response_data['error'], 'Folder path is required')
    
    @patch('app.authenticate_google_drive')
    @patch('app.delete_folder_by_path')
    def test_delete_folder_success(self, mock_delete_folder, mock_auth):
        """Test the delete_folder endpoint when successful."""
        # Configure mocks
        mock_auth.return_value = MagicMock()
        mock_delete_folder.return_value = True  # Deletion successful
        
        # Make request
        response = self.client.post('/delete_folder', data={'folder_path': 'test/folder'})
        
        # Check response
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.data)
        self.assertEqual(response_data['status'], 'success')
    
    @patch('app.authenticate_google_drive')
    @patch('app.delete_folder_by_path')
    def test_delete_folder_failure(self, mock_delete_folder, mock_auth):
        """Test the delete_folder endpoint when deletion fails."""
        # Configure mocks
        mock_auth.return_value = MagicMock()
        mock_delete_folder.return_value = False  # Deletion failed
        
        # Make request
        response = self.client.post('/delete_folder', data={'folder_path': 'test/folder'})
        
        # Check response
        self.assertEqual(response.status_code, 500)
        response_data = json.loads(response.data)
        self.assertEqual(response_data['status'], 'error')


if __name__ == '__main__':
    unittest.main()
