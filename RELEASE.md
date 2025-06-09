# Release Process Documentation

## Overview

This document describes the automated release process for the Google Drive Service. The system uses a hybrid versioning strategy combining calendar versioning with semantic versioning principles.

## Versioning Strategy

**Format**: `YYYY.MM.PATCH` (e.g., `2025.01.0`, `2025.01.1`)

- **YYYY.MM**: Year and month for major/minor releases
- **PATCH**: Incremental patch number for hotfixes
- **Benefits**: Clear timeline context, simple automation, semantic meaning

## Release Types

### 1. Monthly Releases (Automated)
- **Trigger**: First Monday of each month at 09:00 UTC
- **Version**: `YYYY.MM.0` (e.g., `2025.02.0`)
- **Purpose**: Regular feature releases and updates

### 2. Patch Releases (Manual)
- **Trigger**: Manual workflow dispatch
- **Version**: Increments patch number (e.g., `2025.01.0` → `2025.01.1`)
- **Purpose**: Bug fixes and minor improvements

### 3. Hotfix Releases (Manual)
- **Trigger**: Manual workflow dispatch with description
- **Version**: Increments patch number with hotfix tag
- **Purpose**: Critical bug fixes requiring immediate deployment

### 4. Manual Releases
- **Trigger**: Manual workflow dispatch with custom version
- **Version**: User-specified (must follow `YYYY.MM.PATCH` format)
- **Purpose**: Special releases or version corrections

## Release Workflow

### Quality Gates
All releases must pass:
1. **Test Suite**: 100% test pass rate with 80%+ coverage
2. **Security Scan**: Safety and Bandit security checks
3. **Code Quality**: Flake8 linting for critical issues

### Automated Steps
1. **Version Determination**: Calculate next version based on release type
2. **Quality Gates**: Run comprehensive tests and security scans
3. **Version Update**: Update `version.py` with new version
4. **Git Tagging**: Create annotated git tag
5. **Docker Build**: Build and tag Docker image
6. **Registry Push**: Push to GitHub Container Registry (ghcr.io)
7. **Release Creation**: Generate GitHub release with notes
8. **Notification**: Success/failure notifications

## Docker Images

### Registry
- **Location**: `ghcr.io/pitchconnect/google-drive-service`
- **Tags**:
  - `latest`: Most recent release
  - `YYYY.MM.PATCH`: Specific version (e.g., `2025.01.0`)
  - `YYYY.MM`: Monthly version (e.g., `2025.01`)
  - `hotfix-YYYY.MM.PATCH`: Hotfix releases

### Usage
```bash
# Pull latest version
docker pull ghcr.io/pitchconnect/google-drive-service:latest

# Pull specific version
docker pull ghcr.io/pitchconnect/google-drive-service:2025.01.0

# Run container
docker run -p 5000:5000 ghcr.io/pitchconnect/google-drive-service:latest
```

## Manual Release Process

### Standard Release
1. Go to **Actions** → **Release and Deploy**
2. Click **Run workflow**
3. Select release type: `patch`, `minor`, or `manual`
4. For manual releases, specify version in `YYYY.MM.PATCH` format
5. Click **Run workflow**

### Hotfix Release
1. Go to **Actions** → **Hotfix Release**
2. Click **Run workflow**
3. Enter hotfix description
4. Specify target branch (usually `main`)
5. Click **Run workflow**

## Monitoring and Verification

### Release Verification
After each release:
1. Check GitHub Releases page for new release
2. Verify Docker image in GitHub Packages
3. Test health endpoint: `GET /health`
4. Verify version endpoint: `GET /version`

### Health Checks
The service includes comprehensive health checks:
- **Endpoint**: `GET /health`
- **Docker**: Built-in HEALTHCHECK directive
- **Compose**: Health check configuration

### Version Information
- **Endpoint**: `GET /version`
- **Response**: Detailed version and build information

## Troubleshooting

### Failed Release
1. Check workflow logs in GitHub Actions
2. Verify all quality gates passed
3. Check for version conflicts
4. Ensure proper permissions for GitHub token

### Rollback Process
1. Identify previous working version
2. Deploy previous Docker image:
   ```bash
   docker pull ghcr.io/pitchconnect/google-drive-service:PREVIOUS_VERSION
   ```
3. Update deployment configurations
4. Create hotfix if needed

## Security Considerations

### Automated Scans
- **Safety**: Checks for known security vulnerabilities in dependencies
- **Bandit**: Static security analysis for Python code
- **Container Scanning**: GitHub automatically scans pushed images

### Access Control
- **Registry**: GitHub Container Registry with organization access control
- **Workflows**: Require appropriate permissions for package publishing
- **Secrets**: Use GitHub secrets for sensitive configuration

## Best Practices

### Before Release
1. Ensure all tests pass locally
2. Update documentation if needed
3. Review security scan results
4. Test Docker build locally

### Version Management
1. Follow semantic versioning principles
2. Use descriptive commit messages
3. Tag releases appropriately
4. Maintain changelog

### Monitoring
1. Monitor release workflow execution
2. Verify deployment success
3. Check application health post-deployment
4. Monitor for any issues or errors

## Configuration

### Environment Variables
- `SERVICE_VERSION`: Set automatically during build
- `FLASK_ENV`: Environment (development/production)
- `LOG_LEVEL`: Logging level
- `PORT`: Service port (default: 5000)

### Required Secrets
- `GITHUB_TOKEN`: Automatically provided by GitHub Actions
- Additional secrets may be required for deployment targets
