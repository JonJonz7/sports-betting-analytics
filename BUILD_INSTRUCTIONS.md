# Build Instructions -- Prompts for Claude to Build Each Module

This document contains the exact prompts and sequence to build EdgeIQ
from the schema and stubs into a fully functional system.

## Build Order

Build in this sequence -- each step depends on the previous:

1. Database + seed data
2. Odds ingestion pipeline
3. Statistical models (game predictor, player projector)
4. +EV engine (connects models to odds)
5. Intelligence layer (Claude API, contextual splits)
6. Parlay builder
7. CLV tracker
8. API endpoints
9. Dashboard
10. Background jobs (Celery)

---

## Phase 1: Database + Seed Data

### Prompt 1.1 -- Generate synthetic historical data

```
I have a PostgreSQL database with TimescaleDB for a sports betting analytics tool.
Schema files are in schema/ (001 through 006).

Write a Python script `scripts/seed_data.py` that:
1. Connects to PostgreSQL using DATABASE_URL env var
2. Generates 3 seasons of synthetic NBA data:
   - 30 teams with real names, cities, conferences, divisions
   - 450+ players with positions and realistic stats
   - ~1230 games per season (82 games x 30 teams / 2)
   - Realistic scores (90-130 range, home team +3 advantage)
   - Player game stats with realistic distributions
3. Generates odds snapshots for each game:
   - 6 sportsbooks (DraftKings, FanDuel, BetMGM, Caesars, PointsBet, BetRivers)
   - Moneyline, spread, total markets
   - 10-20 snapshots per game (simulating line movement)
   - Realistic vig (~4.5% overround)
4. Uses numpy random with seed for reproducibility

Make all scores and stats follow realistic distributions (not uniform random).
Use Poisson for scores, normal for player stats. Include rest days and travel.
```

### Prompt 1.2 -- Run and verify

```
Run the seed script and verify the data:
- Check row counts match expectations
- Verify odds snapshots are in TimescaleDB hypertable
- Run the clv_rolling and model_leaderboard views
- Fix any issues
```

---

## Phase 2: Odds Ingestion Pipeline

### Prompt 2.1 -- Complete the odds poller

```
File: src/ingestion/odds_poller.py (already has API fetch + parse logic)

Add:
1. Database writer that bulk-inserts OddsSnapshot records into odds_snapshots table
2. Player prop ingestion (The Odds API player props endpoint)
3. Rate limiter that respects the 500 req/month free tier:
   - Track requests in Redis (key: odds_api_requests:{month})
   - Log warning at 80% capacity
   - Hard stop at 95%
4. Deduplication: skip insert if same game+book+market snapshot already exists
   within the last 15 seconds

Write the Celery task that calls this on a schedule:
- Every 30s during NBA game windows (6 PM - 1 AM ET)
- Every 60s for player props
- Every 5 min off-hours
```

---

## Phase 3: Statistical Models

### Prompt 3.1 -- Train the game predictor

```
Files: src/models/game_predictor.py, src/models/feature_engineering.py

Using the synthetic data from the seed script:
1. Build the feature engineering pipeline:
   - For each game, compute all features in FEATURE_COLUMNS
   - Use only data available BEFORE game time (no look-ahead bias)
   - Store feature vectors in feature_sets table

2. Train XGBoost classifier:
   - Train on seasons 1-2, validate on season 3
   - Target: home_win (binary)
   - Use Platt scaling for probability calibration
   - Log metrics: accuracy, log_loss, brier_score, AUC
   - Save model to model_registry table

3. Implement predict_game() that:
   - Computes features for an upcoming game
   - Runs both Poisson model and XGBoost
   - Averages the probabilities (ensemble)
   - Returns GamePrediction with all fields

Print validation metrics. Target: >55% accuracy, brier_score < 0.24
```

### Prompt 3.2 -- Player projector

```
File: src/models/player_projector.py (already has projection logic)

Add:
1. Historical standard deviation calculation from game log
2. Per-opponent defensive adjustment lookup from database
3. Blowout risk model (use spread as proxy: |spread| > 10 = high blowout risk)
4. Batch projection: project all players in a game at once
5. Store projections in player_projections table

Verify: project stats for 5 star players, compare to their season averages.
Projections should be within 15% of actual season averages.
```

---

## Phase 4: +EV Engine

### Prompt 4.1 -- Wire EV engine to live data

```
File: src/engines/ev_engine.py (already has core EV math)

Add:
1. Database integration:
   - Pull latest odds from latest_odds materialized view
   - Pull model predictions from model_predictions table
   - Pull injury impacts from parsed_narratives table

2. Full pipeline function run_ev_scan():
   - For each upcoming game today
   - Get model prediction
   - Get odds from all sportsbooks
   - Run scan_for_ev with Shin vig removal
   - Apply edge confidence scoring
   - Store results in ev_opportunities table
   - Publish alerts via Redis pub/sub for opportunities with EV > 5%

3. Historical EV tracking:
   - After games settle, update ev_opportunities with outcome + closing odds
   - Calculate what the P&L would have been if all opportunities were bet

Test with synthetic data. There should be 5-15 +EV opportunities per night
across 10+ games.
```

---

## Phase 5: Intelligence Layer

### Prompt 5.1 -- Claude API integration

```
File: src/intelligence/narrative_parser.py (already has prompts + parsing)

Add:
1. Batch processing: parse multiple reports in parallel (asyncio.gather)
2. Caching: store parsed results in Redis for 1 hour (same report = same parse)
3. Fallback: if Claude API fails, use estimate_impact_fallback()
4. Cost tracking: log prompt_tokens and response_tokens, estimate cost per parse
5. Database writer: store results in parsed_narratives table

Test with 10 sample injury reports (create fixtures). Verify:
- All 10 return valid NarrativeImpact objects
- impact_score correlates with injury severity
- Star player OUT > starter QUESTIONABLE
```

### Prompt 5.2 -- Contextual splits materialization

```
File: src/intelligence/contextual_splits.py (already has SQL queries)

Add:
1. Materialization job that pre-computes all splits nightly:
   - All 30 teams x 5 split types = 150 computations
   - Store in contextual_splits table
2. Query function that returns splits relevant to a specific game
3. Adjustment calculator: given today's context (home, 0 rest, divisional),
   how should we adjust the team's baseline prediction?

Test: compute splits for 3 teams, verify home/away win% delta is realistic
(NBA home advantage is ~5-7%).
```

---

## Phase 6: Parlay Builder

### Prompt 6.1 -- Compute historical correlations

```
File: src/engines/parlay_builder.py (already has correlation model)

Add:
1. Historical correlation calculator:
   - For each pair of correlated market types
   - Calculate Pearson r from historical game data
   - Require min 30 game sample
   - Store in correlation_pairs table

2. Dynamic correlation updates:
   - Re-compute weekly from the most recent full season
   - Weight recent games more heavily (exponential decay)

3. Three-leg parlay support:
   - Extend calculate_joint_probability to 3 events
   - Use pairwise correlations (simplification of full multivariate)

Test: verify NBA game_total_over + star_points_over correlation is
between 0.30-0.55 on synthetic data.
```

---

## Phase 7: CLV Tracker

### Prompt 7.1 -- Automated CLV pipeline

```
File: src/engines/clv_tracker.py (already has CLV math + stats)

Add:
1. Automated closing line capture:
   - Celery task that snapshots odds 1 minute before game start
   - Marks these as "closing" odds in odds_snapshots

2. Post-settlement CLV calculator:
   - For each settled bet in bet_legs
   - Find the closing odds snapshot
   - Calculate CLV and store in clv_records

3. Dashboard-ready aggregations:
   - CLV by sport, market_type, sportsbook
   - Monthly CLV trend
   - Significance test results

Test: simulate 200 bets from synthetic data, verify CLV summary
produces valid statistics and significance test works.
```

---

## Phase 8: API Endpoints

### Prompt 8.1 -- Complete all endpoints

```
File: src/api/main.py (has route stubs)

Implement all endpoints:
1. GET /api/predictions/{game_id} - return GamePrediction
2. GET /api/opportunities - query ev_opportunities, filter by sport/min_ev
3. GET /api/clv/summary - return CLVSummary for configurable window
4. GET /api/parlays - return correlated parlay opportunities
5. GET /api/splits/{entity_type}/{entity_id} - return contextual splits
6. POST /api/injury/parse - call narrative parser, return NarrativeImpact
7. GET /api/bankroll - return bankroll status from ledger
8. POST /api/bets - record a new bet
9. GET /api/model/performance - return model accuracy metrics

Add:
- Request validation with Pydantic models
- Error handling (404 for unknown games, 503 for DB down)
- Rate limiting (100 req/min)
- WebSocket endpoint for real-time +EV alerts

Test all endpoints with httpx test client.
```

---

## Phase 9: Dashboard

### Prompt 9.1 -- Build full Streamlit dashboard

```
File: src/dashboard/app.py (has tab stubs)

Build out all 5 tabs:

Tab 1 - +EV Opportunities:
- Table of current opportunities sortable by EV%, confidence, odds
- Color coding: green > 5% EV, yellow > 2%, red < 2%
- Click to expand: show Kelly sizing, model probability breakdown
- Auto-refresh every 60 seconds

Tab 2 - CLV Tracker:
- Line chart: rolling 100-bet CLV over time
- Stat cards: avg CLV, t-stat, p-value, beat-close rate
- Bar chart: CLV by sport and market type
- Significance badge (green if p < 0.05)

Tab 3 - Correlated Parlays:
- Table of parlay opportunities with correlation, edge, odds
- Expand to see individual legs and reasoning
- Filter by sport, minimum edge

Tab 4 - Bankroll & P/L:
- Cumulative P&L line chart
- Drawdown chart (% from peak)
- Stat cards: total bankroll, net P/L, ROI, Sharpe ratio
- By-sport breakdown table

Tab 5 - Model Performance:
- Accuracy, Brier score, log loss by sport/market
- Calibration chart (predicted prob vs actual outcome rate)
- Model comparison table if multiple versions exist

Use plotly for all charts. Dark theme. Fetch all data from FastAPI endpoints.
```

---

## Phase 10: Background Jobs

### Prompt 10.1 -- Celery worker setup

```
Create src/worker.py with Celery configuration:

Tasks:
1. poll_odds: runs every 30s during game windows
2. run_predictions: runs 2 hours before first game of the day
3. run_ev_scan: runs every 60s (after odds update)
4. capture_closing_lines: runs 1 min before each game start
5. settle_bets: runs every 5 min, checks for completed games
6. compute_clv: runs after bet settlement
7. refresh_splits: runs nightly at 4 AM

Include:
- Celery beat schedule
- Error handling with retries (max 3)
- Dead letter queue for failed tasks
- Monitoring via Flower (optional)

Write the Dockerfile and add celery worker + beat to docker-compose.yml.
```

---

## Final Verification

### Prompt -- End-to-end test

```
Run the full pipeline end-to-end:
1. Seed the database with synthetic data
2. Start the API, dashboard, and Celery worker
3. Trigger an odds poll
4. Run model predictions for today's games
5. Run the EV scan
6. Verify opportunities appear in the dashboard
7. Simulate placing a bet via API
8. Settle the game
9. Verify CLV is calculated
10. Check the bankroll ledger updated

Report any failures and fix them.
```
