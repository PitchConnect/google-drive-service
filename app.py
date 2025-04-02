from flask import Flask, request, jsonify, make_response, redirect
import os
from google_drive_utils import authenticate_google_drive, create_folder_if_not_exists, upload_file_to_drive, generate_authorization_url, exchange_code_for_tokens, check_token_exists

app = Flask(__name__)

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
    code = request.form.get('code') # Get authorization code from form data
    if not code:
        return jsonify({'error': 'Authorization code is required'}), 400

    success = exchange_code_for_tokens(code)
    if success:
        return jsonify({'status': 'authorization_successful'}), 200
    else:
        return jsonify({'error': 'Failed to exchange authorization code for tokens'}), 500


@app.route('/upload_file', methods=['POST'])
def upload_file_endpoint():
    """Endpoint to upload a file to Google Drive."""

    if not check_token_exists():
        return jsonify({'error': 'Authorization required. Please visit /authorize_gdrive first and then /submit_auth_code.'}), 401

    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    file = request.files['file']
    folder_path = request.form.get('folder_path')

    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    if not folder_path:
        return jsonify({'error': 'Folder path is required'}), 400

    if file:
        try:
            drive_service = authenticate_google_drive() # Now this should just load tokens
            if not drive_service:
                return jsonify({'error': 'Google Drive authentication failed (tokens invalid or missing). Re-authorize.'}), 500

            folder_id = create_folder_if_not_exists(drive_service, folder_path)
            if not folder_id:
                return jsonify({'error': 'Failed to create folder'}), 500

            temp_file_path = os.path.join('/tmp', file.filename)
            file.save(temp_file_path)

            file_url = upload_file_to_drive(drive_service, temp_file_path, folder_id)
            os.remove(temp_file_path)

            if file_url:
                return jsonify({'status': 'success', 'file_url': file_url}), 200
            else:
                return jsonify({'error': 'File upload failed to Google Drive'}), 500

        except Exception as e:
            print(f"Error during file upload: {e}")
            return jsonify({'error': f'Internal server error: {str(e)}'}), 500

    return jsonify({'error': 'Unknown error'}), 500


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')