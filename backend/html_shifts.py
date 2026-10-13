"""Fallback shift source: the NHL's HTML "Time On Ice" reports.

The stats-API shift chart is sometimes empty for finished games. The same data is published as
HTML reports (TH = home team, TV = visitors) which this module parses into the row format the
API would have returned, so corsi.py can use either source unchanged.
"""
import re
from html.parser import HTMLParser

REPORT_URL = "https://www.nhl.com/scores/htmlreports/{season}/{kind}{number}.HTM"
PERIODS = {"1": 1, "2": 2, "3": 3, "OT": 4}  # shootout ("SO") has no shifts worth counting
CLOCK = re.compile(r"^(\d+:\d\d)\s*/\s*\d+:\d\d$")
HEADING = re.compile(r"^(\d+)\s+(.+)$")


class _ReportParser(HTMLParser):
    """Collects table rows as lists of cell text, tracking which cells are player headings."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.rows = []  # (cells, heading) per finished row
        self._stack = []  # open rows: [cells, heading_text]
        self._cell = None
        self._cell_is_heading = False

    def handle_starttag(self, tag, attrs):
        if tag == "tr":
            self._stack.append([[], None])
        elif tag == "td" and self._stack:
            self._cell = []
            self._cell_is_heading = "playerHeading" in dict(attrs).get("class", "")

    def handle_data(self, data):
        if self._cell is not None:
            self._cell.append(data)

    def handle_endtag(self, tag):
        if tag == "td" and self._cell is not None and self._stack:
            text = re.sub(r"\s+", " ", "".join(self._cell).replace("\xa0", " ")).strip()
            self._stack[-1][0].append(text)
            if self._cell_is_heading:
                self._stack[-1][1] = text
            self._cell = None
            self._cell_is_heading = False
        elif tag == "tr" and self._stack:
            cells, heading = self._stack.pop()
            self.rows.append((cells, heading))


def report_url(game_id, kind, season=None):
    """kind is 'TH' (home) or 'TV' (visitor). game_id like 2026020006 -> TH020006.HTM."""
    s = str(game_id)
    return REPORT_URL.format(season=season or f"{s[:4]}{int(s[:4]) + 1}", kind=kind, number=s[4:])


def parse_report(html):
    """sweater number -> [(period, 'm:ss' start, 'm:ss' end)] for one team's report."""
    parser = _ReportParser()
    parser.feed(html)
    players = {}
    current = None
    for cells, heading in parser.rows:
        if heading:
            m = HEADING.match(heading)
            current = int(m.group(1)) if m else None
            if current is not None:
                players.setdefault(current, [])
            continue
        if current is None or len(cells) < 6:
            continue
        shift_no, per, start, end = cells[0], cells[1], CLOCK.match(cells[2]), CLOCK.match(cells[3])
        if shift_no.isdigit() and per in PERIODS and start and end:
            players[current].append((PERIODS[per], start.group(1), end.group(1)))
    return {n: s for n, s in players.items() if s}


def shift_rows(home_html, away_html, roster_spots, home_team_id, away_team_id):
    """Synthetic API-style shift rows, joining sweater numbers to player ids via the roster."""
    rows = []
    for html, team_id in ((home_html, home_team_id), (away_html, away_team_id)):
        by_number = {r["sweaterNumber"]: r["playerId"] for r in roster_spots
                     if r["teamId"] == team_id and "sweaterNumber" in r}
        for number, shifts in parse_report(html).items():
            pid = by_number.get(number)
            if pid is None:
                continue
            for period, start, end in shifts:
                rows.append({"typeCode": 517, "period": period, "startTime": start, "endTime": end,
                             "playerId": pid, "teamId": team_id})
    return rows
