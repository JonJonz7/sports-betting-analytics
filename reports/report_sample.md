# EdgeIQ report

Generated 2026-10-20 17:55 UTC from source **sample** (synthetic sample: fictional teams).

## Data coverage

| first_season | last_season | games | played | with_moneylines | avg_bookmaker_margin |
|---:|---:|---:|---:|---:|---:|
| 2012 | 2019 | 1096 | 1088 | 1096 | 0.0225 |

## Is the betting market calibrated?

If the no-vig closing price says 70%, do those teams win about 70% of the time?

| market_prob_bucket | games | avg_market_prob | actual_home_win_rate |
|---:|---:|---:|---:|
| 0.2 | 36 | 0.261 | 0.278 |
| 0.3 | 92 | 0.359 | 0.293 |
| 0.4 | 199 | 0.451 | 0.492 |
| 0.5 | 273 | 0.552 | 0.52 |
| 0.6 | 280 | 0.652 | 0.6 |
| 0.7 | 170 | 0.743 | 0.741 |
| 0.8 | 37 | 0.84 | 0.919 |
| 0.9 | 1 | 0.912 | 1 |

## Model vs market (walk-forward: each season predicted by a model trained only on earlier seasons)

Lower log loss and Brier score are better.

| season | games | model_log_loss | elo_log_loss | market_log_loss | model_brier | market_brier | model_accuracy | market_accuracy |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 2015 | 136 | 0.6942 | 0.7017 | 0.6557 | 0.2509 | 0.2324 | 0.5441 | 0.5956 |
| 2016 | 136 | 0.7183 | 0.7287 | 0.6923 | 0.2614 | 0.2491 | 0.5074 | 0.5882 |
| 2017 | 136 | 0.6518 | 0.6396 | 0.6174 | 0.2299 | 0.2138 | 0.6176 | 0.6618 |
| 2018 | 136 | 0.6865 | 0.7039 | 0.6699 | 0.2462 | 0.2398 | 0.6103 | 0.5588 |
| 2019 | 136 | 0.6659 | 0.6621 | 0.6587 | 0.2366 | 0.2344 | 0.6176 | 0.5588 |
| ALL | 680 | 0.6833 | 0.6872 | 0.6588 | 0.245 | 0.2339 | 0.5794 | 0.5926 |

**Reading:** over 680 games the model's log loss is 0.6833 vs the market's 0.6588. The market is better calibrated than the model. Expected: closing lines absorb information (injuries, weather, sharp money) that an Elo model never sees.

## Backtest (bets placed at closing odds)

| strategy | games_considered | bets | win_rate | staked | profit | roi | flat_roi | flat_roi_ci_low | flat_roi_ci_high | final_bankroll | max_drawdown |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| model_edge | 680 | 534 | 0.4157 | 1.006e+05 | -5,347 | -0.0532 | 0.0081 | -0.0991 | 0.1157 | 4,653 | 0.7848 |
| bet_every_home_team | 680 | 680 | 0.5456 | 680 | -55.44 | -0.0815 | -0.0815 | -0.1497 | -0.0151 |  |  |

**Reading:** 534 bets, flat-stake ROI +0.81% (95% CI -9.91% to +11.57%). The interval includes zero: no evidence of an edge. Kelly-sized bankroll ended at $4,653 from $10,000, max drawdown 78%. Sizing with Kelly on a model that is less accurate than the market overbets, which is why fractional Kelly and calibration checks matter.

Bets at the closing line have zero closing line value by construction; proving a real edge requires beating the close with earlier prices (see docs/ROADMAP.md).
