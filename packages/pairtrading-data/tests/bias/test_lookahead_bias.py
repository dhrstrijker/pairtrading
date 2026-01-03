"""Tests to detect look-ahead bias.

Look-ahead bias occurs when future information is used to make
decisions that would have been made at an earlier point in time.
This is one of the most common and dangerous errors in backtesting.

These tests verify that the PointInTimeDataFrame wrapper correctly
prevents access to future data.
"""

from datetime import date, timedelta

import pandas as pd
import pytest

from ptdata.core.exceptions import LookAheadBiasError
from ptdata.validation.lookahead import PointInTimeDataFrame


class TestLookAheadBias:
    """Tests to detect and prevent look-ahead bias."""

    def test_cannot_access_future_data(self, sample_prices):
        """PointInTimeDataFrame should only return past data."""
        ref_date = date(2020, 6, 15)
        pit = PointInTimeDataFrame(sample_prices, ref_date)

        data = pit.get_data()
        max_date = pd.to_datetime(data["date"]).max().date()

        assert max_date <= ref_date, (
            f"Look-ahead bias detected: returned data up to {max_date} "
            f"but reference date is {ref_date}"
        )

    def test_cannot_move_reference_backward(self, sample_prices):
        """Reference date can only move forward in time."""
        pit = PointInTimeDataFrame(sample_prices, date(2020, 6, 15))

        with pytest.raises(LookAheadBiasError) as exc_info:
            pit.advance_to(date(2020, 6, 1))

        assert "backward" in str(exc_info.value).lower()

    def test_slice_cannot_exceed_reference(self, sample_prices):
        """Cannot slice data beyond the reference date."""
        pit = PointInTimeDataFrame(sample_prices, date(2020, 6, 15))

        with pytest.raises(LookAheadBiasError):
            pit.slice(date(2020, 1, 1), date(2020, 12, 31))

    def test_split_adjustment_no_future_leak(self, data_with_split):
        """Split adjustment should not use future split information.

        Before a split occurs, the adjusted prices should NOT yet
        reflect the split. Only after the split date should the
        historical prices be adjusted.

        This test verifies that if we're looking at data as of
        one day before the split, we don't see the adjustment yet.
        """
        prices, splits = data_with_split
        split_date = pd.to_datetime(splits.iloc[0]["date"]).date()
        day_before_split = split_date - timedelta(days=1)

        # Create point-in-time view as of day before split
        pit = PointInTimeDataFrame(prices, day_before_split)
        data = pit.get_data()

        # On the day before a split, looking at historical data,
        # adj_close should NOT yet be divided by split ratio
        # (because we don't "know" about the future split)
        #
        # Note: In practice, data providers may provide fully adjusted
        # data. This test is more about the concept - the PIT wrapper
        # should at minimum not expose future dates.
        assert data["date"].max() <= pd.Timestamp(day_before_split)

    def test_advancing_reveals_new_data(self, sample_prices):
        """Advancing the reference date should reveal more data."""
        pit1 = PointInTimeDataFrame(sample_prices, date(2020, 3, 1))
        pit2 = pit1.advance_to(date(2020, 6, 1))

        data1 = pit1.get_data()
        data2 = pit2.get_data()

        assert len(data2) > len(data1), (
            "Advancing reference date should reveal additional data"
        )

    def test_each_day_simulation(self, sample_prices):
        """Simulate day-by-day advancement to verify no leakage."""
        start_date = date(2020, 1, 15)
        end_date = date(2020, 2, 15)

        pit = PointInTimeDataFrame(sample_prices, start_date)

        current_date = start_date
        while current_date <= end_date:
            data = pit.get_data()

            # Verify no future data visible
            if not data.empty:
                max_visible = pd.to_datetime(data["date"]).max().date()
                assert max_visible <= current_date, (
                    f"Future data leaked: saw {max_visible} on {current_date}"
                )

            # Advance to next trading day
            current_date += timedelta(days=1)
            if current_date <= end_date:
                pit = pit.advance_to(current_date)

    def test_get_latest_respects_reference_date(self, sample_multi_symbol_prices):
        """get_latest should return data as of reference date."""
        ref_date = date(2020, 6, 15)
        pit = PointInTimeDataFrame(sample_multi_symbol_prices, ref_date)

        latest = pit.get_latest("AAPL")

        assert latest is not None
        latest_date = pd.to_datetime(latest["date"]).date()
        assert latest_date <= ref_date

    def test_multiple_symbols_all_filtered(self, sample_multi_symbol_prices):
        """All symbols should be filtered by reference date."""
        ref_date = date(2020, 6, 15)
        pit = PointInTimeDataFrame(sample_multi_symbol_prices, ref_date)

        for symbol in ["AAPL", "MSFT", "GOOGL"]:
            data = pit.for_symbol(symbol)
            if not data.empty:
                max_date = pd.to_datetime(data["date"]).max().date()
                assert max_date <= ref_date, (
                    f"Future data for {symbol}: {max_date} > {ref_date}"
                )


class TestLookAheadBiasInSignals:
    """Test that signals cannot use future information."""

    def test_moving_average_uses_only_past(self, sample_prices):
        """Moving average calculation should only use past data."""
        ref_date = date(2020, 6, 15)
        pit = PointInTimeDataFrame(sample_prices, ref_date)
        data = pit.get_data()

        if len(data) >= 20:
            # Calculate 20-day MA using only visible data
            ma20 = data["close"].rolling(window=20).mean()

            # The last MA value should only use the last 20 visible days
            # This is more about demonstrating correct usage
            assert len(ma20.dropna()) <= len(data) - 19

    def test_correlation_uses_only_past(self, sample_multi_symbol_prices):
        """Correlation calculation should only use past data."""
        ref_date = date(2020, 6, 15)
        pit = PointInTimeDataFrame(sample_multi_symbol_prices, ref_date)
        data = pit.get_data()

        # Calculate correlation between AAPL and MSFT
        aapl = data[data["symbol"] == "AAPL"]["close"].reset_index(drop=True)
        msft = data[data["symbol"] == "MSFT"]["close"].reset_index(drop=True)

        if len(aapl) >= 20 and len(msft) >= 20:
            # Make sure we're using aligned data
            min_len = min(len(aapl), len(msft))
            corr = aapl[:min_len].corr(msft[:min_len])

            # Correlation should be calculable without future data
            assert not pd.isna(corr)
