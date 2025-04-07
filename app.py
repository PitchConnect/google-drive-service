import logging
import os

from flask import Flask, request, jsonify

from google_drive_utils import authenticate_google_drive, create_folder_if_not_exists, upload_file_to_drive, \
    generate_authorization_url, exchange_code_for_tokens, check_token_exists, delete_folder_by_path

app = Flask(__name__)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)



@app.route('/authorize_gdrive', methods=['GET'])
def authorize_gdrive_endpoint():
    """Endpoint to get the Google Drive authorization URL."""
    authorization_url = generate_authorization_url()
    if authorization_url:
        return jsonify({'authorization_url': authorization_url}), 200
    else:
        return jsonify({'error': 'Failed to generate authorization URL'}), 500


@app.route('/submit_auth_code', methods=['POST'])
def submit_auth_code_endpoint():
    """Endpoint to submit the authorization code and obtain tokens."""
    code = request.form.get('code')  # Get authorization code from form data
    if not code:
        return jsonify({'error': 'Authorization code is required'}), 400

    success = exchange_code_for_tokens(code)
    if success:
        return jsonify({'status': 'authorization_successful'}), 200
    else:
        return jsonify({'error': 'Failed to exchange authorization code for tokens'}), 500


@app.route('/upload_file', methods=['POST'])
def upload_file_endpoint():
    """Endpoint to upload a file to Google Drive.

    Optional form parameters:
    - overwrite: Set to 'false' to keep both files if a file with the same name exists.
                Default is 'true' (overwrite existing files).
    """

    if not check_token_exists():
        return jsonify(
            {'error': 'Authorization required. Please visit /authorize_gdrive first and then /submit_auth_code.'}), 401

    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    file = request.files['file']
    folder_path = request.form.get('folder_path')

    # Get overwrite parameter (default is True)
    overwrite_param = request.form.get('overwrite', 'true').lower()
    overwrite = overwrite_param != 'false'  # Only 'false' will disable overwriting

    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    if not folder_path:
        return jsonify({'error': 'Folder path is required'}), 400

    if file:
        try:
            drive_service = authenticate_google_drive()  # Now this should just load tokens
            if not drive_service:
                return jsonify(
                    {'error': 'Google Drive authentication failed (tokens invalid or missing). Re-authorize.'}), 500

            folder_id = create_folder_if_not_exists(drive_service, folder_path)
            if not folder_id:
                return jsonify({'error': 'Failed to create folder'}), 500

            temp_file_path = os.path.join('/tmp', file.filename)
            file.save(temp_file_path)

            file_url = upload_file_to_drive(drive_service, temp_file_path, folder_id, overwrite=overwrite)
            os.remove(temp_file_path)

            if file_url:
                return jsonify({
                    'status': 'success',
                    'file_url': file_url,
                    'overwrite_mode': 'enabled' if overwrite else 'disabled'
                }), 200
            else:
                return jsonify({'error': 'File upload failed to Google Drive'}), 500

        except Exception as e:
            logger.exception(f"Error during file upload: {e}")
            return jsonify({'error': f'Internal server error: {str(e)}'}), 500

    return jsonify({'error': 'Unknown error'}), 500


@app.route('/delete_folder', methods=['POST'])
def delete_folder_endpoint():
    """Endpoint to delete a folder in Google Drive by path."""
    folder_path = request.form.get('folder_path')  # Get folder path from form data

    if not folder_path:
        return jsonify({'error': 'Folder path is required'}), 400

    try:
        drive_service = authenticate_google_drive()
        if not drive_service:
            return jsonify({'error': 'Google Drive authentication failed'}), 500

        if delete_folder_by_path(drive_service, folder_path):
            return jsonify({'status': 'success', 'message': f'Folder "{folder_path}" deleted successfully'}), 200
        else:
            return jsonify(
                {'status': 'error', 'message': f'Failed to delete folder "{folder_path}" or folder not found'}), 500

    except Exception as e:
        logger.exception(f"Error during folder deletion: {e}")
        return jsonify({'error': f'Internal server error during folder deletion: {str(e)}'}), 500


@app.route('/health')
def health_check():
    # Check if Google Drive API is accessible
    try:
        drive_service = authenticate_google_drive()
        if drive_service:
            return jsonify({"status": "healthy"}), 200
        else:
            return jsonify({"status": "degraded", "reason": "auth_required"}), 200
    except Exception as e:
        return jsonify({"status": "unhealthy", "reason": str(e)}), 500


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')
