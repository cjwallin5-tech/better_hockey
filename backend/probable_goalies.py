"""Probable starting goalies, inferred from who has been starting for the team.

The NHL publishes no starter until the team confirms it, so this is a guess and the page says so.
Model:
- A goalie's base weight is how often the team has started him lately: each of the team's last
  WINDOW games counts DECAY times less than the one after it.
- On the second night of a back-to-back, the goalie who started the night before is likely rested.
  His chance of going again is the league's observed repeat rate this season, shrunk toward
  REPEAT_PRIOR while the sample is small and never below REPEAT_FLOOR; the rest of the probability is split among the others
  by their base weights.
- Only goalies who started in the team's last WINDOW games are candidates, so traded or injured
  goalies drop out on their own.
"""
WINDOW = 10
DECAY = 0.85
# Confidence correction, checked against the season's own starts (accuracy.py): the raw shares were too sure of themselves when
# they were high (a goalie the model gave 90% or more started about 78% of the time), because teams also rotate their goalies on
# days that are not back-to-backs, which the model cannot see coming. SHRINK pulls every share toward an even split among the
# candidates. 0.2 was picked by replaying 272 team games: fitted on the first half of the season it improved both the log loss and
# the calibration error of the second half too (calibration error 0.070 -> 0.053, log loss 0.709 -> 0.705); more than about 0.4
# starts to hurt. Holding some probability back for a goalie not on the list was tried and made the log loss worse at every setting
# (only 4% of starters were unseen), so it is not done. Re-check on the Accuracy page as games accumulate.
SHRINK = 0.2
REPEAT_PRIOR = 0.15      # chance the same goalie starts both ends of a back-to-back
REPEAT_PRIOR_GAMES = 20  # back-to-backs' worth of weight given to REPEAT_PRIOR
REPEAT_FLOOR = 0.10      # a rested goalie is never certain: teams do start their #1 on both nights


def repeat_rate(back_to_backs, repeats):
    """League-wide chance a goalie starts both games of a back-to-back, shrunk toward the prior."""
    shrunk = (repeats + REPEAT_PRIOR * REPEAT_PRIOR_GAMES) / (back_to_backs + REPEAT_PRIOR_GAMES)
    return max(shrunk, REPEAT_FLOOR)


def calibrate(prob):
    """The raw shares {player_id: share} made less sure: pulled toward an even split among the candidates by SHRINK."""
    n = len(prob)
    return {pid: (1 - SHRINK) * p + SHRINK / n for pid, p in prob.items()}


def predict(recent_starters, back_to_back, p_repeat=REPEAT_PRIOR):
    """recent_starters: [(player_id, name)] for the team's last games, newest first.
    back_to_back: True when the team's previous game was yesterday and its starter is known.
    Returns candidates [{player_id, name, probability, starts}], most likely first."""
    recent = recent_starters[:WINDOW]
    if not recent:
        return []
    weight, starts, names = {}, {}, {}
    for age, (pid, name) in enumerate(recent):
        weight[pid] = weight.get(pid, 0.0) + DECAY ** age
        starts[pid] = starts.get(pid, 0) + 1
        names[pid] = name
    prob = {pid: w / sum(weight.values()) for pid, w in weight.items()}

    last = recent[0][0]
    if back_to_back and len(weight) > 1:
        others = sum(w for pid, w in weight.items() if pid != last)
        prob = {pid: p_repeat if pid == last else (1 - p_repeat) * weight[pid] / others for pid in weight}
    elif len(weight) == 1:
        # Only one goalie has started lately, but the team has a backup we have not seen yet (early in a season, usually). The replay
        # on the Accuracy page found that calling this goalie certain was wrong: the backup played all four back-to-back second nights
        # and four of ten other games. So he is not certain. On a back-to-back he is as likely to go again as any goalie (the repeat
        # rate); otherwise his chance is the rule of succession for k straight starts, (k + 1) / (k + 2). The rest goes to the unseen
        # backup, who is not in the list, so these shares add up to less than 1.
        k = len(recent)
        prob = {last: p_repeat if back_to_back else (k + 1) / (k + 2)}

    prob = calibrate(prob)
    out = [{"player_id": pid, "name": names[pid], "probability": round(p, 3), "starts": starts[pid]}
           for pid, p in prob.items()]
    return sorted(out, key=lambda c: -c["probability"])


def confirmed_starters(box):
    """{team_abbrev: (player_id, name)} for goalies the NHL boxscore marks as starting.
    Empty until the NHL publishes it, which is usually around puck drop, not the morning of."""
    out = {}
    for side in ("homeTeam", "awayTeam"):
        for g in (box.get("playerByGameStats") or {}).get(side, {}).get("goalies", []):
            if g.get("starter"):
                out[box[side]["abbrev"]] = (g["playerId"], (g.get("name") or {}).get("default", "Unknown"))
    return out


def apply_confirmed(candidates, confirmed):
    """Replace the guess with the confirmed starter at 100%. Keeps the full name from our own data
    when we know the goalie; a call-up we've never seen falls back to the boxscore's name."""
    pid, name = confirmed
    known = next((c for c in candidates if c["player_id"] == pid), None)
    return [{"player_id": pid, "name": known["name"] if known else name, "probability": 1.0,
             "starts": known["starts"] if known else 0}]


def next_distribution(recent_starters, previous, back_to_back, p_repeat=REPEAT_PRIOR, prepend=True):
    """Who starts the next game, given a distribution over who started the previous one.

    previous: {player_id: probability} (or {player_id: 1.0} when it is known). Each possible previous
    starter is tried in turn through predict(), and the answers are mixed by how likely he was.
    prepend: whether that previous start is missing from recent_starters (True once a game is more recent
    than our stored starts; False when recent_starters already ends with it).
    Returns {player_id: probability}."""
    names = {pid: name for pid, name in recent_starters}
    out = {}
    total = sum(previous.values()) or 1.0    # a lone known goalie's shares add up to less than 1: weigh by who is left, so it doesn't compound
    for h, weight in ((h, w / total) for h, w in previous.items()):
        history = ([(h, names.get(h, "Unknown"))] + list(recent_starters)) if prepend else list(recent_starters)
        for c in predict(history, back_to_back, p_repeat):
            out[c["player_id"]] = out.get(c["player_id"], 0.0) + weight * c["probability"]
    return out
