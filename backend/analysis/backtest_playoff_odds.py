"""Backtest: how well do the playoff and Cup odds in backend/playoff_odds.py match what happened in past seasons?

Run from backend/: .venv/bin/python -I analysis/backtest_playoff_odds.py [fetch]
The first run (or `fetch`) downloads each season's playoff series and standings from the NHL's public API into
backend/data/playoff_backtest.json (about 80 requests, throttled); later runs read that file. Regular-season games come from game_hist and
team_game_hist, so run the ingest backfills first.

Three questions, each over the seasons where it applies:
  1. Series: with the real matchups and the end-of-season ratings, how often does the model's favourite win a best-of-seven, and is the
     chance it gives right? (2005-06 to 2024-25, every season with a bracket; the model's per-game strength scale is also refit.)
  2. Cup: from the actual 16-team field, how much chance did the model give the champion, and are Cup, final and conference-final chances
     calibrated? (only the current format: 2013-14 on, without the 2019-20 and 2020-21 seasons the format did not apply to.)
  3. Making the playoffs: from the standings a quarter and half of the way through the season, with the real remaining schedule,
     how well does the simulation's chance of making it match who did? (the same seasons as 2.)
  4. A sweep of the per-game strength scale (and the prior games) against all of the above.

Findings (run on 2026-10-27, behind the LOGIT_SCALE of 0.6 in playoff_odds.py, which was 0.9 before this):
  - Series: the better-rated, higher seed won 56.7% of 300 best-of-sevens. At a scale of 0.9 the model said 60.8% on average and was overconfident
    at the top (the 80%+ group: said 84%, happened 61%, 18 series); 0.6 says 57.5% and is calibrated on average. Either beats a coin flip
    (log loss 0.663 against 0.693) and home ice alone (Brier 0.249): the ratings carry some information, but little.
  - Cup: from the actual field the champion was given 6.8% on average against 6.2% for a 1-in-16 guess (9 seasons, the favourite never
    won, the champion was in the model's top 4 four times). Round two odds beat a flat guess clearly; conference-final, final and Cup odds do
    about as well as a flat guess, i.e. almost no skill past the first round. Even the best scale tried does about as well as a flat guess.
  - Making the playoffs: strong from a quarter of the way (Brier 0.156 against 0.250 for a flat guess; 0.107 from half way). At 0.9 it was
    too sure in both directions (teams given under 5% made it 6% of the time; teams at 60-80% made it 55%), which 0.6 mostly fixes.
  - 2015-16: the end-of-season standings put Boston in and Detroit out, the reverse of the real field (tied on points; the NHL's tiebreak differs from
    ours), so that season is left out of the Cup check.
Limits: 9 seasons for the Cup, so a single champion moves it a lot; the end-of-season ratings include games played after the teams'
playoff positions were settled; regular-season goal differential is the only strength measure tested here.
"""
import json
import math
import sys
import time
from collections import defaultdict
from pathlib import Path

import numpy as np
import psycopg
import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))   # run from backend/: python -I analysis/<script>.py
import config
import oldgames
import playoff_odds as po

CACHE = Path(__file__).resolve().parent.parent / "data" / "playoff_backtest.json"
FIRST, LAST = 2006, 2025                  # a season is named by the year its playoffs end
FULL_FORMAT = [y for y in range(2014, 2026) if y not in (2020, 2021)]   # divisions + wild cards, all teams in a normal season
EPS = 0.001


def get(url):
    for wait in (2, 10, 30):
        r = requests.get(url, timeout=30)
        if r.status_code == 200:
            return r.json()
        time.sleep(wait)
    raise SystemExit(f"{url}: HTTP {r.status_code}")


def season_games(conn, year):
    """[(date, home, away, hs, as)] for the regular season that ended in `year`, codes as today's franchises."""
    sid = (year - 1) * 10000 + year
    rows = conn.execute("SELECT game_date, home, away, home_score, away_score FROM game_hist WHERE season_id = %s", (sid,)).fetchall()
    if not rows:
        rows = conn.execute(
            "SELECT game_date, team, opponent, goals_for, goals_against FROM team_game_hist WHERE season_id = %s AND is_home AND team IS NOT NULL",
            (sid,)).fetchall()
    return sorted((d, oldgames.current_code(h), oldgames.current_code(a), hs, a_s) for d, h, a, hs, a_s in rows)


def standings_row(t):
    return {"abbrev": oldgames.current_code(t["teamAbbrev"]["default"]), "name": t["teamName"]["default"], "conference": t.get("conferenceName"),
            "division": t.get("divisionName"), "games_played": t["gamesPlayed"], "points": t["points"],
            "reg_wins": t.get("regulationWins", 0), "goal_diff": t["goalDifferential"]}


def fetch():
    out = {}
    with psycopg.connect(config.DATABASE_URL) as conn:
        for year in range(FIRST, LAST + 1):
            games = season_games(conn, year)
            dates = [g[0] for g in games]
            when = {"end": dates[-1]}
            for name, share in (("q1", 0.25), ("q2", 0.5)):
                when[name] = dates[int(len(dates) * share)]
            print(year, {k: str(v) for k, v in when.items()})
            bracket = get(f"{config.WEB_API}/playoff-bracket/{year}")["series"]
            series = []
            for s in bracket:
                if s["playoffRound"] < 1 or "topSeedTeam" not in s or "bottomSeedTeam" not in s:
                    continue
                series.append({"round": s["playoffRound"], "top": oldgames.current_code(s["topSeedTeam"]["abbrev"]),
                               "bottom": oldgames.current_code(s["bottomSeedTeam"]["abbrev"]),
                               "top_wins": s["topSeedWins"], "bottom_wins": s["bottomSeedWins"]})
            stand = {}
            for name, d in when.items():
                stand[name] = [standings_row(t) for t in get(f"{config.WEB_API}/standings/{d}")["standings"]]
                time.sleep(1)
            out[str(year)] = {"dates": {k: str(v) for k, v in when.items()}, "series": series, "standings": stand}
            time.sleep(1)
    CACHE.write_text(json.dumps(out))
    return out


def load():
    if "fetch" in sys.argv or not CACHE.exists():
        return fetch()
    return json.loads(CACHE.read_text())


# --- Scores ----------------------------------------------------------------------------------------------

def brier(p, y):
    return (p - y) ** 2


def logloss(p, y):
    p = min(1 - EPS, max(EPS, p))
    return -math.log(p if y else 1 - p)


def mean(xs):
    xs = list(xs)
    return sum(xs) / len(xs) if xs else float("nan")


def bins(pairs, edges):
    out = []
    for lo, hi in zip(edges, edges[1:]):
        rows = [(p, y) for p, y in pairs if lo <= p < hi]
        if rows:
            out.append((lo, hi, len(rows), mean(p for p, _ in rows), mean(y for _, y in rows)))
    return out


def show_bins(pairs, edges, label):
    print(f"  {label:<14}{'n':>5}{'said':>8}{'happened':>10}")
    for lo, hi, n, said, rate in bins(pairs, edges):
        print(f"  {lo:>4.0%}-{hi:<8.0%}{n:>5}{said:>8.1%}{rate:>10.1%}")


# --- 1. Series --------------------------------------------------------------------------------------------

def series_rows(data):
    """[{year, round, p_top, y}]: the chance the top seed wins, from the end-of-season ratings, and whether it did."""
    rows = []
    for year, d in data.items():
        teams = {t["abbrev"]: t for t in d["standings"]["end"]}
        rating = po.team_ratings([{"abbrev": a, **t} for a, t in teams.items()])
        for s in d["series"]:
            if s["top"] not in rating or s["bottom"] not in rating:
                continue
            rows.append({"year": int(year), "round": s["round"], "top": s["top"], "bottom": s["bottom"],
                         "rt": rating[s["top"]], "rb": rating[s["bottom"]], "y": 1 if s["top_wins"] == 4 else 0})
    return rows


def p_top(rt, rb, scale, home):
    """Series win chance for the team with home ice, best of seven, the model's game win chance at the given scale and home edge."""
    old = po.LOGIT_SCALE, po.HOME_EDGE
    po.LOGIT_SCALE, po.HOME_EDGE = scale, home
    try:
        return float(po.series_matrix(np.array([rt, rb]))[0, 1])
    finally:
        po.LOGIT_SCALE, po.HOME_EDGE = old


def series_report(rows):
    print(f"\n=== 1. Series ({len(rows)} best-of-sevens, {rows[0]['year']}-{rows[-1]['year']}) ===")
    p = [p_top(r["rt"], r["rb"], po.LOGIT_SCALE, po.HOME_EDGE) for r in rows]
    y = [r["y"] for r in rows]
    base = mean(y)
    print(f"top seed won {base:.1%}; the model said {mean(p):.1%} on average (picked the winner "
          f"{mean(1.0 if (pi > 0.5) == bool(yi) else 0.0 for pi, yi in zip(p, y)):.1%})")
    print(f"Brier: model {mean(brier(a, b) for a, b in zip(p, y)):.4f}, coin flip 0.2500, "
          f"top seed's rate {mean(brier(base, b) for b in y):.4f} (in-sample);  log loss: model {mean(logloss(a, b) for a, b in zip(p, y)):.4f}, coin 0.6931")
    show_bins(list(zip(p, y)), (0, 0.5, 0.6, 0.7, 0.8, 1.01), "model said")
    # does a hard-to-beat baseline (the better regular-season record at home, no model) do as well? just home ice, no strength
    p_home_only = [p_top(0, 0, po.LOGIT_SCALE, po.HOME_EDGE)] * len(rows)
    print(f"home ice alone: Brier {mean(brier(a, b) for a, b in zip(p_home_only, y)):.4f}")

    print("\nRefit of the per-game strength scale (0 = every series a home-ice coin flip; 0.9 = the regular-season model):")
    train = [r for r in rows if r["year"] <= 2015]
    test = [r for r in rows if r["year"] > 2015]
    print(f"  {'scale':>6}{'all':>9}{'2006-15':>10}{'2016-25':>10}   (log loss; lower is better)")
    best = None
    for scale in (0.0, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 1.2):
        ll = lambda rs: mean(logloss(p_top(r["rt"], r["rb"], scale, po.HOME_EDGE), r["y"]) for r in rs)
        a, b, c = ll(rows), ll(train), ll(test)
        print(f"  {scale:>6.1f}{a:>9.4f}{b:>10.4f}{c:>10.4f}")
        if best is None or b < best[1]:
            best = (scale, b, c)
    print(f"  best on 2006-15: {best[0]} (then {best[2]:.4f} on 2016-25, against {mean(logloss(p_top(r['rt'], r['rb'], po.LOGIT_SCALE, po.HOME_EDGE), r['y']) for r in test):.4f} at the current {po.LOGIT_SCALE})")
    return best[0]


# --- 2 and 3. Cup odds and making the playoffs -------------------------------------------------------------

def cup_report(data, scale):
    print("\n=== 2. Cup odds from the actual field (end-of-season standings) ===")
    reach = {k: [] for k in ("round2", "conf_final", "final", "cup")}
    champs = []
    for year in FULL_FORMAT:
        d = data[str(year)]
        teams = d["standings"]["end"]
        series = d["series"]
        field = {s["top"] for s in series if s["round"] == 1} | {s["bottom"] for s in series if s["round"] == 1}
        final = [s for s in series if s["round"] == 4]
        champ = (final[0]["top"] if final[0]["top_wins"] == 4 else final[0]["bottom"]) if final else None
        won = {r: {s["top"] if s["top_wins"] == 4 else s["bottom"] for s in series if s["round"] == r} for r in (1, 2, 3, 4)}
        out = po.simulate(teams, [], sims=1)       # nothing left to play, so the field and seeds are the standings'
        sim_field = {a for a, o in out.items() if o["make_playoffs"] > 0.5}
        if sim_field != field:
            print(f"  {year}: the standings-based field differs from the real one by {sorted(sim_field ^ field)}; using the real field anyway is not possible, skipping")
            continue
        for a in field:
            for key, r in (("round2", 1), ("conf_final", 2), ("final", 3), ("cup", 4)):
                reach[key].append((out[a][key], 1 if a in won[r] else 0))
        champs.append((year, champ, out[champ]["cup"], sorted(field, key=lambda a: -out[a]["cup"]).index(champ) + 1))
    print(f"  {'season':<8}{'champion':<10}{'chance given':>14}{'rank of 16':>12}")
    for year, champ, p, rank in champs:
        print(f"  {year:<8}{champ:<10}{p:>14.1%}{rank:>12}")
    print(f"  average chance given to the champion {mean(p for _, _, p, _ in champs):.1%} (a 1-in-16 guess gives 6.2%); "
          f"favourite won {sum(1 for *_, r in champs if r == 1)} of {len(champs)}, champion in the model's top 4: {sum(1 for *_, r in champs if r <= 4)} of {len(champs)}")
    print(f"  average log score of the champion: model {mean(-math.log(max(p, EPS)) for _, _, p, _ in champs):.3f}, 1-in-16 guess {math.log(16):.3f}")
    for key, base in (("round2", 0.5), ("conf_final", 0.25), ("final", 0.125), ("cup", 0.0625)):
        pairs = reach[key]
        print(f"  {key:<11} n={len(pairs):<4} Brier model {mean(brier(p, y) for p, y in pairs):.4f}, flat {base:.1%} guess {mean(brier(base, y) for _, y in pairs):.4f}")
    edges = (0, 0.02, 0.05, 0.1, 0.2, 0.4, 1.01)
    show_bins(reach["cup"], edges, "Cup chance")


def make_report(data):
    print("\n=== 3. Making the playoffs, simulated from a quarter and half of the way through the season ===")
    with psycopg.connect(config.DATABASE_URL) as conn:
        seasons = {y: season_games(conn, y) for y in FULL_FORMAT}
    for q, label in (("q1", "a quarter"), ("q2", "half")):
        pairs, flat = [], []
        for year in FULL_FORMAT:
            d = data[str(year)]
            when = d["dates"][q]
            teams = d["standings"][q]
            field = {s["top"] for s in d["series"] if s["round"] == 1} | {s["bottom"] for s in d["series"] if s["round"] == 1}
            remaining = [(h, a) for date, h, a, *_ in seasons[year] if str(date) > when]
            out = po.simulate(teams, remaining, sims=1000, seed=year)
            for t in teams:
                pairs.append((out[t["abbrev"]]["make_playoffs"], 1 if t["abbrev"] in field else 0))
        print(f"\n  from {label} of the way ({len(pairs)} team-seasons): Brier {mean(brier(p, y) for p, y in pairs):.4f} "
              f"(a flat 50% guess scores 0.2500), log loss {mean(logloss(p, y) for p, y in pairs):.4f} (flat 0.6931)")
        show_bins(pairs, (0, 0.05, 0.2, 0.4, 0.6, 0.8, 0.95, 1.01), "model said")


def cup_scores(data, scale):
    """(champion's mean log score, {stage: Brier}) for Cup odds from the actual fields at a given per-game scale."""
    old = po.LOGIT_SCALE
    po.LOGIT_SCALE = scale
    try:
        reach = {k: [] for k in ("round2", "conf_final", "final", "cup")}
        champ_logs = []
        for year in FULL_FORMAT:
            d = data[str(year)]
            series = d["series"]
            field = {s["top"] for s in series if s["round"] == 1} | {s["bottom"] for s in series if s["round"] == 1}
            won = {r: {s["top"] if s["top_wins"] == 4 else s["bottom"] for s in series if s["round"] == r} for r in (1, 2, 3, 4)}
            out = po.simulate(d["standings"]["end"], [], sims=1)
            if {a for a, o in out.items() if o["make_playoffs"] > 0.5} != field:
                continue
            for a in field:
                for key, r in (("round2", 1), ("conf_final", 2), ("final", 3), ("cup", 4)):
                    reach[key].append((out[a][key], 1 if a in won[r] else 0))
                if a in won[4]:
                    champ_logs.append(-math.log(max(out[a]["cup"], EPS)))
        return mean(champ_logs), {k: mean(brier(p, y) for p, y in v) for k, v in reach.items()}
    finally:
        po.LOGIT_SCALE = old


def make_scores(data, seasons, q, scale, prior):
    old = po.LOGIT_SCALE, po.PRIOR_GAMES
    po.LOGIT_SCALE, po.PRIOR_GAMES = scale, prior
    try:
        pairs = []
        for year in FULL_FORMAT:
            d = data[str(year)]
            when = d["dates"][q]
            field = {s["top"] for s in d["series"] if s["round"] == 1} | {s["bottom"] for s in d["series"] if s["round"] == 1}
            remaining = [(h, a) for date, h, a, *_ in seasons[year] if str(date) > when]
            out = po.simulate(d["standings"][q], remaining, sims=600, seed=year)
            pairs += [(out[t["abbrev"]]["make_playoffs"], 1 if t["abbrev"] in field else 0) for t in d["standings"][q]]
        return mean(brier(p, y) for p, y in pairs), mean(logloss(p, y) for p, y in pairs)
    finally:
        po.LOGIT_SCALE, po.PRIOR_GAMES = old


def sweeps(data):
    print("\n=== 4. What if the knobs were different? ===")
    print("Cup odds by per-game scale for the series (Brier by stage, lower is better; flat guesses: 0.2500 / 0.1875 / 0.1094 / 0.0586):")
    print(f"  {'scale':>6}{'champion log score':>20}{'round2':>9}{'conf final':>12}{'final':>8}{'cup':>8}   (1-in-16 guess scores {math.log(16):.3f} for the champion)")
    for scale in (0.9, 0.7, 0.5, 0.3, 0.0):
        champ, b = cup_scores(data, scale)
        print(f"  {scale:>6.1f}{champ:>20.3f}{b['round2']:>9.4f}{b['conf_final']:>12.4f}{b['final']:>8.4f}{b['cup']:>8.4f}")
    with psycopg.connect(config.DATABASE_URL) as conn:
        seasons = {y: season_games(conn, y) for y in FULL_FORMAT}
    print("\nMaking the playoffs by regular-season knobs: Brier and log loss from a quarter / half of the way (now: scale 0.9, prior 25 games):")
    print(f"  {'scale':>6}{'prior':>7}{'quarter Brier':>15}{'log loss':>10}{'half Brier':>13}{'log loss':>10}")
    for scale, prior in ((0.9, 25), (0.7, 25), (0.5, 25), (0.9, 40), (0.7, 40), (0.5, 40), (0.7, 60), (0.5, 60)):
        a = make_scores(data, seasons, "q1", scale, prior)
        b = make_scores(data, seasons, "q2", scale, prior)
        print(f"  {scale:>6.1f}{prior:>7}{a[0]:>15.4f}{a[1]:>10.4f}{b[0]:>13.4f}{b[1]:>10.4f}")


def main():
    data = load()
    rows = series_rows(data)
    best = series_report(rows)
    cup_report(data, best)
    make_report(data)
    sweeps(data)


if __name__ == "__main__":
    main()
