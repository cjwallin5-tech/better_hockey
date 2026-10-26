"""Linemate chemistry: does a player's team get more of the good chances with a given teammate than without?

For a pair of skaters we know, at 5v5, the expected goals (xG, our own model) for and against while they were on the ice
together (pair_game), and each player's own 5v5 totals (skater_game_onice). Subtracting gives how each did apart. The
chemistry figure is from the point of view of the player whose page it is: the lift is the pair's xG share together minus
that player's own xG share when playing without the teammate (50% is an even share of the chances). The teammate's own lift is
given too, because a pairing that helps a star but lifts nobody else, or the reverse, looks different from one that helps both.
xG per 60 minutes for and against is shown beside it, since "raises his xG" can be a better offense, a better defense, or both.
(An earlier version pooled both players' time apart; that made any star-with-a-weaker-player pair look like a big boost,
because the weaker player's time alone drags the pooled figure down.)

How sure we are: the lift is a difference of two shares, so its noise falls with the number of shot attempts behind each.
The standard error treats each attempt as an even coin flip, a rough but standard approximation (xG weights make real shares
noisier, so read it as a floor on the noise). The verdict needs MIN_TOGETHER_SEC of time together and then labels |z| below
1 "no clear effect", 1 to 2 "slight" and 2 or more "clear".

What it does not know: why. Apart time is usually with other linemates, against other opponents, from other zone starts and
on other special-teams mixes, so a lift can come from usage rather than the pairing, and a player who is almost always with
this teammate has little apart time to compare against (the verdict then stays quiet). Treat a clear verdict as a clue to
look at, not a measurement of fit.
"""
import math

MIN_TOGETHER_SEC = 30 * 60
XG_LINES_VERSION = 3   # games processed at this lines version or later have expected goals on their pair and line rows (ingest.LINES_VERSION)
SLIGHT_Z = 1.0
CLEAR_Z = 2.0


def share(for_, against):
    """for / (for + against), or None when both are 0 or missing."""
    if for_ is None or against is None or for_ + against <= 0:
        return None
    return for_ / (for_ + against)


def per60(value, seconds):
    return None if value is None or not seconds or seconds <= 0 else value / seconds * 3600


def verdict(lift, z, together_sec):
    """(label, strength): strength is 'clear', 'slight' or 'none'; the label says boost, drag or no clear effect. None when
    there isn't enough time together or the lift can't be measured."""
    if lift is None or z is None or together_sec < MIN_TOGETHER_SEC:
        return None
    if abs(z) < SLIGHT_Z:
        return "no clear effect", "none"
    strength = "clear" if abs(z) >= CLEAR_Z else "slight"
    return (f"{strength} boost" if lift > 0 else f"{strength} drag"), strength


def _lift_z(share_together, share_apart, n_together, n_apart):
    """(lift, z) for a share together against a share apart, from the attempts behind each; (None, None) if unmeasurable."""
    if share_together is None or share_apart is None:
        return None, None
    lift = share_together - share_apart
    if n_together <= 0 or n_apart <= 0:
        return lift, None
    return lift, lift / math.sqrt(0.25 / n_together + 0.25 / n_apart)


def pair_view(together, mine, partner):
    """Chemistry figures for one pair from the viewpoint of `mine`.

    together: {toi, cf, ca, xgf, xga} for the pair (xgf and xga None when not stored for every game).
    mine, partner: each player's own 5v5 totals {toi, cf, ca, xgf, xga}, partner None when unknown.
    Returns xG per 60 and xG share together and apart (the player's own time without the teammate), the lift and its z for
    the player and for the teammate, and the verdict on the player's lift. The Corsi lift stands in when xG isn't stored."""
    def apart(total):
        if not total or any(total.get(k) is None for k in ("toi", "cf", "ca")):
            return None
        a = {k: total[k] - together[k] for k in ("toi", "cf", "ca")}
        a["xgf"] = None if total.get("xgf") is None or together.get("xgf") is None else total["xgf"] - together["xgf"]
        a["xga"] = None if total.get("xga") is None or together.get("xga") is None else total["xga"] - together["xga"]
        return a

    mine_apart, partner_apart = apart(mine), apart(partner)
    n_t = together["cf"] + together["ca"]
    xg_t, cf_t = share(together.get("xgf"), together.get("xga")), share(together["cf"], together["ca"])

    def views(a):
        """(xG share apart, xG lift, xG z, Corsi share apart, Corsi lift, Corsi z) for one player's time apart."""
        if not a:
            return (None,) * 6
        n_a = a["cf"] + a["ca"]
        xg_a = share(a["xgf"], a["xga"]) if a["xgf"] is not None and a["xga"] is not None else None
        cf_a = share(a["cf"], a["ca"])
        xl, xz = _lift_z(xg_t, xg_a, n_t, n_a)
        cl, cz = _lift_z(cf_t, cf_a, n_t, n_a)
        return xg_a, xl, xz, cf_a, cl, cz

    xg_a, xg_lift, xg_z, cf_a, cf_lift, cf_z = views(mine_apart)
    p_xg_a, p_xg_lift, p_xg_z, p_cf_a, p_cf_lift, p_cf_z = views(partner_apart)
    out = {"xgf60_together": per60(together.get("xgf"), together["toi"]), "xga60_together": per60(together.get("xga"), together["toi"]),
           "xg_share_together": xg_t, "xgf60_apart": None, "xga60_apart": None, "xg_share_apart": xg_a,
           "xg_lift": xg_lift, "xg_z": xg_z, "cf_share_together": cf_t, "cf_share_apart": cf_a, "cf_lift": cf_lift,
           "partner_xg_share_apart": p_xg_a, "partner_xg_lift": p_xg_lift, "partner_cf_lift": p_cf_lift}
    if mine_apart:
        out["xgf60_apart"] = per60(mine_apart["xgf"], mine_apart["toi"])
        out["xga60_apart"] = per60(mine_apart["xga"], mine_apart["toi"])
    # xG is the headline; fall back to the Corsi lift (with the same noise estimate) when xG isn't stored yet
    lift, z, out["basis"] = xg_lift, xg_z, "xg"
    plift, pz = p_xg_lift, p_xg_z
    if lift is None and cf_lift is not None:
        lift, z, out["basis"], plift, pz = cf_lift, cf_z, "corsi", p_cf_lift, p_cf_z
    v = verdict(lift, z, together["toi"])
    pv = verdict(plift, pz, together["toi"])
    out["lift"], out["z"] = lift, z
    out["verdict"], out["strength"] = v if v else (None, None)
    out["partner_lift"], out["partner_z"] = plift, pz
    out["partner_verdict"] = pv[0] if pv else None
    return out


def best_and_worst(rows):
    """The best and worst fits among rated rows (those with a verdict and a |z| of at least SLIGHT_Z): (best, worst), each a
    row or None. Only a boost can be best and only a drag can be worst."""
    rated = [r for r in rows if r.get("strength") in ("clear", "slight")]
    best = max((r for r in rated if r["lift"] > 0), key=lambda r: r["z"], default=None)
    worst = min((r for r in rated if r["lift"] < 0), key=lambda r: r["z"], default=None)
    return best, worst
