"""
Write reports/report.md from the warehouse: data coverage, how well the market
and the model are calibrated, model vs market scores, and the backtest, with a
plain-English reading generated from the numbers themselves.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import duckdb
import pandas as pd


def _table(df: pd.DataFrame) -> str:
    if df.empty:
        return "_no rows_\n"
    head = "| " + " | ".join(df.columns) + " |"
    sep = (
        "|"
        + "|".join("---:" if pd.api.types.is_numeric_dtype(df[c]) else "---" for c in df.columns)
        + "|"
    )
    body = [
        "| "
        + " | ".join(
            "" if pd.isna(v) else f"{v:,.4g}" if isinstance(v, float) else str(v) for v in row
        )
        + " |"
        for row in df.itertuples(index=False)
    ]
    return "\n".join([head, sep, *body]) + "\n"


def build_report(con: duckdb.DuckDBPyConnection, source: str) -> str:
    q = lambda sql: con.execute(sql).fetchdf()  # noqa: E731
    coverage = q("""
        select min(season) as first_season, max(season) as last_season, count(*) as games,
               count(*) filter (where is_played) as played,
               count(*) filter (where home_novig is not null) as with_moneylines,
               round(avg(overround) - 1, 4) as avg_bookmaker_margin
        from staging.stg_games
    """)
    calibration = q("""
        select round(floor(home_novig * 10) / 10, 1) as market_prob_bucket,
               count(*) as games,
               round(avg(home_novig), 3) as avg_market_prob,
               round(avg(home_win), 3) as actual_home_win_rate
        from staging.stg_games
        where is_played and home_win is not null and home_novig is not null
        group by 1 order by 1
    """)
    scores = q("select * from marts.model_vs_market")
    backtest = q("select * from marts.backtest_summary")
    overall = scores[scores["season"] == "ALL"].iloc[0] if not scores.empty else None

    lines = [
        "# EdgeIQ report",
        "",
        f"Generated {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC from source **{source}**"
        + (
            " (synthetic sample: fictional teams)"
            if source == "sample"
            else " (real NFL games and closing lines from nflverse)"
        )
        + ".",
        "",
        "## Data coverage",
        "",
        _table(coverage),
        "## Is the betting market calibrated?",
        "",
        "If the no-vig closing price says 70%, do those teams win about 70% of the time?",
        "",
        _table(calibration),
        "## Model vs market (walk-forward: each season predicted by a model trained only on earlier seasons)",
        "",
        "Lower log loss and Brier score are better.",
        "",
        _table(scores),
    ]
    if overall is not None:
        beat = overall["model_log_loss"] < overall["market_log_loss"]
        lines += [
            f"**Reading:** over {int(overall['games'])} games the model's log loss is "
            f"{overall['model_log_loss']} vs the market's {overall['market_log_loss']}. "
            + (
                "The model beat the closing line on this measure; check it isn't luck before trusting it."
                if beat
                else "The market is better calibrated than the model. Expected: closing lines absorb "
                "information (injuries, weather, sharp money) that an Elo model never sees."
            ),
            "",
        ]
    lines += [
        "## Backtest (bets placed at closing odds)",
        "",
        _table(backtest),
    ]
    if not backtest.empty:
        m = backtest.iloc[0]
        ci = (m["flat_roi_ci_low"], m["flat_roi_ci_high"])
        lines += [
            f"**Reading:** {int(m['bets'])} bets, flat-stake ROI {m['flat_roi']:+.2%} "
            f"(95% CI {ci[0]:+.2%} to {ci[1]:+.2%}). "
            + (
                "The interval includes zero: no evidence of an edge. "
                if ci[0] <= 0 <= ci[1]
                else "The interval excludes zero. "
            )
            + f"Kelly-sized bankroll ended at ${m['final_bankroll']:,.0f} from $10,000, "
            f"max drawdown {m['max_drawdown']:.0%}. Sizing with Kelly on a model that is "
            "less accurate than the market overbets, which is why fractional Kelly and "
            "calibration checks matter.",
            "",
            "Bets at the closing line have zero closing line value by construction; proving a "
            "real edge requires beating the close with earlier prices (see docs/ROADMAP.md).",
            "",
        ]
    return "\n".join(lines)


def write_report(con: duckdb.DuckDBPyConnection, path: Path, source: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(build_report(con, source))
    return path
