#!/usr/bin/env python3
"""
Test script for the Google Drive Service file upload functionality.
This script tests both overwrite modes (with and without overwriting).
"""

import argparse
import os
import time

import requests


def create_test_file(filename, content):
    """Create a test file with the given content."""
    with open(filename, "w") as f:
        f.write(content)
    return os.path.abspath(filename)


def test_file_upload(base_url, folder_path, overwrite=True):
    """Test file upload with overwrite functionality."""
    # Create test files
    test_file1 = create_test_file("test_file.txt", f"Test content 1 - {time.time()}")
    test_file2 = create_test_file("test_file.txt", f"Test content 2 - {time.time()}")

    print(f"\n--- Testing file upload with overwrite={overwrite} ---")

    # Upload first file
    print(f"Uploading first file: {test_file1}")
    with open(test_file1, "rb") as f:
        files = {"file": f}
        data = {"folder_path": folder_path}
        if not overwrite:
            data["overwrite"] = "false"

        response = requests.post(f"{base_url}/upload_file", files=files, data=data, timeout=30)

    if response.status_code == 200:
        print(f"First upload successful: {response.json()}")
    else:
        print(f"First upload failed: {response.status_code} - {response.text}")
        return

    # Wait a moment
    time.sleep(1)

    # Upload second file with same name
    print(f"\nUploading second file with same name: {test_file2}")
    with open(test_file2, "rb") as f:
        files = {"file": f}
        data = {"folder_path": folder_path}
        if not overwrite:
            data["overwrite"] = "false"

        response = requests.post(f"{base_url}/upload_file", files=files, data=data, timeout=30)

    if response.status_code == 200:
        print(f"Second upload successful: {response.json()}")
    else:
        print(f"Second upload failed: {response.status_code} - {response.text}")

    # Clean up test files
    os.remove(test_file1)
    os.remove(test_file2)


def main():
    parser = argparse.ArgumentParser(description="Test Google Drive Service file upload functionality")
    parser.add_argument("--url", default="http://localhost:5001", help="Base URL of the Google Drive Service")
    parser.add_argument("--folder", default="test_folder", help="Folder path to upload to")

    args = parser.parse_args()

    # Test with overwrite=True (default)
    test_file_upload(args.url, args.folder, overwrite=True)

    # Test with overwrite=False
    test_file_upload(args.url, args.folder, overwrite=False)


if __name__ == "__main__":
    main()
