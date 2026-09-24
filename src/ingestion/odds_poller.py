"""Odds ingestion -- polls sportsbook APIs for real-time odds data.

Uses The Odds API (https://the-odds-api.com/) to collect odds across
40+ sportsbooks every 30 seconds during live game windows.

Stores snapshots in TimescaleDB hypertable for historical analysis
and closing line comparison.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime

import httpx

logger = logging.getLogger(__name__)

THE_ODDS_API_BASE = "https://api.the-odds-api.com/v4"

# Sport keys used by The Odds API
SPORT_KEYS = {
    "NFL": "americanfootball_nfl",
    "NBA": "basketball_nba",
    "MLB": "baseball_mlb",
    "NHL": "icehockey_nhl",
    "NCAAF": "americanfootball_ncaaf",
    "NCAAB": "basketball_ncaab",
    "MLS": "soccer_usa_mls",
    "EPL": "soccer_epl",
}


@dataclass
class OddsSnapshot:
    """A single odds reading from one sportsbook for one market."""
    captured_at: datetime
    game_id: str
    sportsbook: str
    market_type: str
    home_odds: int | None
    away_odds: int | None
    draw_odds: int | None
    spread_value: float | None
    total_value: float | None
    over_odds: int | None
    under_odds: int | None


async def fetch_odds(
    sport: str,
    api_key: str,
    markets: list[str] | None = None,
    regions: str = "us",
    odds_format: str = "american",
) -> list[dict]:
    """Fetch current odds from The Odds API.

    Args:
        sport: Sport key (e.g., 'NFL', 'NBA').
        api_key: The Odds API key.
        markets: Market types to fetch. Default: ['h2h', 'spreads', 'totals'].
        regions: Region filter (default 'us' for US sportsbooks).
        odds_format: 'american' or 'decimal'.

    Returns:
        List of game dicts with odds from all bookmakers.
    """
    sport_key = SPORT_KEYS.get(sport, sport)
    if markets is None:
        markets = ["h2h", "spreads", "totals"]

    url = f"{THE_ODDS_API_BASE}/sports/{sport_key}/odds"
    params = {
        "apiKey": api_key,
        "regions": regions,
        "markets": ",".join(markets),
        "oddsFormat": odds_format,
    }

    async with httpx.AsyncClient() as client:
        response = await client.get(url, params=params, timeout=30)
        response.raise_for_status()

        # Log remaining API requests
        remaining = response.headers.get("x-requests-remaining", "?")
        used = response.headers.get("x-requests-used", "?")
        logger.info("Odds API: %s remaining, %s used", remaining, used)

        return response.json()


def parse_odds_response(
    games: list[dict],
    captured_at: datetime | None = None,
) -> list[OddsSnapshot]:
    """Parse The Odds API response into OddsSnapshot records.

    Args:
        games: Raw API response (list of game objects).
        captured_at: Timestamp for this snapshot. Default: now.

    Returns:
        List of OddsSnapshot records ready for database insertion.
    """
    if captured_at is None:
        captured_at = datetime.utcnow()

    snapshots = []

    for game in games:
        game_id = game.get("id", "")

        for bookmaker in game.get("bookmakers", []):
            book_name = bookmaker.get("title", "")

            for market in bookmaker.get("markets", []):
                market_key = market.get("key", "")
                outcomes = market.get("outcomes", [])

                snapshot = _build_snapshot(
                    captured_at=captured_at,
                    game_id=game_id,
                    book_name=book_name,
                    market_key=market_key,
                    outcomes=outcomes,
                )
                if snapshot:
                    snapshots.append(snapshot)

    return snapshots


def _build_snapshot(
    captured_at: datetime,
    game_id: str,
    book_name: str,
    market_key: str,
    outcomes: list[dict],
) -> OddsSnapshot | None:
    """Build a single OddsSnapshot from market outcomes."""
    if not outcomes:
        return None

    if market_key == "h2h":
        home_odds = away_odds = draw_odds = None
        for o in outcomes:
            name = o.get("name", "")
            price = o.get("price")
            # The Odds API labels outcomes by team name, not home/away
            # In production, you'd map team names to home/away from the game object
            if len(outcomes) >= 2:
                if o == outcomes[0]:
                    home_odds = price
                elif o == outcomes[1]:
                    away_odds = price
                elif o.get("name") == "Draw":
                    draw_odds = price

        return OddsSnapshot(
            captured_at=captured_at,
            game_id=game_id,
            sportsbook=book_name,
            market_type="moneyline",
            home_odds=home_odds,
            away_odds=away_odds,
            draw_odds=draw_odds,
            spread_value=None,
            total_value=None,
            over_odds=None,
            under_odds=None,
        )

    elif market_key == "spreads":
        home_spread = home_odds = away_odds = None
        for o in outcomes:
            point = o.get("point")
            price = o.get("price")
            if o == outcomes[0]:
                home_spread = point
                home_odds = price
            else:
                away_odds = price

        return OddsSnapshot(
            captured_at=captured_at,
            game_id=game_id,
            sportsbook=book_name,
            market_type="spread",
            home_odds=home_odds,
            away_odds=away_odds,
            draw_odds=None,
            spread_value=home_spread,
            total_value=None,
            over_odds=None,
            under_odds=None,
        )

    elif market_key == "totals":
        total_value = over_odds = under_odds = None
        for o in outcomes:
            if o.get("name") == "Over":
                total_value = o.get("point")
                over_odds = o.get("price")
            elif o.get("name") == "Under":
                under_odds = o.get("price")

        return OddsSnapshot(
            captured_at=captured_at,
            game_id=game_id,
            sportsbook=book_name,
            market_type="total",
            home_odds=None,
            away_odds=None,
            draw_odds=None,
            spread_value=None,
            total_value=total_value,
            over_odds=over_odds,
            under_odds=under_odds,
        )

    return None
