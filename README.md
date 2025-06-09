# Google Drive Service

A microservice for interacting with Google Drive, providing endpoints for file uploads and folder management.

## Features

- Google Drive authentication
- File uploads to specific folders
- Folder creation and deletion
- Automatic folder path creation (nested folders)
- File overwrite control
- Comprehensive test suite
- Robust error handling and retry mechanisms
- Rate limiting to prevent API quota issues
- Circuit breaker pattern for resilience
- Detailed error responses

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
Returns the health status of the service with detailed information.

**Response:**
```json
{
  "service": "google-drive-service",
  "status": "healthy",
  "timestamp": 1623456789.123,
  "version": "development",
  "auth_status": "authenticated",
  "api_response_time_ms": 123.45,
  "api_connectivity": true
}
```

#### GET /info
Returns information about the service, including available endpoints.

#### GET /version
Returns detailed version information including build date and environment.

## Docker Deployment

### Using Docker Compose
```bash
docker-compose up -d
```

### Using Docker Hub Images
```bash
# Pull latest version
docker pull ghcr.io/pitchconnect/google-drive-service:latest

# Run container
docker run -p 5000:5000 ghcr.io/pitchconnect/google-drive-service:latest
```

### Available Tags
- `latest`: Most recent release
- `YYYY.MM.PATCH`: Specific version (e.g., `2025.01.0`)
- `YYYY.MM`: Monthly version (e.g., `2025.01`)

## Configuration

The service requires a `credentials.json` file from the Google Cloud Console with the Drive API enabled.

### Environment Variables

- `LOG_LEVEL`: Logging level (default: INFO)
- `FLASK_ENV`: Environment (development/production)
- `FLASK_DEBUG`: Enable debug mode (true/false)
- `PORT`: Port to run the service on (default: 5000)
- `SERVICE_VERSION`: Version of the service (default: development)

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

## Error Handling

The service implements several layers of error handling and resilience:

### Retry Mechanism

All Google Drive API calls are automatically retried with exponential backoff when transient errors occur:

- Rate limit exceeded errors
- Server-side errors (500, 502, 503, 504)
- Network connectivity issues

### Rate Limiting

API calls are rate-limited to prevent exceeding Google Drive API quotas:

- Default: 5 calls per second
- Burst: Up to 10 calls at once

### Circuit Breaker

The circuit breaker pattern is implemented to prevent cascading failures:

1. After 5 consecutive failures, the circuit opens
2. In open state, calls fail fast without attempting API calls
3. After 60 seconds, the circuit transitions to half-open
4. If a call succeeds in half-open state, the circuit closes

### Detailed Error Responses

All API endpoints return structured error responses:

```json
{
  "error": {
    "type": "ErrorType",
    "message": "Detailed error message",
    "details": [...] // Optional additional details
  }
}
```
