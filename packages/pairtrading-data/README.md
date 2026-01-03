# pairtrading-data

Market data collection and validation library for pair trading strategies.

## Features

- **Data Providers**: Fetch market data from Massive API (formerly Polygon) with automatic caching
- **Stock Universes**: Manage symbol lists (S&P 500, sectors like shipping/mining, custom lists)
- **Bias Prevention**: `PointInTimeDataFrame` prevents look-ahead bias
- **Data Validation**: Quality checks for gaps, outliers, corporate actions

## Installation

### Development (editable install)

```bash
pip install -e .
```

### From Git

```bash
pip install git+https://github.com/dylanstrijker/pairtrading-data.git
```

## Quick Start

```python
from datetime import date
from ptdata import MassiveAPIProvider, CSVCache, CustomUniverse
from ptdata.validation import PointInTimeDataFrame

# Set up API key (or use MASSIVE_API_KEY env var)
provider = MassiveAPIProvider()

# Create cache to avoid re-downloading
cache = CSVCache("./data/cache", provider)

# Define your universe
universe = CustomUniverse(["AAPL", "MSFT", "GOOGL"])

# Fetch data
prices = cache.get_prices(
    symbols=universe.get_symbols(),
    start_date=date(2020, 1, 1),
    end_date=date(2023, 12, 31)
)

# Wrap for bias-safe access
pit_data = PointInTimeDataFrame(prices, reference_date=date(2020, 6, 1))
safe_data = pit_data.get_data()  # Only returns data up to 2020-06-01
```

## Configuration

Set your Massive API key as an environment variable:

```bash
export MASSIVE_API_KEY="your_api_key_here"
```

Or create a `.env` file:

```
MASSIVE_API_KEY=your_api_key_here
```

## Stock Universes

### Custom Universe

```python
from ptdata import CustomUniverse

# From list
universe = CustomUniverse(["AAPL", "MSFT", "GOOGL"])

# From file (one symbol per line)
universe = CustomUniverse.from_file("symbols.txt")
```

### Sector Universe

```python
from ptdata import SectorUniverse

# Available sectors: shipping, mining, metals
universe = SectorUniverse("shipping")
symbols = universe.get_symbols()
```

## Bias Prevention

### Look-Ahead Bias

The `PointInTimeDataFrame` wrapper ensures you only access data that would have been available at a given date:

```python
from ptdata.validation import PointInTimeDataFrame

pit = PointInTimeDataFrame(prices, reference_date=date(2020, 6, 1))

# Only returns data up to 2020-06-01
data = pit.get_data()

# Move forward in time (never backward)
pit = pit.advance_to(date(2020, 6, 15))
```

### Survivorship Bias

Use point-in-time universe constituents when available:

```python
# Get constituents as they were on a specific date
symbols = universe.get_symbols(as_of_date=date(2015, 1, 1))
```

## Testing

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run with coverage
pytest --cov=ptdata
```

## License

MIT
