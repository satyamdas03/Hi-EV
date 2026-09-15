"""Interactive helper to authorize EV against Google Gmail + Calendar.

Prerequisites:
1. Create OAuth 2.0 credentials in Google Cloud Console for a "Desktop app".
2. Enable the Gmail API and Google Calendar API.
3. Download the JSON and save it to the path you will set as EV_GOOGLE_CREDENTIALS_PATH.
4. Set EV_GOOGLE_ENABLED=true and EV_PERSONAL_ONLY=true in your .env.
5. Run: python scripts/setup_google_oauth.py

This performs the browser OAuth flow once and caches the token next to the
credentials file. After that, EV can run read-only Gmail/Calendar ingestion.
"""

import asyncio

from ev.config import get_settings
from ev.google_auth import GoogleAuthError, GoogleAuthHelper


async def main():
    settings = get_settings()
    if not settings.personal_only:
        print("Refusing to run: EV_PERSONAL_ONLY must be true.")
        return 1
    if not settings.google_enabled:
        print("Google integration is disabled. Set EV_GOOGLE_ENABLED=true in .env.")
        return 1
    try:
        helper = GoogleAuthHelper(settings)
        # Trigger the auth flow for both APIs and verify we can build services.
        gmail = helper.get_service("gmail", "v1")
        calendar = helper.get_service("calendar", "v3")
        profile = gmail.users().getProfile(userId="me").execute()
        print(f"Authorized for Gmail account: {profile.get('emailAddress')}")
        cal_list = calendar.calendarList().list().execute()
        print(f"Accessible calendars: {len(cal_list.get('items', []))}")
        print("OAuth token cached. EV can now ingest Gmail + Calendar read-only.")
        return 0
    except GoogleAuthError as exc:
        print(f"Setup failed: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
