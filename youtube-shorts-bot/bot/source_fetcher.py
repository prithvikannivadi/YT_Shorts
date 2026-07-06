"""Find and download reuse-licensed source footage for the outdoor channel.

Searches YouTube for the channel's topics, keeps ONLY videos whose uploader
licensed them for reuse (Creative Commons / public domain - see licensing.py),
downloads one unused clip, and returns a source dict carrying the video path
plus the attribution fields needed for the description.

Turning that clip into narration + a hook is the channel's own script step; this
module deliberately stops at "sourced a clip we're allowed to use, with credit".
"""
from __future__ import annotations

import logging
from pathlib import Path

import yt_dlp

from . import licensing

log = logging.getLogger(__name__)


def _ydl_opts(assets_dir: Path, quiet: bool = True) -> dict:
    return {
        "quiet": quiet,
        "no_warnings": quiet,
        "noplaylist": True,
        "format": "bv*[height>=1080][ext=mp4]/bv*[ext=mp4]/bv*",
        "outtmpl": str(assets_dir / "%(id)s.%(ext)s"),
        "merge_output_format": "mp4",
    }


def find_reusable(cfg, used_ids: list[str], per_query: int = 8) -> dict | None:
    """Return metadata (not yet downloaded) for the first reuse-licensed video
    across the channel's search queries that hasn't been used before."""
    queries = (cfg.get("source") or {}).get("queries") or []
    if not queries:
        raise SystemExit(
            "outdoor channel has no source.queries configured - add search "
            "terms (see config.outdoor.example.yaml)."
        )
    min_dur = int((cfg.get("source") or {}).get("min_duration", 30))
    max_dur = int((cfg.get("source") or {}).get("max_duration", 1200))

    # Flat search first (cheap), then a full extract per candidate to read license.
    flat = {"quiet": True, "no_warnings": True, "extract_flat": "in_playlist",
            "noplaylist": True}
    with yt_dlp.YoutubeDL(flat) as ydl:
        candidates: list[str] = []
        for q in queries:
            try:
                res = ydl.extract_info(f"ytsearch{per_query}:{q}", download=False)
            except Exception as e:  # a bad query shouldn't kill the run
                log.warning("search failed for %r: %s", q, e)
                continue
            for entry in res.get("entries") or []:
                vid = entry.get("id")
                if vid and vid not in used_ids and vid not in candidates:
                    candidates.append(vid)

    with yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True}) as ydl:
        for vid in candidates:
            try:
                info = ydl.extract_info(f"https://youtu.be/{vid}", download=False)
            except Exception as e:
                log.warning("metadata fetch failed for %s: %s", vid, e)
                continue
            if not licensing.is_reusable(info):
                continue
            dur = info.get("duration") or 0
            if not (min_dur <= dur <= max_dur):
                continue
            log.info("reuse-licensed clip: %s by %s (%s)",
                     vid, info.get("uploader"), info.get("license"))
            return info

    log.info("no reuse-licensed clip found across %d candidates", len(candidates))
    return None


def fetch_source(cfg, used_ids: list[str]) -> dict | None:
    """Download one reuse-licensed clip and return a source dict:
    {id, title, description, background_source, source_url, source_author,
     source_license}. Returns None if nothing eligible was found."""
    info = find_reusable(cfg, used_ids)
    if info is None:
        return None

    assets = Path(cfg.paths.assets) / "source_clips"
    assets.mkdir(parents=True, exist_ok=True)
    with yt_dlp.YoutubeDL(_ydl_opts(assets)) as ydl:
        info = ydl.extract_info(info["webpage_url"], download=True)
        path = Path(ydl.prepare_filename(info)).with_suffix(".mp4")

    src = {
        "id": info["id"],
        "title": info.get("title", "").strip(),
        "description": info.get("description", "") or "",
        "background_source": str(path),
        **licensing.attribution(info),
    }
    return src
