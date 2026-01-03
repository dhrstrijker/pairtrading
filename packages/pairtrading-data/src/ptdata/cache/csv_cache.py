"""CSV file cache for market data.

Caches data fetched from providers to local CSV files to avoid
repeated downloads. Uses a simple invalidation strategy:

V1 (Simple): If the requested range is not fully covered by the cache,
delete the cache and re-download everything for that symbol.

Future V2: Could implement delta downloads (download only missing ranges).
"""

import re
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd

from ptdata.cache.metadata import CacheMetadata
from ptdata.core.constants import DEFAULT_CACHE_EXPIRY_DAYS, PRICE_COLUMNS
from ptdata.core.exceptions import InsufficientDataError
from ptdata.providers.base import DataProvider


class CSVCache:
    """CSV file cache for market data.

    Wraps a DataProvider and caches fetched data to CSV files.
    Subsequent requests for the same data are served from cache.

    Directory structure:
        cache_dir/
        ├── AAPL.csv
        ├── MSFT.csv
        └── _metadata.json

    Cache invalidation (V1 - Simple):
    - If requested range not fully covered by cached range, re-download all
    - No partial updates or appending
    - This is simpler and avoids gap/alignment issues

    Example:
        provider = MassiveAPIProvider()
        cache = CSVCache("./data/cache", provider)

        # First call downloads and caches
        prices = cache.get_prices(["AAPL"], date(2020, 1, 1), date(2020, 12, 31))

        # Second call loads from cache (no API call)
        prices = cache.get_prices(["AAPL"], date(2020, 1, 1), date(2020, 6, 30))

    Attributes:
        cache_dir: Path to cache directory
        provider: Underlying data provider
        expiry_days: Days until cache expires (0 = never)
    """

    def __init__(
        self,
        cache_dir: str | Path,
        provider: DataProvider,
        expiry_days: int = DEFAULT_CACHE_EXPIRY_DAYS,
    ) -> None:
        """Initialize CSV cache.

        Args:
            cache_dir: Directory to store cached CSV files
            provider: Data provider to fetch data from
            expiry_days: Days until cache expires. 0 means never expire.
        """
        self.cache_dir = Path(cache_dir)
        self.provider = provider
        self.expiry_days = expiry_days

        # Create cache directory if needed
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # Load metadata
        self._metadata = CacheMetadata.load(self.cache_dir)

    def get_prices(
        self,
        symbols: list[str],
        start_date: date,
        end_date: date,
        adjusted: bool = True,
    ) -> pd.DataFrame:
        """Get prices, using cache when available.

        For each symbol:
        1. Check if cache exists and fully covers [start_date, end_date]
        2. If yes, load from cache
        3. If no, download from provider and overwrite cache

        Args:
            symbols: List of ticker symbols
            start_date: Start date (inclusive)
            end_date: End date (inclusive)
            adjusted: Whether to return adjusted prices

        Returns:
            DataFrame with OHLCV data

        Raises:
            InsufficientDataError: If no data available
        """
        if not symbols:
            raise InsufficientDataError("No symbols provided")

        all_data: list[pd.DataFrame] = []
        symbols_to_fetch: list[str] = []

        # Check which symbols need fetching
        for symbol in symbols:
            symbol_upper = symbol.upper()

            if self._is_cache_valid(symbol_upper, start_date, end_date):
                # Load from cache
                df = self._load_from_cache(symbol_upper, start_date, end_date)
                if not df.empty:
                    all_data.append(df)
                else:
                    # Cache file exists but empty - refetch
                    symbols_to_fetch.append(symbol_upper)
            else:
                symbols_to_fetch.append(symbol_upper)

        # Fetch missing symbols from provider
        if symbols_to_fetch:
            fetched = self._fetch_and_cache(
                symbols_to_fetch, start_date, end_date, adjusted
            )
            if not fetched.empty:
                all_data.append(fetched)

        if not all_data:
            raise InsufficientDataError(
                f"No data available for any symbols in range {start_date} to {end_date}"
            )

        result = pd.concat(all_data, ignore_index=True)
        return result.sort_values(["symbol", "date"]).reset_index(drop=True)

    def _is_cache_valid(self, symbol: str, start_date: date, end_date: date) -> bool:
        """Check if cache fully covers the requested date range.

        Args:
            symbol: Ticker symbol (uppercase)
            start_date: Requested start date
            end_date: Requested end date

        Returns:
            True if cache is valid and covers the range
        """
        # Check metadata
        if not self._metadata.is_valid(symbol, start_date, end_date, self.expiry_days):
            return False

        # Check if file exists
        cache_file = self._get_cache_path(symbol)
        return cache_file.exists()

    # Valid ticker symbol pattern: letters, digits, dots, hyphens (e.g., BRK.A, BRK-B)
    _VALID_SYMBOL_PATTERN = re.compile(r"^[A-Z0-9][A-Z0-9.\-]{0,9}$")

    def _validate_symbol(self, symbol: str) -> None:
        """Validate that a symbol is safe to use in file paths.

        Prevents path traversal attacks by ensuring symbols only contain
        valid ticker characters.

        Args:
            symbol: Ticker symbol to validate

        Raises:
            ValueError: If symbol contains invalid characters
        """
        if not self._VALID_SYMBOL_PATTERN.match(symbol):
            raise ValueError(
                f"Invalid symbol '{symbol}': must be 1-10 characters, "
                "containing only letters, digits, dots, or hyphens"
            )

    def _get_cache_path(self, symbol: str) -> Path:
        """Get the cache file path for a symbol.

        Args:
            symbol: Ticker symbol (uppercase)

        Returns:
            Path to the cache CSV file

        Raises:
            ValueError: If symbol contains invalid characters
        """
        self._validate_symbol(symbol)
        cache_path = self.cache_dir / f"{symbol}.csv"

        # Additional safety check: ensure path stays within cache directory
        try:
            cache_path.resolve().relative_to(self.cache_dir.resolve())
        except ValueError as err:
            raise ValueError(
                f"Invalid symbol '{symbol}': path traversal detected"
            ) from err

        return cache_path

    def _load_from_cache(
        self,
        symbol: str,
        start_date: date,
        end_date: date,
    ) -> pd.DataFrame:
        """Load data from cache file.

        Args:
            symbol: Ticker symbol (uppercase)
            start_date: Start date filter
            end_date: End date filter

        Returns:
            DataFrame with data in the requested range
        """
        cache_file = self._get_cache_path(symbol)

        if not cache_file.exists():
            return pd.DataFrame(columns=PRICE_COLUMNS)

        try:
            df = pd.read_csv(cache_file)
            df["date"] = pd.to_datetime(df["date"]).dt.date

            # Filter to requested range
            mask = (df["date"] >= start_date) & (df["date"] <= end_date)
            return df[mask].copy()

        except Exception:
            # Corrupted file - will trigger refetch
            return pd.DataFrame(columns=PRICE_COLUMNS)

    def _fetch_and_cache(
        self,
        symbols: list[str],
        start_date: date,
        end_date: date,
        adjusted: bool,
    ) -> pd.DataFrame:
        """Fetch data from provider and cache it.

        Args:
            symbols: List of symbols to fetch
            start_date: Start date
            end_date: End date
            adjusted: Whether to fetch adjusted prices

        Returns:
            DataFrame with fetched data
        """
        try:
            df = self.provider.get_prices(symbols, start_date, end_date, adjusted)
        except InsufficientDataError:
            return pd.DataFrame(columns=PRICE_COLUMNS)

        if df.empty:
            return df

        # Cache each symbol separately
        for symbol in df["symbol"].unique():
            symbol_df = df[df["symbol"] == symbol].copy()
            self._save_to_cache(symbol, symbol_df, start_date, end_date)

        return df

    def _save_to_cache(
        self,
        symbol: str,
        df: pd.DataFrame,
        start_date: date,
        end_date: date,
    ) -> None:
        """Save data to cache file.

        Args:
            symbol: Ticker symbol
            df: DataFrame to cache
            start_date: Start of cached range
            end_date: End of cached range
        """
        cache_file = self._get_cache_path(symbol.upper())

        # Save to CSV
        df.to_csv(cache_file, index=False)

        # Update metadata
        self._metadata.set(symbol.upper(), start_date, end_date, len(df))
        self._metadata.save()

    def clear_cache(self, symbols: list[str] | None = None) -> None:
        """Clear cached data.

        Args:
            symbols: Specific symbols to clear, or None for all
        """
        if symbols is None:
            # Clear all cache files
            for csv_file in self.cache_dir.glob("*.csv"):
                csv_file.unlink()
            self._metadata.clear()
        else:
            # Clear specific symbols
            for symbol in symbols:
                symbol_upper = symbol.upper()
                cache_file = self._get_cache_path(symbol_upper)
                if cache_file.exists():
                    cache_file.unlink()
                self._metadata.remove(symbol_upper)
            self._metadata.save()

    def get_cached_symbols(self) -> list[str]:
        """Get list of cached symbols.

        Returns:
            List of symbol names that are currently cached
        """
        return list(self._metadata.symbols.keys())

    def get_cache_info(self, symbol: str) -> dict[str, Any] | None:
        """Get cache info for a symbol.

        Args:
            symbol: Ticker symbol

        Returns:
            Dict with cache info, or None if not cached
        """
        info = self._metadata.get(symbol)
        if info is None:
            return None
        return info.to_dict()
