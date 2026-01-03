"""Backtest result reporting."""

from dataclasses import dataclass
from datetime import date

import pandas as pd

from ptengine.backtest.config import BacktestConfig
from ptengine.portfolio.portfolio import Portfolio
from ptengine.results.metrics import PerformanceMetrics
from ptengine.results.trades import TradeLog


@dataclass
class BacktestResult:
    """Complete results from a backtest run.

    Contains all information needed to analyze backtest performance:
    - Strategy identification
    - Configuration used
    - Final portfolio state
    - Complete trade history
    - Performance metrics

    Attributes:
        strategy_name: Name of the strategy tested
        config: BacktestConfig used
        portfolio: Final portfolio state
        trade_log: Complete trade history
        metrics: Calculated performance metrics
    """

    strategy_name: str
    config: BacktestConfig
    portfolio: Portfolio
    trade_log: TradeLog
    metrics: PerformanceMetrics

    def summary(self) -> str:
        """Generate a text summary of backtest results.

        Returns:
            Formatted string with key metrics
        """
        lines = [
            "=" * 60,
            f"Backtest Results: {self.strategy_name}",
            "=" * 60,
            f"Period: {self.config.start_date} to {self.config.end_date}",
            f"Initial Capital: ${self.config.initial_capital:,.2f}",
            f"Final Equity: ${self.portfolio.equity:,.2f}",
            "",
            "Performance Metrics:",
            "-" * 40,
            f"Total Return: {self.metrics.total_return * 100:.2f}%",
            f"Annualized Return: {self.metrics.annualized_return * 100:.2f}%",
            f"Sharpe Ratio: {self.metrics.sharpe_ratio:.2f}",
            f"Max Drawdown: {self.metrics.max_drawdown * 100:.2f}%",
            f"Max DD Duration: {self.metrics.max_drawdown_duration} days",
            f"Volatility: {self.metrics.volatility * 100:.2f}%",
            "",
            "Trade Statistics:",
            "-" * 40,
            f"Number of Trades: {self.metrics.num_trades}",
            f"Win Rate: {self.metrics.win_rate * 100:.1f}%",
            f"Profit Factor: {self.metrics.profit_factor:.2f}",
            f"Total Commission: ${self.metrics.total_commission:,.2f}",
            "=" * 60,
        ]
        return "\n".join(lines)

    def equity_curve(self) -> pd.DataFrame:
        """Return equity curve as a DataFrame.

        Returns:
            DataFrame with columns: date, equity
        """
        data = [
            {"date": d, "equity": e}
            for d, e in self.portfolio.equity_curve
        ]
        return pd.DataFrame(data)

    def trades_df(self) -> pd.DataFrame:
        """Return trade log as a DataFrame."""
        return self.trade_log.to_dataframe()

    def daily_returns(self) -> pd.Series:
        """Calculate daily returns from equity curve.

        Returns:
            Series of daily returns indexed by date
        """
        ec = self.equity_curve()
        if len(ec) < 2:
            return pd.Series(dtype=float)

        ec = ec.set_index("date")
        returns = ec["equity"].pct_change().dropna()
        return returns

    def cumulative_returns(self) -> pd.Series:
        """Calculate cumulative returns from equity curve.

        Returns:
            Series of cumulative returns indexed by date
        """
        ec = self.equity_curve()
        if len(ec) < 1:
            return pd.Series(dtype=float)

        ec = ec.set_index("date")
        initial = ec["equity"].iloc[0]
        cumulative = (ec["equity"] / initial) - 1
        return cumulative

    def metrics_dict(self) -> dict[str, float | int]:
        """Return metrics as a dictionary."""
        return self.metrics.to_dict()

    @property
    def start_date(self) -> date:
        """Return backtest start date."""
        return self.config.start_date

    @property
    def end_date(self) -> date:
        """Return backtest end date."""
        return self.config.end_date

    @property
    def initial_capital(self) -> float:
        """Return initial capital."""
        return self.config.initial_capital

    @property
    def final_equity(self) -> float:
        """Return final portfolio equity."""
        return self.portfolio.equity
