#!/usr/bin/env python3
"""
Runs in GitHub Actions on a cron. Publishes any DUE posts sitting in queue/.

Each queue/<id>.json looks like:
{
  "id": "v6",
  "video_asset": "https://github.com/<user>/<repo>/releases/download/videos/v6.mp4",
  "caption": "...full caption + hashtags...",
  "publish_at_utc": "2026-07-25T18:00:00Z",
  "thumb_offset": 0        // OPTIONAL, ms. Omit = 0 = the frame-1 hook card.
}

On success the queue file is deleted; the workflow commits that deletion so the
post is never sent twice. Credentials come from env (GitHub secrets):
IG_USER_ID / IG_ACCESS_TOKEN.

STALE-POST GUARD (added 21 Jul after V5 missed 19:00 entirely). GitHub throttles
and drops scheduled workflows on free public repos — on 21 Jul the `*/5` cron ran
ONCE all day. An overdue entry used to stay armed forever, so a cron that finally
woke at 03:00 would have published at 03:00. Anything more than MAX_LATE_MINUTES
overdue is now refused and reported instead of posted. Override for a deliberate
late publish: env ALLOW_LATE=1 (the workflow exposes it as a dispatch input).
"""
import datetime
import glob
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ig_publish import (  # noqa: E402
    load_creds, create_container, wait_ready, publish, already_posted,
)

HERE = os.path.dirname(os.path.abspath(__file__))
QUEUE = os.path.join(HERE, "queue")

# A post this far past its slot is no longer the post that was approved — the
# 19:00 anchor is the point. Refuse rather than post it at a random hour.
MAX_LATE_MINUTES = 30


def _now():
    return datetime.datetime.now(datetime.timezone.utc)


def _scheduled_at(job):
    return datetime.datetime.fromisoformat(job["publish_at_utc"].replace("Z", "+00:00"))


def _due(job):
    return _scheduled_at(job) <= _now()


def _minutes_late(job):
    return (_now() - _scheduled_at(job)).total_seconds() / 60.0


def main():
    uid, tok = load_creds()
    allow_late = os.environ.get("ALLOW_LATE", "").strip().lower() in ("1", "true", "yes")
    posted = []
    stale = []
    for path in sorted(glob.glob(os.path.join(QUEUE, "*.json"))):
        with open(path, encoding="utf-8-sig") as f:
            job = json.load(f)
        if not _due(job):
            print(f"skip {job['id']} (scheduled {job['publish_at_utc']})")
            continue
        late = _minutes_late(job)
        if late > MAX_LATE_MINUTES and not allow_late:
            print(f"!! STALE {job['id']} — due {job['publish_at_utc']}, now {late:.0f} min late "
                  f"(limit {MAX_LATE_MINUTES}). NOT posting. Left in the queue so nothing is "
                  f"lost; re-run with ALLOW_LATE=1 to publish it anyway, or delete the file.")
            stale.append(f"{job['id']}({late:.0f}min)")
            continue
        if late > MAX_LATE_MINUTES:
            print(f"   (ALLOW_LATE set — publishing {job['id']} {late:.0f} min late on purpose)")
        dup = already_posted(uid, tok, job["caption"])
        if dup:
            print(f"ALREADY LIVE {job['id']} (media {dup['id']} @ {dup.get('timestamp')}) "
                  f"-> skipping + removing from queue, NOT reposting")
            os.remove(path)
            posted.append(job["id"] + "(already-live,skipped)")
            continue
        offset = int(job.get("thumb_offset", 0))
        print(f"PUBLISHING {job['id']} -> {job['video_asset']}")
        print(f"  cover: {offset} ms{' (frame-1 hook card)' if offset == 0 else ''}")
        cid = create_container(uid, tok, job["video_asset"], job["caption"], offset)
        wait_ready(tok, cid)
        mid = publish(uid, tok, cid)
        print(f"  posted media {mid}")
        os.remove(path)
        posted.append(job["id"])
    print("PUBLISHED: " + (", ".join(posted) if posted else "(nothing due)"))
    if stale:
        # Fail the job on purpose. A red run is the alert — GitHub emails the repo
        # owner on workflow failure, which is the only thing standing between a
        # missed post and nobody noticing until the next manual check.
        print("STALE (not posted): " + ", ".join(stale))
        sys.exit(1)


if __name__ == "__main__":
    main()
