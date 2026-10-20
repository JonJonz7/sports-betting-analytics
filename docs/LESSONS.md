# Lessons: bugs found by real data, tests and the linter

v1 of this repo was a set of tested engine functions with a README describing a larger system (TimescaleDB, Celery, XGBoost, 140+ features, Claude-powered alerts) that wasn't built. Wiring it into a real pipeline exposed these problems. Each is fixed and tested.

| # | Found by | Problem | Fix |
|---|---|---|---|
| 1 | Linter (unused variable) | `scan_for_ev` chose a vig-removal method and never used it: `vig_method` did nothing, and `market_implied` still contained the vig despite its docstring | De-vig each book's market as a group with the chosen method; tests check that fair probabilities are vig-free and that methods differ on lopsided markets |
| 2 | Linter (unused variable) | Odds poller assumed the first outcome was the home team. The Odds API labels outcomes by team name in no fixed order, so home/away were swapped at random | Match sides by name against the event's `home_team`/`away_team`; skip unmatched rather than guess |
| 3 | Linter (unused variable) | A CLV test computed a summary and asserted nothing | The test now asserts that 5 bets are not called significant |
| 4 | Real data | One game (2020 wk 1 LV @ CAR, +134 / −124) has prices that sum to 98%, which no single book offers | `market_flag` quarantine: kept, flagged, excluded from modeling; tested |
| 5 | Building the runner | DuckDB errors on `DROP VIEW IF EXISTS` when the name is a table | Look up the object's type, then drop it |
| 6 | Backtest | Quarter-Kelly on the model's edges took $10,000 to $18 over 20 seasons | Not a code bug: the model is overconfident relative to the market. Documented as the main finding; Kelly needs calibrated probabilities |

## Takeaways

- **Run the linter as a bug finder.** Unused variables pointed at three real bugs.
- **Benchmark against the strongest baseline available** (the market), not a weak one.
- **Quarantine, don't drop.** Bad rows stay visible and counted, with a test.
- **README claims must match code.** Unbuilt parts are listed as roadmap, not features.
