"""Upload the rendered short to YouTube via the Data API v3."""
from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload

log = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


def _credentials() -> Credentials:
    """Token JSON comes from the YT_TOKEN_JSON env var (CI secret) or token.json
    (created locally by `python -m bot.auth`)."""
    raw = os.environ.get("YT_TOKEN_JSON")
    if not raw:
        token_file = Path("token.json")
        if token_file.exists():
            raw = token_file.read_text(encoding="utf-8")
    if not raw:
        raise SystemExit(
            "No YouTube credentials. Run `python -m bot.auth` locally (see SETUP.md "
            "step 2) or set the YT_TOKEN_JSON secret."
        )
    creds = Credentials.from_authorized_user_info(json.loads(raw), SCOPES)
    if not creds.valid:
        creds.refresh(Request())
    return creds


def build_metadata(segment: dict, cfg) -> tuple[str, str]:
    title = f"{segment['emoji']} {segment['title']}"
    if segment["total_parts"] > 1:
        title = f"{title} | Part {segment['part']}"
    if len(title) > 96:
        title = title[:93].rsplit(" ", 1)[0] + "..."
    title += " #shorts"

    description = (
        f"{segment['title']}\n\n"
        f"Story from r/{segment['subreddit']}.\n"
        f"{cfg.upload.description_extra}"
    )
    return title, description


def upload(video_path: Path, segment: dict, cfg) -> str:
    creds = _credentials()
    youtube = build("youtube", "v3", credentials=creds)
    title, description = build_metadata(segment, cfg)

    body = {
        "snippet": {
            "title": title,
            "description": description,
            "tags": list(cfg.upload.tags),
            "categoryId": str(cfg.upload.category_id),
        },
        "status": {
            "privacyStatus": cfg.upload.privacy,
            "selfDeclaredMadeForKids": False,
        },
    }
    media = MediaFileUpload(str(video_path), chunksize=8 * 1024 * 1024, resumable=True)
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)

    response = None
    retries = 0
    while response is None:
        try:
            _, response = request.next_chunk()
        except HttpError as e:
            if e.resp.status in (500, 502, 503, 504) and retries < 5:
                retries += 1
                wait = 2 ** retries
                log.warning("upload chunk failed (%s), retrying in %ss", e.resp.status, wait)
                time.sleep(wait)
            else:
                raise
    video_id = response["id"]
    log.info("uploaded: https://youtube.com/shorts/%s", video_id)
    return video_id
