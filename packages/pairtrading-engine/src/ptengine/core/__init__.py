"""Core types and utilities for pairtrading-engine."""

from ptengine.core.constants import (
    DEFAULT_CAPITAL_PER_PAIR,
    DEFAULT_INITIAL_CAPITAL,
    DEFAULT_PRICE_COLUMN,
    TRADING_DAYS_PER_YEAR,
)
from ptengine.core.exceptions import (
    ConstraintViolationError,
    InsufficientCapitalError,
    InvalidSignalError,
    PTEngineError,
    StrategyError,
)
from ptengine.core.types import (
    PairPosition,
    PairSignal,
    Position,
    Side,
    Signal,
    SignalType,
    Trade,
    WeightSignal,
)

__all__ = [
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
    # Constants
    "DEFAULT_INITIAL_CAPITAL",
    "DEFAULT_CAPITAL_PER_PAIR",
    "DEFAULT_PRICE_COLUMN",
    "TRADING_DAYS_PER_YEAR",
]
