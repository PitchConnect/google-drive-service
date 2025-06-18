# Code Quality Standards

This document outlines the comprehensive code quality standards and tools used in the Google Drive Service project.

## Overview

The project maintains high code quality through automated tools, pre-commit hooks, and CI/CD pipeline enforcement. All code must pass quality checks before being merged.

## Quality Metrics

### Current Standards

- **Test Coverage**: ≥78% (currently 80%+)
- **Code Style**: PEP 8 compliant with 120 character line length
- **Security**: No high-severity vulnerabilities
- **Linting**: Zero flake8 violations on main code paths

### Quality Tools Stack

| Tool | Purpose | Configuration |
|------|---------|---------------|
| **Black** | Code formatting | `pyproject.toml` |
| **isort** | Import organization | `pyproject.toml` |
| **flake8** | Linting & style | `.flake8` |
| **bandit** | Security scanning | `.bandit.yaml` |
| **pytest** | Testing & coverage | `pytest.ini` |
| **pre-commit** | Hook management | `.pre-commit-config.yaml` |

## Code Formatting

### Black Configuration

```toml
[tool.black]
line-length = 120
target-version = ['py39']
include = '\.pyi?$'
```

**Key Standards:**
- 120 character line length
- Double quotes for strings
- Consistent indentation (4 spaces)
- Automatic trailing comma insertion

### Import Organization (isort)

```toml
[tool.isort]
profile = "black"
line_length = 120
multi_line_output = 3
include_trailing_comma = true
force_grid_wrap = 0
use_parentheses = true
ensure_newline_before_comments = true
```

**Import Order:**
1. Standard library imports
2. Third-party imports
3. Local application imports

## Linting Standards

### flake8 Configuration

```ini
[flake8]
max-line-length = 120
extend-ignore = E203, W503, D100, D103
max-complexity = 15
select = E,W,F,C,B,SIM
```

**Enabled Plugins:**
- `flake8-bugbear`: Additional bug detection
- `flake8-comprehensions`: List/dict comprehension improvements
- `flake8-simplify`: Code simplification suggestions

**Ignored Rules:**
- `E203`: Whitespace before ':' (conflicts with black)
- `W503`: Line break before binary operator (conflicts with black)
- `D100`: Missing docstring in public module (handled separately)
- `D103`: Missing docstring in public function (handled separately)

### Complexity Limits

- **Maximum function complexity**: 15 (McCabe complexity)
- **Maximum line length**: 120 characters
- **Maximum function length**: No hard limit, but prefer smaller functions

## Security Standards

### bandit Configuration

```yaml
exclude_dirs:
  - tests/
  - venv/
  - .venv/
  - env/
  - .env/
  - build/
  - dist/
  - htmlcov/

skips:
  - B101  # assert_used
  - B601  # paramiko_calls
```

**Acceptable Security Findings:**

| Finding | Severity | Rationale |
|---------|----------|-----------|
| B104 | Medium | Hardcoded bind all interfaces - required for containerized deployment |
| B108 | Medium | Hardcoded temp directory - standard practice for file uploads |

**Security Best Practices:**
- No hardcoded credentials
- Input validation on all endpoints
- Secure file handling
- Environment-based configuration

## Testing Standards

### Coverage Requirements

- **Minimum coverage**: 78%
- **Current coverage**: 80%+
- **Target coverage**: 85%+

### Test Structure

```
tests/
├── test_app.py              # Flask application tests
├── test_google_drive_utils.py  # Google Drive utility tests
├── test_integration.py      # Integration tests
├── test_retry_utils.py      # Retry mechanism tests
├── test_version.py          # Version module tests
└── mock_google_drive.py     # Mock implementations
```

### Test Categories

1. **Unit Tests**: Individual function testing
2. **Integration Tests**: Component interaction testing
3. **Mock Tests**: External dependency testing
4. **Error Handling Tests**: Exception and edge case testing

## Pre-commit Hooks

### Hook Configuration

```yaml
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-json
      - id: check-added-large-files
      - id: check-merge-conflicts
      - id: debug-statements

  - repo: https://github.com/pycqa/isort
    hooks:
      - id: isort

  - repo: https://github.com/psf/black
    hooks:
      - id: black

  - repo: https://github.com/pycqa/flake8
    hooks:
      - id: flake8

  - repo: https://github.com/PyCQA/bandit
    hooks:
      - id: bandit
        args: ['-c', '.bandit.yaml']

  - repo: local
    hooks:
      - id: pytest
        name: pytest
        entry: pytest
        language: system
        pass_filenames: false
        always_run: true

      - id: pytest-cov
        name: pytest-coverage
        entry: pytest
        language: system
        pass_filenames: false
        always_run: true
        args: ['--cov=./', '--cov-report=term', '--cov-fail-under=78']
```

### Hook Execution Order

1. **File checks**: Whitespace, file endings, YAML/JSON syntax
2. **Import sorting**: isort organization
3. **Code formatting**: Black formatting
4. **Linting**: flake8 style and complexity checks
5. **Security**: bandit vulnerability scanning
6. **Testing**: pytest execution with coverage

## CI/CD Pipeline

### GitHub Actions Workflow

The CI/CD pipeline enforces all quality standards:

```yaml
name: Code Quality

on:
  push:
    branches: [ main ]
  pull_request:
    branches: [ main ]

jobs:
  code-quality:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v4
    - uses: actions/setup-python@v5
    - name: Install dependencies
    - name: Run pre-commit hooks
    - name: Run bandit security scan
    - name: Run flake8 linting
    - name: Check import sorting
    - name: Check code formatting
    - name: Upload bandit results
```

### Quality Gates

All PRs must pass:
- ✅ Pre-commit hook execution
- ✅ Security scan (no high-severity issues)
- ✅ Linting (zero violations)
- ✅ Code formatting verification
- ✅ Import organization check
- ✅ Test execution (119+ tests)
- ✅ Coverage requirement (≥78%)

## Local Development

### Setup Commands

```bash
# Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Install pre-commit hooks
pre-commit install

# Run all quality checks
pre-commit run --all-files

# Run tests with coverage
pytest --cov=./ --cov-report=term
```

### Manual Quality Checks

```bash
# Code formatting
black --check .
black .  # Apply formatting

# Import sorting
isort --check-only .
isort .  # Apply sorting

# Linting
flake8 .

# Security scanning
bandit -r . -c .bandit.yaml

# Testing
pytest
pytest --cov=./ --cov-report=html  # Generate HTML coverage report
```

## Troubleshooting

### Common Issues

1. **Pre-commit hooks fail**: Run `pre-commit run --all-files` to see specific failures
2. **Coverage below threshold**: Add tests for uncovered code paths
3. **Linting violations**: Use `flake8 .` to see specific issues
4. **Import organization**: Run `isort .` to fix import order
5. **Code formatting**: Run `black .` to apply formatting

### Skipping Hooks (Emergency Only)

```bash
# Skip all hooks (not recommended)
git commit --no-verify -m "emergency fix"

# Skip specific hooks
SKIP=pytest,pytest-cov git commit -m "skip tests temporarily"
```

## Continuous Improvement

### Metrics Tracking

- Monitor test coverage trends
- Track security scan results
- Review linting violation patterns
- Analyze CI/CD pipeline performance

### Tool Updates

- Regularly update tool versions
- Review and adjust configuration
- Evaluate new quality tools
- Gather team feedback on standards

---

This document is maintained alongside the codebase and should be updated when quality standards or tools change.
