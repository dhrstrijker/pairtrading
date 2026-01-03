"""Trade logging and analysis."""

from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import date

import pandas as pd

from ptengine.core.types import Side, Trade


@dataclass
class TradeLog:
    """Log of all trades executed during a backtest.

    Provides methods for analyzing trade history.
    """

    _trades: list[Trade] = field(default_factory=list)

    def add_trade(self, trade: Trade) -> None:
        """Add a trade to the log."""
        self._trades.append(trade)

    def clear(self) -> None:
        """Clear all trades from the log."""
        self._trades.clear()

    def __len__(self) -> int:
        """Return number of trades."""
        return len(self._trades)

    def __iter__(self) -> Iterator[Trade]:
        """Iterate over trades."""
        return iter(self._trades)

    @property
    def trades(self) -> list[Trade]:
        """Return copy of trades list."""
        return self._trades.copy()

    @property
    def num_trades(self) -> int:
        """Return total number of trades."""
        return len(self._trades)

    @property
    def num_long_trades(self) -> int:
        """Return number of long (buy) trades."""
        return sum(1 for t in self._trades if t.side == Side.LONG)

    @property
    def num_short_trades(self) -> int:
        """Return number of short (sell) trades."""
        return sum(1 for t in self._trades if t.side == Side.SHORT)

    @property
    def total_commission(self) -> float:
        """Return total commission paid."""
        return sum(t.commission for t in self._trades)

    @property
    def total_notional(self) -> float:
        """Return total notional value traded."""
        return sum(t.notional for t in self._trades)

    def get_trades_for_symbol(self, symbol: str) -> list[Trade]:
        """Get trades for a specific symbol."""
        return [t for t in self._trades if t.symbol == symbol]

    def get_trades_for_pair(self, pair_id: str) -> list[Trade]:
        """Get trades for a specific pair."""
        return [t for t in self._trades if t.pair_id == pair_id]

    def get_trades_on_date(self, trade_date: date) -> list[Trade]:
        """Get trades executed on a specific date."""
        return [t for t in self._trades if t.date == trade_date]

    def get_trades_in_range(self, start_date: date, end_date: date) -> list[Trade]:
        """Get trades executed within a date range."""
        return [t for t in self._trades if start_date <= t.date <= end_date]

    def to_dataframe(self) -> pd.DataFrame:
        """Convert trade log to a pandas DataFrame.

        Returns:
            DataFrame with columns:
            - date, symbol, side, shares, price, commission, notional, pair_id
        """
        if not self._trades:
            return pd.DataFrame(columns=[
                "date", "symbol", "side", "shares", "price",
                "commission", "notional", "pair_id"
            ])

        data = [
            {
                "date": t.date,
                "symbol": t.symbol,
                "side": t.side.name,
                "shares": t.shares,
                "price": t.price,
                "commission": t.commission,
                "notional": t.notional,
                "pair_id": t.pair_id,
            }
            for t in self._trades
        ]

        return pd.DataFrame(data)

    def get_unique_symbols(self) -> set[str]:
        """Get set of unique symbols traded."""
        return {t.symbol for t in self._trades}

    def get_unique_pairs(self) -> set[str]:
        """Get set of unique pair IDs traded."""
        return {t.pair_id for t in self._trades if t.pair_id is not None}
