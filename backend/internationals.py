"""International medals for players: which national-team tournaments a player appeared in and whether his team won a medal.

A player's tournaments come from the NHL's season-by-season rows (league, season, country, games, points). A medal is worked out by
matching his country and the tournament's year against data/international_results.json (built by analysis/fetch_international_results.py),
so it needs no per-player medal data at all. Three things in the NHL rows need care, and are handled here:
- The same tournament appears under several league labels (the Olympics as "Olympics" and "OG"; the World Championship as "WC" and "WC-A"
  for the years both were used), so appearances are de-duplicated by tournament, year and country.
- The Canada Cup / World Cup of Hockey is held in September, and its season label is inconsistent ("CC" 1975-76 and "Can-Cup" 1976-77
  both mean the 1976 Canada Cup), so those are matched on whichever of the season's two years is an actual edition.
- Country names vary ("USA", "United States", "Czech Republic", "Soviet Union", "Canada U20"), and a country's successor teams share its
  medals for this purpose (the Soviet Union, the Unified Team, the CIS and Russia; Czechoslovakia and Czechia; West Germany and Germany)."""
import json
import re
from pathlib import Path

RESULTS_FILE = Path(__file__).parent / "data" / "international_results.json"

# NHL league labels -> tournament. Lower divisions (WC-B), the European Championships and the under-18 Worlds are not included.
LEAGUES = {
    "olympics": {"Olympics", "OG"},
    "worlds": {"WC", "WC-A"},
    "worldcup": {"WCup", "W-Cup", "Can-Cup", "CC"},
    "fournations": {"4 Nations"},
    "juniors": {"WJC-A", "WJC-20"},
}
LEAGUE_TO_TOURNAMENT = {league: t for t, leagues in LEAGUES.items() for league in leagues}
# Tournaments held in September, labelled with either of the season's two years.
EITHER_YEAR = {"worldcup"}

# A country name (lower case, without a "U20" / "Olympics" suffix) -> the code the results file uses.
NAMES = {
    "canada": "CAN", "usa": "USA", "united states": "USA", "sweden": "SWE", "finland": "FIN", "czechia": "CZE", "czech republic": "CZE",
    "czechoslovakia": "TCH", "soviet union": "URS", "ussr": "URS", "russia": "RUS", "cis": "CIS", "unified team": "EUN", "roc": "RUS",
    "oar": "RUS", "germany": "GER", "west germany": "FRG", "east germany": "GDR", "switzerland": "SUI", "slovakia": "SVK",
    "slovak republic": "SVK", "latvia": "LAT", "norway": "NOR", "belarus": "BLR", "denmark": "DEN", "austria": "AUT", "france": "FRA",
    "team europe": "EUR", "team north america": "NAM", "great britain": "GBR", "italy": "ITA", "poland": "POL", "kazakhstan": "KAZ",
    "slovenia": "SLO", "hungary": "HUN", "japan": "JPN", "south korea": "KOR", "china": "CHN",
}
# Codes whose medals count for each other: one country's team under its predecessor's and successor's names.
LINEAGE = {"URS": "RUS", "EUN": "RUS", "CIS": "RUS", "RUS": "RUS", "TCH": "CZE", "CZE": "CZE", "FRG": "GER", "GER": "GER"}

MEDALS = ("gold", "silver", "bronze")
_cache = {}


def load_results():
    """The results file, read once."""
    if "results" not in _cache:
        _cache["results"] = json.loads(RESULTS_FILE.read_text())
    return _cache["results"]


def country_code(team_name):
    """'USA U20' -> 'USA', 'Czech Republic' -> 'CZE'; None for a name that is not a country the results know."""
    name = re.sub(r"\s+(u-?\d\d|olympics)$", "", (team_name or "").strip(), flags=re.I).lower()
    return NAMES.get(name)


def lineage(code):
    return LINEAGE.get(code, code)


def event_year(tournament, season_id, editions):
    """The year of the edition a season row belongs to, or None if there was no such edition. `editions` are the years with results."""
    start, end = season_id // 10000, season_id % 10000
    if tournament in EITHER_YEAR:
        return next((y for y in (end, start) if y in editions), None)
    return end if end in editions else None


def medal_for(tournament_results, year, code):
    """'gold', 'silver' or 'bronze' if a team of this country won it that year, else None."""
    result = tournament_results.get(str(year))
    if not result or not code:
        return None
    return next((m for m in MEDALS if lineage(result.get(m)) == lineage(code)), None)


def rows_from_landing(payload):
    """The tournament rows in an NHL landing payload's seasonTotals, as {league, season_id, team_name, games, goals, assists, points}."""
    out = []
    for s in (payload or {}).get("seasonTotals", []):
        if s.get("leagueAbbrev") in LEAGUE_TO_TOURNAMENT:
            out.append({"league": s["leagueAbbrev"], "season_id": s["season"], "team_name": (s.get("teamName") or {}).get("default", ""),
                        "games": s.get("gamesPlayed"), "goals": s.get("goals"), "assists": s.get("assists"), "points": s.get("points")})
    return out


def appearances(rows, results=None):
    """A player's tournaments, newest first: [{tournament, label, tier, year, country, code, medal, games, goals, assists, points}].
    rows: {league, season_id, team_name, games, goals, assists, points}. `medal` is gold/silver/bronze, or None for taking part."""
    results = results or load_results()
    tournaments = results["tournaments"]
    names = results["countries"]
    found = {}
    for r in rows:
        tournament = LEAGUE_TO_TOURNAMENT.get(r["league"])
        if not tournament:
            continue
        t = tournaments[tournament]
        year = event_year(tournament, r["season_id"], {int(y) for y in t["results"]})
        if year is None:
            continue  # a tournament edition we have no result for (a lower division, or one not played that year)
        code = country_code(r["team_name"])
        key = (tournament, year, lineage(code) if code else r["team_name"])
        entry = {"tournament": tournament, "label": t["label"], "tier": t["tier"], "year": year, "code": code,
                 "country": names.get(code) or (r["team_name"] or "").strip(), "medal": medal_for(t["results"], year, code),
                 "games": r["games"], "goals": r["goals"], "assists": r["assists"], "points": r["points"]}
        if key not in found or (entry["games"] or 0) > (found[key]["games"] or 0):  # the same tournament under two labels: keep the fuller row
            found[key] = entry
    return sorted(found.values(), key=lambda a: (-a["year"], a["tournament"]))


def medal_counts(apps):
    """{gold, silver, bronze} over a list of appearances."""
    return {m: sum(a["medal"] == m for a in apps) for m in MEDALS}


def by_tournament(apps):
    """{tournament: {gold, silver, bronze, played}} for the tournaments a player appeared in."""
    out = {}
    for a in apps:
        t = out.setdefault(a["tournament"], {"label": a["label"], "tier": a["tier"], "gold": 0, "silver": 0, "bronze": 0, "played": 0})
        t["played"] += 1
        if a["medal"]:
            t[a["medal"]] += 1
    return out


# --- NHL awards and the Triple Gold Club ------------------------------------------------------------------
CUP = "Stanley Cup"


def awards_from_landing(payload):
    """Every NHL award in a landing payload as (trophy, season_id) pairs: one per season a player won it."""
    out = []
    for a in (payload or {}).get("awards", []):
        name = (a.get("trophy") or {}).get("default")
        for s in a.get("seasons", []):
            if name and s.get("seasonId"):
                out.append((name, s["seasonId"]))
    return out


def stanley_cups(awards):
    """The seasons a player won the Stanley Cup, from (trophy, season_id) pairs, oldest first."""
    return sorted({season for trophy, season in awards if trophy == CUP})


def name_key(name):
    """A name reduced for matching: accents dropped, lower case, letters only ('Jaromír Jágr' and 'Jaromir Jagr' agree)."""
    import unicodedata
    return re.sub(r"[^a-z]+", " ", unicodedata.normalize("NFKD", name or "").encode("ascii", "ignore").decode().lower()).strip()


# A roll name that differs from the name the NHL uses for the same player (name key on the roll -> name key in our data).
ROLL_ALIASES = {"fredrik modin": "freddy modin"}


def official_club(results=None):
    """The IIHF's Triple Gold Club roll as {name_key: {cup, olympics, worlds, completed}}, from the results file. Keys are the names as our
    NHL data spells them (see ROLL_ALIASES)."""
    results = results or load_results()
    out = {}
    for m in results.get("triple_gold_club", []):
        key = name_key(m["name"])
        out[ROLL_ALIASES.get(key, key)] = {k: m[k] for k in ("cup", "olympics", "worlds", "completed")}
    return out


def triple_gold(apps, cup_seasons, official=None):
    """The Triple Gold Club: a player who has won the Stanley Cup, an Olympic gold medal and a World Championship gold medal.
    Returns None for a non-member, else {cup, olympics, worlds, completed, source}: the year of each first win (a Cup season counts for the
    year it ended in), the year the third one was won, and where that came from: "computed" from the player's own NHL rows (see
    appearances) or "official" from the IIHF roll (`official`, the player's entry in official_club). The roll covers members whose medals the
    NHL's tournament history leaves out; when both exist, the computed one wins. `cup_seasons` are from stanley_cups."""
    olympics = [a["year"] for a in apps if a["tournament"] == "olympics" and a["medal"] == "gold"]
    worlds = [a["year"] for a in apps if a["tournament"] == "worlds" and a["medal"] == "gold"]
    if cup_seasons and olympics and worlds:
        first = {"cup": min(s % 10000 for s in cup_seasons), "olympics": min(olympics), "worlds": min(worlds)}
        return {**first, "completed": max(first.values()), "source": "computed"}
    if official:
        return {**official, "source": "official"}
    return None


# --- Individual tournament awards ------------------------------------------------------------------------------
# data/international_awards.json (built by analysis/fetch_international_awards.py): the most valuable player and the IIHF directorate awards
# (best goaltender, defenseman and forward) of the tournaments, by name. Names are matched to players here.
AWARDS_FILE = Path(__file__).parent / "data" / "international_awards.json"
AWARD_ORDER = ("mvp", "goaltender", "defense", "forward")
AWARD_LABELS = {"mvp": "Most valuable player", "goaltender": "Best goaltender", "defense": "Best defenseman", "forward": "Best forward"}
# The NHL spells a birth country with ISO codes; the tournament results use the IOC's.
ISO_TO_IOC = {"CHE": "SUI", "DEU": "GER", "DNK": "DEN", "LVA": "LAT", "SVN": "SLO", "NLD": "NED", "LTU": "LTU", "UKR": "UKR"}


def load_awards():
    """The awards file, read once."""
    if "awards" not in _cache:
        _cache["awards"] = json.loads(AWARDS_FILE.read_text())
    return _cache["awards"]


def country_name(code, results=None):
    """A country's display name from its code: the results file's name, else the longest name we know for it ('Belarus' for BLR)."""
    results = results or load_results()
    if code in results["countries"]:
        return results["countries"][code]
    known = [n for n, c in NAMES.items() if c == code]
    return max(known, key=len).title() if known else code


def honors(name, birth_country, apps, awards=None):
    """The tournament awards a player has won, newest first: [{tournament, label, year, award, award_label, code, country}].
    An award is his when the name matches and either he played in that tournament that year (`apps`), or his birth country is the country
    the award was given to. The second rule catches players whose tournament rows the NHL's data lacks, without crediting a namesake from
    another country."""
    awards = awards or load_awards()
    tournaments = load_results()["tournaments"]
    key = name_key(name)
    played = {(a["tournament"], a["year"]) for a in apps}
    born = lineage(ISO_TO_IOC.get(birth_country, birth_country))
    out = []
    for a in awards["awards"]:
        if name_key(a["name"]) != key:
            continue
        if (a["tournament"], a["year"]) in played or (born and lineage(a["code"]) == born):
            out.append({"tournament": a["tournament"], "label": tournaments[a["tournament"]]["label"], "year": a["year"], "award": a["award"],
                        "award_label": AWARD_LABELS[a["award"]], "code": a["code"], "country": country_name(a["code"])})
    return sorted(out, key=lambda h: (-h["year"], h["tournament"], AWARD_ORDER.index(h["award"])))
