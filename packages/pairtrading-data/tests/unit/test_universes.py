"""Unit tests for stock universes."""

import tempfile
from datetime import date

import pytest

from ptdata.universes.custom import CustomUniverse
from ptdata.universes.sectors import SHIPPING_STOCKS, SectorUniverse
from ptdata.universes.sp500 import SP500Universe


class TestCustomUniverse:
    """Test CustomUniverse functionality."""

    def test_basic_creation(self):
        """Should create universe with given symbols."""
        universe = CustomUniverse(["AAPL", "MSFT", "GOOGL"])

        symbols = universe.get_symbols()

        assert len(symbols) == 3
        assert "AAPL" in symbols
        assert "MSFT" in symbols
        assert "GOOGL" in symbols

    def test_deduplicates_symbols(self):
        """Should deduplicate symbols."""
        universe = CustomUniverse(["AAPL", "MSFT", "AAPL", "GOOGL", "MSFT"])

        symbols = universe.get_symbols()

        assert len(symbols) == 3

    def test_sorts_symbols(self):
        """Should sort symbols alphabetically."""
        universe = CustomUniverse(["MSFT", "AAPL", "GOOGL"])

        symbols = universe.get_symbols()

        assert symbols == ["AAPL", "GOOGL", "MSFT"]

    def test_name_property(self):
        """Should have default name 'custom'."""
        universe = CustomUniverse(["AAPL"])

        assert universe.name == "custom"

    def test_custom_name(self):
        """Should accept custom name."""
        universe = CustomUniverse(["AAPL"], name="my_universe")

        assert universe.name == "my_universe"

    def test_len(self):
        """Should return correct length."""
        universe = CustomUniverse(["AAPL", "MSFT", "GOOGL"])

        assert len(universe) == 3

    def test_contains(self):
        """Should support 'in' operator."""
        universe = CustomUniverse(["AAPL", "MSFT"])

        assert "AAPL" in universe
        assert "GOOGL" not in universe

    def test_from_file(self):
        """Should load symbols from file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("AAPL\n")
            f.write("MSFT\n")
            f.write("GOOGL\n")
            f.write("\n")  # Empty line should be ignored
            f.write("# Comment should be ignored\n")
            f.flush()

            universe = CustomUniverse.from_file(f.name)

        symbols = universe.get_symbols()
        assert len(symbols) == 3
        assert "AAPL" in symbols

    def test_returns_copy(self):
        """get_symbols should return a copy, not the original list."""
        universe = CustomUniverse(["AAPL", "MSFT"])

        symbols = universe.get_symbols()
        symbols.append("GOOGL")

        assert len(universe.get_symbols()) == 2


class TestSectorUniverse:
    """Test SectorUniverse functionality."""

    def test_shipping_sector(self):
        """Should return shipping stocks."""
        universe = SectorUniverse("shipping")

        symbols = universe.get_symbols()

        assert len(symbols) > 0
        # Check some known shipping stocks
        assert any(s in symbols for s in ["ZIM", "GOGL", "SBLK"])

    def test_mining_sector(self):
        """Should return mining stocks."""
        universe = SectorUniverse("mining")

        symbols = universe.get_symbols()

        assert len(symbols) > 0

    def test_unknown_sector_raises(self):
        """Should raise error for unknown sector."""
        with pytest.raises(ValueError) as exc_info:
            SectorUniverse("unknown_sector")

        assert "unknown_sector" in str(exc_info.value)

    def test_name_property(self):
        """Should return sector name."""
        universe = SectorUniverse("shipping")

        assert universe.name == "shipping"

    def test_available_sectors(self):
        """Should have multiple sectors available."""
        sectors = SectorUniverse.available_sectors()

        assert len(sectors) >= 3
        assert "shipping" in sectors
        assert "mining" in sectors
        assert "metals" in sectors

    def test_len(self):
        """Should return correct length."""
        universe = SectorUniverse("shipping")

        assert len(universe) == len(SHIPPING_STOCKS)

    def test_contains(self):
        """Should support 'in' operator."""
        universe = SectorUniverse("shipping")

        assert SHIPPING_STOCKS[0] in universe


class TestSP500Universe:
    """Test SP500Universe functionality."""

    def test_fallback_mode(self):
        """Should work with fallback list when not fetching online."""
        universe = SP500Universe(fetch_online=False)

        symbols = universe.get_symbols()

        assert len(symbols) > 0
        # Check some known S&P 500 stocks
        assert "AAPL" in symbols
        assert "MSFT" in symbols

    def test_name_property(self):
        """Should have name 'sp500'."""
        universe = SP500Universe(fetch_online=False)

        assert universe.name == "sp500"

    def test_len(self):
        """Should return correct length."""
        universe = SP500Universe(fetch_online=False)

        assert len(universe) > 50  # Fallback has at least this many

    def test_contains(self):
        """Should support 'in' operator."""
        universe = SP500Universe(fetch_online=False)

        assert "AAPL" in universe
        assert "NONEXISTENT" not in universe

    def test_returns_copy(self):
        """get_symbols should return a copy."""
        universe = SP500Universe(fetch_online=False)

        symbols = universe.get_symbols()
        original_len = len(symbols)
        symbols.append("TEST")

        assert len(universe.get_symbols()) == original_len

    def test_as_of_date_warning(self):
        """as_of_date is currently ignored but shouldn't raise."""
        universe = SP500Universe(fetch_online=False)

        # This should not raise, even though the feature isn't implemented
        symbols = universe.get_symbols(as_of_date=date(2015, 1, 1))

        assert len(symbols) > 0
