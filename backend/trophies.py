"""Trophy winners by season, from the NHL's records site (records.nhl.com).

Pure shaping logic lives here; api.py fetches the rows and adds the season stats for the scoring awards. Notes on the feed:
- Each season lists finalists too, so only rows with status WINNER count.
- Team trophies (the Stanley Cup, Presidents' Trophy and the conference trophies) also carry a row per player on the winning team;
  the team's own row is the one with no player id.
- Awards can be shared in a season (the Vezina and Jennings often have two or three winners).
- Its `value` field is only filled in for some awards and is junk for others, so the scoring stats come from our own season totals.
"""
import re

TEAM_CATEGORY = 1

# Scoring awards: trophy id -> the season-total columns (from career_season) shown next to each winner.
STAT_AWARDS = {
    15: ["games_played", "goals"],                              # Maurice "Rocket" Richard Trophy
    16: ["games_played", "goals", "assists", "points"],         # Art Ross Trophy
}


def key(name):
    """A name reduced to lowercase letters and digits, so the same award matches across feeds despite curly quotes."""
    return re.sub(r"[^a-z0-9]", "", (name or "").lower())


def winners(rows, category_id, team_codes):
    """Winners, newest season first: [{season_id, name, player_id, team}]. team_codes: {team id: abbreviation}."""
    out = []
    for r in rows:
        if r.get("status") != "WINNER":
            continue
        if category_id == TEAM_CATEGORY and r.get("playerId") is not None:
            continue
        out.append({
            "season_id": r["seasonId"],
            "name": r.get("fullName"),
            "player_id": r.get("playerId"),
            "team": team_codes.get(r.get("teamId")),
        })
    return sorted(out, key=lambda w: (-w["season_id"], w["name"] or ""))


def add_stats(winner_rows, season_lines, columns):
    """Attach each winner's season totals (a dict per (player id, season id) in season_lines) under 'stats'."""
    for w in winner_rows:
        line = season_lines.get((w["player_id"], w["season_id"]))
        w["stats"] = {c: line[c] for c in columns} if line else None
    return winner_rows


# How the NHL's trophy categories read on the index page, in display order.
CATEGORY_GROUPS = [
    ("Player awards", {2}),
    ("Team trophies", {TEAM_CATEGORY}),
    ("Coaches, executives and builders", {3, 4, 5}),
]


def summary(info, winner_rows):
    """One index-page row for a trophy: what it is, its newest winner and when it began. winner_rows come from winners()."""
    latest = winner_rows[0] if winner_rows else None
    return {
        "id": info["id"],
        "name": info["name"],
        "category_id": info["categoryId"],
        "description": info.get("briefDescription"),
        "first_season": winner_rows[-1]["season_id"] if winner_rows else None,
        "latest": latest and {k: latest[k] for k in ("season_id", "name", "player_id", "team")},
    }


def group_of(category_id):
    """The index-page section title for a trophy category."""
    return next((title for title, ids in CATEGORY_GROUPS if category_id in ids), "Other")
