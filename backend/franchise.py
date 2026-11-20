"""A franchise's history from the NHL records site: its all-time record, Stanley Cups and playoff appearances, one line per season
(record, where it finished, how far it went in the playoffs), its captains and its retired numbers.

The records site stores a season's playoff outcome on the regular-season row: `playoffRound` and `seriesTitle` name the last series the team
played, `decision` is W or L in it, and `finalPlayoffRound` is how many rounds that era's playoffs had. So a team that won its last series
when that series was the final one won the Cup. Rank fields are 0 when the era had no such grouping (no divisions before 1967, say)."""


import html
import re


def list_items(snippet):
    """The text of each <li> in one of the records site's HTML list snippets (captainHistory, retiredNumbersSummary); [] for None."""
    out = []
    for item in re.findall(r"<li>(.*?)</li>", snippet or "", re.S):
        text = html.unescape(re.sub(r"<[^>]+>", "", item)).replace("\xa0", " ")
        text = re.sub(r"\s+", " ", text).strip()
        if text and text.lower() != "none":   # the site writes "None" for a franchise with nothing to list
            out.append(text)
    return out


def _split_notes(items):
    """(entries, notes): footnote lines start with * or ^ (what the marker means is spelled out in the line itself)."""
    return [i for i in items if i[0] not in "*^"], [i.lstrip("*^ ").strip() for i in items if i[0] in "*^"]


def captains(snippet):
    """{entries, notes} from captainHistory, newest first as the NHL lists them. An entry is {name, dates, none}: `none` marks a stretch
    with no captain (then name is None); a line with co-captains keeps its names and the "(co-captains)" label as written."""
    entries, notes = _split_notes(list_items(snippet))
    out = []
    for text in entries:
        name, sep, dates = text.partition(": ")
        if not sep:
            name, dates = text, None
        none = name.strip().lower().startswith("(no captain")
        out.append({"name": None if none else name.strip(), "dates": dates.strip() if dates else None, "none": none})
    return {"entries": out, "notes": notes}


_RETIRED = re.compile(r"^(\d+)\s*[–-]\s*(.+?)(?:\s*\(([^()]*)\))?\s*(\*)?$")


def retired_numbers(snippet):
    """{entries, notes} from retiredNumbersSummary. An entry is {number, name, years, starred}: years is the span with the team as written
    ("1952-63", "1936-43, 1945-52"), starred marks a line the notes explain (time with a WHA team, say). Shared numbers get one entry each."""
    entries, notes = _split_notes(list_items(snippet))
    out = []
    for text in entries:
        m = _RETIRED.match(text)
        if not m:
            notes.append(text)   # a line that isn't "number - name", kept so nothing the NHL says is lost
            continue
        out.append({"number": int(m.group(1)), "name": m.group(2).strip(), "years": m.group(3), "starred": bool(m.group(4))})
    return {"entries": out, "notes": notes}


def rank(value):
    """A finish position, or None when the era had no such grouping."""
    return value if value else None


def playoff_result(row, current_season):
    """{made, champion, text} for a season row: how far the team got. The season in progress has no result yet."""
    if row["seasonId"] == current_season:
        return {"made": None, "champion": False, "text": None}
    if not row.get("inPlayoffs"):
        return {"made": False, "champion": False, "text": "Missed the playoffs"}
    champion = row.get("decision") == "W" and row.get("playoffRound") == row.get("finalPlayoffRound")
    if champion:
        return {"made": True, "champion": True, "text": "Won the Stanley Cup"}
    title = row.get("seriesTitle")
    return {"made": True, "champion": False, "text": f"Lost in the {title}" if title else "Made the playoffs"}


def record_text(row):
    """'41-30-11' (W-L-OTL), '35-23-12' (W-L-T), or all four when the era had both ties and overtime losses."""
    wins, losses, ties, otl = row.get("wins") or 0, row.get("losses") or 0, row.get("ties"), row.get("overtimeLosses")
    if ties is not None and otl is not None:
        return f"{wins}-{losses}-{ties}-{otl}"
    return f"{wins}-{losses}-{ties if ties is not None else (otl or 0)}"


def season_view(row, current_season):
    return {
        "season_id": row["seasonId"], "team_name": row.get("teamName"), "games_played": row["gamesPlayed"],
        "record": record_text(row), "points": row["points"],
        "division_rank": rank(row.get("divisionSequence")), "conference_rank": rank(row.get("conferenceSequence")),
        "league_rank": rank(row.get("leagueSequence")), "playoffs": playoff_result(row, current_season),
    }


def totals_line(rows, game_type):
    """All-time wins, losses, ties and overtime losses for a game type, summed over the franchise's rows."""
    mine = [r for r in rows if r["gameTypeId"] == game_type]
    if not mine:
        return None
    total = lambda key: sum(r.get(key) or 0 for r in mine)
    return {"games_played": total("gamesPlayed"), "wins": total("wins"), "losses": total("losses"),
            "ties": total("ties"), "overtime_losses": total("overtimeLosses"), "points": total("points")}


def history(franchise, totals, appearances, season_rows, current_season, detail=None):
    """The franchise page: {name, first_season, seasons, cups, playoff_appearances, final_appearances, regular, playoffs, by_season (newest first)}.
    franchise: a row of the records site's franchise list; totals, appearances, season_rows: its rows for this franchise."""
    regular = sorted((r for r in season_rows if r["gameTypeId"] == 2), key=lambda r: r["seasonId"], reverse=True)
    cups = (appearances or {}).get("stanleyCupWins")
    if cups is None:
        cups = max((r.get("cups") or 0 for r in totals), default=0)
    return {
        "name": franchise["fullName"], "first_season": franchise["firstSeasonId"], "last_season": franchise.get("lastSeasonId"),
        "seasons": len(regular), "cups": cups,
        "playoff_appearances": (appearances or {}).get("playoffSeasons"), "final_appearances": (appearances or {}).get("stanleyCupAppearances"),
        "regular": totals_line(totals, 2), "playoffs": totals_line(totals, 3),
        "by_season": [season_view(r, current_season) for r in regular],
        "captains": captains((detail or {}).get("captainHistory")),
        "retired_numbers": retired_numbers((detail or {}).get("retiredNumbersSummary")),
    }
