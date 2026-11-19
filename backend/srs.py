"""Simple Rating System: how many goals a game better (or worse) than average a team is, once the strength of the opponents it has played
is counted. A team's rating is its average goal margin plus the average rating of its opponents, so a +1 margin against strong teams
rates higher than +1 against weak ones. The ratings average to zero. Strength of schedule is the average rating of the opponents faced.
Finished games only; a shootout win counts as the one-goal win the final score shows."""

ITERATIONS = 1000
TOLERANCE = 1e-9


def ratings(games):
    """games: [(home, away, home_score, away_score)] for finished games. Returns {team: {games, margin, sos, srs}}."""
    margin, opponents = {}, {}
    for home, away, home_score, away_score in games:
        if home_score is None or away_score is None:
            continue
        for team, other, diff in ((home, away, home_score - away_score), (away, home, away_score - home_score)):
            margin[team] = margin.get(team, 0) + diff
            opponents.setdefault(team, []).append(other)
    if not margin:
        return {}
    avg_margin = {t: margin[t] / len(opponents[t]) for t in margin}
    rating = dict(avg_margin)
    for _ in range(ITERATIONS):
        nxt = {t: avg_margin[t] + sum(rating[o] for o in opponents[t]) / len(opponents[t]) for t in rating}
        centre = sum(nxt.values()) / len(nxt)
        # each step is averaged with the last one: without that, a schedule that splits teams into two sides (two teams, say) bounces back
        # and forth between two answers instead of settling
        nxt = {t: (rating[t] + r - centre) / 2 for t, r in nxt.items()}
        change = max(abs(nxt[t] - rating[t]) for t in rating)
        rating = nxt
        if change < TOLERANCE:
            break
    return {t: {"games": len(opponents[t]), "margin": avg_margin[t], "srs": rating[t], "sos": rating[t] - avg_margin[t]} for t in rating}
