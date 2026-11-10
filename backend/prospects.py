"""Prospects: players on NHL teams' prospect lists who haven't made the NHL yet, with their junior, college, European
and minor-league stats.

Everything comes from two NHL web endpoints: /prospects/{team} (the list, with bio) and /player/{id}/landing (draft
details and a season-by-season line for every league they've played in). Draft-class rankings (/draft/rankings) carry
no player ids, so the upcoming class is shown as a ranking only (see api.py), without stats.

A prospect's stat line this season is their regular-season row in the league where they played the most games, since
a prospect on loan or called up can have several. Leagues aren't comparable (a point a game in the OHL is not a point a
game in the AHL), so nothing here converts between them.
"""

import re
import unicodedata
from difflib import SequenceMatcher

POSITIONS = {"L", "R", "C", "D", "G"}


def _name(d):
    """The English text of a {'default': ...} name field, or a plain string."""
    if isinstance(d, dict):
        return d.get("default")
    return d


SUFFIXES = {"jr", "sr", "ii", "iii", "iv"}


def match_key(name):
    """A name reduced to what two sources agree on: lower case, accents folded, punctuation and generation suffixes dropped
    ('Zachary L'Heureux Jr.' and "Zachary L'Heureux" match)."""
    folded = unicodedata.normalize("NFKD", name or "").encode("ascii", "ignore").decode().lower()
    words = [w for w in re.sub(r"[^a-z ]", "", folded.replace("-", " ")).split() if w not in SUFFIXES]
    return " ".join(words)


SIMILAR_NAME = 0.85   # how alike two full names must be (0 to 1) to be the same person, on top of the same birth date


def same_person(a, b):
    """Whether two spellings of a name can be one person, given that their birth dates already agree: the same last name, or names
    so alike that only a transliteration differs ('Oleg Kulebiakin' and 'Oleg Kulebyakin')."""
    ka, kb = match_key(a), match_key(b)
    return bool(ka and kb) and (last_word(a) == last_word(b) or SequenceMatcher(None, ka, kb).ratio() >= SIMILAR_NAME)


def link_rankings(rows, prospects, year):
    """Attach the stored prospect to each Central Scouting ranking row of the `year` draft, matched by name among the prospects drafted
    that year. The rankings have no player ids, so a row is linked only when exactly one prospect of that class has its name and no
    other ranked row shares it; everyone else is left alone. Rows that share no exact name with the class but have a
    birth date (`birth_date`, ISO) are matched to the one prospect of the class with that birth date and the same last name (or a
    near-identical name), so a different spelling doesn't break the link. Adds `prospect_id` and `draft` ({year, round, pick, overall, team})
    to the linked rows and returns how many were linked."""
    classmates = {}
    for p in prospects:
        if p.get("draft_year") == year:
            classmates.setdefault(match_key(p["name"]), []).append(p)
    # a second way in for rows whose spelling differs from the draft's ("Ilya" and "Ilia" Morozov, "Teddy" and "Theodore" Lechner):
    # the same birth date among the class, with the same last name or a name so alike that only a transliteration differs
    by_birth = {}
    for p in prospects:
        if p.get("draft_year") == year and p.get("birth_date"):
            by_birth.setdefault(str(p["birth_date"]), []).append(p)
    seen = {}
    for r in rows:
        seen[match_key(r["name"])] = seen.get(match_key(r["name"]), 0) + 1
    linked, used = 0, set()

    def attach(r, p):
        nonlocal linked
        r["prospect_id"] = p["player_id"]
        r["draft"] = {"year": p["draft_year"], "round": p["draft_round"], "pick": p["draft_pick"], "overall": p["draft_overall"],
                      "team": p["draft_team"]}
        used.add(p["player_id"])
        linked += 1

    for r in rows:
        key = match_key(r["name"])
        found = classmates.get(key, [])
        if len(found) == 1 and seen[key] == 1:
            attach(r, found[0])
    for r in rows:
        if r.get("prospect_id") or not r.get("birth_date"):
            continue
        found = [p for p in by_birth.get(str(r["birth_date"]), []) if p["player_id"] not in used and same_person(r["name"], p["name"])]
        if len(found) == 1:
            attach(r, found[0])
    return linked


# --- Finding the drafted players that the teams' lists leave out ---------------------------------------------------------
# /prospects/{team} lists only some of a draft class (about a quarter of the 2026 class), while the draft's own pick list names every
# player with his slot and team but no player id. Each unmatched pick is searched by name and the candidate is accepted only when his
# landing record says he was drafted in that year at that overall pick, which no other player can be.

def parse_picks(data):
    """The picks of a /draft/picks/{year}/all response: [{year, overall, round, pick, team, name, position, country}] (the pick
    list has no player ids)."""
    year = data.get("draftYear")
    out = []
    for p in data.get("picks") or []:
        name = f"{_name(p.get('firstName')) or ''} {_name(p.get('lastName')) or ''}".strip()
        if not (name and p.get("overallPick")) or set(name.lower().split()) == {"forfeited"}:   # a forfeited pick has no player
            continue
        out.append({"year": year, "overall": p["overallPick"], "round": p.get("round"), "pick": p.get("pickInRound"),
                    "team": p.get("teamAbbrev"), "name": name, "position": p.get("positionCode"), "country": p.get("countryCode")})
    return out


def last_word(name):
    """The last word of a name as match_key sees it ('Jeffrey (JP) Hurlbert' -> 'hurlbert'), or ''."""
    words = match_key(name).split()
    return words[-1] if words else ""


def search_candidates(name, results, loose=False):
    """Player ids, in the order given, from a player-search response whose name is `name` once accents, punctuation and suffixes are
    set aside. A search for a name also returns near misses ('Gavin McKenna' brings back 'Gavin Brindley'), which are dropped.
    With `loose`, a candidate need only share the last name, for a pick listed as 'Thomas Bleyl' whom the NHL's records call
    'Tommy Bleyl'; the caller must then confirm the draft details (confirms_pick), which no other player can pass."""
    key = last_word(name) if loose else match_key(name)
    ids = []
    for r in results or []:
        try:
            pid = int(r.get("playerId"))
        except (TypeError, ValueError):
            continue
        same = last_word(r.get("name")) == key if loose else match_key(r.get("name")) == key
        if same and pid not in ids:
            ids.append(pid)
    return ids


def confirms_pick(landing, year, overall):
    """True when a player's landing record says he was drafted in `year` at pick number `overall`."""
    d = (landing or {}).get("draftDetails") or {}
    return bool(year and overall and d.get("year") == year and d.get("overallPick") == overall)


def parse_bio(landing):
    """The bio fields a prospect row stores, from a /player/{id}/landing response (the same keys parse_list gives)."""
    return {
        "player_id": landing["playerId"], "name": f"{_name(landing.get('firstName'))} {_name(landing.get('lastName'))}".strip(),
        "position": landing.get("position"), "shoots": landing.get("shootsCatches"), "birth_date": landing.get("birthDate"),
        "birth_country": landing.get("birthCountry"), "height_in": landing.get("heightInInches"),
        "weight_lb": landing.get("weightInPounds"), "headshot": landing.get("headshot"),
    }


def reached_nhl(seasons):
    """True when any of a player's season rows (parse_landing) is an NHL season with a game played."""
    return any(s.get("league") == "NHL" and (s.get("games") or 0) > 0 for s in seasons)


def class_team(landing, pick, nhl_teams):
    """The NHL team a drafted player belongs to: the one his landing record names if it is an NHL club (his rights may have been
    traded since the draft), else the team that picked him."""
    current = (landing or {}).get("currentTeamAbbrev")
    return current if current in nhl_teams else pick.get("team")


def parse_list(data):
    """Prospect bios from a /prospects/{team} response, one dict per player."""
    out = []
    for key in ("forwards", "defensemen", "goalies"):
        for p in data.get(key) or []:
            out.append({
                "player_id": p["id"], "name": f"{_name(p.get('firstName'))} {_name(p.get('lastName'))}".strip(),
                "position": p.get("positionCode"), "shoots": p.get("shootsCatches"), "birth_date": p.get("birthDate"),
                "birth_country": p.get("birthCountry"), "height_in": p.get("heightInInches"),
                "weight_lb": p.get("weightInPounds"), "headshot": p.get("headshot"),
            })
    return out


def parse_landing(data):
    """(draft, seasons) from a /player/{id}/landing response. draft is {year, round, pick, overall, team} or None;
    seasons are the regular-season and playoff rows (game types 2 and 3) of every league."""
    d = data.get("draftDetails")
    draft = {"year": d.get("year"), "round": d.get("round"), "pick": d.get("pickInRound"),
             "overall": d.get("overallPick"), "team": d.get("teamAbbrev")} if d else None
    seasons = []
    for s in data.get("seasonTotals") or []:
        if s.get("gameTypeId") not in (2, 3):
            continue
        seasons.append({
            "season_id": s["season"], "game_type": s["gameTypeId"], "league": s.get("leagueAbbrev"),
            "team_name": _name(s.get("teamName")) or "", "games": s.get("gamesPlayed") or 0,
            "goals": s.get("goals"), "assists": s.get("assists"), "points": s.get("points"),
            "pim": s.get("pim"), "plus_minus": s.get("plusMinus"),
            "wins": s.get("wins"), "save_pct": s.get("savePctg"), "gaa": s.get("goalsAgainstAvg"),
        })
    return draft, seasons


def current_line(seasons, season_id):
    """The prospect's regular-season row for `season_id` in the league where they played the most, or None."""
    rows = [s for s in seasons if s["season_id"] == season_id and s["game_type"] == 2]
    return max(rows, key=lambda s: s["games"]) if rows else None


def age_on(birth_date, on):
    """Whole years of age on a date (both datetime.date), or None without a birth date."""
    if not birth_date:
        return None
    return on.year - birth_date.year - ((on.month, on.day) < (birth_date.month, birth_date.day))


def points_per_game(row):
    """Points per game for a skater row, None for a goalie or an unplayed row."""
    if not row or not row.get("games") or row.get("points") is None:
        return None
    return row["points"] / row["games"]


# --- Watched prospects in the morning email ---------------------------------------------------------------------
RECENT_DAYS = 3        # a change in a prospect's games total this recent is "lately"
COMPARE_MIN_GAMES = 10  # games needed in both seasons (same league) to compare a points-per-game rate with last season's
COMPARE_GAP = 0.15     # points per game apart before the comparison is worth saying


def recent_change(line, now):
    """What a prospect's season line gained the last time the nightly refresh saw it move: {games, points, days_ago}, or None.

    The stored data is season totals, so this is a difference between two refreshes, not a fixed window: usually the last
    game or few. line: a prospect_season row with prev_games, prev_points and changed_at (a tz-aware datetime, or None)."""
    if not line or line.get("changed_at") is None or line.get("prev_games") is None or line.get("games") is None:
        return None
    games = line["games"] - line["prev_games"]
    days = (now - line["changed_at"]).days
    if games <= 0 or days > RECENT_DAYS:
        return None
    points = None
    if line.get("points") is not None and line.get("prev_points") is not None:
        points = line["points"] - line["prev_points"]
    return {"games": games, "points": points, "days_ago": days}


def prior_rate(seasons, season_id, league):
    """Points per game in the same league the season before `season_id`, when there were enough games to mean something."""
    prev = [s for s in seasons if s["season_id"] == season_id - 10001 and s["game_type"] == 2 and s["league"] == league]
    row = max(prev, key=lambda s: s["games"], default=None)
    return points_per_game(row) if row and row["games"] >= COMPARE_MIN_GAMES else None


def alert(p, line, seasons, now, season_id):
    """One watched prospect, ready for the email. p: the prospect row; line: this season's current line (current_line) or
    None; seasons: all their prospect_season rows. Skater lines carry a rate comparison with last season in the same league."""
    goalie = p["position"] == "G"
    out = {"name": p["name"], "team": p["team"], "position": p["position"], "goalie": goalie, "league": None, "games": 0,
           "goals": None, "assists": None, "points": None, "wins": None, "save_pct": None, "gaa": None,
           "ppg": None, "prior_ppg": None, "change": None}
    if line:
        out.update(league=line["league"], games=line["games"], goals=line["goals"], assists=line["assists"], points=line["points"],
                   wins=line["wins"], save_pct=line["save_pct"], gaa=line["gaa"], ppg=points_per_game(line),
                   change=recent_change(line, now))
        if not goalie:
            out["prior_ppg"] = prior_rate(seasons, season_id, line["league"])
    return out


def alert_line(a):
    """One sentence for a prospect in the email."""
    who = f"{a['name']} ({a['team']} prospect, {a['position']})"
    if a["games"] == 0:
        return f"{who} has no games on record this season yet."
    league = f" in the {a['league']}" if a["league"] else ""
    if a["goalie"]:
        sv = f", {a['save_pct']:.3f} save percentage" if a["save_pct"] is not None else ""
        wins = f", {a['wins']} wins" if a["wins"] is not None else ""
        text = f"{who}: {a['games']} games{league}{wins}{sv}."
    else:
        text = f"{who}: {a['goals']}-{a['assists']}-{a['points']} in {a['games']} games{league} ({a['ppg']:.2f} points a game)."
    c = a.get("change")
    if c:
        when = "since the last update" if c["days_ago"] == 0 else f"over the last {c['days_ago'] + 1} days"
        gained = f", {c['points']} point{'s' if c['points'] != 1 else ''}" if c["points"] is not None and not a["goalie"] else ""
        text += f" Lately: {c['games']} game{'s' if c['games'] != 1 else ''}{gained} {when}."
    if a.get("prior_ppg") is not None and a["ppg"] is not None and abs(a["ppg"] - a["prior_ppg"]) >= COMPARE_GAP:
        text += f" {'Up' if a['ppg'] > a['prior_ppg'] else 'Down'} from {a['prior_ppg']:.2f} a game last season."
    return text


def called_up_line(name, team, nhl_games, points, goalie=False):
    """One sentence for a watched prospect who now has NHL games this season."""
    stat = f"{nhl_games} NHL game{'s' if nhl_games != 1 else ''}" + ("" if goalie or points is None else f", {points} point{'s' if points != 1 else ''}")
    return f"{name} has reached the NHL with {team}: {stat} so far. He is now followed like any other player."
