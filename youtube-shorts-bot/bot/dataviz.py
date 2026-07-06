"""Generated data-viz background for the finance channel.

Zero copyright risk - every pixel is generated, so there is no source video to
license, no Content ID claim, and no attribution needed. It reads the notable
numbers out of the narration and animates them: a ticking hero figure plus a
growing bar chart over a dark financial gradient, laid out to sit clear of the
centered karaoke captions.
"""
from __future__ import annotations

import logging
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw

from .title_card import _font

log = logging.getLogger(__name__)

BG_TOP = (8, 18, 43)       # deep navy
BG_BOTTOM = (2, 4, 10)     # near black
GRID = (30, 44, 78)
ACCENT = (40, 199, 111)    # money green
ACCENT_DIM = (26, 120, 74)
INK = (236, 242, 255)

_SCALES = {
    "thousand": 1_000, "k": 1_000,
    "million": 1_000_000, "m": 1_000_000, "mn": 1_000_000,
    "billion": 1_000_000_000, "bn": 1_000_000_000, "b": 1_000_000_000,
    "trillion": 1_000_000_000_000, "t": 1_000_000_000_000,
}

# $10 million / 50 thousand / $50,000 / 20% / 4 days-style bare numbers
_STAT = re.compile(
    r"(?P<dollar>\$)?\s?"
    r"(?P<num>\d[\d,]*(?:\.\d+)?)\s?"
    r"(?P<scale>thousand|million|billion|trillion|k|mn|bn|m|b|t)?"
    r"\s?(?P<pct>%|percent)?",
    re.I,
)


@dataclass
class Stat:
    prefix: str      # "$" or ""
    value: float     # the number that ticks up (e.g. 10 for "$10 million")
    suffix: str      # " MILLION", "%", "" ...
    magnitude: float # true size for bar scaling / hero selection
    decimals: int


def _parse(m: re.Match) -> Stat | None:
    num = m.group("num")
    if not num or num in {",", "."}:
        return None
    try:
        value = float(num.replace(",", ""))
    except ValueError:
        return None
    dollar = "$" if m.group("dollar") else ""
    scale_word = (m.group("scale") or "").lower()
    pct = m.group("pct")

    if pct:
        return Stat("", value, "%", value, 1 if "." in num else 0)
    if scale_word:
        factor = _SCALES[scale_word]
        label = {1_000: " K", 1_000_000: " MILLION",
                 1_000_000_000: " BILLION", 1_000_000_000_000: " TRILLION"}[factor]
        return Stat(dollar, value, label, value * factor, 1 if "." in num else 0)
    # plain number - only interesting if it's sizeable or a dollar figure
    if dollar or value >= 100:
        return Stat(dollar, value, "", value, 0)
    return None


def extract_stats(text: str, limit: int = 4) -> list[Stat]:
    stats: list[Stat] = []
    seen: set[str] = set()
    for m in _STAT.finditer(text):
        if not m.group("num"):
            continue
        stat = _parse(m)
        if stat is None:
            continue
        key = f"{stat.prefix}{stat.value}{stat.suffix}"
        if key in seen:
            continue
        seen.add(key)
        stats.append(stat)
        if len(stats) >= limit:
            break
    return stats


def _fmt(stat: Stat, current: float) -> str:
    if stat.decimals:
        body = f"{current:,.{stat.decimals}f}"
    elif stat.value >= 1000:
        body = f"{current:,.0f}"
    else:
        body = f"{current:.0f}"
    return f"{stat.prefix}{body}{stat.suffix}"


def _ease_out(x: float) -> float:
    x = max(0.0, min(1.0, x))
    return 1 - (1 - x) ** 3


def _base_frame(w: int, h: int) -> Image.Image:
    img = Image.new("RGB", (w, h))
    px = img.load()
    for y in range(h):
        t = y / h
        r = int(BG_TOP[0] + (BG_BOTTOM[0] - BG_TOP[0]) * t)
        g = int(BG_TOP[1] + (BG_BOTTOM[1] - BG_TOP[1]) * t)
        b = int(BG_TOP[2] + (BG_BOTTOM[2] - BG_TOP[2]) * t)
        for x in range(w):
            px[x, y] = (r, g, b)
    d = ImageDraw.Draw(img)
    step = 90
    for gx in range(0, w, step):
        d.line([(gx, 0), (gx, h)], fill=GRID, width=1)
    for gy in range(0, h, step):
        d.line([(0, gy), (w, gy)], fill=GRID, width=1)
    return img


def generate(cfg, segment: dict, duration: float, out_path: Path) -> Path:
    """Render the animated data-viz clip to out_path (silent mp4) and return it."""
    v = cfg.video
    w, h = int(v.width), int(v.height)
    fps = int(v.fps)
    total = duration + 1.5
    frames = int(total * fps) + 1

    stats = extract_stats(segment.get("narration", ""))
    if not stats:  # nothing numeric - show one neutral figure so it isn't blank
        stats = [Stat("", 100, "%", 100, 0)]
    hero = max(stats, key=lambda s: s.magnitude)
    # Log-scale the bar heights so stats of wildly different magnitude (e.g.
    # $10M next to 20%) all stay visible instead of the small ones vanishing.
    import math

    def _bar_norm(mag: float) -> float:
        return math.log10(max(mag, 1.0) + 10.0)

    max_norm = max(_bar_norm(s.magnitude) for s in stats) or 1.0

    base = _base_frame(w, h)
    hero_font = _font(True, 150)
    small_font = _font(True, 46)

    # layout: hero number ~66% height, bars along the bottom, all below the
    # centered captions so nothing collides.
    hero_y = int(h * 0.66)
    bar_base = int(h * 0.90)
    bar_top = int(h * 0.74)
    n = len(stats)
    bar_w = int(w * 0.16)
    gap = int((w - n * bar_w) / (n + 1))

    proc = subprocess.Popen(
        [
            "ffmpeg", "-y", "-loglevel", "error",
            "-f", "rawvideo", "-pix_fmt", "rgb24",
            "-s", f"{w}x{h}", "-r", str(fps), "-i", "-",
            "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "22",
            "-pix_fmt", "yuv420p", str(out_path.resolve()),
        ],
        stdin=subprocess.PIPE,
    )
    assert proc.stdin is not None

    for i in range(frames):
        t = i / fps
        frame = base.copy()
        d = ImageDraw.Draw(frame)

        # scanning glow line for subtle motion
        gy = int((t * 140) % h)
        d.line([(0, gy), (w, gy)], fill=ACCENT_DIM, width=2)

        # growing bars (staggered)
        for j, s in enumerate(stats):
            prog = _ease_out((t - 0.35 * j) / 0.8)
            full = (bar_base - bar_top) * (_bar_norm(s.magnitude) / max_norm)
            bh = full * prog
            x0 = gap + j * (bar_w + gap)
            color = ACCENT if s is hero else ACCENT_DIM
            d.rounded_rectangle(
                [x0, bar_base - bh, x0 + bar_w, bar_base], radius=12, fill=color
            )

        # hero ticking number
        cur = hero.value * _ease_out(t / 1.4)
        text = _fmt(hero, cur)
        tw = d.textlength(text, font=hero_font)
        d.text(
            ((w - tw) / 2, hero_y), text, font=hero_font, fill=INK,
            stroke_width=6, stroke_fill=(0, 0, 0),
        )
        # small up-arrow accent above the hero
        ax = w / 2
        ay = hero_y - 70
        d.polygon(
            [(ax - 26, ay + 30), (ax, ay - 10), (ax + 26, ay + 30)], fill=ACCENT
        )

        proc.stdin.write(frame.convert("RGB").tobytes())

    proc.stdin.close()
    if proc.wait() != 0:
        raise RuntimeError("dataviz ffmpeg encode failed")
    log.info("data-viz background generated (%d stats, %.1fs)", len(stats), total)
    return out_path
