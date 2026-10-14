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
REPEAT_PRIOR = 0.15      # chance the same goalie starts both ends of a back-to-back
REPEAT_PRIOR_GAMES = 20  # back-to-backs' worth of weight given to REPEAT_PRIOR
REPEAT_FLOOR = 0.10      # a rested goalie is never certain: teams do start their #1 on both nights


def repeat_rate(back_to_backs, repeats):
    """League-wide chance a goalie starts both games of a back-to-back, shrunk toward the prior."""
    shrunk = (repeats + REPEAT_PRIOR * REPEAT_PRIOR_GAMES) / (back_to_backs + REPEAT_PRIOR_GAMES)
    return max(shrunk, REPEAT_FLOOR)


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
    elif back_to_back:
        prob = {last: 1.0}  # no other goalie has started lately: nobody to rest him for

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
