"""Builds backend/data/international_awards.json: the individual awards of the men's international tournaments that matter to NHL players,
as one entry per award: {tournament, year, award, name, code}. The awards kept are the notable ones:

    mvp         the tournament's most valuable player
    goaltender  best goaltender, defenseman, forward: the IIHF directorate awards
    defense
    forward

Media all-star teams are not included: they are a longer list of lesser honors, and their layouts differ from page to page.

    cd backend && .venv/bin/python analysis/fetch_international_awards.py

Where each tournament's awards come from, and what is missing, is written into the file's `coverage` (and printed), because the sources are
uneven: the World Championship has one clean list; the Olympic pages show the directorate awards only from 2002 and no awards at all for
1992 to 1998; the World Junior pages use several layouts; the World Cup, Canada Cup and 4 Nations name only an MVP. Names are matched to NHL
players by internationals.py. Wikipedia text is CC BY-SA 4.0; pages are fetched one at a time, politely, and every hand-entered edition is
checked against the fetched page (each name must appear in it) so a typo or a changed page stops the build."""
import json
import os
import re
import sys
import time
from datetime import date
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))   # backend/, for internationals
import internationals  # noqa: E402

OUT = Path(__file__).resolve().parent.parent / "data" / "international_awards.json"
API = "https://en.wikipedia.org/w/api.php"
UA = "NHLStatsResultsBuilder/1.0 (a personal hockey stats project; reads public award lists)"
PAUSE = 1.2        # seconds between requests: the API rate-limits bursts
AWARDS = ("mvp", "goaltender", "defense", "forward")

_cache = {}
CACHE_DIR = os.environ.get("WIKI_CACHE")   # optional: a directory to keep fetched pages in, so a rerun does not fetch them all again


def wikitext(page):
    """A page's wikitext, fetched once, one request at a time, waiting out Wikipedia's rate limit (HTTP 429)."""
    if page in _cache:
        return _cache[page]
    cached = Path(CACHE_DIR) / (re.sub(r"[^A-Za-z0-9]+", "_", page) + ".json") if CACHE_DIR else None
    if cached and cached.exists():
        _cache[page] = json.loads(cached.read_text())["parse"]["wikitext"]["*"]
        return _cache[page]
    for _ in range(8):
        r = requests.get(API, params={"action": "parse", "page": page, "prop": "wikitext", "format": "json", "redirects": 1},
                         headers={"User-Agent": UA}, timeout=30)
        if r.status_code == 429:
            time.sleep(float(r.headers.get("retry-after", "3")) + 1)
            continue
        r.raise_for_status()
        time.sleep(PAUSE)
        if cached:
            cached.write_text(r.text)
        _cache[page] = r.json()["parse"]["wikitext"]["*"]
        return _cache[page]
    sys.exit(f"rate limited fetching {page!r}: try again in a few minutes")


def row_cells(row):
    """The cells of a wikitext table row, split on newlines and on the inline || and !! separators."""
    out = []
    for line in row.strip().splitlines():
        if line.startswith(("|}", "|+", "{|")):
            continue
        if line.startswith("|") or line.startswith("!"):
            out.extend(re.split(r"\|\||!!", line[1:]))
    return out


def _display(link_target, label):
    """A link's display name: its label, else its target without a '(ice hockey, born 1994)' style qualifier."""
    return (label or re.sub(r"\s*\(.*\)$", "", link_target)).strip()


def player_of(cell):
    """(name, country) of the first player in a cell, or None. The country is whatever the flag says (a code such as CAN, or a name such
    as Czech Republic: internationals.country_code reads both). Handles {{flagathlete|[[Name]]|CODE}}, and a flag template
    ({{flagicon|X}}, {{ihicon|X}}, {{ihj|X}}, {{ih|X}}, {{flagdeco|X}}) followed by the player: a link, or a bare name. The link after the flag is
    the player; a link before it (a position such as [[Goaltender]]) is not."""
    m = re.search(r"\{\{flagathlete\|\[\[([^\]|]+)(?:\|([^\]]+))?\]\]\|\s*([^|}]+?)\s*[|}]", cell)
    if m:
        return _display(m.group(1), m.group(2)), m.group(3).strip()
    f = re.search(r"\{\{(?:flagicon|ihicon|ihj|ih|flagdeco)\|\s*([^|}]+?)\s*(?:\|[^}]*)?\}\}", cell)
    if not f:
        return None
    rest = cell[f.end():]
    link = re.match(r"\s*\[\[([^\]|]+)(?:\|([^\]]+))?\]\]", rest)
    if link:
        return _display(link.group(1), link.group(2)), f.group(1).strip()
    bare = re.match(r"\s*([^<,/\[\{|\n]+)", rest)  # a name with no link, up to the next separator
    if bare and bare.group(1).strip() and not bare.group(1).strip().startswith(("(", ")")):
        return bare.group(1).strip(), f.group(1).strip()
    return None


# --- World Championship (and the Olympic years the IIHF counted as World Championships) ----------------------

def parse_worlds_awards(text):
    """Entries from the IIHF directorate award list: Year | Goaltender | Defence | Forwards | Most Valuable Player. A row whose year links
    to an Olympic tournament belongs to the Olympics."""
    out = []
    for row in re.split(r"\n\|-", text[text.index("{| class"):]):
        cells = row_cells(row)
        year = re.search(r"(\d{4})\]\]", cells[0]) if cells else None
        if not year:
            continue
        tournament = "olympics" if "Olympics" in cells[0] else "worlds"
        for award, cell in zip(AWARDS[1:] + AWARDS[:1], cells[1:5]):  # goaltender, defense, forward, then MVP
            if not re.sub(r"[\s']", "", cell):
                continue
            who = player_of(cell)
            if not who:
                raise ValueError(f"worlds {year.group(1)}: cannot read a player from {cell[:100]!r}")
            out.append({"tournament": tournament, "year": int(year.group(1)), "award": award, "name": who[0], "code": who[1]})
    return out


# --- World Junior Championship ---------------------------------------------------------------------------------

def awards_section(text):
    """The text of an edition page's 'Tournament awards' section (up to the next heading of the same or a higher level), or None."""
    m = re.search(r"\n(={2,4})\s*(?:Tournament |Individual )?[Aa]wards\s*\1\s*\n", text)
    if not m:
        return None
    rest = text[m.end():]
    end = re.search(r"\n={2,%d}[^=\n]" % len(m.group(1)), rest)
    return rest[:end.start()] if end else rest


def juniors_from_table(section):
    """Directorate awards from a table: a column headed 'IIHF Directorate Awards' with rows Goaltender / Defencemen / Forwards, or (2001-style)
    a row labelled 'IIHF Directorate Awards' with the goaltender, defenceman and forward in its next cells."""
    out = {}
    rows = re.split(r"\n\|-", section[section.index("{|"):])
    header = row_cells(rows[0]) if rows else []
    column = next((i for i, c in enumerate(header) if "irectorate" in c), None)
    for row in rows[1:]:
        cells = row_cells(row)
        if not cells:
            continue
        label = re.sub(r"[^a-z]", "", cells[0].lower())
        if column is not None and label.startswith(("goalt", "defen", "forw")):
            who = player_of(cells[column]) if column < len(cells) else None
            if not who:
                raise ValueError("cannot read the directorate player in the %s row" % label)
            out["goaltender" if label.startswith("goalt") else "defense" if label.startswith("defen") else "forward"] = who
        elif "irectorate" in cells[0]:
            players = [player_of(c) for c in cells[1:] if player_of(c)]
            if len(players) != 3:
                raise ValueError("expected 3 directorate players in the row, found %d" % len(players))
            out.update(zip(("goaltender", "defense", "forward"), players))
    return out


def juniors_from_bullets(section):
    """Awards from bullet lists: an 'IIHF best player' / 'Directorate' block of Goaltender / Defenceman / Forward lines, and a 'Most Valuable
    Player' block whose bullet names the player (the position in front of the name is only a label)."""
    out = {}
    block = None
    for line in section.splitlines():
        who = player_of(line)
        low = re.sub(r"[^a-z ]", "", line.lower()).strip()
        if not who:  # a line with no player is a heading (bold, a heading, or a bullet that introduces the list below it)
            if "most valuable" in low:
                block = "mvp"
            elif "directorate" in low or "best player" in low:
                block = "directorate"
            elif low:
                block = "other"
            continue
        before = re.sub(r"\{\{[^}]*\}\}", "", re.sub(r"\[\[(?:[^\]|]*\|)?([^\]]*)\]\]", r"\1", line.split(":")[0]))   # the label, link text kept
        label = re.sub(r"[^a-z]", "", before.lower()) if ":" in line else ""
        if block == "mvp" or label.endswith("mvp"):   # an "MVP:" line counts wherever it sits (2006 files it under the media all-stars)
            out["mvp"] = who
        elif block == "directorate":
            key = ("mvp" if label.endswith("mvp") else "goaltender" if "goalt" in label else "defense" if "defen" in label
                   else "forward" if "forw" in label else None)
            if key:
                out[key] = who
    return out


def parse_juniors_awards(text):
    """{award: (name, code)} for one World Junior edition: the directorate awards, and the MVP where the page lists one."""
    section = awards_section(text)
    if not section:
        raise ValueError("no awards section")
    got = juniors_from_table(section) if "{|" in section and "irectorate" in section else {}
    for award, who in juniors_from_bullets(section).items():
        got.setdefault(award, who)
    return got


# --- Olympic Games ---------------------------------------------------------------------------------------------
# The Olympic pages list the awards in a different layout every time (a table, bullets, a sentence) and, for 1992 to 1998, not at all, so these
# are entered by hand from the pages, and the build checks every name against the page it came from. The 2022 page lists the MVP and a media
# all-star team but not the directorate awards. Countries are the codes in international_results.json (the Olympic Athletes from Russia are RUS).
OLYMPIC_AWARDS = {
    2002: {"mvp": ("Joe Sakic", "CAN"), "goaltender": ("Nikolai Khabibulin", "RUS"), "defense": ("Chris Chelios", "USA"), "forward": ("Joe Sakic", "CAN")},
    2006: {"mvp": ("Antero Niittymäki", "FIN"), "goaltender": ("Antero Niittymäki", "FIN"), "defense": ("Kenny Jönsson", "SWE"),
           "forward": ("Teemu Selänne", "FIN")},
    2010: {"mvp": ("Ryan Miller", "USA"), "goaltender": ("Ryan Miller", "USA"), "defense": ("Brian Rafalski", "USA"), "forward": ("Jonathan Toews", "CAN")},
    2014: {"mvp": ("Teemu Selänne", "FIN"), "goaltender": ("Carey Price", "CAN"), "defense": ("Erik Karlsson", "SWE"), "forward": ("Phil Kessel", "USA")},
    2018: {"mvp": ("Ilya Kovalchuk", "RUS"), "goaltender": ("Danny aus den Birken", "GER"), "defense": ("Vyacheslav Voynov", "RUS"),
           "forward": ("Nikita Gusev", "RUS")},
    2022: {"mvp": ("Juraj Slafkovský", "SVK")},
    2026: {"mvp": ("Connor McDavid", "CAN"), "goaltender": ("Connor Hellebuyck", "USA"), "defense": ("Quinn Hughes", "USA"),
           "forward": ("Connor McDavid", "CAN")},
}


def olympic_title(year):
    return f"Ice hockey at the {year} Winter Olympics" + (" \u2013 Men's tournament" if year >= 1998 else "")


def olympic_awards():
    out = []
    for year, awards in OLYMPIC_AWARDS.items():
        text = wikitext(olympic_title(year))
        for award, (name, code) in awards.items():
            if name not in text:
                sys.exit(f"olympics {year}: {name!r} ({award}) does not appear on the page: check the entry")
            out.append({"tournament": "olympics", "year": year, "award": award, "name": name, "code": code})
    return out


# --- The NHL-run tournaments and the World Junior editions ----------------------------------------------------

SMALL = [("worldcup", 1976, "1976 Canada Cup"), ("worldcup", 1981, "1981 Canada Cup"), ("worldcup", 1984, "1984 Canada Cup"),
         ("worldcup", 1987, "1987 Canada Cup"), ("worldcup", 1991, "1991 Canada Cup"), ("worldcup", 1996, "1996 World Cup of Hockey"),
         ("worldcup", 2004, "2004 World Cup of Hockey"), ("worldcup", 2016, "2016 World Cup of Hockey"), ("fournations", 2025, "4 Nations Face-Off")]


def infobox_mvp(text):
    """The player in an edition page's infobox 'mvp' field, or None."""
    m = re.search(r"\|\s*mvp\s*=\s*([^\n]*)", text)
    return player_of(m.group(1)) if m else None


def small_awards():
    out, missing = [], []
    for tournament, year, title in SMALL:
        who = infobox_mvp(wikitext(title))
        if who:
            out.append({"tournament": tournament, "year": year, "award": "mvp", "name": who[0], "code": who[1]})
        else:
            missing.append(f"{year} {title}")
    return out, missing


def juniors_awards():
    out, partial = [], {}
    for year in range(1977, 2027):
        got = parse_juniors_awards(wikitext(f"{year} World Junior Ice Hockey Championships"))
        lacking = [a for a in AWARDS[1:] if a not in got]
        if lacking:
            partial[year] = lacking
        out += [{"tournament": "juniors", "year": year, "award": a, "name": got[a][0], "code": got[a][1]} for a in AWARDS if a in got]
    return out, partial


def expect(awards, tournament, year, award, name):
    """Stops the build unless the entry exists: a check on the parsers against awards I know."""
    got = next((a["name"] for a in awards if (a["tournament"], a["year"], a["award"]) == (tournament, year, award)), None)
    if got != name:
        sys.exit(f"check failed: {tournament} {year} {award} is {got!r}, expected {name!r}")


def main():
    awards, notes = [], []
    worlds = parse_worlds_awards(wikitext("List of IIHF World Championship directorate award winners"))
    print(f"world championship list: {len(worlds)} awards")
    awards += worlds
    awards += olympic_awards()
    small, missing = small_awards()
    awards += small
    if missing:
        notes.append("no MVP found on the page of: " + ", ".join(missing))
    juniors, partial = juniors_awards()
    print(f"world juniors: {len(juniors)} awards; editions missing some directorate awards: {sorted(partial)}")
    awards += juniors

    # the checks: awards I know, across every source and layout
    for t, y, a, n in [("worlds", 2003, "mvp", "Mats Sundin"), ("worlds", 2015, "mvp", "Jaromír Jágr"), ("worlds", 1992, "forward", "Mats Sundin"),
                       ("olympics", 1960, "goaltender", "Jack McCartan"), ("olympics", 2014, "goaltender", "Carey Price"),
                       ("juniors", 1993, "forward", "Peter Forsberg"), ("juniors", 2009, "mvp", "John Tavares"),
                       ("juniors", 2015, "goaltender", "Denis Godla"), ("juniors", 2006, "forward", "Evgeni Malkin"),
                       ("juniors", 2007, "mvp", "Carey Price"), ("juniors", 2005, "mvp", "Patrice Bergeron")]:
        expect(awards, t, y, a, n)
    if len(juniors) < 150 or len(partial) > 10:
        sys.exit(f"world juniors: only {len(juniors)} awards and {len(partial)} partial editions: a layout has probably changed")

    for a in awards:   # the flags give a code (CAN) or a name (Canada, USSR): store the code, as the results file does
        a["code"] = a["code"] if re.fullmatch(r"[A-Z]{3}", a["code"]) else (internationals.country_code(a["code"]) or a["code"])
    unknown = sorted({a["code"] for a in awards if a["code"] not in internationals.load_results()["countries"]})
    if unknown:
        print(f"country codes the results file has no name for (shown by code): {unknown}")

    seen = {}
    for a in awards:
        key = (a["tournament"], a["year"], a["award"])
        if key in seen and seen[key] != (a["name"], a["code"]):
            sys.exit(f"two different winners for {key}: {seen[key]} and {(a['name'], a['code'])}")
        seen[key] = (a["name"], a["code"])
    awards = [dict(zip(("tournament", "year", "award", "name", "code"), k + v)) for k, v in sorted(seen.items(), key=lambda kv: (kv[0][0], kv[0][1], AWARDS.index(kv[0][2])))]

    coverage = {
        "worlds": "directorate awards 1954-2026 (not 2020); most valuable player from 1999",
        "olympics": "1956-1968 from the IIHF list (they counted as World Championships); directorate awards and MVP for 2002-2018 and 2026; MVP only "
                    "for 2022; none listed on Wikipedia for 1972-1998",
        "worldcup": "most valuable player only (the Canada Cup and the World Cup of Hockey have no directorate awards)",
        "fournations": "most valuable player only",
        "juniors": "directorate awards 1977-2026 except the editions whose page lists none: " + ", ".join(f"{y} ({'/'.join(l)})" for y, l in sorted(partial.items())) + "; most valuable player from 2004 where the page lists one",
    }
    for note in notes:
        coverage["notes"] = coverage.get("notes", "") + note + "; "
    for t in ("worlds", "olympics", "worldcup", "fournations", "juniors"):
        print(f"{t}: {sum(a['tournament'] == t for a in awards)} awards")
    OUT.write_text(json.dumps({"built": date.today().isoformat(),
                               "source": "Wikipedia tournament pages (CC BY-SA 4.0): the IIHF directorate award list, each World Junior and Olympic edition, and "
                                         "each Canada Cup, World Cup of Hockey and 4 Nations page",
                               "coverage": coverage, "awards": awards}, indent=1, ensure_ascii=False) + "\n")
    print(f"wrote {OUT} ({len(awards)} awards)")


if __name__ == "__main__":
    main()
