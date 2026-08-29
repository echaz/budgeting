"""One-time setup: authenticate to Google Drive and write the GDRIVE_*
credentials into .env. This file is gitignored -- do not commit it.

Run it on the docker host (not inside the container):

    cd ~/projects/budgeting && source .venv/bin/activate
    pip install google-auth-oauthlib google-api-python-client
    python scripts/setup_gdrive.py

You are prompted for the OAuth client id/secret (Google Cloud Console ->
Desktop app) unless they are already in the environment. Your browser
opens for you to sign in as your PERSONAL Google account and approve. On
success it writes GDRIVE_CLIENT_ID, GDRIVE_CLIENT_SECRET,
GDRIVE_REFRESH_TOKEN and GDRIVE_FOLDER_ID into .env (creating the backup
folder if needed).
"""
import getpass
import os
import sys
from pathlib import Path

from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/drive.file"]
DEFAULT_ENV = Path(__file__).resolve().parent.parent / ".env"
ENV_PATH = Path(os.environ.get("ENV_FILE", str(DEFAULT_ENV)))
FOLDER_NAME = "budgeting-backups"
FOLDER_MIME = "application/vnd.google-apps.folder"


def ask(name, current, secret=False):
    if current:
        return current
    value = getpass.getpass(f"{name}: ") if secret else input(f"{name}: ")
    return value.strip()


def update_env(path, updates):
    lines = path.read_text().splitlines() if path.exists() else []
    seen = set()
    out = []
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            key = stripped.split("=", 1)[0].strip()
            if key in updates:
                out.append(f"{key}={updates[key]}")
                seen.add(key)
                continue
        out.append(line)
    for key, value in updates.items():
        if key not in seen:
            out.append(f"{key}={value}")
    path.write_text("\n".join(out) + "\n")


def main():
    client_id = ask("GDRIVE_CLIENT_ID", os.environ.get("GDRIVE_CLIENT_ID", ""))
    client_secret = ask(
        "GDRIVE_CLIENT_SECRET", os.environ.get("GDRIVE_CLIENT_SECRET", ""), secret=True
    )
    if not client_id or not client_secret:
        sys.exit("client id and secret are required.")

    client_config = {
        "installed": {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": ["http://localhost"],
        }
    }

    flow = InstalledAppFlow.from_client_config(client_config, scopes=SCOPES)
    print("\nA browser window will open. Sign in as your PERSONAL account and approve.")
    creds = flow.run_local_server(
        port=0,
        open_browser=True,
        prompt="consent",
        access_type="offline",
    )
    if not creds.refresh_token:
        sys.exit("No refresh token returned; re-run to force a fresh consent.")

    # Persist the credentials first so a later failure (e.g. Drive API not yet
    # enabled) can never throw away the freshly minted refresh token.
    update_env(ENV_PATH, {
        "GDRIVE_CLIENT_ID": client_id,
        "GDRIVE_CLIENT_SECRET": client_secret,
        "GDRIVE_REFRESH_TOKEN": creds.refresh_token,
    })

    folder_id = os.environ.get("GDRIVE_FOLDER_ID", "").strip()
    if not folder_id:
        service = build("drive", "v3", credentials=creds, cache_discovery=False)
        folder = service.files().create(
            body={"name": FOLDER_NAME, "mimeType": FOLDER_MIME}, fields="id"
        ).execute()
        folder_id = folder["id"]

    update_env(ENV_PATH, {"GDRIVE_FOLDER_ID": folder_id})

    print("\n=== SUCCESS ===")
    print(f"Wrote GDRIVE_* credentials to {ENV_PATH}")
    print(f"Backup folder id: {folder_id}")
    print("Now run: docker compose run --rm web python manage.py backup_push")


if __name__ == "__main__":
    main()
