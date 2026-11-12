"""Checks our Triple Gold Club members against the list on Wikipedia (which follows the IIHF's own roll), and prints every difference:

    cd backend && .venv/bin/python analysis/check_triple_gold.py

Run it after `ingest.py backfill-international` has finished (it says how many players are still uncollected). Members we list that
Wikipedia does not, and members Wikipedia lists that we miss, are each worth a look: the first usually means a medal or a country name is
mismatched in internationals.py, the second a player the NHL's page lacks an award or tournament row for. The year each person completed
the club is compared too."""
import re
import sys
import unicodedata
from pathlib import Path

import psycopg
import requests
from psycopg.rows import dict_row

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import api  # noqa: E402
import config  # noqa: E402
import internationals  # noqa: E402

UA = "NHLStatsResultsBuilder/1.0 (a personal hockey stats project; reads public member lists)"


def norm(name):
    return re.sub(r"[^a-z]+", " ", unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower()).strip()


def wikipedia_members():
    """{normalised name: year membership was gained} for the players on the Triple Gold Club page."""
    r = requests.get("https://en.wikipedia.org/w/api.php", headers={"User-Agent": UA}, timeout=30,
                     params={"action": "parse", "page": "Triple Gold Club", "prop": "wikitext", "format": "json", "redirects": 1})
    text = r.json()["parse"]["wikitext"]["*"]
    section = text[text.index("===Players==="):text.index("===Coaches===")]
    out = {}
    for row in re.split(r"\n\|-", section):
        who = re.search(r"\{\{sortname\|([^|}]+)\|([^|}]+)", row)
        year = re.search(r"\{\{dts\|[^}]*?(\d{4})\|", row)
        if who and year:
            key = norm(f"{who.group(1)} {who.group(2)}")
            out[internationals.ROLL_ALIASES.get(key, key)] = int(year.group(1))
    return out


def main():
    wiki = wikipedia_members()
    with psycopg.connect(config.DATABASE_URL, row_factory=dict_row) as conn:
        names = {r["player_id"]: r["name"] for r in conn.execute(
            "SELECT player_id, name FROM career_skater WHERE game_type = 2 UNION SELECT player_id, name FROM career_goalie WHERE game_type = 2")}
        done = {names[r["player_id"]] for r in conn.execute("SELECT player_id FROM player_international_fetched WHERE awards_done") if r["player_id"] in names}
    with psycopg.connect(config.DATABASE_URL, row_factory=dict_row) as conn:
        members, fetched, total = api._triple_gold_members(conn, with_official=False)   # what the NHL's data alone gives
    club = {"coverage": {"fetched": fetched, "total": total}}
    ours = {norm(m["name"]): m for m in members}
    collected = {norm(n) for n in done}
    print(f"Wikipedia lists {len(wiki)} players; we list {len(ours)}; {club['coverage']['fetched']} of {club['coverage']['total']} players collected")
    print("\nWe list, Wikipedia does not:")
    for n in sorted(set(ours) - set(wiki)):
        m = ours[n]
        print(f"  {m['name']}: Cup {m['cup']}, Olympics {m['olympics']}, Worlds {m['worlds']} (completed {m['completed']})")
    print("\nWikipedia lists, collected, but we do not:")
    for n in sorted((set(wiki) & collected) - set(ours)):
        print(f"  {n} (Wikipedia: {wiki[n]})")
    known = {norm(n) for n in names.values()}
    print("\nOn the roll but matching no player in our data (add a ROLL_ALIASES entry in internationals.py):")
    for n in sorted(set(wiki) - known):
        print(f"  {n}")
    print("\nWikipedia lists, not collected yet:", len(set(wiki) - collected))
    print("\nBoth list them, but the year completed differs:")
    for n in sorted(set(wiki) & set(ours)):
        if wiki[n] != ours[n]["completed"]:
            print(f"  {ours[n]['name']}: we say {ours[n]['completed']}, Wikipedia {wiki[n]}")


if __name__ == "__main__":
    main()
