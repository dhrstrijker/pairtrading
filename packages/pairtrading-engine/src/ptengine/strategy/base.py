"""Strategy protocol and base implementation.

Defines the interface that all trading strategies must implement.
The Strategy protocol receives PointInTimeDataFrame from pairtrading-data
to ensure no look-ahead bias.
"""

from abc import ABC, abstractmethod
from datetime import date
from typing import Protocol, runtime_checkable

from ptdata.validation import PointInTimeDataFrame

from ptengine.core.types import Signal, Trade


@runtime_checkable
class Strategy(Protocol):
    """Protocol defining the strategy interface.

    Strategies are called once per trading day with point-in-time data.
    They return signals (PairSignal, WeightSignal, or None) which the
    backtest runner executes.

    The key integration point is `on_bar`, which receives a PointInTimeDataFrame
    from pairtrading-data. This wrapper ensures strategies can only access
    data that would have been available on the current simulation date,
    preventing look-ahead bias.
    """

    @property
    def name(self) -> str:
        """Return strategy name for identification."""
        ...

    def on_bar(self, current_date: date, pit_data: PointInTimeDataFrame) -> Signal:
        """Called for each trading day.

        This is the main strategy logic entry point. Analyze the available
        data and return a signal if action should be taken.

        Args:
            current_date: Current simulation date
            pit_data: PointInTimeDataFrame from pairtrading-data
                     - pit_data.get_data() returns only past data
                     - pit_data.for_symbol(symbol) filters by symbol
                     - pit_data.get_latest(symbol) gets most recent row
                     - Raises LookAheadBiasError if accessing future data

        Returns:
            PairSignal: To open/close a pair position
            WeightSignal: To rebalance to target weights
            None: To take no action
        """
        ...

    def on_fill(self, trade: Trade) -> None:
        """Called when a trade is executed (optional).

        Override to track fills, update internal state, or implement
        position-aware logic.

        Args:
            trade: The executed trade
        """
        ...

    def on_start(self, start_date: date, end_date: date) -> None:
        """Called before backtest starts (optional).

        Override to perform initialization that depends on backtest dates.

        Args:
            start_date: Backtest start date
            end_date: Backtest end date
        """
        ...

    def on_end(self) -> None:
        """Called after backtest ends (optional).

        Override to perform cleanup or finalization.
        """
        ...


class BaseStrategy(ABC):
    """Abstract base class for strategies.

    Provides default implementations for optional callbacks.
    Subclass this and implement `name` and `on_bar`.

    Example:
        class MyPairStrategy(BaseStrategy):
            def __init__(self, symbol_a: str, symbol_b: str):
                super().__init__()
                self.symbol_a = symbol_a
                self.symbol_b = symbol_b
                self._position_open = False

            @property
            def name(self) -> str:
                return f"pair_{self.symbol_a}_{self.symbol_b}"

            def on_bar(self, current_date, pit_data):
                data_a = pit_data.for_symbol(self.symbol_a)
                data_b = pit_data.for_symbol(self.symbol_b)

                if len(data_a) < 60:
                    return None

                # Calculate spread z-score
                z_score = self._calculate_zscore(data_a, data_b)

                if z_score > 2.0 and not self._position_open:
                    return PairSignal(
                        signal_type=SignalType.OPEN_PAIR,
                        long_symbol=self.symbol_b,
                        short_symbol=self.symbol_a,
                    )
                return None

            def on_fill(self, trade):
                if trade.pair_id:
                    self._position_open = True
    """

    def __init__(self) -> None:
        """Initialize base strategy."""
        self._trades: list[Trade] = []

    @property
    @abstractmethod
    def name(self) -> str:
        """Return strategy name."""
        ...

    @abstractmethod
    def on_bar(self, current_date: date, pit_data: PointInTimeDataFrame) -> Signal:
        """Process a bar and optionally return a signal."""
        ...

    def on_fill(self, trade: Trade) -> None:
        """Record trade when filled (default: append to trade list)."""
        self._trades.append(trade)

    def on_start(self, start_date: date, end_date: date) -> None:  # noqa: B027
        """Called before backtest starts (default: no-op)."""
        pass

    def on_end(self) -> None:  # noqa: B027
        """Called after backtest ends (default: no-op)."""
        pass

    @property
    def trades(self) -> list[Trade]:
        """Return list of trades filled for this strategy."""
        return self._trades.copy()

    def reset(self) -> None:
        """Reset strategy state for a new backtest run."""
        self._trades.clear()
