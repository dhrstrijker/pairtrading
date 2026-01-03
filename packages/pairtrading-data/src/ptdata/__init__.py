"""
pairtrading-data: Market data collection and validation for pair trading.

This library provides:
- Data providers (Massive API / Polygon) with CSV caching
- Stock universe management (S&P 500, sectors, custom lists)
- Data validation to prevent look-ahead and survivorship bias
- Data quality checks (gaps, outliers, corporate actions)

Usage:
    from ptdata import MassiveAPIProvider, CSVCache, CustomUniverse
    from ptdata.validation import PointInTimeDataFrame

    # Create provider with caching (requires MASSIVE_API_KEY env var)
    provider = MassiveAPIProvider()
    cache = CSVCache("./data/cache", provider)

    # Get data
    universe = CustomUniverse(["AAPL", "MSFT", "GOOGL"])
    prices = cache.get_prices(
        symbols=universe.get_symbols(),
        start_date=date(2020, 1, 1),
        end_date=date(2023, 12, 31)
    )

    # Wrap for bias prevention
    pit_data = PointInTimeDataFrame(prices, reference_date=date(2020, 6, 1))
"""

__version__ = "0.1.0"

# Core types
from ptdata.core.types import PriceBar, CorporateAction, CorporateActionType
from ptdata.core.exceptions import (
    PTDataError,
    LookAheadBiasError,
    SurvivorshipBiasError,
    InsufficientDataError,
    DataQualityError,
)

# Providers
from ptdata.providers.massive import MassiveAPIProvider
from ptdata.providers.csv_file import CSVFileProvider

# Cache
from ptdata.cache.csv_cache import CSVCache

# Universes
from ptdata.universes.custom import CustomUniverse
from ptdata.universes.sectors import SectorUniverse

# Validation
from ptdata.validation.lookahead import PointInTimeDataFrame
from ptdata.validation.gaps import MissingDataStrategy, handle_missing_data

__all__ = [
    # Version
    "__version__",
    # Types
    "PriceBar",
    "CorporateAction",
    "CorporateActionType",
    # Exceptions
    "PTDataError",
    "LookAheadBiasError",
    "SurvivorshipBiasError",
    "InsufficientDataError",
    "DataQualityError",
    # Providers
    "MassiveAPIProvider",
    "CSVFileProvider",
    # Cache
    "CSVCache",
    # Universes
    "CustomUniverse",
    "SectorUniverse",
    # Validation
    "PointInTimeDataFrame",
    "MissingDataStrategy",
    "handle_missing_data",
]
