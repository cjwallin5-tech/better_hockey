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

Unit tests (no database or network needed, no extra packages):
- Backend: `cd backend && .venv/bin/python -m unittest discover -s tests -t .` covers the pure logic: the starter model, age-curve
  comparables, the defensive and on-ice metrics, era adjustment, head-to-head summaries, the playoff simulation, shift and
  shot-attempt maths, the email digest text and saved-view query cleaning.
- Frontend: `cd frontend && npm test` covers the game-page chart data (xG and Corsi flow) in `src/gameFlow.js`.

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

## Season rollover (each October)

The nightly job only keeps the current season (`SEASON_ID` in `backend/config.py`) up to date. Past seasons are loaded by hand
and never refreshed, so when a new season starts the one that just finished stops being updated and needs a final pass:

- Run `python ingest.py backfill-onice`, `backfill-edge` and `backfill-shots` from `backend/` (all resumable; the EDGE one takes
  hours, see Speed & shots below). The EDGE speed extras (bursts, average shot speed, bands) refresh only weekly during the
  season, so this pass is what settles the finished season's final numbers.
- Before relying on `backfill-onice`, check that the finished season's games are in `skater_game_hist`, since that table is what
  the backfill reads. This hasn't been checked for a season ending yet (as of 2026-10).
- The season's data is already correct while it's the current season; this is housekeeping, not a correctness check.

## Features worth knowing about

- **Fantasy team** (`/fantasy`): roster, league scoring you set yourself, fantasy points, a this-week schedule with lineup
  alerts, pickup ideas, and share-link / JSON backup (everything is stored in the browser only).
  **Player values** and the **trade analyzer** (Fantasy tabs) rank every player by fantasy points above a replacement-level
  player at their position over the rest of the season, under your scoring and league size (`frontend/src/value.js` documents the
  method). An early-season rate is pulled toward the player's own goals and assists over the last two seasons
  (`/api/fantasy/priors`), chosen by a backtest on four past seasons; every other stat is pulled toward the position average by its
  own weight (heavy for luck-driven ones like plus/minus and game-winning goals, light for shots and hits; these weights are
  reasoned, not backtested). Games left come from the stored schedule
  (`/api/fantasy/games-left`). League size is saved in the browser only, unlike the roster and scoring, which sync with an account.
  **Category leagues** (head-to-head or roto): choose "Category league" and the categories your league counts in Scoring & backup.
  Values, the trade analyzer, the roster table and pickups then switch to z-scores above replacement across those categories
  (`frontend/src/categories.js` explains the method), with a per-category breakdown in the trade analyzer. Each stat's early-season
  rate is pulled toward the average by a weight that depends on how noisy it is (shutouts and plus/minus far more than shots and
  hits), and z-scores are measured against the spread of real outcomes so a mostly-luck category can't dominate. Those per-stat
  weights come from reasoning about noise, not a backtest (only goals, assists and points could be backtested).
- **Accounts** (`/account`): optional email + password sign-in (scrypt-hashed, HttpOnly cookie session) that syncs the fantasy
  roster and scoring across devices. Tables are created automatically when the API starts (`backend/auth.py`).
  **Password reset** emails a single-use link (valid 1 hour) over SMTP. Set `SMTP_HOST`, `SMTP_PORT` (587, STARTTLS),
  `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM` and `PUBLIC_URL` (the site's address, used in the link) for the API; any provider's
  SMTP works (Resend, SES, Gmail...). With `SMTP_HOST` unset, the link is printed to the API log instead, which is for local
  development only. Over HTTPS the session cookie is marked Secure; put the API behind HTTPS before exposing it publicly.
- **Speed & shots** (`/tracking`, under More, plus a section on each player page): the NHL's EDGE puck and player tracking, since 2021-22.
  Hardest shots, top skating speed, bursts over 22 mph, average shot speed, distance skated, zone time and high-danger shots for
  skaters, and save % by shot range for goalies, each with the NHL's own percentile. `backend/edge.py` flattens the NHL responses;
  `python ingest.py backfill-edge` loads past seasons. The NHL allows only about 70 requests a minute, so the full backfill takes
  hours: it loads the core stats for everyone first, then the speed extras (bursts, average shot speed, shot-speed bands) in a
  second sweep. The nightly run tops up the current season (core stats for players who played; extras weekly).
- **Luck & regression** (`/luck`, under More): who is scoring or saving more, or less, than their shots predict. For skaters it compares
  goals with the summed xG of their shots, and points with an estimate that adds assists gained or lost when teammates finish
  above or below their shots while the player is on the ice (plus shooting % against expected, a full-season pace, on-ice goals
  against expected at 5v5, and the NHL's PDO); for goalies, goals saved above expected. Each gap gets a z-score from the shots' own variance, and
  |z| of 1.5 or more is flagged hot or cold (`backend/luck.py` explains the method and what it can't see). Our xG model doesn't know
  who is shooting, so past seasons' shots (`shot_hist`, loaded by `python ingest.py backfill-shots`, last four seasons) are used to
  estimate each skater's finishing edge and judge them against their own norm rather than an average shooter's; the page can switch
  between the two, shows past G − xG per player, and reports how well one year's luck figure predicts the next. Player and goalie
  pages show a season-by-season table.
  Goalie xG is scaled per season so the league's expected goals on shots on goal match its goals (an attempt's xG includes the
  chance of missing the net, so on-goal shots alone add up to only about two-thirds of the real total), and past skaters' xG is
  scaled so each season sums to that season's goals; this keeps an average player near zero.
  The same figures show up as a hot/cold badge next to rostered players on the Fantasy page, as a panel on each player and goalie
  page (Advanced tab), and as a "LUCK CHECK" section in the morning email (`backend/luck_db.py` holds the shared queries).
- **Recent form** (top of the Trends tab on player and goalie pages): the season next to the last 20, 10 and 5 games (or
  appearances) with a "vs season" column, fantasy points per game under your scoring for skaters, and a rolling points-per-game
  (skaters) or save % (goalies) trend line with a 3, 5, 10 or 20-game window. It is computed in the browser from the game log
  the page already loads (`frontend/src/rolling.js`); windows longer than the games played are hidden. Power-play bonus and
  game-winning-goal scoring can't be included, since game logs don't carry them.
- **Streaming goalies** (Fantasy → Streaming goalies): goalies to pick up for the next 3 to 10 days. Each game is weighted by the
  goalie's chance to start it (the starter model above, confirmed by the NHL near game time), and what a start is worth comes from the
  two teams' ratings: expected goals against from the opponent's offense and the goalie's own team's defense, win chance from the
  standard hockey rule that win odds go with the square of the goals ratio, saves from the implied shots, shutout chance from the
  Poisson chance of no goals (`backend/streaming.py` documents the model and its assumptions). The goalie's own record barely
  counts, because a goalie's results barely repeat from year to year. It scores points under your scoring, or a z-score across the goalie
  categories in a category league. It can't see who is available in your league. `/api/streaming/goalies` supplies the plan.
- **Matchups** (`/matchups`, under More): each team's schedule strength over the next few days (games and how soft or tough each
  opponent is, for skaters or for goalies) and every team's rating as an opponent. Ratings come from expected goals, not goals: a
  backtest on four past seasons found early-season goals against predicts the rest of the season worse than assuming the league
  average, while xG against pulled toward the league average by 20 games' worth cuts the error about 10%. A goalie's effect is
  pulled much harder toward average (his saved goals barely repeat year to year). The Fantasy "This week" tab tags each of your
  players' games soft or tough and shows the week's average. `backend/matchups.py` documents the method; differences between teams
  are modest, so it is a tiebreaker, not a verdict.
- **Role changes** (a Role panel on the skater page's Advanced tab, a "Moving up" tab on Home, and the full list at `/roles`, which is linked from
  that Home card rather than the menu): who has moved up or down the power-play units and who is playing more or less over their last
  few games compared with earlier this season, from the NHL's per-game ice time by situation (`skater_game_toi`, one request a
  night). A skater's unit comes from their share of the team's power-play time (45%+ is PP1, 15%+ is PP2); `backend/roles.py`
  explains the method and its limits. Rostered skaters get a small badge on the Fantasy page.
- **Past seasons on Skaters and Goalies**: the Season picker above each leaderboard shows any season since 2005-06. Those seasons are
  loaded once with `python ingest.py backfill-seasons` from `backend/` (about 20 minutes; it skips seasons already stored, so it is safe to
  re-run, and takes a list such as `20232024,20242025`). They carry the NHL's full-season totals and rates only: pace, last-N-games form
  and expected goals need game-by-game data, so those columns are hidden for past seasons. A finished season is never refreshed, so the
  last nightly run of a season is its final state.
- **Country flags** on player pages are small PNGs in `frontend/public/flags/` (about 30 KB for all 82 countries, from flagcdn.com), so
  nothing is fetched from an outside site. A country the NHL lists that has no file there simply shows no flag; add it to
  `frontend/src/countries.js` and drop the matching `<two-letter code>.png` into that folder.
- **Trophy winners** (`/trophy`, under More): every NHL trophy with its winners by season (`/trophy/<id>`), linked from the Awards table on
  each player page. Winners come live from the NHL's records site (cached a day by `backend/trophies.py` and `api.py`). Only the Art Ross
  and Rocket Richard show stats (the winner's season totals); the other awards are voted or team-based and list winners and teams only.
- **Game page extras**: "Lines and pairings" lists each team's five-on-five forward lines and defense pairs for the game, most-used first
  (combinations under a minute are left out), with ice time, shot attempts for and against, CF% and goals. The defense pairs are the rows
  of `pair_game` where both players are defensemen, since that table holds every two skaters who shared the ice. The shot map (game, team
  and player pages) has a Period filter (1st, 2nd, 3rd, overtime) next to the strength filter.
- **Head-to-head** (`/head-to-head`, under More, and linked from every game page): team-vs-team results, a skater's scoring against a
  team, and a goalie's save percentage against a team, since 2005-06. This season and the previous four come from the games we store
  (past seasons are paired into opponents by `ingest_team_abbrevs`); earlier seasons come from `game_hist`, each club's season
  schedule, loaded once by `python ingest.py backfill-games-hist` from `backend/` (resumable; about 540 requests), and from a player's
  NHL game logs, fetched and stored the first time someone looks that player up (`oldgames.py`, `oldgames_db.py`). The Coyotes' games
  count toward Utah and the Thrashers' toward Winnipeg. When a new season starts, the oldest stored season falls into the older group
  and the `backfill-games-hist` command needs another run to pick it up (the lookups for individual players also won't include it until
  their stored games are refetched).
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
  each rostered player (with a likely-starter guess for goalies), who's hot and who's missing games, role changes (power-play
  moves and ice-time shifts over the last 5 games) and a luck check, at most once per Eastern
  day, using the same SMTP settings as password reset. Preview without sending: `.venv/bin/python digest.py --dry`, or
  `--preview 8478402,8480069` for a list of player ids. To send every morning, follow the steps at the top of `backend/com.hockeystats.digest.plist.example` (a launchd template with
  the SMTP settings and an 8:00 AM schedule; logs in `backend/logs/digest.log`).
- **Playoff odds** (Standings → Playoff odds): Monte Carlo over the remaining schedule (`backend/playoff_odds.py`; the model and its
  knobs are described at the top of that file). **Schedule grid** (`/schedule`, under More): games per team per week, with light
  weeks, heavy weeks and back-to-backs marked. Both need the full-season schedule, which the nightly ingest now loads.
- **Trophy races** (`/trophies`): top-5 contenders for the stat-driven awards (Art Ross, Richard, Norris, Calder, Vezina).
- **Live scores** on the home page come straight from the NHL scoreboard (cached 20s); everything else is from the nightly ingest.
- The footer shows when stats were last refreshed and warns if the nightly job looks like it missed a run.

## Layout

`backend/`:
- `ingest.py` (all data loading, including the manual `backfill-*` commands), `api.py` (all endpoints), `schema.sql`.
- On-ice and shot math: `corsi.py`, `shots.py`, `html_shifts.py`. Tracking: `edge.py`.
- One module per analysis, each with the method in its docstring: `luck.py` / `luck_db.py` (luck and regression), `roles.py` /
  `roles_db.py` (role changes), `matchups.py` / `matchups_db.py` (matchup quality), `streaming.py` (streaming goalies), `era.py`,
  `defense.py`, `trajectory.py`, `headtohead.py`, `probable_goalies.py`, `playoff_odds.py`. The `*_db.py` files hold the queries; the
  rest is pure logic with tests in `tests/`.
- `analysis/`: the backtests behind the prior weights and ratings (run from `backend/`, e.g.
  `.venv/bin/python -I analysis/backtest_team_ratings.py`; they need the stored game logs and, for some, `backfill-shots`).

`frontend/src/`: `pages/` (one per route) and `components/`. Fantasy logic that runs in the browser, each with tests (`npm test`):
`value.js` (points-league value), `categories.js` / `categoryDefs.js` (category-league value), `streaming.js`, `rolling.js` (recent form).
