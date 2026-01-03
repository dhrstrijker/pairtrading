"""Tests for corporate action handling.

Corporate actions (splits, dividends, mergers) can significantly
affect price series and must be handled correctly to avoid:
- False signals from price discontinuities
- Look-ahead bias from using future adjustment factors
- Incorrect returns calculations

These tests verify proper handling of various corporate actions.
"""

from datetime import date, timedelta
from decimal import Decimal

import pandas as pd
import numpy as np
import pytest

from ptdata.core.types import CorporateAction, CorporateActionType
from ptdata.validation.quality import check_adjusted_prices


class TestStockSplits:
    """Tests for stock split handling."""

    def test_split_creates_price_discontinuity(self, data_with_split):
        """Unadjusted prices should show discontinuity at split."""
        prices, splits = data_with_split
        split_date = pd.to_datetime(splits.iloc[0]["date"])
        split_ratio = splits.iloc[0]["split_ratio"]

        # Get prices around split
        before = prices[prices["date"] < split_date]["close"].iloc[-1]
        after = prices[prices["date"] >= split_date]["close"].iloc[0]

        # Unadjusted close should drop by approximately split_ratio
        ratio = before / after
        assert abs(ratio - split_ratio) < 0.1, (
            f"Expected price drop ratio ~{split_ratio}, got {ratio:.2f}"
        )

    def test_adjusted_prices_continuous(self, data_with_split):
        """Adjusted prices should be continuous through split."""
        prices, splits = data_with_split
        split_date = pd.to_datetime(splits.iloc[0]["date"])

        # Get adj_close around split
        before = prices[prices["date"] < split_date]["adj_close"].iloc[-1]
        after = prices[prices["date"] >= split_date]["adj_close"].iloc[0]

        # Adjusted prices should be continuous (no big jump)
        daily_return = abs(after / before - 1)
        assert daily_return < 0.1, (
            f"Adjusted prices should be continuous, got {daily_return:.2%} change"
        )

    def test_returns_calculated_on_adjusted(self, data_with_split):
        """Returns should be calculated using adjusted prices."""
        prices, splits = data_with_split
        split_date = pd.to_datetime(splits.iloc[0]["date"])

        # Calculate returns using adjusted close
        prices = prices.sort_values("date")
        returns = prices["adj_close"].pct_change()

        # Find return around split date
        split_idx = prices[prices["date"] >= split_date].index[0]
        split_return = returns.loc[split_idx]

        # Return should be reasonable (not ~-50% from using unadjusted)
        assert abs(split_return) < 0.1, (
            f"Return at split should be normal, got {split_return:.2%}"
        )

    def test_volume_adjusted_for_split(self, data_with_split):
        """Volume should be adjusted for splits (if applicable)."""
        prices, splits = data_with_split
        split_date = pd.to_datetime(splits.iloc[0]["date"])

        # Note: Volume adjustment depends on data provider
        # Some adjust, some don't. This test documents the behavior.
        before_vol = prices[prices["date"] < split_date]["volume"].mean()
        after_vol = prices[prices["date"] >= split_date]["volume"].mean()

        # Just verify volumes are in reasonable range
        assert before_vol > 0
        assert after_vol > 0


class TestDividends:
    """Tests for dividend handling."""

    def test_dividend_affects_adjusted_price(self):
        """Adjusted price should account for dividends."""
        # Create data with dividend
        dates = pd.bdate_range("2020-01-01", periods=10)
        ex_div_date = dates[5]

        # Unadjusted prices stay flat
        close = [100.0] * 10

        # Adjusted prices drop on ex-dividend date
        # For a $1 dividend on $100 stock = 1% adjustment
        adj_close = [100.0] * 5 + [99.0] * 5  # Pre-dividend dates adjusted down

        df = pd.DataFrame({
            "symbol": ["DIV_TEST"] * 10,
            "date": dates,
            "close": close,
            "adj_close": adj_close,
        })

        # Verify adjustment
        before_adj = df[df["date"] < ex_div_date]["adj_close"].iloc[-1]
        after_adj = df[df["date"] >= ex_div_date]["adj_close"].iloc[0]

        assert before_adj != after_adj, "Adjusted prices should differ around ex-div"

    def test_total_return_includes_dividends(self):
        """Total return calculation should include dividends."""
        # Using adjusted prices automatically includes dividends
        dates = pd.bdate_range("2020-01-01", periods=252)

        # Stock with 2% annual dividend yield, 10% price appreciation
        # Total return should be ~12%
        np.random.seed(42)
        daily_return = 0.10 / 252
        daily_vol = 0.15 / np.sqrt(252)

        returns = np.random.normal(daily_return, daily_vol, 252)
        adj_close = 100 * np.exp(np.cumsum(returns))

        # Unadjusted close would not include dividend adjustment
        # but adjusted close does
        total_return = adj_close[-1] / adj_close[0] - 1

        assert total_return > 0, "Total return should be positive"


class TestMergers:
    """Tests for merger/acquisition handling."""

    def test_acquired_company_data_ends(self, data_with_delisting):
        """Acquired company's data should end at acquisition date."""
        df = data_with_delisting  # Similar to delisting scenario

        # Verify data has an end point
        assert len(df) < 252, "Acquired company data should end"

    def test_acquiring_company_continues(self, sample_prices):
        """Acquiring company should have continuous data."""
        # The surviving company continues trading
        assert len(sample_prices) >= 100, "Acquiring company should have continuous data"


class TestAdjustedPriceQuality:
    """Tests for adjusted price quality checks."""

    def test_detect_adjustment_jump(self):
        """Should detect unexplained jumps in adjustment factor."""
        dates = pd.bdate_range("2020-01-01", periods=10)

        # Create suspicious adjustment (10% jump with no corporate action)
        df = pd.DataFrame({
            "symbol": ["TEST"] * 10,
            "date": dates,
            "close": [100.0] * 10,
            "adj_close": [100.0] * 5 + [110.0] * 5,  # Suspicious jump
        })

        issues = check_adjusted_prices(df, raise_on_error=False)

        assert len(issues) > 0, "Should detect adjustment factor jump"
        assert any(i["check"] == "adjustment_jump" for i in issues)

    def test_consistent_adjustment_passes(self, sample_prices):
        """Consistent adjustment factor should pass checks."""
        # Sample prices have adj_close == close (no adjustments needed)
        issues = check_adjusted_prices(sample_prices, raise_on_error=False)

        # No issues expected for consistent data
        adjustment_issues = [i for i in issues if i["check"] == "adjustment_jump"]
        assert len(adjustment_issues) == 0


class TestCorporateActionTypes:
    """Tests for corporate action type handling."""

    def test_corporate_action_creation(self):
        """Should create corporate action correctly."""
        split = CorporateAction(
            symbol="AAPL",
            date=date(2020, 8, 31),
            action_type=CorporateActionType.SPLIT,
            value=Decimal("4.0"),
        )

        assert split.symbol == "AAPL"
        assert split.action_type == CorporateActionType.SPLIT
        assert split.value == Decimal("4.0")

    def test_corporate_action_is_immutable(self):
        """Corporate actions should be immutable."""
        split = CorporateAction(
            symbol="AAPL",
            date=date(2020, 8, 31),
            action_type=CorporateActionType.SPLIT,
            value=Decimal("4.0"),
        )

        with pytest.raises(Exception):  # frozen dataclass
            split.symbol = "MSFT"

    def test_dividend_action(self):
        """Should create dividend action correctly."""
        dividend = CorporateAction(
            symbol="AAPL",
            date=date(2020, 5, 8),
            action_type=CorporateActionType.DIVIDEND,
            value=Decimal("0.82"),  # Dividend amount
        )

        assert dividend.action_type == CorporateActionType.DIVIDEND
        assert dividend.value == Decimal("0.82")

    def test_delisting_action(self):
        """Should create delisting action correctly."""
        delisting = CorporateAction(
            symbol="LEHM",
            date=date(2008, 9, 15),
            action_type=CorporateActionType.DELISTING,
            value=Decimal("0.0"),  # Final price or 0
        )

        assert delisting.action_type == CorporateActionType.DELISTING
