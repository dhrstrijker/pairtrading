"""CSV file data provider.

Load market data from local CSV files. Useful for:
- Using pre-downloaded data
- Testing with known data files
- Working with data from other sources
"""

from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd

from ptdata.core.constants import PRICE_COLUMNS
from ptdata.core.exceptions import InsufficientDataError, PTDataError


class CSVFileProvider:
    """Load market data from local CSV files.

    Supports two directory structures:

    1. Single file per symbol:
       data_dir/
       ├── AAPL.csv
       ├── MSFT.csv
       └── GOOGL.csv

    2. Combined file with all symbols:
       data_dir/
       └── prices.csv  (with 'symbol' column)

    CSV files must have columns: symbol, date, open, high, low, close, adj_close, volume
    Or for single-symbol files: date, open, high, low, close, adj_close, volume

    Example:
        provider = CSVFileProvider("./data/prices")
        prices = provider.get_prices(
            symbols=["AAPL", "MSFT"],
            start_date=date(2020, 1, 1),
            end_date=date(2020, 12, 31)
        )
    """

    def __init__(
        self,
        data_dir: str | Path,
        date_column: str = "date",
        date_format: str | None = None,
    ) -> None:
        """Initialize CSV file provider.

        Args:
            data_dir: Directory containing CSV files
            date_column: Name of the date column in CSV files
            date_format: Date format string (e.g., "%Y-%m-%d"). If None, pandas infers.
        """
        self.data_dir = Path(data_dir)
        self.date_column = date_column
        self.date_format = date_format

        if not self.data_dir.exists():
            raise PTDataError(f"Data directory not found: {self.data_dir}")

    @property
    def name(self) -> str:
        """Provider identifier."""
        return "csv_file"

    def get_prices(
        self,
        symbols: list[str],
        start_date: date,
        end_date: date,
        adjusted: bool = True,
    ) -> pd.DataFrame:
        """Load OHLCV prices from CSV files.

        Args:
            symbols: List of ticker symbols
            start_date: Start date (inclusive)
            end_date: End date (inclusive)
            adjusted: Whether to use adjusted prices (has no effect, CSV
                     should already contain the desired adj_close values)

        Returns:
            DataFrame with OHLCV data

        Raises:
            InsufficientDataError: If no data available
        """
        if not symbols:
            raise InsufficientDataError("No symbols provided")

        all_data: list[pd.DataFrame] = []

        # Check for combined prices file first
        combined_file = self.data_dir / "prices.csv"
        if combined_file.exists():
            df = self._load_combined_file(combined_file, symbols, start_date, end_date)
            if not df.empty:
                return df

        # Otherwise, load individual symbol files
        for symbol in symbols:
            try:
                df = self._load_symbol_file(symbol, start_date, end_date)
                if not df.empty:
                    all_data.append(df)
            except FileNotFoundError:
                # Symbol file doesn't exist - skip
                continue

        if not all_data:
            raise InsufficientDataError(
                f"No data available for any symbols in range {start_date} to {end_date}"
            )

        result = pd.concat(all_data, ignore_index=True)
        return result.sort_values(["symbol", "date"]).reset_index(drop=True)

    def _load_symbol_file(
        self,
        symbol: str,
        start_date: date,
        end_date: date,
    ) -> pd.DataFrame:
        """Load data from a single-symbol CSV file.

        Looks for files named: {symbol}.csv or {symbol.lower()}.csv
        """
        # Try different file name patterns
        possible_files = [
            self.data_dir / f"{symbol}.csv",
            self.data_dir / f"{symbol.lower()}.csv",
            self.data_dir / f"{symbol.upper()}.csv",
        ]

        file_path: Path | None = None
        for path in possible_files:
            if path.exists():
                file_path = path
                break

        if file_path is None:
            raise FileNotFoundError(f"No CSV file found for symbol: {symbol}")

        df = pd.read_csv(file_path)
        df = self._parse_and_filter(df, start_date, end_date)

        # Add symbol column if not present
        if "symbol" not in df.columns:
            df["symbol"] = symbol

        return df

    def _load_combined_file(
        self,
        file_path: Path,
        symbols: list[str],
        start_date: date,
        end_date: date,
    ) -> pd.DataFrame:
        """Load data from a combined CSV file containing all symbols."""
        df = pd.read_csv(file_path)

        if "symbol" not in df.columns:
            raise PTDataError("Combined CSV file must have a 'symbol' column")

        # Filter to requested symbols (case-insensitive)
        symbols_upper = {s.upper() for s in symbols}
        df = df[df["symbol"].str.upper().isin(symbols_upper)]

        return self._parse_and_filter(df, start_date, end_date)

    def _parse_and_filter(
        self,
        df: pd.DataFrame,
        start_date: date,
        end_date: date,
    ) -> pd.DataFrame:
        """Parse dates and filter to date range.

        Args:
            df: Raw DataFrame from CSV
            start_date: Start date (inclusive)
            end_date: End date (inclusive)

        Returns:
            Filtered DataFrame with standardized columns
        """
        if df.empty:
            return pd.DataFrame(columns=PRICE_COLUMNS)

        # Parse date column
        if self.date_format:
            df[self.date_column] = pd.to_datetime(df[self.date_column], format=self.date_format)
        else:
            df[self.date_column] = pd.to_datetime(df[self.date_column])

        # Convert to date objects for comparison
        df["date"] = df[self.date_column].dt.date

        # Filter to date range
        mask = (df["date"] >= start_date) & (df["date"] <= end_date)
        df = df[mask].copy()

        if df.empty:
            return pd.DataFrame(columns=PRICE_COLUMNS)

        # Ensure required columns exist with correct types
        required_cols = ["open", "high", "low", "close", "volume"]
        for col in required_cols:
            if col not in df.columns:
                raise PTDataError(f"CSV file missing required column: {col}")

        # Handle adj_close (use close if not present)
        if "adj_close" not in df.columns:
            df["adj_close"] = df["close"]

        # Select and rename columns
        df = df[["symbol", "date", "open", "high", "low", "close", "adj_close", "volume"]].copy()

        # Ensure correct types
        for col in ["open", "high", "low", "close", "adj_close"]:
            df[col] = df[col].astype(float)
        df["volume"] = df["volume"].astype(int)

        return df
