"""Unit tests for data providers."""

from datetime import date
from decimal import Decimal
from unittest.mock import Mock, patch
import json

import pandas as pd
import pytest

from ptdata.providers.base import DataProvider
from ptdata.providers.csv_file import CSVFileProvider
from ptdata.providers.massive import MassiveAPIProvider
from ptdata.core.exceptions import PTDataError


class TestDataProviderProtocol:
    """Test that providers conform to the DataProvider protocol."""

    def test_csv_provider_has_name(self, temp_cache_dir):
        """CSVFileProvider should have a name property."""
        provider = CSVFileProvider(temp_cache_dir)
        assert hasattr(provider, "name")
        assert isinstance(provider.name, str)
        assert provider.name == "csv_file"

    def test_csv_provider_has_get_prices(self, temp_cache_dir):
        """CSVFileProvider should have get_prices method."""
        provider = CSVFileProvider(temp_cache_dir)
        assert hasattr(provider, "get_prices")
        assert callable(provider.get_prices)


class TestCSVFileProvider:
    """Test CSVFileProvider functionality."""

    def test_load_single_file(self, temp_cache_dir):
        """Should load a single CSV file."""
        # Create test CSV
        csv_path = temp_cache_dir / "AAPL.csv"
        df = pd.DataFrame({
            "symbol": ["AAPL"] * 5,
            "date": pd.date_range("2020-01-01", periods=5),
            "open": [100.0, 101.0, 102.0, 103.0, 104.0],
            "high": [101.0, 102.0, 103.0, 104.0, 105.0],
            "low": [99.0, 100.0, 101.0, 102.0, 103.0],
            "close": [100.5, 101.5, 102.5, 103.5, 104.5],
            "adj_close": [100.5, 101.5, 102.5, 103.5, 104.5],
            "volume": [1000000] * 5,
        })
        df.to_csv(csv_path, index=False)

        provider = CSVFileProvider(temp_cache_dir)
        result = provider.get_prices(
            symbols=["AAPL"],
            start_date=date(2020, 1, 1),
            end_date=date(2020, 1, 10),
        )

        assert len(result) == 5
        assert result["symbol"].unique().tolist() == ["AAPL"]

    def test_load_multiple_files(self, temp_cache_dir):
        """Should load multiple CSV files."""
        for symbol in ["AAPL", "MSFT"]:
            csv_path = temp_cache_dir / f"{symbol}.csv"
            df = pd.DataFrame({
                "symbol": [symbol] * 5,
                "date": pd.date_range("2020-01-01", periods=5),
                "open": [100.0] * 5,
                "high": [101.0] * 5,
                "low": [99.0] * 5,
                "close": [100.5] * 5,
                "adj_close": [100.5] * 5,
                "volume": [1000000] * 5,
            })
            df.to_csv(csv_path, index=False)

        provider = CSVFileProvider(temp_cache_dir)
        result = provider.get_prices(
            symbols=["AAPL", "MSFT"],
            start_date=date(2020, 1, 1),
            end_date=date(2020, 1, 10),
        )

        assert len(result) == 10
        assert sorted(result["symbol"].unique().tolist()) == ["AAPL", "MSFT"]

    def test_missing_file_raises_error(self, temp_cache_dir):
        """Should raise error for missing CSV file."""
        provider = CSVFileProvider(temp_cache_dir)

        with pytest.raises(PTDataError) as exc_info:
            provider.get_prices(
                symbols=["NONEXISTENT"],
                start_date=date(2020, 1, 1),
                end_date=date(2020, 1, 10),
            )

        # Should raise InsufficientDataError when no data found
        assert "No data available" in str(exc_info.value)

    def test_date_filtering(self, temp_cache_dir):
        """Should filter by date range."""
        csv_path = temp_cache_dir / "AAPL.csv"
        df = pd.DataFrame({
            "symbol": ["AAPL"] * 10,
            "date": pd.date_range("2020-01-01", periods=10),
            "open": [100.0] * 10,
            "high": [101.0] * 10,
            "low": [99.0] * 10,
            "close": [100.5] * 10,
            "adj_close": [100.5] * 10,
            "volume": [1000000] * 10,
        })
        df.to_csv(csv_path, index=False)

        provider = CSVFileProvider(temp_cache_dir)
        result = provider.get_prices(
            symbols=["AAPL"],
            start_date=date(2020, 1, 3),
            end_date=date(2020, 1, 7),
        )

        assert len(result) == 5

    def test_empty_result_for_out_of_range(self, temp_cache_dir):
        """Should raise InsufficientDataError for dates outside file range."""
        csv_path = temp_cache_dir / "AAPL.csv"
        df = pd.DataFrame({
            "symbol": ["AAPL"] * 5,
            "date": pd.date_range("2020-01-01", periods=5),
            "open": [100.0] * 5,
            "high": [101.0] * 5,
            "low": [99.0] * 5,
            "close": [100.5] * 5,
            "adj_close": [100.5] * 5,
            "volume": [1000000] * 5,
        })
        df.to_csv(csv_path, index=False)

        provider = CSVFileProvider(temp_cache_dir)

        with pytest.raises(PTDataError):
            provider.get_prices(
                symbols=["AAPL"],
                start_date=date(2021, 1, 1),
                end_date=date(2021, 1, 10),
            )


class TestMassiveAPIProvider:
    """Test MassiveAPIProvider functionality."""

    def test_requires_api_key(self):
        """Should raise error if no API key provided."""
        with patch.dict("os.environ", {}, clear=True):
            # Remove MASSIVE_API_KEY from environment
            import os
            original = os.environ.pop("MASSIVE_API_KEY", None)

            try:
                with pytest.raises(PTDataError) as exc_info:
                    MassiveAPIProvider()
                assert "MASSIVE_API_KEY" in str(exc_info.value)
            finally:
                if original is not None:
                    os.environ["MASSIVE_API_KEY"] = original

    def test_name_property(self):
        """Should have correct name property."""
        with patch.dict("os.environ", {"MASSIVE_API_KEY": "test_key"}):
            provider = MassiveAPIProvider()
            assert provider.name == "massive"

    @patch("httpx.Client.get")
    def test_get_prices_makes_api_call(self, mock_get):
        """Should make API call for each symbol."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "results": [
                {
                    "t": 1577836800000,  # 2020-01-01
                    "o": 100.0,
                    "h": 101.0,
                    "l": 99.0,
                    "c": 100.5,
                    "v": 1000000,
                }
            ],
            "next_url": None,
        }
        mock_get.return_value = mock_response

        with patch.dict("os.environ", {"MASSIVE_API_KEY": "test_key"}):
            provider = MassiveAPIProvider()
            result = provider.get_prices(
                symbols=["AAPL"],
                start_date=date(2020, 1, 1),
                end_date=date(2020, 1, 10),
            )

            assert mock_get.called
