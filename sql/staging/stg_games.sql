-- stg_games: one row per game, typed, with the betting market translated into probabilities.
-- Grain: game_id.
--
-- American odds -> implied probability:  -150 -> 150/250 = 0.600   +130 -> 100/230 = 0.435
-- The two sides add up to MORE than 1 (here 1.035): that extra is the bookmaker's margin
-- ("overround" / "vig"). Dividing each side by the total removes it ("no-vig" probability),
-- which is the market's honest estimate of the chance each team wins.
with src as (
    select * from read_parquet('{{ lake }}/bronze/games/**/*.parquet', hive_partitioning = true)
),

typed as (
    select
        game_id,
        cast(season as integer)                                     as season,
        game_type,
        week,
        cast(gameday as date)                                       as game_date,
        home_team,
        away_team,
        home_score,
        away_score,
        home_score is not null and away_score is not null           as is_played,
        case when home_score > away_score then 1
             when home_score < away_score then 0 end                as home_win,   -- ties stay NULL
        home_rest,
        away_rest,
        coalesce(div_game = 1, false)                               as is_division,
        game_type <> 'REG'                                          as is_playoff,
        roof,
        temp,
        wind,
        nullif(home_moneyline, 0)                                   as home_moneyline,
        nullif(away_moneyline, 0)                                   as away_moneyline,
        spread_line,
        total_line
    from src
),

implied as (
    select
        *,
        case when home_moneyline < 0 then -home_moneyline / (-home_moneyline + 100.0)
             else 100.0 / (home_moneyline + 100.0) end              as home_implied,
        case when away_moneyline < 0 then -away_moneyline / (-away_moneyline + 100.0)
             else 100.0 / (away_moneyline + 100.0) end              as away_implied
    from typed
),

flagged as (
    select
        *,
        home_implied + away_implied                                 as overround,
        -- Quarantine impossible prices instead of dropping the game. Two sides summing to
        -- under 100% would be a guaranteed profit no single book offers: a data error
        -- (found in the real data: 2020_01_LV_CAR, +134 / -124).
        case
            when home_moneyline is null or away_moneyline is null then 'no_odds'
            when home_implied + away_implied < 1.0 then 'below_100pct'
            when home_implied + away_implied > 1.15 then 'margin_over_15pct'
            else 'ok'
        end                                                         as market_flag
    from implied
)

select
    *,
    case when market_flag = 'ok' then home_implied / overround end  as home_novig,
    case when market_flag = 'ok' then away_implied / overround end  as away_novig
from flagged
