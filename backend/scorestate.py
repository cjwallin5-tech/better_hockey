"""Score-state splits: how play and finishing change with the score, and score-adjusted team ratings.

A shot's score state is the shooting team's lead (goals for minus goals against) just before the shot, worked out
from the game's own goals: trail2 (down two or more), trail1, tied, lead1, lead2 (up two or more). Only unblocked
attempts at even strength in the three regulation periods count (blocks are not stored for every season, and overtime
is 3-on-3), and empty-net attempts have no xG so they are left out of the xG figures.

Score effects: teams that trail shoot more and teams that lead shoot less, so a team that spent the season ahead looks
worse by raw shot share than it is. For each state the league's share of events going to the team in that state is
P_s (it is above 50% for trailing states). A team's events in state s are re-weighted so the league sits at exactly
50/50 in every state: its own events by 0.5 / P_s and its opponents' events by 0.5 / (1 - P_s). The adjusted share is
what the team would post in a game played at an average score state.

Clutch: finishing (goals against expected goals) in close and late situations (third period, within one goal either
way) compared with the same player's finishing everywhere else. Goals are rare, so the gap is almost always inside
chance; analysis/backtest_clutch.py checks whether it repeats from one season to the next.
"""
import math

STATES = ("trail2", "trail1", "tied", "lead1", "lead2")
MIRROR = {"trail2": "lead2", "trail1": "lead1", "tied": "tied", "lead1": "trail1", "lead2": "trail2"}
GROUP = {"trail2": "trailing", "trail1": "trailing", "tied": "tied", "lead1": "leading", "lead2": "leading"}
ATTEMPT = ("shot", "miss", "goal")


def state_of(diff):
    return "trail2" if diff <= -2 else "trail1" if diff == -1 else "tied" if diff == 0 else "lead1" if diff == 1 else "lead2"


def annotate(game_shots):
    """One game's attempts (any order) with `diff` (the shooter's lead before the shot) and `state` added.

    Rows need event_id, time_sec, is_home, kind. Goals, including empty-net and overtime ones, move the score; the
    rows returned are the same dicts, in game order, for every kind (callers filter).
    """
    home = away = 0
    out = []
    for s in sorted(game_shots, key=lambda s: (s["time_sec"], s["event_id"])):
        diff = (home - away) if s["is_home"] else (away - home)
        s["diff"], s["state"] = diff, state_of(diff)
        out.append(s)
        if s["kind"] == "goal":
            home += 1 if s["is_home"] else 0
            away += 0 if s["is_home"] else 1
    return out


def counts(s):
    """Whether a row counts toward the even-strength splits."""
    return s["kind"] in ATTEMPT and s.get("strength") == "ev" and s["period"] <= 3


class Tally:
    """Events for and against one team in each state."""

    def __init__(self):
        self.f = {k: dict.fromkeys(STATES, 0.0) for k in ("xg", "att", "goals")}
        self.a = {k: dict.fromkeys(STATES, 0.0) for k in ("xg", "att", "goals")}

    def add(self, store, state, s):
        store["att"][state] += 1
        store["goals"][state] += s["kind"] == "goal"
        if s.get("xg") is not None and not s.get("empty_net"):
            store["xg"][state] += s["xg"]


def team_tallies(shots):
    """{team: Tally} from annotated rows that also carry `team` and `opponent` abbreviations."""
    out = {}
    for s in shots:
        if not counts(s):
            continue
        out.setdefault(s["team"], Tally()).add(out[s["team"]].f, s["state"], s)
        out.setdefault(s["opponent"], Tally()).add(out[s["opponent"]].a, MIRROR[s["state"]], s)
    return out


def league_share(tallies, key):
    """P_s per state: the share of events in state s that go to the team in that state, for xg, att or goals."""
    f = {s: sum(t.f[key][s] for t in tallies.values()) for s in STATES}
    a = {s: sum(t.a[key][s] for t in tallies.values()) for s in STATES}
    return {s: (f[s] / (f[s] + a[s]) if f[s] + a[s] else 0.5) for s in STATES}


def share(f, a):
    return f / (f + a) if f + a else None


def team_rows(tallies, league=None):
    """One row per team: raw and score-adjusted xG and attempt shares, plus the share in each state group.
    `league` is the tallies the score effect is measured on (more seasons make it steadier); default is `tallies`."""
    p = {k: league_share(league or tallies, k) for k in ("xg", "att", "goals")}
    rows = []
    for team, t in tallies.items():
        row = {"team": team}
        for key in ("xg", "att"):
            raw_f, raw_a = sum(t.f[key].values()), sum(t.a[key].values())
            adj_f = sum(t.f[key][s] * 0.5 / p[key][s] for s in STATES if 0 < p[key][s] < 1)
            adj_a = sum(t.a[key][s] * 0.5 / (1 - p[key][s]) for s in STATES if 0 < p[key][s] < 1)
            row[f"{key}_for"], row[f"{key}_against"] = round(raw_f, 2), round(raw_a, 2)
            row[f"{key}_pct"] = _r(share(raw_f, raw_a))
            row[f"{key}_pct_adj"] = _r(share(adj_f, adj_a))
        row["by_state"] = {}
        for g in ("trailing", "tied", "leading"):
            ss = [s for s in STATES if GROUP[s] == g]
            row["by_state"][g] = {
                "xg_pct": _r(share(sum(t.f["xg"][s] for s in ss), sum(t.a["xg"][s] for s in ss))),
                "att_pct": _r(share(sum(t.f["att"][s] for s in ss), sum(t.a["att"][s] for s in ss))),
                "events": int(sum(t.f["att"][s] + t.a["att"][s] for s in ss)),
            }
        rows.append(row)
    return rows, {k: {s: round(v, 4) for s, v in p[k].items()} for k in p}


def _r(v):
    return None if v is None else round(v, 4)


def league_effects(tallies):
    """The league-wide score effect, per state: the share of xG, attempts and goals going to the team in that state
    and how many events there were."""
    p = {k: league_share(tallies, k) for k in ("xg", "att", "goals")}
    n = {s: sum(t.f["att"][s] for t in tallies.values()) for s in STATES}
    total = sum(n.values()) or 1
    return [{"state": s, "xg_share": round(p["xg"][s], 4), "att_share": round(p["att"][s], 4),
             "goal_share": round(p["goals"][s], 4), "attempts": int(n[s]), "pct_of_attempts": round(n[s] / total, 4)}
            for s in STATES]


# --- Players ----------------------------------------------------------------------------------------
def is_close_late(s):
    """Third period with the shooter's team within one goal either way."""
    return s["period"] == 3 and abs(s["diff"]) <= 1


def finishing(shots):
    """Goals and expected goals over a group of a player's own attempts (those with an xG)."""
    modeled = [s for s in shots if s.get("xg") is not None and not s.get("empty_net")]
    on_goal = [s for s in modeled if s["kind"] in ("shot", "goal")]
    xg = sum(s["xg"] for s in modeled)
    goals = sum(1 for s in modeled if s["kind"] == "goal")
    return {"attempts": len(modeled), "on_goal": len(on_goal), "goals": goals, "xg": xg,
            "var": sum(s["xg"] * (1 - s["xg"]) for s in modeled)}


def clutch(shots):
    """A player's close-and-late finishing against his own finishing everywhere else (his shots, all strengths,
    periods 1-3 and overtime excluded). Returns the two groups, the goals his rest-of-game finishing would predict
    for the clutch shots, and a z-score for the gap (None without enough to compare)."""
    own = [s for s in shots if s["kind"] in ATTEMPT and s["period"] <= 3]
    late = finishing([s for s in own if is_close_late(s)])
    rest = finishing([s for s in own if not is_close_late(s)])
    out = {"close_late": _fin(late), "other": _fin(rest), "expected_goals": None, "z": None}
    if rest["xg"] > 0 and late["xg"] > 0 and rest["goals"] > 0:
        scale = rest["goals"] / rest["xg"]            # his own finishing everywhere else
        expected = late["xg"] * scale
        sd = math.sqrt(late["var"] * scale * scale) if late["var"] > 0 else None
        out["expected_goals"] = round(expected, 2)
        out["z"] = round((late["goals"] - expected) / sd, 2) if sd else None
    return out


def _fin(f):
    return {"attempts": f["attempts"], "goals": f["goals"], "xg": round(f["xg"], 2), "gsax": round(f["goals"] - f["xg"], 2)}


def by_state(shots):
    """A player's own attempts, goals and xG in trailing, tied and leading states (even strength, regulation)."""
    out = {}
    for g in ("trailing", "tied", "leading"):
        f = finishing([s for s in shots if counts(s) and GROUP[s["state"]] == g])
        out[g] = {**_fin(f), "on_goal": f["on_goal"]}
    return out
