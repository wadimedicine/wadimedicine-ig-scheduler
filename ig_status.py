#!/usr/bin/env python3
"""
Read-only status: what's LIVE on @wadimedicine right now vs what's QUEUED.
Lets Claude (or Wadi) look at the account and catch problems — already posted,
wrong video, wrong day — instead of finding out after the fact.

    python ig_status.py
"""
import datetime
import glob
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ig_publish import load_creds, recent_media  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
QUEUE = os.path.join(HERE, "queue")


def main():
    uid, tok = load_creds()

    print("=== LIVE on Instagram (newest first) ===")
    live = recent_media(uid, tok, 15)
    if not live:
        print("  (no posts yet)")
    for m in live:
        cap = (m.get("caption") or "").replace("\n", " ")[:75]
        print(f"  {m.get('timestamp', '?')} | {m.get('media_type', '?'):11} | {cap}")

    print("\n=== QUEUED (scheduled, not yet posted) ===")
    jobs = sorted(glob.glob(os.path.join(QUEUE, "*.json")))
    if not jobs:
        print("  (queue empty)")
    now = datetime.datetime.now(datetime.timezone.utc)
    for p in jobs:
        with open(p, encoding="utf-8-sig") as f:
            j = json.load(f)
        cap = (j.get("caption") or "").replace("\n", " ")[:55]
        t = datetime.datetime.fromisoformat(j["publish_at_utc"].replace("Z", "+00:00"))
        when = "DUE NOW" if t <= now else f"in {str(t - now).split('.')[0]}"
        print(f"  {j['publish_at_utc']} ({when}) | {j['id']:4} | {cap}")


if __name__ == "__main__":
    main()
