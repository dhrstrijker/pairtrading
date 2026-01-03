# Pairtrading

A Python framework for backtesting pair trading strategies.

## Overview

This monorepo contains a complete suite of tools for pair trading research and backtesting:

```
┌─────────────────────┐
│  pairtrading-data   │  Market data collection & validation
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ pairtrading-engine  │  Backtesting engine
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│     Strategies      │  GGR Distance, Cointegration, etc.
└─────────────────────┘
```

## Packages

| Package | Description | Status |
|---------|-------------|--------|
| [pairtrading-data](packages/pairtrading-data/) | Market data fetching, caching, and validation with look-ahead bias prevention | ✅ Complete |
| [pairtrading-engine](packages/pairtrading-engine/) | Backtesting engine with strategy protocol, portfolio management, and performance metrics | ✅ Complete |

## Quick Start

### Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/pairtrading.git
cd pairtrading

# Install both packages in development mode
pip install -e packages/pairtrading-data
pip install -e "packages/pairtrading-engine[dev,strategies]"
```

### Running a Backtest

```python
from datetime import date
from ptdata import MassiveAPIProvider, CSVCache, PointInTimeDataFrame
from ptengine import BacktestRunner, BacktestConfig
from ptengine.strategies import GGRDistanceStrategy

# Setup data provider
cache = CSVCache("./data/cache", MassiveAPIProvider())
symbols = ["AAPL", "MSFT", "GOOGL", "META", "AMZN"]

# Fetch data
prices = cache.get_prices(symbols, date(2020, 1, 1), date(2023, 12, 31))
pit_data = PointInTimeDataFrame(prices, date(2020, 1, 1))

# Configure strategy
strategy = GGRDistanceStrategy(
    symbols=symbols,
    formation_period=120,
    entry_threshold=2.0,
    max_holding_days=20,
)

# Run backtest
config = BacktestConfig(
    start_date=date(2020, 7, 1),
    end_date=date(2023, 12, 31),
    initial_capital=100_000,
)

result = BacktestRunner(strategy, config).run(pit_data)
print(result.summary())
```

## Features

### pairtrading-data
- **Data Providers**: Massive API (Polygon), CSV files
- **Caching**: Automatic CSV caching to avoid re-downloads
- **Universes**: S&P 500, sector-based, custom symbol lists
- **Bias Prevention**: `PointInTimeDataFrame` prevents look-ahead bias
- **Validation**: Data quality checks, gap detection, missing data handling

### pairtrading-engine
- **Strategy Protocol**: `on_bar()` callbacks with point-in-time data
- **Signal Types**: Discrete pairs (`PairSignal`) and continuous weights (`WeightSignal`)
- **Portfolio Management**: Position tracking, P&L calculation, equity curves
- **Execution**: Close-price fills with pluggable commission models
- **Metrics**: Sharpe ratio, max drawdown, win rate, profit factor

### Built-in Strategies
- **GGR Distance**: Gatev, Goetzmann, Rouwenhorst distance method with universe scanning

## Configuration

Set your Massive API key (for fetching market data):

```bash
export MASSIVE_API_KEY="your_api_key_here"
```

Or create a `.env` file:
```
MASSIVE_API_KEY=your_api_key_here
```

## Development

### Running Tests

```bash
# Test all packages
pytest packages/pairtrading-data/tests
pytest packages/pairtrading-engine/tests

# Or with coverage
pytest packages/ --cov=packages --cov-report=html
```

### Code Quality

```bash
# Linting
ruff check packages/

# Type checking
mypy packages/pairtrading-data/src packages/pairtrading-engine/src
```

## Requirements

- Python 3.11+
- pandas >= 2.0
- numpy >= 1.24
- httpx >= 0.25 (for API calls)

## License

MIT License - see [LICENSE](LICENSE) for details.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
