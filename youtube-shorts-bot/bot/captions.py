"""Generate word-pop karaoke captions (.ass subtitles) from TTS word timings.

Style mimics viral Shorts: 1-2 uppercase words at a time, big bold centered
text with a heavy outline, a subtle pop-in scale animation, and every Nth
chunk highlighted yellow.
"""
from __future__ import annotations

from pathlib import Path

HEADER = """[Script Info]
ScriptType: v4.00+
PlayResX: {w}
PlayResY: {h}
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Word,{font},{size},&H00FFFFFF,&H00FFFFFF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,10,3,5,60,60,0,1
Style: WordHi,{font},{size},&H0000E5FF,&H0000E5FF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,10,3,5,60,60,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

POP = r"{\fscx70\fscy70\t(0,70,\fscx100\fscy100)}"


def _ts(seconds: float) -> str:
    seconds = max(0.0, seconds)
    h = int(seconds // 3600)
    m = int(seconds % 3600 // 60)
    s = seconds % 60
    return f"{h}:{m:02d}:{s:05.2f}"


def _esc(text: str) -> str:
    return text.replace("\\", "").replace("{", "(").replace("}", ")")


def chunk_words(words: list[dict], per_chunk: int) -> list[dict]:
    """Group word timings into caption chunks, breaking early at punctuation."""
    chunks = []
    cur: list[dict] = []
    for w in words:
        cur.append(w)
        end_of_clause = w["text"].rstrip().endswith((".", ",", "!", "?", ":", ";"))
        if len(cur) >= per_chunk or end_of_clause:
            chunks.append(cur)
            cur = []
    if cur:
        chunks.append(cur)
    return [
        {
            "text": " ".join(w["text"].strip() for w in c),
            "start": c[0]["start"],
            "end": c[-1]["end"],
        }
        for c in chunks
    ]


def write_ass(
    words: list[dict],
    out_path: Path,
    cfg,
    skip_first_words: int = 0,
    audio_end: float | None = None,
) -> None:
    """Write the .ass file. skip_first_words hides the words covered by the
    on-screen title card (the narrator reads the title while the card shows)."""
    v = cfg.video
    visible = words[skip_first_words:]
    chunks = chunk_words(visible, int(v.caption_words_per_chunk))

    lines = [
        HEADER.format(w=v.width, h=v.height, font=v.font, size=v.caption_font_size)
    ]
    hi_every = max(2, int(v.highlight_every))
    for i, c in enumerate(chunks):
        # Hold each chunk until the next one starts so text never flickers off.
        if i + 1 < len(chunks):
            end = chunks[i + 1]["start"]
        else:
            end = audio_end if audio_end is not None else c["end"] + 0.4
        style = "WordHi" if (i + 1) % hi_every == 0 else "Word"
        text = POP + _esc(c["text"].upper())
        lines.append(
            f"Dialogue: 0,{_ts(c['start'])},{_ts(end)},{style},,0,0,0,,{text}\n"
        )
    out_path.write_text("".join(lines), encoding="utf-8")
