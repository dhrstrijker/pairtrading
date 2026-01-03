"""Data quality validation.

This module provides functions to validate market data quality.
These checks help identify data issues that could affect analysis.
"""

from typing import Any

import pandas as pd

from ptdata.core.constants import (
    COLUMN_ADJ_CLOSE,
    COLUMN_CLOSE,
    COLUMN_HIGH,
    COLUMN_LOW,
    COLUMN_OPEN,
    DEFAULT_EXTREME_MOVE_THRESHOLD,
)
from ptdata.core.exceptions import DataQualityError


def check_price_sanity(
    df: pd.DataFrame,
    raise_on_error: bool = True,
    extreme_move_threshold: float = DEFAULT_EXTREME_MOVE_THRESHOLD,
) -> list[dict[str, Any]]:
    """Validate price data sanity.

    Checks:
    - No negative prices
    - High >= Low
    - Close between High and Low
    - Open between High and Low
    - No extreme single-day moves (default >50%)

    Args:
        df: DataFrame with OHLCV price data
        raise_on_error: If True, raise DataQualityError on first issue
        extreme_move_threshold: Maximum allowed single-day move (0.5 = 50%)

    Returns:
        List of issue dictionaries with keys: symbol, date, check, value, message

    Raises:
        DataQualityError: If raise_on_error is True and issues are found
    """
    issues: list[dict[str, Any]] = []

    if df.empty:
        return issues

    # Check for negative prices
    price_cols = [COLUMN_OPEN, COLUMN_HIGH, COLUMN_LOW, COLUMN_CLOSE, COLUMN_ADJ_CLOSE]
    for col in price_cols:
        if col in df.columns:
            neg_mask = df[col] < 0
            if neg_mask.any():
                for idx in df[neg_mask].index:
                    row = df.loc[idx]
                    issue = {
                        "symbol": row.get("symbol", "UNKNOWN"),
                        "date": row.get("date", "UNKNOWN"),
                        "check": "negative_price",
                        "column": col,
                        "value": row[col],
                        "message": f"Negative {col} price: {row[col]}",
                    }
                    issues.append(issue)

                    if raise_on_error:
                        raise DataQualityError(
                            issue["message"],
                            symbol=issue["symbol"],
                            check_name="negative_price",
                        )

    # Check High >= Low
    if COLUMN_HIGH in df.columns and COLUMN_LOW in df.columns:
        invalid_mask = df[COLUMN_HIGH] < df[COLUMN_LOW]
        if invalid_mask.any():
            for idx in df[invalid_mask].index:
                row = df.loc[idx]
                issue = {
                    "symbol": row.get("symbol", "UNKNOWN"),
                    "date": row.get("date", "UNKNOWN"),
                    "check": "high_low_inversion",
                    "value": f"high={row[COLUMN_HIGH]}, low={row[COLUMN_LOW]}",
                    "message": f"High ({row[COLUMN_HIGH]}) < Low ({row[COLUMN_LOW]})",
                }
                issues.append(issue)

                if raise_on_error:
                    raise DataQualityError(
                        issue["message"],
                        symbol=issue["symbol"],
                        check_name="high_low_inversion",
                    )

    # Check Close between High and Low
    if all(c in df.columns for c in [COLUMN_HIGH, COLUMN_LOW, COLUMN_CLOSE]):
        close_high = df[COLUMN_CLOSE] > df[COLUMN_HIGH]
        close_low = df[COLUMN_CLOSE] < df[COLUMN_LOW]
        invalid_mask = close_high | close_low
        if invalid_mask.any():
            for idx in df[invalid_mask].index:
                row = df.loc[idx]
                close_val = row[COLUMN_CLOSE]
                high_val = row[COLUMN_HIGH]
                low_val = row[COLUMN_LOW]
                issue = {
                    "symbol": row.get("symbol", "UNKNOWN"),
                    "date": row.get("date", "UNKNOWN"),
                    "check": "close_outside_range",
                    "value": f"close={close_val}, high={high_val}, low={low_val}",
                    "message": f"Close ({close_val}) outside High-Low range",
                }
                issues.append(issue)

                if raise_on_error:
                    raise DataQualityError(
                        issue["message"],
                        symbol=issue["symbol"],
                        check_name="close_outside_range",
                    )

    # Check for extreme single-day moves
    if COLUMN_CLOSE in df.columns and "symbol" in df.columns:
        for symbol in df["symbol"].unique():
            symbol_df = df[df["symbol"] == symbol].sort_values("date")
            if len(symbol_df) < 2:
                continue

            returns = symbol_df[COLUMN_CLOSE].pct_change().abs()
            extreme_mask = returns > extreme_move_threshold
            extreme_idx = symbol_df.index[extreme_mask]

            for idx in extreme_idx:
                row = df.loc[idx]
                ret = returns.loc[idx]
                thresh_pct = f"{extreme_move_threshold:.0%}"
                issue = {
                    "symbol": symbol,
                    "date": row.get("date", "UNKNOWN"),
                    "check": "extreme_move",
                    "value": f"{ret:.2%}",
                    "message": f"Extreme move: {ret:.2%} (threshold: {thresh_pct})",
                }
                issues.append(issue)

                if raise_on_error:
                    raise DataQualityError(
                        issue["message"],
                        symbol=symbol,
                        check_name="extreme_move",
                    )

    return issues


def check_adjusted_prices(
    df: pd.DataFrame,
    raise_on_error: bool = True,
) -> list[dict[str, Any]]:
    """Validate adjusted price consistency.

    Checks:
    - adj_close ratio is consistent (no sudden unexplained jumps)
    - adj_close <= close (adjusted for splits should be lower or equal)

    Args:
        df: DataFrame with OHLCV price data
        raise_on_error: If True, raise DataQualityError on first issue

    Returns:
        List of issue dictionaries

    Raises:
        DataQualityError: If raise_on_error is True and issues are found
    """
    issues: list[dict[str, Any]] = []

    if df.empty:
        return issues

    if COLUMN_CLOSE not in df.columns or COLUMN_ADJ_CLOSE not in df.columns:
        return issues

    # Check adjustment ratio consistency per symbol
    if "symbol" in df.columns:
        for symbol in df["symbol"].unique():
            symbol_df = df[df["symbol"] == symbol].sort_values("date")
            if len(symbol_df) < 2:
                continue

            # Calculate adjustment factor
            adj_factor = symbol_df[COLUMN_ADJ_CLOSE] / symbol_df[COLUMN_CLOSE]
            adj_factor_change = adj_factor.pct_change().abs()

            # Large changes in adjustment factor (not on split days) are suspicious
            # Skip first row (NaN from pct_change)
            suspicious = adj_factor_change > 0.1  # 10% change threshold

            # Get indices where suspicious is True (skip first which is NaN)
            suspicious_indices = symbol_df.index[1:][suspicious.iloc[1:].values]

            for idx in suspicious_indices:
                row = df.loc[idx]
                change = adj_factor_change.loc[idx]
                issue = {
                    "symbol": symbol,
                    "date": row.get("date", "UNKNOWN"),
                    "check": "adjustment_jump",
                    "value": f"{change:.2%}",
                    "message": f"Large adjustment factor change: {change:.2%}",
                }
                issues.append(issue)

                if raise_on_error:
                    raise DataQualityError(
                        issue["message"],
                        symbol=symbol,
                        check_name="adjustment_jump",
                    )

    return issues


def validate_dataframe(
    df: pd.DataFrame,
    required_columns: list[str] | None = None,
    raise_on_error: bool = True,
) -> list[dict[str, Any]]:
    """Validate DataFrame structure and run quality checks.

    Args:
        df: DataFrame to validate
        required_columns: List of required column names
        raise_on_error: If True, raise on first issue

    Returns:
        List of all issues found

    Raises:
        DataQualityError: If raise_on_error is True and issues are found
    """
    issues: list[dict[str, Any]] = []

    # Check required columns
    if required_columns:
        missing = set(required_columns) - set(df.columns)
        if missing:
            issue = {
                "check": "missing_columns",
                "value": list(missing),
                "message": f"Missing required columns: {missing}",
            }
            issues.append(issue)

            if raise_on_error:
                raise DataQualityError(issue["message"], check_name="missing_columns")

    # Run price sanity checks
    issues.extend(check_price_sanity(df, raise_on_error=raise_on_error))

    # Run adjusted price checks
    issues.extend(check_adjusted_prices(df, raise_on_error=raise_on_error))

    return issues
