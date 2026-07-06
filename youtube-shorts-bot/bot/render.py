"""Compose the final vertical video with a single ffmpeg pass.

Layers: background (gameplay for Reddit, or the original source video for the
outdoor/finance channels) -> burned-in karaoke captions -> one optional opening
overlay (the Reddit title card, or a curiosity-gap hook) + narration audio
normalized to YouTube loudness. The background's own audio is never mapped, so
the voiceover is always the only sound.
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
    out_path: Path,
    overlay_path: Path | None = None,
    overlay_until: float = 0.0,
    overlay_fullframe: bool = False,
    overlay_y_frac: float = 0.16,
) -> None:
    v = cfg.video
    from .tts import audio_duration

    total = audio_duration(audio_path) + 0.6  # brief tail so the end isn't abrupt

    # base: fit background to frame, then burn captions
    chain = (
        f"[0:v]scale={v.width}:{v.height}:force_original_aspect_ratio=increase,"
        f"crop={v.width}:{v.height},setsar=1,fps={v.fps}[bg];"
        f"[bg]ass={ass_path.name}[vcap]"
    )

    inputs = [
        "-stream_loop", "-1", "-ss", f"{bg_start:.2f}", "-t", f"{total + 1:.2f}",
        "-i", str(bg_clip.resolve()),
        "-i", str(audio_path.resolve()),
    ]
    final = "[vcap]"

    if overlay_path is not None:
        inputs += ["-loop", "1", "-i", str(Path(overlay_path).resolve())]
        if overlay_fullframe:
            # hook PNG is already frame-sized with text positioned; place at 0,0
            chain += (
                f";[vcap][2:v]overlay=0:0"
                f":enable='lt(t,{overlay_until:.2f})'[vout]"
            )
        else:
            # card PNG is a narrower graphic; scale to 90% width and center it
            chain += (
                f";[2:v]scale={int(v.width * 0.9)}:-1[ov];"
                f"[vcap][ov]overlay=(main_w-overlay_w)/2:{int(v.height * overlay_y_frac)}"
                f":enable='lt(t,{overlay_until:.2f})'[vout]"
            )
        final = "[vout]"

    cmd = [
        "ffmpeg", "-y", *inputs,
        "-filter_complex", chain,
        "-map", final, "-map", "1:a",
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
