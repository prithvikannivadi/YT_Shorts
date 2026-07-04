"""Narrate text with Microsoft Edge TTS (free) and capture word-level timings.

edge-tts streams WordBoundary events alongside the audio, which gives us exact
per-word timestamps for the karaoke-style captions - no forced alignment needed.
"""
from __future__ import annotations

import asyncio
import json
import subprocess
from pathlib import Path

import edge_tts


async def _synth(text: str, voice: str, rate: str, out_path: Path) -> list[dict]:
    # boundary="WordBoundary" is required on edge-tts >= 7 (default became sentences)
    communicate = edge_tts.Communicate(text, voice, rate=rate, boundary="WordBoundary")
    words: list[dict] = []
    with open(out_path, "wb") as f:
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                f.write(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                # offsets/durations are in 100-nanosecond ticks
                start = chunk["offset"] / 1e7
                words.append(
                    {
                        "text": chunk["text"],
                        "start": start,
                        "end": start + chunk["duration"] / 1e7,
                    }
                )
    return words


def audio_duration(path: Path) -> float:
    out = subprocess.run(
        [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "json", str(path),
        ],
        capture_output=True, text=True, check=True,
    )
    return float(json.loads(out.stdout)["format"]["duration"])


def _attach_punctuation(words: list[dict], source_text: str) -> list[dict]:
    """Edge TTS strips punctuation from WordBoundary text; recover it from the
    source so captions can break at clause ends. Only applied when the token
    streams line up 1:1, otherwise timings are returned untouched."""
    tokens = source_text.split()
    if len(tokens) != len(words):
        return words
    for w, tok in zip(words, tokens):
        if tok.lstrip('("\'').startswith(w["text"][:2]):
            w["text"] = tok
    return words


def synthesize(text: str, voice: str, rate: str, out_path: Path) -> tuple[list[dict], float]:
    """Returns (word timings, audio duration in seconds)."""
    words = asyncio.run(_synth(text, voice, rate, out_path))
    if not words:
        raise RuntimeError("edge-tts returned no word boundaries (empty text?)")
    return _attach_punctuation(words, text), audio_duration(out_path)
