"""Feature engineering for game prediction models.

Transforms raw game, team, and player data into ML-ready feature vectors.
Handles time-aware feature computation (only uses data available BEFORE game time).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass
class FeatureVector:
    """A complete feature vector for one game."""

    game_id: str
    features: dict[str, float]
    computed_at: datetime
    feature_version: str = "v1.0"


def compute_game_features(
    game: dict,
    home_team_stats: dict,
    away_team_stats: dict,
    league_avgs: dict,
    recent_games_home: list[dict] | None = None,
    recent_games_away: list[dict] | None = None,
    injury_impacts: dict | None = None,
    line_data: dict | None = None,
) -> FeatureVector:
    """Compute the full feature vector for a game.

    All features are computed using only data available BEFORE game time
    (no look-ahead bias).

    Args:
        game: Game record with scheduled_at, home/away team IDs, rest days.
        home_team_stats: Season-to-date stats for home team.
        away_team_stats: Season-to-date stats for away team.
        league_avgs: League-wide averages for normalization.
        recent_games_home: Last N games for home team (for form features).
        recent_games_away: Last N games for away team.
        injury_impacts: Injury impact scores from narrative parser.
        line_data: Opening/current odds and line movement.

    Returns:
        FeatureVector ready for model input.
    """
    features = {}

    # --- Team strength features ---
    features["home_off_rating"] = home_team_stats.get("off_rating", 0)
    features["home_def_rating"] = home_team_stats.get("def_rating", 0)
    features["away_off_rating"] = away_team_stats.get("off_rating", 0)
    features["away_def_rating"] = away_team_stats.get("def_rating", 0)
    features["home_net_rating"] = features["home_off_rating"] - features["home_def_rating"]
    features["away_net_rating"] = features["away_off_rating"] - features["away_def_rating"]
    features["home_win_pct"] = home_team_stats.get("win_pct", 0.5)
    features["away_win_pct"] = away_team_stats.get("win_pct", 0.5)

    # --- Recent form ---
    if recent_games_home:
        last5 = recent_games_home[:5]
        last10 = recent_games_home[:10]
        features["home_win_pct_l5"] = _win_pct(last5)
        features["home_win_pct_l10"] = _win_pct(last10)
        features["home_avg_margin_l5"] = _avg_margin(last5)
    else:
        features["home_win_pct_l5"] = features["home_win_pct"]
        features["home_win_pct_l10"] = features["home_win_pct"]
        features["home_avg_margin_l5"] = 0

    if recent_games_away:
        last5 = recent_games_away[:5]
        last10 = recent_games_away[:10]
        features["away_win_pct_l5"] = _win_pct(last5)
        features["away_win_pct_l10"] = _win_pct(last10)
        features["away_avg_margin_l5"] = _avg_margin(last5)
    else:
        features["away_win_pct_l5"] = features["away_win_pct"]
        features["away_win_pct_l10"] = features["away_win_pct"]
        features["away_avg_margin_l5"] = 0

    # --- Rest and fatigue ---
    features["home_rest_days"] = game.get("home_rest_days", 1) or 1
    features["away_rest_days"] = game.get("away_rest_days", 1) or 1
    features["home_b2b"] = 1 if features["home_rest_days"] == 0 else 0
    features["away_b2b"] = 1 if features["away_rest_days"] == 0 else 0
    features["rest_advantage"] = features["home_rest_days"] - features["away_rest_days"]

    # --- Pace ---
    home_pace = home_team_stats.get("pace", 100)
    away_pace = away_team_stats.get("pace", 100)
    features["home_pace"] = home_pace
    features["away_pace"] = away_pace
    features["pace_matchup_delta"] = home_pace - away_pace
    league_pace = league_avgs.get("pace", 100)
    features["pace_factor"] = (
        ((home_pace + away_pace) / 2) / league_pace if league_pace > 0 else 1.0
    )

    # --- Opponent-adjusted ---
    features["home_off_vs_opp_def"] = features["home_off_rating"] - features["away_def_rating"]
    features["away_off_vs_opp_def"] = features["away_off_rating"] - features["home_def_rating"]

    # --- Injury impact ---
    if injury_impacts:
        features["home_injury_impact"] = injury_impacts.get("home", 0)
        features["away_injury_impact"] = injury_impacts.get("away", 0)
    else:
        features["home_injury_impact"] = 0
        features["away_injury_impact"] = 0

    # --- Line movement ---
    if line_data:
        features["opening_spread"] = line_data.get("opening_spread", 0)
        features["current_spread"] = line_data.get("current_spread", 0)
        features["spread_movement"] = features["current_spread"] - features["opening_spread"]
        features["opening_total"] = line_data.get("opening_total", 0)
        features["current_total"] = line_data.get("current_total", 0)
        features["total_movement"] = features["current_total"] - features["opening_total"]
    else:
        for key in [
            "opening_spread",
            "current_spread",
            "spread_movement",
            "opening_total",
            "current_total",
            "total_movement",
        ]:
            features[key] = 0

    return FeatureVector(
        game_id=game.get("id", ""),
        features=features,
        computed_at=datetime.utcnow(),
    )


def _win_pct(games: list[dict]) -> float:
    """Calculate win percentage from a list of game results."""
    if not games:
        return 0.5
    wins = sum(1 for g in games if g.get("won"))
    return wins / len(games)


def _avg_margin(games: list[dict]) -> float:
    """Calculate average margin of victory from game results."""
    if not games:
        return 0.0
    margins = [g.get("margin", 0) for g in games]
    return sum(margins) / len(margins)
