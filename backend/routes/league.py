"""League-wide endpoints: home, news, milestones, playoff odds, draft lottery, role changes, prospects and draft rankings."""
from collections import defaultdict
from datetime import date, datetime, timezone
import math
import time

from fastapi import APIRouter, HTTPException
import psycopg
from psycopg.rows import dict_row
import requests

import config
import lottery
import news_db
import nhle
import playoff_odds
import prospects as prospectlib
import roles
import roles_db
from routes.common import ALLTIME_TABLES, GOALIES_SQL, SKATERS_SQL, TEAMS_SQL, _goalie_params, ttl_cached

router = APIRouter()


# --- Playoff odds -------------------------------------------------------------------------------
_odds_cache = {"sig": None, "data": None}


@router.get("/api/playoff-odds")
def playoff_odds_endpoint():
    """Chance each team makes the playoffs and goes on to win each round and the Cup, from simulating the rest of the season
    and then the playoffs (see playoff_odds.py)."""
    with psycopg.connect(config.DATABASE_URL, row_factory=dict_row) as conn:
        teams = conn.execute(
            """SELECT abbrev, name, conference, division, games_played, points, reg_wins, goal_diff
               FROM team_season WHERE season_id = %s""", (config.SEASON_ID,)).fetchall()
        remaining = conn.execute(
            "SELECT home, away FROM game WHERE season_id = %s AND state NOT IN ('OFF', 'FINAL')",
            (config.SEASON_ID,)).fetchall()
    if not teams:
        raise HTTPException(404, "No standings yet")
    sig = (sum(t["games_played"] for t in teams), sum(t["points"] or 0 for t in teams), len(remaining))
    if _odds_cache["sig"] != sig:  # results only change when a game finishes, so reuse the run until then
        odds = playoff_odds.simulate(teams, [(g["home"], g["away"]) for g in remaining], seed=sig[0])
        _odds_cache.update(sig=sig, data={
            "sims": playoff_odds.SIMS, "games_remaining": len(remaining),
            "teams": [{**t, **odds[t["abbrev"]]} for t in teams],
        })
    return _odds_cache["data"]


@router.get("/api/lottery")
def draft_lottery():
    """Each team's chances in the draft lottery: of missing the playoffs, finishing with the worst record, and of each pick from the
    first to the sixteenth, from the playoff odds simulation and the NHL's lottery rules (see lottery.py)."""
    odds = playoff_odds_endpoint()
    with psycopg.connect(config.DATABASE_URL, row_factory=dict_row) as conn:
        logos = {r["abbrev"]: r for r in conn.execute(
            "SELECT abbrev, logo_url, logo_dark_url FROM team_season WHERE season_id = %s", (config.SEASON_ID,)).fetchall()}
    teams = []
    for t in odds["teams"]:
        summary = lottery.summary(t["lottery_seed"]) if t.get("lottery_seed") else None
        if not summary:
            continue
        teams.append({
            "team": t["abbrev"], "name": t["name"], "conference": t["conference"], "division": t["division"],
            "games_played": t["games_played"], "points": t["points"], "exp_points": t["exp_points"],
            "p10_points": t["p10_points"], "p90_points": t["p90_points"], "make_playoffs": t["make_playoffs"],
            "logo_url": logos.get(t["abbrev"], {}).get("logo_url"), "logo_dark_url": logos.get(t["abbrev"], {}).get("logo_dark_url"),
            **summary,
        })
    teams.sort(key=lambda r: (-r["first_overall"], r["team"]))
    published = lottery.MATRIX
    return {
        "teams": teams, "sims": odds["sims"], "games_remaining": odds["games_remaining"],
        "seeds": [{"seed": i + 1, "first_draw": lottery.ODDS[i], "first_overall": float(published[i][0]),
                   "top_two": float(published[i][:2].sum()), "worst_pick": int(max(j for j in range(lottery.SEEDS) if published[i][j] > 1e-12)) + 1}
                  for i in range(lottery.SEEDS)],
    }


# --- Home dashboard -----------------------------------------------------------------------------
STREAKS_SQL = """
WITH g AS (
    SELECT player_id, points, goals,
           row_number() OVER (PARTITION BY player_id ORDER BY game_date DESC, game_id DESC) AS rn
    FROM skater_game WHERE season_id = %(season)s
),
agg AS (
    SELECT player_id, count(*) AS games,
           min(rn) FILTER (WHERE points = 0) AS first_pointless,
           min(rn) FILTER (WHERE points > 0) AS first_point,
           min(rn) FILTER (WHERE goals = 0) AS first_goalless
    FROM g GROUP BY player_id
)
SELECT a.player_id,
       COALESCE(a.first_pointless, a.games + 1) - 1 AS point_streak,
       COALESCE(a.first_point, a.games + 1) - 1 AS pointless_streak,
       COALESCE(a.first_goalless, a.games + 1) - 1 AS goal_streak
FROM agg a
"""


@router.get("/api/home")
@ttl_cached(60)
def home():
    today = datetime.now().date()
    params = {"season": config.SEASON_ID, "window": config.RECENT_WINDOW, "games": config.GAMES_PER_SEASON}
    with psycopg.connect(config.DATABASE_URL, row_factory=dict_row) as conn:
        latest = conn.execute(
            "SELECT max(game_date) AS d FROM game WHERE season_id = %s AND state IN ('OFF', 'FINAL')",
            (config.SEASON_ID,),
        ).fetchone()["d"]
        games = conn.execute(
            """SELECT game_id, game_date, home, away, home_score, away_score, last_period, venue
               FROM game WHERE season_id = %s AND game_date = %s AND state IN ('OFF', 'FINAL')
               ORDER BY start_time, game_id""",
            (config.SEASON_ID, latest),
        ).fetchall() if latest else []

        performers = conn.execute(
            """SELECT g.player_id, s.name, g.team, g.opponent, g.is_home, s.position, g.goals, g.assists,
                      g.points, g.shots, g.plus_minus, g.game_id
               FROM skater_game g JOIN skater_season s ON s.player_id = g.player_id AND s.season_id = g.season_id
               WHERE g.season_id = %s AND g.game_date = %s
               ORDER BY g.points DESC, g.goals DESC, g.shots DESC NULLS LAST LIMIT 8""",
            (config.SEASON_ID, latest),
        ).fetchall() if latest else []
        goalie_nights = conn.execute(
            """SELECT g.player_id, s.name, g.team, g.opponent, g.shots_against, g.saves, g.goals_against,
                      g.decision, round(g.saves::numeric / NULLIF(g.shots_against, 0), 3)::float AS save_pct
               FROM goalie_game g JOIN goalie_season s ON s.player_id = g.player_id AND s.season_id = g.season_id
               WHERE g.season_id = %s AND g.game_date = %s AND g.shots_against >= 15
               ORDER BY g.saves::float / g.shots_against DESC, g.shots_against DESC LIMIT 3""",
            (config.SEASON_ID, latest),
        ).fetchall() if latest else []

        next_day = conn.execute(
            "SELECT min(game_date) AS d FROM game WHERE season_id = %s AND state IN ('FUT', 'PRE', 'LIVE', 'CRIT') AND game_date >= %s",
            (config.SEASON_ID, today),
        ).fetchone()["d"]
        upcoming = conn.execute(
            """SELECT game_id, game_date, start_time, home, away, venue, state, home_score, away_score
               FROM game WHERE season_id = %s AND game_date = %s ORDER BY start_time, game_id""",
            (config.SEASON_ID, next_day),
        ).fetchall() if next_day else []

        skaters = conn.execute(SKATERS_SQL, params).fetchall()
        streaks = {r["player_id"]: r for r in conn.execute(STREAKS_SQL, params).fetchall()}
        top_goalies = conn.execute(GOALIES_SQL, _goalie_params()).fetchall()
        top_teams = conn.execute(TEAMS_SQL, {"season": config.SEASON_ID, "games": config.GAMES_PER_SEASON}).fetchall()[:6]

    min_gp = max(1, -(-max(r["games_played"] for r in skaters) // 2))
    qualified = [r for r in skaters if r["games_played"] >= min_gp]

    def slim(r, **extra):
        return {"player_id": r["player_id"], "name": r["name"], "team": r["team"], "position": r["position"],
                "games_played": r["games_played"], "goals": r["goals"], "assists": r["assists"],
                "points": r["points"], "toi_per_game_sec": r["toi_per_game_sec"], **extra}

    hot = sorted((r for r in skaters if streaks.get(r["player_id"], {}).get("point_streak", 0) >= 3),
                 key=lambda r: (-streaks[r["player_id"]]["point_streak"], -r["points"]))[:8]
    cold = sorted(
        (r for r in skaters
         if r["position"] != "D" and (r["toi_per_game_sec"] or 0) >= 17 * 60
         and streaks.get(r["player_id"], {}).get("pointless_streak", 0) >= 3),
        key=lambda r: (-streaks[r["player_id"]]["pointless_streak"], -(r["toi_per_game_sec"] or 0)))[:8]
    goal_pace = sorted(qualified, key=lambda r: -(r["goals"] / r["games_played"]))[:5]

    return {
        "last_game_day": latest,
        "games": games,
        "performers": performers,
        "goalie_nights": goalie_nights,
        "upcoming_day": next_day,
        "upcoming": upcoming,
        "hot": [slim(r, streak=streaks[r["player_id"]]["point_streak"]) for r in hot],
        "cold": [slim(r, streak=streaks[r["player_id"]]["pointless_streak"]) for r in cold],
        # season leaders by the plain totals; a tie goes to the player with fewer games, then more of the other stat
        "points_leaders": [slim(r) for r in sorted(skaters, key=lambda r: (-r["points"], r["games_played"], -r["goals"], r["name"]))[:5]],
        "goals_leaders": [slim(r) for r in sorted(skaters, key=lambda r: (-r["goals"], r["games_played"], -r["points"], r["name"]))[:5]],
        "point_pace": [slim(r, pace=r["point_pace"]) for r in sorted(qualified, key=lambda r: -(r["point_pace"] or 0))[:5]],
        "goal_pace": [slim(r, pace=round(r["goals"] / r["games_played"] * config.GAMES_PER_SEASON, 1)) for r in goal_pace],
        "goalies": [
            {"player_id": g["player_id"], "name": g["name"], "team": g["team"], "games_played": g["games_played"],
             "save_pct": g["save_pct"], "gaa": g["gaa"], "gsaa": g["gsaa"], "wins": g["wins"]}
            for g in sorted((g for g in top_goalies if g["games_played"] >= max(1, min_gp // 2)), key=lambda g: -(g["gsaa"] or 0))[:5]
        ],
        "teams": [{k: t[k] for k in ("abbrev", "name", "logo_url", "logo_dark_url", "games_played", "wins", "losses", "ot_losses", "points", "points_pace", "goal_diff")} for t in top_teams],
        "min_gp": min_gp,
        "games_per_season": config.GAMES_PER_SEASON,
    }


# --- Milestone watch ----------------------------------------------------------------------------
MILESTONES = {
    "skater": {
        "goals": ("Goals", [100, 200, 300, 400, 500, 600, 700, 800, 900, 1000]),
        "assists": ("Assists", [100, 250, 500, 750, 1000, 1250, 1500]),
        "points": ("Points", [250, 500, 750, 1000, 1250, 1500, 1750, 2000, 2500]),
        "games_played": ("Games played", [250, 500, 750, 1000, 1250, 1500]),
    },
    "goalie": {
        "wins": ("Wins", [50, 100, 150, 200, 250, 300, 350, 400, 500, 600]),
        "shutouts": ("Shutouts", [10, 25, 50, 75, 100]),
        "games_played": ("Games played", [100, 250, 500, 750, 1000]),
    },
}


# Smallest milestone worth headlining for each stat; the rest are shown only when asked for.
MAJOR_FROM = {
    "skater": {"goals": 300, "assists": 500, "points": 750, "games_played": 1000},
    "goalie": {"wins": 200, "shutouts": 25, "games_played": 500},
}


MILESTONE_MAX_GAMES = 90  # only show milestones within roughly a season's reach


def _milestone_rows(conn, kind):
    """Active players with their career totals (before this season) and this season's totals."""
    career_t = ALLTIME_TABLES[kind]
    season_t = "skater_season" if kind == "skater" else "goalie_season"
    stats = list(MILESTONES[kind])
    cols_c = ", ".join(f"c.{s} AS career_{s}" for s in stats)
    cols_s = ", ".join(f"s.{s} AS season_{s}" for s in stats if s != "games_played")
    return conn.execute(
        f"""SELECT s.player_id, s.name, s.team, s.games_played AS season_gp, {cols_c}, {cols_s},
                   t.games_played AS team_gp
            FROM {season_t} s
            JOIN {career_t} c ON c.player_id = s.player_id AND c.game_type = 2
            LEFT JOIN team_season t ON t.season_id = s.season_id AND t.abbrev = split_part(s.team, ',', 1)
            WHERE s.season_id = %s AND s.games_played > 0""",
        (config.SEASON_ID,),
    ).fetchall()


@router.get("/api/news")
def news_stories(team: str | None = None, player: int | None = None, top: bool = False, limit: int = 30):
    """Hockey headlines from public feeds, newest first, with links to the publishers. `team` (abbreviation) and `player` (id) keep only
    stories that mention them; `top` keeps only the big ones (ESPN's lead stories, trades, injuries, signings and the like)."""
    if team is not None and not (team := team.strip().upper()).isalpha():
        raise HTTPException(status_code=400, detail="team must be a team abbreviation")
    with psycopg.connect(config.DATABASE_URL, row_factory=dict_row) as conn:
        news_db.ensure_fresh(conn)
        return {"stories": news_db.stories(conn, team=team, player=player, top=top, limit=max(1, min(limit, 100)))}


@router.get("/api/milestones")
def milestones():
    upcoming, reached = [], []
    with psycopg.connect(config.DATABASE_URL, row_factory=dict_row) as conn:
        for kind in ("skater", "goalie"):
            for r in _milestone_rows(conn, kind):
                team_gp = r["team_gp"] or r["season_gp"]
                team_left = max(0, config.GAMES_PER_SEASON - team_gp)
                # Share of team games this player appears in (matters for goalies who split starts).
                appear = min(1.0, r["season_gp"] / team_gp) if team_gp else 1.0
                expected_left = team_left * appear
                for stat, (label, steps) in MILESTONES[kind].items():
                    now = r[f"career_{stat}"]
                    if now is None:
                        continue
                    season_total = r["season_gp"] if stat == "games_played" else (r[f"season_{stat}"] or 0)
                    before = now - season_total
                    base = {"player_id": r["player_id"], "name": r["name"], "team": r["team"], "kind": kind,
                            "stat": stat, "label": label}
                    major_from = MAJOR_FROM[kind][stat]
                    # Crossed during this season: find the game it happened in.
                    for m in (s for s in steps if before < s <= now):
                        reached.append({**base, "milestone": m, "now": now, "before": before, "major": m >= major_from})
                    nxt = next((s for s in steps if s > now), None)
                    if nxt is None:
                        continue
                    # Pace: this season's rate once it's a real sample, otherwise the career rate.
                    career_gp = r["career_games_played"] or 0
                    if stat == "games_played":
                        rate = 1.0  # one per appearance
                    elif r["season_gp"] >= 20:
                        rate = season_total / r["season_gp"]
                    else:
                        rate = (now / career_gp) if career_gp else 0
                    if rate <= 0:
                        continue
                    remaining = nxt - now
                    need = math.ceil(remaining / rate)
                    if need > MILESTONE_MAX_GAMES:
                        continue
                    upcoming.append({**base, "now": now, "milestone": nxt, "remaining": remaining,
                                     "rate": round(rate, 3), "games_needed": need,
                                     "major": nxt >= major_from, "this_season": need <= expected_left,
                                     "rate_source": "this season" if r["season_gp"] >= 20 and stat != "games_played" else "career"})

        # Dates for milestones reached this season, from the player's game log.
        for item in reached:
            table = "skater_game" if item["kind"] == "skater" else "goalie_game"
            stat = item["stat"]
            if stat == "games_played":
                rows = conn.execute(
                    f"SELECT game_date, opponent, 1 AS v FROM {table} WHERE player_id = %s AND season_id = %s ORDER BY game_date, game_id",
                    (item["player_id"], config.SEASON_ID)).fetchall()
            else:
                col = {"goals": "goals", "assists": "assists", "points": "points"}.get(stat)
                if item["kind"] == "goalie":
                    col = {"wins": "(decision = 'W')::int", "shutouts": "(goals_against = 0 AND toi_sec >= 3540)::int"}[stat]
                rows = conn.execute(
                    f"SELECT game_date, opponent, {col} AS v FROM {table} WHERE player_id = %s AND season_id = %s ORDER BY game_date, game_id",
                    (item["player_id"], config.SEASON_ID)).fetchall()
            running = item["before"]
            for g in rows:
                running += g["v"] or 0
                if running >= item["milestone"]:
                    item["date"], item["opponent"] = g["game_date"], g["opponent"]
                    break

    upcoming.sort(key=lambda m: (m["games_needed"], m["remaining"]))
    reached.sort(key=lambda m: str(m.get("date") or ""), reverse=True)
    return {"upcoming": upcoming, "reached": reached, "games_per_season": config.GAMES_PER_SEASON}


# --- Prospects ----------------------------------------------------------------------------------
PROSPECT_SORTS = {"points_per_game", "points", "goals", "assists", "games", "age", "draft", "name", "save_pct", "nhle"}


def _nhle_factors(conn):
    """{league: {factor, lo, hi, pairs, players}} from nhle_factor (empty before analysis/nhle_factors.py --save has run)."""
    return {r["league"]: r for r in conn.execute("SELECT league, factor, lo, hi, pairs, players FROM nhle_factor").fetchall()}


def _nhle_ages(conn):
    """{age bucket: multiplier} from nhle_age (see nhle.AGE_BUCKETS)."""
    return {r["bucket"]: r["multiplier"] for r in conn.execute("SELECT bucket, multiplier FROM nhle_age").fetchall()}


def _prospect_nhle(p, seasons, factors, ages):
    """A skater prospect's NHLe from this season's line, or, while it is under nhle.MIN_GAMES_SHOWN games, from last season's, marked with
    that season_id and `earlier`. Nothing for goalies, for someone already playing in the NHL this season, or when neither season
    qualifies (older seasons would say little about where he is now). seasons: his prospect_season rows (any seasons, any game types)."""
    if p["position"] == "G":
        return None
    now = prospectlib.current_line(seasons, config.SEASON_ID)
    if now and now["league"] == "NHL":
        return None
    for sid in (config.SEASON_ID, config.SEASON_ID - 10001):
        line = prospectlib.current_line(seasons, sid)
        out = nhle.nhle_line(line, factors, config.GAMES_PER_SEASON, nhle.age_on_season(sid, p["birth_date"]), ages)
        if out:
            return {**out, "season_id": sid, "earlier": sid != config.SEASON_ID}
    return None


def _prospect_row(p, line, today, factors=None, ages=None, seasons=None):
    """One prospect as the API returns them: bio, draft, and this season's line in the league they played most in, with its NHL
    equivalent (nhle.py) for skaters in a league that has a factor."""
    pts = prospectlib.points_per_game(line)
    return {"nhle": _prospect_nhle(p, seasons or [], factors or {}, ages), "player_id": p["player_id"], "name": p["name"], "team": p["team"], "position": p["position"], "shoots": p["shoots"],
            "age": prospectlib.age_on(p["birth_date"], today), "birth_country": p["birth_country"],
            "height_in": p["height_in"], "weight_lb": p["weight_lb"], "headshot": p["headshot"],
            "draft": {"year": p["draft_year"], "round": p["draft_round"], "pick": p["draft_pick"], "overall": p["draft_overall"],
                      "team": p["draft_team"]} if p["draft_year"] else None,
            "league": line["league"] if line else None, "club": line["team_name"] if line else None,
            "games": line["games"] if line else 0, "goals": line["goals"] if line else None,
            "assists": line["assists"] if line else None, "points": line["points"] if line else None,
            "points_per_game": pts, "wins": line["wins"] if line else None,
            "save_pct": line["save_pct"] if line else None, "gaa": line["gaa"] if line else None}


@router.get("/api/nhle")
def nhle_factors_endpoint():
    """The league factors behind the NHLe figures: NHL points per game as a multiple of the league's, each with a 90% interval and
    the number of player pairs it was fitted on (analysis/nhle_factors.py)."""
    with psycopg.connect(config.DATABASE_URL, row_factory=dict_row) as conn:
        factors, ages = _nhle_factors(conn), _nhle_ages(conn)
    return {"season_games": config.GAMES_PER_SEASON, "min_games": nhle.MIN_GAMES_SHOWN,
            "factors": sorted(factors.values(), key=lambda f: -f["pairs"]),
            "age_multipliers": [{"bucket": b[0], "multiplier": ages[b[0]]} for b in nhle.AGE_BUCKETS if b[0] in ages]}


@router.get("/api/prospects")
def prospects_list(team: str = "", position: str = "", league: str = "", q: str = "", sort: str = "points_per_game",
                   min_games: int = 5, limit: int = 100):
    """Players on NHL teams' prospect lists with this season's line in the league they played most in (junior, college,
    European or minor league). position is C, L, R, D, F (forwards) or G; sort is one of PROSPECT_SORTS (age and draft
    run lowest first). See prospects.py."""
    if sort not in PROSPECT_SORTS:
        raise HTTPException(400, f"sort must be one of {', '.join(sorted(PROSPECT_SORTS))}")
    limit = max(1, min(limit, 1000))
    with psycopg.connect(config.DATABASE_URL, row_factory=dict_row) as conn:
        today = conn.execute("SELECT (now() AT TIME ZONE 'America/New_York')::date AS d").fetchone()["d"]
        people = conn.execute("SELECT * FROM prospect WHERE on_list").fetchall()
        factors, ages = _nhle_factors(conn), _nhle_ages(conn)
        lines = defaultdict(list)
        for r in conn.execute("SELECT * FROM prospect_season WHERE game_type = 2"):
            lines[r["player_id"]].append(dict(r))
    rows = [_prospect_row(p, prospectlib.current_line(lines.get(p["player_id"], []), config.SEASON_ID), today, factors, ages,
                          lines.get(p["player_id"], [])) for p in people]
    leagues = sorted({r["league"] for r in rows if r["league"]})
    team, league, needle = team.upper(), league.upper(), q.strip().lower()
    out = []
    for r in rows:
        if team and r["team"] != team or league and (r["league"] or "").upper() != league:
            continue
        if position == "F" and r["position"] == "G" or position in ("C", "L", "R", "D", "G") and r["position"] != position:
            continue
        if needle and needle not in r["name"].lower():
            continue
        if r["games"] < min_games and not needle:
            continue
        out.append(r)
    key = {"age": lambda r: (r["age"] is None, r["age"] or 0), "draft": lambda r: (r["draft"] is None, (r["draft"] or {}).get("overall") or 0),
           "name": lambda r: r["name"], "nhle": lambda r: (r["nhle"] is None, -(r["nhle"] or {}).get("points", 0))}.get(sort, lambda r: (r[sort] is None, -(r[sort] or 0)))
    out.sort(key=lambda r: (key(r), r["name"]))
    return {"season": config.SEASON_ID, "total": len(out), "leagues": leagues, "rows": out[:limit]}


@router.get("/api/prospects/{player_id}")
def prospect_detail(player_id: int):
    """A prospect's bio, draft details and every season's line in every league they've played in."""
    with psycopg.connect(config.DATABASE_URL, row_factory=dict_row) as conn:
        today = conn.execute("SELECT (now() AT TIME ZONE 'America/New_York')::date AS d").fetchone()["d"]
        p = conn.execute("SELECT * FROM prospect WHERE player_id = %s", (player_id,)).fetchone()
        if not p:
            raise HTTPException(404, "No prospect with that id")
        seasons = conn.execute(
            """SELECT season_id, game_type, league, team_name, games, goals, assists, points, pim, plus_minus, wins, save_pct, gaa
               FROM prospect_season WHERE player_id = %s ORDER BY season_id DESC, game_type, games DESC""", (player_id,)).fetchall()
        factors, ages = _nhle_factors(conn), _nhle_ages(conn)
    line = prospectlib.current_line(seasons, config.SEASON_ID)
    goalie = p["position"] == "G"
    return {**_prospect_row(p, line, today, factors, ages, seasons), "on_list": p["on_list"], "birth_date": p["birth_date"],
            "seasons": [{**s, "points_per_game": prospectlib.points_per_game(s),
                         "nhle": None if goalie or s["game_type"] != 2 else
                         nhle.nhle_line(s, factors, config.GAMES_PER_SEASON, nhle.age_on_season(s["season_id"], p["birth_date"]), ages)}
                        for s in seasons]}


# The upcoming draft class: NHL Central Scouting's rankings. They carry no player ids, so there are no stats here.
DRAFT_CATEGORIES = {1: "North American skaters", 2: "International skaters", 3: "North American goalies", 4: "International goalies"}


_draft_cache = {}   # category -> (fetched at, response)


DRAFT_TTL = 6 * 3600


def _draft_rankings_raw(category, upcoming):
    """The NHL's rankings response for the upcoming draft if it has published them, else for the latest class it has."""
    r = requests.get(f"{config.WEB_API}/draft/rankings/{upcoming}/{category}", timeout=15)
    if r.status_code == 200:
        return r.json()
    latest = requests.get(f"{config.WEB_API}/draft/rankings/now", timeout=15).json()
    if category == 1:
        return latest
    return requests.get(f"{config.WEB_API}/draft/rankings/{latest['draftYear']}/{category}", timeout=15).json()


@router.get("/api/draft/rankings")
def draft_rankings(category: int = 1):
    """Central Scouting's rankings for the upcoming draft (category 1 NA skaters, 2 international skaters, 3 NA goalies,
    4 international goalies), cached for six hours. `already_drafted` is true when the NHL has not yet published rankings
    for the next draft and these are last June's class."""
    if category not in DRAFT_CATEGORIES:
        raise HTTPException(400, "category must be 1, 2, 3 or 4")
    hit = _draft_cache.get(category)
    today = datetime.now(timezone.utc).date()
    upcoming = today.year if today.month <= 6 else today.year + 1   # the draft is in June
    if not hit or time.time() - hit[0] > DRAFT_TTL:
        try:
            raw = _draft_rankings_raw(category, upcoming)
            rows = raw["rankings"]
        except (requests.RequestException, ValueError, KeyError):
            if hit:
                raw, rows = hit[1]
            else:
                raise HTTPException(502, "The NHL rankings are not available right now")
        else:
            _draft_cache[category] = (time.time(), (raw, rows))
            hit = _draft_cache[category]
    raw, rows = hit[1]
    out = []
    for r in rows:
        born = date.fromisoformat(r["birthDate"]) if r.get("birthDate") else None
        out.append({"rank": r.get("finalRank") or r.get("midtermRank"), "midterm_rank": r.get("midtermRank"),
                    "final_rank": r.get("finalRank"), "name": f"{r.get('firstName', '')} {r.get('lastName', '')}".strip(),
                    "position": r.get("positionCode"), "shoots": r.get("shootsCatches"),
                    "club": r.get("lastAmateurClub"), "league": r.get("lastAmateurLeague"),
                    "age": prospectlib.age_on(born, today), "birth_date": r.get("birthDate"), "height_in": r.get("heightInInches"), "weight_lb": r.get("weightInPounds"),
                    "birth_country": r.get("birthCountry")})
    out.sort(key=lambda r: (r["rank"] is None, r["rank"] or 0, r["name"]))
    year = raw.get("draftYear")
    # the rankings carry no player ids: link the rows we can to a stored prospect of that draft class, by name
    with psycopg.connect(config.DATABASE_URL, row_factory=dict_row) as conn:
        known = conn.execute("SELECT player_id, name, birth_date, draft_year, draft_round, draft_pick, draft_overall, draft_team FROM prospect "
                             "WHERE draft_year = %s", (year,)).fetchall()
    linked = prospectlib.link_rankings(out, known, year)
    # the NHL keeps serving last June's class until it publishes the next one: say so rather than call it upcoming
    return {"draft_year": year, "upcoming_year": upcoming, "already_drafted": bool(year and year < upcoming),
            "category": category, "categories": DRAFT_CATEGORIES, "linked": linked, "rows": out}


# --- Role changes ---------------------------------------------------------------------------------
@router.get("/api/roles/changes")
def role_changes(window: int = 5, kind: str = "all", dir: str = "up", position: str = "", limit: int = 50):
    """Skaters whose power-play unit or even-strength ice time moved over their last `window` games compared with
    their earlier games this season (see roles.py). dir=up lists promotions and rising ice time, dir=down the
    opposite; kind=pp or ev narrows it to one of the two."""
    if kind not in ("all", "pp", "ev"):
        raise HTTPException(400, "kind must be all, pp or ev")
    if dir not in ("up", "down"):
        raise HTTPException(400, "dir must be up or down")
    window = max(2, min(window, 20))
    limit = max(1, min(limit, 200))
    with psycopg.connect(config.DATABASE_URL, row_factory=dict_row) as conn:
        lines = roles_db.player_lines(conn, config.SEASON_ID, window)
    rows = []
    for r in lines.values():
        if position == "F" and r["position"] == "D" or position in ("C", "L", "R", "D") and r["position"] != position:
            continue
        hit = {"all": (r["pp_change"], r["ev_change"]), "pp": (r["pp_change"],), "ev": (r["ev_change"],)}[kind]
        if dir in hit:
            rows.append(r)
    # Biggest move first. Together, a power-play move outweighs a change in even-strength time: the share moves by
    # tenths while the time moves by minutes, so the two are put on a similar scale (0.1 of share ~ 30 seconds).
    size = {"pp": lambda r: r["pp_share_delta"], "ev": lambda r: r["ev_delta"],
            "all": lambda r: r["pp_share_delta"] * 10 + r["ev_delta"] / 300}[kind]
    rows.sort(key=lambda r: (size(r), r["name"]), reverse=dir == "up")
    return {"season": config.SEASON_ID, "window": window, "kind": kind, "dir": dir, "rows": rows[:limit],
            "thresholds": {"pp1": roles.PP1_SHARE, "pp2": roles.PP2_SHARE, "ev_seconds": roles.EV_CHANGE_SEC,
                           "min_base_games": roles.MIN_BASE_GAMES}}


@router.get("/api/roles/players")
def role_players(ids: str = "", window: int = 5):
    """Role-change figures for specific skaters (comma-separated ids), keyed by player id. Skaters without enough
    games to compare are left out."""
    try:
        wanted = [int(x) for x in ids.split(",") if x.strip()][:100]
    except ValueError:
        raise HTTPException(400, "ids must be comma-separated player ids")
    window = max(2, min(window, 20))
    if not wanted:
        return {"season": config.SEASON_ID, "window": window, "players": {}}
    with psycopg.connect(config.DATABASE_URL, row_factory=dict_row) as conn:
        lines = roles_db.player_lines(conn, config.SEASON_ID, window, ids=wanted)
    return {"season": config.SEASON_ID, "window": window, "players": lines}
