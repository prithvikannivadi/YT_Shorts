"""Stories channel content provider: generate an ORIGINAL drama story with the
Claude API (no Reddit dependency) and return a render-ready segment.

Replaces the Reddit fetcher: Reddit's Responsible Builder Policy gates new API
apps behind manual approval, and original AI-authored stories are also stronger
for monetization than reposted content.
"""
from __future__ import annotations

import logging
import random
import re

from . import scriptgen

log = logging.getLogger(__name__)


def _slug(title: str) -> str:
    return "story-" + re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:50]


def fetch(cfg, state) -> tuple[list[dict], str] | None:
    """Generate one original story. Returns ([segment], posted_id)."""
    story_cfg = cfg.get("story") or {}
    themes = story_cfg.get("themes") or []
    if not themes:
        raise SystemExit("stories channel has no story.themes configured (see config.yaml).")

    theme = random.choice(themes)
    recent = ", ".join(state.posted_ids[-10:]) or "none"
    context = (
        f"Story theme: {theme}\n"
        f"Recently used story slugs (avoid similar premises): {recent}"
    )

    for _ in range(3):  # retry if the premise collides with a recent one
        script = scriptgen.generate(cfg, "story", context)
        sid = _slug(script["title"])
        if sid not in state.posted_ids:
            break
    else:
        log.warning("could not generate a fresh story premise after 3 tries")
        return None

    segment = {
        "id": sid,
        "title": script["title"],
        # card style: the spoken title is read while the story card shows
        "spoken_title": script["hook_text"],
        "card_name": story_cfg.get("card_name", "STORYTIME"),
        "narration": _ensure_opener(script["narration"], script["hook_text"]),
        "part": 1,
        "total_parts": 1,
        "emoji": story_cfg.get("emoji", "🍿"),
        "cta": story_cfg.get("cta", "Follow for a new story every day."),
    }
    return [segment], sid


def _ensure_opener(narration: str, hook: str) -> str:
    """The card holds while the hook is spoken, so narration must start with it."""
    n, h = narration.strip(), hook.strip().rstrip(".!?").lower()
    if n.lower().startswith(h):
        return n
    opener = hook.strip()
    if not opener.endswith((".", "!", "?")):
        opener += "."
    return f"{opener} {n}"
