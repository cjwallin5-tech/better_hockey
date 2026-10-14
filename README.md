# NHL Stats

A hockey stats site with more than the official one: point pace (projected to an **84-game** season),
hits and defensive stats, possession (Corsi/Fenwick), expected goals, lines, shot maps, goalie
analytics, career history, milestones and more.

- **backend/** Python: `ingest.py` pulls data from the NHL's public (unofficial) APIs into Postgres;
  `api.py` is a FastAPI app serving JSON.
- **frontend/** React + Vite single-page app (proxies `/api` to the backend in development).

## Run it locally

```bash
createdb hockey_stats
cd backend && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python ingest.py                      # first run takes a few minutes; later runs are incremental
.venv/bin/uvicorn api:app --port 8000           # API (restart it after editing api.py)
cd ../frontend && npm install && npm run dev    # http://localhost:5173
```

Check the API with `backend/.venv/bin/python backend/smoke_test.py` (hits every endpoint).

## Data and the nightly job

`backend/run_ingest.sh` is what the nightly job runs (a macOS launchd agent, 4:00 AM, logs in
`backend/logs/`). Each run only fetches what's new: finished games (one boxscore each), shift charts and
play-by-play for on-ice stats, standings, schedule, and career totals (at most every 12 hours).

Things worth knowing:
- The NHL APIs are unofficial and rate-limit hard (HTTP 429); the ingest throttles and backs off.
- The stats API's shift charts are sometimes empty; `html_shifts.py` rebuilds them from the NHL's
  HTML time-on-ice reports (checked identical on test games).
- Expected goals come from our own model: `train_xg_fetch.py` + `train_xg.py` fit it on a past season
  and write `xg_model.json`. Re-run them to refresh it.
- Lineup gaps are *inferred* from games a team played without a player. The NHL doesn't publish injuries
  or transactions, so the UI says "not in the lineup", never "injured".
- Per-player career data is fetched lazily by the API and cached in Postgres for 24 hours.

## Features worth knowing about

- **Fantasy team** (`/fantasy`): roster, league scoring you set yourself, fantasy points, a this-week schedule with lineup
  alerts, pickup ideas, and share-link / JSON backup (everything is stored in the browser only).
- **Accounts** (`/account`): optional email + password sign-in (scrypt-hashed, HttpOnly cookie session) that syncs the fantasy
  roster and scoring across devices. Tables are created automatically when the API starts (`backend/auth.py`).
  **Password reset** emails a single-use link (valid 1 hour) over SMTP. Set `SMTP_HOST`, `SMTP_PORT` (587, STARTTLS),
  `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM` and `PUBLIC_URL` (the site's address, used in the link) for the API; any provider's
  SMTP works (Resend, SES, Gmail...). With `SMTP_HOST` unset, the link is printed to the API log instead, which is for local
  development only. Over HTTPS the session cookie is marked Secure; put the API behind HTTPS before exposing it publicly.
- **Head-to-head** (`/head-to-head`, under More, and linked from every game page): team-vs-team results and a skater's scoring against a
  team, over this season and the previous four (the games we store). Past seasons are paired into opponents by
  `ingest_team_abbrevs`; the Coyotes' games count toward Utah. Goalies aren't covered.
- **Saved views**: signed-in users can save the current filters and sort on the skater, goalie and all-time leaderboards under
  a name (up to 30) and reopen them with one click. A view is just the page's URL query string, kept per account.
- **Era-adjusted scoring**: the All-Time page's "Era-adjusted" view and the Compare page's adjusted charts rescale each season's
  goals and assists to today's scoring level (the last five completed seasons), separately for forwards and defensemen
  (`backend/era.py` explains the method and what it leaves out). The nightly ingest recomputes the stored career figures.
- **On-ice defense for past seasons**: `python ingest.py backfill-onice` (from `backend/`, optionally with seasons like `20222023,20232024` and
  `--limit N`) computes 5v5 shot attempts, expected goals and ice time per skater for every game of the previous four seasons
  from the NHL play-by-play and shift charts. It's resumable (finished games are skipped) and takes about an hour at the NHL's rate
  limits, so it isn't part of the nightly job. It feeds the "xGA/60 vs. teammates" columns and chart on player and Compare pages.
- **Goalie starts this week** (Fantasy → This week): each rostered goalie's chance of starting every game in the next week, and the
  expected number of starts. It chains the starter guess across games (a back-to-back after an uncertain start is a mix of both
  cases), anchoring on any start the NHL boxscore already shows. Still an inference; `probable_goalies.py` documents the model.
- **Daily roster email**: signed-in users can turn it on from the Account page. `backend/digest.py` emails today's games for
  each rostered player (with a likely-starter guess for goalies), who's hot and who's missing games, at most once per Eastern
  day, using the same SMTP settings as password reset. Preview without sending: `.venv/bin/python digest.py --dry`, or
  `--preview 8478402,8480069` for a list of player ids. To send every morning, copy `~/Library/LaunchAgents/com.hockeystats.ingest.plist`
  to `com.hockeystats.digest.plist`, point it at `backend/run_digest.sh`, set `Hour` to 8, change the `Label`, and run
  `launchctl load` on it (logs in `backend/logs/digest.log`).
- **Playoff odds** (Standings → Playoff odds): Monte Carlo over the remaining schedule (`backend/playoff_odds.py`; the model and its
  knobs are described at the top of that file). **Schedule grid** (`/schedule`, under More): games per team per week, with light
  weeks, heavy weeks and back-to-backs marked. Both need the full-season schedule, which the nightly ingest now loads.
- **Trophy races** (`/trophies`): top-5 contenders for the stat-driven awards (Art Ross, Richard, Norris, Calder, Vezina).
- **Live scores** on the home page come straight from the NHL scoreboard (cached 20s); everything else is from the nightly ingest.
- The footer shows when stats were last refreshed and warns if the nightly job looks like it missed a run.

## Layout

`backend/`: `ingest.py` (all data loading), `corsi.py` / `shots.py` / `html_shifts.py` (on-ice math),
`api.py` (all endpoints), `schema.sql`. `frontend/src/`: `pages/` (one per route) and `components/`.
