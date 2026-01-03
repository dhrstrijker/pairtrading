"""Tests for missing data handling.

Market data often has gaps due to:
- Trading halts
- Data provider issues
- Different market calendars
- Newly listed securities

These tests verify that missing data is handled correctly
and that the system fails gracefully when gaps are too large.
"""


import numpy as np
import pandas as pd
import pytest

from ptdata.core.exceptions import DataQualityError
from ptdata.validation.gaps import (
    MissingDataStrategy,
    find_gaps,
    handle_missing_data,
)


class TestMissingData:
    """Tests for missing data handling strategies."""

    def test_forward_fill_strategy(self, data_with_gaps):
        """Forward fill should propagate last known price."""
        df = data_with_gaps.copy()

        # Introduce NaN values
        df.loc[10:12, "close"] = np.nan
        df.loc[10:12, "adj_close"] = np.nan

        result = handle_missing_data(
            df,
            strategy=MissingDataStrategy.FORWARD_FILL,
            max_consecutive=10,
        )

        # No NaN values should remain
        assert not result["close"].isna().any()

        # Values should be forward filled from row 9
        expected_value = df.loc[9, "close"]
        assert result.loc[10, "close"] == expected_value
        assert result.loc[11, "close"] == expected_value
        assert result.loc[12, "close"] == expected_value

    def test_backward_fill_strategy(self, data_with_gaps):
        """Backward fill should use next known value."""
        df = data_with_gaps.copy()

        # Introduce NaN values
        df.loc[10:12, "close"] = np.nan
        df.loc[10:12, "adj_close"] = np.nan

        result = handle_missing_data(
            df,
            strategy=MissingDataStrategy.BACKWARD_FILL,
            max_consecutive=10,
        )

        # No NaN values should remain
        assert not result["close"].isna().any()

        # Values should be backward filled from row 13
        expected_value = df.loc[13, "close"]
        assert result.loc[10, "close"] == expected_value
        assert result.loc[11, "close"] == expected_value
        assert result.loc[12, "close"] == expected_value

    def test_interpolate_strategy(self, data_with_gaps):
        """Interpolation should create smooth transition."""
        df = data_with_gaps.copy()

        # Set up known values for interpolation
        df.loc[9, "close"] = 100.0
        df.loc[10:12, "close"] = np.nan
        df.loc[13, "close"] = 106.0

        result = handle_missing_data(
            df,
            strategy=MissingDataStrategy.INTERPOLATE,
            columns=["close"],
        )

        # Values should be interpolated
        assert result.loc[10, "close"] == pytest.approx(101.5, rel=0.1)
        assert result.loc[11, "close"] == pytest.approx(103.0, rel=0.1)
        assert result.loc[12, "close"] == pytest.approx(104.5, rel=0.1)

    def test_drop_strategy(self, data_with_gaps):
        """Drop strategy should remove rows with missing data."""
        df = data_with_gaps.copy()
        original_len = len(df)

        # Introduce NaN values
        df.loc[10:12, "close"] = np.nan

        result = handle_missing_data(df, strategy=MissingDataStrategy.DROP)

        assert len(result) == original_len - 3
        assert not result["close"].isna().any()

    def test_raise_strategy(self, data_with_gaps):
        """Raise strategy should error on missing data."""
        df = data_with_gaps.copy()
        df.loc[10, "close"] = np.nan

        with pytest.raises(DataQualityError) as exc_info:
            handle_missing_data(df, strategy=MissingDataStrategy.RAISE)

        assert "missing" in str(exc_info.value).lower()

    def test_max_consecutive_limit(self, data_with_long_gap):
        """Should raise when gap exceeds max_consecutive."""
        df = data_with_long_gap.copy()

        # The fixture has a 10-day gap
        df.loc[5:15, "close"] = np.nan

        with pytest.raises(DataQualityError) as exc_info:
            handle_missing_data(
                df,
                strategy=MissingDataStrategy.FORWARD_FILL,
                max_consecutive=5,
            )

        assert "consecutive" in str(exc_info.value).lower()


class TestFindGaps:
    """Tests for gap detection."""

    def test_find_gaps_accurate(self, data_with_gaps):
        """find_gaps should correctly identify all gaps."""
        # Create data with known gaps
        dates = pd.bdate_range("2020-01-01", periods=30)
        # Remove some dates to create gaps
        dates = dates.delete([10, 11, 12, 13, 14])  # 5-day gap (>3 weekends)

        df = pd.DataFrame({
            "symbol": ["TEST"] * len(dates),
            "date": dates,
            "close": [100.0] * len(dates),
        })

        gaps = find_gaps(df)

        # Should find the gap we created
        assert len(gaps) >= 1

        # Gap should be around the right location
        first_gap = gaps.iloc[0]
        assert first_gap["gap_days"] >= 5

    def test_find_gaps_per_symbol(self, sample_multi_symbol_prices):
        """Should find gaps separately for each symbol."""
        df = sample_multi_symbol_prices.copy()

        # Create gap only for AAPL
        aapl_dates = df[df["symbol"] == "AAPL"]["date"]
        gap_start_idx = len(aapl_dates) // 2
        end_idx = gap_start_idx + 10
        gap_indices = df[(df["symbol"] == "AAPL")].index[gap_start_idx:end_idx]
        df = df.drop(gap_indices)

        gaps = find_gaps(df, symbol_column="symbol")

        # Should find gap for AAPL
        aapl_gaps = gaps[gaps["symbol"] == "AAPL"]
        assert len(aapl_gaps) >= 1

    def test_no_gaps_in_continuous_data(self, sample_prices):
        """Continuous data should have no gaps detected."""
        gaps = find_gaps(sample_prices)

        assert len(gaps) == 0, (
            f"Expected no gaps in continuous data, found {len(gaps)}"
        )

    def test_empty_dataframe(self):
        """Empty DataFrame should return empty gaps."""
        df = pd.DataFrame(columns=["symbol", "date", "close"])

        gaps = find_gaps(df)

        assert len(gaps) == 0


class TestGapHandlingEdgeCases:
    """Edge cases in gap handling."""

    def test_all_nan_column(self):
        """Should handle column that is entirely NaN."""
        df = pd.DataFrame({
            "symbol": ["TEST"] * 5,
            "date": pd.date_range("2020-01-01", periods=5),
            "close": [np.nan] * 5,
            "volume": [1000] * 5,
        })

        with pytest.raises(DataQualityError):
            handle_missing_data(
                df,
                strategy=MissingDataStrategy.FORWARD_FILL,
                max_consecutive=3,
            )

    def test_nan_at_start(self):
        """Forward fill cannot fill NaN at start of series."""
        df = pd.DataFrame({
            "symbol": ["TEST"] * 5,
            "date": pd.date_range("2020-01-01", periods=5),
            "close": [np.nan, np.nan, 102.0, 103.0, 104.0],
            "volume": [1000] * 5,
        })

        result = handle_missing_data(
            df,
            strategy=MissingDataStrategy.FORWARD_FILL,
            max_consecutive=5,
        )

        # First values remain NaN (nothing to forward fill from)
        assert pd.isna(result.loc[0, "close"])
        assert pd.isna(result.loc[1, "close"])

    def test_nan_at_end(self):
        """Backward fill cannot fill NaN at end of series."""
        df = pd.DataFrame({
            "symbol": ["TEST"] * 5,
            "date": pd.date_range("2020-01-01", periods=5),
            "close": [100.0, 101.0, 102.0, np.nan, np.nan],
            "volume": [1000] * 5,
        })

        result = handle_missing_data(
            df,
            strategy=MissingDataStrategy.BACKWARD_FILL,
            max_consecutive=5,
        )

        # Last values remain NaN (nothing to backward fill from)
        assert pd.isna(result.loc[3, "close"])
        assert pd.isna(result.loc[4, "close"])

    def test_sparse_nan_values(self):
        """Sparse NaN values should each be filled independently."""
        close_vals = [
            100.0, np.nan, 102.0, 103.0, np.nan, 105.0, 106.0, np.nan, 108.0, 109.0
        ]
        df = pd.DataFrame({
            "symbol": ["TEST"] * 10,
            "date": pd.date_range("2020-01-01", periods=10),
            "close": close_vals,
            "volume": [1000] * 10,
        })

        result = handle_missing_data(
            df,
            strategy=MissingDataStrategy.FORWARD_FILL,
            max_consecutive=3,
        )

        assert result.loc[1, "close"] == 100.0  # Forward filled from 0
        assert result.loc[4, "close"] == 103.0  # Forward filled from 3
        assert result.loc[7, "close"] == 106.0  # Forward filled from 6

    def test_specific_columns_only(self):
        """Should only process specified columns."""
        df = pd.DataFrame({
            "symbol": ["TEST"] * 5,
            "date": pd.date_range("2020-01-01", periods=5),
            "close": [100.0, np.nan, 102.0, 103.0, 104.0],
            "volume": [1000, np.nan, 1200, 1300, 1400],
        })

        result = handle_missing_data(
            df,
            strategy=MissingDataStrategy.FORWARD_FILL,
            max_consecutive=5,
            columns=["close"],  # Only fill close
        )

        # close should be filled
        assert not result["close"].isna().any()

        # volume should still have NaN
        assert result["volume"].isna().any()
