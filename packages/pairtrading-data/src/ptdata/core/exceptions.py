"""Custom exceptions for pairtrading-data.

Exception Hierarchy:
    PTDataError (base)
    ├── LookAheadBiasError - Future data accessed
    ├── SurvivorshipBiasError - Survivorship bias detected
    ├── InsufficientDataError - Not enough data available
    └── DataQualityError - Data quality checks failed
"""

from datetime import date
from typing import Any


class PTDataError(Exception):
    """Base exception for all pairtrading-data errors."""

    pass


class LookAheadBiasError(PTDataError):
    """Raised when future data is accessed.

    This error indicates that code is attempting to use data that
    would not have been available at the reference date, which would
    introduce look-ahead bias into backtesting results.

    Attributes:
        message: Error description
        access_date: The date from which access was attempted
        data_date: The date of the data being accessed
    """

    def __init__(self, message: str, access_date: date, data_date: date) -> None:
        self.access_date = access_date
        self.data_date = data_date
        super().__init__(f"{message}: attempted to access {data_date} data from {access_date}")


class SurvivorshipBiasError(PTDataError):
    """Raised when survivorship bias is detected.

    This error indicates that the analysis is using data that excludes
    securities that are no longer available (e.g., delisted stocks),
    which would artificially inflate performance metrics.

    Attributes:
        message: Error description
        symbol: The affected symbol (if applicable)
        details: Additional context about the bias
    """

    def __init__(self, message: str, symbol: str | None = None, details: dict[str, Any] | None = None) -> None:
        self.symbol = symbol
        self.details = details or {}
        super().__init__(f"{message}" + (f" (symbol: {symbol})" if symbol else ""))


class InsufficientDataError(PTDataError):
    """Raised when there is not enough data for the requested operation.

    Attributes:
        message: Error description
        symbol: The affected symbol (if applicable)
        required: Number of data points required
        available: Number of data points available
    """

    def __init__(
        self,
        message: str,
        symbol: str | None = None,
        required: int | None = None,
        available: int | None = None,
    ) -> None:
        self.symbol = symbol
        self.required = required
        self.available = available

        details = []
        if symbol:
            details.append(f"symbol: {symbol}")
        if required is not None and available is not None:
            details.append(f"required: {required}, available: {available}")

        detail_str = f" ({', '.join(details)})" if details else ""
        super().__init__(f"{message}{detail_str}")


class DataQualityError(PTDataError):
    """Raised when data quality checks fail.

    This error indicates that the data has issues that could affect
    the accuracy of analysis, such as:
    - Negative prices
    - High < Low
    - Extreme single-day moves
    - Inconsistent adjusted prices

    Attributes:
        message: Error description
        symbol: The affected symbol (if applicable)
        check_name: Name of the quality check that failed
        details: Additional context about the failure
    """

    def __init__(
        self,
        message: str,
        symbol: str | None = None,
        check_name: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.symbol = symbol
        self.check_name = check_name
        self.details = details or {}

        parts = [message]
        if symbol:
            parts.append(f"symbol: {symbol}")
        if check_name:
            parts.append(f"check: {check_name}")

        super().__init__(" | ".join(parts))
