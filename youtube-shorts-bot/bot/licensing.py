"""License filtering + attribution for source footage (outdoor channel).

Only footage the uploader has explicitly licensed for reuse is allowed through.
yt-dlp reports YouTube's license in the ``license`` metadata field as
"Creative Commons Attribution license (reuse allowed)" for CC-BY videos and
None / "Standard YouTube License" for everything else.
"""
from __future__ import annotations

# Substrings that mark footage as reuse-allowed. Public-domain / CC0 clips from
# other extractors surface here too; the default YouTube license does not.
_REUSE_MARKERS = (
    "creative commons",
    "cc-by",
    "cc by",
    "cc0",
    "public domain",
)


def is_reusable(info: dict) -> bool:
    """True only if the video is explicitly licensed for reuse."""
    lic = (info.get("license") or "").strip().lower()
    if not lic:
        return False
    return any(m in lic for m in _REUSE_MARKERS)


def attribution(info: dict) -> dict:
    """Extract the credit fields required by CC-BY (author + link + license)."""
    url = (
        info.get("webpage_url")
        or (f"https://youtu.be/{info['id']}" if info.get("id") else "")
    )
    author = info.get("uploader") or info.get("channel") or info.get("creator") or "unknown"
    return {
        "source_url": url,
        "source_author": author,
        "source_license": info.get("license") or "",
    }
