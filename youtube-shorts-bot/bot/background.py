"""Background gameplay library: download copyright-free clips once, slice at random.

Sources come from config (background.sources) - they must be videos whose
uploader explicitly grants reuse (see SETUP.md). If the library is empty, a
procedurally generated animated-gradient clip is created so the pipeline
still produces a video.
"""
from __future__ import annotations

import json
import logging
import random
import subprocess
from pathlib import Path

log = logging.getLogger(__name__)

FALLBACK_NAME = "_fallback_gradient.mp4"


def _run(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True)


def video_duration(path: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "json", str(path)],
        capture_output=True, text=True, check=True,
    )
    return float(json.loads(out.stdout)["format"]["duration"])


def ensure_library(cfg) -> Path:
    """Download any missing sources; return the library directory."""
    lib = Path(cfg.paths.assets) / "backgrounds"
    lib.mkdir(parents=True, exist_ok=True)
    for url in cfg.background.sources or []:
        try:
            _run([
                "yt-dlp",
                "--no-playlist",
                "-f", "bv*[height>=1080][ext=mp4]/bv*[ext=mp4]/bv*",
                "--remux-video", "mp4",
                "-o", str(lib / "%(id)s.%(ext)s"),
                "--download-archive", str(lib / "archive.txt"),
                url,
            ])
        except subprocess.CalledProcessError as e:
            log.warning("background download failed for %s: %s", url, e)
    return lib


def _ensure_fallback(lib: Path) -> Path:
    fb = lib / FALLBACK_NAME
    if not fb.exists():
        log.warning(
            "background library is empty - generating gradient fallback. "
            "Add copyright-free gameplay URLs to config.yaml (background.sources)."
        )
        _run([
            "ffmpeg", "-y", "-f", "lavfi",
            "-i", "gradients=size=1080x1920:speed=0.03:nb_colors=5:duration=180:rate=30",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
            "-pix_fmt", "yuv420p", str(fb),
        ])
    return fb


def pick_clip(cfg, duration_needed: float) -> tuple[Path, float]:
    """Pick a random library file and random start offset covering the duration."""
    lib = Path(cfg.paths.assets) / "backgrounds"
    lib.mkdir(parents=True, exist_ok=True)
    clips = [p for p in lib.glob("*.mp4") if p.name != FALLBACK_NAME]
    if not clips:
        clips = [_ensure_fallback(lib)]
    random.shuffle(clips)
    for clip in clips:
        try:
            total = video_duration(clip)
        except subprocess.CalledProcessError:
            continue
        margin = total - duration_needed - 2.0
        if margin <= 0:
            continue
        start = random.uniform(1.0, 1.0 + margin)
        return clip, start
    # Nothing long enough - loop the fallback from the top.
    return _ensure_fallback(lib), 0.0
