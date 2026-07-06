"""Finance channel content provider: pick an unused money topic, generate a
script for it, and return a render-ready segment. Background is data-viz, so no
source video or attribution is involved.
"""
from __future__ import annotations

import logging
import re

from . import scriptgen

log = logging.getLogger(__name__)


def _slug(topic: str) -> str:
    return "fin-" + re.sub(r"[^a-z0-9]+", "-", topic.lower()).strip("-")[:50]


def fetch(cfg, state) -> tuple[list[dict], str] | None:
    """Return ([segment], posted_id) for the next unused topic, or None."""
    topics = (cfg.get("finance") or {}).get("topics") or []
    if not topics:
        raise SystemExit(
            "finance channel has no finance.topics configured "
            "(see config.finance.example.yaml)."
        )
    used = set(state.posted_ids)
    emoji = (cfg.get("finance") or {}).get("emoji", "💰")
    cta = (cfg.get("finance") or {}).get("cta", "Follow for more money breakdowns.")

    for topic in topics:
        tid = _slug(topic)
        if tid in used:
            continue
        script = scriptgen.generate(cfg, "finance", f"Money concept: {topic}")
        segment = {
            "id": tid,
            "title": script["title"],
            "hook_text": script["hook_text"],
            "narration": script["narration"],
            "part": 1,
            "total_parts": 1,
            "emoji": emoji,
            "cta": cta,
        }
        return [segment], tid

    log.info("all %d finance topics already used - add more to config", len(topics))
    return None
