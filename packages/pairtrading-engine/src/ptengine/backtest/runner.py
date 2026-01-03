"""Backtest runner - the main simulation engine.

Orchestrates the backtest loop:
1. For each trading day
2. Advance pit_data to current date
3. Update portfolio prices
4. Call strategy.on_bar()
5. Execute trades from signals
6. Record equity
"""

from datetime import date

import pandas as pd
from ptdata.validation import PointInTimeDataFrame

from ptengine.backtest.config import BacktestConfig
from ptengine.core.exceptions import BacktestError, StrategyError
from ptengine.core.types import PairSignal, Trade, WeightSignal
from ptengine.execution.simple import ClosePriceExecution
from ptengine.portfolio.portfolio import Portfolio
from ptengine.results.metrics import calculate_metrics
from ptengine.results.report import BacktestResult
from ptengine.results.trades import TradeLog
from ptengine.strategy.base import Strategy


class BacktestRunner:
    """Runs backtests for trading strategies.

    The runner orchestrates the simulation loop, managing:
    - Time progression
    - Data access (via PointInTimeDataFrame)
    - Portfolio state
    - Signal execution
    - Result collection

    Example:
        from ptengine import BacktestRunner, BacktestConfig
        from ptdata import PointInTimeDataFrame

        config = BacktestConfig(
            start_date=date(2020, 1, 1),
            end_date=date(2023, 12, 31),
            initial_capital=100_000,
        )

        runner = BacktestRunner(strategy, config)
        result = runner.run(pit_data)
        print(result.summary())
    """

    def __init__(self, strategy: Strategy, config: BacktestConfig):
        """Initialize the backtest runner.

        Args:
            strategy: The trading strategy to test
            config: Backtest configuration
        """
        self.strategy = strategy
        self.config = config
        self.portfolio = Portfolio(initial_capital=config.initial_capital)
        self.execution = ClosePriceExecution(commission_model=config.commission_model)
        self.trade_log = TradeLog()

    def run(self, pit_data: PointInTimeDataFrame) -> BacktestResult:
        """Run the backtest simulation.

        Args:
            pit_data: PointInTimeDataFrame containing price data.
                     Should be initialized with reference_date at or before
                     config.start_date.

        Returns:
            BacktestResult with performance metrics and trade history

        Raises:
            BacktestError: If simulation encounters an error
        """
        # Reset state
        self.portfolio.reset()
        self.trade_log.clear()

        # Notify strategy of start
        self.strategy.on_start(self.config.start_date, self.config.end_date)

        # Get trading dates from data
        trading_dates = self._get_trading_dates(pit_data)

        if not trading_dates:
            raise BacktestError(
                "No trading dates found in date range",
                phase="initialization",
            )

        # Main simulation loop
        current_pit = pit_data
        for current_date in trading_dates:
            try:
                self._process_bar(current_date, current_pit)
                # Advance to next date
                current_pit = current_pit.advance_to(current_date)
            except Exception as e:
                if isinstance(e, (BacktestError, StrategyError)):
                    raise
                raise BacktestError(
                    f"Error processing {current_date}: {e}",
                    current_date=current_date,
                    phase="simulation",
                ) from e

        # Notify strategy of end
        self.strategy.on_end()

        # Calculate metrics
        metrics = calculate_metrics(
            equity_curve=self.portfolio.equity_curve,
            trade_log=self.trade_log,
            initial_capital=self.config.initial_capital,
        )

        return BacktestResult(
            strategy_name=self.strategy.name,
            config=self.config,
            portfolio=self.portfolio,
            trade_log=self.trade_log,
            metrics=metrics,
        )

    def _get_trading_dates(self, pit_data: PointInTimeDataFrame) -> list[date]:
        """Extract trading dates from data within config range.

        Args:
            pit_data: PointInTimeDataFrame with price data

        Returns:
            Sorted list of trading dates
        """
        # Get all data (we'll filter by date)
        # First advance to end to see all data
        full_data = pit_data._df  # Access underlying data for date extraction

        # Extract unique dates
        date_col = pit_data._date_column
        dates = pd.to_datetime(full_data[date_col]).dt.date.unique()

        # Filter to config range
        trading_dates = [
            d for d in sorted(dates)
            if self.config.start_date <= d <= self.config.end_date
        ]

        return trading_dates

    def _process_bar(self, current_date: date, pit_data: PointInTimeDataFrame) -> None:
        """Process a single trading day.

        Args:
            current_date: Current simulation date
            pit_data: PointInTimeDataFrame at current date
        """
        # Get current prices
        prices = self._get_current_prices(pit_data, current_date)

        # Update portfolio with current prices
        self.portfolio.update_prices(prices)

        # Call strategy
        try:
            signal = self.strategy.on_bar(current_date, pit_data)
        except Exception as e:
            raise StrategyError(
                f"Strategy error: {e}",
                strategy_name=self.strategy.name,
                current_date=current_date,
                original_error=e,
            ) from e

        # Execute signal if any
        if signal is not None:
            trades = self._execute_signal(signal, current_date, prices)
            for trade in trades:
                self.trade_log.add_trade(trade)
                self.strategy.on_fill(trade)

        # Record equity
        self.portfolio.record_equity(current_date)

    def _get_current_prices(
        self, pit_data: PointInTimeDataFrame, current_date: date
    ) -> dict[str, float]:
        """Get prices for the current date.

        Args:
            pit_data: PointInTimeDataFrame
            current_date: Current simulation date

        Returns:
            Dict mapping symbol to price
        """
        data = pit_data.get_data()
        price_col = self.config.price_column

        # Get most recent price for each symbol
        prices: dict[str, float] = {}

        if "symbol" in data.columns:
            for symbol in data["symbol"].unique():
                symbol_data = data[data["symbol"] == symbol]
                if not symbol_data.empty:
                    # Get latest row for this symbol
                    latest = symbol_data.iloc[-1]
                    prices[symbol] = float(latest[price_col])
        else:
            # Single-symbol data
            if not data.empty:
                latest = data.iloc[-1]
                prices["default"] = float(latest[price_col])

        return prices

    def _execute_signal(
        self,
        signal: PairSignal | WeightSignal,
        current_date: date,
        prices: dict[str, float],
    ) -> list[Trade]:
        """Execute a signal and return resulting trades.

        Args:
            signal: The signal to execute
            current_date: Current simulation date
            prices: Current prices

        Returns:
            List of executed trades
        """
        if isinstance(signal, PairSignal):
            return self.execution.execute_pair_signal(
                signal=signal,
                current_date=current_date,
                prices=prices,
                portfolio=self.portfolio,
                capital_per_pair=self.config.capital_per_pair,
            )
        elif isinstance(signal, WeightSignal):
            return self.execution.execute_weight_signal(
                signal=signal,
                current_date=current_date,
                prices=prices,
                portfolio=self.portfolio,
            )
        return []
