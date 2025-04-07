import logging
import os
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ['https://www.googleapis.com/auth/drive']
CREDENTIALS_PATH = 'credentials.json'
TOKEN_PATH = 'token.json'
REDIRECT_URI = 'urn:ietf:wg:oauth:2.0:oob'  # Define redirect URI here

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def check_token_exists():
    """Checks if token.json exists."""
    return os.path.exists(TOKEN_PATH)


def generate_authorization_url():
    """Generates the Google Drive authorization URL."""
    flow = InstalledAppFlow.from_client_secrets_file(
        CREDENTIALS_PATH, SCOPES, redirect_uri=REDIRECT_URI)
    try:
        authorization_url, state = flow.authorization_url(prompt='consent')
        return authorization_url
    except Exception as e:
        logger.exception(f"Error generating authorization URL: {e}")
        return None


def exchange_code_for_tokens(code):
    """Exchanges the authorization code for access and refresh tokens and saves them."""
    flow = InstalledAppFlow.from_client_secrets_file(
        CREDENTIALS_PATH, SCOPES, redirect_uri=REDIRECT_URI)
    try:
        flow.fetch_token(code=code)
        creds = flow.credentials
        if creds and creds.valid:
            with open(TOKEN_PATH, 'w') as token:
                token.write(creds.to_json())
            return True  # Success
        else:
            return False  # Failed to get valid credentials
    except Exception as e:
        logger.exception(f"Error exchanging authorization code for tokens: {e}")
        return False  # Exchange failed


def authenticate_google_drive():
    """Authenticates with Google Drive API using existing tokens if available."""
    creds = None
    if os.path.exists(TOKEN_PATH):
        creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception as e:
                logger.exception(f"Error refreshing credentials: {e}")
                os.remove(TOKEN_PATH)  # Remove invalid token
                return None  # Indicate authentication failure, force re-auth
        else:
            return None  # No valid credentials available, force authorization flow

    try:
        service = build('drive', 'v3', credentials=creds)
        return service
    except HttpError as error:
        logger.exception(f'An error occurred: {error}')
        return None


def create_folder_if_not_exists(drive_service, folder_path):
    """Creates folders in Google Drive if they don't exist.
    Handles nested folders as well.
    Returns the ID of the last folder created (or existing folder).
    """
    parent_folder_id = 'root'  # Start at the root of Drive
    folders = folder_path.strip('/').split('/')  # Split path into folder names

    for folder_name in folders:
        folder_id = find_folder_id(drive_service, folder_name, parent_folder_id)
        if not folder_id:
            folder_id = create_folder(drive_service, folder_name, parent_folder_id)
        parent_folder_id = folder_id  # Next folder will be inside this one
    return parent_folder_id  # Return the ID of the final folder


def find_folder_id(drive_service, folder_name, parent_id):
    """Finds a folder ID by name within a parent folder."""
    try:
        results = drive_service.files().list(
            q=f"mimeType='application/vnd.google-apps.folder' and name='{folder_name}' and '{parent_id}' in parents and trashed=false",
            fields="files(id)"
        ).execute()
        items = results.get('files', [])
        if items:
            return items[0]['id']  # Return the ID of the first matching folder
        else:
            return None  # Folder not found
    except HttpError as error:
        logger.exception(f'An error occurred: {error}')
        return None


def create_folder(drive_service, folder_name, parent_id):
    """Creates a folder in Google Drive."""
    file_metadata = {
        'name': folder_name,
        'mimeType': 'application/vnd.google-apps.folder',
        'parents': [parent_id]
    }
    try:
        file = drive_service.files().create(body=file_metadata,
                                            fields='id').execute()
        return file.get('id')
    except HttpError as error:
        logger.exception(f'An error occurred: {error}')
        return None


def find_file_id(drive_service, file_name, folder_id):
    """Finds a file ID by name within a parent folder."""
    try:
        results = drive_service.files().list(
            q=f"name='{file_name}' and '{folder_id}' in parents and trashed=false",
            fields="files(id)"
        ).execute()
        items = results.get('files', [])
        if items:
            return items[0]['id']  # Return the ID of the first matching file
        else:
            return None  # File not found
    except HttpError as error:
        logger.exception(f'An error occurred while finding file: {error}')
        return None


def delete_file_by_id(drive_service, file_id):
    """Deletes a file in Google Drive by its file ID."""
    try:
        drive_service.files().delete(fileId=file_id).execute()
        return True  # Deletion successful
    except HttpError as error:
        logger.exception(f'An error occurred during file deletion: {error}')
        return False  # Deletion failed


def upload_file_to_drive(drive_service, file_path, folder_id, overwrite=True):
    """Uploads a file to Google Drive in the specified folder.

    Args:
        drive_service: The Google Drive service instance.
        file_path: Path to the file to upload.
        folder_id: ID of the folder to upload to.
        overwrite: If True, overwrites existing file with the same name. If False, keeps both files.

    Returns:
        The webViewLink (shareable link) of the uploaded file, or None if upload failed.
    """
    file_name = os.path.basename(file_path)

    # Check if file with same name exists and delete it if overwrite is True
    if overwrite:
        existing_file_id = find_file_id(drive_service, file_name, folder_id)
        if existing_file_id:
            logger.info(f"Found existing file '{file_name}' with ID {existing_file_id}. Deleting it before upload.")
            delete_success = delete_file_by_id(drive_service, existing_file_id)
            if not delete_success:
                logger.warning(f"Failed to delete existing file '{file_name}'. Proceeding with upload anyway.")

    # Upload the file
    media = MediaFileUpload(file_path, resumable=True)  # Detect mimetype automatically
    file_metadata = {
        'name': file_name,
        'parents': [folder_id]
    }
    try:
        file = drive_service.files().create(body=file_metadata,
                                            media_body=media,
                                            fields='id,webViewLink').execute()
        logger.info(f"File '{file_name}' uploaded successfully. File ID: {file.get('id')}")
        return file.get('webViewLink')  # Return the webViewLink (shareable link)
    except HttpError as error:
        logger.exception(f'An error occurred during file upload: {error}')
        return None


def get_folder_id_by_path(drive_service, folder_path):
    """Gets the ID of a folder given its full path.
    Returns None if the folder path does not exist.
    """
    parent_folder_id = 'root'  # Start at the root of Drive
    folders = folder_path.strip('/').split('/')
    current_folder_id = parent_folder_id

    for folder_name in folders:
        folder_id = find_folder_id(drive_service, folder_name, current_folder_id)
        if folder_id:
            current_folder_id = folder_id
        else:
            return None  # Folder path not found
    return current_folder_id  # Return the ID of the final folder in the path


def delete_folder_by_id(drive_service, folder_id):
    """Deletes a folder in Google Drive by its folder ID."""
    try:
        drive_service.files().delete(fileId=folder_id).execute()
        return True  # Deletion successful
    except HttpError as error:
        logger.exception(f'An error occurred during folder deletion: {error}')
        return False  # Deletion failed


def delete_folder_by_path(drive_service, folder_path):
    """Deletes a folder in Google Drive given its full path."""
    folder_id = get_folder_id_by_path(drive_service, folder_path)
    if folder_id:
        return delete_folder_by_id(drive_service, folder_id)  # Delete by ID if found
    else:
        logger.error(f"Folder path '{folder_path}' not found, cannot delete.")
        return False  # Folder path not found, cannot delete
