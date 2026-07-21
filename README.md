# WadiMedicine — Instagram Reels auto-scheduler

Fully-automated, **free** Instagram Reel scheduling: Wadi tells Claude *"schedule
V-X for <date> 19:00"*, and it posts itself at that time — hands-off, even if the
PC is off.

## Why it's built this way
Instagram's API (unlike YouTube's) gives us **no local-file upload** and **no
native scheduling**. So:
- **Hosting** — each video is uploaded as a **GitHub Release asset** (public URL
  Meta can pull from). Public repo ⇒ free unlimited Actions minutes too.
- **Timer** — a **GitHub Actions cron** (`.github/workflows/publish.yml`) runs
  every few minutes and publishes any `queue/` job whose time has come. Cloud-run,
  so it fires with the PC off. (GitHub can delay scheduled runs a few minutes.)
- **Publish** — `ig_publish.py` creates a REELS container from the video URL,
  waits for processing, and publishes it (Instagram Content Publishing API).

## How Claude schedules a post
1. `gh release upload videos <file>.mp4` → gets the public asset URL.
2. Writes `queue/<id>.json` (`video_asset`, `caption`, `publish_at_utc`).
3. `git commit && git push`. The cron does the rest at the set time.

## Secrets (GitHub → Settings → Secrets → Actions)
- `IG_USER_ID` — the Instagram user id (17841415462385556)
- `IG_ACCESS_TOKEN` — long-lived IG token (~60 days; refresh before expiry)

Credentials live locally in `ig_credentials.json` (gitignored) and in GitHub
Actions Secrets — never in the repo.

## Manual controls
- Run `python run_queue.py` locally (or trigger the workflow from the Actions tab)
  to publish due posts immediately.
- To cancel a scheduled post, delete its `queue/<id>.json` before its time.
