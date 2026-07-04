"""Compose the final vertical video with a single ffmpeg pass.

Layers: cropped gameplay background -> burned-in karaoke captions -> Reddit
title card overlay (visible while the narrator reads the title) + narration
audio normalized to YouTube loudness.
"""
from __future__ import annotations

import logging
import subprocess
from pathlib import Path

log = logging.getLogger(__name__)


def render(
    cfg,
    bg_clip: Path,
    bg_start: float,
    audio_path: Path,
    ass_path: Path,
    card_path: Path,
    card_until: float,
    out_path: Path,
) -> None:
    v = cfg.video
    from .tts import audio_duration

    total = audio_duration(audio_path) + 0.6  # brief tail so the end isn't abrupt

    filter_complex = (
        # loop guards against a background slice shorter than the narration
        f"[0:v]scale={v.width}:{v.height}:force_original_aspect_ratio=increase,"
        f"crop={v.width}:{v.height},setsar=1,fps={v.fps}[bg];"
        f"[bg]ass={ass_path.name}[sub];"
        f"[2:v]scale={int(v.width * 0.9)}:-1[card];"
        f"[sub][card]overlay=(main_w-overlay_w)/2:{int(v.height * 0.16)}"
        f":enable='lt(t,{card_until:.2f})'[vout]"
    )

    cmd = [
        "ffmpeg", "-y",
        "-stream_loop", "-1", "-ss", f"{bg_start:.2f}", "-t", f"{total + 1:.2f}",
        "-i", str(bg_clip.resolve()),
        "-i", str(audio_path.resolve()),
        "-loop", "1", "-i", str(card_path.resolve()),
        "-filter_complex", filter_complex,
        "-map", "[vout]", "-map", "1:a",
        "-af", "loudnorm=I=-14:TP=-1.5:LRA=11,apad=pad_dur=0.6",
        "-t", f"{total:.2f}",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k", "-ar", "44100",
        "-movflags", "+faststart",
        str(out_path.resolve()),
    ]
    # The ass filter can't handle special chars in paths, so run from its dir
    # and reference it by bare filename.
    log.info("rendering %s", out_path)
    subprocess.run(cmd, check=True, cwd=ass_path.parent)
