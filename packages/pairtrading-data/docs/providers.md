# Data Providers

This document describes the available data providers and how to use them.

## Provider Protocol

All providers implement the `DataProvider` protocol:

```python
from typing import Protocol
from datetime import date
import pandas as pd

class DataProvider(Protocol):
    @property
    def name(self) -> str:
        """Provider identifier."""
        ...

    def get_prices(
        self,
        symbols: list[str],
        start_date: date,
        end_date: date,
        adjusted: bool = True
    ) -> pd.DataFrame:
        """Fetch OHLCV price data."""
        ...
```

## MassiveAPIProvider

Fetches data from the Massive API (formerly Polygon).

### Setup

```python
from ptdata import MassiveAPIProvider

# Uses MASSIVE_API_KEY environment variable
provider = MassiveAPIProvider()

# Or pass API key directly
provider = MassiveAPIProvider(api_key="your_key")
```

### Configuration

Set your API key:

```bash
export MASSIVE_API_KEY="your_api_key_here"
```

Or in `.env`:

```
MASSIVE_API_KEY=your_api_key_here
```

### Usage

```python
from datetime import date

prices = provider.get_prices(
    symbols=["AAPL", "MSFT"],
    start_date=date(2020, 1, 1),
    end_date=date(2023, 12, 31),
    adjusted=True,  # Use split-adjusted prices
)
```

### Rate Limiting

The provider handles rate limiting automatically with exponential backoff.

## CSVFileProvider

Loads data from local CSV files.

### Setup

```python
from pathlib import Path
from ptdata.providers import CSVFileProvider

provider = CSVFileProvider(Path("./data/historical"))
```

### File Format

Files should be named `{SYMBOL}.csv` and contain columns:

| Column | Type | Description |
|--------|------|-------------|
| symbol | str | Ticker symbol |
| date | date | Trading date |
| open | float | Opening price |
| high | float | High price |
| low | float | Low price |
| close | float | Closing price |
| adj_close | float | Adjusted close price |
| volume | int | Trading volume |

Example `AAPL.csv`:

```csv
symbol,date,open,high,low,close,adj_close,volume
AAPL,2020-01-02,74.06,75.15,73.80,75.09,73.45,135647456
AAPL,2020-01-03,74.29,75.14,74.13,74.36,72.73,146322800
...
```

### Usage

```python
prices = provider.get_prices(
    symbols=["AAPL", "MSFT"],
    start_date=date(2020, 1, 1),
    end_date=date(2023, 12, 31),
)
```

## CSVCache

Wraps any provider with CSV file caching.

### Setup

```python
from ptdata import CSVCache, MassiveAPIProvider
from pathlib import Path

provider = MassiveAPIProvider()
cache = CSVCache(Path("./data/cache"), provider)
```

### How It Works

1. First request for a symbol downloads data and saves to CSV
2. Subsequent requests load from CSV if the cached range covers the request
3. If requested range extends beyond cached range, re-downloads all data

### Cache Invalidation

The cache uses a simple invalidation strategy:

- If the requested date range is fully covered by the cache, use cache
- If not, delete the cache file and re-download everything

This avoids complex gap-filling logic while ensuring data consistency.

### Clearing Cache

```python
# Clear specific symbols
cache.clear_cache(symbols=["AAPL", "MSFT"])

# Clear all
cache.clear_cache()
```

### Cache Structure

```
cache_dir/
├── AAPL.csv
├── MSFT.csv
├── GOOGL.csv
└── _metadata.json
```

## Creating Custom Providers

Implement the `DataProvider` protocol:

```python
from datetime import date
import pandas as pd

class MyCustomProvider:
    @property
    def name(self) -> str:
        return "my_custom"

    def get_prices(
        self,
        symbols: list[str],
        start_date: date,
        end_date: date,
        adjusted: bool = True,
    ) -> pd.DataFrame:
        # Fetch data from your source
        data = []
        for symbol in symbols:
            symbol_data = self._fetch_symbol(symbol, start_date, end_date)
            data.append(symbol_data)

        return pd.concat(data, ignore_index=True)
```
