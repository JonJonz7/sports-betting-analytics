"""Tests for the +EV Discrepancy Engine."""

from src.engines.ev_engine import (
    american_to_decimal,
    calculate_edge_confidence,
    calculate_ev,
    decimal_to_implied,
    remove_vig_additive,
    remove_vig_multiplicative,
    remove_vig_shin,
    scan_for_ev,
)


class TestOddsConversion:
    def test_negative_american_to_decimal(self):
        assert round(american_to_decimal(-110), 4) == 1.9091

    def test_positive_american_to_decimal(self):
        assert american_to_decimal(150) == 2.5

    def test_heavy_favorite(self):
        assert round(american_to_decimal(-300), 4) == 1.3333

    def test_heavy_underdog(self):
        assert american_to_decimal(500) == 6.0

    def test_even_money(self):
        assert american_to_decimal(100) == 2.0

    def test_implied_from_decimal(self):
        assert round(decimal_to_implied(2.0), 2) == 0.50
        assert round(decimal_to_implied(1.5), 4) == 0.6667


class TestVigRemoval:
    def test_additive_standard_vig(self):
        # -110/-110 market (4.5% vig)
        implied = [0.5238, 0.5238]
        fair = remove_vig_additive(implied)
        assert abs(sum(fair) - 1.0) < 0.001
        assert abs(fair[0] - 0.5) < 0.01

    def test_multiplicative_skewed_market(self):
        # -333/+250 market
        implied = [0.7692, 0.2857]
        fair = remove_vig_multiplicative(implied)
        assert abs(sum(fair) - 1.0) < 0.01

    def test_shin_converges(self):
        implied = [0.5238, 0.5238]
        fair = remove_vig_shin(implied)
        assert abs(sum(fair) - 1.0) < 0.01


class TestEVCalculation:
    def test_positive_ev(self):
        # 55% probability at even money (+100 / 2.0 decimal)
        ev = calculate_ev(0.55, 2.0)
        assert round(ev, 2) == 0.10

    def test_zero_ev(self):
        ev = calculate_ev(0.50, 2.0)
        assert round(ev, 2) == 0.00

    def test_negative_ev(self):
        ev = calculate_ev(0.45, 2.0)
        assert round(ev, 2) == -0.10

    def test_large_underdog_ev(self):
        # 20% probability at +400 (5.0 decimal) = breakeven
        ev = calculate_ev(0.20, 5.0)
        assert round(ev, 2) == 0.00
        # 25% at +400 = positive EV
        ev2 = calculate_ev(0.25, 5.0)
        assert ev2 > 0

    def test_slight_edge_on_favorite(self):
        # 60% prob at -150 (1.667 decimal)
        ev = calculate_ev(0.60, 1.6667)
        assert ev > 0  # slight +EV


class TestEdgeConfidence:
    def test_high_ev_high_confidence(self):
        c = calculate_edge_confidence(0.08)
        assert c > 0.3

    def test_stale_line_reduces_confidence(self):
        base = calculate_edge_confidence(0.05, line_age_minutes=0)
        stale = calculate_edge_confidence(0.05, line_age_minutes=20)
        assert stale < base

    def test_clv_history_boosts_confidence(self):
        no_history = calculate_edge_confidence(0.05)
        with_history = calculate_edge_confidence(0.05, model_clv_history=0.02)
        assert with_history > no_history

    def test_injury_uncertainty_reduces_confidence(self):
        certain = calculate_edge_confidence(0.05, injury_uncertainty=0.0)
        uncertain = calculate_edge_confidence(0.05, injury_uncertainty=0.5)
        assert uncertain < certain


class TestScanForEV:
    def test_finds_positive_ev(self):
        model = {"home_ml": 0.58, "away_ml": 0.42}
        odds = {"TestBook": {"home_ml": -120, "away_ml": +140}}
        opps = scan_for_ev(model, odds, min_ev=0.01)
        # At least one opportunity should exist
        assert len(opps) >= 1
        assert all(o.ev_pct >= 0.01 for o in opps)

    def test_no_edge_no_opportunities(self):
        model = {"home_ml": 0.50, "away_ml": 0.50}
        odds = {"TestBook": {"home_ml": -110, "away_ml": -110}}
        opps = scan_for_ev(model, odds, min_ev=0.02)
        assert len(opps) == 0

    def test_sorted_by_ev_desc(self):
        model = {"home_ml": 0.60, "away_ml": 0.55}
        odds = {"BookA": {"home_ml": -110, "away_ml": -110}}
        opps = scan_for_ev(model, odds, min_ev=0.01)
        if len(opps) >= 2:
            assert opps[0].ev_pct >= opps[1].ev_pct


def test_scan_reports_vig_free_market_probability():
    from src.engines.ev_engine import VigRemovalMethod

    model = {"home_ml": 0.60, "away_ml": 0.40}
    odds = {"Book": {"home_ml": -110, "away_ml": -110}}
    [opp] = scan_for_ev(model, odds, vig_method=VigRemovalMethod.ADDITIVE, min_ev=0.01)
    assert opp.selection == "home_ml"
    assert abs(opp.market_implied - 0.5) < 1e-9  # 52.4% with vig -> 50% fair


def test_vig_method_changes_fair_probability_on_lopsided_markets():
    from src.engines.ev_engine import VigRemovalMethod

    model = {"fav_ml": 0.85, "dog_ml": 0.15}
    odds = {"Book": {"fav_ml": -400, "dog_ml": 300}}
    add = scan_for_ev(model, odds, VigRemovalMethod.ADDITIVE, min_ev=-1)
    shin = scan_for_ev(model, odds, VigRemovalMethod.SHIN, min_ev=-1)
    fav = lambda opps: next(o.market_implied for o in opps if o.selection == "fav_ml")  # noqa: E731
    assert fav(add) != fav(shin)
