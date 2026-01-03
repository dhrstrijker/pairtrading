# Validation and Bias Prevention

This document covers the validation tools and bias prevention mechanisms in `pairtrading-data`.

## Look-Ahead Bias Prevention

Look-ahead bias occurs when future information is used to make decisions that would have been made at an earlier point in time. This is one of the most common errors in backtesting.

### PointInTimeDataFrame

The `PointInTimeDataFrame` wrapper prevents access to future data:

```python
from datetime import date
from ptdata.validation import PointInTimeDataFrame

# Wrap your price data
pit = PointInTimeDataFrame(prices, reference_date=date(2020, 6, 1))

# Only returns data up to 2020-06-01
safe_data = pit.get_data()

# Get the most recent data point
latest = pit.get_latest("AAPL")

# Filter by symbol
aapl_data = pit.for_symbol("AAPL")
```

### Advancing Time

You can move the reference date forward, but never backward:

```python
# Move forward (allowed)
pit = pit.advance_to(date(2020, 6, 15))

# Move backward (raises LookAheadBiasError)
pit.advance_to(date(2020, 5, 1))  # Raises!
```

### Slicing Data

Request a date range, limited by the reference date:

```python
# Get data for a specific range
data = pit.slice(date(2020, 3, 1), date(2020, 5, 31))

# Cannot request data after reference date
data = pit.slice(date(2020, 3, 1), date(2020, 8, 31))  # Raises!
```

### Properties

```python
# Current reference date
print(pit.reference_date)  # date(2020, 6, 1)

# Number of visible rows
print(len(pit))

# List of symbols
print(pit.symbols)
```

## Survivorship Bias Prevention

Survivorship bias occurs when failed/delisted companies are excluded from analysis.

### Point-in-Time Universes

Request universe constituents as of a specific date:

```python
from ptdata.universes import SP500Universe

universe = SP500Universe()

# Get constituents as of a historical date
# (Note: Currently returns current constituents - see limitations)
symbols = universe.get_symbols(as_of_date=date(2015, 1, 1))
```

### Limitations

- **SP500Universe**: Currently returns current constituents only. Historical constituent tracking requires additional data source.
- **SectorUniverse**: Static lists that don't track historical changes.
- **CustomUniverse**: User must manually handle delistings.

### Handling Delisted Stocks

Include delisted stocks in your analysis up to their delisting date:

```python
# Check if stock was delisted
if "delisted" in df.columns:
    delisted_rows = df[df["delisted"]]
    print(f"Stock delisted on: {delisted_rows['date'].iloc[0]}")
```

## Data Quality Checks

### Price Sanity Checks

Validate OHLCV data integrity:

```python
from ptdata.validation import check_price_sanity

# Returns list of issues, raises if raise_on_error=True
issues = check_price_sanity(df, raise_on_error=False)

for issue in issues:
    print(f"{issue['symbol']} on {issue['date']}: {issue['message']}")
```

Checks performed:
- No negative prices
- High >= Low
- Close between High and Low
- Open between High and Low
- No extreme single-day moves (default >50%)

### Adjusted Price Checks

Validate adjusted price consistency:

```python
from ptdata.validation import check_adjusted_prices

issues = check_adjusted_prices(df, raise_on_error=False)
```

Checks performed:
- Adjustment factor consistency (no sudden unexplained jumps)

### Combined Validation

Run all checks at once:

```python
from ptdata.validation import validate_dataframe

issues = validate_dataframe(
    df,
    required_columns=["symbol", "date", "close", "adj_close"],
    raise_on_error=False,
)
```

## Missing Data Handling

### Finding Gaps

Detect gaps in your data:

```python
from ptdata.validation import find_gaps

gaps = find_gaps(df, date_column="date", symbol_column="symbol")

for _, gap in gaps.iterrows():
    print(f"{gap['symbol']}: {gap['gap_days']} day gap from {gap['gap_start']} to {gap['gap_end']}")
```

### Handling Missing Data

Choose a strategy for missing data:

```python
from ptdata.validation import handle_missing_data, MissingDataStrategy

# Forward fill (use last known value)
df = handle_missing_data(
    df,
    strategy=MissingDataStrategy.FORWARD_FILL,
    max_consecutive=5,  # Max consecutive missing values allowed
)

# Backward fill
df = handle_missing_data(df, strategy=MissingDataStrategy.BACKWARD_FILL)

# Linear interpolation
df = handle_missing_data(df, strategy=MissingDataStrategy.INTERPOLATE)

# Drop rows with missing data
df = handle_missing_data(df, strategy=MissingDataStrategy.DROP)

# Raise error if missing data exists
df = handle_missing_data(df, strategy=MissingDataStrategy.RAISE)
```

### Aligning Dates

Align data from different sources or markets:

```python
from ptdata.validation import align_dates

# Inner join - only dates in both
us_df, uk_df = align_dates(us_df, uk_df, how="inner")

# Left join - keep all dates from first DataFrame
us_df, uk_df = align_dates(us_df, uk_df, how="left")

# Right join - keep all dates from second DataFrame
us_df, uk_df = align_dates(us_df, uk_df, how="right")
```

## Exceptions

### LookAheadBiasError

Raised when attempting to access future data:

```python
from ptdata.core.exceptions import LookAheadBiasError

try:
    pit.advance_to(date(2020, 1, 1))  # Moving backward
except LookAheadBiasError as e:
    print(f"Look-ahead bias detected: {e}")
    print(f"Access date: {e.access_date}")
    print(f"Data date: {e.data_date}")
```

### DataQualityError

Raised when data quality checks fail:

```python
from ptdata.core.exceptions import DataQualityError

try:
    check_price_sanity(df, raise_on_error=True)
except DataQualityError as e:
    print(f"Data quality issue: {e}")
    print(f"Check: {e.check_name}")
```

### InsufficientDataError

Raised when not enough data is available:

```python
from ptdata.core.exceptions import InsufficientDataError

try:
    prices = provider.get_prices(symbols, start, end)
except InsufficientDataError as e:
    print(f"Insufficient data: {e}")
```
