# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Build & Test Commands

```bash
# Install packages for development
pip install -e packages/pairtrading-data[dev]
pip install -e "packages/pairtrading-engine[dev,strategies,analysis]"

# Run tests
pytest packages/pairtrading-data/tests -v
pytest packages/pairtrading-engine/tests -v

# Run a single test file
pytest packages/pairtrading-engine/tests/unit/test_portfolio.py -v

# Run a single test
pytest packages/pairtrading-engine/tests/unit/test_portfolio.py::test_function_name -v

# Lint
ruff check packages/

# Type check
mypy packages/pairtrading-data/src packages/pairtrading-engine/src
```

## Architecture

This is a Python monorepo for pair trading backtesting with two packages:

```
pairtrading-data (ptdata)     →    pairtrading-engine (ptengine)
├── providers/                      ├── strategy/
├── cache/                          ├── backtest/
├── validation/                     ├── portfolio/
└── universes/                      ├── analysis/
                                    └── strategies/
```

**pairtrading-data** handles market data: fetching from APIs (Polygon.io), caching to CSV, validation, and look-ahead bias prevention via `PointInTimeDataFrame`.

**pairtrading-engine** handles backtesting: strategy protocol, portfolio tracking, execution, commission models, performance metrics, and analysis/visualization.

## Key Patterns

### Protocol-Based Design
Both packages use Protocol classes for dependency injection:
- `DataProvider` protocol in ptdata for data sources
- `Strategy` protocol in ptengine for custom strategies
- `CommissionModel` protocol for pluggable commission calculation

### Signal Types
Strategies return one of:
- `PairSignal` - For discrete pair trades (GGR, cointegration): long_symbol + short_symbol + hedge_ratio
- `WeightSignal` - For continuous rebalancing (Kalman, PCA): dict of symbol → weight
- `None` - No action

### Look-Ahead Bias Prevention
`PointInTimeDataFrame` wraps price data and only exposes data available as of `reference_date`. It raises `LookAheadBiasError` if future data is accessed.

```python
pit_data = PointInTimeDataFrame(prices, reference_date=start_date)
pit_data.advance_to(current_date)  # Can only move forward
data = pit_data.get_data()  # Only returns historical data
```

### Frozen Dataclasses
Core types (`PriceBar`, `Trade`, `PairSignal`, `RoundTrip`) are frozen dataclasses with validation in `__post_init__`.

## Creating a Strategy

```python
from ptengine.strategy.base import BaseStrategy
from ptengine.core.types import PairSignal, SignalType

class MyStrategy(BaseStrategy):
    @property
    def name(self) -> str:
        return "my_strategy"

    def on_bar(self, current_date, pit_data) -> Signal:
        # pit_data.get_data() returns only historical data
        # Return PairSignal, WeightSignal, or None
        return PairSignal(
            signal_type=SignalType.OPEN_PAIR,
            long_symbol="AAPL",
            short_symbol="MSFT",
            hedge_ratio=1.0,
        )
```

## Running a Backtest

```python
from ptdata import MassiveAPIProvider
from ptdata.cache import CSVCache
from ptdata.validation import PointInTimeDataFrame
from ptengine import BacktestRunner, BacktestConfig, GGRDistanceStrategy
from ptengine.analysis import StrategyAnalyzer

# Load data
cache = CSVCache("./data", MassiveAPIProvider())
prices = cache.get_prices(symbols, start_date, end_date)
pit_data = PointInTimeDataFrame(prices, reference_date=start_date)

# Run backtest
result = BacktestRunner(strategy, config).run(pit_data)
print(result.summary())

# Analyze
analyzer = StrategyAnalyzer(result)
print(analyzer.full_report())
analyzer.create_tear_sheet(Path("./tearsheet.png"))
```

## Environment Variables

- `MASSIVE_API_KEY` - Polygon.io API key for market data (can be set in `.env` file at repo root)
