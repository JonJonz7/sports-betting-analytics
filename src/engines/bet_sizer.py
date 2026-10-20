"""Kelly Criterion bet sizing -- optimal bankroll allocation.

Calculates the mathematically optimal bet size given an edge and odds.
Supports full Kelly, fractional Kelly, and simultaneous Kelly for
multiple concurrent bets.

Enterprise value: Proper bet sizing is the difference between a profitable
operation and a blown bankroll. Most betting operations use fixed-unit sizing
which either over-bets (risk of ruin) or under-bets (leaves money on the table).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class BetSize:
    """Recommended bet sizing for an opportunity."""

    kelly_full: float  # full Kelly fraction of bankroll
    kelly_half: float  # half Kelly (moderate risk)
    kelly_quarter: float  # quarter Kelly (conservative)
    recommended_fraction: float  # the fraction we'd actually recommend
    recommended_amount: float  # dollar amount based on current bankroll
    risk_of_ruin: float  # probability of going bust at this size
    edge_pct: float  # the EV edge this sizing is based on


def kelly_fraction(probability: float, decimal_odds: float) -> float:
    """Calculate the full Kelly Criterion fraction.

    The Kelly Criterion maximizes the expected logarithmic growth rate of
    bankroll. It answers: "What fraction of my bankroll should I bet?"

    Formula: f* = (b*p - q) / b
    where:
        b = decimal_odds - 1 (net payout per dollar wagered)
        p = probability of winning
        q = 1 - p (probability of losing)

    Args:
        probability: Model's estimated win probability (0-1).
        decimal_odds: Decimal odds offered (e.g., 2.0 for even money).

    Returns:
        Optimal fraction of bankroll to wager (0 = no bet).
        Negative values are clamped to 0 (no edge = don't bet).

    >>> round(kelly_fraction(0.55, 2.0), 2)  # 55% at even money
    0.1
    >>> round(kelly_fraction(0.60, 2.5), 4)  # 60% at +150
    0.3333
    >>> kelly_fraction(0.45, 2.0)  # negative edge = don't bet
    0.0
    """
    if probability <= 0 or probability >= 1 or decimal_odds <= 1:
        return 0.0

    b = decimal_odds - 1  # net payout per dollar
    q = 1 - probability
    f = (b * probability - q) / b

    return max(0.0, f)


def simultaneous_kelly(
    bets: list[tuple[float, float]],
) -> list[float]:
    """Calculate Kelly fractions for multiple simultaneous bets.

    When placing multiple bets at the same time, the standard Kelly formula
    overestimates because it assumes the full bankroll is available for each bet.
    This adjusts by solving the simultaneous system.

    Simplified approach: Scale each Kelly fraction so the sum doesn't exceed
    the max portfolio allocation.

    Args:
        bets: List of (probability, decimal_odds) tuples.

    Returns:
        List of adjusted Kelly fractions, one per bet.

    >>> fracs = simultaneous_kelly([(0.55, 2.0), (0.60, 2.5)])
    >>> all(f >= 0 for f in fracs)
    True
    >>> sum(fracs) <= 0.5  # total exposure capped
    True
    """
    individual = [kelly_fraction(p, o) for p, o in bets]

    total = sum(individual)
    if total == 0:
        return individual

    # Cap total allocation at 25% of bankroll for simultaneous bets
    max_total = 0.25
    if total > max_total:
        scale = max_total / total
        return [f * scale for f in individual]

    return individual


def calculate_bet_size(
    probability: float,
    decimal_odds: float,
    bankroll: float,
    kelly_multiplier: float = 0.25,
    max_bet_pct: float = 0.05,
    min_bet: float = 10.0,
) -> BetSize:
    """Calculate recommended bet size with all safety rails.

    Args:
        probability: Model's win probability (0-1).
        decimal_odds: Decimal odds offered.
        bankroll: Current bankroll in dollars.
        kelly_multiplier: Fraction of Kelly to use (0.25 = quarter Kelly).
        max_bet_pct: Maximum bet as fraction of bankroll (hard cap).
        min_bet: Minimum bet size in dollars.

    Returns:
        BetSize with full analysis.

    >>> size = calculate_bet_size(0.55, 2.0, 10000, kelly_multiplier=0.25)
    >>> size.kelly_full
    0.1
    >>> size.recommended_amount
    250.0
    """
    kf = kelly_fraction(probability, decimal_odds)
    ev = (probability * (decimal_odds - 1)) - (1 - probability)

    recommended_frac = min(kf * kelly_multiplier, max_bet_pct)
    recommended_amt = max(bankroll * recommended_frac, 0.0)

    # Enforce minimum bet
    if 0 < recommended_amt < min_bet:
        recommended_amt = 0.0  # Edge too small for minimum bet
        recommended_frac = 0.0

    # Risk of ruin approximation (simplified)
    ror = _risk_of_ruin(probability, decimal_odds, recommended_frac)

    return BetSize(
        kelly_full=round(kf, 4),
        kelly_half=round(kf * 0.5, 4),
        kelly_quarter=round(kf * 0.25, 4),
        recommended_fraction=round(recommended_frac, 4),
        recommended_amount=round(recommended_amt, 2),
        risk_of_ruin=round(ror, 6),
        edge_pct=round(ev, 4),
    )


def _risk_of_ruin(
    probability: float,
    decimal_odds: float,
    bet_fraction: float,
    ruin_threshold: float = 0.1,
) -> float:
    """Estimate probability of bankroll dropping to ruin_threshold of peak.

    Uses the simplified formula:
        RoR = ((1-p)/p)^(bankroll_units)
    where bankroll_units = 1 / bet_fraction

    Args:
        probability: Win probability.
        decimal_odds: Decimal odds.
        bet_fraction: Fraction of bankroll wagered per bet.
        ruin_threshold: Fraction of bankroll that counts as "ruin" (default 10%).

    Returns:
        Probability of ruin (0-1).
    """
    if bet_fraction <= 0 or probability >= 1 or probability <= 0:
        return 0.0

    # Number of bets the bankroll can sustain
    units = 1.0 / bet_fraction

    # Simplified geometric random walk approximation
    if probability <= 0.5:
        return 1.0  # No edge = eventual ruin

    ratio = (1 - probability) / probability
    ror = ratio ** (units * (1 - ruin_threshold))

    return min(1.0, max(0.0, ror))


def drawdown_adjusted_size(
    base_fraction: float,
    current_bankroll: float,
    peak_bankroll: float,
    drawdown_scale: float = 2.0,
) -> float:
    """Reduce bet size during drawdowns to preserve capital.

    When the bankroll is below its peak, scale down bets proportionally.
    This prevents aggressive sizing during losing streaks.

    Args:
        base_fraction: Normal Kelly fraction.
        current_bankroll: Current bankroll.
        peak_bankroll: All-time high bankroll.
        drawdown_scale: How aggressively to reduce (2.0 = squared reduction).

    Returns:
        Adjusted fraction.

    >>> round(drawdown_adjusted_size(0.05, 8000, 10000), 4)  # 20% drawdown
    0.032
    """
    if peak_bankroll <= 0 or current_bankroll >= peak_bankroll:
        return base_fraction

    ratio = current_bankroll / peak_bankroll
    adjustment = ratio**drawdown_scale

    return base_fraction * adjustment
