# YouTube Shorts Reddit Bot 🍿

Fully automated faceless-channel pipeline: finds top Reddit stories, narrates
them with a free AI voice, renders them over gameplay footage with viral-style
word-pop captions, and uploads to YouTube Shorts 3× daily via GitHub Actions.

## How a video gets made

1. **Fetch** — picks the day's highest-upvoted unposted story from
   r/AmItheAsshole, r/tifu, r/confession, r/pettyrevenge, r/AskReddit
   (AskReddit uses top comments instead of the post body).
2. **Script** — strips Reddit markdown, expands jargon (AITA → "Am I the
   jerk"), softens profanity for monetization, and packs the story into a
   ≤58-second narration. Long stories become Part 1/2/3, queued for later
   runs with a "follow for part two" hook.
3. **Voice** — Microsoft Edge TTS (free) at +12% speed, with word-level
   timestamps captured from the synthesis stream.
4. **Visuals** — a fake Reddit post card shows while the title is read, then
   big centered word-pop captions synced to the voice, over a random slice of
   your copyright-free gameplay library.
5. **Render** — one ffmpeg pass: 1080×1920, 30fps, loudness-normalized audio.
6. **Upload** — YouTube Data API, with emoji title, hashtags, and tags.

## Quick start

Follow **[SETUP.md](SETUP.md)** (Reddit app → YouTube OAuth → background
footage), then test from the Actions tab with upload = false.

Run locally:

```bash
pip install -r requirements.txt          # plus ffmpeg installed on your system
export REDDIT_CLIENT_ID=... REDDIT_CLIENT_SECRET=...
python -m bot.main run --no-upload       # video appears in output/
```

## Layout

```
config.yaml        all knobs: subreddits, voices, caption style, schedule targets
bot/
  main.py          pipeline orchestrator (python -m bot.main run)
  reddit_fetcher.py  story selection
  script.py        cleanup, jargon/profanity handling, part splitting
  tts.py           Edge TTS + word timings
  captions.py      .ass karaoke subtitle generator
  title_card.py    fake Reddit post card (Pillow)
  background.py    yt-dlp library management + random slicing
  render.py        ffmpeg composition
  uploader.py      YouTube upload
  auth.py          one-time local OAuth (python -m bot.auth)
data/state.json    posted history + queued parts (committed back by CI)
```

## Honest notes

- **YouTube API audit**: uploads from unverified API projects are locked
  private. File the (free) audit form early — details in SETUP.md.
- **Reuse policy**: YouTube demonetizes channels it considers "mass-produced
  repetitious content." Channels in this niche that survive add editing
  variety, good story curation, and eventually original elements. Watch your
  first videos and tune `config.yaml` — curation quality is the real
  viral lever.
- **Respect licenses**: only use background footage whose uploader explicitly
  permits reuse, and credit them in the description when asked.
