# EdgeIQ -- Quantitative Sports Betting Analytics Engine

> Self-directed quantitative analytics project. All data is synthetic/simulated.
> Designed to demonstrate enterprise-grade sports analytics architecture and domain expertise.

## What It Does

Identifies mathematically profitable betting opportunities by combining statistical prediction models, real-time cross-book odds comparison, NLP-powered injury analysis, and Kelly-optimal bet sizing -- then proves the edge was real by tracking closing line value.

## The Problem This Solves

| Who | Pain Point | Cost |
|---|---|---|
| **Sportsbook operators** | Stale lines exploited by sharps before injury news is priced in | $2-5B/yr industry-wide in mispriced liability |
| **Quantitative betting firms** | No systematic way to prove model edge vs luck (CLV tracking) | Misallocated bankroll, blown funds |
| **Analytics platforms** | Manual injury parsing is slow -- lines move in seconds, reports take minutes | Subscribers get stale picks, churn |
| **Risk managers** | Correlated parlay exposure is priced independently across markets | Unhedged tail risk on correlated outcomes |

## Core Modules

### 1. +EV Discrepancy Engine (`src/engines/ev_engine.py`)
Compares model-generated probabilities against real-time sportsbook odds to surface positive expected value opportunities. Calculates true EV after vig removal, not just line shopping.

### 2. Statistical Prediction Models (`src/models/`)
- **Game predictor**: Poisson-based score prediction + XGBoost classifier for moneyline/spread/total
- **Player projector**: Usage-rate adjusted projections for props markets
- **Feature engineering**: 140+ features including rest days, travel distance, pace factors, referee tendencies

### 3. LLM Injury & Narrative Parser (`src/intelligence/narrative_parser.py`)
Claude API integration that:
- Parses injury reports, press conferences, and beat reporter tweets
- Quantifies impact on win probability and player props
- Detects "questionable" vs "doubtful" vs "out" sentiment faster than manual reading
- Outputs structured JSON with confidence scores

### 4. Contextual Split & Usage Model (`src/intelligence/contextual_splits.py`)
SQL-driven situational analysis:
- Home/away, rest days, back-to-back, divisional, indoor/outdoor
- Pace-adjusted stats (per-100-possessions for NBA, per-60 for NHL)
- Referee/umpire tendencies by call type
- Weather impact models for outdoor sports

### 5. Correlated Parlay Builder (`src/engines/parlay_builder.py`)
Identifies legs that are positively correlated but priced independently:
- Game total OVER + player points OVER (pace correlation)
- Underdog ML + UNDER (game script correlation)
- Calculates true parlay probability vs book-offered odds
- Flags exploitable correlation gaps

### 6. Kelly Criterion Bet Sizer (`src/engines/bet_sizer.py`)
Optimal bankroll allocation:
- Full Kelly, fractional Kelly (1/4, 1/2), and fixed-unit modes
- Simultaneous Kelly for multiple concurrent bets
- Drawdown-adjusted sizing based on current bankroll vs peak
- Risk-of-ruin calculations at configurable confidence levels

### 7. Closing Line Value Tracker (`src/engines/clv_tracker.py`)
The only metric that proves long-term edge:
- Captures odds at bet placement vs market close
- Calculates CLV in both implied-probability and cents
- Rolling 30/90/365-day CLV with statistical significance tests
- Separates CLV by sport, bet type, and sportsbook

## Architecture

```
                    +------------------+
                    |   Streamlit UI   |
                    +--------+---------+
                             |
                    +--------v---------+
                    |    FastAPI        |
                    |  (REST + WebSocket)|
                    +--------+---------+
                             |
          +------------------+------------------+
          |                  |                  |
+---------v------+  +--------v-------+  +-------v--------+
|  EV Engine     |  | Prediction     |  | Intelligence   |
|  Bet Sizer     |  | Models         |  | (Claude API)   |
|  Parlay Builder|  | (XGBoost)      |  | Narrative NLP  |
|  CLV Tracker   |  |                |  | Context Splits |
+--------+-------+  +--------+-------+  +-------+--------+
         |                   |                   |
         +-------------------+-------------------+
                             |
                    +--------v---------+
                    |   PostgreSQL     |
                    |  + TimescaleDB   |
                    +--------+---------+
                             |
                    +--------v---------+
                    |     Redis        |
                    | (cache + pubsub) |
                    +------------------+

Background: Celery workers poll odds APIs every 30s,
            run model inference on schedule,
            publish alerts via Redis pub/sub
```

## Tech Stack

| Layer | Technology | Why |
|---|---|---|
| Language | Python 3.11+ | Unified stack -- statsmodels/scipy replace R, native Claude SDK |
| Database | PostgreSQL 15 + TimescaleDB | Time-series odds snapshots, JSONB for flexible schemas |
| Cache | Redis 7 | Sub-ms odds lookups, pub/sub for real-time alerts |
| API | FastAPI | Async, auto-docs, WebSocket support for live feeds |
| ML | XGBoost + scikit-learn | Gradient boosting for game prediction, logistic for props |
| NLP | Claude API (Anthropic) | Injury report parsing, narrative sentiment extraction |
| Dashboard | Streamlit | Free, Python-native, no licensing (upgradeable to Plotly Dash) |
| Jobs | Celery + Redis | Scheduled odds polling, model retraining, alert dispatch |
| Deploy | Docker + docker-compose | Single-command local setup, production-ready |

## Database Schema

Six migration files in `schema/` covering 20 tables:

| File | Tables | Purpose |
|---|---|---|
| `001_core.sql` | leagues, teams, players, games | Reference data |
| `002_odds.sql` | sportsbooks, odds_snapshots, player_prop_snapshots | Time-series odds with TimescaleDB hypertables |
| `003_models.sql` | model_predictions, player_projections, feature_sets | ML model outputs |
| `004_bets.sql` | bets, bet_legs, bet_results, bankroll_ledger | Bet tracking and P&L |
| `005_intelligence.sql` | injury_reports, parsed_narratives, contextual_splits, news_signals | NLP and situational data |
| `006_analytics.sql` | clv_records, model_performance, ev_opportunities, correlation_pairs | Analytics and tracking |

## Quick Start

```bash
# Clone and configure
git clone https://github.com/JonJonz7/sports-betting-analytics.git
cd sports-betting-analytics
cp .env.example .env  # Add your API keys

# Start infrastructure
docker-compose up -d  # PostgreSQL + Redis

# Install dependencies
pip install -e ".[dev]"

# Run migrations
psql $DATABASE_URL -f schema/001_core.sql
psql $DATABASE_URL -f schema/002_odds.sql
# ... etc

# Start the API
uvicorn src.api.main:app --reload

# Start the dashboard
streamlit run src/dashboard/app.py

# Run tests
pytest tests/ -v
```

## Project Structure

```
sports-betting-analytics/
|-- README.md
|-- ARCHITECTURE.md              # Detailed system design
|-- BUILD_INSTRUCTIONS.md        # Step-by-step build guide with Claude prompts
|-- pyproject.toml
|-- docker-compose.yml
|-- .env.example
|-- .gitignore
|-- schema/
|   |-- 001_core.sql
|   |-- 002_odds.sql
|   |-- 003_models.sql
|   |-- 004_bets.sql
|   |-- 005_intelligence.sql
|   +-- 006_analytics.sql
|-- src/
|   |-- __init__.py
|   |-- config.py
|   |-- ingestion/
|   |   |-- odds_poller.py       # Real-time odds collection
|   |   +-- injury_scraper.py    # Injury feed ingestion
|   |-- models/
|   |   |-- game_predictor.py    # Poisson + XGBoost game models
|   |   |-- player_projector.py  # Usage-rate player props
|   |   +-- feature_engineering.py
|   |-- engines/
|   |   |-- ev_engine.py         # +EV identification
|   |   |-- bet_sizer.py         # Kelly criterion sizing
|   |   |-- parlay_builder.py    # Correlated parlay detection
|   |   +-- clv_tracker.py       # Closing line value
|   |-- intelligence/
|   |   |-- narrative_parser.py  # Claude API injury NLP
|   |   +-- contextual_splits.py # Situational SQL analytics
|   |-- api/
|   |   |-- main.py
|   |   +-- routes/
|   |       |-- predictions.py
|   |       |-- opportunities.py
|   |       +-- analytics.py
|   +-- dashboard/
|       +-- app.py               # Streamlit dashboard
|-- tests/
|   |-- test_ev_engine.py
|   |-- test_bet_sizer.py
|   +-- test_clv_tracker.py
+-- scripts/
    |-- seed_data.py             # Generate synthetic data
    +-- backtest.py              # Historical backtesting
```

## Key Formulas

**Expected Value:**
```
EV = (model_prob x (decimal_odds - 1)) - (1 - model_prob)
```

**Kelly Criterion (optimal bet size):**
```
f* = (b*p - q) / b
where b = decimal_odds - 1, p = win_probability, q = 1 - p
```

**Closing Line Value:**
```
CLV = (closing_implied_prob - bet_implied_prob) / closing_implied_prob x 100
```

**Poisson Game Total:**
```
P(X = k) = (lambda^k * e^-lambda) / k!
where lambda = team's adjusted scoring rate
```

## License

MIT
