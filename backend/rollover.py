"""Season rollover: the one command to run when a new NHL season starts (each October).

    .venv/bin/python rollover.py 20272028 --dry-run     # look, change nothing
    .venv/bin/python rollover.py 20272028               # do it (takes hours: the EDGE pass alone is most of it)

What it does, in order, and why:
 1. Checks the season that just finished really is finished and complete in the database (every game final, a full schedule).
    The nightly job must have run after its last game, or its final numbers are not stored. --force skips this.
 2. Changes the default SEASON_ID in config.py to the new season. The launchd jobs set no SEASON_ID of their own, so this edit is
    what makes tonight's run (and the API after a restart) follow the new season. The SEASON_ID environment variable still wins.
 3. Runs the regular ingest once. With the new SEASON_ID it fetches the finished season's game-by-game history (team_game_hist,
    skater_game_hist), team abbreviations and home flags, which the nightly job only loads for seasons already past.
 4. Runs the backfills that settle the finished season, all resumable, so a run that is cut short can simply be run again:
    games-hist (head-to-head: the oldest stored season falls into the older group), shots, shot-locations, shot-times,
    leagues (every player of the finished season's league history, fetched again so the season's rows hold final totals, plus any
    rookies; then `nhle` refits the NHLe league factors with the season's new pairs), onice (about an hour) and edge (hours; the
    EDGE speed extras refresh only weekly during a season, so this is their final pass).
 5. Clears the per-player old-games markers so a head-to-head lookup refetches with the moved boundary.
 6. Checks the history tables for the finished season and prints what is left for you to do by hand.

Everything it does is safe to repeat. It never touches git: commit config.py yourself.
"""
import argparse
import os
import re
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
SEASON_LINE = re.compile(r'(SEASON_ID = int\(os\.environ\.get\("SEASON_ID", ")(\d{8})("\)\))')

# name, command arguments, what it settles. The arguments are an ingest.py command, or a script when the first one ends in .py (run
# isolated, from backend/). "{finished}" in an argument becomes the id of the season that just finished.
# Order matters: shots before the passes that annotate them, leagues before the NHLe fit that reads them.
STEPS = [
    ("ingest", [], "regular ingest with the new season: history tables, abbreviations, home flags"),
    ("games-hist", ["backfill-games-hist"], "head-to-head results for the seasons that just left the stored window"),
    ("shots", ["backfill-shots"], "every shot with its xG for the finished season"),
    ("shot-locations", ["backfill-shot-locations"], "shot locations, types and rebounds for those shots"),
    ("shot-times", ["backfill-shot-times"], "period, game time and shooting side for those shots"),
    ("leagues", ["backfill-leagues", "--refresh", "{finished}"], "league records of the finished season's players at their final totals, plus rookies (about 15 minutes)"),
    ("nhle", ["analysis/nhle_factors.py", "--save"], "refit the NHLe league factors and age multipliers with the finished season's pairs"),
    ("onice", ["backfill-onice"], "5v5 on-ice shot attempts and xG for the finished season (about an hour)"),
    ("edge", ["backfill-edge"], "NHL EDGE tracking final numbers (hours)"),
]
STEP_NAMES = [s[0] for s in STEPS] + ["markers"]


def parse_season(text):
    """The season id as an int from '20272028'; raises ValueError unless it is eight digits and the second year follows the first."""
    if not re.fullmatch(r"\d{8}", text or ""):
        raise ValueError(f"{text!r} is not a season id like 20272028")
    first, second = int(text[:4]), int(text[4:])
    if second != first + 1:
        raise ValueError(f"{text} is not two consecutive years")
    return int(text)


def previous_season(season):
    return season - 10001


def rewrite_config(text, new):
    """(new config text, old default) with the SEASON_ID default changed to `new`. Raises ValueError if the line is not found."""
    m = SEASON_LINE.search(text)
    if not m:
        raise ValueError("could not find the SEASON_ID default in config.py")
    return SEASON_LINE.sub(lambda mm: f"{mm.group(1)}{new}{mm.group(3)}", text, count=1), int(m.group(2))


def check_finished(total, final, expected, stats_current=True):
    """Problems with the season that just ended, from its stored game count, how many are final, the schedule length it should have
    (config.regular_season_games) and whether its player stats were refreshed after the last game (None when unknown). Empty when it
    looks complete."""
    problems = []
    if total == 0:
        return ["no games are stored for the season that just ended"]
    if final < total:
        problems.append(f"{total - final} of {total} games are not final yet: the season is not over, or the last nightly ingest has not run")
    if total != expected:
        problems.append(f"{total} games are stored but a full season is {expected}")
    if stats_current is False:
        problems.append("the season's player stats were last refreshed before its final game: run the nightly ingest once more first")
    return problems


def check_history(counts, expected):
    """Warnings from the finished season's history counts: {team_rows, skater_games, shot_games, onice_games}."""
    want = {"team_rows": 2 * expected, "skater_games": expected, "shot_games": expected, "onice_games": expected}
    return [f"{k}: {counts.get(k, 0)} of the expected {v}" for k, v in want.items() if (counts.get(k) or 0) < v]


def plan(skip=(), only=None):
    """The step names to run, in order. only keeps just that one; skip drops the named ones."""
    names = [only] if only else list(STEP_NAMES)
    return [n for n in names if n not in skip]


# ---- database ---------------------------------------------------------------------------------------------
def season_status(conn, season):
    """(games stored, games final, whether player stats were refreshed after the last game or None if there are none)."""
    row = conn.execute("SELECT count(*), count(*) FILTER (WHERE state IN ('OFF', 'FINAL')), max(game_date) FROM game WHERE season_id = %s", (season,)).fetchone()
    refreshed = conn.execute("SELECT max(updated_at) FROM skater_season WHERE season_id = %s", (season,)).fetchone()[0]
    current = None if refreshed is None or row[2] is None else refreshed.date() > row[2]
    return row[0], row[1], current


def history_counts(conn, season):
    one = lambda sql: conn.execute(sql, (season,)).fetchone()[0]
    return {
        "team_rows": one("SELECT count(*) FROM team_game_hist WHERE season_id = %s"),
        "skater_games": one("SELECT count(DISTINCT game_id) FROM skater_game_hist WHERE season_id = %s"),
        "shot_games": one("SELECT count(DISTINCT game_id) FROM shot_hist WHERE season_id = %s"),
        "onice_games": one("SELECT count(DISTINCT game_id) FROM skater_game_onice WHERE season_id = %s"),
    }


def step_command(args, season):
    """The command line for a step (see STEPS): ingest.py with these arguments, or the script named first, run isolated. Every
    "{finished}" becomes the id of the season before `season`, the new one."""
    args = [a.replace("{finished}", str(previous_season(season))) for a in args]
    if args and args[0].endswith(".py"):
        return [sys.executable, "-u", "-I", *args]
    return [sys.executable, "-u", "ingest.py", *args]


def run_step(name, args, season, log):
    """Run one step with SEASON_ID set to the new season, copying its output to the screen and the log. Returns its exit code."""
    env = {**os.environ, "SEASON_ID": str(season), "PYTHONUNBUFFERED": "1"}
    proc = subprocess.Popen(step_command(args, season), cwd=HERE, env=env,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    for line in proc.stdout:
        sys.stdout.write("    " + line)
        log.write(line)
    return proc.wait()


def main(argv=None):
    ap = argparse.ArgumentParser(description="Roll the site over to a new NHL season.")
    ap.add_argument("season", help="the NEW season id, e.g. 20272028")
    ap.add_argument("--dry-run", action="store_true", help="check and print the plan, change nothing")
    ap.add_argument("--skip", default="", help="comma-separated steps to leave out: " + ", ".join(STEP_NAMES))
    ap.add_argument("--only", choices=STEP_NAMES, help="run just this step (the config edit still happens if it is pending)")
    ap.add_argument("--force", action="store_true", help="go ahead even if the finished season looks incomplete")
    args = ap.parse_args(argv)
    try:
        new = parse_season(args.season)
    except ValueError as e:
        ap.error(str(e))
    skip = {s.strip() for s in args.skip.split(",") if s.strip()}
    bad = skip - set(STEP_NAMES)
    if bad:
        ap.error("unknown step(s) in --skip: " + ", ".join(sorted(bad)))
    old = previous_season(new)

    import psycopg
    import config
    text = (HERE / "config.py").read_text()
    _, configured = rewrite_config(text, new)
    if configured not in (old, new):
        print(f"config.py says {configured}, so it is not rolling from {old} to {new}. Nothing changed.")
        return 2
    steps = plan(skip, args.only)

    with psycopg.connect(config.DATABASE_URL) as conn:
        total, final, stats_current = season_status(conn, old)
    expected = config.regular_season_games(old)
    problems = check_finished(total, final, expected, stats_current)
    print(f"Season rollover {old} -> {new}")
    print(f"  finished season {old}: {total} games stored, {final} final")
    for p in problems:
        print(f"  PROBLEM: {p}")
    print(f"  config.py default SEASON_ID: {configured} " + ("(will change)" if configured == old else "(already changed)"))
    print("  plan: " + ", ".join(steps))
    for name, _, why in STEPS:
        if name in steps:
            print(f"    {name:15s} {why}")
    if "markers" in steps:
        print(f"    {'markers':15s} clear the per-player old-games markers so head-to-head refetches")
    if args.dry_run:
        print("Dry run: nothing changed.")
        return 1 if problems else 0
    if problems and not args.force:
        print("Not going ahead. Fix that (run the nightly ingest, or wait for the season to end) or pass --force.")
        return 1

    if configured == old:
        new_text, _ = rewrite_config(text, new)
        (HERE / "config.py").write_text(new_text)
        print(f"config.py: SEASON_ID default {old} -> {new}")
    (HERE / "logs").mkdir(exist_ok=True)
    log_path = HERE / "logs" / f"rollover-{time.strftime('%Y%m%d-%H%M%S')}.log"
    print(f"Log: {log_path}")
    started = time.time()
    with open(log_path, "a") as log:
        for name in steps:
            t0 = time.time()
            print(f"=== {name} ({time.strftime('%H:%M:%S')})", flush=True)
            log.write(f"=== {name}\n")
            if name == "markers":
                with psycopg.connect(config.DATABASE_URL) as conn:
                    n = conn.execute("SELECT count(*) FROM player_game_old_fetched").fetchone()[0]
                    conn.execute("DELETE FROM player_game_old_fetched")
                print(f"    cleared {n} markers")
                continue
            args_for = dict((s[0], s[1]) for s in STEPS)[name]
            rc = run_step(name, args_for, new, log)
            print(f"=== {name} finished in {(time.time() - t0) / 60:.1f} min (exit {rc})", flush=True)
            if rc != 0:
                print(f"Stopped at {name}. Every step is resumable: fix the cause and run the same command again.")
                return rc
    with psycopg.connect(config.DATABASE_URL) as conn:
        counts = history_counts(conn, old)
    print(f"\nDone in {(time.time() - started) / 3600:.1f} h. Finished season {old} history: " + ", ".join(f"{k} {v}" for k, v in counts.items()))
    for w in check_history(counts, expected):
        print(f"  WARNING: {w}")
    print("Still to do by hand:\n  - restart the API (uvicorn) so it reads the new SEASON_ID\n"
          "  - commit config.py\n  - optionally refit the xG model on the finished season: train_xg_fetch.py, then train_xg.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
