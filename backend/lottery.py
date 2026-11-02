"""NHL draft lottery: what a lottery seed is worth, and what a team's chances of each pick are.

The 2026 lottery guide (the NHL's own, with the rules in force since 2022): the 16 teams that miss the playoffs are seeded by points, fewest
first, and two drawings are held, the first for the first overall pick and the second for the second. Each drawing is won at random with the
odds below (the second draw's odds are scaled up for the teams still in it). A team can move up at most 10 spots, so only seeds 1-11 can win
first overall; a seed from 12th to 16th that wins a draw is moved up as far as the cap allows (12th to 2nd, 13th to 3rd, and so on) and the
slot it would otherwise have taken goes to the best seed left. The teams that win nothing keep their order in the remaining slots, so a team
can fall at most two places. Check against the guide: seed 1's chance of the first pick is its own 18.5% plus the 7.0% from seeds 12-16, 25.5%.

Not modelled: who owns each pick (trades and conditions), and the NHL's limit on a team moving up in the lottery more than twice in five years;
both can change who picks where. When both drawings aim at the same slot (a 12th seed wins the first draw and an eligible team the second,
about 2% of the time) the second winner takes the next free slot, which the guide does not spell out.
"""
import numpy as np

ODDS = (0.185, 0.135, 0.115, 0.095, 0.085, 0.075, 0.065, 0.06, 0.05, 0.035, 0.03, 0.025, 0.02, 0.015, 0.005, 0.005)  # first draw, by seed
SEEDS = len(ODDS)
MAX_MOVE = 10


def _slot(taken, target):
    while target in taken:
        target += 1
    return target


def pick_matrix(odds=ODDS, max_move=MAX_MOVE):
    """M[s][p]: the chance seed s+1 ends up with pick p+1, from enumerating both drawings."""
    n = len(odds)
    m = np.zeros((n, n))
    for w1 in range(1, n + 1):
        p1 = odds[w1 - 1]
        slots = {}
        if w1 - max_move <= 1:
            slots[1] = w1
        else:
            slots[w1 - max_move] = w1          # moved up as far as allowed
            slots[1] = 1                       # the best seed takes the first pick
        left = [t for t in range(1, n + 1) if t not in slots.values()]
        z = sum(odds[t - 1] for t in left)
        for w2 in left:
            q = odds[w2 - 1] / z
            taken = dict(slots)
            taken[_slot(taken, max(2, w2 - max_move))] = w2
            free = [k for k in range(1, n + 1) if k not in taken]
            rest = [t for t in range(1, n + 1) if t not in taken.values()]
            for k, t in zip(free, rest):
                taken[k] = t
            for pick, team in taken.items():
                m[team - 1][pick - 1] += p1 * q
    return m


MATRIX = pick_matrix()


def pick_distribution(seed_probs, matrix=MATRIX):
    """The chances of picks 1-16 for a team from its chances of each lottery seed (seed_probs sums to its chance of being in the lottery)."""
    sp = np.asarray(seed_probs, dtype=float)
    return (sp[: matrix.shape[0]] @ matrix).tolist()


def summary(seed_probs, matrix=MATRIX):
    """A team's lottery chances: in the lottery, the worst record, first overall, a top-two and top-five pick, and its expected pick given that it
    is in the lottery."""
    dist = pick_distribution(seed_probs, matrix)
    in_lottery = float(sum(seed_probs))
    return {
        "in_lottery": in_lottery,
        "worst_record": float(seed_probs[0]) if len(seed_probs) else 0.0,
        "first_overall": dist[0], "top_two": dist[0] + dist[1], "top_five": sum(dist[:5]),
        "expected_pick": (sum((i + 1) * p for i, p in enumerate(dist)) / in_lottery) if in_lottery > 0 else None,
        "picks": dist,
    }
