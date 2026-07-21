#!/usr/bin/env python3
"""
WadiMedicine Instagram Reels publisher (Instagram API with Instagram Login).

Publishes a Reel to @wadimedicine from a PUBLIC video URL. Instagram's API has
no local-file upload and no native scheduling, so:
  - the video must already be at a public URL (we host it as a GitHub Release asset)
  - to "schedule", a cron (GitHub Actions) calls this at the target time

Flow: create a REELS container (video_url + caption) -> poll status until FINISHED
-> publish the container.

Usage:
    python ig_publish.py --video-url "https://.../v6.mp4" --caption-file cap.txt
    python ig_publish.py --video-url "https://.../v6.mp4" --caption "..." --dry-run

Creds come from ig_credentials.json (ig_user_id + access_token) unless overridden
by env vars IG_USER_ID / IG_ACCESS_TOKEN (that's how GitHub Actions passes secrets).
"""
import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

# Same machine SSL quirk as the YouTube scheduler: delegate cert verification to
# the OS trust store for local runs. No-op if absent / on Linux (GitHub Actions).
try:
    import truststore
    truststore.inject_into_ssl()
except ImportError:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
CREDS = os.path.join(HERE, "ig_credentials.json")
GRAPH = "https://graph.instagram.com"


def load_creds():
    uid = os.environ.get("IG_USER_ID")
    tok = os.environ.get("IG_ACCESS_TOKEN")
    if uid and tok:
        return uid, tok
    with open(CREDS, encoding="utf-8-sig") as f:  # utf-8-sig tolerates the BOM PowerShell writes
        c = json.load(f)
    return c["ig_user_id"], c["access_token"]


def _api(method, path, params):
    url = f"{GRAPH}/{path}"
    data = urllib.parse.urlencode(params).encode()
    if method == "GET":
        req = urllib.request.Request(url + "?" + data.decode(), method="GET")
    else:
        req = urllib.request.Request(url, data=data, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        sys.exit(f"IG API error {e.code}: {e.read().decode()}")


def create_container(uid, tok, video_url, caption):
    return _api("POST", f"{uid}/media", {
        "media_type": "REELS",
        "video_url": video_url,
        "caption": caption,
        "access_token": tok,
    })["id"]


def wait_ready(tok, container_id, timeout_s=600):
    start = time.time()
    while time.time() - start < timeout_s:
        st = _api("GET", container_id, {"fields": "status_code,status", "access_token": tok})
        code = st.get("status_code")
        print(f"  container {container_id}: {code}")
        if code == "FINISHED":
            return
        if code == "ERROR":
            sys.exit(f"Container processing failed: {st.get('status')}")
        time.sleep(5)
    sys.exit("Timed out waiting for the container to finish processing.")


def publish(uid, tok, container_id):
    return _api("POST", f"{uid}/media_publish", {
        "creation_id": container_id,
        "access_token": tok,
    })["id"]


def recent_media(uid, tok, limit=25):
    """Recent posts already on the account — used for dedup + status checks."""
    r = _api("GET", f"{uid}/media", {
        "fields": "id,caption,timestamp,media_type,permalink",
        "limit": str(limit), "access_token": tok,
    })
    return r.get("data", [])


def already_posted(uid, tok, caption, probe=60):
    """Return the matching live post if this caption is already on the feed, else None.
    Guards against double-posting even if a stale queue entry lingers."""
    key = (caption or "").strip()[:probe]
    if not key:
        return None
    for m in recent_media(uid, tok):
        if (m.get("caption") or "").strip().startswith(key):
            return m
    return None


def main():
    ap = argparse.ArgumentParser(description="Publish a Reel to Instagram.")
    ap.add_argument("--video-url", required=True, help="PUBLIC url of the mp4 (9:16, <=90s).")
    ap.add_argument("--caption", default="")
    ap.add_argument("--caption-file", help="Read caption as UTF-8 from a file (for non-ASCII).")
    ap.add_argument("--dry-run", action="store_true", help="Validate + print, publish nothing.")
    ap.add_argument("--no-publish", action="store_true",
                    help="Create + process the container to prove the pipeline, but do NOT post it.")
    a = ap.parse_args()

    caption = a.caption
    if a.caption_file:
        with open(a.caption_file, encoding="utf-8") as f:
            caption = f.read().strip()

    uid, tok = load_creds()
    print(f"-> IG user   : {uid}")
    print(f"   video_url : {a.video_url}")
    print(f"   caption   : {caption[:70]}{'...' if len(caption) > 70 else ''}")
    if a.dry_run:
        print("DRY RUN - nothing published.")
        return

    cid = create_container(uid, tok, a.video_url, caption)
    print(f"OK container created: {cid}")
    wait_ready(tok, cid)
    if a.no_publish:
        print("VALIDATED: container processed and ready — skipped publish (--no-publish).")
        return
    mid = publish(uid, tok, cid)
    print(f"OK PUBLISHED to Instagram: media id {mid}")
    print(f"   https://www.instagram.com/reel/  (media {mid})")


if __name__ == "__main__":
    main()
