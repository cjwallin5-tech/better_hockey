"""Daily roster digest: today's games for each rostered player, who's hot, who's missing games.

Run it each morning (run_digest.sh). Only accounts that turned the digest on (Account page) get it, at
most once per Eastern-time day. Usage:
    python digest.py                 send to everyone who is due
    python digest.py --dry           print what would be sent, send nothing
    python digest.py --preview 8478402,8480069   print a digest for these player ids (no account needed)
"""
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

import psycopg
from psycopg.rows import dict_row

import api
import config
import mail

ET = ZoneInfo("America/New_York")
HOT_MIN_GAMES = 5      # recent games needed before a hot streak means anything
HOT_RATIO = 1.25       # recent pace at least this much above the season pace
HOT_MAX = 3
MISSING_GAMES = 2      # team games in a row without playing before we flag it


def _roster_rows(conn, ids):
    skaters = {r["player_id"]: r for r in conn.execute(api.SKATERS_SQL, {
        "season": config.SEASON_ID, "window": config.RECENT_WINDOW, "games": config.GAMES_PER_SEASON}).fetchall()
        if r["player_id"] in ids}
    goalies = {r["player_id"]: r for r in conn.execute(api.GOALIES_SQL, api._goalie_params()).fetchall()
               if r["player_id"] in ids}
    return skaters, goalies


def gather(conn, players):
    """players: [{id, kind, name}] -> what today's email is made of."""
    players = list({p["id"]: p for p in players}.values())
    ids = {p["id"] for p in players}
    skaters, goalies = _roster_rows(conn, ids)
    today = conn.execute("SELECT (now() AT TIME ZONE 'America/New_York')::date AS d").fetchone()["d"]
    games = conn.execute(
        "SELECT game_id, start_time, home, away FROM game WHERE season_id = %s AND game_date = %s ORDER BY start_time",
        (config.SEASON_ID, today)).fetchall()
    by_team = {}
    for g in games:
        by_team[g["home"]] = {"opp": g["away"], "home": True, "start": g["start_time"]}
        by_team[g["away"]] = {"opp": g["home"], "home": False, "start": g["start_time"]}

    # likely starters from the probable-goalies model, for rostered goalies
    likely = {}
    for g in api.probable_goalies_endpoint()["games"]:
        for side in (g["away_goalies"], g["home_goalies"]):
            for c in side["candidates"]:
                likely[c["player_id"]] = (c["probability"], side["confirmed"])

    playing, idle, hot, watch = [], [], [], []
    for p in players:
        row = skaters.get(p["id"]) or goalies.get(p["id"])
        if not row:
            continue
        team = (row["team"] or "").split(",")[-1]
        game = by_team.get(team)
        entry = {"name": row.get("name") or p["name"], "team": team, "kind": p["kind"], "game": game}
        if p["kind"] == "goalie":
            entry["start"] = likely.get(p["id"])
        (playing if game else idle).append(entry)
        if p["id"] in skaters:
            if (row["recent_games"] or 0) >= HOT_MIN_GAMES and row["point_pace"] and row["recent_pace"] \
                    and row["recent_pace"] >= HOT_RATIO * row["point_pace"]:
                hot.append({"name": row["name"], "recent_points": row["recent_points"], "recent_games": row["recent_games"],
                            "recent_pace": row["recent_pace"], "pace": row["point_pace"]})
            if row["games_out"] >= MISSING_GAMES:
                watch.append(f"{row['name']} ({team}) hasn't played in the last {row['games_out']} team games.")
            elif row["traded"]:
                watch.append(f"{row['name']} has played for more than one team this season ({row['team']}).")
    hot.sort(key=lambda h: h["recent_pace"] - h["pace"], reverse=True)
    return {"today": today, "roster_size": len(playing) + len(idle), "playing": playing, "idle": idle,
            "hot": hot[:HOT_MAX], "watch": watch}


def render(d):
    """(subject, plain-text body), or None when there is nothing worth an email."""
    if not (d["playing"] or d["hot"] or d["watch"]):
        return None
    lines = [f"Your NHL roster for {d['today']:%A, %B %-d}", ""]
    if d["playing"]:
        lines.append(f"TODAY: {len(d['playing'])} of {d['roster_size']} players have a game")
        for e in sorted(d["playing"], key=lambda e: e["game"]["start"] or datetime.max.replace(tzinfo=ET)):
            g = e["game"]
            when = g["start"].astimezone(ET).strftime("%-I:%M %p ET") if g["start"] else "time TBD"
            note = ""
            if e["kind"] == "goalie" and e.get("start"):
                prob, confirmed = e["start"]
                note = " - confirmed starter" if confirmed else f" - likely starter ({round(prob * 100)}%, a guess)"
            elif e["kind"] == "goalie":
                note = " - starter unclear"
            lines.append(f"  {e['name']} ({e['team']}) {'vs' if g['home'] else '@'} {g['opp']}, {when}{note}")
        lines.append("")
    if d["idle"]:
        lines += ["NO GAME TODAY: " + ", ".join(e["name"] for e in d["idle"]), ""]
    if d["hot"]:
        lines.append("HOT")
        for h in d["hot"]:
            lines.append(f"  {h['name']}: {h['recent_points']} points in the last {h['recent_games']} games "
                         f"(a {h['recent_pace']:.0f}-point pace vs {h['pace']:.0f} for the season)")
        lines.append("")
    if d["watch"]:
        lines += ["WATCH"] + [f"  {w}" for w in d["watch"]] + [""]
    lines.append(f"Turn this email off any time: {config.PUBLIC_URL}/account")
    subject = f"NHL roster: {len(d['playing'])} of {d['roster_size']} play today" if d["playing"] else "NHL roster update"
    return subject, "\n".join(lines)


def due_users(conn):
    return conn.execute(
        """SELECT u.id, u.email, f.players, p.last_sent_on
           FROM digest_pref p JOIN app_user u ON u.id = p.user_id JOIN fantasy_state f ON f.user_id = u.id
           WHERE p.enabled AND jsonb_array_length(f.players) > 0
             AND (p.last_sent_on IS NULL OR p.last_sent_on < (now() AT TIME ZONE 'America/New_York')::date)""").fetchall()


def main(argv):
    dry = "--dry" in argv
    with psycopg.connect(config.DATABASE_URL, row_factory=dict_row) as conn:
        if "--preview" in argv:
            ids = [int(i) for i in argv[argv.index("--preview") + 1].split(",")]
            skaters, goalies = _roster_rows(conn, set(ids))
            players = [{"id": i, "kind": "skater" if i in skaters else "goalie", "name": str(i)} for i in ids]
            out = render(gather(conn, players))
            print(out[0] + "\n\n" + out[1] if out else "(nothing to send)")
            return 0
        sent = skipped = 0
        for u in due_users(conn):
            out = render(gather(conn, u["players"]))
            if out is None:
                skipped += 1
                continue
            if dry:
                print(f"--- would send to {u['email']}\n{out[0]}\n\n{out[1]}\n")
                continue
            if not config.SMTP_HOST:
                print("SMTP_HOST is not set, so nothing can be sent. Use --dry to preview.")
                return 1
            if mail.send(u["email"], *out):
                conn.execute("UPDATE digest_pref SET last_sent_on = (now() AT TIME ZONE 'America/New_York')::date "
                             "WHERE user_id = %s", (u["id"],))
                conn.commit()
                sent += 1
            else:
                print(f"failed to send to {u['email']}")
        print(f"digest: sent {sent}, nothing to say for {skipped}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
