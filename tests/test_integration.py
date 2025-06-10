"""
Integration tests for Google Drive Service.
"""

import unittest
import json
import io
import os
from unittest.mock import patch, MagicMock

from app import app


class TestIntegration(unittest.TestCase):
    """Integration tests for the complete service workflow."""
    
    def setUp(self):
        """Set up test fixtures before each test method."""
        app.config['TESTING'] = True
        self.client = app.test_client()
        self.test_file_content = b'Integration test file content'
    
    def test_service_info_endpoint(self):
        """Test the /info endpoint returns correct service information."""
        response = self.client.get('/info')
        
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.data)
        
        # Check required fields
        self.assertIn('service', response_data)
        self.assertIn('description', response_data)
        self.assertIn('version', response_data)
        self.assertIn('endpoints', response_data)
        
        # Check specific values
        self.assertEqual(response_data['service'], 'google-drive-service')
        self.assertIsInstance(response_data['endpoints'], list)
        self.assertTrue(len(response_data['endpoints']) > 0)
        
        # Check endpoint structure
        for endpoint in response_data['endpoints']:
            self.assertIn('path', endpoint)
            self.assertIn('method', endpoint)
            self.assertIn('description', endpoint)
    
    def test_health_check_workflow(self):
        """Test the complete health check workflow."""
        with patch('app.authenticate_google_drive') as mock_auth:
            # Test healthy state
            mock_auth.return_value = MagicMock()
            
            response = self.client.get('/health')
            self.assertEqual(response.status_code, 200)
            
            response_data = json.loads(response.data)
            self.assertEqual(response_data['status'], 'healthy')
            self.assertIn('timestamp', response_data)
            self.assertIn('service', response_data)
    
    def test_authorization_workflow(self):
        """Test the complete authorization workflow."""
        # Step 1: Get authorization URL
        with patch('app.generate_authorization_url') as mock_generate_url:
            mock_generate_url.return_value = 'https://accounts.google.com/oauth/authorize?...'
            
            response = self.client.get('/authorize_gdrive')
            self.assertEqual(response.status_code, 200)
            
            response_data = json.loads(response.data)
            self.assertIn('authorization_url', response_data)
            self.assertTrue(response_data['authorization_url'].startswith('https://'))
        
        # Step 2: Submit authorization code
        with patch('app.exchange_code_for_tokens') as mock_exchange:
            mock_exchange.return_value = True

            response = self.client.post('/submit_auth_code',
                                      data={'code': 'test_auth_code'})
            self.assertEqual(response.status_code, 200)

            response_data = json.loads(response.data)
            self.assertIn('message', response_data)
    
    @patch('app.check_token_exists')
    @patch('app.authenticate_google_drive')
    @patch('app.create_folder_if_not_exists')
    @patch('app.upload_file_to_drive')
    @patch('os.path.join')
    @patch('os.remove')
    def test_complete_file_upload_workflow(self, mock_remove, mock_join, mock_upload, 
                                         mock_create_folder, mock_auth, mock_check_token):
        """Test the complete file upload workflow."""
        # Configure mocks
        mock_check_token.return_value = True
        mock_auth.return_value = MagicMock()
        mock_create_folder.return_value = 'test_folder_id'
        mock_upload.return_value = 'https://drive.google.com/file/d/test_file_id'
        mock_join.return_value = '/tmp/test_file.txt'
        
        # Test file upload
        data = {
            'folder_path': 'integration/test/folder',
            'file': (io.BytesIO(self.test_file_content), 'integration_test.txt'),
            'overwrite': 'true'
        }
        
        response = self.client.post('/upload_file', data=data)
        self.assertEqual(response.status_code, 200)
        
        response_data = json.loads(response.data)
        self.assertIn('status', response_data)
        self.assertIn('file_url', response_data)
        self.assertTrue(response_data['file_url'].startswith('https://'))
        
        # Verify the workflow called the right functions
        mock_check_token.assert_called_once()
        mock_auth.assert_called_once()
        mock_create_folder.assert_called_once()
        mock_upload.assert_called_once()
    
    @patch('app.check_token_exists')
    @patch('app.authenticate_google_drive')
    @patch('app.delete_folder_by_path')
    def test_complete_folder_deletion_workflow(self, mock_delete, mock_auth, mock_check_token):
        """Test the complete folder deletion workflow."""
        # Configure mocks
        mock_check_token.return_value = True
        mock_auth.return_value = MagicMock()
        mock_delete.return_value = True
        
        # Test folder deletion
        data = {
            'folder_path': 'integration/test/folder'
        }
        
        response = self.client.post('/delete_folder',
                                  data=data)
        self.assertEqual(response.status_code, 200)
        
        response_data = json.loads(response.data)
        self.assertIn('message', response_data)
        
        # Verify the workflow called the right functions
        mock_check_token.assert_called_once()
        mock_auth.assert_called_once()
        mock_delete.assert_called_once_with(mock_auth.return_value, 'integration/test/folder')
    
    def test_error_handling_integration(self):
        """Test error handling across the service."""
        # Test missing required fields
        response = self.client.post('/submit_auth_code', data={})
        self.assertEqual(response.status_code, 400)
        
        # Test missing required fields for upload (should check auth first)
        response = self.client.post('/upload_file', data={})
        self.assertEqual(response.status_code, 401)
        
        # Test unauthorized access
        with patch('app.check_token_exists') as mock_check_token:
            mock_check_token.return_value = False
            
            data = {
                'folder_path': 'test/folder',
                'file': (io.BytesIO(self.test_file_content), 'test.txt')
            }
            
            response = self.client.post('/upload_file', data=data)
            self.assertEqual(response.status_code, 401)
    
    def test_request_tracking_integration(self):
        """Test that request tracking works across endpoints."""
        # Make multiple requests and verify they're tracked
        responses = []
        
        for i in range(3):
            response = self.client.get('/info')
            responses.append(response)
            self.assertEqual(response.status_code, 200)
        
        # All requests should have succeeded
        self.assertEqual(len(responses), 3)
    
    def test_content_type_handling(self):
        """Test handling of different content types."""
        # Test JSON content type
        response = self.client.post('/submit_auth_code', 
                                  data=json.dumps({'code': 'test'}),
                                  content_type='application/json')
        # Should not crash (might return error due to mocking, but shouldn't be 500)
        self.assertNotEqual(response.status_code, 500)
        
        # Test multipart form data
        data = {
            'folder_path': 'test',
            'file': (io.BytesIO(b'test'), 'test.txt')
        }
        response = self.client.post('/upload_file', data=data)
        # Should not crash (might return error due to mocking, but shouldn't be 500)
        self.assertNotEqual(response.status_code, 500)
    
    def test_environment_configuration(self):
        """Test that environment configuration is properly handled."""
        # Test that the app can handle different configurations
        with patch.dict(os.environ, {'LOG_LEVEL': 'DEBUG'}):
            response = self.client.get('/info')
            self.assertEqual(response.status_code, 200)
        
        with patch.dict(os.environ, {'FLASK_ENV': 'testing'}):
            response = self.client.get('/info')
            self.assertEqual(response.status_code, 200)
    
    def test_version_endpoint_integration(self):
        """Test version information integration."""
        response = self.client.get('/info')
        self.assertEqual(response.status_code, 200)
        
        response_data = json.loads(response.data)
        version = response_data.get('version')
        
        # Version should be present and follow expected format
        self.assertIsNotNone(version)
        self.assertIsInstance(version, str)
        self.assertTrue(len(version) > 0)
        
        # Should contain dots (version format)
        self.assertIn('.', version)


if __name__ == '__main__':
    unittest.main()
