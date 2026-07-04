"""Turn a Reddit post into narration segments sized for Shorts.

Cleans Reddit markdown, expands subreddit jargon, softens profanity (for
monetization safety), and splits long stories into multiple parts that get
posted on later runs.
"""
from __future__ import annotations

import re

# Spoken expansions so the narration doesn't read acronyms letter by letter.
JARGON = {
    r"\bAITA\b": "Am I the jerk",
    r"\bWIBTA\b": "Would I be the jerk",
    r"\bYTA\b": "you're the jerk",
    r"\bNTA\b": "not the jerk",
    r"\bTIFU\b": "Today I messed up",
    r"\bTL;?DR:?\b": "Long story short:",
    r"\bOP\b": "the poster",
    r"\bSO\b(?=\s)": "partner",
    r"\bDH\b": "husband",
    r"\bDW\b": "wife",
    r"\bMIL\b": "mother in law",
    r"\bFIL\b": "father in law",
    r"\bBIL\b": "brother in law",
    r"\bSIL\b": "sister in law",
    r"\bIMO\b": "in my opinion",
    r"\bIIRC\b": "if I remember right",
    r"\bAFAIK\b": "as far as I know",
    r"\bIDK\b": "I don't know",
    r"\bTBH\b": "to be honest",
    r"\bBTW\b": "by the way",
    r"\bETA:?\b": "Edit:",
}

# Softened replacements for words that hurt monetization. Case-insensitive.
PROFANITY = {
    "fucking": "freaking",
    "fucked": "screwed",
    "fucker": "jerk",
    "fuck": "screw",
    "motherfucker": "jerk",
    "shitty": "crappy",
    "shit": "crap",
    "bullshit": "nonsense",
    "asshole": "a-hole",
    "bitch": "witch",
    "bastard": "jerk",
    "dick": "jerk",
    "cunt": "jerk",
    "whore": "cheater",
    "slut": "cheater",
}

# "(28F)" / "28M" -> "28 female" / "28 male", and "(F28)" -> "28 female"
_AGE_THEN_GENDER = re.compile(r"\(?\b([1-9][0-9]?)\s*([MmFf])\b\)?")
_GENDER_THEN_AGE = re.compile(r"\(?\b([MmFf])\s*([1-9][0-9]?)\b\)?")


def _spoken_age_gender(text: str) -> str:
    def word(g: str) -> str:
        return "male" if g.upper() == "M" else "female"

    text = _AGE_THEN_GENDER.sub(lambda m: f"{m.group(1)} {word(m.group(2))}", text)
    text = _GENDER_THEN_AGE.sub(lambda m: f"{m.group(2)} {word(m.group(1))}", text)
    return text


def clean_text(text: str) -> str:
    """Strip Reddit markdown and boilerplate; normalize for narration."""
    t = text
    t = re.sub(r"https?://\S+", "", t)
    t = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", t)  # markdown links -> label
    t = re.sub(r"[*_~^#>|`]", "", t)  # markdown symbols
    t = re.sub(r"&amp;", "and", t)
    t = re.sub(r"&\w+;", " ", t)
    t = re.sub(r"\br/(\w+)", r"r slash \1", t)
    t = re.sub(r"\bu/(\w+)", r"\1", t)
    # Drop trailing edit blocks - they ramble and kill retention.
    t = re.sub(r"(?:\n+|(?<=[.!?])\s+)(edit|update)\s*\d*\s*[:\-].*$", "", t, flags=re.I | re.S)
    t = _spoken_age_gender(t)
    for pat, rep in JARGON.items():
        t = re.sub(pat, rep, t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def soften(text: str) -> str:
    def repl(m: re.Match) -> str:
        w = m.group(0)
        rep = PROFANITY[w.lower()]
        return rep.capitalize() if w[0].isupper() else rep

    pat = re.compile(
        r"\b(" + "|".join(sorted(PROFANITY, key=len, reverse=True)) + r")\b", re.I
    )
    return pat.sub(repl, text)


def _sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+", text)
    return [p.strip() for p in parts if p.strip()]


def build_segments(post: dict, cfg) -> list[dict]:
    """Build 1..max_parts narration segments from a post.

    Each segment dict is self-contained (JSON-serializable) so later parts can
    be queued in state and rendered on future runs without refetching Reddit.
    """
    s = cfg.script
    budget = int(s.words_per_second * s.max_seconds)

    title = clean_text(post["title"])
    if cfg.script.soften_profanity:
        title = soften(title)
    if not title.endswith((".", "!", "?")):
        title += "."

    if post["mode"] == "comments":
        body_sentences = []
        for i, c in enumerate(post["comments"], 1):
            c = clean_text(c)
            if cfg.script.soften_profanity:
                c = soften(c)
            if not c.endswith((".", "!", "?")):
                c += "."
            lead = "First answer." if i == 1 else f"Next."
            body_sentences.extend(_sentences(f"{lead} {c}"))
    else:
        body = clean_text(post["body"])
        if cfg.script.soften_profanity:
            body = soften(body)
        body_sentences = _sentences(body)

    title_words = len(title.split())
    cta_words = len(post["cta"].split()) + 6  # cta + part-hook slack

    # Greedily pack sentences into parts within the word budget.
    parts: list[list[str]] = []
    current: list[str] = []
    used = title_words  # part 1 starts with the title
    for sent in body_sentences:
        n = len(sent.split())
        if used + n + cta_words > budget and current:
            parts.append(current)
            if len(parts) >= s.max_parts:
                current = []
                break
            current = []
            used = 4  # "Part two." prefix
        current.append(sent)
        used += n
    if current:
        parts.append(current)
    if not parts:
        parts = [[]]

    total = len(parts)
    ordinal = ["one", "two", "three", "four", "five"]
    segments = []
    for i, sent_group in enumerate(parts, 1):
        pieces = []
        if i == 1:
            pieces.append(title)
        else:
            pieces.append(f"Part {ordinal[min(i - 1, 4)]}.")
        pieces.extend(sent_group)
        if i < total:
            pieces.append(f"Follow so you don't miss part {ordinal[min(i, 4)]}.")
        else:
            pieces.append(post["cta"])
        narration = " ".join(pieces)
        segments.append(
            {
                "post_id": post["id"],
                "subreddit": post["subreddit"],
                "emoji": post["emoji"],
                "title": post["title"],
                "spoken_title": title if i == 1 else f"Part {ordinal[min(i - 1, 4)]}.",
                "narration": narration,
                "part": i,
                "total_parts": total,
                "author": post["author"],
                "score": post["score"],
                "num_comments": post["num_comments"],
            }
        )
    return segments
