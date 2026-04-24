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
    1. Creates a folder named atca_name inside GOOGLE_DRIVE_FOLDER_ID
    2. Uploads the ZIP into that folder
    3. Shares the folder (anyone with link can view)
    4. Returns the folder URL — customer opens their own folder and downloads the ZIP
    """
    zip_filename = os.path.basename(zip_path)
    with _service_lock:
        service = _build_service()

    # ── 1. Create customer folder ─────────────────────────────
    folder_meta = {
        "name"    : atca_name,
        "mimeType": "application/vnd.google-apps.folder",
        "parents" : [GOOGLE_DRIVE_FOLDER_ID],
    }
    folder    = service.files().create(body=folder_meta, fields="id").execute()
    folder_id = folder["id"]
    logging.info(f"[{atca_name}] Drive folder created: {folder_id}")

    # ── 2. Upload ZIP into that folder ────────────────────────
    file_meta = {
        "name"   : zip_filename,
        "parents": [folder_id],
    }
    media = MediaFileUpload(zip_path, mimetype="application/zip", resumable=True)
    service.files().create(body=file_meta, media_body=media, fields="id").execute()
    logging.info(f"[{atca_name}] ZIP uploaded: {zip_filename}")

    # ── 3. Share the folder ───────────────────────────────────
    service.permissions().create(
        fileId=folder_id,
        body={"type": "anyone", "role": "reader"},
    ).execute()

    folder_url = f"https://drive.google.com/drive/folders/{folder_id}?usp=sharing"
    logging.info(f"[{atca_name}] Folder URL: {folder_url}")
    return folder_url
