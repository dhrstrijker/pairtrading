"""Shared pytest fixtures for pairtrading-data tests."""

import sys
import tempfile
from datetime import date
from decimal import Decimal
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

# Add tests directory to path for fixture imports
sys.path.insert(0, str(Path(__file__).parent))

from ptdata.core.types import CorporateAction, CorporateActionType, PriceBar


@pytest.fixture
def sample_price_bar() -> PriceBar:
    """A single price bar for testing."""
    return PriceBar(
        symbol="AAPL",
        date=date(2020, 6, 15),
        open=Decimal("100.00"),
        high=Decimal("102.50"),
        low=Decimal("99.00"),
        close=Decimal("101.25"),
        adj_close=Decimal("100.50"),
        volume=1000000,
    )


@pytest.fixture
def sample_prices() -> pd.DataFrame:
    """Sample price data for testing (one year of daily data)."""
    np.random.seed(42)
    n_days = 252
    start_date = date(2020, 1, 1)

    dates = pd.bdate_range(start=start_date, periods=n_days)

    # Generate random walk prices
    returns = np.random.normal(0.0005, 0.02, n_days)
    prices = 100 * np.exp(np.cumsum(returns))

    df = pd.DataFrame({
        "symbol": "AAPL",
        "date": dates,
        "open": prices * (1 + np.random.uniform(-0.01, 0.01, n_days)),
        "high": prices * (1 + np.random.uniform(0.005, 0.02, n_days)),
        "low": prices * (1 + np.random.uniform(-0.02, -0.005, n_days)),
        "close": prices,
        "adj_close": prices,  # No adjustment for simple test
        "volume": np.random.randint(100000, 10000000, n_days),
    })

    return df


@pytest.fixture
def sample_multi_symbol_prices() -> pd.DataFrame:
    """Sample price data for multiple symbols."""
    np.random.seed(42)
    n_days = 252
    symbols = ["AAPL", "MSFT", "GOOGL"]
    start_date = date(2020, 1, 1)

    dates = pd.bdate_range(start=start_date, periods=n_days)

    all_data = []
    for i, symbol in enumerate(symbols):
        np.random.seed(42 + i)
        returns = np.random.normal(0.0005, 0.02, n_days)
        prices = (100 + i * 50) * np.exp(np.cumsum(returns))

        df = pd.DataFrame({
            "symbol": symbol,
            "date": dates,
            "open": prices * (1 + np.random.uniform(-0.01, 0.01, n_days)),
            "high": prices * (1 + np.random.uniform(0.005, 0.02, n_days)),
            "low": prices * (1 + np.random.uniform(-0.02, -0.005, n_days)),
            "close": prices,
            "adj_close": prices,
            "volume": np.random.randint(100000, 10000000, n_days),
        })
        all_data.append(df)

    return pd.concat(all_data, ignore_index=True)


@pytest.fixture
def sample_split() -> CorporateAction:
    """A sample stock split corporate action."""
    return CorporateAction(
        symbol="AAPL",
        date=date(2020, 8, 31),
        action_type=CorporateActionType.SPLIT,
        value=Decimal("4.0"),  # 4-for-1 split
    )


@pytest.fixture
def temp_cache_dir():
    """Temporary directory for cache testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def data_with_split() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Price data with a stock split for testing adjustment handling."""
    from fixtures.generators import generate_with_stock_split
    return generate_with_stock_split()


@pytest.fixture
def data_with_delisting() -> pd.DataFrame:
    """Price data for a stock that gets delisted."""
    from fixtures.generators import generate_delisting
    return generate_delisting()


@pytest.fixture
def data_with_gaps() -> pd.DataFrame:
    """Price data with missing days."""
    from fixtures.generators import generate_with_missing_days
    return generate_with_missing_days()


@pytest.fixture
def data_with_long_gap() -> pd.DataFrame:
    """Price data with a long gap (>5 days)."""
    from fixtures.generators import generate_with_missing_days
    return generate_with_missing_days(missing_indices=list(range(100, 110)))


@pytest.fixture
def correlated_not_cointegrated() -> tuple[pd.Series, pd.Series]:
    """Two series that are correlated but NOT cointegrated."""
    from fixtures.generators import generate_correlated_not_cointegrated
    return generate_correlated_not_cointegrated()


@pytest.fixture
def different_calendar_data() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Price data from markets with different holiday calendars."""
    from fixtures.generators import generate_different_calendars
    return generate_different_calendars()
