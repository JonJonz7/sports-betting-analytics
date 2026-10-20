# Data dictionary

## Lake (Parquet, `data/lake/`)

| Path | Grain | Notes |
|---|---|---|
| `bronze/games/season=YYYY/*.parquet` | one game | 19 columns kept from nflverse `games.csv`, explicitly typed. Partition replaced on each ingest. |
| `_manifest.jsonl` | one ingest run | `run_id`, `source`, `sha256`, `landed_path`, `rows`, `seasons`, `at` |

## Warehouse (DuckDB, `data/warehouse.duckdb`)

| Table | Grain | Key columns |
|---|---|---|
| `staging.stg_games` | game | `is_played`, `home_win` (NULL on ties), `home_implied`/`away_implied`, `overround`, `market_flag` (ok / no_odds / below_100pct / margin_over_15pct), `home_novig`/`away_novig` (only when `ok`) |
| `staging.stg_team_games` | (game, team) | `is_home`, `points_for`, `points_against`, `rest_days` |
| `features.elo_ratings` | game | `elo_home_pre`, `elo_away_pre` (before the game), `elo_prob_home` |
| `marts.fct_games` | game | stg_games + Elo + `elo_diff`, `rest_diff` |
| `marts.predictions` | game (seasons after warm-up) | `model_prob_home`, `train_rows`, `max_train_season` (< season), `coef_elo` |
| `marts.model_vs_market` | season (+ `ALL`) | log loss, Brier score and accuracy for model, Elo and market |
| `marts.backtest_bets` | bet | `side`, `american_odds`, `model_prob`, `market_prob`, `edge`, `stake`, `won`, `pnl`, `flat_pnl`, `bankroll` |
| `marts.backtest_summary` | strategy | `bets`, `win_rate`, `roi`, `flat_roi` with 95% CI, `final_bankroll`, `max_drawdown` |

## Terms

- **American odds:** −150 = stake 150 to win 100; +130 = stake 100 to win 130.
- **Implied probability:** what the price says, vig included.
- **Overround (vig):** how much the two implied probabilities exceed 100%.
- **No-vig probability:** implied ÷ overround; the market's fair estimate.
- **Log loss:** average −log(probability given to what happened). Lower is better.
- **Brier score:** average (probability − outcome)². Lower is better.
- **CLV:** how much better your price was than the closing price.
