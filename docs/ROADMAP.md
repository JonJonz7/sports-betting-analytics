# Roadmap

What isn't built yet, in priority order.

1. **Earlier prices → real CLV.** Snapshot odds during the week (The Odds API free tier, or a historical odds dataset) so bets can be placed before the close and CLV measured. Wire `src/ingestion/odds_poller.py` into bronze as a second source.
2. **Spreads and totals.** The data has them; model margin and total points (Poisson score model in `src/models/game_predictor.py`) and score the cover and over probabilities.
3. **More features, tested one at a time:** QB changes (`away_qb_id`/`home_qb_id` in the source), weather for outdoor games, travel. Keep only what improves walk-forward log loss.
4. **Calibration step:** isotonic or Platt scaling on the walk-forward predictions before sizing bets.
5. **Live system:** `schema/` (Postgres + TimescaleDB) and `docker-compose.yml` describe storage for live odds; build it once item 1 exists.
6. **Injury text:** `src/intelligence/narrative_parser.py` (Claude API, paid) is optional; evaluate it only against a labeled set and the market.
