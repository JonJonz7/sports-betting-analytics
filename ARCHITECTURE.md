# Architecture -- EdgeIQ Sports Betting Analytics

## System Overview

EdgeIQ is a pipeline-based analytics system with five stages:

```
INGEST --> MODEL --> DETECT --> SIZE --> TRACK
```

1. **INGEST**: Poll sportsbook APIs + scrape injury feeds every 30s
2. **MODEL**: Run statistical models to generate true probabilities
3. **DETECT**: Compare model probabilities vs market odds to find +EV
4. **SIZE**: Calculate optimal bet size via Kelly Criterion
5. **TRACK**: Record bets, measure CLV, prove long-term edge

## Data Flow

```
External APIs                    Internal Pipeline
+-------------+                  +------------------+
| The Odds API| --30s poll--->   | odds_poller      |
| ESPN API    |                  | (Celery worker)  |
| Injury feeds|                  +--------+---------+
+-------------+                           |
                                          v
                                 +--------+---------+
                                 |   PostgreSQL     |
                                 |  odds_snapshots  |
                                 |  (TimescaleDB)   |
                                 +--------+---------+
                                          |
                              +-----------+-----------+
                              |                       |
                     +--------v-------+      +--------v--------+
                     | game_predictor |      | narrative_parser |
                     | (XGBoost)      |      | (Claude API)     |
                     +--------+-------+      +--------+---------+
                              |                       |
                              v                       v
                     +--------+-------+      +--------+---------+
                     | model_         |      | parsed_          |
                     | predictions    |      | narratives       |
                     +--------+-------+      +--------+---------+
                              |                       |
                              +----------+------------+
                                         |
                                +--------v---------+
                                |   ev_engine      |
                                | (compare model   |
                                |  vs market odds) |
                                +--------+---------+
                                         |
                              +----------+----------+
                              |                     |
                     +--------v-------+    +--------v--------+
                     | bet_sizer      |    | parlay_builder  |
                     | (Kelly)        |    | (correlation)   |
                     +--------+-------+    +--------+--------+
                              |                     |
                              +----------+----------+
                                         |
                                +--------v---------+
                                |  Alert / API     |
                                | (Redis pub/sub)  |
                                +--------+---------+
                                         |
                                +--------v---------+
                                |  clv_tracker     |
                                | (post-settlement)|
                                +------------------+
```

## Component Deep Dives

### 1. Odds Ingestion (`src/ingestion/odds_poller.py`)

**Frequency**: Every 30 seconds per sport during live windows
**Source**: The Odds API (supports 40+ sportsbooks)
**Storage**: TimescaleDB hypertable partitioned by day

Why TimescaleDB:
- Odds data is inherently time-series (same market, different prices over time)
- Need efficient queries like "what were the odds at T-5 minutes?"
- Compression: 10:1 ratio on historical odds data
- Continuous aggregates for pre-computed rollups

**Rate limiting**: 500 requests/month on free tier. Celery beat schedules:
- NFL/NBA/MLB: Every 30s during game windows
- Props: Every 60s (higher cardinality)
- Off-hours: Every 5 minutes

### 2. Statistical Models (`src/models/`)

**Game Predictor** (two-stage):

Stage 1 -- Poisson score model:
- Each team's expected goals/points modeled as Poisson(lambda)
- Lambda derived from: offensive rating, defensive rating, pace, rest, venue
- Produces probability distribution over all possible scores
- Used for totals and spread markets

Stage 2 -- XGBoost classifier:
- 140+ features per game
- Target: moneyline outcome (home win / away win / draw)
- Trained on 5+ seasons of historical data
- Outputs calibrated probabilities via Platt scaling

**Player Projector**:
- Usage-rate adjusted minutes projection
- Per-minute stat rates x projected minutes = stat projection
- Adjustments: opponent defensive ranking, pace, blowout risk (reduced minutes)

**Feature Engineering** (key features):
```
rest_days               -- 0 = back-to-back, 1 = normal, 2+ = extra rest
travel_distance_miles   -- haversine from last game city
home_court_advantage    -- venue-specific historical edge
pace_factor             -- possessions per 48 min (NBA) or plays per game (NFL)
opponent_def_rating     -- points allowed per 100 possessions
referee_tendency        -- foul rate, over/under tendency by crew
injury_impact_score     -- from narrative_parser, 0-1 scale
line_movement_velocity  -- how fast the line is moving (sharp signal)
public_betting_pct      -- consensus percentage (fade-the-public signal)
weather_wind_speed      -- outdoor sports only
```

### 3. +EV Discrepancy Engine (`src/engines/ev_engine.py`)

The core value proposition. Steps:

1. Get model probability for outcome X (e.g., home team wins at 58%)
2. Get best available odds across all tracked sportsbooks
3. Remove vig to get implied probability
4. Calculate: `EV = (0.58 x (decimal_odds - 1)) - 0.42`
5. If EV > configurable threshold (default: +2%), flag as opportunity

**Vig removal methods**:
- Additive: `fair_prob = implied_prob / sum(all_implied_probs)`
- Multiplicative: `fair_prob = implied_prob^(1/overround)`
- Shin method: accounts for favorite-longshot bias
- Power method: market-specific calibration

**Edge confidence scoring**:
```
confidence = base_ev_score
           + clv_history_bonus      (model has proven CLV on this market type)
           + volume_bonus           (high-liquidity market = more efficient = edge more meaningful)
           - stale_line_penalty     (odds haven't moved in 10+ min = possible trap)
           - injury_uncertainty     (narrative_parser flagged ambiguous status)
```

### 4. Intelligence Layer (`src/intelligence/`)

**Narrative Parser** (Claude API):

Prompt engineering for structured extraction:
```
Input:  "Luka Doncic (ankle) is listed as questionable for tonight.
         He participated in shootaround but was limping."

Output: {
    "player": "Luka Doncic",
    "injury": "ankle",
    "status": "questionable",
    "sentiment": "likely_out",
    "confidence": 0.65,
    "impact_score": 0.82,
    "source_reliability": "beat_reporter",
    "affected_markets": ["DAL_ML", "DAL_spread", "luka_points_ou"]
}
```

**Contextual Splits**:
All SQL-driven for speed. Pre-computed materialized views:
```sql
-- Example: NBA team performance on back-to-backs
SELECT team_id,
       AVG(points_scored) as avg_pts_b2b,
       AVG(points_scored) FILTER (WHERE rest_days >= 1) as avg_pts_rested,
       AVG(points_scored) - AVG(points_scored) FILTER (WHERE rest_days >= 1) as b2b_penalty
FROM game_stats
WHERE rest_days = 0
GROUP BY team_id
HAVING COUNT(*) >= 10;
```

### 5. Correlated Parlay Builder

**Correlation detection**:
- Historical co-occurrence analysis (when A hits, how often does B hit?)
- Pearson correlation on continuous outcomes (points, yards, rebounds)
- Minimum sample size: 30 games for correlation to be actionable

**Example correlations (NBA)**:
```
Game OVER + Star player points OVER   r = +0.42  (pace drives both)
Underdog ML + Game UNDER              r = +0.31  (game script: underdog slows pace)
Player assists OVER + Team wins       r = +0.28  (ball movement = winning)
```

**Parlay EV calculation**:
```
true_parlay_prob = joint_probability (accounting for correlation)
book_parlay_prob = product of individual implied probs (assumes independence)
parlay_ev = (true_parlay_prob / book_parlay_prob) - 1
```

### 6. CLV Tracking

The gold standard for measuring betting skill.

**Why CLV matters**:
- Beating the closing line consistently = proven edge
- Even if individual bets lose, positive CLV = long-term profitability
- CLV > 0 over 1000+ bets is statistically significant evidence of skill

**Statistical tests**:
- One-sample t-test: Is mean CLV significantly > 0?
- Bootstrap confidence interval: 95% CI on true CLV
- Runs test: Is CLV sequence random or does it show streaks?

## Scaling Considerations

| Component | Current | Scale Target |
|---|---|---|
| Odds polling | 1 Celery worker | 10 workers, geo-distributed |
| Model inference | Single-threaded | GPU batch inference, <100ms latency |
| Database | Single PostgreSQL | Read replicas + connection pooling (PgBouncer) |
| Cache | Single Redis | Redis Cluster for HA |
| API | Single FastAPI process | Kubernetes + horizontal scaling |
| Alerts | Redis pub/sub | Kafka for durability + replay |

## Security

- API keys stored in environment variables, never committed
- Database credentials via Docker secrets in production
- Rate limiting on API endpoints (100 req/min per user)
- Input validation on all bet parameters (no negative amounts, valid odds ranges)
- Audit log on all bet placements and bankroll changes
