"""Link previews: what a chat app or social network shows when someone pastes a link to the site.

Those services fetch the page without running JavaScript, so a single-page app looks the same at every address. The frontend's Vite
plugin (frontend/vite.config.js) asks this module, for each page it serves, for the tags that belong in <head> (GET /api/share/head)
and puts them into index.html. The tags point at a picture drawn here (GET /api/share/image.png): a 1200x630 card with the player's or
team's name, a few headline numbers and, for players, their headshot.

Everything that decides what to say is a pure function of database rows (`*_meta`), so it can be tested without a database. A page
that has no specific preview, or any failure, gets the site's generic one: a preview must never break a page.
"""
import html
import io
import logging
import re
import time
from datetime import datetime
from urllib.parse import parse_qs, quote, urlsplit
from zoneinfo import ZoneInfo

import psycopg
import requests
from fastapi import APIRouter, Response
from psycopg.rows import dict_row

import config

log = logging.getLogger("uvicorn.error")
router = APIRouter(prefix="/api/share")

SITE = "NHL Stats"
ET = ZoneInfo("America/New_York")
W, H = 1200, 630
GENERIC = ("Stats for every NHL skater, goalie and team, with advanced numbers, season projections, trophy odds, "
           "a prospects tracker and a fantasy toolkit.")

# Each team's main color (kept in step with frontend/src/teamColors.js); used for the card's accent.
TEAM_COLORS = {
    "ANA": "#F47A38", "BOS": "#FFB81C", "BUF": "#3A6FD8", "CGY": "#D2001C", "CAR": "#CC0000", "CHI": "#CF0A2C",
    "COL": "#A5314F", "CBJ": "#2A6BC4", "DAL": "#00A870", "DET": "#CE1126", "EDM": "#FF6A13", "FLA": "#C8102E",
    "LAK": "#A2AAAD", "MIN": "#2E7D5B", "MTL": "#AF1E2D", "NSH": "#FFB81C", "NJD": "#CE1126", "NYI": "#3E7BD6",
    "NYR": "#2D6FD6", "OTT": "#D2232A", "PHI": "#F74902", "PIT": "#FFB81C", "SJS": "#2B8FA0", "SEA": "#68A2B9",
    "STL": "#3A6FD8", "TBL": "#3A6FD8", "TOR": "#3A6FD8", "UTA": "#6CACE4", "VAN": "#3E8FD0", "VGK": "#B4975A",
    "WSH": "#D8212F", "WPG": "#4A78C2",
}
DEFAULT_ACCENT = "#38bdf8"
POSITIONS = {"C": "Center", "L": "Left wing", "R": "Right wing", "D": "Defenseman", "G": "Goalie"}

# Pages with their own words (everything else falls back to the generic preview).
PAGES = {
    "/": (SITE, GENERIC),
    "/skaters": ("Skater stats", "Every NHL skater this season, sortable by points, goals, shots, hits and more, with era-adjusted and advanced views."),
    "/goalies": ("Goalie stats", "Every NHL goalie this season: save percentage, goals against, goals saved above average and recent form."),
    "/standings": ("NHL standings", "Standings by division, conference and wild card, with playoff odds."),
    "/alltime/skaters": ("All-time skater leaders", "Career totals for every skater in NHL history, with era-adjusted scoring and Hall of Fame filters."),
    "/alltime/goalies": ("All-time goalie leaders", "Career totals for every goalie in NHL history."),
    "/compare": ("Compare players", "Put NHL players side by side: season and career stats, era-adjusted charts and head-to-head history."),
    "/projections": ("Season projections", "Where each skater's and goalie's points, goals, wins and saves are headed, with ranges."),
    "/prospects": ("NHL prospects", "Every team's prospects with junior, college and European stats, translated to NHL scoring (NHLe)."),
    "/tonight": ("Tonight's games", "Today's NHL games with win chances, probable goalies and who is hot."),
    "/awards": ("NHL award races", "Hart, Vezina, Norris and more: the race and the odds."),
    "/lottery": ("NHL draft lottery odds", "Lottery odds and lottery-position simulations for every non-playoff team."),
    "/schedule": ("NHL schedule", "The schedule with strength of schedule and back-to-back fatigue."),
    "/advanced-stats": ("Advanced stats", "Expected goals, special teams, score effects and tracking data."),
    "/accuracy": ("How accurate are our predictions?", "The site's win-chance and goalie-start predictions, scored against what happened."),
}
PRIVATE = {"/account", "/reset-password", "/my-team", "/leagues", "/watchlist", "/fantasy"}


# --- Small helpers -----------------------------------------------------------------------------------

def num(n):
    return "–" if n is None else f"{n:,}"


def season_label(season_id):
    """20262027 -> '2026-27'."""
    return f"{season_id // 10000}-{str(season_id % 10000)[2:]}"


def last_team(team):
    """A traded player's team is a comma list, latest last."""
    return (team or "").split(",")[-1].strip()


def accent_for(team):
    return TEAM_COLORS.get(last_team(team), DEFAULT_ACCENT)


def plural(n, one, many=None):
    return f"{num(n)} {one if n == 1 else (many or one + 's')}"


def initials(name):
    return "".join(w[0] for w in (name or "").split()[:2]).upper() or "NHL"


def headshot_url(season_id, team, player_id):
    """The NHL's picture host keeps one folder per season and team (the 'latest' folder only serves a grey silhouette)."""
    if not (season_id and team and player_id):
        return None
    return f"https://assets.nhle.com/mugs/nhl/{season_id}/{team}/{player_id}.png"


def _meta(title, description, *, headline=None, subline=None, accent=DEFAULT_ACCENT, stats=(), photo=None, badge=None,
          noindex=False, kind="website"):
    return {"title": title, "description": description, "headline": headline or title, "subline": subline or "",
            "accent": accent, "stats": list(stats)[:5], "photo": photo, "badge": badge or "NHL", "noindex": noindex, "kind": kind}


def default_meta():
    return _meta(SITE, GENERIC, headline="NHL Stats", subline="Every skater, goalie and team", badge="NHL")


# --- Which page is this? -------------------------------------------------------------------------------

def parse_route(url):
    """(kind, key, query) for a page address ('/player/8478402', '/compare?ids=1,2'). kind is player, goalie, prospect, game, team,
    compare, page (a static page, key = its path), private or default. Only the path and query are used."""
    parts = urlsplit(url or "/")
    path = "/" + parts.path.strip("/")
    query = parse_qs(parts.query)
    m = re.fullmatch(r"/(player|goalie|prospect|game)/(\d{1,12})", path)
    if m:
        return m.group(1), int(m.group(2)), query
    m = re.fullmatch(r"/team/([A-Za-z]{2,3})", path)
    if m:
        return "team", m.group(1).upper(), query
    if path == "/compare":
        return "compare", None, query
    if path in PAGES:
        return "page", path, query
    if path in PRIVATE or re.fullmatch(r"/league/\d+", path):
        return "private", path, query
    return "default", None, query


def compare_ids(query):
    """The player ids in a /compare link (?ids=1,2,3), at most four, digits only."""
    return [int(x) for x in re.findall(r"\d{1,12}", ",".join(query.get("ids", [])))][:4]


def route_key(kind, key, query):
    """What makes two page addresses give the same preview: made-up or unknown addresses all share one key, so they can't fill the
    cache or force a new picture each time."""
    return (kind, key, tuple(compare_ids(query)) if kind == "compare" else ())


# --- Pure builders: rows in, preview out ----------------------------------------------------------------

def skater_meta(row, season_id, games_per_season, player_id):
    team = last_team(row["team"])
    pos = POSITIONS.get(row["position"], "")
    pace = round(row["points"] / row["games_played"] * games_per_season) if row["games_played"] else None
    desc = (f"{season_label(season_id)} season: {plural(row['goals'], 'goal')}, {plural(row['assists'], 'assist')}, "
            f"{plural(row['points'], 'point')} in {plural(row['games_played'], 'game')}"
            + (f" (a {pace}-point pace)." if pace else "."))
    return _meta(f"{row['name']} ({pos}, {team})" if pos else row["name"], desc, headline=row["name"],
                 subline=f"{pos} · {team} · {season_label(season_id)}".strip(" ·"), accent=accent_for(team),
                 stats=[("GP", num(row["games_played"])), ("G", num(row["goals"])), ("A", num(row["assists"])), ("P", num(row["points"]))],
                 photo=headshot_url(season_id, team, player_id), badge=initials(row["name"]), kind="profile")


def career_skater_meta(row, last_season, last_team_abbrev, player_id):
    active = row.get("active_season") is not None
    pos = POSITIONS.get(row.get("position"), "")
    span = f" ({season_label(row['first_season'])} to {season_label(last_season)})" if row.get("first_season") and last_season else ""
    desc = (f"Career: {plural(row['goals'], 'goal')}, {plural(row['assists'], 'assist')}, {plural(row['points'], 'point')} "
            f"in {plural(row['games_played'], 'game')}{span}.")
    sub = " · ".join(x for x in (pos, "Career" if not active else "Career so far") if x)
    return _meta(f"{row['name']} ({pos})" if pos else row["name"], desc, headline=row["name"], subline=sub,
                 accent=accent_for(last_team_abbrev),
                 stats=[("GP", num(row["games_played"])), ("G", num(row["goals"])), ("A", num(row["assists"])), ("P", num(row["points"]))],
                 photo=headshot_url(last_season, last_team_abbrev, player_id), badge=initials(row["name"]), kind="profile")


def _sv(v):
    return "–" if v is None else f"{v:.3f}".lstrip("0")


def goalie_meta(row, season_id, player_id):
    team = last_team(row["team"])
    record = f"{row['wins']}-{row['losses']}-{row['ot_losses'] or 0}"
    desc = (f"{season_label(season_id)} season: {record}, {_sv(row['save_pct'])} save percentage, "
            f"{row['gaa']:.2f} goals-against average and {plural(row['shutouts'] or 0, 'shutout')} in {plural(row['games_played'], 'game')}.")
    return _meta(f"{row['name']} (Goalie, {team})", desc, headline=row["name"], subline=f"Goalie · {team} · {season_label(season_id)}",
                 accent=accent_for(team),
                 stats=[("GP", num(row["games_played"])), ("W-L-OTL", record), ("SV%", _sv(row["save_pct"])),
                        ("GAA", f"{row['gaa']:.2f}"), ("SO", num(row["shutouts"] or 0))],
                 photo=headshot_url(season_id, team, player_id), badge=initials(row["name"]), kind="profile")


def career_goalie_meta(row, last_season, last_team_abbrev, player_id):
    record = f"{num(row['wins'])}-{num(row['losses'])}-{num(row['ot_losses'] or 0)}"
    desc = (f"Career: {record}, {_sv(row['save_pct'])} save percentage, {row['gaa']:.2f} goals-against average "
            f"and {plural(row['shutouts'] or 0, 'shutout')} in {plural(row['games_played'], 'game')}.")
    return _meta(f"{row['name']} (Goalie)", desc, headline=row["name"], subline="Goalie · Career", accent=accent_for(last_team_abbrev),
                 stats=[("GP", num(row["games_played"])), ("W", num(row["wins"])), ("SV%", _sv(row["save_pct"])),
                        ("GAA", f"{row['gaa']:.2f}"), ("SO", num(row["shutouts"] or 0))],
                 photo=headshot_url(last_season, last_team_abbrev, player_id), badge=initials(row["name"]), kind="profile")


def team_meta(row):
    record = f"{row['wins']}-{row['losses']}-{row['ot_losses']}"
    gf = round(row["goals_for"] / row["games_played"], 2) if row["games_played"] else None
    ga = round(row["goals_against"] / row["games_played"], 2) if row["games_played"] else None
    desc = (f"{row['name']}: {record}, {plural(row['points'], 'point')}, {ordinal(row['league_rank'])} in the league "
            f"({ordinal(row['division_rank'])} in the {row['division']} division)."
            + (f" {gf} goals for and {ga} against per game." if gf is not None else ""))
    return _meta(f"{row['name']} ({record})", desc, headline=row["name"], subline=f"{row['conference']} · {row['division']}",
                 accent=accent_for(row["abbrev"]),
                 stats=[("Record", record), ("Points", num(row["points"])), ("Rank", ordinal(row["league_rank"])),
                        ("Goal diff", f"{row['goal_diff']:+d}" if row["goal_diff"] is not None else "–")],
                 badge=row["abbrev"])


def ordinal(n):
    if n is None:
        return "–"
    suffix = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def game_meta(row):
    home, away = row["home"], row["away"]
    played = row["state"] in ("FINAL", "OFF") and row["home_score"] is not None
    if played:
        suffix = {"OT": "/OT", "SO": "/SO"}.get(row.get("last_period"), "")
        title = (f"{home} {row['home_score']}, {away} {row['away_score']}" if row["home_score"] >= row["away_score"]
                 else f"{away} {row['away_score']}, {home} {row['home_score']}") + f" (Final{suffix})"
        desc = f"{away} at {home}, {row['game_date']:%B} {row['game_date'].day}: shots, expected goals, win probability and shifts."
        stats = [(away, str(row["away_score"])), (home, str(row["home_score"]))]
        sub = f"Final{suffix} · {row['game_date']:%b} {row['game_date'].day}"
    else:
        when = row["start_time"].astimezone(ET).strftime("%b %-d, %-I:%M %p ET") if row.get("start_time") else f"{row['game_date']:%b} {row['game_date'].day}"
        title = f"{away} at {home}, {when}"
        desc = f"{away} at {home} on {when}: win chances, probable goalies and matchup notes."
        stats = []
        sub = when
    return _meta(title, desc, headline=f"{away} at {home}", subline=sub, accent=accent_for(home), stats=stats, badge=home)


def prospect_meta(row, season_row, player_id, season_id):
    team = row["team"]
    bits = []
    if row.get("draft_year"):
        pick = f"round {row['draft_round']}, #{row['draft_overall']} overall" if row.get("draft_round") and row.get("draft_overall") else "drafted"
        bits.append(f"{row['draft_year']} draft, {pick}" + (f" by {row['draft_team']}" if row.get("draft_team") else ""))
    stats = []
    if season_row:
        gp, pts = season_row["games"], season_row["points"]
        bits.append(f"{season_label(season_row['season_id'])}: {season_row['league']} {season_row['team_name']}, {plural(gp, 'game')}"
                    + (f", {plural(pts, 'point')}" if pts is not None else ""))
        stats = [("League", season_row["league"]), ("GP", num(gp))] + ([("P", num(pts))] if pts is not None else [])
    pos = POSITIONS.get(row.get("position"), "")
    desc = f"{row['name']}, {pos.lower() + ' ' if pos else ''}prospect of {team}. " + ". ".join(bits) + ("." if bits else "")
    return _meta(f"{row['name']} (prospect of {team})", desc.strip(), headline=row["name"], subline=f"{pos} prospect · {team}".strip(" ·"),
                 accent=accent_for(team), stats=stats, photo=row.get("headshot"), badge=initials(row["name"]), kind="profile")


def compare_meta(players):
    """players: [{name, team, points, games_played, kind}] in the order of the link."""
    if not players:
        return _meta(*PAGES["/compare"], headline="Compare players", subline="Side by side")
    names = [p["name"] for p in players]
    lasts = [n.split()[-1] for n in names]
    title = " vs ".join(lasts)
    desc = "Compare " + ", ".join(names) + ": " + "; ".join(f"{p['name']} {num(p['points'])} points in {num(p['games_played'])} games" for p in players) + "."
    return _meta(f"{title} (Compare)", desc, headline=title, subline="Player comparison", accent=accent_for(players[0].get("team")),
                 stats=[(l, f"{num(p['points'])} P") for l, p in zip(lasts, players)], badge="VS")


def leaders_meta(path, title, desc, leaders):
    """A leaderboard page with its top few lines in the description. leaders: [(label, value text)]."""
    if leaders:
        desc = desc + " " + ", ".join(f"{a} {b}" for a, b in leaders[:3]) + "."
    return _meta(title, desc, headline=title, subline="Top: " + ", ".join(a for a, _ in leaders[:3]) if leaders else "",
                 stats=leaders[:5])


# --- Queries ------------------------------------------------------------------------------------------

def _first(conn, sql, params):
    return conn.execute(sql, params).fetchone()


def build_meta(conn, kind, key, query):
    """The preview for a parsed route (see parse_route), read from the database. None means 'use the generic preview'."""
    season = config.SEASON_ID
    if kind == "player":
        row = _first(conn, "SELECT name, team, position, games_played, goals, assists, points FROM skater_season "
                           "WHERE season_id = %s AND player_id = %s AND games_played > 0", (season, key))
        if row:
            return skater_meta(row, season, config.GAMES_PER_SEASON, key)
        career = _first(conn, "SELECT * FROM career_skater WHERE player_id = %s AND game_type = 2", (key,))
        if career:
            last = _first(conn, "SELECT season_id, team FROM career_season WHERE player_id = %s ORDER BY season_id DESC LIMIT 1", (key,))
            return career_skater_meta(career, last["season_id"] if last else None, last_team(last["team"]) if last else None, key)
    elif kind == "goalie":
        row = _first(conn, "SELECT name, team, games_played, wins, losses, ot_losses, save_pct, gaa, shutouts FROM goalie_season "
                           "WHERE season_id = %s AND player_id = %s AND games_played > 0", (season, key))
        if row:
            return goalie_meta(row, season, key)
        career = _first(conn, "SELECT * FROM career_goalie WHERE player_id = %s AND game_type = 2", (key,))
        if career:
            last = _first(conn, "SELECT season_id, team FROM goalie_season WHERE player_id = %s ORDER BY season_id DESC LIMIT 1", (key,))
            return career_goalie_meta(career, last["season_id"] if last else None, last_team(last["team"]) if last else None, key)
    elif kind == "team":
        row = _first(conn, "SELECT * FROM team_season WHERE season_id = %s AND abbrev = %s", (season, key))
        if row:
            return team_meta(row)
    elif kind == "game":
        row = _first(conn, "SELECT * FROM game WHERE game_id = %s", (key,))
        if row:
            return game_meta(row)
    elif kind == "prospect":
        row = _first(conn, "SELECT * FROM prospect WHERE player_id = %s", (key,))
        if row:
            sr = _first(conn, "SELECT * FROM prospect_season WHERE player_id = %s AND game_type = 2 ORDER BY season_id DESC, games DESC LIMIT 1", (key,))
            return prospect_meta(row, sr, key, season)
    elif kind == "compare":
        ids = compare_ids(query)
        out = []
        for pid in ids:
            r = _first(conn, "SELECT name, team, points, games_played FROM skater_season WHERE season_id = %s AND player_id = %s", (season, pid))
            if not r:
                r = _first(conn, "SELECT name, NULL AS team, points, games_played FROM career_skater WHERE player_id = %s AND game_type = 2", (pid,))
            if r:
                out.append(r)
        return compare_meta(out) if out else None
    elif kind == "page":
        if key == "/":
            return default_meta()
        title, desc = PAGES[key]
        if key == "/standings":
            rows = conn.execute("SELECT abbrev, points FROM team_season WHERE season_id = %s ORDER BY league_rank LIMIT 3", (season,)).fetchall()
            return leaders_meta(key, title, desc + " League leaders:", [(r["abbrev"], f"{r['points']} pts") for r in rows])
        if key == "/skaters":
            rows = conn.execute("SELECT name, points FROM skater_season WHERE season_id = %s ORDER BY points DESC, games_played LIMIT 3", (season,)).fetchall()
            return leaders_meta(key, title, desc + " Points leaders:", [(r["name"], f"{r['points']} P") for r in rows])
        if key == "/goalies":
            rows = conn.execute("SELECT name, wins FROM goalie_season WHERE season_id = %s ORDER BY wins DESC, games_played LIMIT 3", (season,)).fetchall()
            return leaders_meta(key, title, desc + " Win leaders:", [(r["name"], f"{r['wins']} W") for r in rows])
        return _meta(f"{title}", desc, headline=title, subline=SITE)
    elif kind == "private":
        return _meta(SITE, GENERIC, noindex=True)
    return None


# --- Tags ----------------------------------------------------------------------------------------------

def page_url(url):
    """The address a preview should name: the configured public address plus the page's own path (and its query for /compare)."""
    kind, key, query = parse_route(url)
    path = "/" + urlsplit(url or "/").path.strip("/") if urlsplit(url or "/").path.strip("/") else "/"
    if kind == "default":
        path = "/"   # an address we don't know is not a page worth naming
    keep = ("?ids=" + ",".join(map(str, compare_ids(query)))) if kind == "compare" and compare_ids(query) else ""
    return config.PUBLIC_URL + (path if path != "/" else "") + keep


def page_title(meta):
    """The browser tab title: the page's name, then the site's."""
    return meta["title"] if meta["title"] == SITE else f"{meta['title']} · {SITE}"


def head_html(meta, url):
    """The <head> tags for a preview (title, description, Open Graph and Twitter card). Every value is escaped."""
    e = lambda s: html.escape(str(s), quote=True)  # noqa: E731
    title = page_title(meta)
    link = page_url(url)
    image = f"{config.PUBLIC_URL}/api/share/image.png?url={quote(page_url(url)[len(config.PUBLIC_URL):] or '/', safe='')}"
    tags = [
        f"<title>{e(title)}</title>",
        f'<meta name="description" content="{e(meta["description"])}" />',
        f'<link rel="canonical" href="{e(link)}" />',
        f'<meta property="og:site_name" content="{e(SITE)}" />',
        f'<meta property="og:type" content="{e(meta["kind"])}" />',
        f'<meta property="og:title" content="{e(title)}" />',
        f'<meta property="og:description" content="{e(meta["description"])}" />',
        f'<meta property="og:url" content="{e(link)}" />',
        f'<meta property="og:image" content="{e(image)}" />',
        f'<meta property="og:image:width" content="{W}" />',
        f'<meta property="og:image:height" content="{H}" />',
        f'<meta property="og:image:alt" content="{e(meta["headline"])}" />',
        '<meta name="twitter:card" content="summary_large_image" />',
        f'<meta name="twitter:title" content="{e(title)}" />',
        f'<meta name="twitter:description" content="{e(meta["description"])}" />',
        f'<meta name="twitter:image" content="{e(image)}" />',
    ]
    if meta.get("noindex"):
        tags.append('<meta name="robots" content="noindex" />')
    return "\n    ".join(tags)


# --- The picture ---------------------------------------------------------------------------------------

BG, PANEL, TEXT, MUTED = "#0c1220", "#162033", "#f1f5f9", "#94a3b8"


def _font(size):
    from PIL import ImageFont
    return ImageFont.load_default(size=size)


def _fit(draw, text, sizes, max_w):
    """(font, text) with the largest size from `sizes` at which `text` fits `max_w`, else the smallest size with an ellipsis."""
    for size in sizes:
        f = _font(size)
        if draw.textlength(text, font=f) <= max_w:
            return f, text
    f = _font(sizes[-1])
    while len(text) > 1 and draw.textlength(text + "…", font=f) > max_w:
        text = text[:-1]
    return f, text + "…"


def _wrap(draw, text, font, max_w, max_lines):
    """`text` broken into at most `max_lines` lines no wider than `max_w`; the last line ends in an ellipsis if text was cut."""
    lines, line = [], ""
    for word in text.split():
        trial = f"{line} {word}".strip()
        if draw.textlength(trial, font=font) <= max_w:
            line = trial
            continue
        lines.append(line)
        line = word
        if len(lines) == max_lines:
            break
    else:
        lines.append(line)
    if len(lines) > max_lines or (len(lines) == max_lines and " ".join(lines) != text):
        lines = lines[:max_lines]
        while lines[-1] and draw.textlength(lines[-1] + "…", font=font) > max_w:
            lines[-1] = lines[-1].rsplit(" ", 1)[0] if " " in lines[-1] else lines[-1][:-1]
        lines[-1] += "…"
    return [ln for ln in lines if ln]


def render_card(meta, photo_bytes=None):
    """The preview picture as PNG bytes: brand, name, one line of detail, up to five headline numbers and a headshot or badge."""
    from PIL import Image, ImageDraw
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    accent = meta["accent"]
    d.rectangle([0, 0, 20, H], fill=accent)
    # brand mark: the site's red and blue underline
    d.text((72, 48), "NHL STATS", font=_font(28), fill=MUTED)
    d.rectangle([72, 90, 120, 94], fill="#ef4444")
    d.rectangle([122, 90, 170, 94], fill="#38bdf8")

    pic = 300
    px, py = W - 72 - pic, 96
    text_w = px - 72 - 40
    f, name = _fit(d, meta["headline"], (84, 72, 62, 54, 46, 40, 34), text_w)
    d.text((72, 140), name, font=f, fill=TEXT)
    if meta["subline"]:
        f2, sub = _fit(d, meta["subline"], (34, 30, 26), text_w)
        d.text((72, 140 + f.size + 22), sub, font=f2, fill=MUTED)

    # headshot in a ring, or a badge with initials / team code
    d.ellipse([px - 8, py - 8, px + pic + 8, py + pic + 8], fill=accent)
    drawn = False
    if photo_bytes:
        try:
            p = Image.open(io.BytesIO(photo_bytes)).convert("RGBA").resize((pic, pic))
            tile = Image.new("RGBA", (pic, pic), PANEL)
            tile.alpha_composite(p)
            mask = Image.new("L", (pic, pic), 0)
            ImageDraw.Draw(mask).ellipse([0, 0, pic - 1, pic - 1], fill=255)
            img.paste(tile.convert("RGB"), (px, py), mask)
            drawn = True
        except Exception:  # a broken picture must not break the card
            log.warning("Couldn't use the headshot for a preview", exc_info=True)
    if not drawn:
        d.ellipse([px, py, px + pic, py + pic], fill=PANEL)
        bf, badge = _fit(d, meta["badge"], (110, 90, 72), pic - 40)
        w = d.textlength(badge, font=bf)
        d.text((px + (pic - w) / 2, py + pic / 2 - bf.size * 0.55), badge, font=bf, fill=accent)

    stats = meta["stats"]
    if stats:
        gap, left, right = 22, 72, W - 72
        tile_w = (right - left - gap * (len(stats) - 1)) / len(stats)
        top, bottom = 420, 560
        for i, (label, value) in enumerate(stats):
            x0 = left + i * (tile_w + gap)
            d.rounded_rectangle([x0, top, x0 + tile_w, bottom], radius=16, fill=PANEL)
            d.rectangle([x0 + 18, top + 18, x0 + 18 + 28, top + 22], fill=accent)
            lf, lab = _fit(d, label, (24, 20), tile_w - 36)
            d.text((x0 + 18, top + 34), lab, font=lf, fill=MUTED)
            vf, val = _fit(d, value, (60, 50, 42, 34, 28), tile_w - 36)
            d.text((x0 + 18, top + 70), val, font=vf, fill=TEXT)
    else:
        df = _font(30)
        for i, line in enumerate(_wrap(d, meta["description"], df, W - 144, 3)):
            d.text((72, 430 + i * 44), line, font=df, fill=MUTED)
    host = urlsplit(config.PUBLIC_URL).netloc
    hf = _font(24)
    d.text((W - 72 - d.textlength(host, font=hf), H - 52), host, font=hf, fill=MUTED)

    out = io.BytesIO()
    img.save(out, "PNG", optimize=True)
    return out.getvalue()


# --- Cache, photos and the two endpoints -------------------------------------------------------------------

_CACHE = {}
TTL = 600
MAX_ENTRIES = 400


def _cached(key, make, ttl=TTL):
    now = time.time()
    hit = _CACHE.get(key)
    if hit and now - hit[0] < ttl:
        return hit[1]
    value = make()
    if len(_CACHE) >= MAX_ENTRIES:
        for k in sorted(_CACHE, key=lambda k: _CACHE[k][0])[: MAX_ENTRIES // 4]:
            _CACHE.pop(k, None)
    _CACHE[key] = (now, value)
    return value


def fetch_photo(url):
    """The headshot's bytes, or None (kept for an hour, including misses, so a missing picture isn't re-asked every view)."""
    if not url or not url.startswith("https://assets.nhle.com/"):
        return None

    def get():
        try:
            r = requests.get(url, timeout=3)
            return r.content if r.ok and r.headers.get("content-type", "").startswith("image") else None
        except requests.RequestException:
            return None
    return _cached(("photo", url), get, ttl=3600)


def meta_for(url):
    """The preview for a page address; the generic one when the page has none or anything goes wrong."""
    kind, key, query = parse_route(url)

    def make():
        try:
            with psycopg.connect(config.DATABASE_URL, row_factory=dict_row) as conn:
                return build_meta(conn, kind, key, query) or default_meta()
        except Exception:
            log.warning("Couldn't build a link preview for %s", url, exc_info=True)
            return default_meta()
    return _cached(("meta",) + route_key(kind, key, query), make)


@router.get("/head")
def head(url: str = "/"):
    """The <head> tags for a page address, as an HTML fragment."""
    return Response(head_html(meta_for(url), url), media_type="text/html", headers={"Cache-Control": "public, max-age=300"})


@router.get("/title")
def title(url: str = "/"):
    """Just the tab title for a page address, so the app can keep it right as you move between pages."""
    return Response(page_title(meta_for(url)), media_type="text/plain; charset=utf-8", headers={"Cache-Control": "public, max-age=300"})


@router.get("/image.png")
def image(url: str = "/"):
    """The preview picture for a page address."""
    meta = meta_for(url)
    png = _cached(("png",) + route_key(*parse_route(url)), lambda: render_card(meta, fetch_photo(meta.get("photo"))))
    return Response(png, media_type="image/png", headers={"Cache-Control": "public, max-age=3600"})
