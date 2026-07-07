"""Render the fake Reddit post card (Pillow PNG) shown while the title is read."""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

FONT_DIRS = [
    "/usr/share/fonts/truetype/dejavu",
    "/usr/share/fonts/TTF",
    "/System/Library/Fonts",
    "C:/Windows/Fonts",
]


def _font(bold: bool, size: int) -> ImageFont.FreeTypeFont:
    name = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
    for d in FONT_DIRS:
        p = Path(d) / name
        if p.exists():
            return ImageFont.truetype(str(p), size)
    return ImageFont.load_default(size)


def _wrap_px(text: str, font: ImageFont.FreeTypeFont, max_w: int) -> list[str]:
    """Wrap by measured pixel width, not character count."""
    d = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    lines: list[str] = []
    cur = ""
    for w in text.split():
        cand = f"{cur} {w}".strip()
        if not cur or d.textlength(cand, font=font) <= max_w:
            cur = cand
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    if len(lines) > 6:
        lines = lines[:6]
        lines[-1] += "..."
    return lines


def _fmt_count(n: int) -> str:
    if n >= 1000:
        return f"{n / 1000:.1f}k".replace(".0k", "k")
    return str(n)


def render_title_card(segment: dict, out_path: Path, width: int = 960) -> None:
    """Reddit-sourced segments (with 'subreddit') get the classic post card with
    real stats. Original AI stories get a clean 'storytime' card - no platform
    branding and no fabricated engagement numbers."""
    pad = 44
    title_font = _font(True, 52)
    meta_font = _font(True, 40)
    small_font = _font(False, 36)

    is_reddit = bool(segment.get("subreddit"))

    title = segment["title"]
    if segment.get("part", 1) > 1:
        title = f"{title} (Part {segment['part']})"
    lines = _wrap_px(title, title_font, width - 2 * pad)
    line_h = 66
    header_h = 110
    footer_h = 96 if is_reddit else 20
    height = pad * 2 + header_h + len(lines) * line_h + footer_h

    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    # Card body
    d.rounded_rectangle([0, 0, width - 1, height - 1], radius=36, fill=(255, 255, 255, 245))

    # Header: avatar + source name
    cx, cy, r = pad + 34, pad + 34, 34
    if is_reddit:
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(255, 69, 0, 255))
        d.text((cx, cy), "r/", font=_font(True, 34), fill="white", anchor="mm")
        d.text((pad + 90, cy), f"r/{segment['subreddit']}", font=meta_font,
               fill=(20, 20, 20, 255), anchor="lm")
        d.text((pad + 90, cy + 42), f"u/{segment['author']}", font=small_font,
               fill=(130, 130, 130, 255), anchor="lm")
    else:
        name = segment.get("card_name", "STORYTIME")
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(255, 69, 0, 255))
        d.text((cx, cy), name[:1], font=_font(True, 34), fill="white", anchor="mm")
        d.text((pad + 90, cy), name, font=meta_font, fill=(20, 20, 20, 255), anchor="lm")
        d.text((pad + 90, cy + 42), "today's story", font=small_font,
               fill=(130, 130, 130, 255), anchor="lm")

    # Title
    y = pad + header_h
    for line in lines:
        d.text((pad, y), line, font=title_font, fill=(10, 10, 10, 255))
        y += line_h

    # Footer: engagement stats (reddit only - real numbers, never fabricated)
    if is_reddit:
        y += 18
        ax = pad + 20
        d.polygon(
            [(ax, y + 26), (ax + 22, y), (ax + 44, y + 26), (ax + 30, y + 26),
             (ax + 30, y + 44), (ax + 14, y + 44), (ax + 14, y + 26)],
            fill=(255, 69, 0, 255),
        )
        score_txt = _fmt_count(segment["score"])
        d.text((ax + 62, y + 22), score_txt, font=meta_font, fill=(60, 60, 60, 255), anchor="lm")

        # speech-bubble icon (DejaVu has no emoji glyphs)
        bx = ax + 62 + int(d.textlength(score_txt, font=meta_font)) + 56
        d.rounded_rectangle([bx, y, bx + 46, y + 36], radius=12, fill=(130, 130, 130, 255))
        d.polygon([(bx + 10, y + 34), (bx + 24, y + 34), (bx + 12, y + 46)],
                  fill=(130, 130, 130, 255))
        d.text((bx + 62, y + 22), _fmt_count(segment["num_comments"]), font=meta_font,
               fill=(60, 60, 60, 255), anchor="lm")

    img.save(out_path)
