"""Unit tests for data validation."""

from datetime import date

import numpy as np
import pandas as pd
import pytest

from ptdata.core.exceptions import DataQualityError, LookAheadBiasError
from ptdata.validation.gaps import (
    MissingDataStrategy,
    align_dates,
    find_gaps,
    handle_missing_data,
)
from ptdata.validation.lookahead import PointInTimeDataFrame
from ptdata.validation.quality import (
    check_price_sanity,
)


class TestPointInTimeDataFrame:
    """Test PointInTimeDataFrame wrapper."""

    def test_get_data_filters_future(self, sample_prices):
        """Should only return data up to reference date."""
        ref_date = date(2020, 6, 15)
        pit = PointInTimeDataFrame(sample_prices, ref_date)

        data = pit.get_data()

        # Convert to date for comparison
        max_date = pd.to_datetime(data["date"]).max().date()
        assert max_date <= ref_date

    def test_advance_to_forward(self, sample_prices):
        """Should allow moving reference date forward."""
        pit = PointInTimeDataFrame(sample_prices, date(2020, 6, 1))

        pit2 = pit.advance_to(date(2020, 6, 15))

        assert pit2.reference_date == date(2020, 6, 15)
        assert len(pit2) >= len(pit)

    def test_advance_to_backward_raises(self, sample_prices):
        """Should raise LookAheadBiasError when moving backward."""
        pit = PointInTimeDataFrame(sample_prices, date(2020, 6, 15))

        with pytest.raises(LookAheadBiasError):
            pit.advance_to(date(2020, 6, 1))

    def test_slice_within_range(self, sample_prices):
        """Should return data within specified range."""
        pit = PointInTimeDataFrame(sample_prices, date(2020, 6, 30))

        sliced = pit.slice(date(2020, 3, 1), date(2020, 3, 31))

        dates = pd.to_datetime(sliced["date"]).dt.date
        assert dates.min() >= date(2020, 3, 1)
        assert dates.max() <= date(2020, 3, 31)

    def test_slice_beyond_reference_raises(self, sample_prices):
        """Should raise when slicing beyond reference date."""
        pit = PointInTimeDataFrame(sample_prices, date(2020, 6, 15))

        with pytest.raises(LookAheadBiasError):
            pit.slice(date(2020, 3, 1), date(2020, 7, 31))

    def test_len_reflects_visible_rows(self, sample_prices):
        """len() should return count of visible rows only."""
        pit1 = PointInTimeDataFrame(sample_prices, date(2020, 3, 1))
        pit2 = PointInTimeDataFrame(sample_prices, date(2020, 6, 1))

        assert len(pit2) > len(pit1)

    def test_get_latest(self, sample_multi_symbol_prices):
        """Should return most recent data point."""
        pit = PointInTimeDataFrame(sample_multi_symbol_prices, date(2020, 6, 15))

        latest = pit.get_latest("AAPL")

        assert latest is not None
        assert latest["symbol"] == "AAPL"
        assert pd.to_datetime(latest["date"]).date() <= date(2020, 6, 15)

    def test_for_symbol(self, sample_multi_symbol_prices):
        """Should filter by symbol."""
        pit = PointInTimeDataFrame(sample_multi_symbol_prices, date(2020, 6, 15))

        aapl_data = pit.for_symbol("AAPL")

        assert (aapl_data["symbol"] == "AAPL").all()

    def test_symbols_property(self, sample_multi_symbol_prices):
        """Should return list of symbols."""
        pit = PointInTimeDataFrame(sample_multi_symbol_prices, date(2020, 6, 15))

        symbols = pit.symbols

        assert sorted(symbols) == ["AAPL", "GOOGL", "MSFT"]


class TestPriceSanity:
    """Test price sanity checks."""

    def test_negative_price_detected(self):
        """Should detect negative prices."""
        df = pd.DataFrame({
            "symbol": ["AAPL"],
            "date": [date(2020, 1, 1)],
            "open": [100.0],
            "high": [101.0],
            "low": [-5.0],  # Invalid
            "close": [100.5],
            "adj_close": [100.5],
            "volume": [1000000],
        })

        with pytest.raises(DataQualityError) as exc_info:
            check_price_sanity(df, raise_on_error=True)

        assert "negative" in str(exc_info.value).lower()

    def test_high_low_inversion_detected(self):
        """Should detect high < low."""
        df = pd.DataFrame({
            "symbol": ["AAPL"],
            "date": [date(2020, 1, 1)],
            "open": [100.0],
            "high": [95.0],  # Invalid - less than low
            "low": [99.0],
            "close": [97.0],
            "adj_close": [97.0],
            "volume": [1000000],
        })

        with pytest.raises(DataQualityError):
            check_price_sanity(df, raise_on_error=True)

    def test_close_outside_range_detected(self):
        """Should detect close outside high-low range."""
        df = pd.DataFrame({
            "symbol": ["AAPL"],
            "date": [date(2020, 1, 1)],
            "open": [100.0],
            "high": [101.0],
            "low": [99.0],
            "close": [105.0],  # Invalid - above high
            "adj_close": [105.0],
            "volume": [1000000],
        })

        with pytest.raises(DataQualityError):
            check_price_sanity(df, raise_on_error=True)

    def test_extreme_move_detected(self):
        """Should detect extreme single-day moves."""
        df = pd.DataFrame({
            "symbol": ["AAPL"] * 2,
            "date": [date(2020, 1, 1), date(2020, 1, 2)],
            "open": [100.0, 200.0],
            "high": [101.0, 201.0],
            "low": [99.0, 199.0],
            "close": [100.0, 200.0],  # 100% move
            "adj_close": [100.0, 200.0],
            "volume": [1000000, 1000000],
        })

        with pytest.raises(DataQualityError) as exc_info:
            check_price_sanity(df, raise_on_error=True, extreme_move_threshold=0.5)

        assert "extreme" in str(exc_info.value).lower()

    def test_valid_data_passes(self, sample_prices):
        """Valid data should pass all checks."""
        issues = check_price_sanity(sample_prices, raise_on_error=False)

        # May have some extreme moves in random data, but not structural issues
        structural_issues = [i for i in issues if i["check"] != "extreme_move"]
        assert len(structural_issues) == 0

    def test_no_raise_returns_issues(self):
        """Should return issues list when not raising."""
        df = pd.DataFrame({
            "symbol": ["AAPL"],
            "date": [date(2020, 1, 1)],
            "open": [100.0],
            "high": [101.0],
            "low": [-5.0],
            "close": [100.5],
            "adj_close": [100.5],
            "volume": [1000000],
        })

        issues = check_price_sanity(df, raise_on_error=False)

        assert len(issues) > 0
        assert any(i["check"] == "negative_price" for i in issues)


class TestGaps:
    """Test gap detection and handling."""

    def test_find_gaps_detects_long_gap(self):
        """Should detect gaps longer than 5 days."""
        dates = pd.date_range("2020-01-01", periods=10, freq="B")
        # Remove days to create a gap
        dates = dates.delete([5, 6, 7, 8])  # Creates >5 day gap

        df = pd.DataFrame({
            "symbol": ["AAPL"] * len(dates),
            "date": dates,
            "close": [100.0] * len(dates),
        })

        gaps = find_gaps(df)

        assert len(gaps) > 0
        assert gaps.iloc[0]["gap_days"] > 5

    def test_find_gaps_ignores_weekends(self):
        """Should not flag normal weekend gaps."""
        dates = pd.bdate_range("2020-01-01", periods=20)

        df = pd.DataFrame({
            "symbol": ["AAPL"] * len(dates),
            "date": dates,
            "close": [100.0] * len(dates),
        })

        gaps = find_gaps(df)

        assert len(gaps) == 0

    def test_handle_missing_forward_fill(self, data_with_gaps):
        """Should forward fill missing values."""
        # Create DataFrame with NaN values
        df = data_with_gaps.copy()
        df.loc[10:15, "close"] = np.nan

        result = handle_missing_data(
            df,
            strategy=MissingDataStrategy.FORWARD_FILL,
            max_consecutive=10,
        )

        assert not result["close"].isna().any()

    def test_handle_missing_drop(self, data_with_gaps):
        """Should drop rows with missing values."""
        df = data_with_gaps.copy()
        original_len = len(df)
        df.loc[10:15, "close"] = np.nan

        result = handle_missing_data(df, strategy=MissingDataStrategy.DROP)

        assert len(result) < original_len
        assert not result["close"].isna().any()

    def test_handle_missing_raise(self):
        """Should raise when missing data exists."""
        df = pd.DataFrame({
            "symbol": ["AAPL"] * 5,
            "date": pd.date_range("2020-01-01", periods=5),
            "close": [100.0, np.nan, 102.0, 103.0, 104.0],
        })

        with pytest.raises(DataQualityError):
            handle_missing_data(df, strategy=MissingDataStrategy.RAISE)

    def test_max_consecutive_exceeded(self):
        """Should raise when consecutive missing exceeds threshold."""
        close_vals = [
            100.0, np.nan, np.nan, np.nan, np.nan, np.nan, 106.0, 107.0, 108.0, 109.0
        ]
        df = pd.DataFrame({
            "symbol": ["AAPL"] * 10,
            "date": pd.date_range("2020-01-01", periods=10),
            "close": close_vals,
        })

        with pytest.raises(DataQualityError) as exc_info:
            handle_missing_data(
                df,
                strategy=MissingDataStrategy.FORWARD_FILL,
                max_consecutive=3,
            )

        assert "consecutive" in str(exc_info.value).lower()


class TestAlignDates:
    """Test date alignment functionality."""

    def test_inner_join(self, different_calendar_data):
        """Inner join should only keep dates in both."""
        us_df, uk_df = different_calendar_data

        aligned_us, aligned_uk = align_dates(us_df, uk_df, how="inner")

        # Both should have same dates
        assert len(aligned_us) == len(aligned_uk)

        us_dates = set(pd.to_datetime(aligned_us["date"]).dt.date)
        uk_dates = set(pd.to_datetime(aligned_uk["date"]).dt.date)
        assert us_dates == uk_dates

    def test_left_join(self, different_calendar_data):
        """Left join should keep all dates from first DataFrame."""
        us_df, uk_df = different_calendar_data

        aligned_us, aligned_uk = align_dates(us_df, uk_df, how="left")

        # US should have all its original dates
        assert len(aligned_us) == len(us_df)

    def test_right_join(self, different_calendar_data):
        """Right join should keep all dates from second DataFrame."""
        us_df, uk_df = different_calendar_data

        aligned_us, aligned_uk = align_dates(us_df, uk_df, how="right")

        # UK should have all its original dates
        assert len(aligned_uk) == len(uk_df)

    def test_sorted_by_date(self, different_calendar_data):
        """Result should be sorted by date."""
        us_df, uk_df = different_calendar_data

        aligned_us, _ = align_dates(us_df, uk_df, how="inner")

        dates = pd.to_datetime(aligned_us["date"])
        assert dates.is_monotonic_increasing
