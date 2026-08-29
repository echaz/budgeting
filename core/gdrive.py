import json

try:
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload, MediaInMemoryUpload
    _IMPORT_ERROR = None
except ImportError as exc:  # pragma: no cover
    _IMPORT_ERROR = exc

MANIFEST_NAME = "manifest.json"
SLOT_NAMES = {"a": "budget-slot-a.sql.gz", "b": "budget-slot-b.sql.gz"}
FOLDER_NAME = "budgeting-backups"
FOLDER_MIME = "application/vnd.google-apps.folder"
SCOPES = ["https://www.googleapis.com/auth/drive.file"]
TOKEN_URI = "https://oauth2.googleapis.com/token"


class DriveConfigError(Exception):
    pass


class DriveBackupStore:
    """Double-buffered backup store on Google Drive.

    Two slot files plus a manifest pointer live in one Drive folder. A push
    writes to the inactive slot, verifies it, then flips the manifest, so a
    failed upload can never clobber the last good copy.
    """

    def __init__(self, client_id, client_secret, refresh_token, folder_id=""):
        if _IMPORT_ERROR is not None:
            raise DriveConfigError(f"Google API libraries not installed: {_IMPORT_ERROR}")

        missing = [
            name for name, value in (
                ("GDRIVE_CLIENT_ID", client_id),
                ("GDRIVE_CLIENT_SECRET", client_secret),
                ("GDRIVE_REFRESH_TOKEN", refresh_token),
            )
            if not value
        ]
        if missing:
            raise DriveConfigError(
                "Missing Google Drive settings: " + ", ".join(missing)
                + ". See .env.example and scripts/gdrive_auth.py."
            )

        self._folder_id = folder_id or ""
        creds = Credentials(
            token=None,
            refresh_token=refresh_token,
            client_id=client_id,
            client_secret=client_secret,
            token_uri=TOKEN_URI,
            scopes=SCOPES,
        )
        self._service = build("drive", "v3", credentials=creds, cache_discovery=False)

    def ensure_folder(self):
        if not self._folder_id:
            folder = self._service.files().create(
                body={"name": FOLDER_NAME, "mimeType": FOLDER_MIME}, fields="id"
            ).execute()
            self._folder_id = folder["id"]
        return self._folder_id

    def _find(self, name):
        query = f"name = '{name}' and '{self._folder_id}' in parents and trashed = false"
        response = self._service.files().list(
            q=query, spaces="drive", fields="files(id, name)"
        ).execute()
        files = response.get("files", [])
        return files[0]["id"] if files else None

    def read_manifest(self):
        if not self._folder_id:
            return {}
        file_id = self._find(MANIFEST_NAME)
        if not file_id:
            return {}
        data = self._service.files().get_media(fileId=file_id).execute()
        try:
            return json.loads(data.decode("utf-8"))
        except (ValueError, AttributeError):
            return {}

    def write_manifest(self, manifest):
        content = json.dumps(manifest, indent=2, sort_keys=True).encode("utf-8")
        media = MediaInMemoryUpload(content, mimetype="application/json", resumable=False)
        file_id = self._find(MANIFEST_NAME)
        if file_id:
            self._service.files().update(fileId=file_id, media_body=media).execute()
        else:
            self._service.files().create(
                body={"name": MANIFEST_NAME, "parents": [self._folder_id]},
                media_body=media,
                fields="id",
            ).execute()

    def upload_to_slot(self, slot, local_path):
        name = SLOT_NAMES[slot]
        media = MediaFileUpload(local_path, mimetype="application/gzip", resumable=True)
        fields = "id, md5Checksum, size"
        file_id = self._find(name)
        if file_id:
            return self._service.files().update(
                fileId=file_id, media_body=media, fields=fields
            ).execute()
        return self._service.files().create(
            body={"name": name, "parents": [self._folder_id]},
            media_body=media,
            fields=fields,
        ).execute()
