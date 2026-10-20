-- fct_games: everything known about a game BEFORE kickoff, plus the result.
-- Features are point-in-time: Elo ratings are the ratings going INTO the game.
-- Grain: game_id.
select
    g.*,
    e.elo_home_pre,
    e.elo_away_pre,
    e.elo_home_pre - e.elo_away_pre                 as elo_diff,
    e.elo_prob_home,
    coalesce(g.home_rest, 7) - coalesce(g.away_rest, 7) as rest_diff
from {{ ref('staging.stg_games') }} g
left join {{ ref('features.elo_ratings') }} e using (game_id)
