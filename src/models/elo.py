"""
Elo ratings for NFL teams, computed point-in-time.

Every team starts at 1500. Before each game, the rating gap (plus a home-field
bonus) gives a win probability. After the game, the winner takes points from
the loser: more points for an upset and for a bigger margin of victory.
Between seasons every rating moves a third of the way back toward the mean,
because rosters change.

The output row for a game holds the ratings going INTO that game, never
after it, so features built from it can't leak the result (look-ahead bias).
Parameters follow FiveThirtyEight's published NFL Elo method.
"""

from __future__ import annotations

import math

import duckdb
import pandas as pd

BASE = 1500.0
K = 20.0
HOME_FIELD = 48.0  # Elo points, about +7% win probability for equal teams
SEASON_REVERT = 1 / 3


def win_probability(elo_diff: float) -> float:
    """P(team A wins) when A is elo_diff points stronger (home field already included)."""
    return 1.0 / (1.0 + 10 ** (-elo_diff / 400.0))


def mov_multiplier(margin: int, winner_elo_diff: float) -> float:
    """Bigger wins move ratings more; favourites' blowouts are damped (autocorrelation fix)."""
    return math.log(abs(margin) + 1) * (2.2 / (winner_elo_diff * 0.001 + 2.2))


def run_elo(games: pd.DataFrame) -> pd.DataFrame:
    """games: game_id, season, game_date, home_team, away_team, home_score, away_score, is_played.
    Returns one row per game with pre-game ratings and the home win probability."""
    ratings: dict[str, float] = {}
    current_season = None
    out = []
    for g in games.sort_values(["game_date", "game_id"]).itertuples(index=False):
        if g.season != current_season:
            ratings = {t: r + (BASE - r) * SEASON_REVERT for t, r in ratings.items()}
            current_season = g.season
        home = ratings.get(g.home_team, BASE)
        away = ratings.get(g.away_team, BASE)
        diff = home + HOME_FIELD - away
        p_home = win_probability(diff)
        out.append((g.game_id, home, away, p_home))

        if g.is_played and g.home_score is not None and not pd.isna(g.home_score):
            margin = int(g.home_score) - int(g.away_score)
            actual = 1.0 if margin > 0 else 0.0 if margin < 0 else 0.5
            winner_diff = diff if margin > 0 else -diff
            mult = mov_multiplier(margin, winner_diff) if margin else 1.0
            shift = K * mult * (actual - p_home)
            ratings[g.home_team] = home + shift
            ratings[g.away_team] = away - shift
    return pd.DataFrame(out, columns=["game_id", "elo_home_pre", "elo_away_pre", "elo_prob_home"])


def build_elo_ratings(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """Python model for the transform runner."""
    games = con.execute("""
        select game_id, season, game_date, home_team, away_team, home_score, away_score, is_played
        from staging.stg_games
    """).fetchdf()
    return run_elo(games)
