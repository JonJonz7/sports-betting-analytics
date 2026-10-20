-- stg_team_games: the same games "unpivoted" to one row per TEAM per game, so per-team
-- questions (rest, home/away splits, form) are simple GROUP BYs.
-- Grain: (game_id, team).
select game_id, season, week, game_date, home_team as team, away_team as opponent, true as is_home,
       home_score as points_for, away_score as points_against, home_rest as rest_days,
       is_division, is_played
from {{ ref('staging.stg_games') }}
union all
select game_id, season, week, game_date, away_team, home_team, false,
       away_score, home_score, away_rest, is_division, is_played
from {{ ref('staging.stg_games') }}
