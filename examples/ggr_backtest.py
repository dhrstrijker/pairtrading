"""Example: Running a GGR Distance Strategy Backtest.

This example demonstrates how to:
1. Generate synthetic price data (or use real data via ptdata)
2. Configure and run the GGR distance strategy
3. Analyze backtest results

To run with real data, replace the synthetic data generation with:
    from ptdata import MassiveAPIProvider, CSVCache
    cache = CSVCache("./data", MassiveAPIProvider())
    prices = cache.get_prices(symbols, start_date, end_date)
"""

from datetime import date
import numpy as np
import pandas as pd

from ptdata.validation import PointInTimeDataFrame

from ptengine import BacktestRunner, BacktestConfig
from ptengine.strategies import GGRDistanceStrategy
from ptengine.commission.models import PerShareCommission


def generate_synthetic_data(
    symbols: list[str],
    start_date: date,
    end_date: date,
    seed: int = 42,
) -> pd.DataFrame:
    """Generate synthetic correlated price data for testing.

    Creates groups of correlated symbols to simulate realistic
    pair trading opportunities.
    """
    np.random.seed(seed)
    dates = pd.date_range(start=start_date, end=end_date, freq="B")

    data = []

    # Initialize prices
    prices = {s: 100.0 + np.random.uniform(-20, 20) for s in symbols}

    # Create correlation groups (pairs of adjacent symbols are correlated)
    for d in dates:
        # Market-wide shock
        market_shock = np.random.normal(0.0003, 0.008)

        for i, symbol in enumerate(symbols):
            # Group shock (adjacent symbols share this)
            group_idx = i // 2
            np.random.seed(seed + int(d.timestamp()) + group_idx)
            group_shock = np.random.normal(0, 0.01)

            # Idiosyncratic shock
            np.random.seed(seed + int(d.timestamp()) + i * 100)
            idio_shock = np.random.normal(0, 0.005)

            # Combined return
            ret = market_shock + group_shock * 0.7 + idio_shock * 0.3
            prices[symbol] *= (1 + ret)

            price = prices[symbol]
            data.append({
                "symbol": symbol,
                "date": d.date(),
                "open": price * (1 + np.random.uniform(-0.005, 0.005)),
                "high": price * (1 + np.random.uniform(0, 0.015)),
                "low": price * (1 - np.random.uniform(0, 0.015)),
                "close": price,
                "adj_close": price,
                "volume": int(np.random.uniform(1e6, 5e6)),
            })

    return pd.DataFrame(data)


def main():
    # Configuration
    symbols = ["AAPL", "MSFT", "GOOGL", "META", "AMZN", "NVDA", "TSLA", "AMD"]
    start_date = date(2020, 1, 1)
    end_date = date(2023, 12, 31)

    print("=" * 60)
    print("GGR Distance Strategy Backtest")
    print("=" * 60)
    print(f"Symbols: {symbols}")
    print(f"Period: {start_date} to {end_date}")
    print()

    # Generate synthetic data (replace with real data in production)
    print("Generating synthetic price data...")
    prices = generate_synthetic_data(symbols, start_date, end_date)
    print(f"Generated {len(prices)} price records for {len(symbols)} symbols")
    print()

    # Create PointInTimeDataFrame
    pit_data = PointInTimeDataFrame(prices, reference_date=start_date)

    # Configure the GGR strategy
    strategy = GGRDistanceStrategy(
        symbols=symbols,
        formation_period=120,      # 6 months for pair identification
        lookback=120,              # 6 months for spread statistics
        entry_threshold=2.0,       # Enter when z-score > 2.0
        exit_threshold=0.5,        # Exit when z-score < 0.5
        max_holding_days=20,       # Maximum 20 days per trade
        top_n_pairs=5,             # Trade top 5 pairs
        min_correlation=0.7,       # Minimum correlation for pair
    )

    print(f"Strategy: {strategy.name}")
    print(f"  Formation Period: {strategy.formation_period} days")
    print(f"  Entry Threshold: {strategy.entry_threshold} std devs")
    print(f"  Exit Threshold: {strategy.exit_threshold} std devs")
    print(f"  Max Holding: {strategy.max_holding_days} days")
    print(f"  Top N Pairs: {strategy.top_n_pairs}")
    print()

    # Configure the backtest
    config = BacktestConfig(
        start_date=date(2020, 7, 1),  # Start after formation period
        end_date=end_date,
        initial_capital=100_000.0,
        capital_per_pair=10_000.0,
        commission_model=PerShareCommission(rate=0.005, minimum=1.0),
    )

    print("Backtest Config:")
    print(f"  Initial Capital: ${config.initial_capital:,.2f}")
    print(f"  Capital per Pair: ${config.capital_per_pair:,.2f}")
    print(f"  Period: {config.start_date} to {config.end_date}")
    print()

    # Run the backtest
    print("Running backtest...")
    runner = BacktestRunner(strategy, config)
    result = runner.run(pit_data)

    # Print results
    print()
    print(result.summary())

    # Additional analysis
    print("\nIdentified Pairs (by SSD):")
    print("-" * 40)
    for sym_a, sym_b, ssd in strategy.get_identified_pairs():
        print(f"  {sym_a} / {sym_b}: SSD = {ssd:.4f}")

    # Trade analysis
    trades_df = result.trades_df()
    if not trades_df.empty:
        print("\nTrade Summary by Symbol:")
        print("-" * 40)
        symbol_trades = trades_df.groupby("symbol").agg({
            "shares": "sum",
            "notional": "sum",
            "commission": "sum",
        })
        print(symbol_trades.to_string())

        print(f"\nUnique pairs traded: {trades_df['pair_id'].nunique()}")

    # Equity curve
    ec = result.equity_curve()
    if not ec.empty:
        print("\nEquity Curve Statistics:")
        print("-" * 40)
        print(f"  Start: ${ec['equity'].iloc[0]:,.2f}")
        print(f"  End: ${ec['equity'].iloc[-1]:,.2f}")
        print(f"  Max: ${ec['equity'].max():,.2f}")
        print(f"  Min: ${ec['equity'].min():,.2f}")

    return result


if __name__ == "__main__":
    result = main()
