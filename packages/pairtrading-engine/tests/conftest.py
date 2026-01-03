"""Shared test fixtures for pairtrading-engine tests."""

from datetime import date

import numpy as np
import pandas as pd
import pytest
from ptdata.validation import PointInTimeDataFrame

from ptengine.backtest.config import BacktestConfig
from ptengine.core.types import PairSignal, Side, SignalType, Trade
from ptengine.portfolio.portfolio import Portfolio


@pytest.fixture
def sample_prices() -> pd.DataFrame:
    """Generate sample price data for two symbols."""
    np.random.seed(42)
    dates = pd.date_range(start="2020-01-01", end="2020-12-31", freq="B")

    data = []
    aapl_price = 100.0
    msft_price = 150.0

    for d in dates:
        # Random walk
        aapl_price *= 1 + np.random.normal(0.0005, 0.02)
        msft_price *= 1 + np.random.normal(0.0003, 0.018)

        for symbol, price in [("AAPL", aapl_price), ("MSFT", msft_price)]:
            data.append({
                "symbol": symbol,
                "date": d.date(),
                "open": price * (1 + np.random.uniform(-0.01, 0.01)),
                "high": price * (1 + np.random.uniform(0, 0.02)),
                "low": price * (1 - np.random.uniform(0, 0.02)),
                "close": price,
                "adj_close": price,
                "volume": int(np.random.uniform(1e6, 1e7)),
            })

    return pd.DataFrame(data)


@pytest.fixture
def pit_data(sample_prices: pd.DataFrame) -> PointInTimeDataFrame:
    """Create PointInTimeDataFrame from sample prices.

    Sets reference_date to before the backtest start_date (2020-03-01)
    to allow the runner to advance through the backtest period.
    """
    return PointInTimeDataFrame(sample_prices, reference_date=date(2020, 1, 1))


@pytest.fixture
def empty_portfolio() -> Portfolio:
    """Create an empty portfolio with default capital."""
    return Portfolio(initial_capital=100_000.0)


@pytest.fixture
def portfolio_with_position() -> Portfolio:
    """Create a portfolio with one position."""
    portfolio = Portfolio(initial_capital=100_000.0)
    trade = Trade(
        date=date(2020, 1, 15),
        symbol="AAPL",
        side=Side.LONG,
        shares=100,
        price=100.0,
        commission=1.0,
    )
    portfolio.execute_trade(trade)
    return portfolio


@pytest.fixture
def backtest_config() -> BacktestConfig:
    """Create a basic backtest configuration."""
    return BacktestConfig(
        start_date=date(2020, 3, 1),
        end_date=date(2020, 12, 31),
        initial_capital=100_000.0,
        capital_per_pair=10_000.0,
    )


@pytest.fixture
def sample_pair_signal() -> PairSignal:
    """Create a sample pair signal."""
    return PairSignal(
        signal_type=SignalType.OPEN_PAIR,
        long_symbol="AAPL",
        short_symbol="MSFT",
        hedge_ratio=1.0,
    )
