#!/usr/bin/env python3
"""
Runs in GitHub Actions on a cron. Publishes any DUE posts sitting in queue/.

Each queue/<id>.json looks like:
{
  "id": "v6",
  "video_asset": "https://github.com/<user>/<repo>/releases/download/videos/v6.mp4",
  "caption": "...full caption + hashtags...",
  "publish_at_utc": "2026-07-25T18:00:00Z"
}

On success the queue file is deleted; the workflow commits that deletion so the
post is never sent twice. Credentials come from env (GitHub secrets):
IG_USER_ID / IG_ACCESS_TOKEN.
"""
import datetime
import glob
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ig_publish import load_creds, create_container, wait_ready, publish  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
QUEUE = os.path.join(HERE, "queue")


def _now():
    return datetime.datetime.now(datetime.timezone.utc)


def _due(job):
    t = datetime.datetime.fromisoformat(job["publish_at_utc"].replace("Z", "+00:00"))
    return t <= _now()


def main():
    uid, tok = load_creds()
    posted = []
    for path in sorted(glob.glob(os.path.join(QUEUE, "*.json"))):
        with open(path, encoding="utf-8") as f:
            job = json.load(f)
        if not _due(job):
            print(f"skip {job['id']} (scheduled {job['publish_at_utc']})")
            continue
        print(f"PUBLISHING {job['id']} -> {job['video_asset']}")
        cid = create_container(uid, tok, job["video_asset"], job["caption"])
        wait_ready(tok, cid)
        mid = publish(uid, tok, cid)
        print(f"  posted media {mid}")
        os.remove(path)
        posted.append(job["id"])
    print("PUBLISHED: " + (", ".join(posted) if posted else "(nothing due)"))


if __name__ == "__main__":
    main()
