"""Look-ahead bias prevention.

This module provides tools to prevent look-ahead bias in backtesting.
The PointInTimeDataFrame wrapper ensures that code can only access
data that would have been available at the reference date.
"""

from datetime import date

import pandas as pd

from ptdata.core.exceptions import LookAheadBiasError


class PointInTimeDataFrame:
    """DataFrame wrapper that prevents look-ahead bias.

    Only allows access to data that would have been available at the
    reference date. Raises LookAheadBiasError if future data is accessed.

    This is critical for backtesting to ensure that signals are generated
    only using information that would have been available at the time.

    Example:
        prices = cache.get_prices(["AAPL"], date(2020, 1, 1), date(2020, 12, 31))

        # Create wrapper with reference date
        pit = PointInTimeDataFrame(prices, date(2020, 6, 15))

        # Only returns data up to 2020-06-15
        data = pit.get_data()
        assert data["date"].max() <= date(2020, 6, 15)

        # Move forward in time
        pit = pit.advance_to(date(2020, 6, 30))

        # Cannot move backward - raises LookAheadBiasError
        pit.advance_to(date(2020, 6, 1))  # Raises!

    Attributes:
        reference_date: The current point in time (data after this is hidden)
    """

    def __init__(
        self,
        df: pd.DataFrame,
        reference_date: date,
        date_column: str = "date",
    ) -> None:
        """Initialize PointInTimeDataFrame.

        Args:
            df: The underlying DataFrame with market data
            reference_date: The reference date (only data up to this date is visible)
            date_column: Name of the date column in the DataFrame

        Raises:
            ValueError: If date column is not found
        """
        if date_column not in df.columns:
            raise ValueError(f"Date column '{date_column}' not found in DataFrame")

        self._df = df.copy()
        self._reference_date = reference_date
        self._date_column = date_column

        # Ensure date column is in proper format
        self._ensure_date_format()

    def _ensure_date_format(self) -> None:
        """Ensure date column contains date objects."""
        if self._df.empty:
            return

        # Convert to datetime if needed, then to date
        if not pd.api.types.is_datetime64_any_dtype(self._df[self._date_column]):
            self._df[self._date_column] = pd.to_datetime(self._df[self._date_column])

        # Convert to date objects for comparison
        if hasattr(self._df[self._date_column].iloc[0], "date"):
            # It's a Timestamp, convert to date
            pass  # We'll handle this in get_data
        elif isinstance(self._df[self._date_column].iloc[0], date):
            # Already date objects
            pass

    @property
    def reference_date(self) -> date:
        """The current point in time."""
        return self._reference_date

    def get_data(self) -> pd.DataFrame:
        """Get data available as of the reference date.

        Returns:
            DataFrame with only data up to and including reference_date
        """
        if self._df.empty:
            return self._df.copy()

        # Create date comparison
        dates = pd.to_datetime(self._df[self._date_column])
        ref_datetime = pd.Timestamp(self._reference_date)

        mask = dates <= ref_datetime
        return self._df[mask].copy()

    def get_latest(self, symbol: str | None = None) -> pd.Series | None:
        """Get the most recent data point as of reference date.

        Args:
            symbol: If provided, get latest for this symbol only

        Returns:
            Series with the latest data, or None if no data available
        """
        data = self.get_data()

        if data.empty:
            return None

        if symbol is not None:
            data = data[data["symbol"] == symbol.upper()]
            if data.empty:
                return None

        # Sort by date and get last row
        data = data.sort_values(self._date_column)
        return data.iloc[-1]

    def advance_to(self, new_date: date) -> "PointInTimeDataFrame":
        """Move the reference date forward.

        Creates a new PointInTimeDataFrame with the updated reference date.
        Cannot move backward in time (would allow look-ahead).

        Args:
            new_date: The new reference date (must be >= current reference_date)

        Returns:
            New PointInTimeDataFrame with updated reference date

        Raises:
            LookAheadBiasError: If trying to move backward in time
        """
        if new_date < self._reference_date:
            raise LookAheadBiasError(
                "Cannot move reference date backward",
                access_date=self._reference_date,
                data_date=new_date,
            )

        return PointInTimeDataFrame(
            self._df,
            new_date,
            self._date_column,
        )

    def slice(self, start_date: date, end_date: date | None = None) -> pd.DataFrame:
        """Get data for a date range (up to reference date).

        Args:
            start_date: Start of the range
            end_date: End of the range (defaults to reference_date)

        Returns:
            DataFrame with data in the range [start_date, min(end_date, reference_date)]

        Raises:
            LookAheadBiasError: If end_date is after reference_date
        """
        if end_date is None:
            end_date = self._reference_date
        elif end_date > self._reference_date:
            raise LookAheadBiasError(
                "Cannot access data after reference date",
                access_date=self._reference_date,
                data_date=end_date,
            )

        data = self.get_data()

        if data.empty:
            return data

        dates = pd.to_datetime(data[self._date_column])
        mask = (dates >= pd.Timestamp(start_date)) & (dates <= pd.Timestamp(end_date))

        return data[mask].copy()

    def __len__(self) -> int:
        """Number of rows visible as of reference date."""
        return len(self.get_data())

    def __repr__(self) -> str:
        """String representation."""
        return (
            f"PointInTimeDataFrame("
            f"reference_date={self._reference_date}, "
            f"visible_rows={len(self)})"
        )

    @property
    def symbols(self) -> list[str]:
        """Get list of symbols in the data."""
        if "symbol" not in self._df.columns:
            return []
        return sorted(self._df["symbol"].unique().tolist())

    def for_symbol(self, symbol: str) -> pd.DataFrame:
        """Get data for a specific symbol.

        Args:
            symbol: Ticker symbol

        Returns:
            DataFrame with data for the symbol (up to reference date)
        """
        data = self.get_data()
        if "symbol" not in data.columns:
            return data
        return data[data["symbol"] == symbol.upper()].copy()
