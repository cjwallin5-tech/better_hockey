"""History and records endpoints: all-time tables, best seasons, era factors, records, past seasons, international results, retired numbers."""

from fastapi import APIRouter, HTTPException
import psycopg
from psycopg.rows import dict_row
import requests

import bestseasons
import config
import era
import internationals
import records
import seasonlists
import seasonpages
from routes.common import ALLTIME_TABLES, SKATERS_SQL, _season_board, ttl_cached

router = APIRouter()


ALLTIME_SORTS = {
    "skater": {"name", "first_season", "games_played", "goals", "assists", "points", "points_per_game",
               "plus_minus", "pim", "ev_goals", "pp_goals", "pp_points", "sh_goals", "sh_points",
               "game_winning_goals", "ot_goals", "shots", "shooting_pct", "fo_win_pct", "hits", "blocked_shots",
               "takeaways", "giveaways", "missed_shots", "shot_attempts", "empty_net_goals", "first_goals",
               "adj_goals", "adj_assists", "adj_points", "adj_points_per_game", "goals_per_game", "assists_per_game",
               "so_att", "so_goals", "so_pct", "so_gwg",
               *(c for c, _ in records.COLUMNS if c not in ("goals_per_game", "assists_per_game"))},
    "goalie": {"name", "first_season", "games_played", "games_started", "wins", "losses", "ot_losses",
               "ties", "saves", "shots_against", "goals_against", "save_pct", "gaa", "shutouts", "toi_sec",
               "so_att", "so_saves", "so_sv_pct", "so_wins", "so_losses"},
}


# --- Era adjustment ---------------------------------------------------------------------------
_era_cache = {"sig": None, "data": None}


@router.get("/api/era-factors")
def era_factors():
    """Per-season, per-role multipliers that turn goals and assists into today's scoring terms (see era.py)."""
    with psycopg.connect(config.DATABASE_URL) as conn:
        sig = conn.execute("SELECT count(*), coalesce(sum(points), 0) FROM career_season").fetchone()
        if _era_cache["sig"] != sig:
            rows = era.load_rows(conn)
            rates = era.league_rates(rows)
            ref = era.reference_rates(rates, config.SEASON_ID - 10001)
            fac = era.factors(rates, ref)
            seasons = {}
            for (season, rl), f in fac.items():
                seasons.setdefault(str(season), {})[rl] = {k: round(v, 4) for k, v in f.items()}
            _era_cache.update(sig=sig, data={
                "reference_seasons": [config.SEASON_ID - 10001 * i for i in range(1, era.REFERENCE_SEASONS + 1)],
                "today": {rl: {k: round(v, 4) for k, v in r.items()} for rl, r in ref.items()}, "seasons": seasons})
    return _era_cache["data"]


@router.get("/api/alltime/{kind}")
def alltime(
    kind: str,
    game_type: int = 2,
    sort: str | None = None,
    dir: str = "desc",
    q: str = "",
    position: str = "",
    country: str = "",
    active: bool = False,
    hof: bool = False,
    min_gp: int = 0,
    min_att: int = 0,
    debut_from: int | None = None,
    debut_to: int | None = None,
    has: str = "",
    limit: int = 50,
    offset: int = 0,
    export: bool = False,
):
    """Career totals for every player in NHL history, sorted/filtered/paged server-side. `has` names a stat that must be above zero
    (the hat trick board leaves out players with none)."""
    if kind not in ALLTIME_TABLES:
        raise HTTPException(404, "Unknown board")
    if game_type not in (2, 3):
        raise HTTPException(400, "game_type must be 2 (regular season) or 3 (playoffs)")
    default_sort = "points" if kind == "skater" else "wins"
    sort = sort or default_sort
    if sort not in ALLTIME_SORTS[kind]:
        raise HTTPException(400, f"Can't sort by {sort}")
    direction = "ASC" if dir.lower() == "asc" else "DESC"
    limit, offset = max(1, min(limit, 10000 if export else 200)), max(0, offset)

    where, params = ["game_type = %(game_type)s"], {"game_type": game_type}
    if q.strip():
        where.append("name ILIKE %(q)s")
        params["q"] = f"%{q.strip()}%"
    if kind == "skater" and position:
        if position == "F":
            where.append("position <> 'D'")
        else:
            where.append("position = %(position)s")
            params["position"] = position
    if country:
        where.append("birth_country = %(country)s")
        params["country"] = country
    if active:
        where.append("active_season IS NOT NULL")
    if hof:
        where.append("hall_of_fame = 'Y'")
    if min_gp > 0:
        where.append("games_played >= %(min_gp)s")
        params["min_gp"] = min_gp
    if min_att > 0:
        where.append("so_att >= %(min_att)s")
        params["min_att"] = min_att
    if has:
        if has not in ALLTIME_SORTS[kind] or has == "name":
            raise HTTPException(400, f"Can't filter on {has}")
        where.append(f"{has} > 0")
    if debut_from is not None:
        where.append("first_season >= %(debut_from)s")
        params["debut_from"] = debut_from * 10000 + debut_from + 1
    if debut_to is not None:
        where.append("first_season <= %(debut_to)s")
        params["debut_to"] = debut_to * 10000 + debut_to + 1

    table, clause = ALLTIME_TABLES[kind], " AND ".join(where)
    with psycopg.connect(config.DATABASE_URL, row_factory=dict_row) as conn:
        total = conn.execute(f"SELECT count(*) AS n FROM {table} WHERE {clause}", params).fetchone()["n"]
        # place/tied: the player's rank in the whole filtered list (not just this page) by the sorted stat, where players with the
        # same value share a place. A text sort (name) and missing values have no ties, so they just count.
        ranked = sort != "name"
        rows = conn.execute(
            f"SELECT *, "
            + (f"rank() OVER (ORDER BY {sort} {direction} NULLS LAST) AS place, "
               f"({sort} IS NOT NULL AND count(*) OVER (PARTITION BY {sort}) > 1) AS tied "
               if ranked else
               f"row_number() OVER (ORDER BY name {direction}) AS place, false AS tied ")
            + f"FROM {table} WHERE {clause} "
            f"ORDER BY {sort} {direction} NULLS LAST, name LIMIT %(limit)s OFFSET %(offset)s",
            {**params, "limit": limit, "offset": offset},
        ).fetchall()
        # each player's most recent season and team, so the page can show a headshot (the picture host is keyed by season, team and id)
        last_sql = ("SELECT DISTINCT ON (player_id) player_id, season_id, team FROM career_season WHERE player_id = ANY(%s) ORDER BY player_id, season_id DESC"
                    if kind == "skater" else
                    "SELECT DISTINCT ON (player_id) player_id, season_id, team FROM goalie_season WHERE player_id = ANY(%s) ORDER BY player_id, season_id DESC")
        last = {x["player_id"]: x for x in conn.execute(last_sql, ([r["player_id"] for r in rows],)).fetchall()}
    for r in rows:
        r.pop("updated_at", None)
        seen = last.get(r["player_id"])
        r["last_season"], r["last_team"] = (seen["season_id"], seen["team"]) if seen else (None, None)
    return {"total": total, "offset": offset, "limit": limit, "sort": sort, "dir": direction.lower(), "rows": rows}


@router.get("/api/best-seasons/{kind}")
def best_seasons(kind: str, sort: str | None = None, dir: str = "desc", q: str = "", position: str = "", active: bool = False,
                 hof: bool = False, min_gp: int | None = None, season_from: int | None = None, season_to: int | None = None,
                 limit: int = 50, offset: int = 0, export: bool = False):
    """The best individual seasons in NHL history for one kind of player ('skater' from 1917-18, 'goalie' from 2005-06), by any stat,
    filtered and paged. Each row is one player's one season, with its place in the filtered list (`place`, and `tied` when shared)."""
    if kind not in bestseasons.SORTS:
        raise HTTPException(404, "Unknown board")
    sort = sort or ("points" if kind == "skater" else "wins")
    if sort not in bestseasons.SORTS[kind]:
        raise HTTPException(400, f"Can't sort by {sort}")
    limit, offset = max(1, min(limit, 10000 if export else 200)), max(0, offset)
    with psycopg.connect(config.DATABASE_URL, row_factory=dict_row) as conn:
        board = _season_board(conn, kind)
    rows, total = bestseasons.query(board, kind, sort=sort, direction="asc" if dir.lower() == "asc" else "desc", q=q, position=position,
                                    season_from=season_from, season_to=season_to, min_gp=min_gp, active=active, hof=hof,
                                    offset=offset, limit=limit)
    return {"total": total, "offset": offset, "limit": limit, "sort": sort, "dir": "asc" if dir.lower() == "asc" else "desc", "rows": rows}


# --- International tournaments ------------------------------------------------------------------
# Countries whose medals are pooled under one line in the medal tables (a country's predecessor and successor teams).
LINEAGE_NAMES = {"RUS": "Russia / Soviet Union", "CZE": "Czechia / Czechoslovakia", "GER": "Germany"}


def _lineage_name(code, names):
    return LINEAGE_NAMES.get(internationals.lineage(code)) or names.get(code, code)


@router.get("/api/international/results")
@ttl_cached(3600)
def international_results():
    """Every tournament's medalists by year (newest first) and a medal table by country, from data/international_results.json."""
    data = internationals.load_results()
    names = data["countries"]
    out = []
    for key, t in data["tournaments"].items():
        table = {}
        editions = []
        for year in sorted(t["results"], key=int, reverse=True):
            r = t["results"][year]
            editions.append({"year": int(year), **{m: {"code": r[m], "name": names[r[m]]} for m in internationals.MEDALS if m in r}})
            for m in internationals.MEDALS:
                if m in r:
                    row = table.setdefault(internationals.lineage(r[m]), {"country": _lineage_name(r[m], names), "gold": 0, "silver": 0, "bronze": 0})
                    row[m] += 1
        medal_table = sorted(table.values(), key=lambda c: (-c["gold"], -c["silver"], -c["bronze"], c["country"]))
        out.append({"id": key, "label": t["label"], "tier": t["tier"], "has_bronze": any("bronze" in r for r in t["results"].values()),
                    "editions": editions, "medal_table": medal_table})
    return {"tournaments": out, "source": data["source"], "built": data["built"]}


@router.get("/api/international/leaders")
@ttl_cached(300)
def international_leaders(tournament: str | None = None, limit: int = 25):
    """The most decorated players: medals won across the tournaments (or in one), gold first. Built from the international rows collected by
    `ingest.py backfill-international`, so `coverage` says how many players have been collected so far."""
    if tournament is not None and tournament not in internationals.LEAGUES:
        raise HTTPException(400, "Unknown tournament")
    limit = max(1, min(limit, 100))
    with psycopg.connect(config.DATABASE_URL, row_factory=dict_row) as conn:
        rows = conn.execute("SELECT player_id, season_id, league, team_name, games, goals, assists, points FROM player_international").fetchall()
        people = {r["player_id"]: r for r in conn.execute(
            """SELECT player_id, name, position, 'skater' AS kind, active_season FROM career_skater WHERE game_type = 2
               UNION ALL SELECT player_id, name, 'G', 'goalie', active_season FROM career_goalie WHERE game_type = 2""")}
        fetched = conn.execute("SELECT count(*) AS n FROM player_international_fetched").fetchone()["n"]
    by_player = {}
    for r in rows:
        by_player.setdefault(r["player_id"], []).append(r)
    board = []
    for pid, prow in by_player.items():
        if pid not in people:
            continue
        apps = [a for a in internationals.appearances(prow) if tournament in (None, a["tournament"])]
        medals = internationals.medal_counts(apps)
        if not any(medals.values()):
            continue
        p = people[pid]
        board.append({"player_id": pid, "name": p["name"], "position": p["position"], "kind": p["kind"], "active": p["active_season"] is not None,
                      **medals, "total": sum(medals.values()), "played": len(apps)})
    board.sort(key=lambda b: (-b["gold"], -b["silver"], -b["bronze"], -b["played"], b["name"]))
    return {"tournament": tournament, "players": board[:limit], "medalists": len(board),
            "coverage": {"fetched": fetched, "total": len(people)}}


def _triple_gold_members(conn, with_official=True):
    """Triple Gold Club members: computed from the collected tournament rows and Stanley Cups, plus (with_official) everyone on the IIHF roll
    that the NHL's own tournament history leaves out. Returns (members, number of players collected so far, number of players)."""
    cups = {}
    for r in conn.execute("SELECT player_id, season_id FROM player_award WHERE trophy = %s", (internationals.CUP,)):
        cups.setdefault(r["player_id"], []).append(r["season_id"])
    rows = conn.execute(
        "SELECT player_id, season_id, league, team_name, games, goals, assists, points FROM player_international WHERE player_id = ANY(%s)",
        (list(cups),)).fetchall()
    people = {r["player_id"]: r for r in conn.execute(
        """SELECT player_id, name, position, 'skater' AS kind, active_season FROM career_skater WHERE game_type = 2
           UNION ALL SELECT player_id, name, 'G', 'goalie', active_season FROM career_goalie WHERE game_type = 2""")}
    done = conn.execute("SELECT count(*) AS n FROM player_international_fetched WHERE awards_done").fetchone()["n"]
    official = internationals.official_club() if with_official else {}
    by_player = {}
    for r in rows:
        by_player.setdefault(r["player_id"], []).append(r)
    members, seen = [], set()
    for pid, prow in by_player.items():
        p = people.get(pid)
        if not p:
            continue
        tg = internationals.triple_gold(internationals.appearances(prow), sorted(cups[pid]), official.get(internationals.name_key(p["name"])))
        if tg:
            members.append({"player_id": pid, "name": p["name"], "position": p["position"], "kind": p["kind"],
                            "active": p["active_season"] is not None, "cups": len(cups[pid]), **tg})
            seen.add(internationals.name_key(p["name"]))
    # roll members whose rows are not collected yet (or never will be): matched to a player by name, preferring one with a Cup on record
    by_name = {}
    for pid, p in people.items():
        by_name.setdefault(internationals.name_key(p["name"]), []).append(pid)
    for key, entry in official.items():
        if key in seen:
            continue
        ids = by_name.get(key, [])
        pid = next((i for i in ids if i in cups), ids[0] if ids else None)
        if pid is not None:
            p = people[pid]
            members.append({"player_id": pid, "name": p["name"], "position": p["position"], "kind": p["kind"],
                            "active": p["active_season"] is not None, "cups": len(cups.get(pid, [])) or None, **entry, "source": "official"})
    members.sort(key=lambda m: (m["completed"], m["name"]))
    return members, done, len(people)


@router.get("/api/international/awards")
@ttl_cached(3600)
def international_awards(tournament: str | None = None, limit: int = 15):
    """The individual awards of the international tournaments (most valuable player and the IIHF directorate awards: best goaltender,
    defenseman and forward): the winners by year, newest first, and the players with the most. Names are linked to a player page only when
    exactly one player in our data has that name. See internationals.py and analysis/fetch_international_awards.py for what each tournament
    covers (`coverage`)."""
    if tournament is not None and tournament not in internationals.LEAGUES:
        raise HTTPException(400, "Unknown tournament")
    data = internationals.load_awards()
    limit = max(1, min(limit, 50))
    with psycopg.connect(config.DATABASE_URL, row_factory=dict_row) as conn:
        found = {}
        for r in conn.execute(
                """SELECT player_id, name, 'skater' AS kind FROM career_skater WHERE game_type = 2
                   UNION ALL SELECT player_id, name, 'goalie' FROM career_goalie WHERE game_type = 2"""):
            found.setdefault(internationals.name_key(r["name"]), []).append(r)
    link = lambda name: (lambda hits: {"player_id": hits[0]["player_id"], "kind": hits[0]["kind"]} if len(hits) == 1 else {})(found.get(internationals.name_key(name), []))

    out = {}
    for t in internationals.LEAGUES:
        if tournament not in (None, t):
            continue
        rows = [x for x in data["awards"] if x["tournament"] == t]
        years = {}
        counts = {}
        for x in rows:
            years.setdefault(x["year"], {})[x["award"]] = {"name": x["name"], "code": x["code"], "country": internationals.country_name(x["code"]), **link(x["name"])}
            c = counts.setdefault(internationals.name_key(x["name"]), {"name": x["name"], "total": 0, **{k: 0 for k in internationals.AWARD_ORDER}})
            c[x["award"]] += 1
            c["total"] += 1
        leaders = sorted(counts.values(), key=lambda c: (-c["total"], -c["mvp"], c["name"]))[:limit]
        out[t] = {"awards": [k for k in internationals.AWARD_ORDER if any(k in v for v in years.values())],
                  "editions": [{"year": y, "awards": years[y]} for y in sorted(years, reverse=True)],
                  "leaders": [{**c, **link(c["name"])} for c in leaders if c["total"] > 1]}
    return {"tournaments": out, "coverage": data["coverage"], "source": data["source"], "built": data["built"]}


@router.get("/api/international/triple-gold")
@ttl_cached(300)
def triple_gold_club():
    """The Triple Gold Club: players who have won the Stanley Cup, an Olympic gold medal and a World Championship gold medal, with the year
    of each and the year they completed it. Members are worked out from the tournament rows and awards `ingest.py backfill-international`
    collects, and the IIHF's own roll fills in members the NHL's tournament history leaves out (`source` says which; `coverage` says how
    many players are collected so far)."""
    with psycopg.connect(config.DATABASE_URL, row_factory=dict_row) as conn:
        members, done, total = _triple_gold_members(conn)
    return {"members": members, "coverage": {"fetched": done, "total": total}}


GAME_RECORD_STATS = {"goals", "assists", "points"}


@router.get("/api/records/games")
def game_records(stat: str = "goals", game_type: int = 2, q: str = "", position: str = "", limit: int = 50, offset: int = 0,
                 export: bool = False):
    """Single-game scoring records: the games with the most goals, assists or points by one skater (see records.py)."""
    if stat not in GAME_RECORD_STATS:
        raise HTTPException(400, f"Can't rank games by {stat}")
    if game_type not in (2, 3):
        raise HTTPException(400, "game_type must be 2 (regular season) or 3 (playoffs)")
    limit, offset = max(1, min(limit, 10000 if export else 200)), max(0, offset)
    where, params = ["game_type = %(game_type)s", f"{stat} >= 3"], {"game_type": game_type}
    if q.strip():
        where.append("name ILIKE %(q)s")
        params["q"] = f"%{q.strip()}%"
    if position == "F":
        where.append("position <> 'D'")
    elif position:
        where.append("position = %(position)s")
        params["position"] = position
    clause = " AND ".join(where)
    with psycopg.connect(config.DATABASE_URL, row_factory=dict_row) as conn:
        total = conn.execute(f"SELECT count(*) AS n FROM notable_game WHERE {clause}", params).fetchone()["n"]
        # Games with the same count share a place (a 5-goal game is a tie for first with every other 5-goal game).
        rows = conn.execute(
            f"SELECT *, rank() OVER (ORDER BY {stat} DESC) AS place, "
            f"(count(*) OVER (PARTITION BY {stat}) > 1) AS tied FROM notable_game WHERE {clause} "
            f"ORDER BY {stat} DESC, points DESC, game_date LIMIT %(limit)s OFFSET %(offset)s",
            {**params, "limit": limit, "offset": offset}).fetchall()
    for r in rows:
        r["game_date"] = r["game_date"].isoformat()
    return {"total": total, "offset": offset, "limit": limit, "stat": stat, "rows": rows}


@router.get("/api/alltime/{kind}/countries")
def alltime_countries(kind: str):
    if kind not in ALLTIME_TABLES:
        raise HTTPException(404, "Unknown board")
    with psycopg.connect(config.DATABASE_URL, row_factory=dict_row) as conn:
        rows = conn.execute(
            f"SELECT birth_country AS c, count(*) AS n FROM {ALLTIME_TABLES[kind]} "
            "WHERE game_type = 2 AND birth_country IS NOT NULL GROUP BY 1 ORDER BY 2 DESC"
        ).fetchall()
    return [r["c"] for r in rows]


@router.get("/api/records")
def records():
    """Single-season records and who is on pace to threaten them (scaled to this season's length)."""
    params = {"season": config.SEASON_ID, "window": config.RECENT_WINDOW, "games": config.GAMES_PER_SEASON}
    with psycopg.connect(config.DATABASE_URL, row_factory=dict_row) as conn:
        recs = conn.execute("SELECT stat, rank, player_id, name, season_id, games, value FROM season_record ORDER BY stat, rank").fetchall()
        skaters = conn.execute(SKATERS_SQL, params).fetchall()
    min_gp = max(1, -(-max(r["games_played"] for r in skaters) // 2))
    out = {}
    for stat in ("points", "goals", "assists"):
        best = next(r for r in recs if r["stat"] == stat and r["rank"] == 1)
        paces = sorted(
            ({"player_id": r["player_id"], "name": r["name"], "team": r["team"], "games_played": r["games_played"],
              "value": r[stat], "pace": round(r[stat] / r["games_played"] * config.GAMES_PER_SEASON, 1)}
             for r in skaters if r["games_played"] >= min_gp),
            key=lambda p: -p["pace"])[:5]
        out[stat] = {"record": best, "top_ten": [r for r in recs if r["stat"] == stat], "on_pace": paces}
    return {"records": out, "min_gp": min_gp, "games_per_season": config.GAMES_PER_SEASON}


@router.get("/api/history/season/{season}")
def history_season(season: int):
    """Who made their NHL debut in a season and who played their last (see seasonlists.py)."""
    if not (19171918 <= season <= config.SEASON_ID and season % 10000 - season // 10000 == 1):
        raise HTTPException(404, "No such season")
    with psycopg.connect(config.DATABASE_URL, row_factory=dict_row) as conn:
        return {"season": season, "debuts": seasonlists.debuts(conn, season), "finals": seasonlists.finals(conn, season, config.SEASON_ID)}


_nhl_cache = {}   # url -> payload; the NHL's answers for a finished season never change, so each is read once


def _nhl_json(url):
    """A web API payload, kept for good (only used for finished seasons). 502 when the NHL doesn't answer and we have nothing."""
    if url in _nhl_cache:
        return _nhl_cache[url]
    try:
        r = requests.get(url, timeout=20)
        r.raise_for_status()
        payload = r.json()
    except (requests.RequestException, ValueError):
        raise HTTPException(502, "The NHL site isn't answering right now")
    if len(_nhl_cache) >= 200:
        _nhl_cache.clear()
    _nhl_cache[url] = payload
    return payload


def _past_season(season):
    if not (19171918 <= season < config.SEASON_ID and season % 10000 - season // 10000 == 1):
        raise HTTPException(404, "No such finished season")


@router.get("/api/history/season/{season}/standings")
def history_season_standings(season: int):
    """A finished season's final standings, best first (see seasonpages.py). Empty for a season the NHL doesn't list (a lockout)."""
    _past_season(season)
    end = seasonpages.end_date(_nhl_json(f"{config.WEB_API}/standings-season"), season)
    rows = seasonpages.standings(_nhl_json(f"{config.WEB_API}/standings/{end}")) if end else []
    return {"season": season, "date": end, "rows": rows}


@router.get("/api/history/season/{season}/playoffs")
def history_season_playoffs(season: int):
    """A finished season's playoff series by round, and the Cup winner."""
    _past_season(season)
    return {"season": season, **seasonpages.playoffs(_nhl_json(f"{config.WEB_API}/playoff-bracket/{season % 10000}"))}


@router.get("/api/history/season/{season}/leaders")
def history_season_leaders(season: int):
    """The top ten skaters (and, from 2005-06, goalies) of a finished season."""
    _past_season(season)
    with psycopg.connect(config.DATABASE_URL, row_factory=dict_row) as conn:
        return {"season": season, **seasonpages.leaders(conn, season)}


@router.get("/api/history/numbers")
def history_numbers():
    """How many players have worn each sweater number."""
    with psycopg.connect(config.DATABASE_URL) as conn:
        return seasonlists.numbers(conn)


@router.get("/api/history/numbers/{number}")
def history_number(number: int):
    """Everyone who has worn a sweater number, with their teams and seasons."""
    with psycopg.connect(config.DATABASE_URL) as conn:
        return seasonlists.number_history(conn, number)
