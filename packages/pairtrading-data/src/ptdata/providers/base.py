"""Base protocol for data providers.

This module defines the interface that all data providers must implement.
Using a Protocol allows for dependency injection and easy testing.
"""

from datetime import date
from typing import Protocol, runtime_checkable

import pandas as pd


@runtime_checkable
class DataProvider(Protocol):
    """Protocol for data providers.

    All data providers must implement this interface. This enables:
    - Dependency injection (swap providers without changing code)
    - Easy testing with mock providers
    - Consistent API across different data sources

    Example:
        class MyProvider:
            @property
            def name(self) -> str:
                return "my_provider"

            def get_prices(
                self,
                symbols: list[str],
                start_date: date,
                end_date: date,
                adjusted: bool = True
            ) -> pd.DataFrame:
                # Fetch and return data
                ...

        # MyProvider is now a valid DataProvider
        provider: DataProvider = MyProvider()
    """

    @property
    def name(self) -> str:
        """Provider identifier.

        Returns:
            Unique string identifying this provider (e.g., "massive", "csv")
        """
        ...

    def get_prices(
        self,
        symbols: list[str],
        start_date: date,
        end_date: date,
        adjusted: bool = True,
    ) -> pd.DataFrame:
        """Fetch OHLCV price data for the specified symbols and date range.

        Args:
            symbols: List of ticker symbols to fetch
            start_date: Start date (inclusive)
            end_date: End date (inclusive)
            adjusted: Whether to return split/dividend adjusted prices
                     If True, adj_close reflects corporate actions
                     If False, adj_close equals close

        Returns:
            DataFrame with columns:
                - symbol: str - Ticker symbol
                - date: date - Trading date
                - open: float - Opening price
                - high: float - Highest price
                - low: float - Lowest price
                - close: float - Closing price
                - adj_close: float - Adjusted closing price
                - volume: int - Trading volume

            Note: DataFrame uses float for prices (not Decimal) for
            compatibility with pandas and numpy operations. Convert
            to PriceBar if exact decimal representation is needed.

        Raises:
            PTDataError: If data cannot be fetched
            InsufficientDataError: If no data available for the range
        """
        ...
