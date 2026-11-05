"""NHLe factors from our own data, and a backtest of whether they predict anything.

Run from backend/ (needs player_league_season, loaded by `python ingest.py backfill-leagues`):
    .venv/bin/python -I analysis/nhle_factors.py [--save]

A pair is one player's regular-season record in a non-NHL league (20+ games) followed by his NHL regular season the next season
(20+ games). The factor for a league is the games-weighted ratio of NHL points per game to that league's points per game
(weight = harmonic-style g1 x g2 / (g1 + g2), so a pair counts for no more than its shorter season). Confidence intervals come from
resampling players. The backtest fits on seasons up to CUTOFF and predicts the NHL points per game of later pairs, against
assuming every pair scores the average. --save writes the factors to nhle_factor (what the site reads).

Survivorship: only players who reached the NHL are in a pair, so the factors answer "if he gets there, how much does he score" and run
higher than they would for every prospect. Public NHLe tables share this and so does this one.
"""
from pathlib import Path
import math, random, sys
from collections import defaultdict
from datetime import date

import psycopg

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))   # run from backend/: python -I analysis/<script>.py
import config, nhle

MIN_GAMES = 20
MIN_PAIRS = 30        # pairs a league needs before its factor is used
CUTOFF = 20172018     # the backtest fits on pairs whose league season is up to this one
BOOTSTRAPS = 300

with psycopg.connect(config.DATABASE_URL) as conn:
    fetched = conn.execute("SELECT count(*) FROM player_league_fetched").fetchone()[0]
    rows = conn.execute("""
        WITH s AS (SELECT player_id, season_id, league, sum(games) g, sum(points) p FROM player_league_season
                   WHERE game_type = 2 AND games > 0 AND points IS NOT NULL GROUP BY 1, 2, 3)
        SELECT a.player_id, a.season_id, a.league, a.g, a.p, b.g, b.p, f.birth_date
        FROM s a JOIN s b ON b.player_id = a.player_id AND b.league = 'NHL' AND b.season_id = a.season_id + 10001
        JOIN player_league_fetched f ON f.player_id = a.player_id
        WHERE a.league <> 'NHL' AND a.g >= %s AND b.g >= %s""", (MIN_GAMES, MIN_GAMES)).fetchall()


def age_in(season_id, birth):
    """Age on September 15 of the season's first year, or None without a birth date."""
    return None if birth is None else (date(season_id // 10000, 9, 15) - birth).days / 365.25


pairs = []
for pid, season, league, ga, pa, gb, pb, birth in rows:
    pairs.append({"player": pid, "season": season, "league": league, "ppg_a": pa / ga, "ppg_b": pb / gb,
                  "w": ga * gb / (ga + gb), "age": age_in(season, birth)})
print(f"{fetched} players fetched, {len(pairs)} pairs ({len({p['player'] for p in pairs})} players)")


def factor(ps):
    den = sum(p["w"] * p["ppg_a"] for p in ps)
    return sum(p["w"] * p["ppg_b"] for p in ps) / den if den else None


by_league = defaultdict(list)
for p in pairs:
    by_league[p["league"]].append(p)

rng = random.Random(7)
print(f"\n{'league':16s} {'pairs':>5s} {'players':>7s} {'factor':>7s}   {'90% interval':>14s}   {'league ppg':>10s}  {'NHL ppg':>8s}")
FACTORS = {}
for league, ps in sorted(by_league.items(), key=lambda kv: -len(kv[1])):
    if len(ps) < 8:
        continue
    f = factor(ps)
    by_player = defaultdict(list)
    for p in ps:
        by_player[p["player"]].append(p)
    ids = list(by_player)
    boots = sorted(factor([p for i in (rng.choice(ids) for _ in ids) for p in by_player[i]]) for _ in range(BOOTSTRAPS))
    lo, hi = boots[int(0.05 * BOOTSTRAPS)], boots[int(0.95 * BOOTSTRAPS)]
    wsum = sum(p["w"] for p in ps)
    print(f"{league:16s} {len(ps):5d} {len(ids):7d} {f:7.3f}   {lo:6.3f} - {hi:6.3f}   {sum(p['w'] * p['ppg_a'] for p in ps) / wsum:10.2f}  {sum(p['w'] * p['ppg_b'] for p in ps) / wsum:8.2f}")
    if len(ps) >= MIN_PAIRS:
        FACTORS[league] = {"factor": f, "lo": lo, "hi": hi, "pairs": len(ps), "players": len(ids)}

# ---- backtest: fit on the early seasons, predict the later ones ------------------------------------------------
train = [p for p in pairs if p["season"] <= CUTOFF]
test = [p for p in pairs if p["season"] > CUTOFF]
fit = {lg: factor(ps) for lg, ps in by_league.items() if len([p for p in ps if p["season"] <= CUTOFF]) >= MIN_PAIRS}
fit = {lg: factor([p for p in by_league[lg] if p["season"] <= CUTOFF]) for lg in fit}
mean_b = sum(p["w"] * p["ppg_b"] for p in train) / sum(p["w"] for p in train) if train else 0
usable = [p for p in test if p["league"] in fit]
print(f"\nBacktest: fit on league seasons up to {CUTOFF} ({len(train)} pairs), predict {len(usable)} later pairs in leagues with {MIN_PAIRS}+ training pairs")


def score(pred):
    w = sum(p["w"] for p in usable)
    rmse = math.sqrt(sum(p["w"] * (pred(p) - p["ppg_b"]) ** 2 for p in usable) / w)
    xs, ys = [pred(p) for p in usable], [p["ppg_b"] for p in usable]
    mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
    cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    sx, sy = math.sqrt(sum((x - mx) ** 2 for x in xs)), math.sqrt(sum((y - my) ** 2 for y in ys))
    return rmse, (cov / (sx * sy) if sx and sy else float("nan"))


if usable:
    for name, pred in (("everyone scores the average", lambda p: mean_b), ("league factor x league ppg", lambda p: fit[p["league"]] * p["ppg_a"])):
        r, c = score(pred)
        print(f"  {name:30s} rmse {r:.4f}   correlation {c:+.3f}")
    # an age multiplier per bucket, fitted on the training pairs only, applied to the later ones
    def bucket_of(age):
        return None if age is None else nhle.age_bucket(age)
    ratios = {}
    for b in nhle.AGE_BUCKETS:
        grp = [p for p in train if p["league"] in fit and p["age"] is not None and nhle.age_bucket(p["age"]) == b[0]]
        if len(grp) >= 15:
            ratios[b[0]] = sum(p["w"] * p["ppg_b"] for p in grp) / sum(p["w"] * fit[p["league"]] * p["ppg_a"] for p in grp)
    age_pred = lambda p: fit[p["league"]] * p["ppg_a"] * ratios.get(bucket_of(p["age"]), 1.0)
    r, c = score(age_pred)
    print(f"  {'factor x age multiplier':30s} rmse {r:.4f}   correlation {c:+.3f}   multipliers fitted on training pairs: "
          + ", ".join(f"{k} {v:.2f}" for k, v in ratios.items()))
    # age: does the factor model over- or under-shoot by age?
    print("  actual NHL ppg / predicted, by age at the league season (1.00 = unbiased):")
    for lo, hi, label in ((0, 19, "under 19"), (19, 20, "19"), (20, 21, "20"), (21, 22, "21"), (22, 23, "22"), (23, 99, "23 and over")):
        grp = [p for p in usable if p["age"] is not None and lo <= p["age"] < hi]
        if len(grp) >= 15:
            a = sum(p["w"] * p["ppg_b"] for p in grp)
            e = sum(p["w"] * fit[p["league"]] * p["ppg_a"] for p in grp)
            print(f"    {label:12s} {len(grp):4d} pairs  {a / e:5.2f}")

# the age multipliers saved for the site are fitted on every pair
AGE_MULT = {}
for b in nhle.AGE_BUCKETS:
    grp = [p for p in pairs if p["league"] in FACTORS and p["age"] is not None and nhle.age_bucket(p["age"]) == b[0]]
    if len(grp) >= 15:
        AGE_MULT[b[0]] = sum(p["w"] * p["ppg_b"] for p in grp) / sum(p["w"] * FACTORS[p["league"]]["factor"] * p["ppg_a"] for p in grp)
print("\nage multipliers on all pairs: " + ", ".join(f"{k} {v:.2f}" for k, v in AGE_MULT.items()))

if "--save" in sys.argv:
    with psycopg.connect(config.DATABASE_URL) as conn:
        conn.execute((Path(__file__).resolve().parent.parent / "schema.sql").read_text())
        conn.execute("DELETE FROM nhle_factor")
        with conn.cursor() as cur:
            cur.executemany("INSERT INTO nhle_factor (league, factor, lo, hi, pairs, players) VALUES (%s,%s,%s,%s,%s,%s)",
                            [(lg, f["factor"], f["lo"], f["hi"], f["pairs"], f["players"]) for lg, f in FACTORS.items()])
            cur.execute("DELETE FROM nhle_age")
            cur.executemany("INSERT INTO nhle_age (bucket, multiplier) VALUES (%s, %s)", list(AGE_MULT.items()))
        conn.commit()
    print(f"\nsaved {len(FACTORS)} league factors to nhle_factor")
