#!/usr/bin/env python3
"""
yt_migrate.py — copy YouTube playlists (and optionally Liked videos) from one
Google account to another. Resumable across the API's daily quota reset.

One-time setup
--------------
1. https://console.cloud.google.com -> create a project -> APIs & Services
   -> Library -> enable "YouTube Data API v3".
2. APIs & Services -> OAuth consent screen -> External -> fill the required
   fields -> under "Test users" add BOTH Google accounts (old and new).
3. APIs & Services -> Credentials -> Create credentials -> OAuth client ID
   -> Application type "Desktop app" -> download the JSON and save it next
   to this script as client_secret.json.
4. pip install google-api-python-client google-auth-oauthlib

Usage
-----
python yt_migrate.py export                  # sign in as OLD account -> playlists.json
python yt_migrate.py export --include-likes  # also capture Liked videos
python yt_migrate.py import --dry-run        # preview what will be created
python yt_migrate.py import                  # sign in as NEW account, create lists

Writes cost 50 quota units each against a default budget of 10,000/day
(~200 videos/day). When the quota runs out the script saves progress to
state.json and exits; just re-run `import` the next day until it says Done.

Not covered by the API: Watch Later, watch history, and playlists you *saved*
from other channels (only playlists you created are exported).
"""
import argparse
import json
import os
import sys
import time

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

CLIENT_SECRET = "client_secret.json"
SNAPSHOT = "playlists.json"
STATE = "state.json"
TOKEN_OLD = "token_old.json"
TOKEN_NEW = "token_new.json"

READ_SCOPES = ["https://www.googleapis.com/auth/youtube.readonly"]
WRITE_SCOPES = ["https://www.googleapis.com/auth/youtube"]

WRITE_COST = 50          # playlists.insert, playlistItems.insert, videos.rate
DAILY_QUOTA = 10_000     # default allocation; check your project's Quotas page
QUOTA_REASONS = {"quotaExceeded", "dailyLimitExceeded", "rateLimitExceeded"}


# --------------------------------------------------------------------------- auth

def get_service(token_file, scopes, label):
    creds = None
    if os.path.exists(token_file):
        creds = Credentials.from_authorized_user_file(token_file, scopes)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(CLIENT_SECRET):
                sys.exit(f"Missing {CLIENT_SECRET}. See the setup notes at the top of this script.")
            print(f"\n>>> A browser window will open. Sign in as your {label} account. <<<\n")
            flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRET, scopes)
            creds = flow.run_local_server(port=0, prompt="consent")
        with open(token_file, "w") as f:
            f.write(creds.to_json())
    return build("youtube", "v3", credentials=creds)


def paged(request_fn, **kwargs):
    """Yield items across all pages of a list() call."""
    page_token = None
    while True:
        resp = request_fn(pageToken=page_token, **kwargs).execute()
        yield from resp.get("items", [])
        page_token = resp.get("nextPageToken")
        if not page_token:
            return


def error_reason(err):
    try:
        data = json.loads(err.content.decode("utf-8"))
        return data["error"]["errors"][0]["reason"]
    except Exception:
        return ""


# ------------------------------------------------------------------------- export

def cmd_export(args):
    yt = get_service(TOKEN_OLD, READ_SCOPES, "OLD")
    print("Reading playlists from the old account...")

    playlists = []
    for pl in paged(yt.playlists().list, part="snippet,status",
                    mine=True, maxResults=50):
        playlists.append({
            "kind": "playlist",
            "source_id": pl["id"],
            "title": pl["snippet"]["title"],
            "description": pl["snippet"].get("description", ""),
            "privacy": pl["status"]["privacyStatus"],
            "video_ids": [],
        })

    if args.include_likes:
        ch = yt.channels().list(part="contentDetails", mine=True).execute()
        items = ch.get("items") or []
        likes_id = items[0]["contentDetails"]["relatedPlaylists"].get("likes") if items else None
        if likes_id:
            playlists.append({"kind": "likes", "source_id": likes_id,
                              "title": "Liked videos", "video_ids": []})
        else:
            print("  (no Liked videos playlist found on this account)")

    for pl in playlists:
        for item in paged(yt.playlistItems().list, part="contentDetails",
                          playlistId=pl["source_id"], maxResults=50):
            pl["video_ids"].append(item["contentDetails"]["videoId"])
        if pl["kind"] == "likes":
            pl["video_ids"].reverse()   # like oldest first so newest ends up on top
        print(f"  {pl['title']}: {len(pl['video_ids'])} videos")

    with open(SNAPSHOT, "w") as f:
        json.dump(playlists, f, indent=2)

    n_lists = sum(1 for p in playlists if p["kind"] == "playlist")
    n_videos = sum(len(p["video_ids"]) for p in playlists)
    units = (n_lists + n_videos) * WRITE_COST
    days = -(-units // DAILY_QUOTA)
    print(f"\nSaved {len(playlists)} lists / {n_videos} videos to {SNAPSHOT}.")
    print(f"Import will cost ~{units:,} quota units -> about {days} day(s) at {DAILY_QUOTA:,}/day.")


# ------------------------------------------------------------------------- import

def load_state():
    if os.path.exists(STATE):
        with open(STATE) as f:
            return json.load(f)
    return {}


def save_state(state):
    tmp = STATE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(state, f, indent=2)
    os.replace(tmp, STATE)


def cmd_import(args):
    if not os.path.exists(SNAPSHOT):
        sys.exit(f"{SNAPSHOT} not found. Run `python yt_migrate.py export` first.")
    with open(SNAPSHOT) as f:
        playlists = json.load(f)
    state = load_state()

    if args.dry_run:
        remaining = 0
        for pl in playlists:
            st = state.get(pl["source_id"], {"dest_id": None, "next": 0, "skipped": []})
            left = len(pl["video_ids"]) - st["next"]
            remaining += left + (1 if pl["kind"] == "playlist" and not st["dest_id"] else 0)
            status = "done" if left == 0 and (st["dest_id"] or pl["kind"] == "likes") else f"{left} to go"
            print(f"  [{pl['kind']:8}] {pl['title']} ({len(pl['video_ids'])} videos) - {status}")
        print(f"\nRemaining writes: {remaining} (~{remaining * WRITE_COST:,} units, "
              f"~{-(-remaining * WRITE_COST // DAILY_QUOTA)} day(s)).")
        return

    yt = get_service(TOKEN_NEW, WRITE_SCOPES, "NEW")
    print("Importing into the new account...")

    try:
        for pl in playlists:
            st = state.setdefault(pl["source_id"], {"dest_id": None, "next": 0, "skipped": []})
            ids = pl["video_ids"]

            if pl["kind"] == "playlist" and st["dest_id"] is None:
                resp = yt.playlists().insert(part="snippet,status", body={
                    "snippet": {"title": pl["title"][:150],
                                "description": pl.get("description", "")[:5000]},
                    "status": {"privacyStatus": pl.get("privacy", "private")},
                }).execute()
                st["dest_id"] = resp["id"]
                save_state(state)
                print(f"\nCreated playlist '{pl['title']}' ({pl.get('privacy')})")
            elif st["next"] < len(ids):
                print(f"\nResuming '{pl['title']}' at {st['next']}/{len(ids)}")

            while st["next"] < len(ids):
                vid = ids[st["next"]]
                try:
                    if pl["kind"] == "likes":
                        yt.videos().rate(id=vid, rating="like").execute()
                    else:
                        yt.playlistItems().insert(part="snippet", body={
                            "snippet": {
                                "playlistId": st["dest_id"],
                                "resourceId": {"kind": "youtube#video", "videoId": vid},
                            }
                        }).execute()
                except HttpError as e:
                    reason = error_reason(e)
                    if reason in QUOTA_REASONS:
                        raise
                    # Deleted, private, or region-blocked video: note it and move on.
                    st["skipped"].append({"videoId": vid, "reason": reason or str(e.resp.status)})
                st["next"] += 1
                save_state(state)
                if st["next"] % 10 == 0 or st["next"] == len(ids):
                    print(f"  {st['next']}/{len(ids)}", end="\r", flush=True)
                time.sleep(0.2)

            print(f"  '{pl['title']}': {st['next']}/{len(ids)} done, "
                  f"{len(st['skipped'])} skipped")

    except HttpError as e:
        reason = error_reason(e)
        if reason == "youtubeSignupRequired":
            print("\nThe new account has no YouTube channel yet. Sign in to youtube.com "
                  "as that account, create a channel (avatar -> Create a channel), "
                  "then re-run import.")
            sys.exit(3)
        if reason in QUOTA_REASONS:
            print("\n\nDaily API quota exhausted. Progress is saved in state.json.")
            print("Re-run `python yt_migrate.py import` after the quota resets (midnight Pacific).")
            sys.exit(2)
        raise

    skipped = [(pl["title"], s) for pl in playlists
               for s in state.get(pl["source_id"], {}).get("skipped", [])]
    print("\nDone.")
    if skipped:
        print(f"{len(skipped)} video(s) could not be added (deleted/private/unavailable):")
        for title, s in skipped:
            print(f"  {title}: https://youtu.be/{s['videoId']} ({s['reason']})")


# --------------------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    p_exp = sub.add_parser("export", help="snapshot playlists from the OLD account")
    p_exp.add_argument("--include-likes", action="store_true",
                       help="also export Liked videos (re-liked on the new account)")
    p_imp = sub.add_parser("import", help="create playlists on the NEW account")
    p_imp.add_argument("--dry-run", action="store_true", help="show the plan, write nothing")
    args = ap.parse_args()
    {"export": cmd_export, "import": cmd_import}[args.cmd](args)


if __name__ == "__main__":
    main()
