# pairtrading-engine

Backtesting engine for pair trading strategies.

## Overview

`pairtrading-engine` is the backtesting layer for a pair trading framework. It provides:

- **Strategy Protocol**: Define strategies with `on_bar()` callbacks
- **Two Signal Types**: Discrete pairs (PairSignal) and continuous weights (WeightSignal)
- **Portfolio Management**: Track positions, PnL, and equity curves
- **Execution Models**: Simple close-price fills (V1)
- **Performance Metrics**: Sharpe ratio, max drawdown, win rate, and more
- **Commission Models**: Zero, per-share, percentage, IBKR tiered

## Architecture

```
┌─────────────────────┐
│  pairtrading-data   │  ← Data layer (dependency)
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ pairtrading-engine  │  ← This library
│ (Backtest Engine)   │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  Strategy Projects  │
└─────────────────────┘
```

## Installation

```bash
# Development install
pip install -e .

# With strategy dependencies (scipy, statsmodels)
pip install -e ".[strategies]"

# With dev tools
pip install -e ".[dev]"
```

## Quick Start

```python
from datetime import date
from ptdata import CSVCache, MassiveAPIProvider, PointInTimeDataFrame
from ptengine import BacktestRunner, BacktestConfig
from ptengine.strategy import BaseStrategy
from ptengine.core.types import PairSignal, SignalType

class MyPairStrategy(BaseStrategy):
    def __init__(self, symbol_a: str, symbol_b: str):
        super().__init__()
        self.symbol_a = symbol_a
        self.symbol_b = symbol_b

    @property
    def name(self) -> str:
        return f"pair_{self.symbol_a}_{self.symbol_b}"

    def on_bar(self, current_date, pit_data):
        # Your strategy logic here
        # pit_data.get_data() returns only past data (no look-ahead bias)
        return None

# Setup data
cache = CSVCache("./data", MassiveAPIProvider())
prices = cache.get_prices(["AAPL", "MSFT"], date(2020, 1, 1), date(2023, 12, 31))
pit_data = PointInTimeDataFrame(prices, date(2020, 1, 1))

# Run backtest
strategy = MyPairStrategy("AAPL", "MSFT")
config = BacktestConfig(
    start_date=date(2020, 3, 1),
    end_date=date(2023, 12, 31),
    initial_capital=100_000,
)

result = BacktestRunner(strategy, config).run(pit_data)
print(result.summary())
```

## Signal Types

### PairSignal (Discrete Pairs)

For strategies like GGR distance or cointegration:

```python
from ptengine.core.types import PairSignal, SignalType

signal = PairSignal(
    signal_type=SignalType.OPEN_PAIR,
    long_symbol="MSFT",
    short_symbol="AAPL",
    hedge_ratio=1.2,
)
```

### WeightSignal (Continuous Weights)

For strategies like Kalman filter or PCA eigenportfolios:

```python
from ptengine.core.types import WeightSignal

signal = WeightSignal(
    weights={"AAPL": -0.3, "MSFT": 0.3},  # 30% short AAPL, 30% long MSFT
    rebalance=True,
)
```

## Requirements

- Python 3.11+
- pairtrading-data (sibling project)
- pandas >= 2.0
- numpy >= 1.24

## License

MIT
