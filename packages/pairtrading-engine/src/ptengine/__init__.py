"""pairtrading-engine: Backtesting engine for pair trading strategies.

Usage:
    from ptengine import BacktestRunner, BacktestConfig
    from ptengine.strategy import BaseStrategy
    from ptengine.core.types import PairSignal, WeightSignal, SignalType

    class MyStrategy(BaseStrategy):
        def on_bar(self, current_date, pit_data):
            # Your strategy logic here
            return None

    config = BacktestConfig(
        start_date=date(2020, 1, 1),
        end_date=date(2023, 12, 31),
        initial_capital=100_000,
    )

    result = BacktestRunner(strategy, config).run(pit_data)
    print(result.summary())
"""

from ptengine.core.types import (
    Side,
    SignalType,
    PairSignal,
    WeightSignal,
    Position,
    PairPosition,
    Trade,
    Signal,
)
from ptengine.core.exceptions import (
    PTEngineError,
    InvalidSignalError,
    InsufficientCapitalError,
    ConstraintViolationError,
    StrategyError,
    BacktestError,
    ExecutionError,
)
from ptengine.core.constants import (
    DEFAULT_INITIAL_CAPITAL,
    DEFAULT_CAPITAL_PER_PAIR,
    DEFAULT_PRICE_COLUMN,
    TRADING_DAYS_PER_YEAR,
)

# Backtest components
from ptengine.backtest.config import BacktestConfig
from ptengine.backtest.runner import BacktestRunner

# Portfolio
from ptengine.portfolio.portfolio import Portfolio

# Strategy
from ptengine.strategy.base import Strategy, BaseStrategy

# Results
from ptengine.results.report import BacktestResult
from ptengine.results.metrics import PerformanceMetrics
from ptengine.results.trades import TradeLog

# Execution
from ptengine.execution.simple import ClosePriceExecution

# Commission
from ptengine.commission.models import (
    ZeroCommission,
    PerShareCommission,
    PercentageCommission,
    IBKRTieredCommission,
)

# Built-in strategies
from ptengine.strategies.ggr_distance import GGRDistanceStrategy

__version__ = "0.1.0"

__all__ = [
    # Version
    "__version__",
    # Enums
    "Side",
    "SignalType",
    # Signal types
    "PairSignal",
    "WeightSignal",
    "Signal",
    # Position types
    "Position",
    "PairPosition",
    "Trade",
    # Exceptions
    "PTEngineError",
    "InvalidSignalError",
    "InsufficientCapitalError",
    "ConstraintViolationError",
    "StrategyError",
    "BacktestError",
    "ExecutionError",
    # Constants
    "DEFAULT_INITIAL_CAPITAL",
    "DEFAULT_CAPITAL_PER_PAIR",
    "DEFAULT_PRICE_COLUMN",
    "TRADING_DAYS_PER_YEAR",
    # Backtest
    "BacktestConfig",
    "BacktestRunner",
    # Portfolio
    "Portfolio",
    # Strategy
    "Strategy",
    "BaseStrategy",
    # Results
    "BacktestResult",
    "PerformanceMetrics",
    "TradeLog",
    # Execution
    "ClosePriceExecution",
    # Commission
    "ZeroCommission",
    "PerShareCommission",
    "PercentageCommission",
    "IBKRTieredCommission",
    # Strategies
    "GGRDistanceStrategy",
]
