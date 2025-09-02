#!/usr/bin/env python3
"""
Debug script for CI/CD environment testing.
This script helps identify environment-specific issues that might cause test failures.
"""

import os
import platform
import subprocess  # nosec B404 - needed for CI/CD debugging
import sys
from pathlib import Path


def print_section(title):
    """Print a formatted section header."""
    print(f"\n{'=' * 60}")
    print(f" {title}")
    print(f"{'=' * 60}")


def run_command(cmd_list, description):
    """Run a command and print its output."""
    print(f"\n{description}:")
    print(f"Command: {' '.join(cmd_list)}")
    try:
        result = subprocess.run(
            cmd_list, capture_output=True, text=True, timeout=30, check=False
        )  # nosec B603 - controlled command execution for CI debugging
        print(f"Exit code: {result.returncode}")
        if result.stdout:
            print(f"STDOUT:\n{result.stdout}")
        if result.stderr:
            print(f"STDERR:\n{result.stderr}")
        return result.returncode == 0
    except subprocess.TimeoutExpired:
        print("Command timed out after 30 seconds")
        return False
    except Exception as e:
        print(f"Error running command: {e}")
        return False


def main():
    """Main debug function."""
    print_section("CI/CD Environment Debug Information")

    # System information
    print_section("System Information")
    print(f"Platform: {platform.platform()}")
    print(f"Python version: {sys.version}")
    print(f"Python executable: {sys.executable}")
    print(f"Current working directory: {os.getcwd()}")
    print(f"PYTHONPATH: {os.environ.get('PYTHONPATH', 'Not set')}")

    # Environment variables
    print_section("Relevant Environment Variables")
    env_vars = ["PATH", "PYTHONPATH", "HOME", "USER", "CI", "GITHUB_ACTIONS"]
    for var in env_vars:
        value = os.environ.get(var, "Not set")
        print(f"{var}: {value}")

    # File system check
    print_section("File System Check")
    current_dir = Path(".")
    print("Files in current directory:")
    for item in sorted(current_dir.iterdir()):
        if item.is_file():
            print(f"  FILE: {item.name} ({item.stat().st_size} bytes)")
        elif item.is_dir():
            print(f"  DIR:  {item.name}/")

    # Python packages
    print_section("Python Package Versions")
    packages = ["pytest", "pytest-cov", "coverage", "flask", "werkzeug", "google-api-python-client", "requests", "mock"]

    for package in packages:
        try:
            result = subprocess.run(  # nosec B603 - controlled execution for package version checking
                [
                    sys.executable,
                    "-c",
                    f'import {package.replace("-", "_")}; print({package.replace("-", "_")}.__version__)',
                ],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
            if result.returncode == 0:
                print(f"{package}: {result.stdout.strip()}")
            else:
                print(f"{package}: Not installed or error")
        except (subprocess.TimeoutExpired, subprocess.SubprocessError, OSError) as e:
            print(f"{package}: Error checking version - {e}")

    # Test discovery
    print_section("Test Discovery")
    run_command([sys.executable, "-m", "pytest", "--collect-only", "tests/"], "Pytest test collection")

    # Simple import test
    print_section("Import Tests")
    imports_to_test = [
        "import sys",
        "import os",
        "import pytest",
        "import coverage",
        "import flask",
        "from src.core import logging_config",
        "from src.core import error_handling",
    ]

    for import_stmt in imports_to_test:
        try:
            # Use compile and exec for safer execution of known import statements
            compiled_stmt = compile(import_stmt, "<string>", "exec")
            exec(compiled_stmt)  # nosec B102 - controlled execution of known import statements
            print(f"✅ {import_stmt}")
        except Exception as e:
            print(f"❌ {import_stmt} - Error: {e}")

    # Run a single simple test
    print_section("Single Test Execution")
    run_command(
        [sys.executable, "-m", "pytest", "tests/test_version.py::TestVersionModule::test_get_version", "-v"],
        "Run single simple test",
    )

    print_section("Debug Complete")
    print("If this script runs successfully but tests fail, the issue is likely in the test execution environment.")


if __name__ == "__main__":
    main()
