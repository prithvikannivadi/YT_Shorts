# Setup Guide

Three things to set up, in order: Reddit API (2 min), YouTube upload credentials
(~15 min), and background footage (10 min). Then flip on the schedule.

---

## 1. Reddit API app (free, 2 minutes)

1. Log into Reddit, go to <https://www.reddit.com/prefs/apps>
2. Click **"create another app..."** at the bottom
3. Fill in:
   - **name**: `shorts-bot`
   - type: select **script**
   - **redirect uri**: `http://localhost:8080` (required but unused)
4. Click **create app**
5. Copy two values:
   - **client ID** — the string under the app name (looks like `Ab1Cd2Ef3Gh4`)
   - **secret** — labeled `secret`
6. In your GitHub repo: **Settings → Secrets and variables → Actions → New repository secret**, add:
   - `REDDIT_CLIENT_ID` = the client ID
   - `REDDIT_CLIENT_SECRET` = the secret
7. In `config.yaml`, change `reddit.user_agent` to include your Reddit username.

## 2. YouTube upload credentials (~15 minutes, one time)

You do this part **on your own computer** because it opens a browser to log
into the YouTube channel.

1. Go to <https://console.cloud.google.com/> → create a new project (name it anything, e.g. `shorts-bot`)
2. **APIs & Services → Library** → search **"YouTube Data API v3"** → **Enable**
3. **APIs & Services → OAuth consent screen**:
   - User type: **External** → Create
   - Fill in app name + your email (twice) → Save through the steps
   - Under **Audience → Test users**, add the Google account that owns your YouTube channel
4. **APIs & Services → Credentials → Create credentials → OAuth client ID**:
   - Application type: **Desktop app**
   - Download the JSON, rename it to `client_secret.json`
5. On your computer, in the `youtube-shorts-bot/` folder:

   ```bash
   pip install google-auth-oauthlib
   python -m bot.auth
   ```

   A browser opens — log in with your channel's account and approve. This writes `token.json`.
6. Add a GitHub secret `YT_TOKEN_JSON` containing the **entire contents** of `token.json`.
7. **Never commit** `client_secret.json` or `token.json` (they're gitignored).

### ⚠️ The API audit (important)

YouTube locks videos uploaded through **unverified** API projects to *private*.
To publish publicly via the API you need to complete a free, one-time audit:

- Fill out the form at <https://support.google.com/youtube/contact/yt_api_form>
  (select "API Audit"). Describe the app honestly: "personal tool that uploads
  my own narrated videos to my own channel on a schedule." Approval usually
  takes a few days to a couple of weeks.
- **Until then**: run the bot as-is — uploads land as private/locked, and you
  can't just flip them public in Studio (locked-private uploads must be
  re-uploaded). Practical workaround while waiting: trigger the workflow with
  **upload = false**, download the rendered .mp4 from the run's artifacts, and
  post it manually. Everything else stays automated.

## 3. Background footage (10 minutes)

The bot needs gameplay videos whose uploaders **explicitly allow reuse**:

1. On YouTube, search for things like:
   - `minecraft parkour no copyright free to use`
   - `subway surfers gameplay no copyright`
   - `satisfying video no copyright free to use`
2. **Verify the description actually says** it's free to use / no copyright /
   CC-BY. Prefer long videos (20+ min) so random slices rarely repeat.
3. Paste 3–5 URLs into `config.yaml` under `background.sources`.
4. Keep a note of which channels you used and credit them in
   `upload.description_extra` if their license asks for attribution.

The workflow downloads each video once and caches the library between runs.
If the list is empty the bot renders over a generated gradient background so
nothing breaks — but real gameplay footage performs far better.

## 4. Turn it on

1. Push/merge this project to the repo's **default branch** (scheduled
   workflows only run from the default branch).
2. Test manually first: **Actions → Shorts Bot → Run workflow** with
   **upload = false**, then download the artifact and watch the video.
3. Happy with it? Run again with upload = true, or just let the schedule
   (3× daily) take over.

## Troubleshooting

- **"No eligible story found"** — lower `reddit.min_score` in config.yaml.
- **Upload 401/invalid_grant** — token expired (test-mode OAuth tokens expire
  after 7 days of inactivity until your consent screen is published; click
  **Publish app** on the OAuth consent screen to stop that), then rerun
  `python -m bot.auth` and update the secret.
- **Upload quota** — the default YouTube API quota (10,000 units/day) covers
  ~6 uploads/day; 3×/day is safely within it.
- **Video looks wrong** — run locally: `pip install -r requirements.txt`,
  set the two Reddit env vars, then `python -m bot.main run --no-upload`.
