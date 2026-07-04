"""Persistent state: which posts were already used, and queued multi-part segments.

Stored as a small JSON file that the GitHub Actions workflow commits back to the
repo after each run, so history survives between ephemeral CI runners.
"""
from __future__ import annotations

import json
from pathlib import Path


class State:
    def __init__(self, data_dir: str | Path):
        self.path = Path(data_dir) / "state.json"
        if self.path.exists():
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        else:
            raw = {}
        self.posted_ids: list[str] = raw.get("posted_ids", [])
        self.pending_parts: list[dict] = raw.get("pending_parts", [])

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(
                {
                    "posted_ids": self.posted_ids[-2000:],
                    "pending_parts": self.pending_parts,
                },
                indent=2,
            ),
            encoding="utf-8",
        )

    def pop_pending_part(self) -> dict | None:
        if self.pending_parts:
            return self.pending_parts.pop(0)
        return None

    def queue_parts(self, parts: list[dict]) -> None:
        self.pending_parts.extend(parts)

    def mark_posted(self, post_id: str) -> None:
        if post_id not in self.posted_ids:
            self.posted_ids.append(post_id)
