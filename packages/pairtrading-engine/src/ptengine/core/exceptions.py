"""Exception hierarchy for pairtrading-engine.

All engine-specific exceptions inherit from PTEngineError for easy catching.
"""

from datetime import date
from typing import Any


class PTEngineError(Exception):
    """Base exception for all pairtrading-engine errors."""

    pass


class InvalidSignalError(PTEngineError):
    """Raised when a strategy returns an invalid signal.

    Attributes:
        message: Error description
        signal: The invalid signal
        reason: Why the signal is invalid
    """

    def __init__(self, message: str, signal: Any = None, reason: str | None = None):
        self.signal = signal
        self.reason = reason
        super().__init__(message)


class InsufficientCapitalError(PTEngineError):
    """Raised when there's not enough capital to execute a trade.

    Attributes:
        required: Capital required for the trade
        available: Capital available
        symbol: Symbol being traded (optional)
    """

    def __init__(
        self,
        required: float,
        available: float,
        symbol: str | None = None,
    ):
        self.required = required
        self.available = available
        self.symbol = symbol
        msg = f"Insufficient capital: required {required:.2f}, available {available:.2f}"
        if symbol:
            msg += f" for {symbol}"
        super().__init__(msg)


class ConstraintViolationError(PTEngineError):
    """Raised when a signal violates a portfolio constraint.

    Attributes:
        constraint_name: Name of the violated constraint
        signal: The signal that violated the constraint
        details: Additional details about the violation
    """

    def __init__(
        self,
        constraint_name: str,
        signal: Any = None,
        details: dict[str, Any] | None = None,
    ):
        self.constraint_name = constraint_name
        self.signal = signal
        self.details = details or {}
        msg = f"Constraint violation: {constraint_name}"
        if details:
            msg += f" - {details}"
        super().__init__(msg)


class StrategyError(PTEngineError):
    """Raised when a strategy encounters an error during execution.

    Attributes:
        strategy_name: Name of the strategy
        current_date: Date when error occurred
        original_error: The underlying exception (if any)
    """

    def __init__(
        self,
        message: str,
        strategy_name: str | None = None,
        current_date: date | None = None,
        original_error: Exception | None = None,
    ):
        self.strategy_name = strategy_name
        self.current_date = current_date
        self.original_error = original_error
        full_msg = message
        if strategy_name:
            full_msg = f"[{strategy_name}] {message}"
        if current_date:
            full_msg = f"{full_msg} (on {current_date})"
        super().__init__(full_msg)


class BacktestError(PTEngineError):
    """Raised when the backtest runner encounters an error.

    Attributes:
        current_date: Date when error occurred
        phase: Phase of backtest (e.g., 'initialization', 'simulation', 'reporting')
    """

    def __init__(
        self,
        message: str,
        current_date: date | None = None,
        phase: str | None = None,
    ):
        self.current_date = current_date
        self.phase = phase
        full_msg = message
        if phase:
            full_msg = f"[{phase}] {message}"
        if current_date:
            full_msg = f"{full_msg} (on {current_date})"
        super().__init__(full_msg)


class ExecutionError(PTEngineError):
    """Raised when trade execution fails.

    Attributes:
        symbol: Symbol that failed to execute
        reason: Why execution failed
    """

    def __init__(self, message: str, symbol: str | None = None, reason: str | None = None):
        self.symbol = symbol
        self.reason = reason
        super().__init__(message)
