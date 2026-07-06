# Channels

The bot runs multiple channels off one codebase. Each channel is a **config
file** that selects a content source (fetcher), a background source, and a hook
style. Pick the channel at runtime:

```bash
python -m bot.main run --config config.yaml             # reddit
python -m bot.main run --config config.finance.yaml     # finance
python -m bot.main run --config config.outdoor.yaml     # outdoor
```

## Content source per channel

| Channel | Content fetcher | Script | Background |
|---------|-----------------|--------|------------|
| reddit  | `reddit_fetcher` (Reddit API) | cleaned post text | gameplay library |
| finance | `finance_fetcher` (topic pool) | **Claude API** (`scriptgen`) | generated **data-viz** |
| outdoor | `outdoor_fetcher` (`source_fetcher`, CC-only) | **Claude API** (`scriptgen`) | the sourced **original clip** |

`main._fetch_segments()` dispatches on `channel.type`. Finance and outdoor need
`ANTHROPIC_API_KEY` (script generation); reddit does not.

## Background source is channel-specific (verified)

Enforced in `background.pick_background()` via `channel.background_mode`:

| Channel  | `background_mode` | Background that gets used                          |
|----------|-------------------|----------------------------------------------------|
| reddit   | `gameplay`        | random slice of the downloaded gameplay library    |
| finance  | `dataviz`         | a **generated** animated chart of the script's numbers |
| outdoor  | `source`          | the content's **own original source video**        |

**Gameplay footage is used ONLY by the Reddit channel.** Finance never uses a
source video (zero copyright risk); outdoor's fetcher puts the CC-licensed clip
on `segment["background_source"]` and the pipeline uses it directly.

Verified end-to-end: reddit renders gameplay+card, finance renders data-viz+hook
from an LLM script, outdoor renders source-clip+hook with attribution.

## Hook style is channel-specific

`hook.style` controls the opening 2-3 seconds — the biggest lever on
"stayed to watch":

- **`card`** (reddit): the fake Reddit post card is the hook; the narrator reads
  the title while it's on screen.
- **`overlay`** (finance, outdoor): a big curiosity-gap text hook is burned onto
  the opening frames, and the narration is front-loaded so sentence one *is* the
  hook (no ramp-up). Best results come from the fetcher supplying a
  purpose-written `segment["hook_text"]`; otherwise it's derived from the title.

Both styles share the same mechanic: the opener is spoken first, shown on
screen, and the captions skip those words until the overlay clears.

## What each channel's fetcher must return

A segment dict the shared pipeline understands:

| Field                | reddit | source channels | notes                                   |
|----------------------|:------:|:---------------:|-----------------------------------------|
| `title`              |   ✓    |        ✓        | used for slug + upload title            |
| `narration`          |   ✓    |        ✓        | full spoken script                      |
| `spoken_title`       |   ✓    |        –        | reddit: words shown on the card         |
| `hook_text`          |   –    |    ✓ (best)     | the curiosity-gap line for the overlay  |
| `background_source`  |   –    |        ✓        | path to the original source video       |
| `source_url` / `source_author` | – | recommended | for description attribution (see below) |
| `voice`, `part`, `total_parts`, `emoji`, `cta` | ✓ | ✓ | shared fields |

## Attribution for source channels

Finance/outdoor use other people's footage, so credit + a link belongs in the
description. **Important:** attribution is etiquette and is *required* by some
licenses (e.g. Creative Commons BY), but a credit does **not** by itself grant
you rights to reuse copyrighted footage or guarantee monetization — see the
monetization notes when configuring these channels. Set `attribution.enabled`
in the channel config and have the fetcher record `source_url` / `source_author`.
