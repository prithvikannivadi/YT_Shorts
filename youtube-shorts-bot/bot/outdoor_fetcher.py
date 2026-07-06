"""Outdoor channel content provider: source one reuse-licensed clip, generate a
narration about it, and return a render-ready segment carrying the clip as the
background plus the creator attribution.
"""
from __future__ import annotations

import logging

from . import scriptgen, source_fetcher

log = logging.getLogger(__name__)


def fetch(cfg, state) -> tuple[list[dict], str] | None:
    """Return ([segment], posted_id), or None if no eligible clip was found."""
    src = source_fetcher.fetch_source(cfg, state.posted_ids)
    if src is None:
        return None

    desc = (src.get("description") or "")[:1500]
    context = f"Title: {src['title']}\nDescription: {desc}"
    script = scriptgen.generate(cfg, "outdoor", context)

    emoji = (cfg.get("outdoor") or {}).get("emoji", "🌲")
    cta = (cfg.get("outdoor") or {}).get("cta", "Follow for more wild moments.")
    segment = {
        "id": src["id"],
        "title": script["title"],
        "hook_text": script["hook_text"],
        "narration": script["narration"],
        "background_source": src["background_source"],
        "source_url": src["source_url"],
        "source_author": src["source_author"],
        "source_license": src["source_license"],
        "part": 1,
        "total_parts": 1,
        "emoji": emoji,
        "cta": cta,
    }
    return [segment], src["id"]
