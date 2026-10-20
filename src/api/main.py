"""
EdgeIQ API (FastAPI): read-only access to the warehouse plus betting math.

    uvicorn src.api.main:app --reload        # http://localhost:8000/docs

Warehouse endpoints read the DuckDB file built by `python -m src.cli all`.
Calculator endpoints are pure functions from src/engines and need no data.
"""

from __future__ import annotations

from functools import lru_cache

import duckdb
from fastapi import FastAPI, HTTPException, Query

from src.config import WAREHOUSE_PATH
from src.engines.bet_sizer import kelly_fraction
from src.engines.clv_tracker import calculate_clv
from src.engines.ev_engine import (
    american_to_decimal,
    calculate_ev,
    decimal_to_implied,
    remove_vig_additive,
)

app = FastAPI(
    title="EdgeIQ",
    description="NFL win-probability model vs the betting market: data, scores, backtest and betting math.",
    version="0.2.0",
)


@lru_cache(maxsize=1)
def _warehouse_exists() -> bool:
    return WAREHOUSE_PATH.exists()


def query(sql: str, params: list | None = None) -> list[dict]:
    if not WAREHOUSE_PATH.exists():
        raise HTTPException(
            503, "Warehouse not built yet: run `python -m src.cli all --source sample`"
        )
    con = duckdb.connect(str(WAREHOUSE_PATH), read_only=True)
    try:
        cur = con.execute(sql, params or [])
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]
    finally:
        con.close()


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "warehouse": WAREHOUSE_PATH.exists()}


@app.get("/api/games/{game_id}")
def get_game(game_id: str) -> dict:
    """Everything known before kickoff, the model's and the market's probabilities, and the result."""
    rows = query(
        """
        select f.game_id, f.season, f.week, f.game_date, f.home_team, f.away_team,
               f.home_score, f.away_score, f.home_moneyline, f.away_moneyline, f.market_flag,
               f.home_novig as market_prob_home, f.elo_prob_home, p.model_prob_home,
               f.elo_diff, f.rest_diff, f.is_division
        from marts.fct_games f left join marts.predictions p using (game_id)
        where f.game_id = ?""",
        [game_id],
    )
    if not rows:
        raise HTTPException(404, f"No game {game_id}")
    return rows[0]


@app.get("/api/scores")
def get_scores() -> list[dict]:
    """Model vs market log loss, Brier score and accuracy by season."""
    return query("select * from marts.model_vs_market order by season")


@app.get("/api/backtest")
def get_backtest() -> list[dict]:
    """Backtest summaries: the model strategy and the bet-every-home-team baseline."""
    return query("select * from marts.backtest_summary")


@app.get("/api/calc/ev")
def calc_ev(
    model_prob: float = Query(..., gt=0, lt=1),
    american_odds: int = Query(..., description="e.g. -110 or +150"),
    kelly_multiplier: float = Query(0.25, gt=0, le=1),
) -> dict:
    """Expected value and Kelly stake for one bet."""
    if -100 < american_odds < 100:
        raise HTTPException(422, "American odds are <= -100 or >= +100")
    dec = american_to_decimal(american_odds)
    return {
        "decimal_odds": round(dec, 4),
        "implied_prob": round(decimal_to_implied(dec), 4),
        "ev_per_unit": round(calculate_ev(model_prob, dec), 4),
        "kelly_full": round(kelly_fraction(model_prob, dec), 4),
        "kelly_recommended": round(kelly_fraction(model_prob, dec) * kelly_multiplier, 4),
    }


@app.get("/api/calc/no-vig")
def calc_no_vig(home_odds: int, away_odds: int) -> dict:
    """Remove the bookmaker margin from a two-way market."""
    implied = [decimal_to_implied(american_to_decimal(o)) for o in (home_odds, away_odds)]
    fair = remove_vig_additive(implied)
    return {
        "overround": round(sum(implied), 4),
        "home_fair": round(fair[0], 4),
        "away_fair": round(fair[1], 4),
    }


@app.get("/api/calc/clv")
def calc_clv(bet_odds: int, closing_odds: int) -> dict:
    """Closing line value: did you get a better price than the market's final one?"""
    r = calculate_clv(bet_odds, closing_odds)
    return {k: (round(v, 4) if isinstance(v, float) else v) for k, v in vars(r).items()}
