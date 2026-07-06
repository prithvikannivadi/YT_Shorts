"""LLM script generation via the Claude API (Anthropic SDK).

The finance and outdoor channels have no human-written scripts, so this module
writes them. Finance scripts are prompted to lead with a concrete number (so the
data-viz background has real stats to animate); outdoor scripts narrate a sourced
clip from its title/description. Both return the {title, hook, narration} shape
the render pipeline expects, via structured outputs so the JSON always parses.
"""
from __future__ import annotations

import json
import logging
import os

import anthropic

log = logging.getLogger(__name__)

# Structured-output schema — guarantees the response is valid JSON in this shape.
_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "hook": {"type": "string"},
        "narration": {"type": "string"},
    },
    "required": ["title", "hook", "narration"],
    "additionalProperties": False,
}

_SYSTEM = {
    "finance": (
        "You write scripts for a faceless finance YouTube Shorts channel that "
        "explains money concepts in a punchy, confident, conversational voice. "
        "Rules: the FIRST sentence of the narration must be a single surprising, "
        "concrete claim built around a specific dollar figure or percentage — that "
        "sentence is also the 'hook'. Include at least two concrete numbers total. "
        "No filler, no 'in this video', no disclaimers beyond a light tone. End on a "
        "one-line takeaway. 'title' is a curiosity-gap YouTube title, <=70 chars, no "
        "clickbait lies. 'hook' is the spoken opener, <=10 words, the shock. "
        "'narration' is the full spoken script and MUST begin with the hook sentence."
    ),
    "outdoor": (
        "You write scripts for a faceless outdoors/wildlife YouTube Shorts channel. "
        "You are given the title and description of a real video clip. Write a vivid, "
        "high-energy narration that hypes what is happening in that clip. Rules: open "
        "on the single most dramatic beat — that opener is the 'hook'. Keep it "
        "concrete and sensory, never generic. Do not invent facts that contradict the "
        "clip's description. 'title' is a curiosity-gap YouTube title, <=70 chars. "
        "'hook' is the spoken opener, <=10 words. 'narration' is the full spoken "
        "script and MUST begin with the hook sentence."
    ),
}


def _client() -> anthropic.Anthropic:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise SystemExit(
            "ANTHROPIC_API_KEY is not set - required to generate finance/outdoor "
            "scripts (see SETUP.md). The Reddit channel does not need it."
        )
    return anthropic.Anthropic()


def generate(cfg, channel_type: str, context: str) -> dict:
    """Generate a script for a channel. `context` is a finance topic string, or
    the outdoor clip's "Title: ...\\nDescription: ..." block. Returns
    {title, hook_text, narration}."""
    system = _SYSTEM.get(channel_type)
    if system is None:
        raise ValueError(f"no script prompt for channel type {channel_type!r}")

    model = (cfg.get("scriptgen") or {}).get("model", "claude-opus-4-8")
    max_words = int(cfg.script.words_per_second * cfg.script.max_seconds)
    user = (
        f"{context}\n\n"
        f"Write the script now. The narration must be at most {max_words} words "
        f"so it fits in a {cfg.script.max_seconds}-second Short."
    )

    client = _client()
    resp = client.messages.create(
        model=model,
        max_tokens=1500,
        system=system,
        output_config={"format": {"type": "json_schema", "schema": _SCHEMA}},
        messages=[{"role": "user", "content": user}],
    )
    if resp.stop_reason == "refusal":
        raise RuntimeError("script generation was refused by the safety classifier")
    text = next(b.text for b in resp.content if b.type == "text")
    data = json.loads(text)
    log.info("generated %s script: %s", channel_type, data["title"][:60])
    return {
        "title": data["title"].strip(),
        "hook_text": data["hook"].strip(),
        "narration": data["narration"].strip(),
    }
