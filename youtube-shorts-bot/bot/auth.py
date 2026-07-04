"""One-time local OAuth flow for YouTube uploads.

Run this ON YOUR OWN COMPUTER (it opens a browser):

    pip install google-auth-oauthlib
    python -m bot.auth

Requires client_secret.json in the current directory (SETUP.md step 2).
Writes token.json - paste its contents into the YT_TOKEN_JSON GitHub secret.
"""
from __future__ import annotations

from pathlib import Path

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


def main() -> None:
    secrets = Path("client_secret.json")
    if not secrets.exists():
        raise SystemExit(
            "client_secret.json not found. Download it from your Google Cloud "
            "project's OAuth credentials page (SETUP.md step 2) and place it here."
        )
    flow = InstalledAppFlow.from_client_secrets_file(str(secrets), SCOPES)
    creds = flow.run_local_server(port=8080, prompt="consent")
    Path("token.json").write_text(creds.to_json(), encoding="utf-8")
    print("\n✅ Wrote token.json")
    print("Now add its ENTIRE contents as a GitHub Actions secret named YT_TOKEN_JSON:")
    print("  repo → Settings → Secrets and variables → Actions → New repository secret")
    print("\nKeep token.json private - it can upload to your channel. Do NOT commit it.")


if __name__ == "__main__":
    main()
