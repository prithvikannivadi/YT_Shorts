# Channels

The bot runs multiple channels off one codebase. Each channel is a **config
file** that selects a content source (fetcher), a background source, and a hook
style. Pick the channel at runtime:

```bash
python -m bot.main run --config config.yaml             # reddit
python -m bot.main run --config config.finance.yaml     # finance
python -m bot.main run --config config.outdoor.yaml     # outdoor
```

## Background source is channel-specific (verified)

This is enforced in `background.pick_background()` via `channel.background_mode`:

| Channel  | `background_mode` | Background that gets used                          |
|----------|-------------------|----------------------------------------------------|
| reddit   | `gameplay`        | random slice of the downloaded gameplay library    |
| finance  | `source`          | the content's **own original source video**        |
| outdoor  | `source`          | the content's **own original source video**        |

**Gameplay footage is used ONLY by the Reddit channel.** For `source` channels
the fetcher must put the original video on each segment as
`segment["background_source"]` (a local path to the downloaded clip); the
pipeline uses that directly and never touches the gameplay library.

Verified by rendering one short per mode and confirming the background: Reddit →
gameplay, finance → its source clip. See the render logs (`background: original
source video ...` vs the gameplay path).

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
