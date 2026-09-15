"""Shared Google OAuth2 helper for Gmail + Calendar ingestion."""

from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from ev.config import Settings, get_settings
from ev.security.boundary import assert_personal_only

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/calendar.readonly",
]


class GoogleAuthError(Exception):
    """Raised when Google OAuth setup is missing or invalid."""


def _credentials_path(config: Settings) -> Path | None:
    return config.google_credentials_path


def _token_path(credentials_path: Path) -> Path:
    return credentials_path.parent / "token.json"


def _load_or_create_credentials(credentials_path: Path):
    token_path = _token_path(credentials_path)
    creds = None
    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(str(credentials_path), SCOPES)
            creds = flow.run_local_server(port=0)
        token_path.write_text(creds.to_json(), encoding="utf-8")
    return creds


class GoogleAuthHelper:
    """Creates authorized Gmail/Calendar service objects for the EV user."""

    def __init__(self, config: Settings | None = None):
        self.config = config or get_settings()
        assert_personal_only(self.config)
        if not self.config.google_enabled:
            raise GoogleAuthError("Google integration is disabled (EV_GOOGLE_ENABLED=false)")
        path = _credentials_path(self.config)
        if not path or not Path(path).exists():
            raise GoogleAuthError(
                "Google OAuth credentials not found. "
                "Set EV_GOOGLE_CREDENTIALS_PATH to a downloaded credentials.json."
            )
        self.credentials_path = Path(path)

    def get_service(self, api_name: str, version: str):
        creds = _load_or_create_credentials(self.credentials_path)
        return build(api_name, version, credentials=creds, static_discovery=False)
