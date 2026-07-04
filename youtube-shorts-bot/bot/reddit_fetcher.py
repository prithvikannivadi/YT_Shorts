"""Fetch the best unposted story from the configured subreddits via the Reddit API."""
from __future__ import annotations

import logging
import os

import praw

log = logging.getLogger(__name__)


def _client(cfg) -> praw.Reddit:
    client_id = os.environ.get("REDDIT_CLIENT_ID")
    client_secret = os.environ.get("REDDIT_CLIENT_SECRET")
    if not client_id or not client_secret:
        raise SystemExit(
            "REDDIT_CLIENT_ID / REDDIT_CLIENT_SECRET are not set. "
            "See SETUP.md step 1 to create a free Reddit API app."
        )
    return praw.Reddit(
        client_id=client_id,
        client_secret=client_secret,
        user_agent=cfg.reddit.user_agent,
    )


def _top_comments(post, limit: int, max_chars: int) -> list[str]:
    post.comment_sort = "top"
    post.comments.replace_more(limit=0)
    out = []
    for c in post.comments:
        if getattr(c, "stickied", False) or not getattr(c, "body", None):
            continue
        body = c.body.strip()
        if body in ("[deleted]", "[removed]") or len(body) < 15 or len(body) > max_chars:
            continue
        if body.startswith(("http://", "https://")):
            continue
        out.append(body)
        if len(out) >= limit:
            break
    return out


def fetch_best_post(cfg, posted_ids: list[str]) -> dict | None:
    """Return the highest-scoring eligible post across all configured subreddits."""
    reddit = _client(cfg)
    r = cfg.reddit
    best: dict | None = None

    for sub_cfg in r.subreddits:
        sub = reddit.subreddit(sub_cfg["name"])
        mode = sub_cfg.get("mode", "selftext")
        try:
            posts = list(sub.top(time_filter=r.time_filter, limit=r.posts_per_subreddit))
        except Exception as e:  # one bad subreddit shouldn't kill the run
            log.warning("failed to fetch r/%s: %s", sub_cfg["name"], e)
            continue

        for post in posts:
            if post.stickied or post.id in posted_ids:
                continue
            if r.skip_nsfw and post.over_18:
                continue
            if post.score < r.min_score:
                continue

            if mode == "selftext":
                body = (post.selftext or "").strip()
                if body in ("", "[deleted]", "[removed]"):
                    continue
                if len(body.split()) < r.min_words:
                    continue
                comments: list[str] = []
            else:  # comments mode (AskReddit-style)
                body = ""
                comments = _top_comments(post, r.comments_per_post, r.comment_max_chars)
                if len(comments) < 3:
                    continue

            if best is None or post.score > best["score"]:
                best = {
                    "id": post.id,
                    "subreddit": sub_cfg["name"],
                    "mode": mode,
                    "emoji": sub_cfg.get("emoji", "🍿"),
                    "cta": sub_cfg.get("cta", "Follow for more."),
                    "title": post.title.strip(),
                    "body": body,
                    "comments": comments,
                    "author": str(post.author) if post.author else "unknown",
                    "score": post.score,
                    "num_comments": post.num_comments,
                }

    return best
