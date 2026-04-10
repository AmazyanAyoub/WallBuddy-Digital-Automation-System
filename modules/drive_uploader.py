import os
import logging

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
import pickle

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from config import GOOGLE_DRIVE_FOLDER_ID

SCOPES = ["https://www.googleapis.com/auth/drive"]
TOKEN_FILE = "token.pickle"
CLIENT_SECRET_FILE = "credentials.json"


def _build_service():
    creds = None

    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, "rb") as f:
            creds = pickle.load(f)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRET_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_FILE, "wb") as f:
            pickle.dump(creds, f)

    return build("drive", "v3", credentials=creds)


def upload_zip(zip_path: str) -> str:
    set_name  = os.path.splitext(os.path.basename(zip_path))[0]
    file_name = os.path.basename(zip_path)

    logging.info(f"[{set_name}] Uploading {file_name} to Google Drive...")

    service = _build_service()

    file_metadata = {
        "name"   : file_name,
        "parents": [GOOGLE_DRIVE_FOLDER_ID],
    }
    media = MediaFileUpload(zip_path, mimetype="application/zip", resumable=True)

    uploaded = service.files().create(
        body=file_metadata,
        media_body=media,
        fields="id, name",
    ).execute()

    file_id = uploaded["id"]

    service.permissions().create(
        fileId=file_id,
        body={"type": "anyone", "role": "reader"},
    ).execute()

    public_url = f"https://drive.google.com/file/d/{file_id}/view?usp=sharing"
    logging.info(f"[{set_name}] Public URL: {public_url}")
    return public_url