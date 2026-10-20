"""Player stat projection -- usage-rate adjusted projections for props markets.

Projects player stats by:
1. Estimating minutes/playing time
2. Applying per-minute stat rates
3. Adjusting for opponent, pace, and game context

Enterprise value: Player props are the fastest-growing betting market and the
least efficient. Books set lines based on season averages; usage-adjusted
projections capture matchup edges.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class PlayerProjection:
    """Projected stats for a player in a specific game."""

    player_id: str
    player_name: str
    game_id: str
    projected_minutes: float
    projections: dict[str, float]  # stat_name -> projected value
    confidence: float  # 0-1


def project_player_stats(
    player_season: dict,
    opponent_defense: dict,
    team_pace: float,
    opponent_pace: float,
    league_avg_pace: float,
    projected_minutes: float | None = None,
    blowout_risk: float = 0.0,
) -> dict[str, float]:
    """Project a player's stats for a specific game.

    Methodology:
    1. Start with per-minute rates from season data
    2. Estimate minutes (or use provided projection)
    3. Adjust for opponent defensive ranking
    4. Adjust for game pace
    5. Apply blowout risk (star bench time in blowouts)

    Args:
        player_season: Player's season averages and per-minute rates.
            Expected keys: minutes_pg, points_pm, rebounds_pm, assists_pm, etc.
        opponent_defense: Opponent's defensive ratings.
            Expected keys: pts_allowed_rank, reb_allowed_rank, etc. (1=best, 30=worst)
        team_pace: Player's team pace (possessions per 48 min).
        opponent_pace: Opponent's pace.
        league_avg_pace: League average pace.
        projected_minutes: Override for minutes projection.
        blowout_risk: Probability of a blowout (0-1), reduces minutes.

    Returns:
        Dict of projected stats: points, rebounds, assists, etc.

    >>> stats = project_player_stats(
    ...     {"minutes_pg": 34, "points_pm": 0.85, "rebounds_pm": 0.24, "assists_pm": 0.18},
    ...     {"pts_allowed_rank": 25},  # weak defense
    ...     team_pace=100, opponent_pace=102, league_avg_pace=100,
    ... )
    >>> stats["points"] > 28  # should be above average vs weak defense
    True
    """
    # Step 1: Estimate minutes
    base_minutes = projected_minutes or player_season.get("minutes_pg", 30)

    # Blowout adjustment: reduce minutes by expected garbage time
    if blowout_risk > 0:
        # In a blowout, starters lose ~8 minutes on average
        minutes_reduction = blowout_risk * 8
        base_minutes = max(base_minutes - minutes_reduction, 12)

    # Step 2: Per-minute rates
    points_pm = player_season.get("points_pm", 0.7)
    rebounds_pm = player_season.get("rebounds_pm", 0.2)
    assists_pm = player_season.get("assists_pm", 0.15)
    threes_pm = player_season.get("threes_pm", 0.08)
    steals_pm = player_season.get("steals_pm", 0.03)
    blocks_pm = player_season.get("blocks_pm", 0.02)
    turnovers_pm = player_season.get("turnovers_pm", 0.08)

    # Step 3: Opponent adjustment
    # Rank 1 = best defense, 30 = worst. Normalize to multiplier around 1.0
    def _opp_multiplier(rank: int, num_teams: int = 30) -> float:
        """Convert defensive rank to a scoring multiplier.
        Rank 1 (best D) -> ~0.90, Rank 30 (worst D) -> ~1.10
        """
        if num_teams <= 1:
            return 1.0
        # Linear scaling: rank 1 = 0.90, rank 30 = 1.10
        return 0.90 + (rank - 1) * (0.20 / (num_teams - 1))

    pts_multiplier = _opp_multiplier(opponent_defense.get("pts_allowed_rank", 15))
    reb_multiplier = _opp_multiplier(opponent_defense.get("reb_allowed_rank", 15))
    ast_multiplier = _opp_multiplier(opponent_defense.get("ast_allowed_rank", 15))

    # Step 4: Pace adjustment
    expected_pace = (team_pace + opponent_pace) / 2
    pace_factor = expected_pace / league_avg_pace if league_avg_pace > 0 else 1.0

    # Step 5: Calculate projections
    projections = {
        "minutes": round(base_minutes, 1),
        "points": round(points_pm * base_minutes * pts_multiplier * pace_factor, 1),
        "rebounds": round(rebounds_pm * base_minutes * reb_multiplier * pace_factor, 1),
        "assists": round(assists_pm * base_minutes * ast_multiplier * pace_factor, 1),
        "threes": round(threes_pm * base_minutes * pace_factor, 1),
        "steals": round(steals_pm * base_minutes * pace_factor, 1),
        "blocks": round(blocks_pm * base_minutes * pace_factor, 1),
        "turnovers": round(turnovers_pm * base_minutes * pace_factor, 1),
    }

    # Derived: points + rebounds + assists (PRA) - common prop market
    projections["pra"] = round(
        projections["points"] + projections["rebounds"] + projections["assists"], 1
    )

    return projections


def prop_probability(
    projection: float,
    line: float,
    historical_std: float | None = None,
) -> dict[str, float]:
    """Estimate over/under probability for a player prop line.

    Uses a normal distribution centered on the projection with
    historical standard deviation.

    Args:
        projection: Projected stat value.
        line: The sportsbook's prop line (e.g., 24.5 points).
        historical_std: Standard deviation from player's game log.
            If None, estimates as 25% of projection.

    Returns:
        Dict with over_prob and under_prob.

    >>> result = prop_probability(28.0, 24.5, historical_std=6.0)
    >>> result["over_prob"] > 0.5  # projection > line
    True
    """
    import math

    if historical_std is None:
        historical_std = max(projection * 0.25, 1.0)  # rough estimate

    if historical_std <= 0:
        # No variance: deterministic
        return {
            "over_prob": 1.0 if projection > line else 0.0,
            "under_prob": 1.0 if projection < line else 0.0,
        }

    # Z-score: how many SDs is the line from the projection?
    z = (line - projection) / historical_std

    # CDF using error function
    under_prob = 0.5 * (1 + math.erf(z / math.sqrt(2)))
    over_prob = 1 - under_prob

    return {
        "over_prob": round(over_prob, 4),
        "under_prob": round(under_prob, 4),
    }
