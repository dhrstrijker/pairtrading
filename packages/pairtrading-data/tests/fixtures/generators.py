"""Synthetic data generators with known properties for testing.

These generators create test data with specific characteristics to verify
that the system handles various scenarios correctly, including:
- Stock splits and corporate actions
- Delistings (for survivorship bias testing)
- Correlated but not cointegrated series
- Missing data and gaps
- Different trading calendars
"""

from datetime import date

import numpy as np
import pandas as pd


def generate_price_series(
    n_days: int = 252,
    start_price: float = 100.0,
    annual_return: float = 0.08,
    annual_volatility: float = 0.20,
    start_date: date | None = None,
    symbol: str = "TEST",
    seed: int = 42,
) -> pd.DataFrame:
    """Generate a random walk price series with specified parameters.

    Args:
        n_days: Number of trading days
        start_price: Starting price
        annual_return: Expected annual return (as decimal)
        annual_volatility: Annual volatility (as decimal)
        start_date: Start date (default: 2020-01-01)
        symbol: Ticker symbol
        seed: Random seed for reproducibility

    Returns:
        DataFrame with OHLCV columns
    """
    np.random.seed(seed)

    if start_date is None:
        start_date = date(2020, 1, 1)

    # Daily parameters from annual
    daily_return = annual_return / 252
    daily_vol = annual_volatility / np.sqrt(252)

    # Generate returns
    returns = np.random.normal(daily_return, daily_vol, n_days)
    prices = start_price * np.exp(np.cumsum(returns))

    # Generate OHLC with realistic intraday range
    intraday_range = daily_vol * 0.5
    highs = prices * (1 + np.abs(np.random.normal(0, intraday_range, n_days)))
    lows = prices * (1 - np.abs(np.random.normal(0, intraday_range, n_days)))
    opens = lows + (highs - lows) * np.random.uniform(0.2, 0.8, n_days)

    # Ensure price relationships are valid
    highs = np.maximum(highs, np.maximum(prices, opens))
    lows = np.minimum(lows, np.minimum(prices, opens))

    dates = pd.bdate_range(start=start_date, periods=n_days)

    return pd.DataFrame({
        "symbol": symbol,
        "date": dates,
        "open": opens,
        "high": highs,
        "low": lows,
        "close": prices,
        "adj_close": prices,  # Will be adjusted if there are corporate actions
        "volume": np.random.randint(100000, 10000000, n_days),
    })


def generate_with_stock_split(
    n_days: int = 252,
    split_day: int = 126,
    split_ratio: float = 2.0,
    seed: int = 42,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Generate price data with a stock split.

    The split occurs at split_day. Before the split:
    - close prices are higher (pre-split)
    - adj_close should be lower (adjusted for the split)

    After the split:
    - close prices drop by split_ratio
    - adj_close should be continuous

    Args:
        n_days: Number of trading days
        split_day: Day index when split occurs (0-indexed)
        split_ratio: Split ratio (2.0 = 2-for-1 split)
        seed: Random seed for reproducibility

    Returns:
        Tuple of (prices_df, splits_df) where:
        - prices_df has OHLCV with both close and adj_close
        - splits_df has split information

    Use case: Test that split adjustments are applied correctly
    and look-ahead bias is detected (can't know about future splits).
    """
    np.random.seed(seed)

    start_date = date(2020, 1, 1)
    dates = pd.bdate_range(start=start_date, periods=n_days)

    # Generate continuous returns (this represents the "true" price movement)
    daily_return = 0.0003
    daily_vol = 0.02
    returns = np.random.normal(daily_return, daily_vol, n_days)

    # The adjusted close is the continuous series
    adj_close = 100 * np.exp(np.cumsum(returns))

    # The actual close price is the adjusted price * split factor
    # Before split: close = adj_close * split_ratio
    # After split: close = adj_close
    close = adj_close.copy()
    close[:split_day] = close[:split_day] * split_ratio

    # Generate other OHLC based on close
    intraday_range = 0.01
    high = close * (1 + np.abs(np.random.normal(0, intraday_range, n_days)))
    low = close * (1 - np.abs(np.random.normal(0, intraday_range, n_days)))
    open_price = low + (high - low) * np.random.uniform(0.2, 0.8, n_days)

    # Adjust OHLC for split as well
    adj_high = high.copy()
    adj_low = low.copy()
    adj_open = open_price.copy()
    adj_high[:split_day] = adj_high[:split_day] / split_ratio
    adj_low[:split_day] = adj_low[:split_day] / split_ratio
    adj_open[:split_day] = adj_open[:split_day] / split_ratio

    prices_df = pd.DataFrame({
        "symbol": "SPLIT_TEST",
        "date": dates,
        "open": open_price,
        "high": high,
        "low": low,
        "close": close,
        "adj_close": adj_close,
        "volume": np.random.randint(100000, 10000000, n_days),
    })

    split_date = dates[split_day].date()
    splits_df = pd.DataFrame({
        "symbol": ["SPLIT_TEST"],
        "date": [split_date],
        "split_ratio": [split_ratio],
    })

    return prices_df, splits_df


def generate_delisting(
    n_days: int = 252,
    delist_day: int = 200,
    final_price_drop: float = 0.9,
    seed: int = 42,
) -> pd.DataFrame:
    """Generate price data for a stock that gets delisted.

    The stock trades normally until delist_day, then stops.
    Optionally includes a price drop leading up to delisting.

    Args:
        n_days: Total number of days (data only exists until delist_day)
        delist_day: Day index when delisting occurs
        final_price_drop: Price drop leading to delisting (0.9 = 90% drop)
        seed: Random seed for reproducibility

    Returns:
        DataFrame with OHLCV data until delisting date

    Use case: Test survivorship bias - stock should be included
    until delisting date, then excluded from universe.
    """
    np.random.seed(seed)

    start_date = date(2020, 1, 1)
    dates = pd.bdate_range(start=start_date, periods=delist_day)

    # Generate price series with decline leading to delisting
    daily_vol = 0.02

    # Normal returns until 20 days before delisting
    decline_start = max(0, delist_day - 20)
    returns = np.random.normal(0.0003, daily_vol, delist_day)

    # Add significant decline at the end
    if decline_start < delist_day:
        decline_period = delist_day - decline_start
        decline_per_day = np.log(1 - final_price_drop) / decline_period
        noise = np.random.normal(0, daily_vol * 2, decline_period)
        returns[decline_start:] = decline_per_day + noise

    prices = 100 * np.exp(np.cumsum(returns))

    # Generate OHLC
    high = prices * (1 + np.abs(np.random.normal(0, 0.01, delist_day)))
    low = prices * (1 - np.abs(np.random.normal(0, 0.01, delist_day)))
    open_price = low + (high - low) * np.random.uniform(0.2, 0.8, delist_day)

    return pd.DataFrame({
        "symbol": "DELIST_TEST",
        "date": dates,
        "open": open_price,
        "high": high,
        "low": low,
        "close": prices,
        "adj_close": prices,
        "volume": np.random.randint(100000, 10000000, delist_day),
        "delisted": [False] * (delist_day - 1) + [True],
    })


def generate_correlated_not_cointegrated(
    n_days: int = 252,
    correlation: float = 0.9,
    drift_a: float = 0.0005,
    drift_b: float = -0.0003,
    seed: int = 42,
) -> tuple[pd.Series, pd.Series]:
    """Generate two series that are correlated but NOT cointegrated.

    Two series can be highly correlated in returns but NOT cointegrated
    if they have different drifts (trends). This is a common mistake
    in pairs trading - high correlation doesn't imply mean reversion.

    Args:
        n_days: Number of trading days
        correlation: Target return correlation
        drift_a: Daily drift for series A
        drift_b: Daily drift for series B
        seed: Random seed for reproducibility

    Returns:
        Tuple of (series_a, series_b) - price series that are
        correlated but will fail cointegration tests

    Use case: Test that correlation != cointegration.
    These pairs should FAIL cointegration tests.
    """
    np.random.seed(seed)

    # Generate correlated returns using Cholesky decomposition
    daily_vol = 0.02

    # Create correlation matrix
    corr_matrix = np.array([[1.0, correlation], [correlation, 1.0]])
    chol = np.linalg.cholesky(corr_matrix)

    # Generate independent standard normal returns
    independent_returns = np.random.normal(0, 1, (n_days, 2))

    # Transform to correlated returns
    correlated_returns = (chol @ independent_returns.T).T * daily_vol

    # Add different drifts - this breaks cointegration!
    returns_a = correlated_returns[:, 0] + drift_a
    returns_b = correlated_returns[:, 1] + drift_b

    # Convert to prices
    price_a = 100 * np.exp(np.cumsum(returns_a))
    price_b = 100 * np.exp(np.cumsum(returns_b))

    return pd.Series(price_a, name="A"), pd.Series(price_b, name="B")


def generate_cointegrated_pair(
    n_days: int = 252,
    mean_spread: float = 0.0,
    spread_volatility: float = 0.05,
    half_life: int = 20,
    seed: int = 42,
) -> tuple[pd.Series, pd.Series]:
    """Generate two series that ARE cointegrated.

    Uses the Ornstein-Uhlenbeck process to generate a mean-reverting spread,
    then constructs two price series that maintain this relationship.

    Args:
        n_days: Number of trading days
        mean_spread: Long-term mean of the spread
        spread_volatility: Volatility of the spread
        half_life: Mean reversion half-life in days
        seed: Random seed for reproducibility

    Returns:
        Tuple of (series_a, series_b) - price series that ARE cointegrated

    Use case: Test that cointegrated pairs pass cointegration tests.
    """
    np.random.seed(seed)

    # Mean reversion parameter
    theta = np.log(2) / half_life

    # Generate OU process for spread
    dt = 1.0  # 1 day
    spread = np.zeros(n_days)
    spread[0] = mean_spread

    for t in range(1, n_days):
        dW = np.random.normal(0, np.sqrt(dt))
        drift = theta * (mean_spread - spread[t-1]) * dt
        spread[t] = spread[t-1] + drift + spread_volatility * dW

    # Generate common factor (market movement)
    market_returns = np.random.normal(0.0003, 0.015, n_days)
    market = 100 * np.exp(np.cumsum(market_returns))

    # Construct two series that maintain the spread relationship
    # A = market, B = market + spread
    price_a = market
    price_b = market * (1 + spread / 100)  # Scale spread to price level

    return pd.Series(price_a, name="A"), pd.Series(price_b, name="B")


def generate_with_missing_days(
    n_days: int = 252,
    missing_indices: list[int] | None = None,
    seed: int = 42,
) -> pd.DataFrame:
    """Generate price data with specific missing days.

    Args:
        n_days: Number of trading days (before removing missing days)
        missing_indices: List of day indices to remove (0-indexed)
        seed: Random seed for reproducibility

    Returns:
        DataFrame with gaps at specified indices

    Use case: Test gap handling strategies.
    """
    if missing_indices is None:
        missing_indices = [50, 51, 100, 150, 151, 152]

    df = generate_price_series(n_days=n_days, symbol="GAP_TEST", seed=seed)

    # Remove the specified indices
    mask = ~df.index.isin(missing_indices)
    return df[mask].reset_index(drop=True)


def generate_different_calendars(
    n_days: int = 252,
    seed: int = 42,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Generate price data for two markets with different holiday calendars.

    Simulates US and UK markets where some holidays differ:
    - US has July 4th, Thanksgiving
    - UK has different bank holidays

    Args:
        n_days: Number of base trading days
        seed: Random seed for reproducibility

    Returns:
        Tuple of (us_df, uk_df) with different trading dates

    Use case: Test calendar alignment logic when comparing securities
    from different markets.
    """
    np.random.seed(seed)

    start_date = date(2020, 1, 1)

    # Generate base dates
    us_dates = pd.bdate_range(start=start_date, periods=n_days)

    # US-specific holidays (simplified)
    us_holidays = [
        pd.Timestamp("2020-01-20"),  # MLK Day
        pd.Timestamp("2020-02-17"),  # Presidents Day
        pd.Timestamp("2020-07-03"),  # July 4 observed
        pd.Timestamp("2020-09-07"),  # Labor Day
        pd.Timestamp("2020-11-26"),  # Thanksgiving
    ]

    # UK-specific holidays (simplified)
    uk_holidays = [
        pd.Timestamp("2020-01-01"),  # New Year (US open)
        pd.Timestamp("2020-04-10"),  # Good Friday
        pd.Timestamp("2020-04-13"),  # Easter Monday
        pd.Timestamp("2020-05-08"),  # VE Day
        pd.Timestamp("2020-08-31"),  # August Bank Holiday
    ]

    us_dates_filtered = us_dates[~us_dates.isin(us_holidays)]
    uk_dates_filtered = us_dates[~us_dates.isin(uk_holidays)]

    # Generate US data
    n_us = len(us_dates_filtered)
    us_returns = np.random.normal(0.0003, 0.02, n_us)
    us_prices = 100 * np.exp(np.cumsum(us_returns))

    us_df = pd.DataFrame({
        "symbol": "US_TEST",
        "date": us_dates_filtered,
        "open": us_prices * 0.99,
        "high": us_prices * 1.01,
        "low": us_prices * 0.98,
        "close": us_prices,
        "adj_close": us_prices,
        "volume": np.random.randint(100000, 10000000, n_us),
    })

    # Generate UK data (with slight correlation to US)
    np.random.seed(seed + 1)
    n_uk = len(uk_dates_filtered)
    uk_returns = np.random.normal(0.0002, 0.018, n_uk)
    uk_prices = 150 * np.exp(np.cumsum(uk_returns))

    uk_df = pd.DataFrame({
        "symbol": "UK_TEST",
        "date": uk_dates_filtered,
        "open": uk_prices * 0.99,
        "high": uk_prices * 1.01,
        "low": uk_prices * 0.98,
        "close": uk_prices,
        "adj_close": uk_prices,
        "volume": np.random.randint(100000, 10000000, n_uk),
    })

    return us_df, uk_df
