"""Standalone script to perform the Google OAuth flow for EV.

Run this once to authorize EV to read Gmail + Calendar.
It reads EV_GOOGLE_CREDENTIALS_PATH from .env and saves a token next to it.
"""

from pathlib import Path

from dotenv import load_dotenv
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/calendar.readonly",
]


def main():
    import os

    creds_path = Path(os.environ["EV_GOOGLE_CREDENTIALS_PATH"])
    token_path = creds_path.parent / "token.json"

    creds = None
    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print("Refreshing existing token...")
            creds.refresh(Request())
        else:
            print(f"Starting browser OAuth flow using credentials: {creds_path}")
            flow = InstalledAppFlow.from_client_secrets_file(str(creds_path), SCOPES)
            creds = flow.run_local_server(port=0)
        token_path.write_text(creds.to_json(), encoding="utf-8")
        print(f"Saved token to {token_path}")
    else:
        print(f"Token already valid at {token_path}")

    print("OAuth setup complete. You can now run EV Google ingestion.")


if __name__ == "__main__":
    main()
