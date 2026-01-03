"""Tests for trading calendar alignment.

Different markets have different trading calendars:
- US markets closed for Thanksgiving, July 4th
- UK markets closed for bank holidays
- Hong Kong has different holidays

When analyzing pairs across markets, dates must be aligned
to avoid comparing data from different days.

These tests verify proper calendar alignment.
"""


import pandas as pd

from ptdata.validation.gaps import align_dates, find_gaps


class TestCalendarAlignment:
    """Tests for aligning different trading calendars."""

    def test_inner_join_keeps_common_dates(self, different_calendar_data):
        """Inner join should only keep dates present in both datasets."""
        us_df, uk_df = different_calendar_data

        aligned_us, aligned_uk = align_dates(us_df, uk_df, how="inner")

        # Both should have same dates
        us_dates = set(pd.to_datetime(aligned_us["date"]).dt.date)
        uk_dates = set(pd.to_datetime(aligned_uk["date"]).dt.date)

        assert us_dates == uk_dates, "Inner join should result in identical date sets"

        # Length should be same
        assert len(aligned_us) == len(aligned_uk)

    def test_inner_join_smaller_than_either(self, different_calendar_data):
        """Inner join result should be <= either input."""
        us_df, uk_df = different_calendar_data

        aligned_us, aligned_uk = align_dates(us_df, uk_df, how="inner")

        assert len(aligned_us) <= len(us_df)
        assert len(aligned_uk) <= len(uk_df)

    def test_left_join_preserves_first(self, different_calendar_data):
        """Left join should keep all dates from first DataFrame."""
        us_df, uk_df = different_calendar_data

        aligned_us, aligned_uk = align_dates(us_df, uk_df, how="left")

        # US dates should all be preserved
        us_dates = set(pd.to_datetime(us_df["date"]).dt.date)
        aligned_us_dates = set(pd.to_datetime(aligned_us["date"]).dt.date)

        assert aligned_us_dates == us_dates, "Left join should preserve all left dates"

    def test_right_join_preserves_second(self, different_calendar_data):
        """Right join should keep all dates from second DataFrame."""
        us_df, uk_df = different_calendar_data

        aligned_us, aligned_uk = align_dates(us_df, uk_df, how="right")

        # UK dates should all be preserved
        uk_dates = set(pd.to_datetime(uk_df["date"]).dt.date)
        aligned_uk_dates = set(pd.to_datetime(aligned_uk["date"]).dt.date)

        assert aligned_uk_dates == uk_dates, "Right join should preserve right dates"

    def test_aligned_data_sorted(self, different_calendar_data):
        """Aligned data should be sorted by date."""
        us_df, uk_df = different_calendar_data

        aligned_us, aligned_uk = align_dates(us_df, uk_df, how="inner")

        # Check sorting
        us_dates = pd.to_datetime(aligned_us["date"])
        uk_dates = pd.to_datetime(aligned_uk["date"])

        assert us_dates.is_monotonic_increasing
        assert uk_dates.is_monotonic_increasing


class TestCrossMarketPairs:
    """Tests for pairs spanning different markets."""

    def test_pair_return_calculation(self, different_calendar_data):
        """Returns should be calculated on aligned dates only."""
        us_df, uk_df = different_calendar_data

        aligned_us, aligned_uk = align_dates(us_df, uk_df, how="inner")

        # Calculate returns
        us_returns = aligned_us["close"].pct_change()
        uk_returns = aligned_uk["close"].pct_change()

        # Should have same length
        assert len(us_returns) == len(uk_returns)

        # Can calculate spread
        spread = us_returns - uk_returns
        assert len(spread) == len(us_returns)

    def test_correlation_on_aligned_dates(self, different_calendar_data):
        """Correlation should be calculated on aligned dates."""
        us_df, uk_df = different_calendar_data

        aligned_us, aligned_uk = align_dates(us_df, uk_df, how="inner")

        # Calculate correlation on aligned data
        us_returns = aligned_us["close"].pct_change().dropna()
        uk_returns = aligned_uk["close"].pct_change().dropna()

        # Ensure same length for correlation
        min_len = min(len(us_returns), len(uk_returns))
        corr = us_returns[:min_len].corr(uk_returns[:min_len])

        assert not pd.isna(corr), "Correlation should be calculable"
        assert -1 <= corr <= 1, "Correlation should be in valid range"


class TestHolidayHandling:
    """Tests for specific holiday scenarios."""

    def test_us_thanksgiving_gap(self):
        """US markets should have gap around Thanksgiving."""
        # Thanksgiving is 4th Thursday of November
        # Market closed Thu-Fri
        dates = pd.bdate_range("2020-11-01", "2020-11-30")

        # Remove Thanksgiving period (Nov 26-27, 2020)
        thanksgiving_dates = [pd.Timestamp("2020-11-26"), pd.Timestamp("2020-11-27")]
        dates = dates[~dates.isin(thanksgiving_dates)]

        df = pd.DataFrame({
            "symbol": ["US_STOCK"] * len(dates),
            "date": dates,
            "close": [100.0] * len(dates),
        })

        # Find gaps - should not flag Thanksgiving as suspicious
        gaps = find_gaps(df)

        # Small gap (2 days + weekend = 4 days) should not be flagged
        # Our threshold is >5 days
        assert len(gaps) == 0, "Thanksgiving gap should not be flagged as suspicious"

    def test_christmas_new_year_gap(self):
        """Extended holiday period should be flagged if > 5 days."""
        # Around Christmas/New Year, markets may be closed multiple days
        dates = pd.bdate_range("2020-12-01", "2021-01-15")

        # Remove extended holiday period (Dec 24 - Jan 1)
        holiday_dates = pd.date_range("2020-12-24", "2021-01-01")
        dates = dates[~dates.isin(holiday_dates)]

        df = pd.DataFrame({
            "symbol": ["US_STOCK"] * len(dates),
            "date": dates,
            "close": [100.0] * len(dates),
        })

        gaps = find_gaps(df)

        # This should be flagged as it's > 5 calendar days
        assert len(gaps) > 0, "Extended holiday gap should be flagged"


class TestTimezoneConsiderations:
    """Tests for timezone-related issues."""

    def test_dates_not_times(self):
        """Alignment should work on dates, not times."""
        # Create data with same dates (different times don't matter for daily data)
        dates = pd.bdate_range("2020-01-01", periods=10)

        us_df = pd.DataFrame({
            "symbol": ["US"] * 10,
            "date": dates,
            "close": [100.0] * 10,
        })

        uk_df = pd.DataFrame({
            "symbol": ["UK"] * 10,
            "date": dates,
            "close": [150.0] * 10,
        })

        aligned_us, aligned_uk = align_dates(us_df, uk_df, how="inner")

        # Should align on date
        assert len(aligned_us) == 10, "Should align on dates"
        assert len(aligned_uk) == 10, "Should align on dates"


class TestEdgeCases:
    """Edge cases in calendar alignment."""

    def test_no_overlap(self):
        """Should handle case with no overlapping dates."""
        dates1 = pd.bdate_range("2020-01-01", periods=10)
        dates2 = pd.bdate_range("2020-02-01", periods=10)

        df1 = pd.DataFrame({
            "symbol": ["A"] * 10,
            "date": dates1,
            "close": [100.0] * 10,
        })

        df2 = pd.DataFrame({
            "symbol": ["B"] * 10,
            "date": dates2,
            "close": [100.0] * 10,
        })

        aligned1, aligned2 = align_dates(df1, df2, how="inner")

        assert len(aligned1) == 0, "No overlap should result in empty DataFrame"
        assert len(aligned2) == 0

    def test_complete_overlap(self):
        """Should handle complete overlap correctly."""
        dates = pd.bdate_range("2020-01-01", periods=10)

        df1 = pd.DataFrame({
            "symbol": ["A"] * 10,
            "date": dates,
            "close": [100.0] * 10,
        })

        df2 = pd.DataFrame({
            "symbol": ["B"] * 10,
            "date": dates,
            "close": [150.0] * 10,
        })

        aligned1, aligned2 = align_dates(df1, df2, how="inner")

        assert len(aligned1) == 10, "Complete overlap should preserve all dates"
        assert len(aligned2) == 10

    def test_single_overlapping_date(self):
        """Should handle single overlapping date."""
        df1 = pd.DataFrame({
            "symbol": ["A"] * 5,
            "date": pd.bdate_range("2020-01-01", periods=5),
            "close": [100.0] * 5,
        })

        df2 = pd.DataFrame({
            "symbol": ["B"] * 5,
            "date": pd.bdate_range("2020-01-03", periods=5),  # Overlaps on Jan 3-7
            "close": [150.0] * 5,
        })

        aligned1, aligned2 = align_dates(df1, df2, how="inner")

        # Should have 3 overlapping business days (Jan 3, 6, 7)
        assert len(aligned1) > 0, "Should find overlapping dates"
        assert len(aligned1) == len(aligned2)

    def test_empty_dataframe(self):
        """Should handle empty DataFrame gracefully."""
        df1 = pd.DataFrame(columns=["symbol", "date", "close"])
        df2 = pd.DataFrame({
            "symbol": ["B"] * 5,
            "date": pd.bdate_range("2020-01-01", periods=5),
            "close": [100.0] * 5,
        })

        aligned1, aligned2 = align_dates(df1, df2, how="inner")

        assert len(aligned1) == 0
        assert len(aligned2) == 0
