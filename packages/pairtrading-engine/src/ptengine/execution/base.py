"""Base execution model protocol.

Defines the interface that all execution models must implement.
"""

from datetime import date
from typing import Protocol

from ptengine.core.types import PairSignal, Trade, WeightSignal
from ptengine.portfolio.portfolio import Portfolio


class ExecutionModel(Protocol):
    """Protocol for trade execution models.

    Execution models determine how signals are converted to trades.
    Different models can implement various fill assumptions:
    - Close price (V1)
    - VWAP
    - Slippage models
    - Partial fills
    """

    def execute_pair_signal(
        self,
        signal: PairSignal,
        current_date: date,
        prices: dict[str, float],
        portfolio: Portfolio,
        capital_per_pair: float,
    ) -> list[Trade]:
        """Execute a pair signal.

        Args:
            signal: The pair signal to execute
            current_date: Current simulation date
            prices: Current prices for all symbols
            portfolio: Current portfolio state
            capital_per_pair: Capital to allocate per pair

        Returns:
            List of trades executed (typically 2 for open, 2 for close)
        """
        ...

    def execute_weight_signal(
        self,
        signal: WeightSignal,
        current_date: date,
        prices: dict[str, float],
        portfolio: Portfolio,
    ) -> list[Trade]:
        """Execute a weight signal.

        Args:
            signal: The weight signal to execute
            current_date: Current simulation date
            prices: Current prices for all symbols
            portfolio: Current portfolio state

        Returns:
            List of trades to rebalance to target weights
        """
        ...
