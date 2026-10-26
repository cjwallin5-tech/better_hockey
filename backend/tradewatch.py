"""Sell-high and buy-low ideas for the morning email, from the luck figures (luck.py).

A player scoring well above what their shots predict (a hot streak that isn't backed by shot quality) is worth more in a
trade now than they will be, so selling is worth a look. A good player scoring well below it is the mirror image: cheap
to get now, likely to bounce back. The gaps are judged against the player's own finishing history (the *_adj figures), so
an elite finisher who always beats the model is not called lucky for it.

- SELL HIGH: your own skaters flagged hot with a gap of at least SELL_MIN_GAP points, and your hot goalies (a goalie's
  results barely repeat from year to year, so a hot stretch is the least likely to last).
- BUY LOW: skaters not on your roster, flagged cold, at least BUY_MIN_GAP points below expectation, and good enough that
  they are worth having (an expected pace of BUY_MIN_PACE points a season). Players on your watchlist come first.

What it does not know: who is available in your league (other teams' rosters are not visible), injuries, or role changes
(see the role-change section for those). Early in the season the flags swing a lot, so the email says so.
"""
import luck

SELL_MIN_GAP = 3       # points above expectation before a skater is worth a sell-high line
BUY_MIN_GAP = 3        # points below expectation before a skater is worth a buy-low line
BUY_MIN_PACE = 45      # expected points over a full season: below this the player isn't worth the trouble
SELL_MAX = 3
BUY_MAX = 3


def _skater(r, gap):
    expected = r["xpoints_adj"]
    return {"name": r["name"], "team": (r["team"] or "").split(",")[-1], "kind": "skater", "z": r["points_z_adj"],
            "actual": r["points"], "expected": expected, "gap": gap}


def sell_high(skaters, goalies, owned, games):
    """Rostered players (ids in `owned`) running hot. Skaters ranked by points above expectation, then goalies by z."""
    out = []
    for r in skaters:
        if r["player_id"] in owned and r["enough"] and r["points_flag_adj"] == "hot" and r["xpoints_adj"] is not None:
            gap = r["points"] - r["xpoints_adj"]
            if gap >= SELL_MIN_GAP:
                out.append(_skater(r, gap))
    out.sort(key=lambda a: -a["gap"])
    g = [{"name": r["name"], "team": (r["team"] or "").split(",")[-1], "kind": "goalie", "z": r["z"],
          "actual": r["goals"], "expected": r["xga"], "gap": r["xga"] - r["goals"]}
         for r in goalies if r["player_id"] in owned and r["enough"] and r["flag"] == "hot"]
    g.sort(key=lambda a: -a["z"])
    return (out + g)[:SELL_MAX]


def buy_low(skaters, owned, games, watched=frozenset()):
    """Cold, good skaters not on the roster: watchlist first, then the biggest gap below expectation."""
    out = []
    for r in skaters:
        if r["player_id"] in owned or not r["enough"] or r["points_flag_adj"] != "cold" or r["xpoints_adj"] is None:
            continue
        gap = r["xpoints_adj"] - r["points"]
        expected_pace = luck.pace(r["xpoints_adj"], r["games_played"], games)
        if gap >= BUY_MIN_GAP and expected_pace is not None and expected_pace >= BUY_MIN_PACE:
            out.append({**_skater(r, gap), "watched": r["player_id"] in watched})
    out.sort(key=lambda a: (not a["watched"], -a["gap"]))
    return out[:BUY_MAX]


def sell_line(a):
    """One sentence for the sell-high section."""
    if a["kind"] == "goalie":
        return (f"{a['name']} ({a['team']}) has allowed {a['actual']} goals against about {a['expected']:.0f} expected from the "
                f"shots faced (z {a['z']:+.1f}). Goalie results rarely repeat, so this is the likeliest streak to fade.")
    return (f"{a['name']} ({a['team']}) has {a['actual']} points against about {a['expected']:.0f} expected from the shots "
            f"(z {a['z']:+.1f}), {a['gap']:.0f} more than expected. That rate usually settles, so his trade value may be at a high.")


def buy_line(a):
    """One sentence for the buy-low section."""
    tag = " (on your watchlist)" if a.get("watched") else ""
    return (f"{a['name']} ({a['team']}){tag} has {a['actual']} points against about {a['expected']:.0f} expected from the shots "
            f"(z {a['z']:+.1f}), {a['gap']:.0f} fewer than expected. Worth a trade offer or a pickup if he is available.")
