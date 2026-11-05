"""Win and losing streaks for a team, for the watchlist part of the morning email.

A streak is worth a line once it reaches MIN_STREAK games, and a long one that just ended is news too (MIN_ENDED).
Overtime and shootout losses count as losses here, as in the standings' streak column (which calls them OT): the team lost,
even though it kept a point. The email says how many of a losing run went to overtime so that is not hidden.
"""
MIN_STREAK = 4    # games in a row before a running streak is mentioned
MIN_ENDED = 5     # a streak this long that the latest game just ended is mentioned


def _run(results, win):
    """How many games at the end of `results` are all wins (win=True) or all non-wins (win=False)."""
    n = 0
    for r in reversed(results):
        if (r["result"] == "W") != win:
            break
        n += 1
    return n


def analyze(results):
    """results: [{result: 'W'|'L'|'OTL', gf, ga, opponent}] oldest first. Returns {'current': ..., 'ended': ...}:
    current is the running streak {'kind': 'win'|'losing', 'length', 'gf', 'ga', 'otl'} or None under MIN_STREAK;
    ended is {'kind', 'length', 'by': the game that ended it} or None. Both can be None."""
    if not results:
        return {"current": None, "ended": None}
    won_last = results[-1]["result"] == "W"
    length = _run(results, won_last)
    run = results[-length:]
    current = None
    if length >= MIN_STREAK:
        current = {"kind": "win" if won_last else "losing", "length": length, "gf": sum(r["gf"] for r in run),
                   "ga": sum(r["ga"] for r in run), "otl": sum(r["result"] == "OTL" for r in run)}
    # the streak before the latest game, when the latest game broke it
    earlier = results[:-1]
    ended = None
    if earlier and (earlier[-1]["result"] == "W") != won_last:
        before = _run(earlier, not won_last)
        if before >= MIN_ENDED:
            ended = {"kind": "win" if not won_last else "losing", "length": before, "by": results[-1]}
    return {"current": current, "ended": ended}


def lines(name, info):
    """The email lines for one team: [] when there is nothing to say. name is how the email calls the team."""
    out = []
    cur, end = info["current"], info["ended"]
    if cur and cur["kind"] == "win":
        out.append(f"{name} have won {cur['length']} straight, outscoring opponents {cur['gf']}-{cur['ga']}.")
    elif cur:
        ot = f" ({cur['otl']} in overtime or a shootout)" if cur["otl"] else ""
        out.append(f"{name} have lost {cur['length']} straight{ot}, being outscored {cur['ga']}-{cur['gf']}.")
    if end:
        by = end["by"]
        score = f"{by['gf']}-{by['ga']}" if by["gf"] > by["ga"] else f"{by['ga']}-{by['gf']}"
        if end["kind"] == "win":
            how = "an overtime or shootout loss" if by["result"] == "OTL" else "a loss"
            out.append(f"{name}'s {end['length']}-game win streak ended with {how} to {by['opponent']}, {score}.")
        else:
            out.append(f"{name}'s {end['length']}-game losing streak ended with a win over {by['opponent']}, {score}.")
    return out
