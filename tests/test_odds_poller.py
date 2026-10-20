from datetime import datetime

from src.ingestion.odds_poller import parse_odds_response

GAME = {
    "id": "evt1",
    "home_team": "Kansas City Chiefs",
    "away_team": "Baltimore Ravens",
    "bookmakers": [
        {
            "title": "DraftKings",
            "markets": [
                # The Odds API lists outcomes in no fixed order: away first here
                {
                    "key": "h2h",
                    "outcomes": [
                        {"name": "Baltimore Ravens", "price": 124},
                        {"name": "Kansas City Chiefs", "price": -148},
                    ],
                },
                {
                    "key": "spreads",
                    "outcomes": [
                        {"name": "Baltimore Ravens", "price": -110, "point": 3},
                        {"name": "Kansas City Chiefs", "price": -110, "point": -3},
                    ],
                },
            ],
        }
    ],
}


def test_sides_are_matched_by_team_name_not_position():
    snaps = {s.market_type: s for s in parse_odds_response([GAME], datetime(2024, 9, 5))}
    assert snaps["moneyline"].home_odds == -148 and snaps["moneyline"].away_odds == 124
    assert snaps["spread"].spread_value == -3


def test_unmatched_names_are_skipped_not_guessed():
    bad = {**GAME, "home_team": "Someone Else"}
    assert parse_odds_response([bad], datetime(2024, 9, 5)) == []
