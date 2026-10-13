"""Per-game on-ice shot attempts (Corsi/Fenwick) from play-by-play plus shift charts.

The NHL's play-by-play doesn't say who was on the ice, so we join each shot attempt with the
players whose shifts cover that moment. Only 5v5 (both goalies in net) is counted, matching
the NHL's published season "SAT" numbers.
"""
from collections import defaultdict

# Every shot attempt: on goal, missed, blocked, or a goal.
ATTEMPT_EVENTS = {"shot-on-goal", "missed-shot", "blocked-shot", "goal"}
FIVE_ON_FIVE = "1551"  # situationCode: away goalie, away skaters, home skaters, home goalie
SHIFT_TYPE = 517  # regular shifts; other type codes are goal/penalty markers


def clock_to_seconds(period, mmss):
    """Seconds elapsed since the start of regulation/overtime for a period-relative clock."""
    minutes, seconds = mmss.split(":")
    return (period - 1) * 1200 + int(minutes) * 60 + int(seconds)


def parse_shifts(shift_rows):
    """player_id -> (team_id, [(start, end), ...]) in absolute game seconds."""
    shifts = defaultdict(list)
    team_of = {}
    for s in shift_rows:
        if s.get("typeCode") != SHIFT_TYPE or not s.get("startTime") or not s.get("endTime"):
            continue
        if s["period"] > 4:  # shootouts have no on-ice attribution
            continue
        start = clock_to_seconds(s["period"], s["startTime"])
        end = clock_to_seconds(s["period"], s["endTime"])
        if end < start:  # malformed row
            continue
        shifts[s["playerId"]].append((start, end))
        team_of[s["playerId"]] = s["teamId"]
    return shifts, team_of


def parse_attempts(plays, situation=FIVE_ON_FIVE):
    """Shot attempts in the given strength state: (second, shooting team id, event kind)."""
    out = []
    for p in plays:
        if p["typeDescKey"] not in ATTEMPT_EVENTS:
            continue
        if p["periodDescriptor"]["number"] > 4 or p["periodDescriptor"]["periodType"] == "SO":
            continue
        if situation and p.get("situationCode") != situation:
            continue
        t = clock_to_seconds(p["periodDescriptor"]["number"], p["timeInPeriod"])
        out.append((t, p["details"]["eventOwnerTeamId"], p["typeDescKey"]))
    return out


def on_ice(shifts, t, include_start=False):
    """True if a player with these (start, end) shifts was on the ice at second t.

    A shift covers (start, end]: at the very second a shift begins the player has not yet
    contributed, and at the second it ends they still count. `include_start` flips that.
    """
    if include_start:
        return any(a <= t < b for a, b in shifts)
    return any(a < t <= b for a, b in shifts)


def game_corsi(plays, shift_rows, include_start=False):
    """player_id -> dict(cf, ca, ff, fa, gf, ga) at 5v5 for one game."""
    shifts, team_of = parse_shifts(shift_rows)
    attempts = parse_attempts(plays)
    totals = defaultdict(lambda: dict(cf=0, ca=0, ff=0, fa=0, gf=0, ga=0))
    for t, shooting_team, kind in attempts:
        for pid, spans in shifts.items():
            if not on_ice(spans, t, include_start):
                continue
            mine = team_of[pid] == shooting_team
            row = totals[pid]
            row["cf" if mine else "ca"] += 1
            if kind != "blocked-shot":
                row["ff" if mine else "fa"] += 1
            if kind == "goal":
                row["gf" if mine else "ga"] += 1
    return totals


def coverage(plays, shift_rows):
    """Share of 5v5 attempts where exactly 12 players (5 skaters + goalie per side) were matched
    as on the ice. Low values mean the shift data is missing or incomplete for that game."""
    shifts, _ = parse_shifts(shift_rows)
    attempts = parse_attempts(plays)
    if not attempts or not shifts:
        return 0.0
    full = sum(1 for t, _, _ in attempts if sum(on_ice(sp, t) for sp in shifts.values()) == 12)
    return full / len(attempts)


# --- Line combinations ----------------------------------------------------------------------------
from bisect import bisect_right
from itertools import combinations


def game_lines(plays, shift_rows, roster_spots):
    """5v5 time on ice and shot attempts for players, pairs and forward lines in one game.

    Time comes from sweeping shift boundaries; the strength state of each stretch is the
    situationCode of the most recent play (an approximation: the code only changes on plays).
    Returns {"toi": {player: sec}, "pairs": {(team, a, b): [toi, cf, ca, gf, ga]},
             "trios": {(team, a, b, c): [toi, cf, ca, gf, ga]}} with ids sorted within a key.
    """
    pos = {r["playerId"]: r.get("positionCode") for r in roster_spots}
    shifts, team_of = parse_shifts(shift_rows)
    skaters = {pid: spans for pid, spans in shifts.items() if pos.get(pid) in ("C", "L", "R", "D")}

    state_events = sorted(
        (clock_to_seconds(p["periodDescriptor"]["number"], p["timeInPeriod"]), p["situationCode"])
        for p in plays
        if p.get("situationCode") and p["periodDescriptor"]["number"] <= 3
    )
    times = [t for t, _ in state_events]
    states = [s for _, s in state_events]

    def state_at(t):
        i = bisect_right(times, t) - 1
        return states[max(i, 0)] if states else None

    bounds = {0, 1200, 2400, 3600}
    for spans in skaters.values():
        for a, b in spans:
            bounds.update((a, b))
    bounds.update(times)
    ordered = sorted(b for b in bounds if b <= 3600)

    toi = defaultdict(int)
    pairs = defaultdict(lambda: [0, 0, 0, 0, 0])
    trios = defaultdict(lambda: [0, 0, 0, 0, 0])

    def groups(on):
        """Skaters on ice split by team, then (forwards, defense)."""
        by_team = defaultdict(list)
        for pid in on:
            by_team[team_of[pid]].append(pid)
        return by_team

    for t0, t1 in zip(ordered, ordered[1:]):
        if t1 <= t0 or state_at(t0) != FIVE_ON_FIVE:
            continue
        on = [pid for pid, spans in skaters.items() if any(a <= t0 and t1 <= b for a, b in spans)]
        dt = t1 - t0
        for team, members in groups(on).items():
            members.sort()
            for pid in members:
                toi[pid] += dt
            for a, b in combinations(members, 2):
                pairs[(team, a, b)][0] += dt
            fwds = [p for p in members if pos.get(p) != "D"]
            if len(fwds) == 3:
                trios[(team, *fwds)][0] += dt

    # Shot attempts and goals credited to whoever was on the ice together.
    for t, shooting_team, kind in parse_attempts(plays):
        on = [pid for pid, spans in skaters.items() if on_ice(spans, t)]
        for team, members in groups(on).items():
            members.sort()
            mine = team == shooting_team
            cf, ca = (1, 0) if mine else (0, 1)
            gf, ga = (1, 0) if mine and kind == "goal" else (0, 1) if (not mine and kind == "goal") else (0, 0)
            for a, b in combinations(members, 2):
                row = pairs[(team, a, b)]
                row[1] += cf; row[2] += ca; row[3] += gf; row[4] += ga
            fwds = [p for p in members if pos.get(p) != "D"]
            if len(fwds) == 3:
                row = trios[(team, *fwds)]
                row[1] += cf; row[2] += ca; row[3] += gf; row[4] += ga
    return {"toi": dict(toi), "pairs": dict(pairs), "trios": dict(trios)}
