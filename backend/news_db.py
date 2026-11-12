"""Database side of news.py: keeps the headlines fresh in Postgres and answers the API's queries.
Functions take an open psycopg connection that returns dict rows."""
import logging
import threading
import time
from datetime import datetime, timedelta, timezone

import psycopg
from psycopg.rows import dict_row

import config
import news

log = logging.getLogger(__name__)

TOP_WINDOW_DAYS = 4        # the Top tab only looks this far back...
TOP_HALF_LIFE_HOURS = 18   # ...and a story's score halves every this many hours, so the newest big stories lead
REFRESH_SECONDS = 20 * 60  # how often the feeds are read, when someone is looking
RETRY_SECONDS = 5 * 60     # after a read that found nothing (every feed down)
KEEP_DAYS = 30

_lock = threading.Lock()
_last_try = 0.0  # time.monotonic() of the last attempt, so a burst of page views starts one refresh, not many


def _tagger(conn):
    teams = conn.execute("SELECT abbrev, name, common_name FROM team_season WHERE season_id = %s", (config.SEASON_ID,)).fetchall()
    players = conn.execute(
        """SELECT player_id, name, team FROM skater_season WHERE season_id = %(s)s
           UNION SELECT player_id, name, team FROM goalie_season WHERE season_id = %(s)s""", {"s": config.SEASON_ID}).fetchall()
    return news.Tagger(teams, players)


STAR_SKATERS = 60
STAR_GOALIES = 20


def _stars(conn):
    """Ids of this season's best-known players: the top scorers and the goalies with the most wins."""
    s = {"s": config.SEASON_ID}
    ids = {r["player_id"] for r in conn.execute(
        "SELECT player_id FROM skater_season WHERE season_id = %(s)s ORDER BY points DESC LIMIT %(n)s", {**s, "n": STAR_SKATERS})}
    ids |= {r["player_id"] for r in conn.execute(
        "SELECT player_id FROM goalie_season WHERE season_id = %(s)s ORDER BY wins DESC NULLS LAST LIMIT %(n)s", {**s, "n": STAR_GOALIES})}
    return ids


def refresh(conn):
    """Read every feed, tag the stories and store them (newer data replaces older). Returns how many stories were stored."""
    oldest = news.now_utc() - timedelta(days=KEEP_DAYS)
    items = [i for i in news.fetch_all() if i["published"] >= oldest]
    if not items:
        return 0
    tagger = _tagger(conn)
    tags = [tagger.tag(item) for item in items]
    scores = news.score_all(items, tags, _stars(conn))
    rows = [(i["url"], i["title"], i["summary"], i["source"], i["published"], score, teams, players)
            for i, (teams, players, _), score in zip(items, tags, scores)]
    with conn.cursor() as cur:
        cur.executemany(
            """INSERT INTO news_item (url, title, summary, source, published_at, score, teams, players)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
               ON CONFLICT (url) DO UPDATE SET title = EXCLUDED.title, summary = EXCLUDED.summary, source = EXCLUDED.source,
                   score = EXCLUDED.score, teams = EXCLUDED.teams, players = EXCLUDED.players, fetched_at = now()""", rows)
    conn.execute("DELETE FROM news_item WHERE published_at < %s", (oldest,))
    return len(rows)


def _refresh_in_own_connection(wait):
    """Runs a refresh on its own connection (it may be on a background thread). With wait=False, gives up if one is already running."""
    global _last_try
    if not _lock.acquire(blocking=wait):
        return
    try:
        with psycopg.connect(config.DATABASE_URL, row_factory=dict_row) as conn:
            stored = refresh(conn)
        if not stored:  # every feed failed: try again sooner than usual
            _last_try = time.monotonic() - REFRESH_SECONDS + RETRY_SECONDS
    except Exception:  # a news problem must never take the API down
        log.exception("news refresh failed")
    finally:
        _lock.release()


def ensure_fresh(conn):
    """Called before reading. If the stored stories are older than REFRESH_SECONDS, they are refreshed: in the background when there is
    something to show meanwhile, and before answering when the table is still empty (the very first visit)."""
    global _last_try
    if time.monotonic() - _last_try < REFRESH_SECONDS:
        return
    newest = conn.execute("SELECT max(fetched_at) AS t FROM news_item").fetchone()["t"]
    _last_try = time.monotonic()
    if newest and datetime.now(timezone.utc) - newest < timedelta(seconds=REFRESH_SECONDS):
        return
    if newest:
        threading.Thread(target=_refresh_in_own_connection, args=(False,), daemon=True).start()
    else:
        _refresh_in_own_connection(True)


def stories(conn, *, team=None, player=None, top=False, limit=30):
    """Stored stories, newest first, optionally only those tagged with a team or a player, or only the big ones.
    Each is {url, title, summary, source, published_at, top (whether it counts as a big story), teams: [abbrev], players: [{id, name, kind}]}."""
    # Top stories: big enough, recent enough, ranked by score decayed for age. Everything else: newest first.
    order = ("score * power(0.5, extract(epoch FROM now() - published_at) / 3600.0 / %(half)s) DESC, published_at DESC"
             if top else "published_at DESC")
    rows = conn.execute(
        f"""SELECT url, title, summary, source, published_at, score, teams, players FROM news_item
           WHERE (%(team)s::text IS NULL OR %(team)s = ANY(teams))
             AND (%(player)s::int IS NULL OR %(player)s = ANY(players))
             AND (NOT %(top)s OR (score >= %(min)s AND published_at > now() - make_interval(days => %(days)s)))
           ORDER BY {order} LIMIT %(limit)s""",
        {"team": team, "player": player, "top": top, "limit": limit, "min": news.MIN_TOP, "days": TOP_WINDOW_DAYS,
         "half": TOP_HALF_LIFE_HOURS}).fetchall()
    ids = sorted({p for r in rows for p in r["players"]})
    who = {}
    if ids:
        who = {r["player_id"]: r for r in conn.execute(
            """SELECT player_id, name, 'skater' AS kind FROM skater_season WHERE season_id = %(s)s AND player_id = ANY(%(ids)s)
               UNION SELECT player_id, name, 'goalie' AS kind FROM goalie_season WHERE season_id = %(s)s AND player_id = ANY(%(ids)s)""",
            {"s": config.SEASON_ID, "ids": ids})}
    return [{"url": r["url"], "title": r["title"], "summary": r["summary"], "source": r["source"],
             "published_at": r["published_at"].isoformat(), "top": r["score"] >= news.MIN_TOP, "teams": r["teams"],
             "players": [{"id": p, "name": who[p]["name"], "kind": who[p]["kind"]} for p in r["players"] if p in who]}
            for r in rows]
