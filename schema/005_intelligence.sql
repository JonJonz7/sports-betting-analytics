-- ============================================================
-- 005_intelligence.sql -- Injury reports, narratives, splits, news
-- ============================================================

-- Raw injury reports (from official sources)
CREATE TABLE injury_reports (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    player_id       UUID NOT NULL REFERENCES players(id),
    game_id         UUID REFERENCES games(id),
    reported_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    source          TEXT NOT NULL,               -- 'official_report', 'beat_reporter', 'press_conf'
    status          TEXT NOT NULL,               -- 'out', 'doubtful', 'questionable', 'probable', 'available'
    injury_type     TEXT,                        -- 'ankle', 'hamstring', 'illness', 'rest'
    raw_text        TEXT,                        -- original report text
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_injuries_player ON injury_reports(player_id, reported_at DESC);
CREATE INDEX idx_injuries_game ON injury_reports(game_id);

-- Claude-parsed narrative analysis
CREATE TABLE parsed_narratives (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    injury_report_id UUID REFERENCES injury_reports(id),
    parsed_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Structured extraction from Claude
    player_name     TEXT NOT NULL,
    injury_detail   TEXT,
    official_status TEXT,                        -- what the team listed
    llm_sentiment   TEXT NOT NULL,               -- 'likely_playing', 'likely_limited', 'likely_out', 'uncertain'
    confidence      REAL NOT NULL,               -- 0-1, Claude's self-assessed confidence
    impact_score    REAL NOT NULL,               -- 0-1, estimated impact on team performance

    -- Market impact assessment
    affected_markets TEXT[] DEFAULT '{}',         -- ['DAL_ML', 'DAL_spread', 'luka_points_ou']
    win_prob_shift  REAL,                        -- e.g., -0.08 = team loses 8% win probability
    total_shift     REAL,                        -- e.g., -3.5 = total drops 3.5 points

    -- Raw Claude response
    llm_response    JSONB,
    model_used      TEXT,                        -- 'claude-sonnet-4-6'
    prompt_tokens   INTEGER,
    response_tokens INTEGER,

    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_narratives_player ON parsed_narratives(player_name);
CREATE INDEX idx_narratives_time ON parsed_narratives(parsed_at DESC);

-- Pre-computed contextual splits
CREATE TABLE contextual_splits (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    entity_type     TEXT NOT NULL,               -- 'team', 'player'
    entity_id       UUID NOT NULL,               -- team_id or player_id
    league_id       UUID NOT NULL REFERENCES leagues(id),
    split_type      TEXT NOT NULL,               -- 'home_away', 'rest_days', 'division', 'indoor_outdoor'
    split_value     TEXT NOT NULL,               -- 'home', '0_rest', 'vs_division', 'outdoor'
    season          TEXT NOT NULL,               -- '2024-25'
    sample_size     INTEGER NOT NULL,

    -- Aggregated stats
    stats           JSONB NOT NULL,              -- sport-specific aggregated stats
    /*
        NBA example: {
            "avg_points": 112.3,
            "avg_total": 221.5,
            "win_pct": 0.62,
            "ats_record": "18-12",
            "ou_record": "16-14",
            "avg_margin": 4.2
        }
    */

    computed_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (entity_type, entity_id, split_type, split_value, season)
);

CREATE INDEX idx_splits_entity ON contextual_splits(entity_type, entity_id);
CREATE INDEX idx_splits_type ON contextual_splits(split_type, split_value);

-- News signals (broader than injury -- trades, suspensions, coaching changes)
CREATE TABLE news_signals (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    published_at    TIMESTAMPTZ NOT NULL,
    source          TEXT NOT NULL,               -- 'espn', 'twitter', 'beat_reporter'
    headline        TEXT NOT NULL,
    body            TEXT,
    entities        JSONB DEFAULT '[]',          -- [{"type": "player", "id": "...", "name": "..."}, ...]
    signal_type     TEXT,                        -- 'injury', 'trade', 'suspension', 'lineup', 'weather'
    sentiment       TEXT,                        -- 'positive', 'negative', 'neutral'
    impact_score    REAL,                        -- 0-1
    processed       BOOLEAN DEFAULT FALSE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_news_time ON news_signals(published_at DESC);
CREATE INDEX idx_news_type ON news_signals(signal_type);
CREATE INDEX idx_news_unprocessed ON news_signals(processed) WHERE NOT processed;
