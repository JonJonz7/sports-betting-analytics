"""+EV Discrepancy Engine -- identifies positive expected value betting opportunities.

Compares model-generated probabilities against real-time sportsbook odds to surface
bets where the bettor has a mathematical edge. Accounts for vig removal, CLV history,
and injury uncertainty.

Enterprise value: This is the core revenue engine. A sportsbook operator uses this
in reverse to detect where their lines are exploitable. An analytics firm uses it
to prove signal quality to subscribers.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum


class VigRemovalMethod(Enum):
    """Methods for removing sportsbook vig to get fair probabilities."""
    ADDITIVE = "additive"
    MULTIPLICATIVE = "multiplicative"
    SHIN = "shin"
    POWER = "power"


@dataclass
class EVOpportunity:
    """A detected +EV betting opportunity."""
    game_id: str
    market_type: str           # 'moneyline', 'spread', 'total', 'player_prop'
    selection: str             # 'home', 'away', 'over', 'under'
    sportsbook: str
    model_prob: float          # model's estimated probability (0-1)
    market_implied: float      # sportsbook's implied probability after vig removal
    ev_pct: float              # expected value as percentage
    edge_confidence: float     # composite confidence score (0-1)
    odds_american: int         # American odds at detection
    kelly_full: float          # full Kelly fraction
    kelly_quarter: float       # quarter Kelly fraction


def american_to_decimal(american: int) -> float:
    """Convert American odds to decimal odds.

    American odds: -110 means bet $110 to win $100.
                   +150 means bet $100 to win $150.

    >>> american_to_decimal(-110)
    1.909090909090909
    >>> american_to_decimal(+150)
    2.5
    """
    if american > 0:
        return 1 + american / 100
    return 1 + 100 / abs(american)


def decimal_to_implied(decimal_odds: float) -> float:
    """Convert decimal odds to implied probability.

    >>> round(decimal_to_implied(2.0), 2)
    0.5
    >>> round(decimal_to_implied(1.5), 4)
    0.6667
    """
    if decimal_odds <= 0:
        return 0.0
    return 1.0 / decimal_odds


def remove_vig_additive(
    implied_probs: list[float],
) -> list[float]:
    """Remove vig using the additive method (simplest).

    Divides each implied probability by the sum of all implied probabilities
    (the overround) to normalize to 100%.

    Args:
        implied_probs: List of implied probabilities from market odds.

    Returns:
        List of fair (no-vig) probabilities summing to 1.0.

    >>> probs = remove_vig_additive([0.5238, 0.5238])  # -110/-110 market
    >>> round(sum(probs), 2)
    1.0
    >>> round(probs[0], 4)
    0.5
    """
    overround = sum(implied_probs)
    if overround == 0:
        return implied_probs
    return [p / overround for p in implied_probs]


def remove_vig_multiplicative(
    implied_probs: list[float],
) -> list[float]:
    """Remove vig using the multiplicative (proportional) method.

    Better than additive for markets with large favorite-longshot spreads.
    Each probability is raised to the power of (1 / overround).

    >>> probs = remove_vig_multiplicative([0.7692, 0.2857])  # -333/+250
    >>> abs(sum(probs) - 1.0) < 0.01
    True
    """
    overround = sum(implied_probs)
    if overround == 0:
        return implied_probs
    k = 1.0 / overround
    fair = [p ** k for p in implied_probs]
    # Renormalize to handle floating point
    total = sum(fair)
    return [p / total for p in fair]


def remove_vig_shin(
    implied_probs: list[float],
    max_iterations: int = 100,
) -> list[float]:
    """Remove vig using the Shin method.

    Accounts for the favorite-longshot bias by modeling the proportion of
    informed bettors in the market. More accurate for exotic markets.

    Reference: Shin, H.S. (1993). "Measuring the Incidence of Insider Trading
    in a Market for State-Contingent Claims."
    """
    n = len(implied_probs)
    overround = sum(implied_probs)
    if overround <= 1.0:
        return implied_probs

    # Binary search for Shin parameter z
    z_low, z_high = 0.0, 1.0
    for _ in range(max_iterations):
        z = (z_low + z_high) / 2
        fair = []
        for p in implied_probs:
            discriminant = z**2 + 4 * (1 - z) * (p**2 / overround)
            fair_p = (math.sqrt(discriminant) - z) / (2 * (1 - z))
            fair.append(fair_p)

        total = sum(fair)
        if abs(total - 1.0) < 1e-8:
            return fair
        elif total > 1.0:
            z_low = z
        else:
            z_high = z

    # Fallback to additive if Shin doesn't converge
    return remove_vig_additive(implied_probs)


def calculate_ev(model_prob: float, decimal_odds: float) -> float:
    """Calculate expected value of a bet.

    EV = (probability * payout) - (1 - probability) * stake
    For a $1 bet: EV = p * (odds - 1) - (1 - p)

    A positive EV means the bet has mathematical edge.

    Args:
        model_prob: Model's estimated probability of the outcome (0-1).
        decimal_odds: Decimal odds offered by the sportsbook.

    Returns:
        Expected value as a decimal (0.05 = 5% edge).

    >>> round(calculate_ev(0.55, 2.0), 2)  # 55% prob at even money
    0.1
    >>> round(calculate_ev(0.50, 2.0), 2)  # 50% prob at even money = no edge
    0.0
    >>> round(calculate_ev(0.45, 2.0), 2)  # 45% prob at even money = negative EV
    -0.1
    """
    return model_prob * (decimal_odds - 1) - (1 - model_prob)


def calculate_edge_confidence(
    base_ev: float,
    model_clv_history: float | None = None,
    market_volume: str = "high",
    line_age_minutes: int = 0,
    injury_uncertainty: float = 0.0,
) -> float:
    """Calculate composite confidence score for an EV opportunity.

    Factors:
    - base_ev: Higher EV = more confident (but extreme EV can mean model error)
    - model_clv_history: Past CLV proves model quality
    - market_volume: High-volume markets are more efficient (edge more meaningful)
    - line_age_minutes: Stale lines might be traps
    - injury_uncertainty: Uncertain injury status reduces confidence

    Returns:
        Confidence score between 0 and 1.
    """
    # Base: EV contributes, but cap extreme values (might be model error)
    ev_score = min(base_ev * 5, 0.4)  # 8% EV = 0.4, max contribution

    # CLV history bonus: proven model gets up to +0.25
    clv_bonus = 0.0
    if model_clv_history is not None and model_clv_history > 0:
        clv_bonus = min(model_clv_history * 10, 0.25)

    # Volume bonus: high-volume = more efficient market = edge more meaningful
    volume_scores = {"high": 0.15, "medium": 0.10, "low": 0.05}
    volume_bonus = volume_scores.get(market_volume, 0.10)

    # Stale line penalty: odds unchanged for too long = possible trap
    stale_penalty = 0.0
    if line_age_minutes > 10:
        stale_penalty = min((line_age_minutes - 10) * 0.005, 0.15)

    # Injury uncertainty penalty
    injury_penalty = injury_uncertainty * 0.2

    confidence = ev_score + clv_bonus + volume_bonus - stale_penalty - injury_penalty
    return max(0.0, min(1.0, confidence))


def scan_for_ev(
    model_predictions: dict[str, float],
    market_odds: dict[str, dict[str, int]],
    vig_method: VigRemovalMethod = VigRemovalMethod.SHIN,
    min_ev: float = 0.02,
) -> list[EVOpportunity]:
    """Scan all markets for +EV opportunities.

    Args:
        model_predictions: Dict mapping outcome keys to model probabilities.
            e.g. {"home_ml": 0.58, "away_ml": 0.42, "over_220": 0.53}
        market_odds: Dict mapping sportsbook names to outcome odds.
            e.g. {"DraftKings": {"home_ml": -150, "away_ml": +130},
                   "FanDuel":   {"home_ml": -145, "away_ml": +125}}
        vig_method: Method for removing vig from market odds.
        min_ev: Minimum EV threshold to flag (default 2%).

    Returns:
        List of EVOpportunity objects, sorted by EV descending.
    """
    from .bet_sizer import kelly_fraction

    vig_removers = {
        VigRemovalMethod.ADDITIVE: remove_vig_additive,
        VigRemovalMethod.MULTIPLICATIVE: remove_vig_multiplicative,
        VigRemovalMethod.SHIN: remove_vig_shin,
    }
    remove_vig = vig_removers.get(vig_method, remove_vig_additive)

    opportunities: list[EVOpportunity] = []

    for book_name, book_odds in market_odds.items():
        # Group odds by market for vig removal
        # For each outcome, calculate EV against model
        for outcome_key, odds_american in book_odds.items():
            if outcome_key not in model_predictions:
                continue

            model_prob = model_predictions[outcome_key]
            decimal_odds = american_to_decimal(odds_american)
            market_implied = decimal_to_implied(decimal_odds)

            ev = calculate_ev(model_prob, decimal_odds)

            if ev >= min_ev:
                kf = kelly_fraction(model_prob, decimal_odds)
                confidence = calculate_edge_confidence(base_ev=ev)

                opportunities.append(
                    EVOpportunity(
                        game_id="",  # populated by caller
                        market_type=_infer_market_type(outcome_key),
                        selection=outcome_key,
                        sportsbook=book_name,
                        model_prob=model_prob,
                        market_implied=market_implied,
                        ev_pct=ev,
                        edge_confidence=confidence,
                        odds_american=odds_american,
                        kelly_full=kf,
                        kelly_quarter=kf * 0.25,
                    )
                )

    opportunities.sort(key=lambda x: x.ev_pct, reverse=True)
    return opportunities


def _infer_market_type(outcome_key: str) -> str:
    """Infer market type from outcome key naming convention."""
    key = outcome_key.lower()
    if "ml" in key:
        return "moneyline"
    if "spread" in key:
        return "spread"
    if "over" in key or "under" in key or "total" in key:
        return "total"
    if "points" in key or "rebounds" in key or "yards" in key:
        return "player_prop"
    return "unknown"
