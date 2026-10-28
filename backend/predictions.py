"""A forward-looking record of the site's predictions, for the owner's Accuracy page.

accuracy.py replays the season after the fact. This module is the honest version: every morning (after the nightly ingest) it stores
the win chance and the probable goalie for each game that has not started, exactly as the Tonight page shows them, and the first
stored value is never overwritten. Once a game is final, `resolve` fills in what happened. `report` then scores only these logged
predictions, so nothing was fitted or tuned with the result in view.

    python predictions.py            # grade finished games, then log today's (what run_ingest.sh runs)
    python predictions.py log        # only log
    python predictions.py resolve    # only grade
"""
import sys

import psycopg
from psycopg.rows import dict_row

import accuracy
import config

DDL = """
CREATE TABLE IF NOT EXISTS prediction_log (
    kind       TEXT NOT NULL,                  -- 'win' (subject = home team) or 'goalie' (subject = the team in goal)
    game_id    BIGINT NOT NULL,
    subject    TEXT NOT NULL,
    season_id  INT NOT NULL,
    game_date  DATE NOT NULL,
    made_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    p          DOUBLE PRECISION NOT NULL,      -- win: home win chance; goalie: the top pick's chance
    pick       BIGINT,                         -- goalie: the top pick's player id
    confirmed  BOOLEAN NOT NULL DEFAULT false, -- goalie: the NHL had already confirmed the starter
    outcome    BOOLEAN,                        -- win: home won; goalie: the top pick started. NULL until the game is final
    actual     BIGINT,                         -- goalie: who actually started
    PRIMARY KEY (kind, game_id, subject)
);
"""


def init_db():
    with psycopg.connect(config.DATABASE_URL) as conn:
        conn.execute(DDL)


# --- Pure helpers (tested without a database) ----------------------------------------------------------

def rows_from_tonight(games):
    """Prediction rows from /api/tonight's games, skipping games that have started and predictions the model could not make."""
    out = []
    for g in games:
        if g["state"] not in ("FUT", "PRE"):
            continue
        if g.get("home_win") is not None:
            out.append({"kind": "win", "game_id": g["game_id"], "subject": g["home"], "p": g["home_win"], "pick": None, "confirmed": False})
        for side in ("home", "away"):
            goalie = (g.get("goalies") or {}).get(side)
            if goalie and goalie.get("player_id") is not None and goalie.get("probability") is not None:
                out.append({"kind": "goalie", "game_id": g["game_id"], "subject": goalie["team"], "p": goalie["probability"],
                            "pick": goalie["player_id"], "confirmed": bool(goalie["confirmed"])})
    return out


def grade(row, game, starter):
    """(outcome, actual) for one logged prediction given its final game and the team's starting goalie id (or None).
    outcome is None when it cannot be graded yet."""
    if row["kind"] == "win":
        if game["home_score"] is None or game["away_score"] is None:
            return None, None
        return game["home_score"] > game["away_score"], None
    if starter is None:
        return None, None
    return row["pick"] == starter, starter


def report(rows):
    """Scores for graded rows ({kind, game_date, p, outcome, confirmed}), the shape the Accuracy page shows."""
    wins = [r for r in rows if r["kind"] == "win" and r["outcome"] is not None]
    goalies = [r for r in rows if r["kind"] == "goalie" and r["outcome"] is not None]
    win_preds = [(r["p"], 1 if r["outcome"] else 0) for r in wins]
    coin = [(0.5, y) for _, y in win_preds]
    out = {"win": {"games": len(wins), "from": min((r["game_date"] for r in wins), default=None),
                   "to": max((r["game_date"] for r in wins), default=None),
                   "model": accuracy.summarize(win_preds), "coin": accuracy.summarize(coin),
                   "vs_coin": accuracy.paired([accuracy.brier(p, y) for p, y in win_preds], [accuracy.brier(p, y) for p, y in coin]),
                   "calibration": accuracy.calibration(win_preds)}}
    n = len(goalies)
    unconfirmed = [r for r in goalies if not r["confirmed"]]
    out["goalie"] = {"games": n, "from": min((r["game_date"] for r in goalies), default=None),
                     "to": max((r["game_date"] for r in goalies), default=None),
                     "top_correct": sum(1 for r in goalies if r["outcome"]) / n if n else None,
                     "top_correct_unconfirmed": sum(1 for r in unconfirmed if r["outcome"]) / len(unconfirmed) if unconfirmed else None,
                     "unconfirmed": len(unconfirmed),
                     "calibration": accuracy.calibration([(r["p"], 1 if r["outcome"] else 0) for r in unconfirmed],
                                                         edges=(0.0, 0.5, 0.6, 0.7, 0.8, 0.9, 1.01))}
    return out


# --- Database work -------------------------------------------------------------------------------------

def log_today(conn=None):
    """Store predictions for today's games that have not started. Returns the number of new rows."""
    import api            # late import: importing api builds the whole app, and api imports this module

    games = api.tonight_endpoint()
    day = games["date"]
    new = 0
    own = conn is None
    conn = conn or psycopg.connect(config.DATABASE_URL, row_factory=dict_row)
    try:
        for r in rows_from_tonight(games["games"]):
            cur = conn.execute(
                """INSERT INTO prediction_log (kind, game_id, subject, season_id, game_date, p, pick, confirmed)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s) ON CONFLICT DO NOTHING""",
                (r["kind"], r["game_id"], r["subject"], config.SEASON_ID, day, r["p"], r["pick"], r["confirmed"]))
            new += cur.rowcount
        conn.commit()
    finally:
        if own:
            conn.close()
    return new


def resolve(conn=None):
    """Grade logged predictions whose games are now final. Returns the number graded."""
    own = conn is None
    conn = conn or psycopg.connect(config.DATABASE_URL, row_factory=dict_row)
    graded = 0
    try:
        pending = conn.execute(
            """SELECT p.kind, p.game_id, p.subject, p.pick, g.home_score, g.away_score FROM prediction_log p
               JOIN game g ON g.game_id = p.game_id WHERE p.outcome IS NULL AND g.state IN ('OFF', 'FINAL')""").fetchall()
        for row in pending:
            starter = None
            if row["kind"] == "goalie":
                s = conn.execute(
                    """SELECT player_id FROM goalie_game WHERE game_id = %s AND team = %s AND started
                       ORDER BY toi_sec DESC NULLS LAST LIMIT 1""", (row["game_id"], row["subject"])).fetchone()
                starter = s["player_id"] if s else None
            outcome, actual = grade(row, row, starter)
            if outcome is None:
                continue
            conn.execute("UPDATE prediction_log SET outcome = %s, actual = %s WHERE kind = %s AND game_id = %s AND subject = %s",
                         (outcome, actual, row["kind"], row["game_id"], row["subject"]))
            graded += 1
        conn.commit()
    finally:
        if own:
            conn.close()
    return graded


def load_report():
    with psycopg.connect(config.DATABASE_URL, row_factory=dict_row) as conn:
        rows = conn.execute("SELECT kind, game_date, p, outcome, confirmed, actual FROM prediction_log WHERE season_id = %s",
                            (config.SEASON_ID,)).fetchall()
        logged = conn.execute("SELECT count(*) AS n, min(game_date) AS since FROM prediction_log WHERE season_id = %s",
                              (config.SEASON_ID,)).fetchone()
    return {"logged": logged["n"], "since": logged["since"], **report(rows)}


def main(argv):
    init_db()
    what = argv[0] if argv else "all"
    if what in ("resolve", "all"):
        print(f"graded {resolve()} predictions")
    if what in ("log", "all"):
        print(f"logged {log_today()} new predictions")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
