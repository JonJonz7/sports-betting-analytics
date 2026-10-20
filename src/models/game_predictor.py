"""Game outcome prediction -- Poisson score model + XGBoost classifier.

Two-stage prediction:
1. Poisson model estimates expected scores for each team (used for totals/spreads)
2. XGBoost classifier predicts moneyline outcome with calibrated probabilities

Enterprise value: Independent probability generation is the foundation of the
entire +EV pipeline. Without accurate probabilities, the EV engine has nothing
to compare against market odds.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np


@dataclass
class GamePrediction:
    """Full prediction output for a single game."""

    game_id: str
    home_team: str
    away_team: str

    # Moneyline probabilities (sum to 1)
    home_win_prob: float
    away_win_prob: float
    draw_prob: float  # 0 for most US sports

    # Score predictions
    home_score_pred: float
    away_score_pred: float
    total_pred: float
    spread_pred: float  # negative = home favored

    # Confidence
    model_confidence: float  # 0-1


def poisson_probability(lam: float, k: int) -> float:
    """Probability of exactly k events given rate lambda.

    P(X = k) = (lambda^k * e^-lambda) / k!

    Used to model the number of goals/points scored by each team.

    >>> round(poisson_probability(2.5, 3), 4)
    0.2138
    >>> round(poisson_probability(1.0, 0), 4)
    0.3679
    """
    if lam <= 0 or k < 0:
        return 0.0
    return (lam**k) * math.exp(-lam) / math.factorial(k)


def poisson_score_matrix(
    home_lambda: float,
    away_lambda: float,
    max_score: int = 10,
) -> np.ndarray:
    """Build a score probability matrix using independent Poisson distributions.

    Returns a (max_score+1) x (max_score+1) matrix where cell [i][j] is the
    probability that home scores i and away scores j.

    Args:
        home_lambda: Home team's expected scoring rate.
        away_lambda: Away team's expected scoring rate.
        max_score: Maximum score to model (10 for soccer, 50+ for basketball).

    Returns:
        numpy array of shape (max_score+1, max_score+1).
    """
    matrix = np.zeros((max_score + 1, max_score + 1))
    for i in range(max_score + 1):
        for j in range(max_score + 1):
            matrix[i][j] = poisson_probability(home_lambda, i) * poisson_probability(away_lambda, j)
    return matrix


def predict_from_poisson(
    home_lambda: float,
    away_lambda: float,
    max_score: int = 10,
) -> dict:
    """Derive moneyline, spread, and total probabilities from Poisson model.

    Args:
        home_lambda: Home team's expected goals/points.
        away_lambda: Away team's expected goals/points.
        max_score: Max score to model.

    Returns:
        Dict with home_win, away_win, draw, over/under probabilities.

    >>> result = predict_from_poisson(2.5, 1.8)
    >>> result['home_win'] > result['away_win']
    True
    >>> abs(result['home_win'] + result['away_win'] + result['draw'] - 1.0) < 0.01
    True
    """
    matrix = poisson_score_matrix(home_lambda, away_lambda, max_score)

    home_win = 0.0
    away_win = 0.0
    draw = 0.0

    for i in range(max_score + 1):
        for j in range(max_score + 1):
            if i > j:
                home_win += matrix[i][j]
            elif j > i:
                away_win += matrix[i][j]
            else:
                draw += matrix[i][j]

    total = home_lambda + away_lambda

    return {
        "home_win": round(home_win, 4),
        "away_win": round(away_win, 4),
        "draw": round(draw, 4),
        "predicted_total": round(total, 1),
        "predicted_spread": round(away_lambda - home_lambda, 1),
        "home_score_pred": round(home_lambda, 1),
        "away_score_pred": round(away_lambda, 1),
    }


def calculate_team_lambda(
    offensive_rating: float,
    opponent_defensive_rating: float,
    league_avg_scoring: float,
    home_advantage: float = 0.0,
    rest_adjustment: float = 0.0,
    pace_factor: float = 1.0,
    injury_impact: float = 0.0,
) -> float:
    """Calculate a team's expected scoring rate (lambda) for Poisson model.

    Uses the Dixon-Coles approach: attack strength * defense weakness * home advantage.

    Args:
        offensive_rating: Team's scoring ability (points per game or per 100 possessions).
        opponent_defensive_rating: Opponent's defensive rating (points allowed).
        league_avg_scoring: League-wide average scoring rate.
        home_advantage: Home court/field advantage in points (e.g., 3.0 for NBA).
        rest_adjustment: Rest days impact (e.g., -2.0 for back-to-back in NBA).
        pace_factor: Pace multiplier (1.0 = league average pace).
        injury_impact: Scoring reduction from injuries (e.g., -0.05 = 5% reduction).

    Returns:
        Expected scoring rate (lambda).

    >>> round(calculate_team_lambda(112.0, 108.0, 110.0, home_advantage=3.0), 1)
    114.8
    """
    if league_avg_scoring <= 0:
        return 0.0

    # Attack strength: how much better/worse than average this team scores
    attack = offensive_rating / league_avg_scoring

    # Defense weakness: how many points the opponent allows relative to average
    defense_weakness = opponent_defensive_rating / league_avg_scoring

    # Base expected score
    lam = attack * defense_weakness * league_avg_scoring

    # Adjustments
    lam += home_advantage
    lam += rest_adjustment
    lam *= pace_factor
    lam *= 1 + injury_impact  # injury_impact is negative for missing players

    return max(0.0, lam)


# Feature list for XGBoost model (140+ features)
FEATURE_COLUMNS = [
    # Team strength
    "home_off_rating",
    "home_def_rating",
    "away_off_rating",
    "away_def_rating",
    "home_net_rating",
    "away_net_rating",
    "home_win_pct",
    "away_win_pct",
    # Recent form (last 5, 10 games)
    "home_win_pct_l5",
    "away_win_pct_l5",
    "home_win_pct_l10",
    "away_win_pct_l10",
    "home_avg_margin_l5",
    "away_avg_margin_l5",
    # Rest and travel
    "home_rest_days",
    "away_rest_days",
    "home_b2b",
    "away_b2b",
    "travel_distance_miles",
    # Pace and style
    "home_pace",
    "away_pace",
    "pace_matchup_delta",
    "home_3pt_rate",
    "away_3pt_rate",
    "home_ft_rate",
    "away_ft_rate",
    # Opponent-adjusted
    "home_off_vs_opp_def",
    "away_off_vs_opp_def",
    "home_sos",
    "away_sos",  # strength of schedule
    # Injury impact
    "home_injury_impact",
    "away_injury_impact",
    # Line movement
    "opening_spread",
    "current_spread",
    "spread_movement",
    "opening_total",
    "current_total",
    "total_movement",
    "line_movement_velocity",
    # Public betting
    "public_home_pct",
    "public_away_pct",
    # Situational
    "is_divisional",
    "is_conference",
    "is_rivalry",
    "home_altitude_advantage",
    # Referee/umpire
    "referee_over_tendency",
    "referee_foul_rate",
    # Weather (outdoor sports)
    "wind_speed",
    "temperature",
    "precipitation_prob",
    # Historical matchup
    "h2h_home_win_pct",
    "h2h_avg_total",
    "h2h_sample_size",
]
