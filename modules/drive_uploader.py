import os
import logging
import pickle
import threading

from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from config import GOOGLE_DRIVE_FOLDER_ID

SCOPES             = ["https://www.googleapis.com/auth/drive"]
TOKEN_FILE         = "token.pickle"
CLIENT_SECRET_FILE = "credentials.json"

_service_lock = threading.Lock()


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
            creds = flow.run_local_server(port=0, prompt="select_account")
        with open(TOKEN_FILE, "wb") as f:
            pickle.dump(creds, f)
    return build("drive", "v3", credentials=creds)


def upload_zip(zip_path: str, atca_name: str) -> str:
    """
    Uploads the ZIP directly into GOOGLE_DRIVE_FOLDER_ID.
    Returns a direct download link — customer clicks and ZIP downloads immediately.
    """
    zip_filename = os.path.basename(zip_path)
    with _service_lock:
        service = _build_service()

    file_meta = {
        "name"   : zip_filename,
        "parents": [GOOGLE_DRIVE_FOLDER_ID],
    }
    media = MediaFileUpload(zip_path, mimetype="application/zip", resumable=True)
    uploaded = service.files().create(body=file_meta, media_body=media, fields="id").execute()
    file_id  = uploaded["id"]
    logging.info(f"[{atca_name}] ZIP uploaded: {zip_filename}")

    service.permissions().create(
        fileId=file_id,
        body={"type": "anyone", "role": "reader"},
    ).execute()

    download_url = f"https://drive.google.com/uc?export=download&id={file_id}"
    logging.info(f"[{atca_name}] Download URL: {download_url}")
    return download_url
