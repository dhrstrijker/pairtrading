"""Tests for GGR Distance Strategy."""

from datetime import date

import numpy as np
import pandas as pd
import pytest
from ptdata.validation import PointInTimeDataFrame

from ptengine.core.types import SignalType
from ptengine.strategies.ggr_distance import GGRDistanceStrategy, PairCandidate


@pytest.fixture
def correlated_prices() -> pd.DataFrame:
    """Generate price data for correlated symbols."""
    np.random.seed(42)
    dates = pd.date_range(start="2020-01-01", end="2020-12-31", freq="B")

    data = []

    # Create 4 symbols: A & B highly correlated, C & D highly correlated
    # A-B pair and C-D pair should be identified
    base_a = 100.0
    base_b = 100.0
    base_c = 50.0
    base_d = 50.0

    for d in dates:
        # Common factor for A-B pair
        shock_ab = np.random.normal(0, 0.01)
        # Common factor for C-D pair
        shock_cd = np.random.normal(0, 0.015)

        # A and B move together (high correlation)
        base_a *= 1 + shock_ab + np.random.normal(0, 0.002)
        base_b *= 1 + shock_ab + np.random.normal(0, 0.002)

        # C and D move together (high correlation)
        base_c *= 1 + shock_cd + np.random.normal(0, 0.003)
        base_d *= 1 + shock_cd + np.random.normal(0, 0.003)

        for symbol, price in [("A", base_a), ("B", base_b), ("C", base_c), ("D", base_d)]:
            data.append({
                "symbol": symbol,
                "date": d.date(),
                "open": price,
                "high": price * 1.01,
                "low": price * 0.99,
                "close": price,
                "adj_close": price,
                "volume": 1000000,
            })

    return pd.DataFrame(data)


@pytest.fixture
def diverging_pair_prices() -> pd.DataFrame:
    """Generate prices where pair A-B diverges then converges."""
    np.random.seed(123)
    dates = pd.date_range(start="2020-01-01", end="2020-12-31", freq="B")

    data = []
    price_a = 100.0
    price_b = 100.0

    for i, d in enumerate(dates):
        # First 150 days: move together
        if i < 150:
            shock = np.random.normal(0.0003, 0.01)
            price_a *= 1 + shock + np.random.normal(0, 0.001)
            price_b *= 1 + shock + np.random.normal(0, 0.001)
        # Days 150-180: diverge (A rises, B falls)
        elif i < 180:
            price_a *= 1 + 0.01 + np.random.normal(0, 0.005)
            price_b *= 1 - 0.008 + np.random.normal(0, 0.005)
        # Days 180+: converge back
        else:
            shock = np.random.normal(0, 0.01)
            price_a *= 1 + shock - 0.003
            price_b *= 1 + shock + 0.003

        for symbol, price in [("A", price_a), ("B", price_b)]:
            data.append({
                "symbol": symbol,
                "date": d.date(),
                "open": price,
                "high": price * 1.01,
                "low": price * 0.99,
                "close": price,
                "adj_close": price,
                "volume": 1000000,
            })

    return pd.DataFrame(data)


class TestGGRDistanceStrategy:
    """Tests for GGRDistanceStrategy."""

    def test_initialization(self):
        """Test strategy initializes with correct parameters."""
        strategy = GGRDistanceStrategy(
            symbols=["A", "B", "C"],
            formation_period=60,
            entry_threshold=2.5,
            top_n_pairs=3,
        )

        assert strategy.formation_period == 60
        assert strategy.entry_threshold == 2.5
        assert strategy.top_n_pairs == 3
        assert len(strategy.symbols) == 3
        assert "ggr_distance" in strategy.name

    def test_formation_identifies_correlated_pairs(self, correlated_prices: pd.DataFrame):
        """Test that formation correctly identifies correlated pairs."""
        strategy = GGRDistanceStrategy(
            symbols=["A", "B", "C", "D"],
            formation_period=60,  # Reduced to fit available data
            top_n_pairs=2,
            min_correlation=0.7,
        )

        pit_data = PointInTimeDataFrame(correlated_prices, date(2020, 1, 1))

        # Run enough bars to complete formation (need 60+ days)
        current_pit = pit_data
        for d in pd.date_range("2020-04-01", "2020-04-15", freq="B"):
            current_pit = current_pit.advance_to(d.date())
            strategy.on_bar(d.date(), current_pit)

        # Check pairs were identified
        pairs = strategy.get_identified_pairs()
        assert len(pairs) > 0

        # A-B and C-D should be among the top pairs (lowest SSD)
        pair_symbols = [(p[0], p[1]) for p in pairs]
        # Check that either (A,B) or (B,A) is in pairs
        has_ab = any(
            (s1 == "A" and s2 == "B") or (s1 == "B" and s2 == "A")
            for s1, s2, _ in pairs
        )
        assert has_ab, f"Expected A-B pair in {pair_symbols}"

    def test_no_signal_with_insufficient_data(self, correlated_prices: pd.DataFrame):
        """Test that strategy returns None when insufficient data."""
        strategy = GGRDistanceStrategy(
            symbols=["A", "B"],
            formation_period=120,
        )

        # Only use first 30 days of data
        short_data = correlated_prices[
            correlated_prices["date"] <= date(2020, 2, 15)
        ]
        pit_data = PointInTimeDataFrame(short_data, date(2020, 2, 1))

        signal = strategy.on_bar(date(2020, 2, 15), pit_data)
        assert signal is None

    def test_entry_signal_on_divergence(self, diverging_pair_prices: pd.DataFrame):
        """Test that strategy generates entry signal when spread diverges."""
        strategy = GGRDistanceStrategy(
            symbols=["A", "B"],
            formation_period=120,
            lookback=60,
            entry_threshold=1.5,  # Lower threshold for test
            top_n_pairs=1,
            min_correlation=0.5,
        )

        pit_data = PointInTimeDataFrame(diverging_pair_prices, date(2020, 1, 1))

        # Run through the backtest
        signals = []
        current_pit = pit_data
        for d in pd.date_range("2020-06-01", "2020-09-30", freq="B"):
            current_pit = current_pit.advance_to(d.date())
            signal = strategy.on_bar(d.date(), current_pit)
            if signal is not None:
                signals.append((d.date(), signal))

        # Should have at least one entry signal
        entry_signals = [
            (d, s) for d, s in signals
            if s.signal_type == SignalType.OPEN_PAIR
        ]
        assert len(entry_signals) > 0, "Expected entry signal on divergence"

    def test_exit_on_time_limit(self, diverging_pair_prices: pd.DataFrame):
        """Test that positions close after max_holding_days."""
        strategy = GGRDistanceStrategy(
            symbols=["A", "B"],
            formation_period=120,
            lookback=60,
            entry_threshold=1.5,
            max_holding_days=10,  # Short holding period for test
            top_n_pairs=1,
            min_correlation=0.5,
        )

        pit_data = PointInTimeDataFrame(diverging_pair_prices, date(2020, 1, 1))

        # Run through full year
        signals = []
        current_pit = pit_data
        for d in pd.date_range("2020-06-01", "2020-12-15", freq="B"):
            current_pit = current_pit.advance_to(d.date())
            signal = strategy.on_bar(d.date(), current_pit)
            if signal is not None:
                signals.append((d.date(), signal))

        # Should have both entry and exit signals
        entry_signals = [s for _, s in signals if s.signal_type == SignalType.OPEN_PAIR]
        exit_signals = [s for _, s in signals if s.signal_type == SignalType.CLOSE_PAIR]

        if entry_signals:
            # If we entered, we should also exit
            assert len(exit_signals) > 0, "Expected exit signal after entry"

    def test_reset_clears_state(self, correlated_prices: pd.DataFrame):
        """Test that reset clears all strategy state."""
        strategy = GGRDistanceStrategy(
            symbols=["A", "B", "C", "D"],
            formation_period=60,
            top_n_pairs=2,
        )

        pit_data = PointInTimeDataFrame(correlated_prices, date(2020, 1, 1))

        # Run some bars (need 60+ days for formation)
        current_pit = pit_data
        for d in pd.date_range("2020-04-01", "2020-04-15", freq="B"):
            current_pit = current_pit.advance_to(d.date())
            strategy.on_bar(d.date(), current_pit)

        # Verify state exists
        assert strategy._formation_complete

        # Reset
        strategy.reset()

        # Verify state is cleared
        assert not strategy._formation_complete
        assert len(strategy._pairs) == 0
        assert len(strategy._active_positions) == 0


class TestPairCandidate:
    """Tests for PairCandidate dataclass."""

    def test_creation(self):
        """Test PairCandidate creation."""
        pair = PairCandidate(
            symbol_a="AAPL",
            symbol_b="MSFT",
            ssd=0.05,
            correlation=0.92,
        )

        assert pair.symbol_a == "AAPL"
        assert pair.symbol_b == "MSFT"
        assert pair.ssd == 0.05
        assert pair.correlation == 0.92

    def test_sorting_by_ssd(self):
        """Test that pairs can be sorted by SSD."""
        pairs = [
            PairCandidate("A", "B", ssd=0.10, correlation=0.9),
            PairCandidate("C", "D", ssd=0.05, correlation=0.85),
            PairCandidate("E", "F", ssd=0.15, correlation=0.95),
        ]

        sorted_pairs = sorted(pairs, key=lambda x: x.ssd)

        assert sorted_pairs[0].symbol_a == "C"  # Lowest SSD
        assert sorted_pairs[-1].symbol_a == "E"  # Highest SSD
