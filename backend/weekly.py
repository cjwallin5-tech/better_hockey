"""The Sunday "week ahead" section of the daily email (digest.py adds it on Sundays).

The best lineup for the coming Monday to Sunday, the goalies' starts, streaming goalie picks and which days are heavy or light. It
is the server-side twin of the Fantasy page's lineup optimizer (frontend/src/lineup.js and value.js), for points leagues: a skater's
score for a game is his fantasy points per game under the account's scoring, pulled toward his own two-season record early in a
season and moved by how soft the opponent is; a goalie's is his chance to start the game times what a start there is worth
(streaming.py). Each day each position group starts the highest scores among the players with a game, up to the account's slots
(synced with the roster; the defaults are 2 C, 2 L, 2 R, 4 D, 2 G). Category leagues get the schedule and goalie sections but no
lineup, since the category model is not ported.

Like the page, it cannot see injuries, who else owns whom, or lines changing.

    python digest.py --dry --sunday     print what the Sunday emails would hold, whatever day it is
    python digest.py --preview 8478402,8480069 --sunday     the same for a list of player ids with default scoring and slots
"""
from datetime import timedelta

import api
import config

GROUPS = ("C", "L", "R", "D", "G")
DEFAULT_SLOTS = {"C": 2, "L": 2, "R": 2, "D": 4, "G": 2}
DEFAULT_SCORING = {"goals": 1.0, "assists": 1.0}
SKATER_STATS = ("plus_minus", "pim", "pp_points", "sh_points", "game_winning_goals", "shots", "hits", "blocked_shots",
                "takeaways", "giveaways")
# Games' worth of average play blended into a rate (value.js PRIOR_WEIGHT and categoryDefs.js): goals and assists toward the
# player's own record, or the position average without one; each other stat toward the average by how noisy it is.
PRIOR_HISTORY, PRIOR_NO_HISTORY, PRIOR_OTHER = 40, 10, 10
STAT_PRIOR = {"plus_minus": 30, "pim": 20, "pp_points": 25, "sh_points": 60, "game_winning_goals": 100, "shots": 8, "hits": 8,
              "blocked_shots": 8, "takeaways": 12, "giveaways": 12}
HEAVY_GAMES = 4        # games in the week at or above which a player's week is heavy
LIGHT_GAMES = 2        # at or below which it is light
STREAM_MAX = 3         # goalies suggested for streaming


# --- Scores (pure; the same maths as value.js and lineup.js) --------------------------------------------------

def shrink(total, games, mean, prior):
    return (total + prior * mean) / (games + prior)


def skater_rates(rows, scoring, priors):
    """{player_id: (group, shrunk fantasy points per game)} for every skater row with a game played.

    rows: skater_season rows (position, games_played, goals, assists, and the other stats). priors: {player_id: {goals, assists}}
    per-game track records. The prior mean for a position group is taken over players who play regularly, not call-ups.
    """
    w = lambda key: float(scoring.get(key) or 0)
    other = [k for k in SKATER_STATS if w(k)]
    groups = {}
    for r in rows:
        if not r["games_played"]:
            continue
        group = r["position"] if r["position"] in ("C", "L", "R", "D") else "C"
        record = priors.get(r["player_id"])
        groups.setdefault(group, []).append({
            "id": r["player_id"], "gp": r["games_played"],
            "ga": (r["goals"] or 0) * w("goals") + (r["assists"] or 0) * w("assists"),
            "stats": {k: r[k] or 0 for k in other},
            "prior_ga": record["goals"] * w("goals") + record["assists"] * w("assists") if record else None})
    out = {}
    for group, players in groups.items():
        top = max(p["gp"] for p in players)
        regulars = [p for p in players if p["gp"] >= max(1, top / 3)]
        games = sum(p["gp"] for p in regulars)
        mean_ga = sum(p["ga"] for p in regulars) / games if games else 0.0
        mean_stat = {k: (sum(p["stats"][k] for p in regulars) / games if games else 0.0) for k in other}
        for p in players:
            ga = (shrink(p["ga"], p["gp"], p["prior_ga"], PRIOR_HISTORY) if p["prior_ga"] is not None
                  else shrink(p["ga"], p["gp"], mean_ga, PRIOR_NO_HISTORY))
            out[p["id"]] = (group, ga + sum(w(k) * shrink(p["stats"][k], p["gp"], mean_stat[k], STAT_PRIOR.get(k, PRIOR_OTHER))
                                            for k in other))
    return out


def skater_game_score(base, ratio):
    """A skater's score for one game: the per-game rate moved by the matchup (above 1 is soft). Works for negative rates too."""
    r = 1.0 if ratio is None else ratio
    return base + abs(base) * (r - 1)


def goalie_game_score(game, scoring):
    """A goalie's expected fantasy points for one game: his chance to start times the stat line of a start (streaming.py)."""
    w = lambda key: float(scoring.get(key) or 0)
    line, p = game.get("line") or {}, game.get("probability") or 0.0
    return p * (w("wins") * line.get("win", 0) + w("losses") * line.get("loss", 0) + w("ot_losses") * line.get("otl", 0)
                + w("saves") * line.get("saves", 0) + w("goals_against") * line.get("ga", 0) + w("shutouts") * line.get("shutout", 0))


def build_entries(roster, week, goalie_plan, rates, scoring, dates):
    """[{id, name, kind, group, games: [{date, score, opponent, home}], known}] for the roster, games limited to `dates`.

    week: fantasy_week's players ({str(id): {games, games_out}}); goalie_plan: streaming plan goalies [{player_id, games}];
    rates: skater_rates()."""
    goalies = {g["player_id"]: g for g in goalie_plan}
    out = []
    for p in roster:
        if p["kind"] == "goalie":
            games = [{"date": g["date"], "score": goalie_game_score(g, scoring), "opponent": g["opponent"], "home": g["home_game"],
                      "chance": g["probability"], "confirmed": g["confirmed"]}
                     for g in goalies.get(p["id"], {}).get("games", []) if g["date"] in dates]
            out.append({"id": p["id"], "name": p["name"], "kind": "goalie", "group": "G", "games": games, "known": p["id"] in goalies})
            continue
        group, base = rates.get(p["id"], ("C", 0.0))
        info = week.get(str(p["id"]), {})
        games = [{"date": g["game_date"], "score": skater_game_score(base, g.get("skater_ratio")), "opponent": g["opponent"],
                  "home": g["home_game"]} for g in info.get("games", []) if g["game_date"] in dates]
        out.append({"id": p["id"], "name": p["name"], "kind": "skater", "group": group, "games": games,
                    "known": p["id"] in rates})
    return out


def optimize(entries, slots):
    """The best daily lineup: each day every position group starts its highest scores among the players with a game, up to its slots.
    Positions are independent (no UTIL slot), so the best N of each group is optimal. Returns {dates, starts, total, by_player}:
    starts maps date -> set of starting ids; by_player maps id -> {starts, score, sat}."""
    dates = sorted({g["date"] for e in entries for g in e["games"]})
    starts = {d: set() for d in dates}
    by_player = {e["id"]: {"starts": 0, "score": 0.0, "sat": 0} for e in entries}
    total = 0.0
    for group in GROUPS:
        pool = [e for e in entries if e["group"] == group]
        n = slots.get(group, 0)
        for d in dates:
            playing = [(sum(g["score"] for g in e["games"] if g["date"] == d), e["id"]) for e in pool
                       if any(g["date"] == d for g in e["games"])]
            playing.sort(key=lambda x: (-x[0], x[1]))
            for i, (score, pid) in enumerate(playing):
                stat = by_player[pid]
                if i < n:
                    starts[d].add(pid)
                    stat["starts"] += 1
                    stat["score"] += score
                    total += score
                else:
                    stat["sat"] += 1
    return {"dates": dates, "starts": starts, "total": total, "by_player": by_player}


def week_load(entries):
    """([(name, games)] heavy, [(name, games)] light) for the week, busiest first, from players' game counts. Goalies are left out:
    how many games a goalie starts is a different question (see the goalie section)."""
    counts = [(e["name"], len(e["games"])) for e in entries if e["kind"] == "skater" and e["known"]]
    heavy = sorted([c for c in counts if c[1] >= HEAVY_GAMES], key=lambda c: (-c[1], c[0]))
    light = sorted([c for c in counts if c[1] <= LIGHT_GAMES], key=lambda c: (c[1], c[0]))
    return heavy, light


def streaming_picks(goalie_plan, roster_ids, scoring, dates, n=STREAM_MAX):
    """Goalies not on the roster, best expected fantasy points over the window: [{name, team, starts, points}]. Empty when the
    scoring counts no goalie stat (then points can't rank them)."""
    if not any(float(scoring.get(k) or 0) for k in ("wins", "losses", "ot_losses", "saves", "goals_against", "shutouts")):
        return []
    rows = []
    for g in goalie_plan:
        if g["player_id"] in roster_ids:
            continue
        games = [x for x in g["games"] if x["date"] in dates]
        if not games:
            continue
        rows.append({"name": g["name"], "team": g["team"], "starts": sum(x["probability"] for x in games),
                     "points": sum(goalie_game_score(x, scoring) for x in games)})
    rows.sort(key=lambda r: (-r["points"], r["name"]))
    return rows[:n]


# --- The email ------------------------------------------------------------------------------------------------

def _day(d):
    return f"{d:%a} {d.month}/{d.day}"


def render(plan, entries, heavy, light, picks, slots, points_league, first, last):
    """The section's text for one account."""
    lines = [f"WEEK AHEAD: {_day(first)} to {_day(last)}", ""]
    if not plan["dates"]:
        lines.append("None of your players have a game this week.")
    elif points_league:
        slot_text = ", ".join(f"{slots[g]} {g}" for g in GROUPS if slots.get(g))
        lines += [f"Best lineup ({slot_text}; changing it daily). Expected total: {plan['total']:.1f} points", ""]
        for d in plan["dates"]:
            start = [e for e in entries if e["id"] in plan["starts"][d]]
            sit = [e for e in entries if e["id"] not in plan["starts"][d] and any(g["date"] == d for g in e["games"])]
            start.sort(key=lambda e: (GROUPS.index(e["group"]), e["name"]))
            lines.append(f"  {_day(d)}: start {', '.join(f'{e['name']} ({e['group']})' for e in start) or 'nobody'}")
            if sit:
                lines.append(f"      sit {', '.join(e['name'] for e in sorted(sit, key=lambda e: e['name']))}")
        benched = [e for e in entries if plan["by_player"][e["id"]]["starts"] == 0 and e["games"]]
        if benched:
            lines += ["", "Never starts this week (your slots are full at their position): " + ", ".join(e["name"] for e in benched)]
    else:
        lines.append("Your league counts categories, which the lineup doesn't score yet, so there is no lineup here.")
    lines.append("")

    goalies = [e for e in entries if e["kind"] == "goalie"]
    if goalies:
        lines.append("Your goalies")
        for e in goalies:
            expected = sum(g["chance"] for g in e["games"])
            lines.append(f"  {e['name']}: about {expected:.1f} starts expected in {len(e['games'])} team games" if e["games"] else f"  {e['name']}: no games this week")
        lines.append("")
    if picks:
        lines.append("Streaming goalies (best expected points this week; check who is available in your league)")
        lines += [f"  {p['name']} ({p['team']}): about {p['starts']:.1f} starts, {p['points']:.1f} points" for p in picks]
        lines.append("")
    if heavy or light:
        lines.append("Heavy and light weeks")
        if heavy:
            lines.append(f"  Heavy ({HEAVY_GAMES}+ games): " + ", ".join(f"{n} {g}" for n, g in heavy))
        if light:
            lines.append(f"  Light ({LIGHT_GAMES} or fewer): " + ", ".join(f"{n} {g}" for n, g in light))
        lines.append("")
    unknown = [e["name"] for e in entries if not e["known"]]
    if unknown:
        lines += [f"No stats yet for {', '.join(unknown)}, so they are scored 0.", ""]
    lines.append("The lineup can't see injuries, who your league's other teams hold, or line changes; check the news before you lock it.")
    return "\n".join(lines)


# --- Database work ---------------------------------------------------------------------------------------------

def load_shared(conn):
    """What every account's Sunday section shares: skater rows and track records, the week's schedule and the goalie plan.
    Returns (rows, priors, goalie_plan, today); the days are tomorrow through the Sunday after (the Monday-Sunday week)."""
    rows = conn.execute("SELECT * FROM skater_season WHERE season_id = %s AND games_played > 0", (config.SEASON_ID,)).fetchall()
    priors = api.fantasy_priors()["players"]
    plan = api.streaming_goalies(days=8)
    today = conn.execute("SELECT (now() AT TIME ZONE 'America/New_York')::date AS d").fetchone()["d"]
    return rows, priors, plan["goalies"], today


def week_dates(today):
    """Monday-to-Sunday of the coming week when run on a Sunday; otherwise tomorrow through seven days on."""
    start = today + timedelta(days=1)
    return [start + timedelta(days=i) for i in range(7)]


def section(roster, scoring, league, shared):
    """The week-ahead text for one account's roster, scoring and league shape. shared is load_shared()'s result."""
    rows, priors, goalie_plan, today = shared
    scoring = {k: v for k, v in (scoring or {}).items() if v} or DEFAULT_SCORING
    slots = {g: (league.get("slots") or {}).get(g, DEFAULT_SLOTS[g]) for g in GROUPS}
    points_league = league.get("format") != "categories"
    days = week_dates(today)
    dates = set(days)
    ids = [p["id"] for p in roster]
    week = api.fantasy_week(ids=",".join(map(str, ids)), days=8)["players"] if ids else {}
    entries = build_entries(roster, week, goalie_plan, skater_rates(rows, scoring, priors), scoring, dates)
    plan = optimize(entries, slots)
    heavy, light = week_load(entries)
    picks = streaming_picks(goalie_plan, set(ids), scoring, dates)
    return render(plan, entries, heavy, light, picks, slots, points_league, days[0], days[-1])
