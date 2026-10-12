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
