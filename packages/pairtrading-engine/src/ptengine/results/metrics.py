"""Performance metrics calculation.

Provides standard performance metrics for backtest evaluation:
- Total and annualized returns
- Sharpe ratio
- Maximum drawdown
- Win rate and profit factor
"""

from dataclasses import dataclass
from datetime import date
import math

import numpy as np
import pandas as pd

from ptengine.core.constants import (
    TRADING_DAYS_PER_YEAR,
    DEFAULT_RISK_FREE_RATE,
    MIN_TRADING_DAYS_FOR_METRICS,
)
from ptengine.results.trades import TradeLog


@dataclass
class PerformanceMetrics:
    """Container for backtest performance metrics.

    Attributes:
        total_return: Total return as decimal (0.10 = 10%)
        annualized_return: Annualized return as decimal
        sharpe_ratio: Annualized Sharpe ratio
        max_drawdown: Maximum drawdown as decimal (0.20 = 20%)
        max_drawdown_duration: Days in longest drawdown
        volatility: Annualized volatility
        win_rate: Fraction of winning trades (0.0 to 1.0)
        profit_factor: Gross profit / gross loss
        num_trades: Total number of trades
        avg_trade_return: Average return per trade
        total_commission: Total commission paid
    """

    total_return: float
    annualized_return: float
    sharpe_ratio: float
    max_drawdown: float
    max_drawdown_duration: int
    volatility: float
    win_rate: float
    profit_factor: float
    num_trades: int
    avg_trade_return: float
    total_commission: float

    def to_dict(self) -> dict[str, float | int]:
        """Convert metrics to dictionary."""
        return {
            "total_return": self.total_return,
            "annualized_return": self.annualized_return,
            "sharpe_ratio": self.sharpe_ratio,
            "max_drawdown": self.max_drawdown,
            "max_drawdown_duration": self.max_drawdown_duration,
            "volatility": self.volatility,
            "win_rate": self.win_rate,
            "profit_factor": self.profit_factor,
            "num_trades": self.num_trades,
            "avg_trade_return": self.avg_trade_return,
            "total_commission": self.total_commission,
        }


def calculate_metrics(
    equity_curve: list[tuple[date, float]],
    trade_log: TradeLog,
    initial_capital: float,
    risk_free_rate: float = DEFAULT_RISK_FREE_RATE,
) -> PerformanceMetrics:
    """Calculate performance metrics from backtest results.

    Args:
        equity_curve: List of (date, equity) tuples
        trade_log: Log of all trades
        initial_capital: Starting capital
        risk_free_rate: Annual risk-free rate for Sharpe calculation

    Returns:
        PerformanceMetrics instance
    """
    if len(equity_curve) < MIN_TRADING_DAYS_FOR_METRICS:
        return _empty_metrics(trade_log.num_trades, trade_log.total_commission)

    # Convert to arrays
    dates = [e[0] for e in equity_curve]
    equity_values = np.array([e[1] for e in equity_curve])

    # Returns
    total_return = (equity_values[-1] - initial_capital) / initial_capital

    # Daily returns
    daily_returns = np.diff(equity_values) / equity_values[:-1]
    daily_returns = daily_returns[np.isfinite(daily_returns)]

    if len(daily_returns) == 0:
        return _empty_metrics(trade_log.num_trades, trade_log.total_commission)

    # Annualized return
    trading_days = len(equity_values)
    years = trading_days / TRADING_DAYS_PER_YEAR
    if years > 0 and equity_values[-1] > 0 and initial_capital > 0:
        annualized_return = (equity_values[-1] / initial_capital) ** (1 / years) - 1
    else:
        annualized_return = 0.0

    # Volatility (annualized)
    volatility = np.std(daily_returns) * np.sqrt(TRADING_DAYS_PER_YEAR)

    # Sharpe ratio
    if volatility > 0:
        daily_rf = risk_free_rate / TRADING_DAYS_PER_YEAR
        excess_return = np.mean(daily_returns) - daily_rf
        sharpe_ratio = (excess_return / np.std(daily_returns)) * np.sqrt(TRADING_DAYS_PER_YEAR)
    else:
        sharpe_ratio = 0.0

    # Drawdown analysis
    max_drawdown, max_dd_duration = _calculate_drawdown(equity_values, dates)

    # Trade metrics
    win_rate, profit_factor, avg_trade_return = _calculate_trade_metrics(trade_log)

    return PerformanceMetrics(
        total_return=float(total_return),
        annualized_return=float(annualized_return),
        sharpe_ratio=float(sharpe_ratio),
        max_drawdown=float(max_drawdown),
        max_drawdown_duration=max_dd_duration,
        volatility=float(volatility),
        win_rate=win_rate,
        profit_factor=profit_factor,
        num_trades=trade_log.num_trades,
        avg_trade_return=avg_trade_return,
        total_commission=trade_log.total_commission,
    )


def _calculate_drawdown(
    equity_values: np.ndarray, dates: list[date]
) -> tuple[float, int]:
    """Calculate maximum drawdown and duration.

    Args:
        equity_values: Array of equity values
        dates: List of corresponding dates

    Returns:
        (max_drawdown, max_drawdown_duration_days)
    """
    if len(equity_values) < 2:
        return 0.0, 0

    # Running maximum
    running_max = np.maximum.accumulate(equity_values)

    # Drawdown at each point
    drawdowns = (running_max - equity_values) / running_max

    # Maximum drawdown
    max_drawdown = np.max(drawdowns)

    # Find drawdown duration
    max_dd_duration = 0
    current_dd_start = None

    for i, (eq, run_max) in enumerate(zip(equity_values, running_max)):
        if eq < run_max:
            # In drawdown
            if current_dd_start is None:
                current_dd_start = i
        else:
            # At new high
            if current_dd_start is not None:
                duration = (dates[i] - dates[current_dd_start]).days
                max_dd_duration = max(max_dd_duration, duration)
                current_dd_start = None

    # Check if still in drawdown at end
    if current_dd_start is not None:
        duration = (dates[-1] - dates[current_dd_start]).days
        max_dd_duration = max(max_dd_duration, duration)

    return float(max_drawdown), max_dd_duration


def _calculate_trade_metrics(trade_log: TradeLog) -> tuple[float, float, float]:
    """Calculate trade-based metrics using round-trip matching.

    Matches opening and closing trades by pair_id to calculate
    accurate win rate, profit factor, and average return.

    Args:
        trade_log: Log of all trades

    Returns:
        (win_rate, profit_factor, avg_trade_return)
    """
    if trade_log.num_trades == 0:
        return 0.0, 0.0, 0.0

    # Use round-trip matching from analysis module
    from ptengine.analysis.trade_analysis import match_round_trips

    round_trips = match_round_trips(trade_log, include_open=False)

    if not round_trips:
        return 0.0, 0.0, 0.0

    # Calculate win rate
    winners = [rt for rt in round_trips if rt.pnl > 0]
    losers = [rt for rt in round_trips if rt.pnl < 0]

    win_rate = len(winners) / len(round_trips)

    # Calculate profit factor
    gross_profit = sum(rt.pnl for rt in winners)
    gross_loss = abs(sum(rt.pnl for rt in losers))

    if gross_loss > 0:
        profit_factor = gross_profit / gross_loss
    else:
        profit_factor = float("inf") if gross_profit > 0 else 0.0

    # Calculate average return
    avg_trade_return = sum(rt.return_pct for rt in round_trips) / len(round_trips)

    return win_rate, profit_factor, avg_trade_return


def _empty_metrics(num_trades: int, total_commission: float) -> PerformanceMetrics:
    """Return empty metrics when insufficient data."""
    return PerformanceMetrics(
        total_return=0.0,
        annualized_return=0.0,
        sharpe_ratio=0.0,
        max_drawdown=0.0,
        max_drawdown_duration=0,
        volatility=0.0,
        win_rate=0.0,
        profit_factor=0.0,
        num_trades=num_trades,
        avg_trade_return=0.0,
        total_commission=total_commission,
    )
