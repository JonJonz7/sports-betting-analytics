# Architecture

## What runs today (batch)

```
nflverse games.csv ──► ingest ──► data/landing/<source>/games_<date>_<sha>.csv.gz   (exact bytes)
                          │
                          └──► data/lake/bronze/games/season=YYYY/*.parquet        (typed, idempotent)
                               data/lake/_manifest.jsonl                           (lineage)
                                      │
                               quality gate (8 checks)  ── fail = stop
                                      │
                               transform runner (sql/models.toml) into DuckDB:
                                 staging.stg_games ─► staging.stg_team_games
                                 features.elo_ratings      (Python)
                                 marts.fct_games
                                 marts.predictions         (Python, walk-forward)
                                 marts.model_vs_market
                                      │
                               backtest ─► marts.backtest_bets / backtest_summary
                                      │
                               reports/report.md · FastAPI · Streamlit
```

Run with `make run` (real data) or `make demo` (synthetic). CI runs the demo on every push; a weekly workflow runs the real pipeline.

## Decisions

**D1. Parquet lake + DuckDB.** Parquet partitions by season make re-ingestion idempotent (replace a partition, never append), and DuckDB queries Parquet directly with no server. *Alternative:* Postgres; heavier to run and unnecessary for ~8k games a year.

**D2. Land raw bytes first.** Exact source bytes plus SHA-256 make every number traceable and the lake rebuildable without re-downloading. A changed upstream file gets a new hash and a new landing file.

**D3. A hand-written transform runner instead of dbt.** Deliberate, for learning: it shows ref resolution, ordering, materialization and tests in ~150 lines, and supports Python models in the same graph. The companion project ([financial-restatement-pipeline](https://github.com/JonJonz7/financial-restatement-pipeline)) uses dbt itself.

**D4. Point-in-time everything.** Elo rows are pre-game; the model is walk-forward by season with a test enforcing `max_train_season < season`. Random train/test splits would leak future information.

**D5. The market is the benchmark, not a feature.** The model must form an independent opinion to be compared with the closing line; including the line as a feature would just copy it.

**D6. Quarantine over deletion.** Impossible prices are flagged (`market_flag`), counted and excluded from modeling, with tests at both ends.

**D7. Uncertainty in every result.** Backtest ROI comes with a bootstrap 95% CI, max drawdown and a baseline strategy.

## Live system (designed, not built)

For real-time use the batch design extends to:

- **Odds capture:** `src/ingestion/odds_poller.py` polls The Odds API (paid key) every 30–300 s and writes snapshots to a time-series table (`schema/002_odds.sql`, TimescaleDB hypertable).
- **Opportunity scan:** `src/engines/ev_engine.scan_for_ev` compares model probabilities with every book's de-vigged price; `bet_sizer` sizes; `clv_tracker` measures CLV once games close.
- **Serving:** the FastAPI app already exposes the calculators; live endpoints would read from Postgres.

None of this runs yet; see docs/ROADMAP.md.
