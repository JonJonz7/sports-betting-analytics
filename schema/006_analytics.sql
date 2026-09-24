-- ============================================================
-- 006_analytics.sql -- CLV records, model performance, EV opps
-- ============================================================

-- CLV tracking records (one per settled bet leg)
CREATE TABLE clv_records (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    bet_leg_id      UUID NOT NULL REFERENCES bet_legs(id),
    game_id         UUID NOT NULL REFERENCES games(id),
    recorded_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Odds comparison
    bet_odds        INTEGER NOT NULL,            -- American odds at bet placement
    closing_odds    INTEGER NOT NULL,            -- American odds at market close
    bet_implied     REAL NOT NULL,               -- implied prob at bet
    closing_implied REAL NOT NULL,               -- implied prob at close

    -- CLV metrics
    clv_cents       REAL NOT NULL,               -- CLV in cents
    clv_pct         REAL NOT NULL,               -- CLV as percentage

    -- Context
    market_type     TEXT NOT NULL,
    sport           TEXT NOT NULL,
    sportsbook_id   UUID NOT NULL REFERENCES sportsbooks(id),
    time_before_close INTERVAL,                  -- how long before game start the bet was placed

    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_clv_time ON clv_records(recorded_at DESC);
CREATE INDEX idx_clv_sport ON clv_records(sport, market_type);

-- Model performance tracking (per model, per time period)
CREATE TABLE model_performance (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    model_id        UUID NOT NULL REFERENCES model_registry(id),
    period_start    DATE NOT NULL,
    period_end      DATE NOT NULL,
    sport           TEXT NOT NULL,
    market_type     TEXT NOT NULL,               -- 'moneyline', 'spread', 'total'

    -- Accuracy metrics
    total_predictions INTEGER NOT NULL,
    correct          INTEGER NOT NULL,
    accuracy         REAL NOT NULL,              -- correct / total
    log_loss         REAL,                       -- calibration quality
    brier_score      REAL,                       -- probability calibration

    -- Profitability metrics (if betting at model's recommended odds)
    simulated_roi    REAL,                       -- return on investment
    avg_clv          REAL,                       -- average CLV of model's picks
    sharpe_ratio     REAL,                       -- risk-adjusted returns

    -- Calibration buckets (predicted prob vs actual outcome rate)
    calibration      JSONB,                      -- [{"bucket": "0.5-0.6", "predicted": 0.55, "actual": 0.53, "n": 120}]

    computed_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (model_id, period_start, period_end, sport, market_type)
);

-- EV opportunities (every +EV opportunity detected, whether bet or not)
CREATE TABLE ev_opportunities (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    detected_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    game_id         UUID NOT NULL REFERENCES games(id),
    player_id       UUID REFERENCES players(id),
    sportsbook_id   UUID NOT NULL REFERENCES sportsbooks(id),
    market_type     TEXT NOT NULL,
    selection       TEXT NOT NULL,               -- 'home', 'over', etc.

    -- EV calculation
    model_prob      REAL NOT NULL,
    market_implied  REAL NOT NULL,
    ev_pct          REAL NOT NULL,               -- (model_prob * (odds-1)) - (1 - model_prob)
    edge_confidence REAL,                        -- composite confidence score

    -- Odds at detection
    odds_at_detection INTEGER NOT NULL,
    line_at_detection REAL,

    -- Kelly sizing
    kelly_full      REAL,
    kelly_quarter   REAL,

    -- Was it acted on?
    bet_placed      BOOLEAN DEFAULT FALSE,
    bet_id          UUID REFERENCES bets(id),

    -- Outcome (populated post-game)
    outcome         TEXT,                        -- 'won', 'lost', 'push'
    closing_odds    INTEGER,
    clv_pct         REAL,

    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_ev_game ON ev_opportunities(game_id);
CREATE INDEX idx_ev_time ON ev_opportunities(detected_at DESC);
CREATE INDEX idx_ev_positive ON ev_opportunities(ev_pct DESC) WHERE ev_pct > 0;

-- Correlation pairs (for parlay builder)
CREATE TABLE correlation_pairs (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    sport           TEXT NOT NULL,
    leg_a_type      TEXT NOT NULL,               -- 'game_total_over'
    leg_b_type      TEXT NOT NULL,               -- 'player_points_over'
    correlation     REAL NOT NULL,               -- Pearson r (-1 to 1)
    sample_size     INTEGER NOT NULL,
    p_value         REAL,
    season          TEXT NOT NULL,
    computed_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (sport, leg_a_type, leg_b_type, season)
);

-- Rolling CLV summary view
CREATE VIEW clv_rolling AS
SELECT
    sport,
    market_type,
    COUNT(*) AS total_bets,
    ROUND(AVG(clv_pct)::NUMERIC, 3) AS avg_clv_pct,
    ROUND(STDDEV(clv_pct)::NUMERIC, 3) AS std_clv_pct,
    ROUND((AVG(clv_pct) / NULLIF(STDDEV(clv_pct) / SQRT(COUNT(*)), 0))::NUMERIC, 2) AS t_stat,
    -- p < 0.05 when |t_stat| > 1.96 for large samples
    CASE
        WHEN COUNT(*) >= 30 AND ABS(AVG(clv_pct) / NULLIF(STDDEV(clv_pct) / SQRT(COUNT(*)), 0)) > 1.96
        THEN 'significant'
        ELSE 'not_significant'
    END AS significance
FROM clv_records
WHERE recorded_at >= NOW() - INTERVAL '90 days'
GROUP BY sport, market_type
ORDER BY avg_clv_pct DESC;

-- Model leaderboard view
CREATE VIEW model_leaderboard AS
SELECT
    mr.name AS model_name,
    mr.version,
    mp.sport,
    mp.market_type,
    mp.total_predictions,
    ROUND(mp.accuracy::NUMERIC * 100, 1) AS accuracy_pct,
    ROUND(mp.brier_score::NUMERIC, 4) AS brier_score,
    ROUND(mp.avg_clv::NUMERIC, 3) AS avg_clv,
    ROUND(mp.simulated_roi::NUMERIC * 100, 1) AS roi_pct,
    ROUND(mp.sharpe_ratio::NUMERIC, 2) AS sharpe
FROM model_performance mp
JOIN model_registry mr ON mr.id = mp.model_id
WHERE mp.period_end >= CURRENT_DATE - 90
ORDER BY mp.avg_clv DESC NULLS LAST;
