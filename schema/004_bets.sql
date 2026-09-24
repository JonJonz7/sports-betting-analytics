-- ============================================================
-- 004_bets.sql -- Bet tracking, legs, results, bankroll
-- ============================================================

-- Individual bets (can be straight or parlay)
CREATE TABLE bets (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    placed_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    sportsbook_id   UUID NOT NULL REFERENCES sportsbooks(id),
    bet_type        TEXT NOT NULL,               -- 'straight', 'parlay', 'teaser'

    -- Sizing
    stake           NUMERIC(12,2) NOT NULL,      -- amount wagered
    potential_payout NUMERIC(12,2) NOT NULL,
    combined_odds   INTEGER NOT NULL,            -- American odds of full bet

    -- Kelly analysis at time of bet
    kelly_fraction  REAL,                        -- what Kelly suggested
    actual_fraction REAL,                        -- what was actually bet (e.g., 1/4 Kelly)
    model_edge      REAL,                        -- EV% at time of bet

    -- Result
    status          TEXT NOT NULL DEFAULT 'pending', -- 'pending', 'won', 'lost', 'push', 'void'
    settled_at      TIMESTAMPTZ,
    profit_loss     NUMERIC(12,2),               -- positive = profit, negative = loss

    -- Metadata
    notes           TEXT,
    tags            TEXT[],                       -- ['nba', 'props', 'injury_play']
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_bets_status ON bets(status);
CREATE INDEX idx_bets_placed ON bets(placed_at DESC);
CREATE INDEX idx_bets_book ON bets(sportsbook_id);

-- Bet legs (for parlays, each leg is a row; straight bets have 1 leg)
CREATE TABLE bet_legs (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    bet_id          UUID NOT NULL REFERENCES bets(id) ON DELETE CASCADE,
    game_id         UUID NOT NULL REFERENCES games(id),
    player_id       UUID REFERENCES players(id), -- NULL for game-level bets

    -- What was bet
    market_type     TEXT NOT NULL,               -- 'moneyline', 'spread', 'total', 'player_prop'
    selection       TEXT NOT NULL,               -- 'home', 'away', 'over', 'under'
    line_value      REAL,                        -- spread or total line
    odds_at_bet     INTEGER NOT NULL,            -- American odds when placed

    -- Model's assessment at time of bet
    model_prob      REAL,                        -- model's estimated probability
    implied_prob    REAL,                        -- market implied probability
    ev_at_bet       REAL,                        -- expected value at time of bet

    -- Closing line (populated at game start)
    closing_odds    INTEGER,                     -- odds at market close
    closing_implied REAL,
    clv_cents       REAL,                        -- CLV in cents (e.g., +3.2 cents)
    clv_pct         REAL,                        -- CLV as percentage

    -- Result
    leg_result      TEXT DEFAULT 'pending',      -- 'won', 'lost', 'push', 'void'
    actual_value    REAL,                        -- actual score/stat for spread/total/prop

    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_legs_bet ON bet_legs(bet_id);
CREATE INDEX idx_legs_game ON bet_legs(game_id);
CREATE INDEX idx_legs_player ON bet_legs(player_id);

-- Bankroll ledger (append-only, every deposit/withdrawal/bet is a row)
CREATE TABLE bankroll_ledger (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    recorded_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    sportsbook_id   UUID REFERENCES sportsbooks(id), -- NULL for total bankroll
    entry_type      TEXT NOT NULL,               -- 'deposit', 'withdrawal', 'bet_placed', 'bet_settled'
    amount          NUMERIC(12,2) NOT NULL,      -- positive = money in, negative = money out
    balance_after   NUMERIC(12,2) NOT NULL,      -- running balance
    bet_id          UUID REFERENCES bets(id),    -- link to bet if applicable
    notes           TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_bankroll_time ON bankroll_ledger(recorded_at DESC);
CREATE INDEX idx_bankroll_book ON bankroll_ledger(sportsbook_id);

-- Bet results summary view
CREATE VIEW bet_summary AS
SELECT
    date_trunc('day', b.placed_at) AS bet_date,
    b.bet_type,
    COUNT(*) AS total_bets,
    SUM(b.stake) AS total_staked,
    SUM(b.profit_loss) FILTER (WHERE b.status IN ('won', 'lost', 'push')) AS net_profit,
    COUNT(*) FILTER (WHERE b.status = 'won') AS wins,
    COUNT(*) FILTER (WHERE b.status = 'lost') AS losses,
    COUNT(*) FILTER (WHERE b.status = 'push') AS pushes,
    ROUND(
        COUNT(*) FILTER (WHERE b.status = 'won')::NUMERIC /
        NULLIF(COUNT(*) FILTER (WHERE b.status IN ('won', 'lost')), 0) * 100,
        1
    ) AS win_pct,
    ROUND(AVG(bl.ev_at_bet)::NUMERIC * 100, 2) AS avg_ev_pct,
    ROUND(AVG(bl.clv_pct)::NUMERIC, 2) AS avg_clv_pct
FROM bets b
LEFT JOIN bet_legs bl ON bl.bet_id = b.id
WHERE b.status != 'pending'
GROUP BY 1, 2
ORDER BY 1 DESC;
