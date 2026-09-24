-- ============================================================
-- 002_odds.sql -- Odds data: sportsbooks, snapshots, props
-- Requires TimescaleDB extension for hypertables
-- ============================================================

CREATE EXTENSION IF NOT EXISTS timescaledb;

-- Sportsbook registry
CREATE TABLE sportsbooks (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name            TEXT NOT NULL UNIQUE,        -- 'DraftKings', 'FanDuel', 'BetMGM'
    api_key         TEXT NOT NULL,               -- identifier in odds API
    max_bet_limit   NUMERIC(12,2),               -- typical max bet allowed
    speed_to_limit  TEXT,                        -- 'fast', 'moderate', 'slow'
    clv_tolerance   REAL,                        -- how much CLV before limiting
    active          BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Game-level odds snapshots (moneyline, spread, total)
-- This is a TimescaleDB hypertable partitioned by captured_at
CREATE TABLE odds_snapshots (
    captured_at     TIMESTAMPTZ NOT NULL,
    game_id         UUID NOT NULL REFERENCES games(id),
    sportsbook_id   UUID NOT NULL REFERENCES sportsbooks(id),
    market_type     TEXT NOT NULL,               -- 'moneyline', 'spread', 'total'

    -- Odds values (American format stored, converted at query time)
    home_odds       INTEGER,                     -- American odds: -110, +150, etc.
    away_odds       INTEGER,
    draw_odds       INTEGER,                     -- soccer/hockey regulation

    -- Spread / total specific
    spread_value    REAL,                        -- -3.5, +7, etc.
    total_value     REAL,                        -- 215.5, 45.5, etc.
    over_odds       INTEGER,
    under_odds      INTEGER,

    -- Derived at write time
    home_implied    REAL,                        -- implied probability (0-1)
    away_implied    REAL,
    overround       REAL,                        -- vig percentage (e.g., 1.045)

    PRIMARY KEY (captured_at, game_id, sportsbook_id, market_type)
);

-- Convert to TimescaleDB hypertable (7-day chunks)
SELECT create_hypertable('odds_snapshots', 'captured_at',
    chunk_time_interval => INTERVAL '7 days',
    if_not_exists => TRUE
);

-- Compression policy: compress chunks older than 30 days
ALTER TABLE odds_snapshots SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'game_id, sportsbook_id, market_type',
    timescaledb.compress_orderby = 'captured_at DESC'
);

SELECT add_compression_policy('odds_snapshots', INTERVAL '30 days',
    if_not_exists => TRUE
);

-- Player prop snapshots
CREATE TABLE player_prop_snapshots (
    captured_at     TIMESTAMPTZ NOT NULL,
    game_id         UUID NOT NULL REFERENCES games(id),
    player_id       UUID NOT NULL REFERENCES players(id),
    sportsbook_id   UUID NOT NULL REFERENCES sportsbooks(id),
    prop_type       TEXT NOT NULL,               -- 'points', 'rebounds', 'passing_yards', etc.
    line_value      REAL NOT NULL,               -- 24.5, 275.5, etc.
    over_odds       INTEGER NOT NULL,            -- American odds
    under_odds      INTEGER NOT NULL,
    over_implied    REAL,
    under_implied   REAL,

    PRIMARY KEY (captured_at, game_id, player_id, sportsbook_id, prop_type)
);

SELECT create_hypertable('player_prop_snapshots', 'captured_at',
    chunk_time_interval => INTERVAL '7 days',
    if_not_exists => TRUE
);

-- Indexes for common query patterns
CREATE INDEX idx_odds_game_time ON odds_snapshots (game_id, captured_at DESC);
CREATE INDEX idx_odds_book_market ON odds_snapshots (sportsbook_id, market_type, captured_at DESC);
CREATE INDEX idx_props_player_time ON player_prop_snapshots (player_id, captured_at DESC);
CREATE INDEX idx_props_game ON player_prop_snapshots (game_id, captured_at DESC);

-- Continuous aggregate: latest odds per market (materialized view refreshed every 60s)
CREATE MATERIALIZED VIEW latest_odds AS
SELECT DISTINCT ON (game_id, sportsbook_id, market_type)
    captured_at,
    game_id,
    sportsbook_id,
    market_type,
    home_odds,
    away_odds,
    spread_value,
    total_value,
    over_odds,
    under_odds,
    home_implied,
    away_implied,
    overround
FROM odds_snapshots
ORDER BY game_id, sportsbook_id, market_type, captured_at DESC;

CREATE UNIQUE INDEX idx_latest_odds ON latest_odds (game_id, sportsbook_id, market_type);
