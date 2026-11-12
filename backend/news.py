"""NHL news: reads headlines from public RSS feeds, tags each with the teams and players it mentions, and flags the big stories.
We keep only the headline, a short excerpt and the link to the publisher; nothing here copies an article.
Parsing and tagging are pure functions (tested without a network); `fetch_all` is the only part that goes online."""
import html
import re
import unicodedata
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

import requests

FEEDS = [
    ("ESPN", "https://www.espn.com/espn/rss/nhl/news"),
    ("Yahoo Sports", "https://sports.yahoo.com/nhl/rss/"),
    ("CBS Sports", "https://www.cbssports.com/rss/headlines/nhl/"),
    ("The Athletic", "https://theathletic.com/nhl/?rss"),
]
FETCH_TIMEOUT = 8
USER_AGENT = "Mozilla/5.0 (compatible; NHLStatsNewsReader/1.0)"
SUMMARY_CHARS = 240

# This is a stats site, not a betting site: odds, picks and parlays are left out.
BETTING = re.compile(r"\b(odds|picks?|parlays?|best bets?|prop bets?|sportsbook|betting|promo codes?|bet365|fanduel|draftkings)\b", re.I)
# Auto-written previews for every game add noise and nothing else.
FILLER = re.compile(r"\bgame preview\b", re.I)

# --- How big a story is --------------------------------------------------------------------------------
# A story's score adds up the pieces below; a story at or above MIN_TOP is a "top story". Every weight lives here so it can be tuned.
# The Top tab then orders by score with a decay for age (see news_db), so a big story stays up for a day or two and then fades.
MIN_TOP = 8
TYPE_WEIGHTS = [  # what the headline reports; the first (highest) tier that matches counts
    (10, re.compile(r"\b(trades?|traded|trading|acquires?|acquired|fires?|fired|hires?|hired|retires?|retired|retirement|dies|died|"
                    r"passes away|lockout|steps? down)\b", re.I)),
    (7, re.compile(r"\b(signs?|signed|signing|extension|contract|waives?|waived|waivers|claimed|buyout|suspends?|suspended|suspension|"
                   r"injur(?:y|ed|ies)|out indefinitely|out for|placed on|surgery|hall of fame|inducted|cba)\b", re.I)),
    (4, re.compile(r"\b(hat trick|milestone|record|returns?|recalled|scratched|debut|calls? up)\b", re.I)),
]
# A single story of the 7 tier needs one more signal (a star, a second outlet, ESPN); the 10 tier stands alone.
RECAP = re.compile(r"\b\d{1,2}-\d{1,2}(?:-\d{1,2})?\b")  # a score or record in the headline: a game recap
RECAP_PENALTY = -6
ANALYSIS = re.compile(r"\b(power rankings?|mailbag|takeaways|observations|standouts|what to watch|guide to|ranking|ranked|fantasy|"
                      r"grades|stock watch|could|should|might|ideas|candidates|predictions?|how to watch|where to watch|watch live|live stream)\b|\?", re.I)
ANALYSIS_PENALTY = -8  # opinion, speculation, lists and viewing guides are not news (enough to undo a trade keyword and a star)
NOT_NHL = re.compile(r"\b(PWHL|NCAA|college|CHL|OHL|WHL|QMJHL|ECHL|world juniors?|women's)\b", re.I)
NOT_NHL_PENALTY = -8
EXTRA_OUTLET = 3       # per other outlet carrying the same story...
EXTRA_OUTLET_MAX = 6   # ...up to this much
STAR_IN_HEADLINE = 3
STAR_IN_TEXT = 2
SOURCE_BONUS = {"ESPN": 2, "The Athletic": 1}  # ESPN's list is its editors' lead stories
SAME_STORY_HOURS = 36
STOP_WORDS = {"after", "about", "their", "there", "with", "from", "that", "this", "have", "will", "were", "been", "into", "over",
              "says", "just", "than", "them", "your", "what", "when", "where", "which", "while", "would", "could", "first", "second",
              "third", "game", "games", "night", "season", "team", "teams", "nhl"}

NICKNAMES = {"habs": "MTL", "leafs": "TOR", "bolts": "TBL", "canes": "CAR", "preds": "NSH"}


# --- Reading a feed ----------------------------------------------------------------------------------

# Headlines sometimes carry emoji; the site shows none.
EMOJI = re.compile("[\U0001F000-\U0001FFFF\u2600-\u27BF\u2B00-\u2BFF\uFE0F\u200D]")


def clean(text, limit=None):
    """Plain text from a feed field: tags and emoji removed, entities decoded, whitespace collapsed, cut at a word boundary."""
    text = re.sub(r"<[^>]+>", " ", html.unescape(text or ""))
    text = re.sub(r"\s+", " ", EMOJI.sub("", html.unescape(text))).strip()
    if limit and len(text) > limit:
        text = text[:limit].rsplit(" ", 1)[0].rstrip(" ,;:-") + "…"
    return text


def _when(raw):
    try:
        t = parsedate_to_datetime(raw.strip())
    except (TypeError, ValueError, AttributeError):
        return None
    return t if t.tzinfo else t.replace(tzinfo=timezone.utc)


def url_key(url):
    """The same story can arrive with tracking parameters or a trailing slash; this is what makes two links equal."""
    return re.sub(r"[?#].*$", "", (url or "").strip()).rstrip("/").lower()


def parse_feed(xml_bytes, default_source):
    """Items of one RSS 2.0 feed as {url, title, summary, source, source_detail, published}. Items missing a title, link or date are skipped.
    Yahoo's feed credits the original outlet in <source> ("The Hockey News - Columbus Blue Jackets"): the outlet becomes the source and the
    part after the dash is kept as source_detail, which names the team the story is about."""
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError:
        return []
    items = []
    for node in root.iter("item"):
        fields = {}
        for child in node:
            name = child.tag.rsplit("}", 1)[-1]
            text = (child.text or "").strip()
            if text and name not in fields:  # first non-empty wins (The Athletic lists description twice)
                fields[name] = text
        title, link, published = clean(fields.get("title")), (fields.get("link") or "").strip(), _when(fields.get("pubDate"))
        if not (title and link.startswith("http") and published):
            continue
        source, _, detail = clean(fields.get("source") or fields.get("publisher")).partition(" - ")
        items.append({"url": link, "title": title, "summary": clean(fields.get("description"), SUMMARY_CHARS),
                      "source": source or default_source, "source_detail": detail, "published": published})
    return items


def keep(item):
    """Whether a story belongs on the site (no betting content, no auto-written previews)."""
    return not (BETTING.search(item["title"]) or "/betting/" in item["url"] or FILLER.search(item["title"]))


def merge(batches):
    """Every feed's items as one list, newest first, with a story that several feeds carry kept once (same link or same headline)."""
    seen, out = set(), []
    for item in sorted((i for batch in batches for i in batch if keep(i)), key=lambda i: i["published"], reverse=True):
        keys = {url_key(item["url"]), re.sub(r"\W+", " ", item["title"].lower()).strip()}
        if keys & seen:
            continue
        seen |= keys
        out.append(item)
    return out


def _fetch_one(feed):
    source, url = feed
    try:
        r = requests.get(url, timeout=FETCH_TIMEOUT, headers={"User-Agent": USER_AGENT})
        r.raise_for_status()
        return parse_feed(r.content, source)
    except requests.RequestException:
        return []  # one feed being down must not hide the others


def fetch_all(feeds=FEEDS):
    """Merged, filtered items from every feed (the feeds are read in parallel)."""
    with ThreadPoolExecutor(max_workers=len(feeds)) as pool:
        return merge(pool.map(_fetch_one, feeds))


# --- Tagging -----------------------------------------------------------------------------------------

def fold(text):
    """Accents removed (Montréal -> Montreal), curly quotes straightened, spaces collapsed; capitals kept."""
    text = unicodedata.normalize("NFKD", text or "")
    text = "".join(c for c in text if not unicodedata.combining(c)).replace("’", "'")
    return re.sub(r"\s+", " ", text).strip()


def norm(text):
    """fold(), lower-cased, with punctuation as spaces ("J.T. Miller" -> "j t miller")."""
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", fold(text).lower())).strip()


def _alternation(words):
    return "|".join(re.escape(w) for w in sorted(words, key=len, reverse=True))


class Tagger:
    """Finds the teams and players a piece of text mentions.
    teams: [{abbrev, name, common_name}]; players: [{player_id, name, team}] for the current season (a traded player's team is a comma list)."""

    def __init__(self, teams, players):
        self.teams = {t["abbrev"] for t in teams}
        full = {norm(t["name"]): t["abbrev"] for t in teams}
        self._full_team = re.compile(rf"\b({_alternation(full)})\b") if full else None
        self._full_team_map = full
        # A nickname alone ("Oilers") is matched with its capital, so "wild" and "stars" in ordinary prose don't count; "Wild Card" isn't the team.
        nick = {fold(t["common_name"]): t["abbrev"] for t in teams if t.get("common_name")}
        self._nick_team = re.compile(rf"\b({_alternation(nick)})\b(?! [Cc]ard)") if nick else None
        self._nick_team_map = nick
        self._slang = re.compile(rf"\b({_alternation(w.capitalize() for w in NICKNAMES)})\b")
        self._player_team = {p["player_id"]: p["team"].split(",")[-1].strip() for p in players if p.get("team")}

        by_name = {}
        for p in players:
            by_name.setdefault(norm(p["name"]), []).append(p["player_id"])
        self._full_player_map = {n: ids[0] for n, ids in by_name.items() if len(ids) == 1}  # two players with one name can't be told apart
        self._full_player = re.compile(rf"\b({_alternation(self._full_player_map)})\b") if self._full_player_map else None

        surnames = {}
        for p in players:
            tokens = re.sub(r"[^\w' -]", "", fold(p["name"])).split()
            if len(tokens) > 1 and len(tokens[-1]) >= 5:
                surnames.setdefault(tokens[-1], set()).add(p["player_id"])
        self._surname_map = {s: next(iter(ids)) for s, ids in surnames.items() if len(ids) == 1}
        self._surname = re.compile(rf"\b({_alternation(self._surname_map)})\b") if self._surname_map else None

    def team_tags(self, text):
        """Teams named in the text, by full name, nickname ("Oilers", "Habs")."""
        found = set()
        if self._full_team:
            found |= {self._full_team_map[m] for m in self._full_team.findall(norm(text))}
        folded = fold(text)
        if self._nick_team:
            found |= {self._nick_team_map[m] for m in self._nick_team.findall(folded)}
        found |= {NICKNAMES[m.lower()] for m in self._slang.findall(folded)}
        return found

    def player_tags(self, text, teams=()):
        """Players named in the text. A full name always counts. A surname alone (headlines use them) counts only when no other current player
        shares it and the player's team is one of `teams` (named in the same story): "Hamilton" in a story about the PWHL's Hamilton
        team is not Dougie Hamilton."""
        found = set()
        if self._full_player:
            found |= {self._full_player_map[m] for m in self._full_player.findall(norm(text))}
        if self._surname:
            for m in self._surname.findall(fold(text)):
                pid = self._surname_map[m]
                if self._player_team.get(pid) in teams:
                    found.add(pid)
        return found

    def tag(self, item):
        """(team abbrevs, player ids, player ids named in the headline) for a story. Teams come from the whole text; a player named in the
        headline also adds their own team."""
        head = item["title"]
        body = " ".join([item["title"], item.get("summary") or "", item.get("source_detail") or ""])
        teams = self.team_tags(body)
        players = self.player_tags(body, teams)
        in_head = self.player_tags(head, teams)
        teams |= {self._player_team[p] for p in in_head if p in self._player_team}
        return sorted(teams & self.teams), sorted(players), sorted(in_head)


def _tokens(title):
    return {w for w in re.findall(r"[a-z0-9]+", fold(title).lower()) if len(w) >= 4 and w not in STOP_WORDS}


def same_story(a, b, tags_a, tags_b, other_outlet=True):
    """Whether two items report one story: close in time, and sharing a named player and two headline words, or four headline words.
    By default they must come from different outlets (an outlet's own repeat is not another outlet carrying the story, so it earns no
    coverage bonus); other_outlet=False also matches two stories from one outlet, to keep near-duplicates out of the Top list."""
    if (other_outlet and a["source"] == b["source"]) or abs((a["published"] - b["published"]).total_seconds()) > SAME_STORY_HOURS * 3600:
        return False
    shared = len(_tokens(a["title"]) & _tokens(b["title"]))
    return shared >= 4 or (shared >= 2 and bool(set(tags_a[1]) & set(tags_b[1])))


def score_all(items, tags, stars=frozenset()):
    """A newsworthiness score per item (parallel to `items`; `tags` are the results of Tagger.tag; `stars` are player ids).
    Adds the story type, a bonus for each other outlet carrying it and for stars involved, ESPN's lead-list bonus, and penalties for
    recaps, opinion pieces and non-NHL hockey."""
    out = []
    for i, item in enumerate(items):
        title = item["title"]
        score = next((w for w, rx in TYPE_WEIGHTS if rx.search(title)), 0)
        if RECAP.search(title):
            score += RECAP_PENALTY
        if ANALYSIS.search(title):
            score += ANALYSIS_PENALTY
        if NOT_NHL.search(title) or NOT_NHL.search(item.get("summary") or ""):
            score += NOT_NHL_PENALTY
        outlets = sum(1 for j, other in enumerate(items) if j != i and same_story(item, other, tags[i], tags[j]))
        score += min(EXTRA_OUTLET * outlets, EXTRA_OUTLET_MAX)
        named = set(tags[i][1]) & set(stars)
        if named:
            score += STAR_IN_HEADLINE if named & set(tags[i][2]) else STAR_IN_TEXT
        score += SOURCE_BONUS.get(item["source"], 0)
        out.append(score)
    # A story several outlets carry should appear once in the Top list: its best-scoring version keeps its score, the others (still in
    # Latest) are held just under the top line.
    for i, item in enumerate(items):
        if any(j != i and same_story(item, other, tags[i], tags[j], other_outlet=False) and (out[j], -j) > (out[i], -i)
               for j, other in enumerate(items)):
            out[i] = min(out[i], MIN_TOP - 1)
    return out


def now_utc():
    return datetime.now(timezone.utc)
