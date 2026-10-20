import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from src.api.main import app
from src.backtest.backtest import Strategy, bootstrap_ci, max_drawdown, simulate


def _games(rows):
    return pd.DataFrame(
        rows,
        columns=[
            "game_id",
            "season",
            "game_date",
            "home_team",
            "away_team",
            "home_win",
            "home_moneyline",
            "away_moneyline",
            "home_novig",
            "away_novig",
            "model_prob_home",
        ],
    )


def test_bets_only_when_edge_clears_threshold_and_settles_correctly():
    games = _games(
        [
            # model 60% vs market 50%: 10-point edge on home at +100 -> bet, wins
            ("g1", 2020, "2020-09-10", "A", "B", 1, 100, -100, 0.5, 0.5, 0.60),
            # model agrees with market: no bet
            ("g2", 2020, "2020-09-11", "C", "D", 0, 100, -100, 0.5, 0.5, 0.51),
        ]
    )
    s = Strategy(min_edge=0.03, kelly_multiplier=0.25, max_bet_pct=0.05, starting_bankroll=1000)
    bets = simulate(games, s)
    assert list(bets["game_id"]) == ["g1"]
    # full Kelly at even money with p=0.6 is 0.2; quarter = 0.05 -> stake 50
    assert bets.loc[0, "stake"] == 50.0
    assert bets.loc[0, "pnl"] == 50.0 and bets.loc[0, "bankroll"] == 1050.0


def test_picks_the_side_with_the_bigger_edge():
    games = _games([("g1", 2020, "2020-09-10", "A", "B", 0, 120, -140, 0.44, 0.56, 0.30)])
    bets = simulate(games, Strategy(min_edge=0.03))
    assert bets.loc[0, "side"] == "away" and bets.loc[0, "won"]


def test_drawdown_and_bootstrap():
    assert max_drawdown(pd.Series([110.0, 55.0, 80.0]), 100.0) == pytest.approx(0.5)
    lo, hi = bootstrap_ci(np.array([1.0, -1.0] * 50))
    assert lo < 0 < hi


client = TestClient(app)


def test_ev_endpoint():
    r = client.get("/api/calc/ev", params={"model_prob": 0.55, "american_odds": -110}).json()
    assert r["ev_per_unit"] == pytest.approx(0.05, abs=1e-3)
    assert (
        client.get("/api/calc/ev", params={"model_prob": 0.5, "american_odds": 50}).status_code
        == 422
    )


def test_no_vig_endpoint():
    r = client.get("/api/calc/no-vig", params={"home_odds": -110, "away_odds": -110}).json()
    assert r["home_fair"] == pytest.approx(0.5) and r["overround"] > 1
