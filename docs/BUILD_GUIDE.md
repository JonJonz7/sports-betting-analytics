# Build guide: from an empty folder to EdgeIQ

The order this project is built in, what to do at each step, why, and how you know a step is finished. Each phase ends in something that runs. Rebuild it yourself; the repo is the reference answer.

**Time:** about 5 weeks at 1–2 hours a day. **You need:** Python 3.11, git.

| Phase | You build | Done when |
|---|---|---|
| 0 | The question and the rules of a fair test | You can explain why the market is the benchmark and what "look-ahead" means |
| 1 | Skeleton + tooling | `make lint test` runs |
| 2 | Hands-on look at the data | You've converted 3 moneylines to probabilities by hand |
| 3 | Betting math (engines) | EV, no-vig and Kelly tests pass |
| 4 | Synthetic sample | `scripts/make_sample_games.py` writes 1,096 games with known properties |
| 5 | Ingestion: land + bronze | Re-running ingest leaves the same row count |
| 6 | Bronze quality gate | Every check fails when you corrupt the data on purpose |
| 7 | Transform runner | Models build in order; a failing test stops the build |
| 8 | Staging SQL | `stg_games` has market probabilities; impossible prices quarantined |
| 9 | Elo (Python model) | Ratings are pre-game and zero-sum |
| 10 | Walk-forward model | No season is predicted by a model that saw it |
| 11 | Scoring vs the market | `model_vs_market` per season |
| 12 | Backtest | ROI with a bootstrap CI, drawdown, baseline |
| 13 | Report, API, dashboard | `make run` produces reports/report.md |
| 14 | CI + weekly refresh | Every push is tested; real data refreshes weekly |
| 15 | Docs | A stranger can run it and understand the result |

---

## Phase 0: The question and the rules of a fair test

**Question:** can a model built on public data predict NFL games better than the betting market's closing line?

Rules you commit to before writing code:

1. **The benchmark is the market.** The closing line is the consensus after all information (injuries, weather, sharp money). Beating "50/50" is easy; beating the close is the real test.
2. **No look-ahead.** Every feature must be known before kickoff. Every prediction for season S comes from a model trained only on seasons before S.
3. **Results come with uncertainty.** A ROI without a confidence interval proves nothing.

## Phase 1: Skeleton and tooling

```bash
git init edgeiq && cd edgeiq
python3.11 -m venv .venv && source .venv/bin/activate
mkdir -p src/{pipeline,models,backtest,engines,api,dashboard} sql/{staging,marts} tests scripts data/sample docs
```

`pyproject.toml` (dependency ranges + ruff + pytest config), `requirements.txt` (exact pins for CI), `Makefile`, `.gitignore` (`data/landing/`, `data/lake/`, `*.duckdb`).

## Phase 2: Look at the data by hand

```bash
curl -sL https://github.com/nflverse/nfldata/raw/master/data/games.csv -o games.csv
python - <<'PY'
import pandas as pd
g = pd.read_csv("games.csv")
print(g.shape, g.season.min(), g.season.max())
print(g[["game_id","home_team","away_team","home_moneyline","away_moneyline","home_score","away_score"]].tail())
PY
```

Convert by hand to learn the math:

- American **−150** → bet 150 to win 100 → implied 150/250 = **60.0%**
- American **+130** → bet 100 to win 130 → implied 100/230 = **43.5%**
- They add to **103.5%**: the extra 3.5% is the bookmaker's margin (the *vig* or *overround*).
- No-vig probabilities: 60.0/103.5 = **58.0%**, 43.5/103.5 = **42.0%**.

Notice: moneylines start in 2006; future games have no scores; ties exist.

## Phase 3: Betting math (pure functions)

`src/engines/`: `ev_engine.py` (odds conversion, vig removal: additive, multiplicative, Shin; EV), `bet_sizer.py` (Kelly), `clv_tracker.py` (closing line value). Pure functions, no I/O, so they're easy to test with doctests and pytest.

- **EV** of a $1 bet = p × (decimal − 1) − (1 − p).
- **Kelly** fraction = (b·p − q)/b, with b = decimal − 1. Use a fraction of it (¼): full Kelly assumes your probabilities are exactly right.

**Done when:** `pytest tests/test_ev_engine.py tests/test_bet_sizer.py tests/test_clv_tracker.py` passes.

## Phase 4: Synthetic sample (your test oracle)

`scripts/make_sample_games.py` writes games **in the same columns as the real file**, with fictional teams whose true strengths you control, and a "market" that sees those strengths with a little noise and charges 4.5% vig. Because you know the truth, tests can assert things like "the market beats an Elo model" and "the model learns that stronger teams win".

## Phase 5: Ingestion (land → bronze)

`src/pipeline/ingest.py`:

1. **Fetch** the CSV (or read the sample).
2. **Land** the exact bytes, gzipped, named with date + SHA-256 prefix. Same bytes → same file, so landing twice is a no-op.
3. **Parse** with explicit types (`dtype=str`, then convert): never let pandas guess. Fail with `SchemaError` if a column you depend on disappears upstream.
4. **Write bronze** Parquet partitioned by `season=YYYY` with `existing_data_behavior="delete_matching"`: re-running replaces partitions instead of appending duplicates (**idempotent**).
5. **Manifest:** one JSON line per run (source, SHA-256, rows, seasons) for lineage.

**Done when:** `test_bronze_write_is_idempotent` passes.

## Phase 6: Bronze quality gate

`src/pipeline/checks.py`: 8 SQL checks over the Parquet files (unique game_id, key columns present, scores both present or both missing, scores non-negative, moneylines look like American odds, sane weeks…). Each returns a count of failing rows; `error` checks stop the pipeline.

**Done when:** `test_each_check_can_fail` corrupts the data 5 different ways and each check catches its case. *A check that can't fail is decoration.*

## Phase 7: The transform runner

`src/pipeline/transform.py` + `sql/models.toml`. Build it yourself before using dbt, to understand what dbt does:

- Models listed in order; `{{ ref('schema.model') }}` is resolved, and using a model before it's built is an error.
- `kind = "sql"` → `create table/view ... as <sql>`; `kind = "python"` → a function returns a DataFrame that becomes a table. Elo and the ML model are Python models in the same graph.
- Tests per model (`unique`, `not_null`, `expression`, `row_count_equals`, `max_share`) run right after it builds; the first failure stops everything.
- Gotcha found here: DuckDB refuses `DROP VIEW` on a table, so the runner looks up the existing object's type before dropping.

## Phase 8: Staging SQL

`sql/staging/stg_games.sql`: types, `is_played`, `home_win` (ties stay NULL), implied and no-vig probabilities, `overround`, and `market_flag`. The real data contains one game whose moneylines sum to 98% (impossible at one book). It is **quarantined** (flagged, kept, excluded from modeling), and a test asserts quarantined prices never reach the model. `stg_team_games.sql` unpivots to one row per team per game.

## Phase 9: Elo ratings

`src/models/elo.py`: start at 1500, +48 for home field, K=20, margin-of-victory multiplier, a third of the way back to the mean between seasons. The row for each game stores ratings **before** the game is applied.

**Done when:** `test_ratings_are_pre_game_and_zero_sum` passes.

## Phase 10: Walk-forward model

`src/models/win_model.py`: logistic regression on Elo difference, rest difference, division and playoff flags. For each season S, train on seasons < S only (3 warm-up seasons). The market price is deliberately **not** a feature: the point is an independent opinion to compare with the market.

**Done when:** the `max_train_season < season` test passes on real data.

## Phase 11: Score against the market

`sql/marts/model_vs_market.sql`: log loss, Brier score and accuracy for the model, Elo alone and the market, per season and overall. Log loss punishes confident wrong answers, which is exactly what loses money.

## Phase 12: Backtest

`src/backtest/backtest.py`: in date order, bet the side whose model probability beats the no-vig market by ≥ 3 points, at closing odds; stake ¼ Kelly capped at 5% of bankroll. Report bets, win rate, ROI, flat-stake ROI with a **bootstrap 95% CI** (2,000 resamples), max drawdown, and a **baseline** (bet every home team) to compare against.

## Phase 13: Report, API, dashboard

- `src/reporting.py` writes `reports/report.md`, including a plain-English reading generated from the numbers.
- `src/api/main.py`: FastAPI with games, scores and backtest endpoints, plus calculators (EV/Kelly, no-vig, CLV). Test with `fastapi.testclient`.
- `src/dashboard/app.py`: Streamlit; test headless with `streamlit.testing.v1.AppTest`.

## Phase 14: CI and the weekly refresh

`.github/workflows/ci.yml`: lint, 81 tests and the demo pipeline on every push. `refresh.yml`: every Tuesday, download fresh real data, run everything, publish the report as a job summary and artifact.

## Phase 15: Documentation

README (question, result, how to run, limitations), this guide, ARCHITECTURE.md, LESSONS.md, DATA_DICTIONARY.md, ROADMAP.md.

---

## Interview angles

- **Benchmarking:** "I scored my model against the closing line, not against coin flips. It lost, and I can show by how much, season by season."
- **Leakage:** "Ratings are stored pre-game and the model is trained walk-forward; a test fails if any season is predicted by a model that saw it."
- **Uncertainty:** "The backtest ROI is −3% with a 95% interval of −7% to +1%: indistinguishable from zero, so there's no evidence of an edge."
- **Risk:** "Kelly sizing on a miscalibrated model went from $10,000 to $18. Sizing amplifies model error."
- **Data quality:** "Real data had a price no sportsbook could offer; I quarantined it with a test instead of silently dropping it."
- **Tooling:** "I wrote a small dbt-style runner to understand ref resolution, materialization and tests. My other project uses dbt itself."
