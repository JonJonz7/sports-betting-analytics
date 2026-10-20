# EdgeIQ report

Generated 2026-10-20 17:49 UTC from source **nflverse** (real NFL games and closing lines from nflverse).

## Data coverage

| first_season | last_season | games | played | with_moneylines | avg_bookmaker_margin |
|---:|---:|---:|---:|---:|---:|
| 1999 | 2026 | 7548 | 7369 | 5415 | 0.0276 |

## Is the betting market calibrated?

If the no-vig closing price says 70%, do those teams win about 70% of the time?

| market_prob_bucket | games | avg_market_prob | actual_home_win_rate |
|---:|---:|---:|---:|
| 0 | 7 | 0.093 | 0 |
| 0.1 | 108 | 0.163 | 0.194 |
| 0.2 | 384 | 0.256 | 0.255 |
| 0.3 | 674 | 0.353 | 0.344 |
| 0.4 | 733 | 0.446 | 0.438 |
| 0.5 | 885 | 0.555 | 0.529 |
| 0.6 | 1108 | 0.648 | 0.617 |
| 0.7 | 975 | 0.748 | 0.759 |
| 0.8 | 456 | 0.842 | 0.86 |
| 0.9 | 42 | 0.917 | 0.952 |

## Model vs market (walk-forward: each season predicted by a model trained only on earlier seasons)

Lower log loss and Brier score are better.

| season | games | model_log_loss | elo_log_loss | market_log_loss | model_brier | market_brier | model_accuracy | market_accuracy |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 2006 | 220 | 0.6574 | 0.6573 | 0.6694 | 0.2335 | 0.238 | 0.5864 | 0.5909 |
| 2007 | 266 | 0.6184 | 0.6197 | 0.5896 | 0.2155 | 0.2034 | 0.6429 | 0.6842 |
| 2008 | 193 | 0.6223 | 0.6229 | 0.6003 | 0.2174 | 0.2082 | 0.6166 | 0.6632 |
| 2009 | 253 | 0.5946 | 0.596 | 0.5822 | 0.2041 | 0.1984 | 0.6917 | 0.6957 |
| 2010 | 267 | 0.6544 | 0.6564 | 0.6324 | 0.2314 | 0.2209 | 0.6217 | 0.6554 |
| 2011 | 267 | 0.6128 | 0.6131 | 0.5931 | 0.213 | 0.2038 | 0.6442 | 0.6667 |
| 2012 | 266 | 0.6298 | 0.6274 | 0.6023 | 0.2207 | 0.2087 | 0.6316 | 0.6466 |
| 2013 | 266 | 0.6197 | 0.6208 | 0.5924 | 0.2163 | 0.2027 | 0.6617 | 0.7105 |
| 2014 | 266 | 0.6035 | 0.6016 | 0.5991 | 0.2083 | 0.2066 | 0.688 | 0.6692 |
| 2015 | 267 | 0.6354 | 0.6405 | 0.6488 | 0.2214 | 0.2287 | 0.6667 | 0.6217 |
| 2016 | 265 | 0.6266 | 0.6264 | 0.6216 | 0.2193 | 0.217 | 0.6302 | 0.6453 |
| 2017 | 266 | 0.6238 | 0.623 | 0.5932 | 0.2174 | 0.2031 | 0.6541 | 0.703 |
| 2018 | 265 | 0.63 | 0.6362 | 0.6135 | 0.221 | 0.2124 | 0.6113 | 0.6642 |
| 2019 | 266 | 0.6414 | 0.6369 | 0.6163 | 0.2248 | 0.2141 | 0.6429 | 0.6429 |
| 2020 | 267 | 0.6242 | 0.6218 | 0.59 | 0.2164 | 0.2019 | 0.6554 | 0.6742 |
| 2021 | 284 | 0.6574 | 0.6552 | 0.6232 | 0.2323 | 0.2177 | 0.5951 | 0.6232 |
| 2022 | 282 | 0.6404 | 0.6367 | 0.605 | 0.2253 | 0.2093 | 0.6277 | 0.6596 |
| 2023 | 285 | 0.6533 | 0.659 | 0.627 | 0.2301 | 0.2186 | 0.614 | 0.6772 |
| 2024 | 285 | 0.611 | 0.6067 | 0.5892 | 0.2113 | 0.201 | 0.6772 | 0.7053 |
| 2025 | 284 | 0.6373 | 0.6365 | 0.607 | 0.2235 | 0.2109 | 0.6408 | 0.662 |
| 2026 | 92 | 0.6569 | 0.66 | 0.6614 | 0.2336 | 0.2334 | 0.6087 | 0.6196 |
| ALL | 5372 | 0.6303 | 0.6303 | 0.6104 | 0.2204 | 0.2115 | 0.64 | 0.6629 |

**Reading:** over 5372 games the model's log loss is 0.6303 vs the market's 0.6104. The market is better calibrated than the model. Expected: closing lines absorb information (injuries, weather, sharp money) that an Elo model never sees.

## Backtest (bets placed at closing odds)

| strategy | games_considered | bets | win_rate | staked | profit | roi | flat_roi | flat_roi_ci_low | flat_roi_ci_high | final_bankroll | max_drawdown |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| model_edge | 5373 | 3849 | 0.405 | 6.389e+05 | -9,983 | -0.0156 | -0.0305 | -0.0737 | 0.0113 | 17.55 | 0.9997 |
| bet_every_home_team | 5373 | 5373 | 0.5576 | 5,373 | -231.3 | -0.043 | -0.043 | -0.0708 | -0.0161 |  |  |

**Reading:** 3849 bets, flat-stake ROI -3.05% (95% CI -7.37% to +1.13%). The interval includes zero: no evidence of an edge. Kelly-sized bankroll ended at $18 from $10,000, max drawdown 100%. Sizing with Kelly on a model that is less accurate than the market overbets, which is why fractional Kelly and calibration checks matter.

Bets at the closing line have zero closing line value by construction; proving a real edge requires beating the close with earlier prices (see docs/ROADMAP.md).
