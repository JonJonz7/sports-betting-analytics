-- ============================================================
-- 001_core.sql -- Reference data: leagues, teams, players, games
-- ============================================================

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Leagues / sports
CREATE TABLE leagues (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name            TEXT NOT NULL UNIQUE,        -- 'NFL', 'NBA', 'MLB', 'NHL', 'NCAAF', 'NCAAB'
    sport           TEXT NOT NULL,               -- 'football', 'basketball', 'baseball', 'hockey'
    api_key         TEXT NOT NULL,               -- key used in The Odds API
    active          BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Teams
CREATE TABLE teams (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    league_id       UUID NOT NULL REFERENCES leagues(id),
    name            TEXT NOT NULL,               -- 'Los Angeles Lakers'
    abbreviation    TEXT NOT NULL,               -- 'LAL'
    city            TEXT,
    state           TEXT,
    venue           TEXT,                        -- home venue name
    latitude        DOUBLE PRECISION,            -- for travel distance calc
    longitude       DOUBLE PRECISION,
    conference      TEXT,
    division        TEXT,
    active          BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (league_id, abbreviation)
);

-- Players
CREATE TABLE players (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    team_id         UUID REFERENCES teams(id),   -- NULL if free agent
    league_id       UUID NOT NULL REFERENCES leagues(id),
    full_name       TEXT NOT NULL,
    position        TEXT,                        -- 'PG', 'QB', 'SP', etc.
    jersey_number   SMALLINT,
    status          TEXT DEFAULT 'active',       -- 'active', 'injured', 'inactive'
    external_ids    JSONB DEFAULT '{}',          -- ESPN ID, SR ID, etc.
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_players_team ON players(team_id);
CREATE INDEX idx_players_name ON players(full_name);

-- Games / events
CREATE TABLE games (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    league_id       UUID NOT NULL REFERENCES leagues(id),
    external_id     TEXT,                        -- API-provided game ID
    home_team_id    UUID NOT NULL REFERENCES teams(id),
    away_team_id    UUID NOT NULL REFERENCES teams(id),
    scheduled_at    TIMESTAMPTZ NOT NULL,
    venue           TEXT,
    status          TEXT DEFAULT 'scheduled',    -- 'scheduled', 'live', 'final', 'postponed'

    -- Final results (populated post-game)
    home_score      SMALLINT,
    away_score      SMALLINT,
    overtime        BOOLEAN DEFAULT FALSE,

    -- Contextual factors (populated pre-game)
    home_rest_days  SMALLINT,                    -- days since last game
    away_rest_days  SMALLINT,
    weather         JSONB,                       -- outdoor sports: temp, wind, precip
    referee_crew    TEXT,

    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (league_id, external_id)
);

CREATE INDEX idx_games_scheduled ON games(scheduled_at);
CREATE INDEX idx_games_league_date ON games(league_id, scheduled_at);
CREATE INDEX idx_games_teams ON games(home_team_id, away_team_id);

-- Game-level player stats (post-game)
CREATE TABLE player_game_stats (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    game_id         UUID NOT NULL REFERENCES games(id),
    player_id       UUID NOT NULL REFERENCES players(id),
    team_id         UUID NOT NULL REFERENCES teams(id),
    minutes         REAL,
    stats           JSONB NOT NULL DEFAULT '{}', -- sport-specific: points, yards, hits, etc.
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (game_id, player_id)
);

CREATE INDEX idx_pgs_player ON player_game_stats(player_id);
CREATE INDEX idx_pgs_game ON player_game_stats(game_id);
