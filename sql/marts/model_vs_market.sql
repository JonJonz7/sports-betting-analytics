-- model_vs_market: how good are the probabilities? Scored per season and overall on
-- played games that have both a model prediction and a market price.
--   log loss  lower is better; punishes confident wrong answers hard
--   Brier     mean squared error of the probability; lower is better
-- The market (no-vig closing line) is the benchmark every model has to beat.
with scored as (
    select
        f.season,
        f.home_win,
        p.model_prob_home,
        f.elo_prob_home,
        f.home_novig
    from {{ ref('marts.fct_games') }} f
    join {{ ref('marts.predictions') }} p using (game_id)
    where f.is_played and f.home_win is not null and f.home_novig is not null
),

per_game as (
    select
        season,
        -(home_win * ln(model_prob_home) + (1 - home_win) * ln(1 - model_prob_home)) as model_ll,
        -(home_win * ln(elo_prob_home)   + (1 - home_win) * ln(1 - elo_prob_home))   as elo_ll,
        -(home_win * ln(home_novig)      + (1 - home_win) * ln(1 - home_novig))      as market_ll,
        power(model_prob_home - home_win, 2) as model_brier,
        power(home_novig - home_win, 2)      as market_brier,
        ((model_prob_home > 0.5) = (home_win = 1))::int as model_correct,
        ((home_novig > 0.5) = (home_win = 1))::int      as market_correct
    from scored
)

select
    cast(season as varchar)        as season,
    count(*)                       as games,
    round(avg(model_ll), 4)        as model_log_loss,
    round(avg(elo_ll), 4)          as elo_log_loss,
    round(avg(market_ll), 4)       as market_log_loss,
    round(avg(model_brier), 4)     as model_brier,
    round(avg(market_brier), 4)    as market_brier,
    round(avg(model_correct), 4)   as model_accuracy,
    round(avg(market_correct), 4)  as market_accuracy
from per_game
group by season
union all
select
    'ALL', count(*), round(avg(model_ll), 4), round(avg(elo_ll), 4), round(avg(market_ll), 4),
    round(avg(model_brier), 4), round(avg(market_brier), 4),
    round(avg(model_correct), 4), round(avg(market_correct), 4)
from per_game
order by season
