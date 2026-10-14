CREATE TABLE IF NOT EXISTS skater_season (
    season_id        INTEGER NOT NULL,
    player_id        INTEGER NOT NULL,
    name             TEXT NOT NULL,
    team             TEXT,
    position         TEXT,
    games_played     INTEGER NOT NULL,
    goals            INTEGER NOT NULL,
    assists          INTEGER NOT NULL,
    points           INTEGER NOT NULL,
    plus_minus       INTEGER,
    pim              INTEGER,
    shots            INTEGER,
    toi_per_game_sec REAL,
    hits             INTEGER,
    blocked_shots    INTEGER,
    takeaways        INTEGER,
    giveaways        INTEGER,
    hits_per60       REAL,
    blocks_per60     REAL,
    takeaways_per60  REAL,
    giveaways_per60  REAL,
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (season_id, player_id)
);

CREATE TABLE IF NOT EXISTS skater_game (
    player_id  INTEGER NOT NULL,
    season_id  INTEGER NOT NULL,
    game_id    BIGINT NOT NULL,
    game_date  DATE NOT NULL,
    team       TEXT,
    opponent   TEXT,
    is_home    BOOLEAN,
    goals      INTEGER NOT NULL,
    assists    INTEGER NOT NULL,
    points     INTEGER NOT NULL,
    shots      INTEGER,
    plus_minus INTEGER,
    pim        INTEGER,
    toi_sec    INTEGER,
    PRIMARY KEY (player_id, game_id)
);
CREATE INDEX IF NOT EXISTS skater_game_player_date
    ON skater_game (player_id, season_id, game_date DESC);

-- Per-game defensive stats (from boxscores). ALTERs rather than CREATE columns so older databases upgrade in place.
ALTER TABLE skater_game ADD COLUMN IF NOT EXISTS hits          INTEGER;
ALTER TABLE skater_game ADD COLUMN IF NOT EXISTS blocked_shots INTEGER;
ALTER TABLE skater_game ADD COLUMN IF NOT EXISTS takeaways     INTEGER;
ALTER TABLE skater_game ADD COLUMN IF NOT EXISTS giveaways     INTEGER;

CREATE TABLE IF NOT EXISTS team_season (
    season_id        INTEGER NOT NULL,
    abbrev           TEXT NOT NULL,
    team_id          INTEGER,
    name             TEXT NOT NULL,
    common_name      TEXT,
    logo_url         TEXT,
    logo_dark_url    TEXT,
    conference       TEXT,
    division         TEXT,
    league_rank      INTEGER,
    conference_rank  INTEGER,
    division_rank    INTEGER,
    wildcard_rank    INTEGER,
    games_played     INTEGER NOT NULL,
    wins             INTEGER,
    losses           INTEGER,
    ot_losses        INTEGER,
    points           INTEGER,
    point_pct        REAL,
    reg_wins         INTEGER,
    reg_ot_wins      INTEGER,
    goals_for        INTEGER,
    goals_against    INTEGER,
    goal_diff        INTEGER,
    l10_wins         INTEGER,
    l10_losses       INTEGER,
    l10_ot_losses    INTEGER,
    l10_points       INTEGER,
    streak_code      TEXT,
    streak_count     INTEGER,
    home_record      TEXT,
    road_record      TEXT,
    pp_pct           REAL,
    pk_pct           REAL,
    shots_for_pg     REAL,
    shots_against_pg REAL,
    fo_win_pct       REAL,
    shutouts         INTEGER,
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (season_id, abbrev)
);

CREATE TABLE IF NOT EXISTS goalie_season (
    season_id INTEGER NOT NULL,
    player_id INTEGER NOT NULL,
    name      TEXT NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (season_id, player_id)
    -- stat columns are created from GOALIE_STATS in ingest.py
);

CREATE TABLE IF NOT EXISTS goalie_game (
    player_id     INTEGER NOT NULL,
    season_id     INTEGER NOT NULL,
    game_id       BIGINT NOT NULL,
    game_date     DATE NOT NULL,
    team          TEXT,
    opponent      TEXT,
    is_home       BOOLEAN,
    started       BOOLEAN,
    decision      TEXT,
    shots_against INTEGER,
    saves         INTEGER,
    goals_against INTEGER,
    toi_sec       INTEGER,
    ev_goals_against INTEGER,
    pp_goals_against INTEGER,
    sh_goals_against INTEGER,
    PRIMARY KEY (player_id, game_id)
);
CREATE INDEX IF NOT EXISTS goalie_game_player_date ON goalie_game (player_id, season_id, game_date DESC);

-- Per-game 5v5 on-ice shot attempts, computed from play-by-play + shift charts (see corsi.py).
CREATE TABLE IF NOT EXISTS skater_game_onice (
    player_id INTEGER NOT NULL,
    game_id   BIGINT NOT NULL,
    season_id INTEGER NOT NULL,
    cf INTEGER NOT NULL,  -- Corsi for/against: all attempts while this player is on the ice
    ca INTEGER NOT NULL,
    ff INTEGER NOT NULL,  -- Fenwick: excludes blocked attempts
    fa INTEGER NOT NULL,
    gf INTEGER NOT NULL,
    ga INTEGER NOT NULL,
    PRIMARY KEY (player_id, game_id)
);

-- Which games have usable shift data. The NHL feed sometimes returns no shifts for a game;
-- those are retried on later runs.
CREATE TABLE IF NOT EXISTS game_shift_status (
    game_id    BIGINT PRIMARY KEY,
    has_shifts BOOLEAN NOT NULL,
    coverage   REAL,           -- share of 5v5 attempts with a full 12 players matched on ice
    checked_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Career data (bio, career totals, every past season) from the NHL player "landing" endpoint.
-- Filled lazily by the API the first time a player page is opened, then refreshed daily.
CREATE TABLE IF NOT EXISTS player_career (
    player_id  INTEGER PRIMARY KEY,
    payload    JSONB NOT NULL,
    fetched_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Where a game's shift data came from: the stats API, or the HTML time-on-ice reports.
ALTER TABLE game_shift_status ADD COLUMN IF NOT EXISTS source TEXT;

-- All-time career totals (every player in NHL history), per game type (2 = regular, 3 = playoffs).
-- Stat columns are created from ALLTIME_* lists in ingest.py.
CREATE TABLE IF NOT EXISTS career_skater (
    player_id INTEGER NOT NULL,
    game_type INTEGER NOT NULL,
    name      TEXT NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (player_id, game_type)
);
CREATE TABLE IF NOT EXISTS career_goalie (
    player_id INTEGER NOT NULL,
    game_type INTEGER NOT NULL,
    name      TEXT NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (player_id, game_type)
);

-- Every regular-season game: scores for finished games, start times for upcoming ones.
CREATE TABLE IF NOT EXISTS game (
    game_id     BIGINT PRIMARY KEY,
    season_id   INTEGER NOT NULL,
    game_date   DATE NOT NULL,
    start_time  TIMESTAMPTZ,
    venue       TEXT,
    state       TEXT NOT NULL,        -- FUT / PRE / LIVE / CRIT / FINAL / OFF
    home        TEXT NOT NULL,
    away        TEXT NOT NULL,
    home_score  INTEGER,
    away_score  INTEGER,
    last_period TEXT,                 -- REG / OT / SO for finished games
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS game_date_idx ON game (season_id, game_date);

-- 5v5 time and shot attempts for forward lines and for any two skaters on the ice together.
CREATE TABLE IF NOT EXISTS line_game (
    game_id BIGINT NOT NULL,
    team    TEXT NOT NULL,
    p1 INTEGER NOT NULL, p2 INTEGER NOT NULL, p3 INTEGER NOT NULL,   -- ids ascending
    toi_sec INTEGER NOT NULL,
    cf INTEGER NOT NULL, ca INTEGER NOT NULL, gf INTEGER NOT NULL, ga INTEGER NOT NULL,
    PRIMARY KEY (game_id, team, p1, p2, p3)
);
CREATE TABLE IF NOT EXISTS pair_game (
    game_id BIGINT NOT NULL,
    team    TEXT NOT NULL,
    p1 INTEGER NOT NULL, p2 INTEGER NOT NULL,                         -- ids ascending
    toi_sec INTEGER NOT NULL,
    cf INTEGER NOT NULL, ca INTEGER NOT NULL, gf INTEGER NOT NULL, ga INTEGER NOT NULL,
    PRIMARY KEY (game_id, team, p1, p2)
);
CREATE INDEX IF NOT EXISTS pair_game_p2 ON pair_game (p2);
ALTER TABLE skater_game_onice ADD COLUMN IF NOT EXISTS toi_5v5_sec INTEGER;
-- Bumped when the on-ice computation gains outputs, so old games get recomputed.
ALTER TABLE game_shift_status ADD COLUMN IF NOT EXISTS lines_version INTEGER NOT NULL DEFAULT 0;

-- Every shot attempt with normalized rink coordinates (attacking goal at x = +89) and its expected
-- goals value (NULL for blocked shots, empty nets and attempts without coordinates).
CREATE TABLE IF NOT EXISTS shot (
    game_id    BIGINT NOT NULL,
    event_id   INTEGER NOT NULL,
    season_id  INTEGER NOT NULL,
    period     INTEGER NOT NULL,
    time_sec   INTEGER NOT NULL,
    team       TEXT NOT NULL,         -- shooting team
    opponent   TEXT NOT NULL,
    shooter_id INTEGER,
    goalie_id  INTEGER,
    kind       TEXT NOT NULL,         -- shot / miss / block / goal
    shot_type  TEXT,
    x          REAL, y REAL, distance REAL, angle REAL,
    strength   TEXT,                  -- ev / pp / sh, from the shooter's point of view
    situation  TEXT,
    empty_net  BOOLEAN,
    rebound    BOOLEAN,
    xg         REAL,
    PRIMARY KEY (game_id, event_id)
);
CREATE INDEX IF NOT EXISTS shot_shooter ON shot (season_id, shooter_id);
CREATE INDEX IF NOT EXISTS shot_team ON shot (season_id, team);
ALTER TABLE skater_game_onice ADD COLUMN IF NOT EXISTS xgf REAL;
ALTER TABLE skater_game_onice ADD COLUMN IF NOT EXISTS xga REAL;

-- Past seasons' game-by-game results, for "pace vs. past seasons" charts. Immutable once stored.
CREATE TABLE IF NOT EXISTS skater_game_hist (
    player_id INTEGER NOT NULL,
    season_id INTEGER NOT NULL,
    game_id   BIGINT NOT NULL,
    game_date DATE NOT NULL,
    goals     INTEGER NOT NULL,
    assists   INTEGER NOT NULL,
    points    INTEGER NOT NULL,
    PRIMARY KEY (player_id, game_id)
);
CREATE INDEX IF NOT EXISTS skater_game_hist_player ON skater_game_hist (player_id, season_id, game_date);
CREATE TABLE IF NOT EXISTS team_game_hist (
    team_name   TEXT NOT NULL,
    season_id   INTEGER NOT NULL,
    game_id     BIGINT NOT NULL,
    game_date   DATE NOT NULL,
    points      INTEGER NOT NULL,
    wins        INTEGER NOT NULL,
    goals_for   INTEGER NOT NULL,
    goals_against INTEGER NOT NULL,
    PRIMARY KEY (team_name, game_id)
);
-- The best single seasons ever, from the NHL stats API.
CREATE TABLE IF NOT EXISTS season_record (
    stat      TEXT NOT NULL,          -- goals / assists / points
    rank      INTEGER NOT NULL,
    player_id INTEGER NOT NULL,
    name      TEXT NOT NULL,
    season_id INTEGER NOT NULL,
    games     INTEGER NOT NULL,
    value     INTEGER NOT NULL,
    PRIMARY KEY (stat, rank)
);

-- One row per skater per regular season, back to 1917-18: the age curves behind career comparables.
CREATE TABLE IF NOT EXISTS career_season (
    player_id    INTEGER NOT NULL,
    season_id    INTEGER NOT NULL,
    team         TEXT,
    games_played INTEGER NOT NULL,
    goals        INTEGER NOT NULL,
    assists      INTEGER NOT NULL,
    points       INTEGER NOT NULL,
    PRIMARY KEY (player_id, season_id)
);
CREATE INDEX IF NOT EXISTS career_season_season ON career_season (season_id);

-- Hits, blocks, takeaways, giveaways per skater per season. The NHL only tracks these from 2005-06.
CREATE TABLE IF NOT EXISTS defense_season (
    player_id        INTEGER NOT NULL,
    season_id        INTEGER NOT NULL,
    team             TEXT,
    position         TEXT,
    games_played     INTEGER NOT NULL,
    toi_per_game_sec REAL,
    hits             INTEGER NOT NULL,
    blocked_shots    INTEGER NOT NULL,
    takeaways        INTEGER NOT NULL,
    giveaways        INTEGER NOT NULL,
    PRIMARY KEY (player_id, season_id)
);
ALTER TABLE skater_game_onice ADD COLUMN IF NOT EXISTS team TEXT;

-- Era-adjusted career scoring (see era.py), filled by the ingest after the career seasons are loaded.
ALTER TABLE career_skater ADD COLUMN IF NOT EXISTS adj_goals REAL;
ALTER TABLE career_skater ADD COLUMN IF NOT EXISTS adj_assists REAL;
ALTER TABLE career_skater ADD COLUMN IF NOT EXISTS adj_points REAL;
ALTER TABLE career_skater ADD COLUMN IF NOT EXISTS adj_points_per_game REAL;

-- Abbreviations for the past-season team results, so head-to-head can pair teams with opponents.
ALTER TABLE team_game_hist ADD COLUMN IF NOT EXISTS team TEXT;
ALTER TABLE team_game_hist ADD COLUMN IF NOT EXISTS opponent TEXT;

-- NHL EDGE tracking stats per player and regular season (columns are added from edge.py's column lists).
CREATE TABLE IF NOT EXISTS edge_skater_season (
    player_id  INTEGER NOT NULL,
    season_id  INTEGER NOT NULL,
    has_data   BOOLEAN NOT NULL DEFAULT false,   -- false when the NHL had nothing for this player-season
    fetched_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (player_id, season_id)
);
CREATE TABLE IF NOT EXISTS edge_goalie_season (
    player_id  INTEGER NOT NULL,
    season_id  INTEGER NOT NULL,
    has_data   BOOLEAN NOT NULL DEFAULT false,
    fetched_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (player_id, season_id)
);
ALTER TABLE edge_skater_season ADD COLUMN IF NOT EXISTS extras_at TIMESTAMPTZ;   -- when the speed-detail extras were fetched
