"""
Mock implementation of Google Drive service for testing.
This can be used for integration testing without actual Google Drive API calls.
"""

import json
import os
import uuid
from datetime import datetime


class MockFile:
    """Represents a file or folder in the mock Google Drive."""

    def __init__(self, name, parent_id=None, is_folder=False):
        self.id = str(uuid.uuid4())
        self.name = name
        self.parent_id = parent_id
        self.is_folder = is_folder
        self.mime_type = "application/vnd.google-apps.folder" if is_folder else "application/octet-stream"
        self.created_time = datetime.now().isoformat()
        self.web_view_link = f"https://drive.google.com/file/d/{self.id}"
        self.content = None  # For files only
        self.trashed = False

    def to_api_resource(self):
        """Convert to a format similar to Google Drive API response."""
        return {
            "id": self.id,
            "name": self.name,
            "mimeType": self.mime_type,
            "parents": [self.parent_id] if self.parent_id else [],
            "createdTime": self.created_time,
            "webViewLink": self.web_view_link,
            "trashed": self.trashed,
        }


class MockGoogleDriveService:
    """A mock implementation of Google Drive service for testing."""

    def __init__(self):
        self.files_db = {}  # Dictionary to store files: {file_id: MockFile}

        # Create root folder
        root = MockFile("root", is_folder=True)
        root.id = "root"  # Override with standard ID
        self.files_db[root.id] = root

    def files(self):
        """Return the files resource."""
        return MockFilesResource(self)


class MockFilesResource:
    """Mock implementation of the files resource."""

    def __init__(self, drive_service):
        self.drive_service = drive_service

    def list(self, q=None, fields=None):
        """Mock implementation of files().list()."""
        return MockListRequest(self.drive_service, q, fields)

    def create(self, body=None, media_body=None, fields=None):
        """Mock implementation of files().create()."""
        return MockCreateRequest(self.drive_service, body, media_body, fields)

    def delete(self, fileId=None):
        """Mock implementation of files().delete()."""
        return MockDeleteRequest(self.drive_service, fileId)

    def get(self, fileId=None, fields=None):
        """Mock implementation of files().get()."""
        return MockGetRequest(self.drive_service, fileId, fields)


class MockListRequest:
    """Mock implementation of the list request."""

    def __init__(self, drive_service, q, fields):
        self.drive_service = drive_service
        self.q = q
        self.fields = fields

    def execute(self):
        """Execute the list request."""
        # Parse query and return matching files
        matching_files = []

        if not self.q:
            # Return all files
            for file_id, file_obj in self.drive_service.files_db.items():
                if not file_obj.trashed:
                    matching_files.append(file_obj.to_api_resource())
        else:
            # Parse query
            conditions = self.q.split(" and ")
            for file_id, file_obj in self.drive_service.files_db.items():
                if file_obj.trashed:
                    continue

                matches_all = True
                for condition in conditions:
                    if "name='" in condition:
                        name = condition.split("name='")[1].split("'")[0]
                        if file_obj.name != name:
                            matches_all = False
                            break

                    if "mimeType='" in condition:
                        mime_type = condition.split("mimeType='")[1].split("'")[0]
                        if file_obj.mime_type != mime_type:
                            matches_all = False
                            break

                    if "' in parents" in condition:
                        parent_id = condition.split("'")[1]
                        if file_obj.parent_id != parent_id:
                            matches_all = False
                            break

                    if "trashed=" in condition:
                        trashed = condition.split("trashed=")[1].lower() == "true"
                        if file_obj.trashed != trashed:
                            matches_all = False
                            break

                if matches_all:
                    matching_files.append(file_obj.to_api_resource())

        # Return results in the format expected by the API
        return {"files": matching_files}


class MockCreateRequest:
    """Mock implementation of the create request."""

    def __init__(self, drive_service, body, media_body, fields):
        self.drive_service = drive_service
        self.body = body
        self.media_body = media_body
        self.fields = fields

    def execute(self):
        """Execute the create request."""
        name = self.body.get("name", "Untitled")
        mime_type = self.body.get("mimeType", "application/octet-stream")
        parents = self.body.get("parents", ["root"])
        parent_id = parents[0] if parents else "root"

        # Check if parent exists
        if parent_id not in self.drive_service.files_db:
            raise Exception(f"Parent folder with ID {parent_id} not found")

        # Create the file or folder
        is_folder = mime_type == "application/vnd.google-apps.folder"
        file_obj = MockFile(name, parent_id, is_folder)

        # Store in the database
        self.drive_service.files_db[file_obj.id] = file_obj

        # Return the file resource
        result = file_obj.to_api_resource()

        # Filter fields if specified
        if self.fields:
            field_list = self.fields.split(",")
            result = {k: v for k, v in result.items() if k in field_list}

        return result


class MockDeleteRequest:
    """Mock implementation of the delete request."""

    def __init__(self, drive_service, file_id):
        self.drive_service = drive_service
        self.file_id = file_id

    def execute(self):
        """Execute the delete request."""
        if self.file_id not in self.drive_service.files_db:
            raise Exception(f"File with ID {self.file_id} not found")

        # Mark as trashed
        self.drive_service.files_db[self.file_id].trashed = True

        # Return empty response
        return {}


class MockGetRequest:
    """Mock implementation of the get request."""

    def __init__(self, drive_service, file_id, fields):
        self.drive_service = drive_service
        self.file_id = file_id
        self.fields = fields

    def execute(self):
        """Execute the get request."""
        if self.file_id not in self.drive_service.files_db:
            raise Exception(f"File with ID {self.file_id} not found")

        # Return the file resource
        result = self.drive_service.files_db[self.file_id].to_api_resource()

        # Filter fields if specified
        if self.fields:
            field_list = self.fields.split(",")
            result = {k: v for k, v in result.items() if k in field_list}

        return result
