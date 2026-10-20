"""
Backtest: would betting the model's edges have made money?

For every played game with a model prediction and closing moneylines, in date
order:
  edge(side) = model probability - market no-vig probability
  bet the side with the larger edge if edge >= min_edge,
  stake = fractional Kelly (src/engines/bet_sizer.kelly_fraction) x bankroll,
          capped at max_bet_pct of bankroll,
  settle at the closing American odds.

Reported: bets, win rate, ROI on money staked, profit, max drawdown, and a
bootstrap 95% confidence interval for flat-stake ROI (resample the bets 2,000
times). If the interval includes 0, the result is indistinguishable from luck.

Honest caveat built into the design: these bets are placed AT the closing
line, so closing line value (CLV) is zero by construction. A real edge shows
up as beating the close, which needs earlier odds than this dataset has.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

import duckdb
import numpy as np
import pandas as pd

from src.engines.bet_sizer import kelly_fraction
from src.engines.ev_engine import american_to_decimal


@dataclass(frozen=True)
class Strategy:
    name: str = "model_edge"
    min_edge: float = 0.03
    kelly_multiplier: float = 0.25
    max_bet_pct: float = 0.05
    starting_bankroll: float = 10_000.0


@dataclass
class Summary:
    strategy: str
    games_considered: int
    bets: int
    win_rate: float
    staked: float
    profit: float
    roi: float
    flat_roi: float
    flat_roi_ci_low: float
    flat_roi_ci_high: float
    final_bankroll: float
    max_drawdown: float


GAMES_SQL = """
    select f.game_id, f.season, f.game_date, f.home_team, f.away_team, f.home_win,
           f.home_moneyline, f.away_moneyline, f.home_novig, f.away_novig,
           p.model_prob_home
    from marts.fct_games f
    join marts.predictions p using (game_id)
    where f.is_played and f.home_win is not null
      and f.home_moneyline is not null and f.away_moneyline is not null
    order by f.game_date, f.game_id
"""


def load_games(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    return con.execute(GAMES_SQL).fetchdf()


def simulate(games: pd.DataFrame, strategy: Strategy = Strategy()) -> pd.DataFrame:
    """One row per bet placed, with the bankroll after settlement."""
    bankroll = strategy.starting_bankroll
    rows = []
    for g in games.itertuples(index=False):
        sides = [
            ("home", g.model_prob_home, g.home_novig, g.home_moneyline, g.home_win == 1),
            ("away", 1 - g.model_prob_home, g.away_novig, g.away_moneyline, g.home_win == 0),
        ]
        side, prob, market, odds, won = max(sides, key=lambda s: s[1] - s[2])
        edge = prob - market
        if edge < strategy.min_edge:
            continue
        dec = american_to_decimal(int(odds))
        fraction = min(kelly_fraction(prob, dec) * strategy.kelly_multiplier, strategy.max_bet_pct)
        if fraction <= 0:
            continue
        stake = round(bankroll * fraction, 2)
        pnl = stake * (dec - 1) if won else -stake
        bankroll += pnl
        rows.append(
            {
                "game_id": g.game_id,
                "season": g.season,
                "game_date": g.game_date,
                "side": side,
                "team": g.home_team if side == "home" else g.away_team,
                "american_odds": int(odds),
                "model_prob": round(prob, 4),
                "market_prob": round(market, 4),
                "edge": round(edge, 4),
                "stake": stake,
                "won": bool(won),
                "pnl": round(pnl, 2),
                "flat_pnl": (dec - 1) if won else -1.0,
                "bankroll": round(bankroll, 2),
            }
        )
    return pd.DataFrame(rows)


def max_drawdown(bankroll: pd.Series, start: float) -> float:
    """Largest fall from a peak, as a fraction of that peak."""
    if bankroll.empty:
        return 0.0
    path = pd.concat([pd.Series([start]), bankroll], ignore_index=True)
    peaks = path.cummax()
    return float(((peaks - path) / peaks).max())


def bootstrap_ci(flat_pnl: np.ndarray, n: int = 2000, seed: int = 0) -> tuple[float, float]:
    """95% interval for mean flat-stake profit per bet (= flat ROI)."""
    if len(flat_pnl) < 2:
        return (float("nan"), float("nan"))
    rng = np.random.default_rng(seed)
    means = rng.choice(flat_pnl, size=(n, len(flat_pnl)), replace=True).mean(axis=1)
    return float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5))


def summarize(bets: pd.DataFrame, games_considered: int, strategy: Strategy) -> Summary:
    if bets.empty:
        return Summary(
            strategy.name,
            games_considered,
            0,
            0,
            0,
            0,
            0,
            0,
            float("nan"),
            float("nan"),
            strategy.starting_bankroll,
            0,
        )
    lo, hi = bootstrap_ci(bets["flat_pnl"].to_numpy())
    staked = float(bets["stake"].sum())
    profit = float(bets["pnl"].sum())
    return Summary(
        strategy=strategy.name,
        games_considered=games_considered,
        bets=len(bets),
        win_rate=round(float(bets["won"].mean()), 4),
        staked=round(staked, 2),
        profit=round(profit, 2),
        roi=round(profit / staked, 4) if staked else 0.0,
        flat_roi=round(float(bets["flat_pnl"].mean()), 4),
        flat_roi_ci_low=round(lo, 4),
        flat_roi_ci_high=round(hi, 4),
        final_bankroll=round(float(bets["bankroll"].iloc[-1]), 2),
        max_drawdown=round(max_drawdown(bets["bankroll"], strategy.starting_bankroll), 4),
    )


def baseline_home_flat(games: pd.DataFrame) -> pd.DataFrame:
    """Benchmark: 1 unit on every home team at the closing line."""
    dec = games["home_moneyline"].astype(int).map(american_to_decimal)
    won = games["home_win"] == 1
    return pd.DataFrame({"flat_pnl": np.where(won, dec - 1, -1.0)})


def run_backtest(
    con: duckdb.DuckDBPyConnection, strategy: Strategy = Strategy()
) -> tuple[pd.DataFrame, list[Summary]]:
    """Simulate, write marts.backtest_bets / marts.backtest_summary, return both."""
    games = load_games(con)
    bets = simulate(games, strategy)
    model_summary = summarize(bets, len(games), strategy)

    base = baseline_home_flat(games)
    lo, hi = bootstrap_ci(base["flat_pnl"].to_numpy())
    base_roi = round(float(base["flat_pnl"].mean()), 4) if len(base) else 0.0
    baseline = Summary(
        "bet_every_home_team",
        len(games),
        len(base),
        round(float((games["home_win"] == 1).mean()), 4) if len(games) else 0,
        float(len(base)),
        round(float(base["flat_pnl"].sum()), 2),
        base_roi,
        base_roi,
        round(lo, 4),
        round(hi, 4),
        float("nan"),
        float("nan"),
    )

    summaries = [model_summary, baseline]
    con.execute("create schema if not exists marts")
    con.register("_bets", bets if not bets.empty else pd.DataFrame({"game_id": []}))
    con.execute("create or replace table marts.backtest_bets as select * from _bets")
    con.unregister("_bets")
    summary_df = pd.DataFrame([asdict(s) for s in summaries])
    con.register("_summary", summary_df)
    con.execute("create or replace table marts.backtest_summary as select * from _summary")
    con.unregister("_summary")
    return bets, summaries
