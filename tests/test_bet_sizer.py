"""Tests for the Kelly Criterion bet sizer."""

from src.engines.bet_sizer import (
    calculate_bet_size,
    drawdown_adjusted_size,
    kelly_fraction,
    simultaneous_kelly,
)


class TestKellyFraction:
    def test_even_money_slight_edge(self):
        # 55% at +100 (2.0 decimal)
        f = kelly_fraction(0.55, 2.0)
        assert round(f, 2) == 0.10

    def test_larger_edge(self):
        # 60% at +150 (2.5 decimal)
        f = kelly_fraction(0.60, 2.5)
        assert round(f, 4) == 0.3333

    def test_no_edge_returns_zero(self):
        f = kelly_fraction(0.50, 2.0)
        assert f == 0.0

    def test_negative_edge_returns_zero(self):
        f = kelly_fraction(0.45, 2.0)
        assert f == 0.0

    def test_edge_cases(self):
        assert kelly_fraction(0.0, 2.0) == 0.0
        assert kelly_fraction(1.0, 2.0) == 0.0  # p=1 is invalid
        assert kelly_fraction(0.5, 1.0) == 0.0  # odds=1 is invalid


class TestSimultaneousKelly:
    def test_scales_down_total_allocation(self):
        bets = [(0.55, 2.0), (0.60, 2.5)]
        fracs = simultaneous_kelly(bets)
        assert sum(fracs) <= 0.25  # capped

    def test_preserves_relative_sizes(self):
        bets = [(0.55, 2.0), (0.60, 2.5)]
        fracs = simultaneous_kelly(bets)
        # Second bet has more edge, should get larger fraction
        assert fracs[1] > fracs[0]

    def test_no_edge_bets(self):
        bets = [(0.45, 2.0), (0.40, 2.0)]
        fracs = simultaneous_kelly(bets)
        assert all(f == 0 for f in fracs)


class TestCalculateBetSize:
    def test_basic_sizing(self):
        size = calculate_bet_size(0.55, 2.0, 10000, kelly_multiplier=0.25)
        assert size.kelly_full == 0.1
        assert size.kelly_quarter == 0.025
        assert size.recommended_amount == 250.0

    def test_max_bet_cap(self):
        # Large edge but capped at 5% of bankroll
        size = calculate_bet_size(0.80, 2.0, 10000, kelly_multiplier=1.0, max_bet_pct=0.05)
        assert size.recommended_amount <= 500.0  # 5% of 10000

    def test_minimum_bet_enforcement(self):
        # Tiny bankroll, edge too small for minimum bet
        size = calculate_bet_size(0.51, 2.0, 100, kelly_multiplier=0.25, min_bet=10.0)
        # 0.01 Kelly * 0.25 * 100 = $0.25, below $10 minimum
        assert size.recommended_amount == 0.0

    def test_no_edge_no_bet(self):
        size = calculate_bet_size(0.50, 2.0, 10000)
        assert size.recommended_amount == 0.0
        assert size.kelly_full == 0.0


class TestDrawdownAdjustment:
    def test_no_drawdown_no_change(self):
        result = drawdown_adjusted_size(0.05, 10000, 10000)
        assert result == 0.05

    def test_drawdown_reduces_size(self):
        result = drawdown_adjusted_size(0.05, 8000, 10000)
        assert result < 0.05

    def test_deep_drawdown_severe_reduction(self):
        result = drawdown_adjusted_size(0.05, 5000, 10000)
        assert result < 0.02  # more than halved

    def test_above_peak_no_change(self):
        result = drawdown_adjusted_size(0.05, 12000, 10000)
        assert result == 0.05
