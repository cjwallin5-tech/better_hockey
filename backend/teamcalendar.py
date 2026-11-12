"""A team's whole season as a calendar: every game with its opponent, home or away, result or start time, and whether it is the second
night of a back-to-back, plus an iCalendar (.ics) version to put in a phone or desktop calendar. Pure functions over game rows."""
from datetime import datetime, timedelta, timezone

FINAL_STATES = ("OFF", "FINAL")
LIVE_STATES = ("LIVE", "CRIT")
GAME_HOURS = 3  # how long a game is drawn for in a calendar app


def game_entry(g, abbrev, previous_date):
    """One calendar entry for the team's game `g` (a game row). previous_date: the date of the team's previous game, or None."""
    home = g["home"] == abbrev
    final = g["state"] in FINAL_STATES
    us, them = (g["home_score"], g["away_score"]) if home else (g["away_score"], g["home_score"])
    result = None
    if final and us is not None and them is not None:
        result = "W" if us > them else ("L" if g["last_period"] in (None, "REG") else "OTL")
    return {
        "game_id": g["game_id"], "date": g["game_date"].isoformat(), "start_time": g["start_time"].isoformat() if g["start_time"] else None,
        "opponent": g["away"] if home else g["home"], "home": home, "venue": g["venue"],
        "state": "FINAL" if final else ("LIVE" if g["state"] in LIVE_STATES else "UPCOMING"),
        "us": us if final else None, "them": them if final else None, "result": result,
        "period": g["last_period"] if final and g["last_period"] in ("OT", "SO") else None,
        "back_to_back": previous_date is not None and (g["game_date"] - previous_date) == timedelta(days=1),
    }


def build(games, abbrev):
    """{games: [entry...], summary} from the team's game rows in date order."""
    entries, previous = [], None
    for g in games:
        entries.append(game_entry(g, abbrev, previous))
        previous = g["game_date"]
    played = [e for e in entries if e["result"]]
    return {"games": entries, "summary": {
        "games": len(entries), "played": len(played), "remaining": len(entries) - len(played),
        "wins": sum(e["result"] == "W" for e in played), "losses": sum(e["result"] == "L" for e in played),
        "ot_losses": sum(e["result"] == "OTL" for e in played),
        "home": sum(e["home"] for e in entries), "away": sum(not e["home"] for e in entries),
        "back_to_backs": sum(e["back_to_back"] for e in entries),
    }}


# --- iCalendar -------------------------------------------------------------------------------------------

def _escape(text):
    """Text values in iCalendar escape backslashes, semicolons, commas and newlines."""
    return str(text).replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\r\n", "\\n").replace("\n", "\\n")


def _fold(line):
    """Content lines are folded at 75 octets: the rest continues on the next line after a space."""
    raw = line.encode("utf-8")
    if len(raw) <= 75:
        return line
    parts, current, size = [], "", 0
    for ch in line:
        n = len(ch.encode("utf-8"))
        if size + n > (75 if not parts else 74):
            parts.append(current)
            current, size = "", 0
        current += ch
        size += n
    parts.append(current)
    return "\r\n ".join(parts)


def _stamp(dt):
    return dt.strftime("%Y%m%dT%H%M%SZ")


def to_ics(abbrev, team_name, season_label, games, now):
    """The season as an iCalendar file (CRLF line endings, one timed event per game). `games` are the entries from build().
    `now` is the timestamp the file is stamped with. Games with no start time yet are left out."""
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Faceoff//Team calendar//EN", "CALSCALE:GREGORIAN", "METHOD:PUBLISH",
             f"X-WR-CALNAME:{_escape(f'{team_name} {season_label}')}"]
    for g in games:
        if not g["start_time"]:
            continue
        start = datetime.fromisoformat(g["start_time"]).astimezone(timezone.utc)
        title = f"{'vs' if g['home'] else '@'} {g['opponent']}"
        if g["result"]:
            title += f" ({g['result']} {g['us']}-{g['them']}{' ' + g['period'] if g['period'] else ''})"
        lines += ["BEGIN:VEVENT", f"UID:game-{g['game_id']}@nhl-stats", f"DTSTAMP:{_stamp(now)}", f"DTSTART:{_stamp(start)}",
                  f"DTEND:{_stamp(start + timedelta(hours=GAME_HOURS))}", f"SUMMARY:{_escape(abbrev + ' ' + title)}"]
        if g["venue"]:
            lines.append(f"LOCATION:{_escape(g['venue'])}")
        lines.append("END:VEVENT")
    lines.append("END:VCALENDAR")
    return "\r\n".join(_fold(line) for line in lines) + "\r\n"
