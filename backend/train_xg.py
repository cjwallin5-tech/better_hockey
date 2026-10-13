"""Fit the expected-goals model on a saved season of shots (see train_xg_fetch.py).

A logistic regression on unblocked, non-empty-net attempts using shot location, shot type,
rebound and strength. Writes xg_model.json (coefficients only, so scoring needs no ML library)
and prints held-out calibration so the model can be judged before it's used.

Usage: python train_xg.py data/shots_2025.jsonl.gz
"""
import gzip, json, math, random, sys

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import log_loss, roc_auc_score

import shots

TYPES = ["wrist", "snap", "slap", "backhand", "tip-in", "deflected", "wrap-around", "poke", "bat", "between-legs", "cradle"]


def row_features(s):
    """Feature vector for one shot dict (shared with scoring via shots.xg)."""
    return shots.features(s)


def main(path):
    games = []
    with gzip.open(path, "rt") as f:
        for line in f:
            rec = json.loads(line)
            games.append(rec["shots"])
    random.Random(7).shuffle(games)
    split = int(len(games) * 0.8)
    train_games, test_games = games[:split], games[split:]

    def build(gs):
        X, y = [], []
        for g in gs:
            for s in g:
                if s["kind"] == "block" or s["empty_net"] or s["x"] is None or s["strength"] is None:
                    continue
                X.append(shots.features(s))
                y.append(1 if s["kind"] == "goal" else 0)
        return np.array(X), np.array(y)

    Xtr, ytr = build(train_games)
    Xte, yte = build(test_games)
    print(f"train {len(ytr):,} attempts ({ytr.mean():.4f} goal rate), test {len(yte):,}")

    model = LogisticRegression(C=1.0, max_iter=2000)
    model.fit(Xtr, ytr)
    p = model.predict_proba(Xte)[:, 1]
    base = np.full_like(p, ytr.mean())
    print(f"held-out log loss {log_loss(yte, p):.4f} (baseline {log_loss(yte, base):.4f}), AUC {roc_auc_score(yte, p):.3f}")
    print(f"held-out goals {yte.sum()} vs sum of xG {p.sum():.1f}")
    order = np.argsort(p)
    print("calibration by decile (predicted -> actual):")
    for chunk in np.array_split(order, 10):
        print(f"  {p[chunk].mean():.3f} -> {yte[chunk].mean():.3f}   (n={len(chunk)})")

    # Refit on everything for the shipped model.
    Xall = np.vstack([Xtr, Xte]); yall = np.concatenate([ytr, yte])
    final = LogisticRegression(C=1.0, max_iter=2000).fit(Xall, yall)
    json.dump({
        "features": shots.FEATURE_NAMES,
        "coef": [float(c) for c in final.coef_[0]],
        "intercept": float(final.intercept_[0]),
        "trained_on": path,
        "attempts": int(len(yall)),
        "goal_rate": float(yall.mean()),
        "holdout": {"log_loss": float(log_loss(yte, p)), "auc": float(roc_auc_score(yte, p))},
    }, open("xg_model.json", "w"), indent=1)
    print("wrote xg_model.json")


if __name__ == "__main__":
    main(sys.argv[1])
