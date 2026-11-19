"""Where a player finished among all NHL skaters in each finished season: the seasons they led the league in goals, assists or points, and how
many times they were in the top 5 and top 10. A rank is 1 plus the number of skaters with more, so a tie shares a place (and two players can
both have led the league). The current season is left out until it ends."""

STATS = (("points", "Points"), ("goals", "Goals"), ("assists", "Assists"))
TOP = 10


def summarize(rows):
    """rows: [{season_id, goals, assists, points, goals_rank, assists_rank, points_rank}], one per season.
    Returns one entry per stat the player ever finished in the top TOP for: {stat, label, led: [{season_id, value}] (oldest first),
    top5, top10 (counts, including the seasons they led)}."""
    out = []
    for stat, label in STATS:
        seasons = sorted(({"season_id": r["season_id"], "value": r[stat], "rank": r[f"{stat}_rank"]} for r in rows
                          if r[stat] > 0 and r[f"{stat}_rank"] <= TOP), key=lambda s: s["season_id"])
        if seasons:
            out.append({"stat": stat, "label": label,
                        "led": [{"season_id": s["season_id"], "value": s["value"]} for s in seasons if s["rank"] == 1],
                        "top5": sum(1 for s in seasons if s["rank"] <= 5), "top10": len(seasons)})
    return out
