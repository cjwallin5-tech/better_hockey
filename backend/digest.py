"""Daily roster digest (on Sundays it opens with the week-ahead lineup from weekly.py): today's games for each rostered player, who's hot, who's missing games, plus a section for
the players, prospects and teams on the user's watchlist (games, hot/cold, role changes, nearby milestones, how a prospect's
season is going and when one reaches the NHL). Rostered players who are
scoring above what their shots predict come up as sell-high ideas, and good players elsewhere scoring below it as buy-low
ideas (tradewatch.py); the rest of the roster's luck flags stay in the luck check.

Run it each morning (run_digest.sh). Only accounts that turned the digest on (Account page) get it, at
most once per Eastern-time day. Usage:
    python digest.py                 send to everyone who is due
    python digest.py --dry           print what would be sent, send nothing
    add --sunday to --dry or --preview to include the Sunday week-ahead section whatever the day is
    python digest.py --preview 8478402,8480069   print a digest for these player ids (no account needed)
"""
import sys
import time
from datetime import datetime
from zoneinfo import ZoneInfo

import psycopg
from psycopg.rows import dict_row

import api
import absences_db
import config
import fatigue
import luck_db
import mail
import prospects
import roles_db
import tradewatch
import weekly

ET = ZoneInfo("America/New_York")
HOT_MIN_GAMES = 5      # recent games needed before a hot streak means anything
HOT_RATIO = 1.25       # recent pace at least this much above the season pace
HOT_MAX = 3
MISSING_GAMES = 2      # team games in a row without playing before we flag it
LUCK_MAX = 4           # most luck-check lines in one email, biggest gaps first
ROLE_WINDOW = 5        # games compared with the rest of the season for role changes
ROLE_MAX = 4           # most role-change lines in one email, biggest moves first
MILESTONE_SOON = 10    # a watched player this many games (at the current pace) from a career milestone is worth a line
MILESTONE_RECENT_DAYS = 2  # a milestone reached this recently still gets a line
MILESTONE_MAX = 6      # most milestone lines in one email
SEND_ATTEMPTS = 5      # tries per email; waits 30s, 60s, 90s, 120s between them
SEND_WAIT_SECONDS = 30


REST_NOTES = {
    "tired": "second night of a back-to-back vs a rested team",
    "edge": "opponent is on the second night of a back-to-back",
}


def rest_note(game):
    """' - ...' when the game's rest favors one side (see fatigue.py), else an empty string. Teams on the tired side
    average about 0.4 goals a game worse in our data."""
    text = REST_NOTES.get(game.get("rest"))
    return f" - {text}" if text else ""


def todays_rest(conn, today):
    """{team: 'tired' | 'edge'} for today's games where one side played yesterday and the other is rested."""
    import api   # the rows are built there; imported late so tests of the pure parts don't need the API
    _, current, _ = api._team_games(conn, with_past=False)
    rest = fatigue.rest_days(current)
    out = {}
    for r in current:
        if r["game_date"] == today:
            k = fatigue.kind(rest[r["team"], r["game_id"]], rest.get((r["opponent"], r["game_id"]), fatigue.FIRST_GAME_REST))
            if k in REST_NOTES:
                out[r["team"]] = k
    return out


def _mmss(seconds):
    return f"{int(round(seconds)) // 60}:{int(round(seconds)) % 60:02d}"


def role_alerts(conn, players):
    """Rostered skaters whose power-play unit or even-strength ice time moved over their last ROLE_WINDOW games
    (see roles.py), biggest moves first. Each is a dict ready for render()."""
    ids = [p["id"] for p in players if p["kind"] == "skater"]
    if not ids:
        return []
    lines = [r for r in roles_db.player_lines(conn, config.SEASON_ID, ROLE_WINDOW, ids=ids).values() if r["direction"]]
    # same scale as the Role changes page: a power-play move outweighs even-strength time
    lines.sort(key=lambda r: abs(r["pp_share_delta"] * 10 + r["ev_delta"] / 300), reverse=True)
    return [{"name": r["name"], "team": r["team"], "window": r["window"], "pp_change": r["pp_change"],
             "pp_label": r["pp_label"], "pp_base": r["pp_base"], "pp": r["pp"], "ev_change": r["ev_change"],
             "ev_base": r["ev_base"], "ev": r["ev"]} for r in lines[:ROLE_MAX]]


def league_luck(conn):
    """Luck rows for every skater and goalie, fetched once per run and shared by every user's email."""
    return {"skaters": luck_db.skater_rows(conn, config.SEASON_ID, config.GAMES_PER_SEASON),
            "goalies": luck_db.goalie_rows(conn, config.SEASON_ID)}


def luck_alerts(league, players, hot=True, cold=True):
    """Players running well above or below what their shots predict (flagged by luck.py, with enough of a sample to
    mean something), biggest gaps first. `league` is league_luck(); hot and cold choose which directions to keep.
    Each is a dict ready for render()."""
    ids = {p["id"] for p in players}
    keep = {f for f, on in (("hot", hot), ("cold", cold)) if on}
    out = []
    for r in league["skaters"]:
        if r["player_id"] in ids and r["enough"] and r["points_flag_adj"] in keep:  # judged against the player's own history
            out.append({"name": r["name"], "kind": "skater", "flag": r["points_flag_adj"], "z": r["points_z_adj"],
                        "actual": r["points"], "expected": r["xpoints_adj"]})
    for r in league["goalies"]:
        if r["player_id"] in ids and r["enough"] and r["flag"] in keep:
            out.append({"name": r["name"], "kind": "goalie", "flag": r["flag"], "z": r["z"],
                        "actual": r["goals"], "expected": r["xga"]})
    out.sort(key=lambda a: abs(a["z"]), reverse=True)
    return out[:LUCK_MAX]


def _roster_rows(conn, ids):
    skaters = {r["player_id"]: r for r in conn.execute(api.SKATERS_SQL, {
        "season": config.SEASON_ID, "window": config.RECENT_WINDOW, "games": config.GAMES_PER_SEASON}).fetchall()
        if r["player_id"] in ids}
    goalies = {r["player_id"]: r for r in conn.execute(api.GOALIES_SQL, api._goalie_params()).fetchall()
               if r["player_id"] in ids}
    return skaters, goalies


def gather(conn, players, league=None, roster=True, watched=frozenset(), absent=None):
    """players: [{id, kind, name}] -> what today's email is made of. `league` is league_luck() (fetched here when
    omitted). roster=True is the user's own team: hot players there become sell-high lines and the league's cold
    stars not on the team become buy-low lines (`watched` ids come first); otherwise (watchlist players) every luck
    flag stays in the luck check. `absent` is absences_db.current() (fetched here when omitted)."""
    league = league or league_luck(conn)
    players = list({p["id"]: p for p in players}.values())
    ids = {p["id"] for p in players}
    skaters, goalies = _roster_rows(conn, ids)
    today = conn.execute("SELECT (now() AT TIME ZONE 'America/New_York')::date AS d").fetchone()["d"]
    games = conn.execute(
        "SELECT game_id, start_time, home, away FROM game WHERE season_id = %s AND game_date = %s ORDER BY start_time",
        (config.SEASON_ID, today)).fetchall()
    rest = todays_rest(conn, today)
    by_team = {}
    for g in games:
        by_team[g["home"]] = {"opp": g["away"], "home": True, "start": g["start_time"], "rest": rest.get(g["home"])}
        by_team[g["away"]] = {"opp": g["home"], "home": False, "start": g["start_time"], "rest": rest.get(g["away"])}

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
    out = {"today": today, "roster_size": len(playing) + len(idle), "playing": playing, "idle": idle,
           "hot": hot[:HOT_MAX], "watch": watch, "roles": role_alerts(conn, players),
           "luck": luck_alerts(league, players, hot=not roster), "sell": [], "buy": [],
           "absent": teammate_lines(absent if absent is not None else absences_db.current(conn, config.SEASON_ID), skaters) if roster else []}
    if roster:
        out["sell"] = tradewatch.sell_high(league["skaters"], league["goalies"], ids, config.GAMES_PER_SEASON)
        out["buy"] = tradewatch.buy_low(league["skaters"], ids, config.GAMES_PER_SEASON, watched)
    return out


ABSENT_MAX = 4          # most teammate-out lines in one email
ABSENT_MIN_SEC = 30     # seconds a game, seen or expected, for a teammate's gain to be worth a line


def mmss(seconds):
    return f"{'+' if seconds >= 0 else '-'}{abs(round(seconds)) // 60}:{abs(round(seconds)) % 60:02d}"


def teammate_lines(absent, skaters):
    """Lines about roster skaters whose teammate (a top-role regular) is out and who are playing more because of it: [{name, out, games,
    seen, expected}], biggest first. skaters: {player_id: season row} of the roster."""
    out = []
    for a in absent:
        for m in a["teammates"]:
            if m["player_id"] in skaters and m["player_id"] != a["player_id"]:
                seen = m["seen"] if m["seen"]["games"] >= absences_db.SEEN_MIN_GAMES else None
                gain = seen["total"] if seen else m["expected"]["total"]
                if gain >= ABSENT_MIN_SEC:
                    out.append({"name": m["name"], "out": a["name"], "out_team": a["team"], "games_out": a["games_out"], "role": a["role"],
                                "seen": m["seen"], "expected": m["expected"]})
    out.sort(key=lambda e: -(e["seen"]["total"] if e["seen"]["games"] >= absences_db.SEEN_MIN_GAMES else e["expected"]["total"]))
    return out[:ABSENT_MAX]


def absent_line(e):
    seen, exp = e["seen"], e["expected"]
    games = f"{e['games_out']} game{'s' if e['games_out'] != 1 else ''}"
    text = f"{e['name']}: {e['out']} ({e['out_team']}, {e['role'] if e['role'] != 'none' else 'top-minutes'} player) has missed {games}. "
    if seen["games"] >= absences_db.SEEN_MIN_GAMES:
        text += (f"{e['name']} is playing {mmss(seen['total'])} a game more since ({mmss(seen['ev'])} even strength, {mmss(seen['pp'])} power play); "
                 f"a teammate in his spot usually gains about {mmss(exp['total'])}.")
    else:
        text += f"A teammate in his spot usually gains about {mmss(exp['total'])} a game, but it has only been {games}."
    return text


def milestone_alerts(ms, ids, today):
    """Milestones for these player ids from api.milestones(): reached in the last MILESTONE_RECENT_DAYS days, or
    within MILESTONE_SOON games at the current pace. Reached ones first, then the nearest. Dicts ready for render()."""
    out = []
    for m in ms["reached"]:
        d = m.get("date")
        if m["player_id"] in ids and d and 0 <= (today - d).days < MILESTONE_RECENT_DAYS:
            out.append({"name": m["name"], "label": m["label"], "milestone": m["milestone"], "reached": True, "need": 0})
    soon = [m for m in ms["upcoming"] if m["player_id"] in ids and m["games_needed"] <= MILESTONE_SOON]
    soon.sort(key=lambda m: (m["games_needed"], m["remaining"]))
    for m in soon:
        out.append({"name": m["name"], "label": m["label"], "milestone": m["milestone"], "reached": False,
                    "remaining": m["remaining"], "need": m["games_needed"]})
    return out[:MILESTONE_MAX]


def prospect_alerts(conn, ids):
    """Watched prospects who are still prospects: this season's line, what changed lately and how it compares with last
    season (see prospects.py). Prospects who have reached the NHL are split out: ({ids...}, [alert dicts])."""
    if not ids:
        return set(), []
    skaters, goalies = _roster_rows(conn, set(ids))
    in_nhl = set(skaters) | set(goalies)
    people = conn.execute("SELECT * FROM prospect WHERE player_id = ANY(%s)", (list(ids),)).fetchall()
    seasons = {}
    for r in conn.execute("SELECT * FROM prospect_season WHERE player_id = ANY(%s) AND game_type = 2", (list(ids),)):
        seasons.setdefault(r["player_id"], []).append(r)
    now = datetime.now(ET)
    out = []
    for p in people:
        if p["player_id"] in in_nhl:
            continue
        mine = seasons.get(p["player_id"], [])
        out.append(prospects.alert(p, prospects.current_line(mine, config.SEASON_ID), mine, now, config.SEASON_ID))
    # recent movers first, then by name
    out.sort(key=lambda a: (a["change"] is None, a["name"]))
    return in_nhl, out


def gather_watch(conn, items, roster_ids, ms=None, league=None):
    """items: [{kind: 'player'|'prospect'|'team', ref, name}] from the user's watchlist. Players already on the roster are
    left to the roster sections. A watched prospect who has since reached the NHL is followed like a player, with a line
    saying so. Returns the same pieces as gather() for the watched players, plus `milestones`, `prospects` and `teams`
    (today's game for each watched team), or None when there is nothing to report on."""
    ids = {int(i["ref"]): i for i in items if i["kind"] == "player" and int(i["ref"]) not in roster_ids}
    prospect_ids = {int(i["ref"]): i for i in items if i["kind"] == "prospect" and int(i["ref"]) not in roster_ids}
    teams = [i["ref"] for i in items if i["kind"] == "team"]
    if not ids and not teams and not prospect_ids:
        return None
    in_nhl, prospect_list = prospect_alerts(conn, set(prospect_ids))
    called_up = {i: prospect_ids[i] for i in in_nhl if i not in ids}
    skaters, goalies = _roster_rows(conn, set(ids) | set(called_up))
    names = {**called_up, **ids}
    players = [{"id": i, "kind": "skater" if i in skaters else "goalie", "name": names[i]["name"]}
               for i in names if i in skaters or i in goalies]
    d = gather(conn, players, league, roster=False)
    d["milestones"] = milestone_alerts(ms, set(ids), d["today"]) if ms and ids else []
    d["prospects"] = prospect_list
    d["called_up"] = [prospects.called_up_line((skaters.get(i) or goalies[i])["name"], ((skaters.get(i) or goalies[i])["team"] or "").split(",")[-1],
                                               (skaters.get(i) or goalies[i])["games_played"], (skaters.get(i) or {}).get("points"),
                                               goalie=i in goalies and i not in skaters)
                      for i in called_up if i in skaters or i in goalies]
    games = conn.execute("SELECT home, away, start_time FROM game WHERE season_id = %s AND game_date = %s "
                         "ORDER BY start_time", (config.SEASON_ID, d["today"])).fetchall()
    by_team = {}
    for g in games:
        by_team[g["home"]] = {"opp": g["away"], "home": True, "start": g["start_time"]}
        by_team[g["away"]] = {"opp": g["home"], "home": False, "start": g["start_time"]}
    d["teams"] = [{"team": t, "game": by_team.get(t)} for t in teams]
    return d


def milestone_line(a):
    if a["reached"]:
        return f"{a['name']} reached {a['milestone']:,} career {a['label'].lower()}."
    return (f"{a['name']} is {a['remaining']} {a['label'].lower()} from {a['milestone']:,} career, "
            f"about {a['need']} game{'s' if a['need'] != 1 else ''} away at the current pace.")


def _game_line(label, game, kind="skater", start=None):
    when = game["start"].astimezone(ET).strftime("%-I:%M %p ET") if game["start"] else "time TBD"
    note = ""
    if kind == "goalie" and start:
        prob, confirmed = start
        note = " - confirmed starter" if confirmed else f" - likely starter ({round(prob * 100)}%, a guess)"
    elif kind == "goalie":
        note = " - starter unclear"
    return f"  {label} {'vs' if game['home'] else '@'} {game['opp']}, {when}{note}{rest_note(game)}"


def watch_lines(w):
    """The WATCHLIST block of the email (a list of lines, empty when there is nothing to say)."""
    lines = []
    games = sorted(w.get("playing", []), key=lambda e: e["game"]["start"] or datetime.max.replace(tzinfo=ET))
    games = [_game_line(f"{e['name']} ({e['team']})", e["game"], e["kind"], e.get("start")) for e in games]
    games += [_game_line(t["team"], t["game"]) for t in w.get("teams", []) if t["game"]]
    if games:
        lines += ["Playing today"] + games
    off = [e["name"] for e in w.get("idle", [])] + [t["team"] for t in w.get("teams", []) if not t["game"]]
    if off:
        lines.append("No game today: " + ", ".join(off))
    for title, items, fmt in (
        ("Hot", w.get("hot", []), lambda h: f"{h['name']}: {h['recent_points']} points in the last {h['recent_games']} games "
                                            f"(a {h['recent_pace']:.0f}-point pace vs {h['pace']:.0f} for the season)"),
        ("Role changes", w.get("roles", []), role_line),
        ("Luck check", w.get("luck", []), luck_line),
        ("Milestones", w.get("milestones", []), milestone_line),
        ("Prospects", w.get("prospects", []), prospects.alert_line),
        ("Reached the NHL", w.get("called_up", []), str),
        ("Watch", w.get("watch", []), str),
    ):
        if items:
            lines += [title] + [f"  {fmt(i)}" for i in items]
    return lines


def role_line(a):
    """One sentence for the role-changes section."""
    parts = []
    if a["pp_change"]:
        parts.append(f"{a['pp_label']} ({_mmss(a['pp_base'])} to {_mmss(a['pp'])} of power play a game)")
    if a["ev_change"]:
        parts.append(f"{'more' if a['ev_change'] == 'up' else 'less'} even-strength time "
                     f"({_mmss(a['ev_base'])} to {_mmss(a['ev'])} a game)")
    return f"{a['name']} ({a['team']}): " + "; ".join(parts) + f". Last {a['window']} games vs the rest of the season."


def luck_line(a):
    """One sentence for the luck-check section."""
    if a["kind"] == "goalie":
        if a["flag"] == "hot":
            return (f"{a['name']} has allowed {a['actual']} goals against about {a['expected']:.0f} expected from the shots "
                    f"faced (z {a['z']:+.1f}). Hard to keep up, so some of it may cool off.")
        return (f"{a['name']} has allowed {a['actual']} goals against about {a['expected']:.0f} expected from the shots "
                f"faced (z {a['z']:+.1f}). A better stretch may be coming.")
    if a["flag"] == "hot":
        return (f"{a['name']} has {a['actual']} points against about {a['expected']:.0f} expected from the shots "
                f"(z {a['z']:+.1f}). Some of it may cool off.")
    return (f"{a['name']} has {a['actual']} points against about {a['expected']:.0f} expected from the shots "
            f"(z {a['z']:+.1f}). A bounce back may be coming.")


def render(d, w=None, week=None):
    """(subject, plain-text body), or None when there is nothing worth an email. `w` is gather_watch()'s result; `week` is
    the Sunday week-ahead text (weekly.section), shown first."""
    watch = watch_lines(w) if w else []
    if not (week or d["playing"] or d["hot"] or d["watch"] or d.get("luck") or d.get("roles") or d.get("sell") or d.get("buy") or d.get("absent") or watch):
        return None
    lines = [f"Your NHL roster for {d['today']:%A, %B %-d}" if d["roster_size"] else f"Your NHL watchlist for {d['today']:%A, %B %-d}", ""]
    if week:
        lines += [week, ""]
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
            lines.append(f"  {e['name']} ({e['team']}) {'vs' if g['home'] else '@'} {g['opp']}, {when}{note}{rest_note(g)}")
        lines.append("")
    if d["idle"]:
        lines += ["NO GAME TODAY: " + ", ".join(e["name"] for e in d["idle"]), ""]
    if d["hot"]:
        lines.append("HOT")
        for h in d["hot"]:
            lines.append(f"  {h['name']}: {h['recent_points']} points in the last {h['recent_games']} games "
                         f"(a {h['recent_pace']:.0f}-point pace vs {h['pace']:.0f} for the season)")
        lines.append("")
    if d.get("roles"):
        lines.append("ROLE CHANGES (ice time is the earliest sign of a new role)")
        lines += [f"  {role_line(a)}" for a in d["roles"]]
        lines.append("")
    if d.get("sell"):
        lines.append("SELL HIGH (scoring above what the shots say; early in the season these swing a lot)")
        lines += [f"  {tradewatch.sell_line(a)}" for a in d["sell"]]
        lines.append("")
    if d.get("buy"):
        lines.append("BUY LOW (good players scoring below what the shots say; we can't see who is available in your league)")
        lines += [f"  {tradewatch.buy_line(a)}" for a in d["buy"]]
        lines.append("")
    if d.get("absent"):
        lines.append("TEAMMATE OUT (more ice time for your players; the NHL publishes no injuries, so this is inferred from games missed)")
        lines += [f"  {absent_line(e)}" for e in d["absent"]]
        lines.append("")
    if d.get("luck"):
        lines.append("LUCK CHECK (results vs. what the shots say; early in the season these swing a lot)")
        lines += [f"  {luck_line(a)}" for a in d["luck"]]
        lines.append("")
    if d["watch"]:
        lines += ["WATCH"] + [f"  {w}" for w in d["watch"]] + [""]
    if watch:
        lines += ["WATCHLIST"] + watch + [""]
    lines.append(f"Turn this email off any time: {config.PUBLIC_URL}/account")
    subject = (f"NHL roster: {len(d['playing'])} of {d['roster_size']} play today" if d["playing"]
               else "NHL roster update" if d["roster_size"] else "NHL watchlist update")
    if week:
        subject = f"Week ahead and today: {subject}" if d["playing"] else f"Week ahead: {subject}"
    return subject, "\n".join(lines)


def due_users(conn):
    return conn.execute(
        """SELECT u.id, u.email, coalesce(f.players, '[]'::jsonb) AS players, coalesce(f.scoring, '{}'::jsonb) AS scoring,
                  coalesce(f.league, '{}'::jsonb) AS league, p.last_sent_on
           FROM digest_pref p JOIN app_user u ON u.id = p.user_id LEFT JOIN fantasy_state f ON f.user_id = u.id
           WHERE p.enabled AND (coalesce(jsonb_array_length(f.players), 0) > 0
                                OR EXISTS (SELECT 1 FROM watch_item w WHERE w.user_id = u.id))
             AND (p.last_sent_on IS NULL OR p.last_sent_on < (now() AT TIME ZONE 'America/New_York')::date)""").fetchall()


def send_with_retry(to, subject, body, attempts=SEND_ATTEMPTS, wait=SEND_WAIT_SECONDS, sleep=time.sleep):
    """mail.send, retried: launchd often fires right as the Mac wakes, before the network is back."""
    for i in range(attempts):
        if mail.send(to, subject, body):
            return True
        if i < attempts - 1:
            sleep(wait * (i + 1))
    return False


def main(argv):
    dry = "--dry" in argv
    with psycopg.connect(config.DATABASE_URL, row_factory=dict_row) as conn:
        today = conn.execute("SELECT (now() AT TIME ZONE 'America/New_York')::date AS d").fetchone()["d"]
        sunday = today.weekday() == 6 or ("--sunday" in argv and (dry or "--preview" in argv))
        shared = weekly.load_shared(conn) if sunday else None     # the week's schedule and goalie plan, shared by every email
        if "--preview" in argv:
            ids = [int(i) for i in argv[argv.index("--preview") + 1].split(",")]
            skaters, goalies = _roster_rows(conn, set(ids))
            players = [{"id": i, "kind": "skater" if i in skaters else "goalie", "name": str(i)} for i in ids]
            out = render(gather(conn, players), week=weekly.section(players, {}, {}, shared) if sunday else None)
            print(out[0] + "\n\n" + out[1] if out else "(nothing to send)")
            return 0
        sent = skipped = 0
        league = None  # luck rows for every player: one query set shared by all the emails
        ms = None  # api.milestones() scans every player, so it runs once and only if someone watches a player
        absent = absences_db.current(conn, config.SEASON_ID)   # who is out, shared by every email
        for u in due_users(conn):
            items = conn.execute("SELECT kind, ref, name FROM watch_item WHERE user_id = %s", (u["id"],)).fetchall()
            if ms is None and any(i["kind"] == "player" for i in items):
                ms = api.milestones()
            roster_ids = {p["id"] for p in u["players"]}
            league = league or league_luck(conn)
            watched = {int(i["ref"]) for i in items if i["kind"] == "player"}
            week = weekly.section(u["players"], u["scoring"], u["league"], shared) if sunday and u["players"] else None
            out = render(gather(conn, u["players"], league, watched=watched, absent=absent), gather_watch(conn, items, roster_ids, ms, league), week)
            if out is None:
                skipped += 1
                continue
            if dry:
                print(f"--- would send to {u['email']}\n{out[0]}\n\n{out[1]}\n")
                continue
            if not config.SMTP_HOST:
                print("SMTP_HOST is not set, so nothing can be sent. Use --dry to preview.")
                return 1
            if send_with_retry(u["email"], *out):
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
