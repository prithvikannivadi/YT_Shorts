"""Curiosity-gap hook engine.

The single biggest lever on Shorts 'stayed to watch' is the first ~2 seconds.
This module produces two things:

  1. an on-screen hook line burned onto the opening frames (big, bold, high
     contrast so it reads over any footage), and
  2. a spoken opener so the payoff lands in sentence one, before any setup.

Channels get the best results by supplying a purpose-written ``hook_text`` on
the segment (their script generator knows the payoff). If none is given, a hook
is derived heuristically from the title as a fallback.
"""
from __future__ import annotations

import re

from PIL import Image, ImageDraw

from .title_card import _font, _wrap_px

# Openers that bury the hook - strip them so sentence one starts on the payoff.
_FILLER = re.compile(
    r"^(so|well|ok|okay|um|uh|like|basically|honestly|look|now|yeah|anyway)\b[\s,]*",
    re.I,
)


def make_hook(title: str, hook_text: str | None, cfg) -> str:
    """Return the on-screen hook line (punchy, trimmed, curiosity-gap intact)."""
    raw = (hook_text or title or "").strip()
    # Peel filler openers repeatedly ("so basically, ..." -> "...").
    prev = None
    while prev != raw:
        prev = raw
        raw = _FILLER.sub("", raw).strip()

    max_words = int(cfg.hook.max_words)
    words = raw.split()
    truncated = len(words) > max_words
    line = " ".join(words[:max_words]).strip()
    # A hook should leave a loop open - avoid ending on a hard stop.
    line = line.rstrip(".")
    if truncated and not line.endswith(("?", "!", "…")):
        line += "…"
    return line


def spoken_opener(hook_line: str) -> str:
    """The spoken version of the hook (normal casing, reads as a clean opener)."""
    line = hook_line.rstrip("…").strip()
    if not line.endswith(("?", "!", ".")):
        line += "."
    return line


def ensure_opens_with(narration: str, spoken: str) -> str:
    """Guarantee the narration's first words ARE the spoken hook, so the caption
    skip and overlay timing line up (mirrors how Reddit speaks its title first).
    """
    narration = narration.strip()
    head = spoken.rstrip(".!?").lower()
    if narration.lower().startswith(head):
        return narration
    return f"{spoken} {narration}".strip()


def render_hook(text: str, out_path, cfg) -> None:
    """Render a full-frame transparent PNG with the hook line, ready to overlay
    at (0,0). White text with a heavy black stroke + drop shadow stays legible
    over gameplay, gradients, or original source footage alike."""
    v = cfg.video
    w, h = int(v.width), int(v.height)
    size = int(cfg.hook.font_size)
    font = _font(True, size)

    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    lines = _wrap_px(text.upper(), font, int(w * 0.86))
    line_h = int(size * 1.14)
    total_h = line_h * len(lines)
    y = int(h * 0.30) - total_h // 2
    stroke = max(6, size // 11)

    for line in lines:
        tw = d.textlength(line, font=font)
        x = (w - tw) / 2
        # soft drop shadow for extra separation from bright footage
        d.text((x + 4, y + 6), line, font=font, fill=(0, 0, 0, 130))
        d.text(
            (x, y), line, font=font, fill=(255, 255, 255, 255),
            stroke_width=stroke, stroke_fill=(0, 0, 0, 255),
        )
        y += line_h

    img.save(out_path)
