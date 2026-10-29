# Youtube Playlists Migrate

Copy your YouTube playlists (and optionally Liked videos) from one Google
account to another using the official YouTube Data API v3. Titles,
descriptions, privacy settings and video order are preserved. The API is free;
its daily quota limits you to about 200 videos per day, so the script saves
progress after every video and resumes when you run it again.

*Created: October 27, 2026*

## Setup (once, ~5 minutes)

1. At <https://console.cloud.google.com> create a project and enable
   **YouTube Data API v3** (*APIs & Services → Library*).
2. *OAuth consent screen* → **External** → add **both** Google accounts under
   **Test users**. Leave the app in *Testing* status.
3. *Credentials → Create credentials → OAuth client ID → Desktop app* →
   download the JSON as `client_secret.json` next to the script.
4. Sign in to youtube.com as the **new** account and create a channel
   (avatar → *Create a channel*). A new Google account has none by default.
5. `pip install google-api-python-client google-auth-oauthlib`

## Usage

```bash
python yt_migrate.py export                  # sign in as OLD account -> playlists.json
python yt_migrate.py export --include-likes  # also capture Liked videos
python yt_migrate.py import --dry-run        # preview; writes nothing
python yt_migrate.py import                  # sign in as NEW account; resumable
```

Each command opens a browser for sign-in. `export` finishes in one run and
prints how many days the import will take. `import` stops when the daily quota
is used up; run it again the next day until it prints `Done.` You can edit
`playlists.json` between the two steps to drop playlists you don't want.

## Quota

10,000 units/day per project, reset at midnight Pacific. Creating a playlist,
adding a video, or liking a video each cost 50 units (~200 writes/day).
Quota can't be bought, and using multiple projects to multiply it breaks the
API terms, so larger libraries simply take several daily runs:
500 videos ≈ 3 days, 1,000 ≈ 6 days.

## Files

| File | Purpose |
|---|---|
| `client_secret.json`, `token_old.json`, `token_new.json` | Credentials — **never commit** |
| `playlists.json` | Snapshot of the old account's playlists |
| `state.json` | Import progress; delete to start the import over |

## Not migrated

Watch Later, watch history, and playlists you *saved* from other channels (only
playlists you created are exported). Deleted or private videos are skipped and
listed at the end. Subscriptions could be added using the same pattern.

## Troubleshooting

- **`youtubeSignupRequired`** — the new account has no channel. Do setup step 4
  and re-run.
- **"Access blocked / app not verified"** — that account isn't a test user.
  Add it on the OAuth consent screen.
- **`invalid_grant` on a later day** — Testing-mode tokens expire after 7 days.
  Delete the relevant `token_*.json` and re-run; progress is kept.
- **Wrong account signed in** — delete that `token_*.json` and re-run.
- **"Daily API quota exhausted"** — expected; run again tomorrow.
