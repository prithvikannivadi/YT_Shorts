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

from . import background, captions, hook, render, script, state, title_card, tts
from .config import load_config

log = logging.getLogger("bot")


def _slug(segment: dict) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", segment["title"].lower()).strip("-")[:50]
    ident = segment.get("post_id") or segment.get("id") or "item"
    return f"{ident}-p{segment.get('part', 1)}-{base}"


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

    # Hook style: "card" (Reddit title card is the hook) or "overlay" (a
    # curiosity-gap text hook, used by the outdoor & finance channels).
    hook_cfg = cfg.get("hook") or {}
    style = hook_cfg.get("style", "card")

    # The opener is spoken FIRST and shown on-screen; captions skip those words
    # while the overlay holds. This unifies Reddit's card and the hook overlay.
    if style == "overlay":
        hook_line = hook.make_hook(segment["title"], segment.get("hook_text"), cfg)
        spoken = hook.spoken_opener(hook_line)
        segment["narration"] = hook.ensure_opens_with(segment["narration"], spoken)
    else:
        spoken = segment["spoken_title"]

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

        # 2. Opening overlay + how long it holds (until the spoken hook ends)
        n_open = len(spoken.split())
        overlay_until = (
            words[n_open - 1]["end"] + 0.2 if n_open <= len(words) else 3.0
        )
        if style == "overlay":
            overlay_until = max(overlay_until, float(hook_cfg.get("hold_seconds", 2.6)))
            overlay_path = work / "hook.png"
            hook.render_hook(hook_line, overlay_path, cfg)
            overlay_fullframe, overlay_y = True, 0.30
        else:
            overlay_path = work / "card.png"
            title_card.render_title_card(segment, overlay_path)
            overlay_fullframe, overlay_y = False, 0.16

        # 3. Captions (skip the words shown on the opening overlay)
        ass_path = work / "captions.ass"
        captions.write_ass(
            words, ass_path, cfg, skip_first_words=n_open, audio_end=duration
        )

        # 4. Channel-aware background + final render. Reddit -> gameplay library;
        #    outdoor/finance -> the content's own original source video.
        bg_clip, bg_start = background.pick_background(cfg, segment, duration + 1.5)
        render.render(
            cfg, bg_clip, bg_start, audio_path, ass_path, out_path,
            overlay_path=overlay_path, overlay_until=overlay_until,
            overlay_fullframe=overlay_fullframe, overlay_y_frac=overlay_y,
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
