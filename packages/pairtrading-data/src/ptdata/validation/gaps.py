"""Missing data detection and handling.

This module provides tools to identify and handle gaps in market data.
Proper handling of missing data is crucial for accurate backtesting.
"""

from enum import Enum, auto
from typing import Any

import numpy as np
import pandas as pd

from ptdata.core.constants import DEFAULT_MAX_CONSECUTIVE_MISSING
from ptdata.core.exceptions import DataQualityError


class MissingDataStrategy(Enum):
    """Strategy for handling missing data."""

    FORWARD_FILL = auto()  # Fill with last known value
    BACKWARD_FILL = auto()  # Fill with next known value
    DROP = auto()  # Drop rows with missing data
    INTERPOLATE = auto()  # Linear interpolation
    RAISE = auto()  # Raise an error


def find_gaps(
    df: pd.DataFrame,
    date_column: str = "date",
    symbol_column: str | None = "symbol",
) -> pd.DataFrame:
    """Find gaps in price data (missing trading days).

    Identifies date gaps that are longer than expected weekends/holidays.

    Args:
        df: DataFrame with date column
        date_column: Name of the date column
        symbol_column: Name of the symbol column (if per-symbol analysis)

    Returns:
        DataFrame with columns:
        - symbol (if symbol_column provided)
        - gap_start: First date of the gap
        - gap_end: Last date of the gap
        - gap_days: Number of calendar days in the gap
        - gap_trading_days: Estimated trading days missed
    """
    if df.empty:
        cols = ["symbol", "gap_start", "gap_end", "gap_days", "gap_trading_days"]
        return pd.DataFrame(columns=cols)

    gaps: list[dict[str, Any]] = []

    # Ensure date is proper format
    df = df.copy()
    df[date_column] = pd.to_datetime(df[date_column])

    if symbol_column and symbol_column in df.columns:
        # Analyze per symbol
        for symbol in df[symbol_column].unique():
            symbol_df = df[df[symbol_column] == symbol].sort_values(date_column)
            symbol_gaps = _find_gaps_in_series(symbol_df[date_column])
            for gap in symbol_gaps:
                gap["symbol"] = symbol
                gaps.append(gap)
    else:
        # Analyze entire dataset
        df_sorted = df.sort_values(date_column)
        gaps = _find_gaps_in_series(df_sorted[date_column])

    return pd.DataFrame(gaps)


def _find_gaps_in_series(dates: pd.Series) -> list[dict[str, Any]]:
    """Find gaps in a sorted date series.

    A gap is defined as more than 3 calendar days between trading days
    (to account for weekends).

    Args:
        dates: Sorted pandas Series of dates

    Returns:
        List of gap dictionaries
    """
    gaps = []

    if len(dates) < 2:
        return gaps

    dates = dates.reset_index(drop=True)

    for i in range(1, len(dates)):
        prev_date = dates.iloc[i - 1]
        curr_date = dates.iloc[i]

        # Calculate calendar days between
        delta = (curr_date - prev_date).days

        # More than 3 days suggests a gap (weekend is max 2 days)
        # Adjust threshold for holidays (up to 4-5 days for long weekends)
        if delta > 5:
            # Estimate trading days missed (roughly 5 trading days per 7 calendar days)
            trading_days_missed = int(delta * 5 / 7) - 1

            gap_start = prev_date.date() if hasattr(prev_date, "date") else prev_date
            gap_end = curr_date.date() if hasattr(curr_date, "date") else curr_date
            gaps.append({
                "gap_start": gap_start,
                "gap_end": gap_end,
                "gap_days": delta,
                "gap_trading_days": max(0, trading_days_missed),
            })

    return gaps


def handle_missing_data(
    df: pd.DataFrame,
    strategy: MissingDataStrategy,
    max_consecutive: int = DEFAULT_MAX_CONSECUTIVE_MISSING,
    columns: list[str] | None = None,
) -> pd.DataFrame:
    """Handle missing data according to the specified strategy.

    Args:
        df: DataFrame with potential missing values
        strategy: How to handle missing data
        max_consecutive: Maximum consecutive missing values allowed
                        (only for FORWARD_FILL and BACKWARD_FILL)
        columns: Specific columns to fill (default: all numeric)

    Returns:
        DataFrame with missing data handled

    Raises:
        DataQualityError: If strategy is RAISE and missing data exists,
                         or if max_consecutive is exceeded
    """
    if df.empty:
        return df.copy()

    df = df.copy()

    # Determine columns to process
    if columns is None:
        columns = df.select_dtypes(include=[np.number]).columns.tolist()

    # Check for missing data
    missing_mask = df[columns].isna()
    has_missing = missing_mask.any().any()

    if not has_missing:
        return df

    if strategy == MissingDataStrategy.RAISE:
        # Find first missing value
        for col in columns:
            if df[col].isna().any():
                first_missing_idx = df[col].isna().idxmax()
                raise DataQualityError(
                    f"Missing data found in column '{col}'",
                    check_name="missing_data",
                    details={"index": first_missing_idx},
                )

    elif strategy == MissingDataStrategy.DROP:
        df = df.dropna(subset=columns)

    elif strategy == MissingDataStrategy.FORWARD_FILL:
        # Check consecutive missing before filling
        _check_consecutive_missing(df, columns, max_consecutive)
        df[columns] = df[columns].ffill()

    elif strategy == MissingDataStrategy.BACKWARD_FILL:
        _check_consecutive_missing(df, columns, max_consecutive)
        df[columns] = df[columns].bfill()

    elif strategy == MissingDataStrategy.INTERPOLATE:
        df[columns] = df[columns].interpolate(method="linear")

    return df


def _check_consecutive_missing(
    df: pd.DataFrame,
    columns: list[str],
    max_consecutive: int,
) -> None:
    """Check if consecutive missing values exceed threshold.

    Args:
        df: DataFrame to check
        columns: Columns to check
        max_consecutive: Maximum allowed consecutive missing values

    Raises:
        DataQualityError: If threshold exceeded
    """
    for col in columns:
        if col not in df.columns:
            continue

        # Find consecutive NaN runs
        is_null = df[col].isna()
        if not is_null.any():
            continue

        # Group consecutive NaNs
        groups = is_null.ne(is_null.shift()).cumsum()
        consecutive_counts = is_null.groupby(groups).sum()

        max_found = consecutive_counts.max()
        if max_found > max_consecutive:
            raise DataQualityError(
                f"Too many consecutive missing values in '{col}': "
                f"{max_found} (max allowed: {max_consecutive})",
                check_name="consecutive_missing",
                details={"column": col, "count": max_found, "max": max_consecutive},
            )


def align_dates(
    df1: pd.DataFrame,
    df2: pd.DataFrame,
    date_column: str = "date",
    how: str = "inner",
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Align two DataFrames by date.

    Useful for comparing or combining price data from different symbols
    or sources that may have different trading calendars.

    Args:
        df1: First DataFrame
        df2: Second DataFrame
        date_column: Name of the date column
        how: Join method ('inner', 'outer', 'left', 'right')

    Returns:
        Tuple of aligned DataFrames
    """
    df1 = df1.copy()
    df2 = df2.copy()

    # Ensure date columns are datetime
    df1[date_column] = pd.to_datetime(df1[date_column])
    df2[date_column] = pd.to_datetime(df2[date_column])

    if how == "inner":
        # Keep only dates present in both
        common_dates = set(df1[date_column]) & set(df2[date_column])
        df1 = df1[df1[date_column].isin(common_dates)]
        df2 = df2[df2[date_column].isin(common_dates)]

    elif how == "outer":
        # Include all dates from both
        # This would require creating placeholder rows - more complex
        # For now, just return as is
        pass

    elif how == "left":
        # Keep all dates from df1
        df2 = df2[df2[date_column].isin(df1[date_column])]

    elif how == "right":
        # Keep all dates from df2
        df1 = df1[df1[date_column].isin(df2[date_column])]

    # Sort by date
    df1 = df1.sort_values(date_column).reset_index(drop=True)
    df2 = df2.sort_values(date_column).reset_index(drop=True)

    return df1, df2
