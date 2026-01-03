"""Data validation and bias prevention."""

from ptdata.validation.lookahead import PointInTimeDataFrame
from ptdata.validation.quality import (
    check_price_sanity,
    check_adjusted_prices,
    validate_dataframe,
)
from ptdata.validation.gaps import (
    MissingDataStrategy,
    find_gaps,
    handle_missing_data,
    align_dates,
)

__all__ = [
    # Look-ahead bias prevention
    "PointInTimeDataFrame",
    # Data quality checks
    "check_price_sanity",
    "check_adjusted_prices",
    "validate_dataframe",
    # Missing data handling
    "MissingDataStrategy",
    "find_gaps",
    "handle_missing_data",
    "align_dates",
]
