# To do (as of 2026-10-20)

## Open

1. **Push the two local commits** (`43f3985` tracking stats, `246cc15` fixes): `git push origin main`.
2. **Look at the new pages in a browser** (none have been seen on screen yet): Home probable goalies, Fantasy goalie starts, player pages,
   Compare, the All-Time era-adjusted view, saved views, head-to-head, Speed & shots, and the game-page charts.
3. **Next October (first run after a season ends):** run both `python ingest.py backfill-onice` and `backfill-edge` so the season that
   just ended is filled in. Both were fully caught up for 2025-26 as of this date.

## Known issues (not scheduled)

- **Tracking leaders hide early-season stars.** `/api/tracking/leaders` defaults to `min_gp=10`, so in the first weeks of a season players
  with fewer games (McDavid, MacKinnon) are missing from the current-season list. Options: scale the default to games played so far, skip
  it for speed stats, and/or make it a visible control.
- **Current-season speed extras lag the core stats by up to a week** (bursts, average shot speed, bands refresh weekly; core stats nightly).
  Options: show an "as of" date next to them, or refresh them nightly.

## Done

- EDGE tracking backfill pass 2 finished on 2026-10-16 (all 5,435 skater-seasons have extras).
- Extras verified and `smoke_test.py` rerun on 2026-10-20: 0 failures.
- API on port 8000 restarted with the newer endpoints.
- On-ice backfill is complete for 2022-23 through 2025-26.
- Morning roster email set up on 2026-10-20 (Gmail SMTP, `com.hockeystats.digest` launchd job loaded for 8:00 AM, test email sent,
  API restarted with the SMTP settings so password-reset emails send). It sends nothing until an account turns the digest on, and the
  "turn this off" link points at `localhost:5173` until `PUBLIC_URL` is set to a real address. If the API is restarted by hand it needs
  the SMTP variables from `~/Library/LaunchAgents/com.hockeystats.digest.plist` exported first.
