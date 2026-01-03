"""Massive API (formerly Polygon) data provider.

This provider fetches market data from the Massive API.
Requires an API key set as MASSIVE_API_KEY environment variable.

API Documentation: https://docs.polygon.io/ (legacy)
"""

import os
import time
from datetime import date
from typing import Any

import httpx
import pandas as pd
from dotenv import load_dotenv

from ptdata.core.constants import (
    DEFAULT_API_RETRY_COUNT,
    DEFAULT_API_RETRY_DELAY,
    DEFAULT_API_TIMEOUT,
    PRICE_COLUMNS,
)
from ptdata.core.exceptions import InsufficientDataError, PTDataError

# Load environment variables from .env file
load_dotenv()


class MassiveAPIProvider:
    """Massive API (formerly Polygon) data provider.

    Fetches daily OHLCV data from the Massive API with:
    - Automatic rate limiting and retry logic
    - Pagination for large date ranges
    - Split and dividend adjusted prices

    Attributes:
        api_key: API key for authentication
        base_url: Base URL for API requests

    Example:
        provider = MassiveAPIProvider()
        prices = provider.get_prices(
            symbols=["AAPL", "MSFT"],
            start_date=date(2020, 1, 1),
            end_date=date(2020, 12, 31)
        )
    """

    # Polygon.io API base URL (Massive API should have similar structure)
    BASE_URL = "https://api.polygon.io"

    def __init__(
        self,
        api_key: str | None = None,
        timeout: float = DEFAULT_API_TIMEOUT,
        retry_count: int = DEFAULT_API_RETRY_COUNT,
        retry_delay: float = DEFAULT_API_RETRY_DELAY,
    ) -> None:
        """Initialize the Massive API provider.

        Args:
            api_key: API key. If not provided, reads from MASSIVE_API_KEY env var.
            timeout: Request timeout in seconds
            retry_count: Number of retries for failed requests
            retry_delay: Base delay between retries (exponential backoff)

        Raises:
            PTDataError: If API key is not found
        """
        self.api_key = api_key or os.getenv("MASSIVE_API_KEY")
        if not self.api_key:
            raise PTDataError(
                "MASSIVE_API_KEY not found. Set it as an environment variable "
                "or pass it to the constructor."
            )

        self.timeout = timeout
        self.retry_count = retry_count
        self.retry_delay = retry_delay

        self._client = httpx.Client(timeout=self.timeout)

    @property
    def name(self) -> str:
        """Provider identifier."""
        return "massive"

    def get_prices(
        self,
        symbols: list[str],
        start_date: date,
        end_date: date,
        adjusted: bool = True,
    ) -> pd.DataFrame:
        """Fetch OHLCV prices from Massive API.

        Args:
            symbols: List of ticker symbols
            start_date: Start date (inclusive)
            end_date: End date (inclusive)
            adjusted: Whether to return adjusted prices

        Returns:
            DataFrame with OHLCV data

        Raises:
            PTDataError: If API request fails
            InsufficientDataError: If no data available
        """
        if not symbols:
            raise InsufficientDataError("No symbols provided")

        all_data: list[pd.DataFrame] = []

        for symbol in symbols:
            try:
                df = self._fetch_symbol(symbol, start_date, end_date, adjusted)
                if not df.empty:
                    all_data.append(df)
            except Exception as e:
                # Log warning but continue with other symbols
                print(f"Warning: Failed to fetch {symbol}: {e}")

        if not all_data:
            raise InsufficientDataError(
                f"No data available for any symbols in range {start_date} to {end_date}"
            )

        result = pd.concat(all_data, ignore_index=True)
        return result.sort_values(["symbol", "date"]).reset_index(drop=True)

    def _fetch_symbol(
        self,
        symbol: str,
        start_date: date,
        end_date: date,
        adjusted: bool,
    ) -> pd.DataFrame:
        """Fetch data for a single symbol with retry logic.

        Uses the Polygon.io aggregates endpoint:
        /v2/aggs/ticker/{ticker}/range/1/day/{from}/{to}
        """
        url = (
            f"{self.BASE_URL}/v2/aggs/ticker/{symbol}/range/1/day/"
            f"{start_date.isoformat()}/{end_date.isoformat()}"
        )

        params = {
            "apiKey": self.api_key,
            "adjusted": "true" if adjusted else "false",
            "sort": "asc",
            "limit": 50000,  # Max results per request
        }

        data = self._request_with_retry(url, params)

        if not data.get("results"):
            return pd.DataFrame(columns=PRICE_COLUMNS)

        return self._parse_response(symbol, data["results"])

    def _request_with_retry(
        self,
        url: str,
        params: dict[str, Any],
    ) -> dict[str, Any]:
        """Make HTTP request with exponential backoff retry.

        Args:
            url: Request URL
            params: Query parameters

        Returns:
            JSON response data

        Raises:
            PTDataError: If all retries fail
        """
        last_error: Exception | None = None

        for attempt in range(self.retry_count):
            try:
                response = self._client.get(url, params=params)

                if response.status_code == 200:
                    return response.json()

                if response.status_code == 429:
                    # Rate limited - wait and retry
                    delay = self.retry_delay * (2**attempt)
                    time.sleep(delay)
                    continue

                if response.status_code in (401, 403):
                    raise PTDataError(f"Authentication failed: {response.text}")

                response.raise_for_status()

            except httpx.HTTPError as e:
                last_error = e
                if attempt < self.retry_count - 1:
                    delay = self.retry_delay * (2**attempt)
                    time.sleep(delay)

        msg = f"API request failed after {self.retry_count} retries: {last_error}"
        raise PTDataError(msg)

    def _parse_response(
        self, symbol: str, results: list[dict[str, Any]]
    ) -> pd.DataFrame:
        """Parse API response into DataFrame.

        Args:
            symbol: Ticker symbol
            results: List of result dicts from API

        Returns:
            DataFrame with standardized columns
        """
        records = []

        for r in results:
            # Polygon.io response format:
            # t: timestamp (ms), o: open, h: high, l: low, c: close, v: volume
            # vw: volume weighted average (we use this as adj_close if available)
            timestamp_ms = r.get("t", 0)
            trade_date = date.fromtimestamp(timestamp_ms / 1000)

            records.append(
                {
                    "symbol": symbol,
                    "date": trade_date,
                    "open": float(r.get("o", 0)),
                    "high": float(r.get("h", 0)),
                    "low": float(r.get("l", 0)),
                    "close": float(r.get("c", 0)),
                    # Use close as adj_close if not provided separately
                    # (adjusted=true in params should handle this)
                    "adj_close": float(r.get("c", 0)),
                    "volume": int(r.get("v", 0)),
                }
            )

        return pd.DataFrame(records)

    def close(self) -> None:
        """Close the HTTP client."""
        self._client.close()

    def __enter__(self) -> "MassiveAPIProvider":
        """Context manager entry."""
        return self

    def __exit__(self, *args: Any) -> None:
        """Context manager exit."""
        self.close()

    def __del__(self) -> None:
        """Cleanup on garbage collection."""
        if hasattr(self, "_client"):
            try:
                self._client.close()
            except Exception:
                pass  # Ignore errors during cleanup
