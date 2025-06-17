# Contributing to Google Drive Service

Thank you for your interest in contributing to the Google Drive Service! This document provides guidelines and information for contributors.

## Code Quality Standards

This project maintains high code quality standards through automated tools and processes. All contributions must adhere to these standards.

### Code Style

- **Python Code Style**: Follow PEP 8 with 120 character line length
- **Import Organization**: Use isort with black profile
- **Code Formatting**: Use black formatter (automatically applied by pre-commit hooks)
- **Docstrings**: All modules, classes, and functions should have descriptive docstrings

### Quality Tools

The project uses several automated quality tools:

- **Black**: Code formatting (120 char line length)
- **isort**: Import sorting and organization  
- **flake8**: Linting with plugins (bugbear, comprehensions, simplify)
- **bandit**: Security vulnerability scanning
- **pytest**: Testing with coverage requirements

## Development Workflow

### 1. Setup Development Environment

```bash
# Clone the repository
git clone https://github.com/PitchConnect/google-drive-service.git
cd google-drive-service

# Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Install pre-commit hooks
pre-commit install
```

### 2. Create Feature Branch

```bash
git checkout -b feature/your-feature-name
```

### 3. Make Changes

- Write code following the established patterns
- Add tests for new functionality
- Update documentation as needed
- Ensure all quality checks pass locally

### 4. Run Quality Checks

```bash
# Run all pre-commit hooks
pre-commit run --all-files

# Run tests with coverage
pytest --cov=./ --cov-report=term

# Check specific tools individually
black --check .
isort --check-only .
flake8 .
bandit -r . -c .bandit.yaml
```

### 5. Commit Changes

Pre-commit hooks will automatically run on commit. If any checks fail, fix the issues and commit again.

```bash
git add .
git commit -m "feat: add new feature description"
```

### 6. Push and Create Pull Request

```bash
git push origin feature/your-feature-name
```

Create a pull request with:
- Clear description of changes
- Reference to any related issues
- Screenshots/examples if applicable

## Pull Request Guidelines

### Requirements

- ✅ All tests must pass (119+ tests)
- ✅ Code coverage must be ≥78% (currently 80%+)
- ✅ All quality checks must pass (black, isort, flake8, bandit)
- ✅ No high-severity security issues
- ✅ Clear commit messages following conventional commits

### PR Description Template

```markdown
## Summary
Brief description of changes

## Changes Made
- List of specific changes
- New features added
- Bug fixes

## Testing
- [ ] All existing tests pass
- [ ] New tests added for new functionality
- [ ] Manual testing completed

## Quality Checks
- [ ] Code formatted with black
- [ ] Imports organized with isort
- [ ] Linting passes (flake8)
- [ ] Security scan passes (bandit)
- [ ] Coverage maintained/improved
```

## Testing Requirements

### Test Coverage

- Minimum 78% code coverage required
- New features must include comprehensive tests
- Tests should cover both success and error cases

### Test Types

- **Unit Tests**: Test individual functions and methods
- **Integration Tests**: Test component interactions
- **Mock Tests**: Use mocks for external dependencies (Google Drive API)

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=./ --cov-report=term

# Run specific test file
pytest tests/test_app.py

# Run with verbose output
pytest -v
```

## Security Guidelines

### Security Scanning

All code is automatically scanned for security vulnerabilities using bandit. 

### Acceptable Security Findings

Current acceptable findings (documented in `.bandit.yaml`):
- B104: Hardcoded bind all interfaces (required for containerized deployment)
- B108: Hardcoded temp directory (standard practice for file uploads)

### Security Best Practices

- Never commit credentials or secrets
- Use environment variables for configuration
- Validate all user inputs
- Follow principle of least privilege
- Keep dependencies updated

## Documentation

### Code Documentation

- All modules must have descriptive docstrings
- Functions should document parameters and return values
- Complex logic should include inline comments

### README Updates

Update README.md when:
- Adding new API endpoints
- Changing configuration options
- Modifying deployment procedures
- Adding new features

## Release Process

### Version Numbering

This project uses calendar versioning (CalVer): `YYYY.MM.PATCH`

- `YYYY`: Year (e.g., 2025)
- `MM`: Month (e.g., 01 for January)
- `PATCH`: Incremental patch number

### Creating Releases

1. Update version using the bump script:
   ```bash
   python scripts/bump_version.py patch
   ```

2. Create and push tag:
   ```bash
   git tag -a v2025.01.1 -m "Release v2025.01.1"
   git push origin main --tags
   ```

3. GitHub Actions will automatically build and publish Docker images

## Getting Help

- **Issues**: Create GitHub issues for bugs or feature requests
- **Discussions**: Use GitHub Discussions for questions
- **Code Review**: All PRs receive thorough code review

## Code of Conduct

- Be respectful and inclusive
- Focus on constructive feedback
- Help maintain a positive community environment

Thank you for contributing to the Google Drive Service! 🚀
