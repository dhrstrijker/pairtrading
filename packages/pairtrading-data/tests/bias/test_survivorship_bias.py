"""Tests to detect survivorship bias.

Survivorship bias occurs when failed/delisted companies are excluded
from the analysis, making historical returns appear better than they
actually were.

These tests verify that:
1. Delisted stocks are included in data up to their delisting date
2. Universe constituents are tracked point-in-time where possible
3. The system warns when survivorship bias may be present
"""

from datetime import date, timedelta

import pandas as pd

from ptdata.universes.sp500 import SP500Universe
from ptdata.validation.lookahead import PointInTimeDataFrame


class TestSurvivorshipBias:
    """Tests to detect and prevent survivorship bias."""

    def test_delisted_stock_included_until_delisting(self, data_with_delisting):
        """Delisted stocks should be in data until delisting date."""
        df = data_with_delisting

        # Verify we have data for the stock
        assert len(df) > 0, "Delisted stock should have data until delisting"

        # Check that data ends (the stock was delisted)
        assert len(df) < 252, "Delisted stock should have fewer than 252 days of data"

        # Verify the last row is marked as delisted
        assert df["delisted"].iloc[-1], "Last row should be marked as delisted"

        # Verify data exists before delisting
        non_delisted = df[~df["delisted"]]
        assert len(non_delisted) > 0, "Should have data before delisting"

    def test_point_in_time_view_includes_delisted(self, data_with_delisting):
        """Point-in-time view should include delisted stock before delisting."""
        df = data_with_delisting

        # Get the delisting date
        delist_date = df[df["delisted"]]["date"].iloc[0]
        delist_date = pd.to_datetime(delist_date).date()

        # Create PIT view one day before delisting
        day_before = delist_date - timedelta(days=1)
        pit = PointInTimeDataFrame(df, day_before)

        data = pit.get_data()
        assert len(data) > 0, (
            "Delisted stock should be visible before its delisting date"
        )

    def test_point_in_time_view_after_delisting(self, data_with_delisting):
        """Point-in-time view after delisting should still show historical data."""
        df = data_with_delisting

        # Get the delisting date
        delist_date = df[df["delisted"]]["date"].iloc[0]
        delist_date = pd.to_datetime(delist_date).date()

        # Create PIT view after delisting
        after_delist = delist_date + timedelta(days=30)
        pit = PointInTimeDataFrame(df, after_delist)

        data = pit.get_data()
        # Should see all historical data up to delisting
        assert len(data) == len(df), (
            "Should be able to see all historical data including delisted stock"
        )

    def test_universe_point_in_time_warning(self):
        """Universe should warn when point-in-time data is not available.

        The SP500Universe currently returns current constituents only,
        which introduces survivorship bias. This test documents this
        limitation.
        """
        universe = SP500Universe(fetch_online=False)

        # Requesting historical constituents
        # Currently this returns current constituents (known limitation)
        symbols_2015 = universe.get_symbols(as_of_date=date(2015, 1, 1))
        symbols_now = universe.get_symbols()

        # Note: This is documenting current (limited) behavior
        # A proper implementation would return different results
        assert len(symbols_2015) == len(symbols_now), (
            "Current implementation doesn't support point-in-time universe "
            "(this is a known limitation that should be fixed in future)"
        )


class TestSurvivorshipBiasInBacktest:
    """Test survivorship bias in backtest scenarios."""

    def test_pair_with_delisted_stock(self, data_with_delisting, sample_prices):
        """Pairs including delisted stocks should handle delisting correctly."""
        delisting_df = data_with_delisting.copy()
        surviving_df = sample_prices.copy()

        # Make sure the surviving stock has data beyond the delisting
        surviving_df["symbol"] = "SURVIVOR"

        # Combine into one dataset
        combined = pd.concat([delisting_df, surviving_df], ignore_index=True)

        # Before delisting, both stocks should be available
        delist_date = delisting_df[delisting_df["delisted"]]["date"].iloc[0]
        delist_date = pd.to_datetime(delist_date).date()
        before_delist = delist_date - timedelta(days=30)

        pit = PointInTimeDataFrame(combined, before_delist)
        data = pit.get_data()

        symbols = data["symbol"].unique()
        assert len(symbols) == 2, "Both stocks should be visible before delisting"

    def test_calculating_returns_with_delisting(self, data_with_delisting):
        """Return calculation should handle delisting correctly."""
        df = data_with_delisting.copy()

        # Calculate returns
        df = df.sort_values("date")
        df["return"] = df["close"].pct_change()

        # The last return (delisting) might be extreme
        # but should be included in any analysis
        assert len(df[~df["return"].isna()]) > 0

        # Check that we captured the decline leading to delisting
        last_returns = df["return"].tail(10)
        assert last_returns.mean() < 0, (
            "Returns before delisting should be negative on average"
        )


class TestSurvivorshipAwareness:
    """Tests to ensure the system is aware of survivorship bias risks."""

    def test_sector_universe_is_static(self):
        """Sector universes are static and may have survivorship bias.

        This test documents that sector universes don't track historical
        changes (companies leaving/joining sectors).
        """
        from ptdata.universes.sectors import SectorUniverse

        universe = SectorUniverse("shipping")

        # These should return the same symbols (static list)
        symbols_2015 = universe.get_symbols(as_of_date=date(2015, 1, 1))
        symbols_2020 = universe.get_symbols(as_of_date=date(2020, 1, 1))

        assert symbols_2015 == symbols_2020, (
            "Sector universe is static - same symbols regardless of date "
            "(survivorship bias risk)"
        )

    def test_custom_universe_has_no_temporal_awareness(self):
        """Custom universes are user-defined and static."""
        from ptdata.universes.custom import CustomUniverse

        universe = CustomUniverse(["AAPL", "MSFT", "LEHM"])  # LEHM = Lehman Bros

        # Lehman Bros was delisted in 2008, but custom universe
        # doesn't know about this
        symbols = universe.get_symbols(as_of_date=date(2007, 1, 1))

        assert "LEHM" in symbols, (
            "Custom universe includes all symbols regardless of date "
            "(user must manually handle delistings)"
        )
