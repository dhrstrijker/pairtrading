"""Unit tests for CSV cache system."""

from datetime import date
from pathlib import Path
from unittest.mock import Mock, patch
import json

import pandas as pd
import pytest

from ptdata.cache.csv_cache import CSVCache
from ptdata.cache.metadata import CacheMetadata


class TestCacheMetadata:
    """Test cache metadata tracking."""

    def test_save_and_load(self, temp_cache_dir):
        """Should save and load metadata correctly."""
        metadata = CacheMetadata(temp_cache_dir)

        metadata.set("AAPL", date(2020, 1, 1), date(2020, 12, 31), row_count=252)
        metadata.save()

        # Create new instance to test loading
        metadata2 = CacheMetadata.load(temp_cache_dir)
        info = metadata2.get("AAPL")

        assert info is not None
        assert info.start_date == date(2020, 1, 1)
        assert info.end_date == date(2020, 12, 31)

    def test_unknown_symbol_returns_none(self, temp_cache_dir):
        """Should return None for unknown symbols."""
        metadata = CacheMetadata(temp_cache_dir)

        result = metadata.get("UNKNOWN")

        assert result is None

    def test_is_valid_full_coverage(self, temp_cache_dir):
        """Should return True when cache fully covers requested range."""
        metadata = CacheMetadata(temp_cache_dir)
        metadata.set("AAPL", date(2020, 1, 1), date(2020, 12, 31), row_count=252)

        # Fully covered (use max_age_days=0 to ignore expiry)
        assert metadata.is_valid("AAPL", date(2020, 3, 1), date(2020, 6, 30), max_age_days=0)
        assert metadata.is_valid("AAPL", date(2020, 1, 1), date(2020, 12, 31), max_age_days=0)

    def test_is_valid_partial_coverage(self, temp_cache_dir):
        """Should return False when cache doesn't fully cover range."""
        metadata = CacheMetadata(temp_cache_dir)
        metadata.set("AAPL", date(2020, 1, 1), date(2020, 6, 30), row_count=126)

        # Not covered - extends beyond
        assert not metadata.is_valid("AAPL", date(2020, 1, 1), date(2020, 12, 31), max_age_days=0)
        # Not covered - starts before
        assert not metadata.is_valid("AAPL", date(2019, 6, 1), date(2020, 3, 1), max_age_days=0)

    def test_remove_symbol(self, temp_cache_dir):
        """Should remove metadata for a symbol."""
        metadata = CacheMetadata(temp_cache_dir)
        metadata.set("AAPL", date(2020, 1, 1), date(2020, 12, 31), row_count=252)
        metadata.set("MSFT", date(2020, 1, 1), date(2020, 12, 31), row_count=252)

        metadata.remove("AAPL")

        assert metadata.get("AAPL") is None
        assert metadata.get("MSFT") is not None


class TestCSVCache:
    """Test CSVCache functionality."""

    def test_cache_miss_calls_provider(self, temp_cache_dir):
        """Should call provider when cache miss occurs."""
        mock_provider = Mock()
        mock_provider.name = "mock"
        mock_provider.get_prices.return_value = pd.DataFrame({
            "symbol": ["AAPL"] * 5,
            "date": pd.date_range("2020-01-01", periods=5),
            "open": [100.0] * 5,
            "high": [101.0] * 5,
            "low": [99.0] * 5,
            "close": [100.5] * 5,
            "adj_close": [100.5] * 5,
            "volume": [1000000] * 5,
        })

        cache = CSVCache(temp_cache_dir, mock_provider)
        result = cache.get_prices(
            symbols=["AAPL"],
            start_date=date(2020, 1, 1),
            end_date=date(2020, 1, 10),
        )

        mock_provider.get_prices.assert_called_once()
        assert len(result) == 5

    def test_cache_hit_skips_provider(self, temp_cache_dir):
        """Should not call provider when cache hit occurs."""
        mock_provider = Mock()
        mock_provider.name = "mock"
        mock_provider.get_prices.return_value = pd.DataFrame({
            "symbol": ["AAPL"] * 5,
            "date": pd.date_range("2020-01-01", periods=5),
            "open": [100.0] * 5,
            "high": [101.0] * 5,
            "low": [99.0] * 5,
            "close": [100.5] * 5,
            "adj_close": [100.5] * 5,
            "volume": [1000000] * 5,
        })

        cache = CSVCache(temp_cache_dir, mock_provider)

        # First call - cache miss
        cache.get_prices(
            symbols=["AAPL"],
            start_date=date(2020, 1, 1),
            end_date=date(2020, 1, 5),
        )

        # Reset mock
        mock_provider.reset_mock()

        # Second call - cache hit (same range)
        result = cache.get_prices(
            symbols=["AAPL"],
            start_date=date(2020, 1, 1),
            end_date=date(2020, 1, 5),
        )

        mock_provider.get_prices.assert_not_called()
        assert len(result) == 5

    def test_cache_invalidation_on_range_extension(self, temp_cache_dir):
        """Should re-download when requested range extends beyond cache."""
        mock_provider = Mock()
        mock_provider.name = "mock"

        # First response - partial range
        first_response = pd.DataFrame({
            "symbol": ["AAPL"] * 5,
            "date": pd.date_range("2020-01-01", periods=5),
            "open": [100.0] * 5,
            "high": [101.0] * 5,
            "low": [99.0] * 5,
            "close": [100.5] * 5,
            "adj_close": [100.5] * 5,
            "volume": [1000000] * 5,
        })

        # Second response - extended range
        second_response = pd.DataFrame({
            "symbol": ["AAPL"] * 10,
            "date": pd.date_range("2020-01-01", periods=10),
            "open": [100.0] * 10,
            "high": [101.0] * 10,
            "low": [99.0] * 10,
            "close": [100.5] * 10,
            "adj_close": [100.5] * 10,
            "volume": [1000000] * 10,
        })

        mock_provider.get_prices.side_effect = [first_response, second_response]

        cache = CSVCache(temp_cache_dir, mock_provider)

        # First call - cache miss
        cache.get_prices(
            symbols=["AAPL"],
            start_date=date(2020, 1, 1),
            end_date=date(2020, 1, 5),
        )

        # Second call - extended range, should trigger re-download
        result = cache.get_prices(
            symbols=["AAPL"],
            start_date=date(2020, 1, 1),
            end_date=date(2020, 1, 10),
        )

        assert mock_provider.get_prices.call_count == 2
        assert len(result) == 10

    def test_writes_csv_file(self, temp_cache_dir):
        """Should write CSV file to cache directory."""
        mock_provider = Mock()
        mock_provider.name = "mock"
        mock_provider.get_prices.return_value = pd.DataFrame({
            "symbol": ["AAPL"] * 5,
            "date": pd.date_range("2020-01-01", periods=5),
            "open": [100.0] * 5,
            "high": [101.0] * 5,
            "low": [99.0] * 5,
            "close": [100.5] * 5,
            "adj_close": [100.5] * 5,
            "volume": [1000000] * 5,
        })

        cache = CSVCache(temp_cache_dir, mock_provider)
        cache.get_prices(
            symbols=["AAPL"],
            start_date=date(2020, 1, 1),
            end_date=date(2020, 1, 10),
        )

        csv_path = temp_cache_dir / "AAPL.csv"
        assert csv_path.exists()

        # Verify content
        df = pd.read_csv(csv_path)
        assert len(df) == 5
        assert df["symbol"].iloc[0] == "AAPL"

    def test_clear_cache_removes_files(self, temp_cache_dir):
        """Should remove cached files when clearing cache."""
        mock_provider = Mock()
        mock_provider.name = "mock"
        mock_provider.get_prices.return_value = pd.DataFrame({
            "symbol": ["AAPL"] * 5,
            "date": pd.date_range("2020-01-01", periods=5),
            "open": [100.0] * 5,
            "high": [101.0] * 5,
            "low": [99.0] * 5,
            "close": [100.5] * 5,
            "adj_close": [100.5] * 5,
            "volume": [1000000] * 5,
        })

        cache = CSVCache(temp_cache_dir, mock_provider)
        cache.get_prices(
            symbols=["AAPL"],
            start_date=date(2020, 1, 1),
            end_date=date(2020, 1, 10),
        )

        csv_path = temp_cache_dir / "AAPL.csv"
        assert csv_path.exists()

        cache.clear_cache(symbols=["AAPL"])
        assert not csv_path.exists()

    def test_multiple_symbols(self, temp_cache_dir):
        """Should handle multiple symbols correctly."""
        mock_provider = Mock()
        mock_provider.name = "mock"
        mock_provider.get_prices.return_value = pd.DataFrame({
            "symbol": ["AAPL"] * 5 + ["MSFT"] * 5,
            "date": list(pd.date_range("2020-01-01", periods=5)) * 2,
            "open": [100.0] * 10,
            "high": [101.0] * 10,
            "low": [99.0] * 10,
            "close": [100.5] * 10,
            "adj_close": [100.5] * 10,
            "volume": [1000000] * 10,
        })

        cache = CSVCache(temp_cache_dir, mock_provider)
        result = cache.get_prices(
            symbols=["AAPL", "MSFT"],
            start_date=date(2020, 1, 1),
            end_date=date(2020, 1, 10),
        )

        assert len(result) == 10
        assert sorted(result["symbol"].unique().tolist()) == ["AAPL", "MSFT"]
