"""Closing Line Value (CLV) Tracker -- the gold standard for measuring betting skill.

CLV measures whether you consistently bet at better odds than the market's closing
price. Positive CLV over a large sample is the strongest evidence of genuine
edge -- even if individual bets lose.

Why CLV matters more than win rate:
- A 52% win rate at -110 odds is profitable, but might be luck over 100 bets
- Consistent +2% CLV over 1000 bets is statistically provable edge (p < 0.01)
- Every sharp betting operation tracks CLV as their primary KPI

Enterprise value: Sportsbooks use CLV to identify sharp bettors for limiting.
Analytics firms use CLV to prove their picks have genuine edge, not luck.
"""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass
class CLVResult:
    """CLV measurement for a single bet."""
    bet_odds_american: int
    closing_odds_american: int
    bet_implied: float          # implied probability at bet time
    closing_implied: float      # implied probability at close
    clv_pct: float              # CLV as percentage
    clv_cents: float            # CLV in cents (e.g., +3.2 cents on the dollar)
    beat_close: bool            # did the bettor get better odds than close?


@dataclass
class CLVSummary:
    """Aggregate CLV statistics over a sample of bets."""
    total_bets: int
    avg_clv_pct: float
    median_clv_pct: float
    std_clv_pct: float
    t_statistic: float
    p_value: float
    significant: bool           # is CLV significantly > 0?
    confidence_interval: tuple[float, float]  # 95% CI
    beat_close_rate: float      # % of bets that beat the closing line
    best_clv: float
    worst_clv: float


def american_to_implied(american: int) -> float:
    """Convert American odds to implied probability.

    >>> round(american_to_implied(-110), 4)
    0.5238
    >>> round(american_to_implied(150), 4)
    0.4
    """
    if american < 0:
        return abs(american) / (abs(american) + 100)
    return 100 / (american + 100)


def calculate_clv(
    bet_odds: int,
    closing_odds: int,
) -> CLVResult:
    """Calculate closing line value for a single bet.

    CLV = (closing_implied - bet_implied) / closing_implied * 100

    If you bet at -110 (52.38% implied) and the line closes at -120 (54.55% implied),
    you got a better price than the market settled on. CLV = +3.97%.

    Args:
        bet_odds: American odds at the time of bet placement.
        closing_odds: American odds at market close (game start).

    Returns:
        CLVResult with full breakdown.

    >>> result = calculate_clv(-110, -120)
    >>> result.beat_close
    True
    >>> result.clv_pct > 0
    True
    """
    bet_implied = american_to_implied(bet_odds)
    closing_implied = american_to_implied(closing_odds)

    # CLV: how much better (or worse) your price was vs close
    if closing_implied == 0:
        clv_pct = 0.0
    else:
        clv_pct = (closing_implied - bet_implied) / closing_implied * 100

    # CLV in cents: raw difference in implied probability
    clv_cents = (closing_implied - bet_implied) * 100

    return CLVResult(
        bet_odds_american=bet_odds,
        closing_odds_american=closing_odds,
        bet_implied=bet_implied,
        closing_implied=closing_implied,
        clv_pct=round(clv_pct, 4),
        clv_cents=round(clv_cents, 2),
        beat_close=clv_pct > 0,
    )


def summarize_clv(records: list[CLVResult]) -> CLVSummary:
    """Calculate aggregate CLV statistics with significance testing.

    Performs a one-sample t-test to determine whether the mean CLV
    is significantly greater than zero.

    Args:
        records: List of CLVResult objects from settled bets.

    Returns:
        CLVSummary with statistical analysis.
    """
    if not records:
        return CLVSummary(
            total_bets=0, avg_clv_pct=0, median_clv_pct=0, std_clv_pct=0,
            t_statistic=0, p_value=1.0, significant=False,
            confidence_interval=(0, 0), beat_close_rate=0, best_clv=0, worst_clv=0,
        )

    values = [r.clv_pct for r in records]
    n = len(values)

    # Descriptive stats
    mean_clv = sum(values) / n
    sorted_vals = sorted(values)
    median_clv = sorted_vals[n // 2] if n % 2 else (sorted_vals[n // 2 - 1] + sorted_vals[n // 2]) / 2

    # Standard deviation
    variance = sum((v - mean_clv) ** 2 for v in values) / max(n - 1, 1)
    std_clv = math.sqrt(variance)

    # One-sample t-test: H0: mean CLV = 0, H1: mean CLV > 0
    se = std_clv / math.sqrt(n) if n > 0 else 0
    t_stat = mean_clv / se if se > 0 else 0

    # Approximate p-value using normal distribution (valid for n >= 30)
    p_value = _normal_sf(t_stat) if n >= 30 else _t_sf(t_stat, n - 1)

    # 95% confidence interval
    z_95 = 1.96
    ci_low = mean_clv - z_95 * se
    ci_high = mean_clv + z_95 * se

    beat_rate = sum(1 for r in records if r.beat_close) / n

    return CLVSummary(
        total_bets=n,
        avg_clv_pct=round(mean_clv, 4),
        median_clv_pct=round(median_clv, 4),
        std_clv_pct=round(std_clv, 4),
        t_statistic=round(t_stat, 3),
        p_value=round(p_value, 6),
        significant=p_value < 0.05 and mean_clv > 0,
        confidence_interval=(round(ci_low, 4), round(ci_high, 4)),
        beat_close_rate=round(beat_rate, 4),
        best_clv=round(max(values), 4),
        worst_clv=round(min(values), 4),
    )


def rolling_clv(
    records: list[CLVResult],
    window: int = 100,
) -> list[dict]:
    """Calculate rolling CLV over a sliding window.

    Useful for tracking whether model quality is improving or degrading.

    Args:
        records: Chronologically ordered CLVResult list.
        window: Number of bets in the rolling window.

    Returns:
        List of dicts with rolling stats per window position.
    """
    results = []
    for i in range(window, len(records) + 1):
        window_records = records[i - window:i]
        summary = summarize_clv(window_records)
        results.append({
            "window_end": i,
            "avg_clv": summary.avg_clv_pct,
            "t_stat": summary.t_statistic,
            "significant": summary.significant,
            "beat_close_rate": summary.beat_close_rate,
        })
    return results


def _normal_sf(z: float) -> float:
    """Survival function for standard normal (1 - CDF). Approximation."""
    # Abramowitz and Stegun approximation 7.1.26
    t = 1.0 / (1.0 + 0.2316419 * abs(z))
    d = 0.3989422804014327  # 1/sqrt(2*pi)
    p = d * math.exp(-z * z / 2.0) * (
        t * (0.319381530 + t * (-0.356563782 + t * (1.781477937 +
        t * (-1.821255978 + t * 1.330274429))))
    )
    return p if z > 0 else 1.0 - p


def _t_sf(t_stat: float, df: int) -> float:
    """Approximate survival function for t-distribution. Falls back to normal for large df."""
    if df >= 30:
        return _normal_sf(t_stat)
    # Rough approximation for small samples
    adjusted = t_stat * (1 - 1 / (4 * max(df, 1)))
    return _normal_sf(adjusted)
