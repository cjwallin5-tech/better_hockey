"""Builds backend/data/international_results.json: who won gold, silver and bronze at each men's international tournament that matters to
NHL players, by country. Run it again after a tournament ends:

    cd backend && .venv/bin/python analysis/fetch_international_results.py

The Olympics, World Championship and World Junior lists are read from Wikipedia's medal tables (text under CC BY-SA 4.0). The three small
NHL-run tournaments (Canada Cup, World Cup of Hockey, 4 Nations Face-Off) have no medal table, only a champion and a runner-up per
edition, so those are written out below. Read the JSON before committing it: the script prints every edition it found, and refuses to
write anything if a table has gone missing or changed shape.

Countries are three-letter codes as Wikipedia's hockey templates use them (CAN, USA, URS, TCH ...); `countries` in the file gives each
code a display name. Matching a player's team name to a code lives in internationals.py."""
import json
import re
import sys
import unicodedata
from datetime import date
from pathlib import Path

import requests

OUT = Path(__file__).resolve().parent.parent / "data" / "international_results.json"
API = "https://en.wikipedia.org/w/api.php"
UA = "NHLStatsResultsBuilder/1.0 (a personal hockey stats project; reads public medal tables)"

COUNTRIES = {
    "CAN": "Canada", "USA": "United States", "SWE": "Sweden", "FIN": "Finland", "CZE": "Czechia", "TCH": "Czechoslovakia",
    "URS": "Soviet Union", "RUS": "Russia", "EUN": "Unified Team", "CIS": "CIS", "GBR": "Great Britain", "GER": "Germany",
    "FRG": "West Germany", "GDR": "East Germany", "SUI": "Switzerland", "SVK": "Slovakia", "BLR": "Belarus", "LAT": "Latvia",
    "NOR": "Norway", "DEN": "Denmark", "ITA": "Italy", "AUT": "Austria", "POL": "Poland", "FRA": "France", "BEL": "Belgium",
    "HUN": "Hungary", "ROU": "Romania", "YUG": "Yugoslavia", "KAZ": "Kazakhstan", "SLO": "Slovenia", "NED": "Netherlands",
    "EUR": "Team Europe", "NAM": "Team North America",
}


def wikitext(page):
    r = requests.get(API, params={"action": "parse", "page": page, "prop": "wikitext", "format": "json", "redirects": 1},
                     headers={"User-Agent": UA}, timeout=30)
    r.raise_for_status()
    return r.json()["parse"]["wikitext"]["*"]


def rows_of(table_text):
    """The rows of a wikitext table, split on the |- markers."""
    return re.split(r"\n\|-[^\n]*", table_text)


def cells_of(row):
    """The cells of a wikitext table row, in order: header cells (!) have their attributes dropped, ordinary cells (|) are kept whole."""
    out = []
    for line in row.strip().splitlines():
        if line.startswith(("|}", "|+", "{|")):
            continue
        if line.startswith("!"):
            out.append(re.sub(r"^!(?:[^|\[]*\|)?", "", line))
        elif line.startswith("|"):
            out.append(line[1:])
    return out


# Teams whose cell is a link, not a country template (the Unified Team of 1992, the Olympic Athletes from Russia of 2018, and the
# joint Czech and Slovak team of the 1993 World Juniors, which carried on Czechoslovakia's place).
NAMED = {"Unified Team": "EUN", "Olympic Athletes from Russia": "RUS", "Czech Republic and Slovakia": "TCH"}


def code_of(cell):
    """The three-letter country code in a medal cell, or None for an empty cell. Any other cell is an error: a row this parser can't
    read must stop the build, not shift the medals along by one."""
    m = re.search(r"\{\{ih(?:-big|j)?\|([A-Z]{3})", cell)
    if m:
        return m.group(1)
    for name, code in NAMED.items():
        if name in cell:
            return code
    if not re.sub(r"[\s']", "", cell):
        return None
    raise ValueError(f"cannot read a country from: {cell[:120]!r}")


def medals_from(cells, positions, where):
    """{gold, silver, bronze} from the cells at `positions`; None when all three are empty (a future edition); an error when only some are."""
    codes = [code_of(cells[p]) if p < len(cells) else None for p in positions]
    if not any(codes):
        return None
    if not all(codes):
        raise ValueError(f"{where}: some medal cells are empty: {codes}")
    return dict(zip(("gold", "silver", "bronze"), codes))


def parse_worlds(text):
    """World Championship medalists by year. Years the Winter or Summer Olympics counted as the World Championship are left out (the
    Olympic table has them, and a player's row for those is an Olympic one)."""
    out = {}
    for row in rows_of(text):
        cells = cells_of(row)
        year = re.search(r"(\d{4})\]\]", cells[0]) if cells else None
        if not year or "cancel" in row.lower() or "{{dagger}}" in cells[0] or re.search(r"\]\]\s*\*", cells[0]):
            continue
        medals = medals_from(cells, (1, 2, 3), f"worlds {year.group(1)}")
        if medals:
            out[year.group(1)] = medals
    return out


def parse_olympics(text):
    """Men's Olympic medalists by year, from the Summary tables. The tables come in three layouts, told apart by their cell counts:
    1924-1992 list gold, silver, bronze, fourth (7 cells); 1994 on interleave the scores of the medal games (9 cells); the 1920 playoff
    has a gold, a silver and a bronze game (12 cells)."""
    start = text.index("====Summary====")
    end = text.index("====Medal table====", start)
    layouts = {7: (3, 4, 5), 9: (3, 5, 6), 12: (3, 6, 9)}
    out = {}
    for row in rows_of(text[start:end]):
        cells = cells_of(row)
        year = re.match(r"\s*(\d{4})\s*<br", cells[1]) if len(cells) > 1 else None
        if not year:
            continue
        if len(cells) not in layouts:
            raise ValueError(f"olympics {year.group(1)}: {len(cells)} cells, expected 7, 9 or 12")
        medals = medals_from(cells, layouts[len(cells)], f"olympics {year.group(1)}")
        if medals:
            out[year.group(1)] = medals
    return out


def parse_juniors(text):
    """Official World Junior Championship medalists by year (the 1974-76 invitationals are not official and are left out)."""
    out = {}
    for row in rows_of(text[text.index("===Official tournaments"):]):
        cells = cells_of(row)
        year = re.search(r"(\d{4}) World Junior[^\]]*\|(\d{4})\]\]", cells[0]) if cells else None
        if not year:
            continue
        medals = medals_from(cells, (1, 2, 3), f"juniors {year.group(2)}")
        if medals:
            out[year.group(2)] = medals
    return out


def parse_triple_gold(text):
    """The Triple Gold Club's roll of players from its Wikipedia page (which follows the IIHF's own list): name, the year the third gold
    was won, and the year of the first Olympic gold, World Championship gold and Stanley Cup (a Cup counts for the year it ended in).
    Used to cover members whose medals the NHL's own tournament history leaves out (it has no 1991 World Championship for Lidstrom)."""
    section = text[text.index("===Players==="):text.index("===Coaches===")]
    out = []
    for row in rows_of(section):
        cells = cells_of(row)
        if len(cells) < 6:
            continue
        who = re.search(r"\{\{sortname\|([^|}]+)\|([^|}]+)", cells[1])
        gained = re.search(r"\{\{dts\|[^}]*?(\d{4})\|", cells[2])
        if not (who and gained):
            continue
        firsts = []
        for cell in cells[3:6]:
            years = [int(y) for y in re.findall(r"\|(\d{4})\]\]", cell)]
            if not years:
                raise ValueError(f"triple gold: no year in {cell[:100]!r} for {who.group(1)} {who.group(2)}")
            firsts.append(min(years))
        out.append({"name": f"{who.group(1)} {who.group(2)}", "completed": int(gained.group(1)),
                    "olympics": firsts[0], "worlds": firsts[1], "cup": firsts[2]})
    return out


# Champion and runner-up only: these tournaments are a final, with no bronze-medal game. Each line below was checked against the
# editions' Wikipedia pages (Canada Cup, World Cup of Hockey, 4 Nations Face-Off).
CANADA_CUP = {"1976": ("CAN", "TCH"), "1981": ("URS", "CAN"), "1984": ("CAN", "SWE"), "1987": ("CAN", "URS"), "1991": ("CAN", "USA")}
WORLD_CUP = {"1996": ("USA", "CAN"), "2004": ("CAN", "FIN"), "2016": ("CAN", "EUR")}
FOUR_NATIONS = {"2025": ("CAN", "USA")}


def finals(table):
    return {year: {"gold": g, "silver": s} for year, (g, s) in table.items()}


def check(name, results, first, last, expect):
    """Stops the build if a table is missing years or an edition I know does not match."""
    years = sorted(int(y) for y in results)
    problems = []
    if years[0] != first or years[-1] != last:
        problems.append(f"covers {years[0]}-{years[-1]}, expected {first}-{last}")
    for year, (g, s, b) in expect.items():
        got = results.get(str(year))
        if not got or (got["gold"], got["silver"], got.get("bronze")) != (g, s, b):
            problems.append(f"{year}: got {got}, expected {g}/{s}/{b}")
    if problems:
        sys.exit(f"{name}: " + "; ".join(problems))


def main():
    olympics = parse_olympics(wikitext("Ice hockey at the Olympic Games"))
    worlds = parse_worlds(wikitext("List of IIHF World Championship medalists"))
    juniors = parse_juniors(wikitext("List of IIHF World Under-20 Championship medalists"))

    # Editions I know well; the build stops if the parsed tables disagree.
    check("olympics", olympics, 1920, 2026, {
        1920: ("CAN", "USA", "TCH"), 1924: ("CAN", "USA", "GBR"), 1980: ("USA", "URS", "SWE"), 1992: ("EUN", "CAN", "TCH"),
        1994: ("SWE", "CAN", "FIN"), 1998: ("CZE", "RUS", "FIN"), 2002: ("CAN", "USA", "RUS"), 2006: ("SWE", "FIN", "CZE"),
        2010: ("CAN", "USA", "FIN"), 2014: ("CAN", "SWE", "FIN"), 2018: ("RUS", "GER", "CAN"), 2022: ("FIN", "RUS", "SVK"),
        2026: ("USA", "CAN", "FIN")})
    check("worlds", worlds, 1930, 2026, {2019: ("FIN", "CAN", "RUS"), 2010: ("CZE", "RUS", "SWE")})
    check("juniors", juniors, 1977, 2026, {2005: ("CAN", "RUS", "CZE"), 2018: ("CAN", "SWE", "USA")})

    club = parse_triple_gold(wikitext("Triple Gold Club"))
    names = {unicodedata.normalize("NFKD", m["name"]).encode("ascii", "ignore").decode() for m in club}   # without accents
    if len(club) < 25 or not {"Sidney Crosby", "Tomas Jonsson", "Nicklas Lidstrom"} <= names:
        sys.exit(f"triple gold: parsed {len(club)} players, expected 25 or more including Crosby, Jonsson and Lidstrom")
    crosby = next(m for m in club if m["name"] == "Sidney Crosby")
    if (crosby["cup"], crosby["olympics"], crosby["worlds"], crosby["completed"]) != (2009, 2010, 2015, 2015):
        sys.exit(f"triple gold: Crosby parsed as {crosby}")

    tournaments = {
        "olympics": {"label": "Olympic Games", "tier": 1, "results": olympics},
        "worlds": {"label": "World Championship", "tier": 1, "results": worlds},
        "worldcup": {"label": "World Cup of Hockey / Canada Cup", "tier": 1, "results": {**finals(CANADA_CUP), **finals(WORLD_CUP)}},
        "fournations": {"label": "4 Nations Face-Off", "tier": 1, "results": finals(FOUR_NATIONS)},
        "juniors": {"label": "World Junior Championship", "tier": 2, "results": juniors},
    }
    used = {c for t in tournaments.values() for r in t["results"].values() for c in r.values()}
    unknown = sorted(used - set(COUNTRIES))
    if unknown:
        sys.exit(f"country codes with no name: {unknown} (add them to COUNTRIES)")

    for key, t in tournaments.items():
        print(f"{key}: {len(t['results'])} editions")
    print(f"triple gold club: {len(club)} players")
    for year in sorted(olympics):
        r = olympics[year]
        print(f"  olympics {year}: {r['gold']} / {r['silver']} / {r['bronze']}")
    OUT.write_text(json.dumps({
        "built": date.today().isoformat(),
        "source": "Wikipedia medal tables (CC BY-SA 4.0); Canada Cup, World Cup of Hockey and 4 Nations finals from their Wikipedia pages",
        "countries": {c: COUNTRIES[c] for c in sorted(used)},
        "tournaments": tournaments,
        "triple_gold_club": club,
    }, indent=1, sort_keys=False) + "\n")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
