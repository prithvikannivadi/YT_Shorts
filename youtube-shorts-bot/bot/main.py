"""Pipeline entry point.

    python -m bot.main run                 # fetch -> render -> upload one short
    python -m bot.main run --no-upload     # render only (video left in output/)
    python -m bot.main fetch-backgrounds   # (re)download the background library
"""
from __future__ import annotations

import argparse
import logging
import random
import re
import sys
import tempfile
from pathlib import Path

from . import background, captions, render, script, state, title_card, tts
from .config import load_config

log = logging.getLogger("bot")


def _slug(segment: dict) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", segment["title"].lower()).strip("-")[:50]
    return f"{segment['post_id']}-p{segment['part']}-{base}"


def cmd_run(args: argparse.Namespace) -> int:
    cfg = load_config(args.config)
    st = state.State(cfg.paths.data)

    # Queued part from an earlier multi-part story takes priority.
    segment = st.pop_pending_part()
    if segment is None:
        from .reddit_fetcher import fetch_best_post

        post = fetch_best_post(cfg, st.posted_ids)
        if post is None:
            log.info("no eligible story found today - nothing to do")
            st.save()
            return 0
        segments = script.build_segments(post, cfg)
        voice = random.choice(list(cfg.tts.voices))
        for s in segments:
            s["voice"] = voice
        segment = segments[0]
        st.queue_parts(segments[1:])
        st.mark_posted(post["id"])

    log.info(
        "story: r/%s '%s' (part %d/%d)",
        segment["subreddit"], segment["title"][:60],
        segment["part"], segment["total_parts"],
    )

    out_dir = Path(cfg.paths.output)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{_slug(segment)}.mp4"

    with tempfile.TemporaryDirectory() as td:
        work = Path(td)

        # 1. Narration + word timings
        audio_path = work / "narration.mp3"
        words, duration = tts.synthesize(
            segment["narration"], segment["voice"], cfg.tts.rate, audio_path
        )
        min_s, max_s = cfg.script.min_seconds, cfg.script.max_seconds
        if duration < min_s:
            log.warning("narration only %.1fs (< %ds min) - posting anyway", duration, min_s)
        if duration > max_s + 5:
            log.warning("narration %.1fs overshot the %ds budget", duration, max_s)

        # 2. Captions (skip the words shown on the title card)
        n_title_words = len(segment["spoken_title"].split())
        card_until = (
            words[n_title_words - 1]["end"] + 0.15
            if n_title_words <= len(words) else 3.0
        )
        ass_path = work / "captions.ass"
        captions.write_ass(
            words, ass_path, cfg, skip_first_words=n_title_words, audio_end=duration
        )

        # 3. Title card overlay
        card_path = work / "card.png"
        title_card.render_title_card(segment, card_path)

        # 4. Background slice + final render
        background.ensure_library(cfg)
        bg_clip, bg_start = background.pick_clip(cfg, duration + 1.5)
        render.render(
            cfg, bg_clip, bg_start, audio_path, ass_path, card_path,
            card_until, out_path,
        )

    log.info("rendered %s (%.1fs)", out_path, duration)

    if cfg.upload.enabled and not args.no_upload:
        from .uploader import upload

        video_id = upload(out_path, segment, cfg)
        log.info("live at https://youtube.com/shorts/%s", video_id)
    else:
        log.info("upload skipped - video saved to %s", out_path)

    st.save()
    return 0


def cmd_fetch_backgrounds(args: argparse.Namespace) -> int:
    cfg = load_config(args.config)
    lib = background.ensure_library(cfg)
    clips = list(lib.glob("*.mp4"))
    log.info("background library: %d clip(s) in %s", len(clips), lib)
    if not clips:
        log.warning("library is empty - add URLs to config.yaml background.sources")
    return 0


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    parser = argparse.ArgumentParser(prog="bot")
    parser.add_argument("--config", default="config.yaml")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_run = sub.add_parser("run", help="produce and post one short")
    p_run.add_argument("--no-upload", action="store_true")
    p_run.set_defaults(func=cmd_run)

    p_bg = sub.add_parser("fetch-backgrounds", help="download background library")
    p_bg.set_defaults(func=cmd_fetch_backgrounds)

    args = parser.parse_args()
    sys.exit(args.func(args))


if __name__ == "__main__":
    main()
