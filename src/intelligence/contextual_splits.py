"""Contextual Split & Usage Model -- SQL-driven situational analysis.

Computes performance splits for teams and players across dimensions like
home/away, rest days, divisional games, indoor/outdoor, and referee tendencies.
All heavy lifting is done in PostgreSQL for speed.

Enterprise value: Situational edges are invisible to models that only use
season averages. A team's 3-point shooting splits home vs away, or a QB's
performance on short rest, can move the true probability 2-5%.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SplitResult:
    """A single contextual split comparison."""

    entity_type: str  # 'team' or 'player'
    entity_name: str
    split_type: str  # 'home_away', 'rest_days', 'division', etc.
    baseline_value: float  # performance in baseline condition
    split_value: float  # performance in split condition
    delta: float  # split_value - baseline_value
    delta_pct: float  # delta as percentage of baseline
    sample_size: int
    significant: bool  # is the split statistically meaningful?


# SQL queries for each split type
# These run against the PostgreSQL database directly

SPLIT_QUERIES: dict[str, str] = {
    "home_away": """
        -- Team performance: home vs away
        WITH team_games AS (
            SELECT
                g.id,
                CASE WHEN g.home_team_id = %(team_id)s THEN 'home' ELSE 'away' END AS venue,
                CASE WHEN g.home_team_id = %(team_id)s THEN g.home_score ELSE g.away_score END AS team_score,
                CASE WHEN g.home_team_id = %(team_id)s THEN g.away_score ELSE g.home_score END AS opp_score,
                CASE
                    WHEN g.home_team_id = %(team_id)s AND g.home_score > g.away_score THEN 1
                    WHEN g.away_team_id = %(team_id)s AND g.away_score > g.home_score THEN 1
                    ELSE 0
                END AS won
            FROM games g
            WHERE (g.home_team_id = %(team_id)s OR g.away_team_id = %(team_id)s)
              AND g.status = 'final'
              AND g.scheduled_at >= %(season_start)s
        )
        SELECT
            venue,
            COUNT(*) AS games,
            ROUND(AVG(team_score)::numeric, 1) AS avg_scored,
            ROUND(AVG(opp_score)::numeric, 1) AS avg_allowed,
            ROUND(AVG(won)::numeric * 100, 1) AS win_pct,
            ROUND(AVG(team_score + opp_score)::numeric, 1) AS avg_total
        FROM team_games
        GROUP BY venue
        ORDER BY venue;
    """,
    "rest_days": """
        -- Performance by rest days (0 = back-to-back)
        WITH team_games AS (
            SELECT
                g.id,
                CASE WHEN g.home_team_id = %(team_id)s THEN g.home_rest_days
                     ELSE g.away_rest_days END AS rest,
                CASE WHEN g.home_team_id = %(team_id)s THEN g.home_score ELSE g.away_score END AS team_score,
                CASE WHEN g.home_team_id = %(team_id)s THEN g.away_score ELSE g.home_score END AS opp_score,
                CASE
                    WHEN g.home_team_id = %(team_id)s AND g.home_score > g.away_score THEN 1
                    WHEN g.away_team_id = %(team_id)s AND g.away_score > g.home_score THEN 1
                    ELSE 0
                END AS won
            FROM games g
            WHERE (g.home_team_id = %(team_id)s OR g.away_team_id = %(team_id)s)
              AND g.status = 'final'
              AND g.scheduled_at >= %(season_start)s
        )
        SELECT
            CASE
                WHEN rest = 0 THEN 'back_to_back'
                WHEN rest = 1 THEN '1_day_rest'
                WHEN rest = 2 THEN '2_days_rest'
                ELSE '3_plus_rest'
            END AS rest_bucket,
            COUNT(*) AS games,
            ROUND(AVG(team_score)::numeric, 1) AS avg_scored,
            ROUND(AVG(won)::numeric * 100, 1) AS win_pct,
            ROUND(AVG(team_score + opp_score)::numeric, 1) AS avg_total
        FROM team_games
        WHERE rest IS NOT NULL
        GROUP BY rest_bucket
        ORDER BY rest_bucket;
    """,
    "division": """
        -- Performance: divisional vs non-divisional games
        WITH team_games AS (
            SELECT
                g.id,
                CASE
                    WHEN t_home.division = t_away.division THEN 'divisional'
                    ELSE 'non_divisional'
                END AS game_type,
                CASE WHEN g.home_team_id = %(team_id)s THEN g.home_score ELSE g.away_score END AS team_score,
                CASE WHEN g.home_team_id = %(team_id)s THEN g.away_score ELSE g.home_score END AS opp_score,
                CASE
                    WHEN g.home_team_id = %(team_id)s AND g.home_score > g.away_score THEN 1
                    WHEN g.away_team_id = %(team_id)s AND g.away_score > g.home_score THEN 1
                    ELSE 0
                END AS won
            FROM games g
            JOIN teams t_home ON t_home.id = g.home_team_id
            JOIN teams t_away ON t_away.id = g.away_team_id
            WHERE (g.home_team_id = %(team_id)s OR g.away_team_id = %(team_id)s)
              AND g.status = 'final'
              AND g.scheduled_at >= %(season_start)s
        )
        SELECT
            game_type,
            COUNT(*) AS games,
            ROUND(AVG(team_score)::numeric, 1) AS avg_scored,
            ROUND(AVG(won)::numeric * 100, 1) AS win_pct,
            ROUND(AVG(team_score - opp_score)::numeric, 1) AS avg_margin
        FROM team_games
        GROUP BY game_type;
    """,
    "player_home_away": """
        -- Player stats: home vs away
        SELECT
            CASE WHEN g.home_team_id = pgs.team_id THEN 'home' ELSE 'away' END AS venue,
            COUNT(*) AS games,
            ROUND(AVG(pgs.minutes)::numeric, 1) AS avg_minutes,
            ROUND(AVG((pgs.stats->>'points')::numeric)::numeric, 1) AS avg_points,
            ROUND(AVG((pgs.stats->>'rebounds')::numeric)::numeric, 1) AS avg_rebounds,
            ROUND(AVG((pgs.stats->>'assists')::numeric)::numeric, 1) AS avg_assists
        FROM player_game_stats pgs
        JOIN games g ON g.id = pgs.game_id
        WHERE pgs.player_id = %(player_id)s
          AND g.status = 'final'
          AND g.scheduled_at >= %(season_start)s
        GROUP BY venue;
    """,
    "referee_tendencies": """
        -- Referee crew: average total and foul rate
        SELECT
            g.referee_crew,
            COUNT(*) AS games,
            ROUND(AVG(g.home_score + g.away_score)::numeric, 1) AS avg_total,
            ROUND(AVG(g.home_score + g.away_score)::numeric, 1) -
                (SELECT ROUND(AVG(home_score + away_score)::numeric, 1)
                 FROM games
                 WHERE league_id = %(league_id)s AND status = 'final'
                   AND scheduled_at >= %(season_start)s) AS total_vs_avg
        FROM games g
        WHERE g.league_id = %(league_id)s
          AND g.status = 'final'
          AND g.referee_crew IS NOT NULL
          AND g.scheduled_at >= %(season_start)s
        GROUP BY g.referee_crew
        HAVING COUNT(*) >= 10
        ORDER BY avg_total DESC;
    """,
}


def get_team_splits(
    team_id: str,
    split_types: list[str] | None = None,
    season_start: str = "2024-10-01",
    db_connection=None,
) -> dict[str, list[dict]]:
    """Fetch team performance splits from the database.

    Args:
        team_id: UUID of the team.
        split_types: Which splits to compute. Default: all.
        season_start: Start date for the analysis window.
        db_connection: Database connection (psycopg2 or SQLAlchemy).

    Returns:
        Dict mapping split_type -> list of result rows.
    """
    if split_types is None:
        split_types = ["home_away", "rest_days", "division"]

    results = {}
    for split_type in split_types:
        query = SPLIT_QUERIES.get(split_type)
        if not query:
            continue

        params = {"team_id": team_id, "season_start": season_start}

        if db_connection is not None:
            cursor = db_connection.cursor()
            cursor.execute(query, params)
            columns = [desc[0] for desc in cursor.description]
            rows = [dict(zip(columns, row)) for row in cursor.fetchall()]
            results[split_type] = rows
        else:
            # Return empty for testing without DB
            results[split_type] = []

    return results


def get_player_splits(
    player_id: str,
    split_types: list[str] | None = None,
    season_start: str = "2024-10-01",
    db_connection=None,
) -> dict[str, list[dict]]:
    """Fetch player performance splits from the database.

    Args:
        player_id: UUID of the player.
        split_types: Which splits to compute. Default: home_away.
        season_start: Start date for the analysis window.
        db_connection: Database connection.

    Returns:
        Dict mapping split_type -> list of result rows.
    """
    if split_types is None:
        split_types = ["player_home_away"]

    results = {}
    for split_type in split_types:
        query = SPLIT_QUERIES.get(split_type)
        if not query:
            continue

        params = {"player_id": player_id, "season_start": season_start}

        if db_connection is not None:
            cursor = db_connection.cursor()
            cursor.execute(query, params)
            columns = [desc[0] for desc in cursor.description]
            rows = [dict(zip(columns, row)) for row in cursor.fetchall()]
            results[split_type] = rows
        else:
            results[split_type] = []

    return results


def calculate_split_impact(
    baseline_stat: float,
    split_stat: float,
    sample_size: int,
    min_sample: int = 10,
) -> SplitResult | None:
    """Determine if a split is meaningful enough to adjust predictions.

    Args:
        baseline_stat: Average in the baseline condition.
        split_stat: Average in the split condition.
        sample_size: Number of observations in the split.
        min_sample: Minimum sample size to consider.

    Returns:
        SplitResult if sample is large enough, else None.
    """
    if sample_size < min_sample or baseline_stat == 0:
        return None

    delta = split_stat - baseline_stat
    delta_pct = (delta / baseline_stat) * 100

    # Simple significance check: delta must be > 1 standard error
    # Rough approximation: SE ~ baseline * 0.1 / sqrt(n)
    se_approx = baseline_stat * 0.1 / (sample_size**0.5)
    significant = abs(delta) > 2 * se_approx and sample_size >= 20

    return SplitResult(
        entity_type="",
        entity_name="",
        split_type="",
        baseline_value=baseline_stat,
        split_value=split_stat,
        delta=round(delta, 2),
        delta_pct=round(delta_pct, 2),
        sample_size=sample_size,
        significant=significant,
    )
