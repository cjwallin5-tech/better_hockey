"""Private fantasy leagues: friends share their rosters so the site can see who is actually taken.

A league has an owner, an invite code and optional shared settings (scoring and slots). Each member has one team whose
roster is that member's own synced fantasy roster (fantasy_state), so it stays current without extra steps. The owner can also add
teams managed by hand for friends who don't use the site, so a league can be complete. Rosters are visible only to the league's
members, and only team names are shown to other members, never emails.

Limits worth knowing: a user has one synced roster, so the same roster shows in every league they are in; and a team's roster is
only as current as its owner's last sync (a signed-in browser syncs on every change).
"""
import re
import secrets

import psycopg
from fastapi import APIRouter, HTTPException, Request
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from pydantic import BaseModel

import auth
import config

router = APIRouter(prefix="/api")

MAX_LEAGUES_OWNED = 5
MAX_LEAGUES_JOINED = 10
MIN_TEAMS, MAX_TEAMS = 2, 32
MAX_ROSTER = auth.MAX_ROSTER
NAME_LEN = 60
CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"   # no I, O, 0 or 1: easy to read out
CODE_LEN = 8
GROUPS = ("C", "L", "R", "D", "G")

DDL = """
CREATE TABLE IF NOT EXISTS league (
    id          BIGSERIAL PRIMARY KEY,
    name        TEXT NOT NULL,
    owner_id    BIGINT NOT NULL REFERENCES app_user(id) ON DELETE CASCADE,
    invite_code TEXT NOT NULL UNIQUE,
    teams       INTEGER NOT NULL DEFAULT 12,
    settings    JSONB NOT NULL DEFAULT '{}',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS league_team (
    id         BIGSERIAL PRIMARY KEY,
    league_id  BIGINT NOT NULL REFERENCES league(id) ON DELETE CASCADE,
    name       TEXT NOT NULL,
    user_id    BIGINT REFERENCES app_user(id) ON DELETE CASCADE,   -- NULL: a team the owner manages by hand
    players    JSONB NOT NULL DEFAULT '[]',                         -- used only by hand-managed teams
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (league_id, user_id)
);
CREATE INDEX IF NOT EXISTS league_team_user_idx ON league_team (user_id);
"""


def init_db():
    with psycopg.connect(config.DATABASE_URL) as conn:
        conn.execute(DDL)


# --- Pure helpers (tested without a database) ----------------------------------------------------------

def new_invite_code():
    return "".join(secrets.choice(CODE_ALPHABET) for _ in range(CODE_LEN))


def clean_code(raw):
    """An invite code as typed or pasted: upper case, letters and digits only, or None when it can't be one."""
    code = re.sub(r"[^A-Za-z0-9]", "", raw or "").upper()
    return code if len(code) == CODE_LEN else None


def clean_name(raw, default=None):
    name = " ".join((raw or "").split())[:NAME_LEN]
    return name or default


def clean_players(raw):
    """A roster list kept to what the site uses: {id, kind, name}, valid kinds only, no repeats, at most MAX_ROSTER."""
    out, seen = [], set()
    for p in (raw or []):
        if not isinstance(p, dict) or not isinstance(p.get("id"), int) or isinstance(p.get("id"), bool):
            continue
        if p.get("kind") not in ("skater", "goalie") or not isinstance(p.get("name"), str) or p["id"] in seen:
            continue
        seen.add(p["id"])
        out.append({"id": p["id"], "kind": p["kind"], "name": p["name"][:100]})
        if len(out) >= MAX_ROSTER:
            break
    return out


def _whole(v, lo, hi):
    return min(hi, max(lo, int(v))) if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def clean_settings(raw):
    """Shared league settings: {format, slots, scoring, categories}, each part kept only when valid.

    format is 'points' or 'categories'; slots are whole numbers 0-10 for C, L, R, D and G; scoring is numbers by stat name;
    categories are lists of short names for skaters and goalies. Anything else is dropped."""
    raw = raw if isinstance(raw, dict) else {}
    out = {}
    if raw.get("format") in ("points", "categories"):
        out["format"] = raw["format"]
    slots = raw.get("slots")
    if isinstance(slots, dict):
        cleaned = {g: _whole(slots.get(g), 0, 10) for g in GROUPS}
        out["slots"] = {g: v for g, v in cleaned.items() if v is not None}
    scoring = raw.get("scoring")
    if isinstance(scoring, dict):
        out["scoring"] = {k: float(v) for k, v in scoring.items()
                          if isinstance(k, str) and 0 < len(k) < 40 and isinstance(v, (int, float)) and not isinstance(v, bool)}
    cats = raw.get("categories")
    if isinstance(cats, dict):
        out["categories"] = {kind: [c for c in (cats.get(kind) or []) if isinstance(c, str) and 0 < len(c) < 30][:20]
                             for kind in ("skater", "goalie")}
    return out


def taken_ids(teams):
    """Every player id on any team: [{players: [{id}...]}...] -> set of ids."""
    return {p["id"] for t in teams for p in t["players"]}


def team_view(row, viewer_id, roster):
    """One team as members see it. roster: the team's players (the owner's synced roster, or the hand-managed list).
    No email is shown: a member is identified by the team name."""
    return {"id": row["id"], "name": row["name"], "manual": row["user_id"] is None,
            "mine": row["user_id"] is not None and row["user_id"] == viewer_id, "players": roster}


def league_view(league, team_rows, rosters, viewer_id):
    """The league as a member sees it. rosters: {user_id: players} for user-linked teams."""
    teams = []
    for r in team_rows:
        roster = clean_players(r["players"]) if r["user_id"] is None else clean_players(rosters.get(r["user_id"], []))
        teams.append(team_view(r, viewer_id, roster))
    owner_team = next((t for t, r in zip(teams, team_rows) if r["user_id"] == league["owner_id"]), None)
    return {"id": league["id"], "name": league["name"], "teams_allowed": league["teams"], "settings": league["settings"] or {},
            "is_owner": league["owner_id"] == viewer_id, "owner_team": owner_team["name"] if owner_team else None,
            "teams": teams, "taken": sorted(taken_ids(teams)), "created_at": league["created_at"]}


# --- Routes ---------------------------------------------------------------------------------------------

def _user(conn, request):
    user = auth.current_user(conn, request)
    if not user:
        raise HTTPException(401, "Not signed in")
    return user


def _league_for_member(conn, league_id, user):
    """(league row, the user's team row or None). 404 for a league the user is not in, so ids can't be probed."""
    league = conn.execute("SELECT * FROM league WHERE id = %s", (league_id,)).fetchone()
    mine = conn.execute("SELECT * FROM league_team WHERE league_id = %s AND user_id = %s", (league_id, user["id"])).fetchone()
    if not league or not mine:
        raise HTTPException(404, "League not found")
    return league, mine


def _owner_league(conn, league_id, user):
    league, mine = _league_for_member(conn, league_id, user)
    if league["owner_id"] != user["id"]:
        raise HTTPException(403, "Only the league's owner can do that")
    return league, mine


def _detail(conn, league, viewer_id):
    teams = conn.execute("SELECT * FROM league_team WHERE league_id = %s ORDER BY created_at, id", (league["id"],)).fetchall()
    ids = [t["user_id"] for t in teams if t["user_id"] is not None]
    rosters = {r["user_id"]: r["players"] for r in conn.execute(
        "SELECT user_id, players FROM fantasy_state WHERE user_id = ANY(%s)", (ids,))} if ids else {}
    out = league_view(league, teams, rosters, viewer_id)
    if out["is_owner"]:
        out["invite_code"] = league["invite_code"]
    return out


def _unique_code(conn):
    for _ in range(10):
        code = new_invite_code()
        if not conn.execute("SELECT 1 FROM league WHERE invite_code = %s", (code,)).fetchone():
            return code
    raise HTTPException(500, "Couldn't make an invite code; try again")


class LeagueIn(BaseModel):
    name: str
    team_name: str = ""
    teams: int = 12
    settings: dict = {}


@router.post("/leagues")
def create_league(body: LeagueIn, request: Request):
    name = clean_name(body.name)
    if not name:
        raise HTTPException(400, "Give the league a name")
    teams = _whole(body.teams, MIN_TEAMS, MAX_TEAMS) or 12
    with psycopg.connect(config.DATABASE_URL, row_factory=dict_row) as conn:
        user = _user(conn, request)
        owned = conn.execute("SELECT count(*) AS n FROM league WHERE owner_id = %s", (user["id"],)).fetchone()["n"]
        if owned >= MAX_LEAGUES_OWNED:
            raise HTTPException(400, f"You can own up to {MAX_LEAGUES_OWNED} leagues")
        league = conn.execute(
            "INSERT INTO league (name, owner_id, invite_code, teams, settings) VALUES (%s, %s, %s, %s, %s) RETURNING *",
            (name, user["id"], _unique_code(conn), teams, Jsonb(clean_settings(body.settings)))).fetchone()
        conn.execute("INSERT INTO league_team (league_id, name, user_id) VALUES (%s, %s, %s)",
                     (league["id"], clean_name(body.team_name, "My team"), user["id"]))
        return _detail(conn, league, user["id"])


@router.get("/leagues")
def list_leagues(request: Request):
    with psycopg.connect(config.DATABASE_URL, row_factory=dict_row) as conn:
        user = _user(conn, request)
        rows = conn.execute(
            """SELECT l.id, l.name, l.teams, l.owner_id, t.name AS my_team,
                      (SELECT count(*) FROM league_team x WHERE x.league_id = l.id) AS team_count
               FROM league l JOIN league_team t ON t.league_id = l.id AND t.user_id = %s ORDER BY l.created_at""",
            (user["id"],)).fetchall()
    return {"leagues": [{"id": r["id"], "name": r["name"], "teams_allowed": r["teams"], "team_count": r["team_count"],
                         "my_team": r["my_team"], "is_owner": r["owner_id"] == user["id"]} for r in rows]}


@router.get("/leagues/{league_id}")
def get_league(league_id: int, request: Request):
    with psycopg.connect(config.DATABASE_URL, row_factory=dict_row) as conn:
        user = _user(conn, request)
        league, _ = _league_for_member(conn, league_id, user)
        return _detail(conn, league, user["id"])


class LeaguePatch(BaseModel):
    name: str | None = None
    teams: int | None = None
    settings: dict | None = None


@router.put("/leagues/{league_id}")
def update_league(league_id: int, body: LeaguePatch, request: Request):
    with psycopg.connect(config.DATABASE_URL, row_factory=dict_row) as conn:
        user = _user(conn, request)
        league, _ = _owner_league(conn, league_id, user)
        name = clean_name(body.name, league["name"]) if body.name is not None else league["name"]
        teams = _whole(body.teams, MIN_TEAMS, MAX_TEAMS) if body.teams is not None else league["teams"]
        count = conn.execute("SELECT count(*) AS n FROM league_team WHERE league_id = %s", (league_id,)).fetchone()["n"]
        if teams is None or teams < count:
            raise HTTPException(400, f"The league already has {count} teams")
        settings = clean_settings(body.settings) if body.settings is not None else league["settings"]
        league = conn.execute("UPDATE league SET name = %s, teams = %s, settings = %s WHERE id = %s RETURNING *",
                              (name, teams, Jsonb(settings), league_id)).fetchone()
        return _detail(conn, league, user["id"])


@router.post("/leagues/{league_id}/invite/reset")
def reset_invite(league_id: int, request: Request):
    with psycopg.connect(config.DATABASE_URL, row_factory=dict_row) as conn:
        user = _user(conn, request)
        _owner_league(conn, league_id, user)
        code = _unique_code(conn)
        conn.execute("UPDATE league SET invite_code = %s WHERE id = %s", (code, league_id))
    return {"invite_code": code}


@router.delete("/leagues/{league_id}")
def delete_league(league_id: int, request: Request):
    with psycopg.connect(config.DATABASE_URL, row_factory=dict_row) as conn:
        user = _user(conn, request)
        _owner_league(conn, league_id, user)
        conn.execute("DELETE FROM league WHERE id = %s", (league_id,))
    return {"ok": True}


class JoinIn(BaseModel):
    code: str
    team_name: str = ""


@router.post("/leagues/join")
def join_league(body: JoinIn, request: Request):
    code = clean_code(body.code)
    if not code:
        raise HTTPException(400, "That isn't an invite code")
    with psycopg.connect(config.DATABASE_URL, row_factory=dict_row) as conn:
        user = _user(conn, request)
        league = conn.execute("SELECT * FROM league WHERE invite_code = %s", (code,)).fetchone()
        if not league:
            raise HTTPException(404, "No league has that invite code")
        if conn.execute("SELECT 1 FROM league_team WHERE league_id = %s AND user_id = %s", (league["id"], user["id"])).fetchone():
            raise HTTPException(409, "You are already in that league")
        joined = conn.execute("SELECT count(*) AS n FROM league_team WHERE user_id = %s", (user["id"],)).fetchone()["n"]
        if joined >= MAX_LEAGUES_JOINED:
            raise HTTPException(400, f"You can be in up to {MAX_LEAGUES_JOINED} leagues")
        count = conn.execute("SELECT count(*) AS n FROM league_team WHERE league_id = %s", (league["id"],)).fetchone()["n"]
        if count >= league["teams"]:
            raise HTTPException(400, "That league is full")
        conn.execute("INSERT INTO league_team (league_id, name, user_id) VALUES (%s, %s, %s)",
                     (league["id"], clean_name(body.team_name, "My team"), user["id"]))
        return _detail(conn, league, user["id"])


@router.delete("/leagues/{league_id}/membership")
def leave_league(league_id: int, request: Request):
    with psycopg.connect(config.DATABASE_URL, row_factory=dict_row) as conn:
        user = _user(conn, request)
        league, mine = _league_for_member(conn, league_id, user)
        if league["owner_id"] == user["id"]:
            raise HTTPException(400, "The owner can't leave; delete the league instead")
        conn.execute("DELETE FROM league_team WHERE id = %s", (mine["id"],))
    return {"ok": True}


class TeamIn(BaseModel):
    name: str
    players: list[dict] = []


@router.post("/leagues/{league_id}/teams")
def add_manual_team(league_id: int, body: TeamIn, request: Request):
    """The owner adds a team for someone who doesn't use the site, with a roster entered by hand."""
    name = clean_name(body.name)
    if not name:
        raise HTTPException(400, "Give the team a name")
    with psycopg.connect(config.DATABASE_URL, row_factory=dict_row) as conn:
        user = _user(conn, request)
        league, _ = _owner_league(conn, league_id, user)
        count = conn.execute("SELECT count(*) AS n FROM league_team WHERE league_id = %s", (league_id,)).fetchone()["n"]
        if count >= league["teams"]:
            raise HTTPException(400, "The league is full")
        conn.execute("INSERT INTO league_team (league_id, name, players) VALUES (%s, %s, %s)",
                     (league_id, name, Jsonb(clean_players(body.players))))
        return _detail(conn, league, user["id"])


class TeamPatch(BaseModel):
    name: str


@router.put("/leagues/{league_id}/teams/{team_id}")
def rename_team(league_id: int, team_id: int, body: TeamPatch, request: Request):
    """A member renames their own team; the owner can rename any."""
    name = clean_name(body.name)
    if not name:
        raise HTTPException(400, "Give the team a name")
    with psycopg.connect(config.DATABASE_URL, row_factory=dict_row) as conn:
        user = _user(conn, request)
        league, mine = _league_for_member(conn, league_id, user)
        team = conn.execute("SELECT * FROM league_team WHERE id = %s AND league_id = %s", (team_id, league_id)).fetchone()
        if not team:
            raise HTTPException(404, "Team not found")
        if team["id"] != mine["id"] and league["owner_id"] != user["id"]:
            raise HTTPException(403, "You can only rename your own team")
        conn.execute("UPDATE league_team SET name = %s WHERE id = %s", (name, team_id))
        return _detail(conn, league, user["id"])


class PlayersIn(BaseModel):
    players: list[dict]


@router.put("/leagues/{league_id}/teams/{team_id}/players")
def set_manual_roster(league_id: int, team_id: int, body: PlayersIn, request: Request):
    """The owner sets the roster of a hand-managed team. Members' own teams follow their synced fantasy roster instead."""
    with psycopg.connect(config.DATABASE_URL, row_factory=dict_row) as conn:
        user = _user(conn, request)
        league, _ = _owner_league(conn, league_id, user)
        team = conn.execute("SELECT * FROM league_team WHERE id = %s AND league_id = %s", (team_id, league_id)).fetchone()
        if not team:
            raise HTTPException(404, "Team not found")
        if team["user_id"] is not None:
            raise HTTPException(400, "That team follows its owner's fantasy roster")
        conn.execute("UPDATE league_team SET players = %s WHERE id = %s", (Jsonb(clean_players(body.players)), team_id))
        return _detail(conn, league, user["id"])


@router.delete("/leagues/{league_id}/teams/{team_id}")
def remove_team(league_id: int, team_id: int, request: Request):
    """The owner removes a team (a member who left the league's table, or a hand-managed team). Not their own."""
    with psycopg.connect(config.DATABASE_URL, row_factory=dict_row) as conn:
        user = _user(conn, request)
        league, mine = _owner_league(conn, league_id, user)
        team = conn.execute("SELECT * FROM league_team WHERE id = %s AND league_id = %s", (team_id, league_id)).fetchone()
        if not team:
            raise HTTPException(404, "Team not found")
        if team["id"] == mine["id"]:
            raise HTTPException(400, "Delete the league instead of removing your own team")
        conn.execute("DELETE FROM league_team WHERE id = %s", (team_id,))
        return _detail(conn, league, user["id"])
