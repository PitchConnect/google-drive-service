#!/bin/bash
# Script to run tests locally

# Install development dependencies if needed
if [ "$1" == "--install" ]; then
    echo "Installing development dependencies..."
    pip install -r requirements-dev.txt
fi

# Run the tests with coverage
pytest --cov=./ --cov-report=term

# Exit with the pytest exit code
exit $?
