-- ============================================================
-- 003_models.sql -- Model predictions, projections, feature sets
-- ============================================================

-- Model registry (track which model version produced which predictions)
CREATE TABLE model_registry (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name            TEXT NOT NULL,               -- 'nba_game_xgb_v3', 'nfl_player_proj_v2'
    version         TEXT NOT NULL,
    sport           TEXT NOT NULL,
    model_type      TEXT NOT NULL,               -- 'game_outcome', 'player_props', 'total'
    hyperparams     JSONB DEFAULT '{}',
    training_window TEXT,                        -- '2019-2024' seasons
    validation_metrics JSONB DEFAULT '{}',       -- accuracy, log_loss, brier_score
    active          BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (name, version)
);

-- Game-level predictions
CREATE TABLE model_predictions (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    model_id        UUID NOT NULL REFERENCES model_registry(id),
    game_id         UUID NOT NULL REFERENCES games(id),
    predicted_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Probabilities (0-1, must sum to ~1)
    home_win_prob   REAL NOT NULL,
    away_win_prob   REAL NOT NULL,
    draw_prob       REAL DEFAULT 0,

    -- Score predictions
    home_score_pred REAL,
    away_score_pred REAL,
    total_pred      REAL,                        -- predicted game total
    spread_pred     REAL,                        -- predicted spread (negative = home favored)

    -- Confidence
    confidence      REAL,                        -- model's self-assessed confidence (0-1)

    -- Was this prediction correct? (populated post-game)
    correct_ml      BOOLEAN,
    correct_spread  BOOLEAN,
    correct_total   BOOLEAN,

    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (model_id, game_id)
);

CREATE INDEX idx_predictions_game ON model_predictions(game_id);
CREATE INDEX idx_predictions_model ON model_predictions(model_id, predicted_at DESC);

-- Player-level projections
CREATE TABLE player_projections (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    model_id        UUID NOT NULL REFERENCES model_registry(id),
    game_id         UUID NOT NULL REFERENCES games(id),
    player_id       UUID NOT NULL REFERENCES players(id),
    projected_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Projected stats (sport-agnostic via JSONB)
    projections     JSONB NOT NULL,              -- {"points": 24.5, "rebounds": 8.2, "assists": 6.1}

    -- Minutes projection (key driver)
    projected_minutes REAL,

    -- Confidence
    confidence      REAL,

    -- Actuals (populated post-game)
    actuals         JSONB,                       -- {"points": 28, "rebounds": 7, "assists": 9}

    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (model_id, game_id, player_id)
);

CREATE INDEX idx_projections_player ON player_projections(player_id);
CREATE INDEX idx_projections_game ON player_projections(game_id);

-- Feature sets (stored for reproducibility and debugging)
CREATE TABLE feature_sets (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    game_id         UUID NOT NULL REFERENCES games(id),
    generated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    features        JSONB NOT NULL,              -- full feature vector as JSON
    feature_version TEXT NOT NULL,               -- 'v3.2' -- feature engineering version
    UNIQUE (game_id, feature_version)
);
