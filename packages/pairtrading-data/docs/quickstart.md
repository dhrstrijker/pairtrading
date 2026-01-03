# Quick Start Guide

This guide will help you get started with `pairtrading-data` for fetching and validating market data.

## Installation

```bash
pip install -e .
```

## Configuration

Set your Massive API key:

```bash
export MASSIVE_API_KEY="your_api_key_here"
```

Or create a `.env` file in your project root:

```
MASSIVE_API_KEY=your_api_key_here
```

## Basic Usage

### 1. Set up the data provider with caching

```python
from pathlib import Path
from datetime import date

from ptdata import MassiveAPIProvider, CSVCache, CustomUniverse

# Create provider (uses MASSIVE_API_KEY env var)
provider = MassiveAPIProvider()

# Wrap with cache to avoid re-downloading
cache_dir = Path("./data/cache")
cache = CSVCache(cache_dir, provider)
```

### 2. Define your stock universe

```python
# Option A: Custom list
universe = CustomUniverse(["AAPL", "MSFT", "GOOGL", "AMZN"])

# Option B: Sector-based
from ptdata import SectorUniverse
universe = SectorUniverse("shipping")

# Option C: From file
universe = CustomUniverse.from_file("symbols.txt")
```

### 3. Fetch data

```python
prices = cache.get_prices(
    symbols=universe.get_symbols(),
    start_date=date(2020, 1, 1),
    end_date=date(2023, 12, 31),
)

print(f"Fetched {len(prices)} rows for {prices['symbol'].nunique()} symbols")
```

### 4. Wrap for bias-safe access

```python
from ptdata.validation import PointInTimeDataFrame

# Create point-in-time wrapper
pit = PointInTimeDataFrame(prices, reference_date=date(2020, 6, 1))

# Only returns data up to 2020-06-01
safe_data = pit.get_data()

# Advance time (cannot go backward)
pit = pit.advance_to(date(2020, 6, 15))
```

## Complete Example

```python
from datetime import date
from pathlib import Path

from ptdata import MassiveAPIProvider, CSVCache, CustomUniverse
from ptdata.validation import PointInTimeDataFrame, check_price_sanity

# Setup
provider = MassiveAPIProvider()
cache = CSVCache(Path("./data/cache"), provider)
universe = CustomUniverse(["AAPL", "MSFT"])

# Fetch data
prices = cache.get_prices(
    symbols=universe.get_symbols(),
    start_date=date(2020, 1, 1),
    end_date=date(2023, 12, 31),
)

# Validate data quality
issues = check_price_sanity(prices, raise_on_error=False)
if issues:
    print(f"Warning: Found {len(issues)} data quality issues")

# Simulate point-in-time access for backtesting
reference_date = date(2020, 6, 1)
pit = PointInTimeDataFrame(prices, reference_date)

# Calculate something (only using data available at reference_date)
available_data = pit.get_data()
for symbol in universe.get_symbols():
    symbol_data = available_data[available_data["symbol"] == symbol]
    if len(symbol_data) >= 20:
        ma20 = symbol_data["close"].tail(20).mean()
        print(f"{symbol} 20-day MA as of {reference_date}: {ma20:.2f}")
```

## Using with CSV Files (No API)

If you already have CSV files:

```python
from ptdata.providers import CSVFileProvider

# Load from local CSV files
provider = CSVFileProvider(Path("./data/historical"))

# Files should be named {SYMBOL}.csv (e.g., AAPL.csv, MSFT.csv)
prices = provider.get_prices(
    symbols=["AAPL", "MSFT"],
    start_date=date(2020, 1, 1),
    end_date=date(2023, 12, 31),
)
```

## Next Steps

- [Data Providers](providers.md) - Learn about different data sources
- [Validation](validation.md) - Understand bias prevention and quality checks
