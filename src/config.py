"""Application configuration -- loaded from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Config:
    """Immutable configuration loaded once at startup."""

    # Database
    database_url: str = field(
        default_factory=lambda: os.getenv(
            "DATABASE_URL", "postgresql://localhost:5432/edgeiq"
        )
    )
    redis_url: str = field(
        default_factory=lambda: os.getenv("REDIS_URL", "redis://localhost:6379/0")
    )

    # External APIs
    odds_api_key: str = field(
        default_factory=lambda: os.getenv("ODDS_API_KEY", "")
    )
    anthropic_api_key: str = field(
        default_factory=lambda: os.getenv("ANTHROPIC_API_KEY", "")
    )

    # EV Engine thresholds
    min_ev_threshold: float = 0.02      # 2% minimum EV to flag opportunity
    min_edge_confidence: float = 0.5    # minimum composite confidence score
    stale_line_minutes: int = 10        # odds unchanged > this = stale warning

    # Bet sizing
    kelly_fraction: float = 0.25        # quarter Kelly default (conservative)
    max_bet_pct: float = 0.05           # never bet more than 5% of bankroll
    min_bet_amount: float = 10.0        # minimum bet size in dollars

    # Model
    min_sample_size: int = 30           # minimum games for correlation/split
    prediction_confidence_floor: float = 0.52  # don't bet if model < 52% confident

    # Odds polling
    poll_interval_live: int = 30        # seconds between polls during game windows
    poll_interval_props: int = 60
    poll_interval_off: int = 300        # 5 min during off-hours

    # CLV
    clv_significance_min_bets: int = 100  # need 100+ bets for significance test


def load_config() -> Config:
    """Load configuration from environment."""
    return Config()
