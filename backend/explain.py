"""Why a skater's season looks the way it does: the biggest things that changed, in plain words and in points.

Each finding is measured against the player's own last season (shot volume, shot quality, ice time, a new team) or
against what their shots and teammates' shots predict (finishing and assist luck), and priced in goals or points over a
full season (`games` games) when it can be, so the findings can be ranked and added up. Two groups:
  luck   results running above or below what the chances support: the player's finishing against the quality of their
         shots, and teammates scoring more or fewer goals than their shots predict (which moves a player's assists).
         These tend to fade, see luck.py.
  real   things the player controls or is given: how many shots they take, how good the shots are, how much they play,
         how much power-play time they get. These tend to last, at least while the role does.
The prices are estimates from simple rates, not a model of the player: they say which factor is biggest and roughly how
big, and a factor's price can overlap with another's (more ice time is also more shots). The recent-role finding compares
the last few games with the earlier ones this season, so it is a different window from the rest.

What it does not know: injuries, a coach's changes it can't see in ice time, or why a line changed.
"""
MIN_GP = 5               # games this season before anything is said about shot volume, quality or time
MIN_LAST_GP = 20         # games last season for it to count as a baseline
MIN_ATTEMPTS = 30        # shot attempts this season before shot quality is compared
CHANGE_PCT = 0.15        # a shot volume or quality change smaller than this is not worth a line
MIN_PRICE = 1.0          # goals or points over a season below which a factor is left out
TOI_CHANGE_SEC = 60      # ice time moves smaller than this are left out
ASSIST_MIN_PRICE = 1.5   # teammates' scoring is a noisier factor, so its bar is higher
MAX_FINDINGS = 6
EARLY_GP = 20            # fewer games than this and a season pace is mostly noise


def _mmss(sec):
    s = int(round(abs(sec)))
    return f"{s // 60}:{s % 60:02d}"


def _signed(v, digits=0):
    return f"{v:+.{digits}f}".replace("-", "−")


def _per_game(total, gp):
    return total / gp if gp else None


def finding(key, kind, direction, title, text, price=None, unit=None):
    """One finding. price: estimated goals or points over a full season (+ helps, - hurts), None when it isn't priced."""
    return {"key": key, "kind": kind, "direction": direction, "title": title, "text": text, "price": price, "unit": unit}


def finishing(f):
    lk = f.get("luck")
    if not lk or not lk.get("enough") or lk.get("diff_adj") is None or not f["gp"]:
        return None
    price = lk["diff_adj"] * f["games"] / f["gp"]
    if abs(price) < MIN_PRICE:
        return None
    d = "up" if price > 0 else "down"
    return finding(
        "finishing", "luck", d, "Finishing",
        f"{lk['goals']} goals from shots worth {lk['ixg'] * (1 + lk.get('skill', 0)):.1f} expected for a shooter of this record "
        f"({_signed(lk['diff_adj'], 1)} so far). That is {_signed(price)} goals over {f['games']} games if it keeps up, "
        f"and finishing luck tends to fade.", price, "goals")


def teammates_scoring(f):
    lk = f.get("luck")
    if not lk or not lk.get("enough") or lk.get("assist_luck") is None or not f["gp"]:
        return None
    price = lk["assist_luck"] * f["games"] / f["gp"]
    if abs(price) < ASSIST_MIN_PRICE:
        return None
    d = "up" if price > 0 else "down"
    return finding(
        "teammates", "luck", d, "Teammates' finishing",
        f"Linemates are scoring {'more' if price > 0 else 'less'} than their shots predict while this player is on the ice, "
        f"worth about {_signed(lk['assist_luck'], 1)} assists so far ({_signed(price)} over {f['games']} games). That also tends to fade.",
        price, "points")


def shot_volume(f):
    now, last = f.get("now"), f.get("last")
    if not now or not last or f["gp"] < MIN_GP or last["gp"] < MIN_LAST_GP or not last.get("attempts") or not now.get("attempts"):
        return None
    a_now, a_last = now["attempts"] / f["gp"], last["attempts"] / last["gp"]
    change = a_now / a_last - 1
    value_last = last["ixg"] / last["attempts"]   # expected goals per attempt, last season
    price = (a_now - a_last) * value_last * f["games"]
    if abs(change) < CHANGE_PCT or abs(price) < MIN_PRICE:
        return None
    return finding(
        "volume", "real", "up" if price > 0 else "down", "Shot volume",
        f"{a_now:.1f} shot attempts a game against {a_last:.1f} last season ({_signed(change * 100)}%), worth about "
        f"{_signed(price)} goals over {f['games']} games at last season's shot quality.", price, "goals")


def shot_quality(f):
    now, last = f.get("now"), f.get("last")
    if not now or not last or f["gp"] < MIN_GP or last["gp"] < MIN_LAST_GP or (now.get("attempts") or 0) < MIN_ATTEMPTS or not last.get("attempts"):
        return None
    q_now, q_last = now["ixg"] / now["attempts"], last["ixg"] / last["attempts"]
    change = q_now / q_last - 1
    price = (q_now - q_last) * (now["attempts"] / f["gp"]) * f["games"]
    if abs(change) < CHANGE_PCT or abs(price) < MIN_PRICE:
        return None
    return finding(
        "quality", "real", "up" if price > 0 else "down", "Shot quality",
        f"{q_now:.3f} expected goals per attempt against {q_last:.3f} last season ({_signed(change * 100)}%): "
        f"{'better' if price > 0 else 'worse'} chances, worth about {_signed(price)} goals over {f['games']} games.", price, "goals")


def ice_time(f):
    now, last = f.get("now"), f.get("last")
    if not now or not last or f["gp"] < MIN_GP or last["gp"] < MIN_LAST_GP or not now.get("toi_sec") or not last.get("toi_sec"):
        return None
    delta = now["toi_sec"] - last["toi_sec"]
    per_minute = (last["points"] / last["gp"]) / (last["toi_sec"] / 60)   # last season's points per minute played
    price = delta / 60 * per_minute * f["games"]
    if abs(delta) < TOI_CHANGE_SEC or abs(price) < MIN_PRICE:
        return None
    return finding(
        "ice_time", "real", "up" if delta > 0 else "down", "Ice time",
        f"{_mmss(now['toi_sec'])} a game against {_mmss(last['toi_sec'])} last season ({'+' if delta > 0 else '−'}{_mmss(delta)}), worth "
        f"about {_signed(price)} points over {f['games']} games at last season's scoring per minute. "
        f"(Some of this is already in the shot volume.)", price, "points")


def recent_role(f):
    r = f.get("role")
    if not r or not (r.get("pp_change") or r.get("ev_change")):
        return None
    parts, price = [], None
    if r.get("pp_change"):
        delta = r["pp"] - r["pp_base"]
        parts.append(f"{r['pp_label']}: {_mmss(r['pp_base'])} to {_mmss(r['pp'])} of power play a game")
        rate = f.get("pp_points_per60")
        if rate:
            price = delta / 3600 * rate * f["games"]
    if r.get("ev_change"):
        parts.append(f"{'more' if r['ev_change'] == 'up' else 'less'} even-strength time ({_mmss(r['ev_base'])} to {_mmss(r['ev'])} a game)")
    direction = "up" if (r.get("pp_change") or r.get("ev_change")) and r.get("direction") != "down" else "down"
    text = f"Last {r['window']} games against the earlier ones: " + "; ".join(parts) + "."
    if price is not None:
        text += f" The power-play part is worth about {_signed(price)} points over {f['games']} games at this player's power-play rate."
    return finding("role", "real", direction, "Recent role", text, price if price is not None and abs(price) >= MIN_PRICE else None,
                   "points" if price is not None else None)


def team_change(f):
    last = f.get("last")
    if not last or not last.get("team") or not f.get("team") or last["team"].split(",")[-1] == f["team"].split(",")[-1]:
        return None
    return finding("team", "real", "neutral", "New team",
                   f"Played for {last['team'].split(',')[-1]} last season and for {f['team'].split(',')[-1]} now, so the role, line and power play are all new.")


def linemates(f):
    lm = f.get("linemates")
    if not lm or not lm.get("season"):
        return None
    season = lm["season"][:2]
    recent = (lm.get("recent") or [])[:2]
    names = lambda ps: " and ".join(p["name"] for p in ps)
    ppg = lambda ps: sum(p["ppg"] for p in ps if p.get("ppg") is not None) / max(1, sum(1 for p in ps if p.get("ppg") is not None)) if ps else None
    if recent and {p["id"] for p in recent} != {p["id"] for p in season} and lm.get("recent_games", 0) >= 3:
        text = (f"Over the last {lm['recent_games']} games, the most common linemates are {names(recent)}; "
                f"for the season so far it is {names(season)}.")
        better = (ppg(recent) or 0) - (ppg(season) or 0)
        d = "up" if better > 0.15 else "down" if better < -0.15 else "neutral"
        return finding("linemates", "real", d, "Linemates", text)
    top = ppg(season)
    if top is not None and top >= 1.1:
        return finding("linemates", "real", "up", "Linemates", f"Spends most of the 5v5 time with {names(season)}, who are scoring {top:.1f} points a game between them.")
    return None


FINDERS = (finishing, teammates_scoring, shot_volume, shot_quality, ice_time, recent_role, team_change, linemates)


def explain(f):
    """f: the player's facts (see explain_db.facts). Returns {headline, pace, last_pace, change, luck_total, real_total,
    findings}; findings are priced ones first (largest first), then the unpriced ones."""
    games = f["games"]
    pace = _per_game(f["points"], f["gp"])
    pace = pace * games if pace is not None else None
    last = f.get("last")
    last_pace = _per_game(last["points"], last["gp"]) * games if last and last.get("gp", 0) >= MIN_LAST_GP else None
    found = [x for x in (fn(f) for fn in FINDERS) if x]
    found.sort(key=lambda x: (x["price"] is None, -abs(x["price"] or 0)))
    found = found[:MAX_FINDINGS]
    luck_total = sum(x["price"] for x in found if x["kind"] == "luck" and x["price"] is not None)
    real_total = sum(x["price"] for x in found if x["kind"] == "real" and x["price"] is not None)
    change = pace - last_pace if pace is not None and last_pace is not None else None
    unexplained = change - luck_total - real_total if change is not None else None
    return {"games": games, "pace": pace, "last_pace": last_pace, "change": change,
            "luck_total": luck_total, "real_total": real_total, "unexplained": unexplained,
            "early": f["gp"] < EARLY_GP, "findings": found,
            "headline": headline(f["name"], pace, last_pace, change, luck_total, real_total, unexplained, found)}


def headline(name, pace, last_pace, change, luck_total, real_total, unexplained, found):
    if pace is None:
        return f"{name} has no games yet this season."
    if not found:
        return (f"{name} is on pace for {pace:.0f} points" + (f", against {last_pace:.0f} last season" if last_pace is not None else "")
                + ". Nothing stands out: shot volume, shot quality, ice time and finishing are all close to normal.")
    base = f"{name} is on pace for {pace:.0f} points"
    if last_pace is not None:
        base += f", {'up' if change >= 0 else 'down'} {abs(change):.0f} from {last_pace:.0f} last season"
    base += "."
    if change is not None and (luck_total or real_total):
        base += (f" Of the {_signed(change)}, about {_signed(luck_total)} is results running {'above' if luck_total >= 0 else 'below'} what the "
                 f"chances support, {_signed(real_total)} is real change in shots, ice time and role, and {_signed(unexplained)} is left unexplained.")
    return base
