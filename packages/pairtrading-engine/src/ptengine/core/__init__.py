"""Core types and utilities for pairtrading-engine."""

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
)
from ptengine.core.constants import (
    DEFAULT_INITIAL_CAPITAL,
    DEFAULT_CAPITAL_PER_PAIR,
    DEFAULT_PRICE_COLUMN,
    TRADING_DAYS_PER_YEAR,
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
