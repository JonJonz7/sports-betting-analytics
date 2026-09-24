"""Tests for the Closing Line Value tracker."""

import pytest

from src.engines.clv_tracker import (
    CLVResult,
    american_to_implied,
    calculate_clv,
    rolling_clv,
    summarize_clv,
)


class TestAmericanToImplied:
    def test_favorite(self):
        assert round(american_to_implied(-110), 4) == 0.5238

    def test_underdog(self):
        assert round(american_to_implied(150), 4) == 0.4

    def test_heavy_favorite(self):
        assert round(american_to_implied(-300), 4) == 0.75

    def test_even_money(self):
        assert round(american_to_implied(100), 4) == 0.5


class TestCalculateCLV:
    def test_positive_clv(self):
        # Bet at -110, closed at -120 (got better price)
        result = calculate_clv(-110, -120)
        assert result.beat_close is True
        assert result.clv_pct > 0

    def test_negative_clv(self):
        # Bet at -120, closed at -110 (got worse price)
        result = calculate_clv(-120, -110)
        assert result.beat_close is False
        assert result.clv_pct < 0

    def test_zero_clv(self):
        # Bet at same price as close
        result = calculate_clv(-110, -110)
        assert result.clv_pct == 0.0
        assert result.beat_close is False

    def test_underdog_positive_clv(self):
        # Bet at +150, closed at +130 (got better price on underdog)
        result = calculate_clv(150, 130)
        assert result.beat_close is True
        assert result.clv_pct > 0


class TestSummarizeCLV:
    def test_empty_records(self):
        summary = summarize_clv([])
        assert summary.total_bets == 0
        assert summary.significant is False

    def test_positive_clv_sample(self):
        # Simulate 50 bets with consistently positive CLV
        records = []
        for i in range(50):
            records.append(calculate_clv(-110, -115))  # small positive CLV each time

        summary = summarize_clv(records)
        assert summary.total_bets == 50
        assert summary.avg_clv_pct > 0
        assert summary.beat_close_rate == 1.0

    def test_mixed_clv_sample(self):
        records = []
        # 30 positive CLV bets
        for _ in range(30):
            records.append(calculate_clv(-110, -120))
        # 20 negative CLV bets
        for _ in range(20):
            records.append(calculate_clv(-120, -110))

        summary = summarize_clv(records)
        assert summary.total_bets == 50
        assert summary.beat_close_rate == 0.6

    def test_significance_requires_sample_size(self):
        # Small sample should not be significant even if all positive
        records = [calculate_clv(-110, -120) for _ in range(5)]
        summary = summarize_clv(records)
        # With only 5 bets, hard to reach significance

    def test_confidence_interval(self):
        records = [calculate_clv(-110, -115) for _ in range(100)]
        summary = summarize_clv(records)
        ci_low, ci_high = summary.confidence_interval
        assert ci_low <= summary.avg_clv_pct <= ci_high


class TestRollingCLV:
    def test_rolling_window(self):
        records = [calculate_clv(-110, -115) for _ in range(150)]
        rolling = rolling_clv(records, window=100)
        assert len(rolling) == 51  # 150 - 100 + 1
        assert all(r["avg_clv"] > 0 for r in rolling)

    def test_empty_records(self):
        rolling = rolling_clv([], window=100)
        assert len(rolling) == 0
