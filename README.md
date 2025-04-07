# Google Drive Service

A microservice for interacting with Google Drive, providing endpoints for file uploads and folder management.

## Features

- Google Drive authentication
- File uploads to specific folders
- Folder creation and deletion
- Automatic folder path creation (nested folders)
- File overwrite control
- Comprehensive test suite

## API Endpoints

### Authentication

#### GET /authorize_gdrive
Returns a Google authorization URL that the user should visit to authorize the application.

#### POST /submit_auth_code
Submits the authorization code obtained from Google to get access tokens.

**Parameters:**
- `code`: The authorization code from Google

### File Operations

#### POST /upload_file
Uploads a file to a specified folder path in Google Drive.

**Parameters:**
- `file`: The file to upload (multipart/form-data)
- `folder_path`: The folder path in Google Drive (e.g., "folder1/folder2")
- `overwrite`: (Optional) Set to "false" to keep both files if a file with the same name exists. Default is "true" (overwrite existing files).

**Response:**
```json
{
  "status": "success",
  "file_url": "https://drive.google.com/file/d/...",
  "overwrite_mode": "enabled"
}
```

#### POST /delete_folder
Deletes a folder in Google Drive by path.

**Parameters:**
- `folder_path`: The folder path to delete

### Health Check

#### GET /health
Returns the health status of the service.

## Docker Deployment

The service can be deployed using Docker and Docker Compose:

```bash
docker-compose up -d
```

## Configuration

The service requires a `credentials.json` file from the Google Cloud Console with the Drive API enabled.

## Development

### Testing

This project includes a comprehensive test suite using pytest. To run the tests:

1. Install development dependencies:
   ```bash
   pip install -r requirements-dev.txt
   ```

2. Run the tests:
   ```bash
   ./run_tests.sh
   ```

   Or use pytest directly:
   ```bash
   pytest
   ```

3. To see test coverage:
   ```bash
   pytest --cov=./ --cov-report=term
   ```

### Continuous Integration

This project uses GitHub Actions for continuous integration. Pull requests to the main branch require passing tests before they can be merged.

The CI pipeline:
1. Runs the test suite
2. Generates code coverage reports
3. Prevents merging PRs with failing tests

### Mock Google Drive Service

For testing purposes, a mock implementation of the Google Drive service is provided in `tests/mock_google_drive.py`. This allows for integration testing without actual Google Drive API calls.
