# -*- coding: utf-8 -*-
"""Utilities to download images from Google Drive folders using a service account.

Environment variables used:
- GDRIVE_SERVICE_ACCOUNT_JSON: path to service account JSON file
- GDRIVE_DNI_FOLDER_ID: Drive folder ID for DNI images
- GDRIVE_LAB_FOLDER_ID: Drive folder ID for LAB images
- GDRIVE_DB_FOLDER_ID: Drive folder ID for ALDIMI_DB (optional)

Notes:
- This module is optional: if credentials are missing, functions raise a clear error
  and calling code should fallback to local folders.
"""
from pathlib import Path
import os
import io
from typing import List
import json

try:
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaIoBaseDownload
except Exception:
    # If packages are missing, we'll raise at runtime when trying to use Drive.
    service_account = None
    build = None
    MediaIoBaseDownload = None

SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]


def _get_drive_service():
    json_path = os.environ.get("GDRIVE_SERVICE_ACCOUNT_JSON")
    if not json_path:
        raise RuntimeError("GDRIVE_SERVICE_ACCOUNT_JSON not set; provide service account JSON path.")
    if service_account is None or build is None:
        raise RuntimeError("google-auth / google-api-python-client not installed. Add them to requirements.")
    creds = service_account.Credentials.from_service_account_file(json_path, scopes=SCOPES)
    service = build("drive", "v3", credentials=creds, cache_discovery=False)
    return service


def list_files_in_folder(folder_id: str, mime_types: List[str] = None) -> List[dict]:
    """Return list of file metadata in the folder. mime_types optional filter (list of mime substrings)."""
    svc = _get_drive_service()
    q = f"'{folder_id}' in parents and trashed = false"
    files = []
    page_token = None
    while True:
        resp = svc.files().list(q=q, fields="nextPageToken, files(id, name, mimeType)", pageToken=page_token).execute()
        for f in resp.get("files", []):
            if mime_types:
                if any(mt in f.get("mimeType", "") for mt in mime_types):
                    files.append(f)
            else:
                files.append(f)
        page_token = resp.get("nextPageToken")
        if not page_token:
            break
    return files


def download_file(file_id: str, dest_path: Path):
    svc = _get_drive_service()
    request = svc.files().get_media(fileId=file_id)
    fh = io.FileIO(dest_path, 'wb')
    downloader = MediaIoBaseDownload(fh, request)
    done = False
    while not done:
        status, done = downloader.next_chunk()
    fh.close()
    return dest_path


def download_folder_images(folder_id: str, dest_dir: Path, max_files: int = 0) -> List[Path]:
    dest_dir.mkdir(parents=True, exist_ok=True)
    files = list_files_in_folder(folder_id, mime_types=["image", "application/octet-stream", "image/png", "image/jpeg", "image/jpg"])
    paths = []
    for i, f in enumerate(files):
        if max_files and i >= max_files:
            break
        name = f.get("name")
        fid = f.get("id")
        # sanitize name
        safe_name = name.replace('/', '_').replace('\\', '_')
        target = dest_dir / safe_name
        try:
            download_file(fid, target)
            paths.append(target)
        except Exception as e:
            # skip failed downloads but continue
            continue
    return paths


def get_json_from_drive(folder_id: str, filename: str):
    """Download and parse a JSON file stored inside the given Drive folder.
    Returns parsed JSON or None if file not found.
    """
    svc = _get_drive_service()
    q = f"'{folder_id}' in parents and name='{filename}' and trashed = false"
    resp = svc.files().list(q=q, fields="files(id, name)").execute()
    files = resp.get("files", [])
    if not files:
        return None
    file_id = files[0]["id"]
    fh = io.BytesIO()
    downloader = MediaIoBaseDownload(fh, svc.files().get_media(fileId=file_id))
    done = False
    while not done:
        _, done = downloader.next_chunk()
    fh.seek(0)
    try:
        return json.loads(fh.read().decode("utf-8"))
    except Exception:
        return None


def upload_json_to_drive(folder_id: str, filename: str, data) -> dict:
    """Upload or update a JSON file into the specified Drive folder.
    Returns created/updated file metadata.
    """
    svc = _get_drive_service()
    json_bytes = json.dumps(data, indent=2, ensure_ascii=False).encode("utf-8")
    fh = io.BytesIO(json_bytes)
    try:
        from googleapiclient.http import MediaIoBaseUpload
    except Exception:
        raise RuntimeError("googleapiclient.http.MediaIoBaseUpload not available")

    media = MediaIoBaseUpload(fh, mimetype="application/json", resumable=True)

    q = f"'{folder_id}' in parents and name='{filename}' and trashed = false"
    resp = svc.files().list(q=q, fields="files(id, name)").execute()
    files = resp.get("files", [])
    if files:
        file_id = files[0]["id"]
        updated = svc.files().update(fileId=file_id, media_body=media).execute()
        return updated
    else:
        metadata = {"name": filename, "parents": [folder_id]}
        created = svc.files().create(body=metadata, media_body=media, fields="id").execute()
        return created
