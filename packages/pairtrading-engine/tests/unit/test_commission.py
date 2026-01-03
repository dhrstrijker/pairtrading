"""Tests for commission models."""


from ptengine.commission.models import (
    IBKRTieredCommission,
    PercentageCommission,
    PerShareCommission,
    ZeroCommission,
)


class TestZeroCommission:
    """Tests for ZeroCommission model."""

    def test_always_zero(self):
        model = ZeroCommission()
        assert model.calculate(100, 150.0) == 0.0
        assert model.calculate(1000, 10.0) == 0.0


class TestPerShareCommission:
    """Tests for PerShareCommission model."""

    def test_basic_calculation(self):
        model = PerShareCommission(rate=0.01, minimum=1.0)
        # 100 shares * $0.01 = $1.00
        assert model.calculate(100, 150.0) == 1.0

    def test_minimum_applies(self):
        model = PerShareCommission(rate=0.01, minimum=5.0)
        # 100 shares * $0.01 = $1.00, but minimum is $5
        assert model.calculate(100, 150.0) == 5.0

    def test_maximum_applies(self):
        model = PerShareCommission(rate=0.01, minimum=1.0, maximum=10.0)
        # 10000 shares * $0.01 = $100, but max is $10
        assert model.calculate(10000, 150.0) == 10.0

    def test_handles_negative_shares(self):
        model = PerShareCommission(rate=0.01, minimum=1.0)
        assert model.calculate(-100, 150.0) == 1.0


class TestPercentageCommission:
    """Tests for PercentageCommission model."""

    def test_basic_calculation(self):
        model = PercentageCommission(rate=0.001, minimum=1.0)
        # $15,000 notional * 0.1% = $15
        assert model.calculate(100, 150.0) == 15.0

    def test_minimum_applies(self):
        model = PercentageCommission(rate=0.001, minimum=5.0)
        # $100 notional * 0.1% = $0.10, but minimum is $5
        assert model.calculate(1, 100.0) == 5.0


class TestIBKRTieredCommission:
    """Tests for IBKRTieredCommission model."""

    def test_basic_calculation(self):
        model = IBKRTieredCommission()
        commission = model.calculate(100, 150.0)
        # Should be reasonable, between minimum and max
        assert commission >= model.minimum

    def test_small_trade_capped_by_max_pct(self):
        model = IBKRTieredCommission()
        # Very small trade: minimum would be $0.35 but max 1% of $10 = $0.10
        # IBKR caps commission at max_pct even below minimum
        commission = model.calculate(1, 10.0)
        max_expected = 1 * 10.0 * model.maximum_pct
        assert commission == max_expected

    def test_maximum_applies(self):
        model = IBKRTieredCommission()
        # Very large trade should hit percentage max
        commission = model.calculate(100000, 100.0)
        max_expected = 100000 * 100.0 * model.maximum_pct
        assert commission <= max_expected
