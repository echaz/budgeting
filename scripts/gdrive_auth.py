"""One-time helper to mint a Google Drive OAuth refresh token.

Sign in as the PERSONAL Google account that should own the budgeting
database backups, approve access, then copy the printed refresh token into
.env as GDRIVE_REFRESH_TOKEN.

Run it through the container with the callback port published, e.g.:

    docker compose run --rm -p 8080:8080 \
        -e GDRIVE_CLIENT_ID -e GDRIVE_CLIENT_SECRET \
        web python scripts/gdrive_auth.py --no-browser --host 0.0.0.0 --port 8080

Then open the printed URL in your browser, sign in as your personal
account, and approve. The callback returns to http://localhost:8080.
"""
import argparse
import os
import sys

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/drive.file"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--client-id", default=os.environ.get("GDRIVE_CLIENT_ID", ""))
    parser.add_argument("--client-secret", default=os.environ.get("GDRIVE_CLIENT_SECRET", ""))
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()

    if not args.client_id or not args.client_secret:
        sys.exit("Set --client-id/--client-secret or GDRIVE_CLIENT_ID/GDRIVE_CLIENT_SECRET.")

    client_config = {
        "installed": {
            "client_id": args.client_id,
            "client_secret": args.client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": ["http://localhost"],
        }
    }

    flow = InstalledAppFlow.from_client_config(client_config, scopes=SCOPES)
    creds = flow.run_local_server(
        host=args.host,
        port=args.port,
        open_browser=not args.no_browser,
        prompt="consent",
        access_type="offline",
    )

    if not creds.refresh_token:
        sys.exit("No refresh token returned. Re-run with a fresh consent (prompt=consent).")

    print("\n=== SUCCESS ===")
    print("Add this line to your .env:\n")
    print(f"GDRIVE_REFRESH_TOKEN={creds.refresh_token}")


if __name__ == "__main__":
    main()
