#!/usr/bin/env python3
"""
StarTalk Discord notifier.

Checks for new:
  - YouTube videos and YouTube Shorts (announced separately)
  - Patreon posts
  - Podcast episodes (Spotify API, or the podcast's RSS feed)
and posts each one to a Discord webhook, pinging the matching role.

Every source is optional: anything without settings is skipped.
Settings come from environment variables (GitHub Actions secrets). See SETUP.md.

The first time a source runs, it records what already exists WITHOUT posting,
so your server isn't flooded with old uploads.

Usage:
  python notifier.py            check once (what GitHub Actions runs)
  python notifier.py --dry-run  print what would be posted, post nothing
  python notifier.py --test     post the latest item from each source, marked [TEST],
                                without actually pinging anyone
  python notifier.py --loop 5   keep running, checking every 5 minutes (for a server)
"""

import argparse
import json
import os
import sys
import time
import traceback
import xml.etree.ElementTree as ET
from collections import namedtuple
from datetime import datetime, timezone

import requests

# ---------------------------------------------------------------------------
# Message text. {title} is replaced with the video/post/episode title.
# The link goes on its own line underneath, so Discord shows a preview.
# ---------------------------------------------------------------------------
MESSAGES = {
    "videos": "🎬 **New video:** {title}",
    "shorts": "⚡ **New Short:** {title}",
    "patreon": "💜 **New Patreon post:** {title}",
    "patreon_locked": "💜 **New Patreon post (patrons only):** {title}",
    "podcast": "🎙️ **New episode:** {title}",
}

STATE_FILE = os.environ.get("STATE_FILE", "state.json")
KEEP_IDS = 300          # how many already-seen IDs to remember per source
RECENT_ONLY = 20        # only ever consider this many of the newest Patreon posts / episodes
TIMEOUT = 20
UA = {"User-Agent": "Mozilla/5.0 (compatible; StarTalkDiscordNotifier/1.0)"}

Item = namedtuple("Item", "id title url kind")


def env(name):
    return os.environ.get(name, "").strip()


def log(msg):
    print(f"[{datetime.now(timezone.utc):%Y-%m-%d %H:%M:%S}Z] {msg}", flush=True)


# --------------------------------------------------------------------------- state

def load_state():
    try:
        with open(STATE_FILE, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


def save_state(state):
    tmp = STATE_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=1, sort_keys=True)
    os.replace(tmp, STATE_FILE)


# --------------------------------------------------------------------------- discord

def post_discord(webhook, role_id, text, url, dry_run=False, ping=True):
    content = f"{text}\n{url}"
    if role_id:
        content = f"<@&{role_id}> {content}"
    if dry_run:
        log(f"  (dry run) would post: {content!r}")
        return
    payload = {
        "content": content,
        # Only ever ping the one intended role, never @everyone by accident.
        # Test posts show the role but don't actually notify anyone.
        "allowed_mentions": {"parse": [], "roles": [role_id] if (role_id and ping) else []},
    }
    if not ping:
        payload["flags"] = 4096  # SUPPRESS_NOTIFICATIONS: silent test messages
    for _ in range(5):
        r = requests.post(webhook, json=payload, timeout=TIMEOUT)
        if r.status_code == 429:
            time.sleep(float(r.json().get("retry_after", 1)) + 0.5)
            continue
        if r.status_code >= 400:
            raise RuntimeError(f"Discord webhook error {r.status_code}: {r.text[:300]}")
        return
    raise RuntimeError("Discord kept rate-limiting the webhook")


# --------------------------------------------------------------------------- youtube

YT_NS = {"atom": "http://www.w3.org/2005/Atom", "yt": "http://www.youtube.com/xml/schemas/2015"}


def youtube_entries(channel_id):
    r = requests.get("https://www.youtube.com/feeds/videos.xml",
                     params={"channel_id": channel_id}, headers=UA, timeout=TIMEOUT)
    r.raise_for_status()
    root = ET.fromstring(r.content)
    entries = []
    for e in root.findall("atom:entry", YT_NS):
        vid = e.findtext("yt:videoId", namespaces=YT_NS)
        title = e.findtext("atom:title", default="New upload", namespaces=YT_NS)
        if vid:
            entries.append((vid, title))
    entries.reverse()  # feed is newest-first; announce oldest-first
    return entries


def youtube_kind(video_id):
    """'shorts', 'videos', or None if YouTube gave an unclear answer (retry next run)."""
    r = requests.get(f"https://www.youtube.com/shorts/{video_id}", headers=UA,
                     allow_redirects=False, timeout=TIMEOUT, stream=True)
    r.close()
    if r.status_code == 200:
        return "shorts"
    if 300 <= r.status_code < 400 and "watch" in r.headers.get("Location", ""):
        return "videos"
    return None


# --------------------------------------------------------------------------- patreon

PATREON_API = "https://www.patreon.com/api/oauth2/v2"


def patreon_items(token):
    h = {"Authorization": f"Bearer {token}", **UA}
    r = requests.get(f"{PATREON_API}/campaigns", headers=h, timeout=TIMEOUT)
    if r.status_code == 401:
        raise RuntimeError("Patreon token was rejected (401). It has probably expired; "
                           "make a new one (see SETUP.md) and update the PATREON_TOKEN secret.")
    r.raise_for_status()
    campaigns = r.json().get("data") or []
    if not campaigns:
        raise RuntimeError("This Patreon token has no campaign. Use the creator account's token.")
    campaign_id = campaigns[0]["id"]

    url = f"{PATREON_API}/campaigns/{campaign_id}/posts"
    params = {"fields[post]": "title,url,published_at,is_public", "page[count]": 50}
    posts, pages = [], 0
    while url and pages < 40:
        r = requests.get(url, headers=h, params=params, timeout=TIMEOUT)
        r.raise_for_status()
        data = r.json()
        posts.extend(data.get("data") or [])
        url = (data.get("links") or {}).get("next")
        params = None  # the "next" link already contains them
        pages += 1

    now = datetime.now(timezone.utc)
    out = []
    for p in posts:
        a = p.get("attributes") or {}
        published = a.get("published_at")
        if not published:
            continue  # draft
        try:
            when = datetime.fromisoformat(published.replace("Z", "+00:00"))
        except ValueError:
            continue
        if when > now:
            continue  # scheduled for later
        link = a.get("url") or ""
        if link.startswith("/"):
            link = "https://www.patreon.com" + link
        kind = "patreon" if a.get("is_public") else "patreon_locked"
        out.append((when, Item(p["id"], a.get("title") or "New post", link, kind)))
    out.sort(key=lambda x: x[0])
    return [item for _, item in out][-RECENT_ONLY:]


# --------------------------------------------------------------------------- podcast

def spotify_items(client_id, client_secret, show_id):
    t = requests.post("https://accounts.spotify.com/api/token",
                      data={"grant_type": "client_credentials"},
                      auth=(client_id, client_secret), timeout=TIMEOUT)
    t.raise_for_status()
    token = t.json()["access_token"]
    r = requests.get(f"https://api.spotify.com/v1/shows/{show_id}/episodes",
                     params={"market": "US", "limit": RECENT_ONLY},
                     headers={"Authorization": f"Bearer {token}"}, timeout=TIMEOUT)
    r.raise_for_status()
    eps = [e for e in r.json().get("items") or [] if e]
    eps.sort(key=lambda e: e.get("release_date") or "")
    return [Item(e["id"], e.get("name") or "New episode",
                 (e.get("external_urls") or {}).get("spotify", ""), "podcast") for e in eps]


def rss_items(feed_url):
    r = requests.get(feed_url, headers=UA, timeout=TIMEOUT)
    r.raise_for_status()
    root = ET.fromstring(r.content)
    items = root.findall("./channel/item")[:RECENT_ONLY]
    items.reverse()  # feeds are newest-first
    out = []
    for it in items:
        guid = it.findtext("guid") or it.findtext("link") or it.findtext("title")
        if guid:
            link = (it.findtext("link") or "").strip()
            # Some hosts supply a bare homepage instead of an episode page.
            # Use the episode's public audio URL when there is no usable link.
            if not link.startswith(("https://", "http://")):
                enclosure = it.find("enclosure")
                link = enclosure.get("url", "").strip() if enclosure is not None else ""
            if not link.startswith(("https://", "http://")):
                raise RuntimeError("Podcast episode has no usable page or audio link")
            out.append(Item(guid.strip(), (it.findtext("title") or "New episode").strip(),
                            link, "podcast"))
    return out


# --------------------------------------------------------------------------- core

def announce_new(state, key, items, targets, args):
    """Post items not seen before. targets maps item.kind -> (webhook, role_id)."""
    seen_list = state.get(key)
    first_run = seen_list is None and not args.test
    seen_list = list(seen_list or [])
    seen = set(seen_list)

    if args.test:
        items = items[-1:]  # just the latest one
    if first_run:
        log(f"{key}: first run, recording {len(items)} existing item(s) without posting")

    for item in items:
        if item.id in seen and not args.test:
            continue
        if not first_run:
            target = targets.get(item.kind)
            if not target:
                log(f"{key}: no webhook set for {item.kind!r}, skipping {item.title!r}")
            else:
                text = MESSAGES[item.kind].format(title=item.title)
                if args.test:
                    text = "[TEST] " + text
                log(f"{key}: posting {item.kind} → {item.title!r}")
                post_discord(target[0], target[1], text, item.url, args.dry_run, ping=not args.test)
        if item.id not in seen and not args.test:
            seen.add(item.id)
            seen_list.append(item.id)
        if not args.test and not args.dry_run:
            state[key] = seen_list[-KEEP_IDS:]  # save as we go, so a crash can't cause repeats

    if not args.test and not args.dry_run:
        state[key] = seen_list[-KEEP_IDS:]


def check_youtube(state, args):
    channel = env("YOUTUBE_CHANNEL_ID")
    targets = {}
    if env("WEBHOOK_VIDEOS"):
        targets["videos"] = (env("WEBHOOK_VIDEOS"), env("ROLE_VIDEOS"))
    if env("WEBHOOK_SHORTS"):
        targets["shorts"] = (env("WEBHOOK_SHORTS"), env("ROLE_SHORTS"))
    if not channel or not targets:
        return

    entries = youtube_entries(channel)
    known = set(state.get("youtube") or [])
    first_run = "youtube" not in state and not args.test
    items = []
    for vid, title in entries:
        if vid in known and not args.test:
            continue
        if first_run:
            items.append(Item(vid, title, "", "videos"))  # recorded only, never posted
            continue
        kind = youtube_kind(vid)
        if kind is None:
            log(f"youtube: couldn't tell if {vid} is a Short yet; will retry next run")
            continue
        url = f"https://www.youtube.com/shorts/{vid}" if kind == "shorts" \
            else f"https://www.youtube.com/watch?v={vid}"
        items.append(Item(vid, title, url, kind))
    if args.test:
        # Test mode: post the latest video AND the latest Short, so both pings get checked.
        latest = {}
        for item in items:
            latest[item.kind] = item
        for item in latest.values():
            announce_new(state, "youtube", [item], targets, args)
        return
    announce_new(state, "youtube", items, targets, args)


def check_patreon(state, args):
    token = env("PATREON_TOKEN")
    webhook = env("WEBHOOK_PATREON")
    if not token or not webhook:
        return
    target = (webhook, env("ROLE_PATREON"))
    announce_new(state, "patreon", patreon_items(token),
                 {"patreon": target, "patreon_locked": target}, args)


def check_podcast(state, args):
    webhook = env("WEBHOOK_PODCAST")
    if not webhook:
        return
    if env("SPOTIFY_CLIENT_ID") and env("SPOTIFY_CLIENT_SECRET") and env("SPOTIFY_SHOW_ID"):
        items = spotify_items(env("SPOTIFY_CLIENT_ID"), env("SPOTIFY_CLIENT_SECRET"),
                              env("SPOTIFY_SHOW_ID"))
    elif env("PODCAST_RSS_URL"):
        items = rss_items(env("PODCAST_RSS_URL"))
    else:
        return
    announce_new(state, "podcast", items, {"podcast": (webhook, env("ROLE_PODCAST"))}, args)


def run_once(args):
    state = load_state()
    failures = 0
    for name, fn in (("YouTube", check_youtube), ("Patreon", check_patreon),
                     ("Podcast", check_podcast)):
        try:
            fn(state, args)
        except Exception as e:  # one broken source shouldn't stop the others
            failures += 1
            log(f"{name} check failed: {e}")
            traceback.print_exc()
    if not args.test and not args.dry_run:
        save_state(state)
    return failures


def main():
    ap = argparse.ArgumentParser(description="StarTalk Discord notifier")
    ap.add_argument("--dry-run", action="store_true", help="print instead of posting")
    ap.add_argument("--test", action="store_true",
                    help="post the latest item from each source, marked [TEST]")
    ap.add_argument("--loop", type=float, metavar="MINUTES",
                    help="keep running, checking every MINUTES")
    args = ap.parse_args()

    if args.loop:
        while True:
            run_once(args)
            time.sleep(max(args.loop, 1) * 60)
    sys.exit(1 if run_once(args) else 0)


if __name__ == "__main__":
    main()
