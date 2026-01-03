"""Portfolio state management.

The Portfolio class tracks all positions, cash, and P&L throughout a backtest.
It supports both individual positions and linked pair positions.
"""

from dataclasses import dataclass, field
from datetime import date
from typing import Iterator

from ptengine.core.types import Position, PairPosition, Trade, Side
from ptengine.core.exceptions import InsufficientCapitalError
from ptengine.core.constants import DEFAULT_INITIAL_CAPITAL


@dataclass
class Portfolio:
    """Manages portfolio state during backtesting.

    Tracks:
    - Cash balance
    - Individual positions (for weight-based strategies)
    - Pair positions (for discrete pair strategies)
    - Equity curve over time
    - Cumulative realized P&L

    Attributes:
        initial_capital: Starting capital
        cash: Current cash balance
        positions: Dict of symbol -> Position for individual holdings
        pair_positions: Dict of pair_id -> PairPosition for pair trades
        equity_curve: List of (date, equity) tuples
    """

    initial_capital: float = DEFAULT_INITIAL_CAPITAL
    cash: float = field(init=False)
    positions: dict[str, Position] = field(default_factory=dict)
    pair_positions: dict[str, PairPosition] = field(default_factory=dict)
    equity_curve: list[tuple[date, float]] = field(default_factory=list)
    _cumulative_commission: float = field(default=0.0, init=False)

    def __post_init__(self) -> None:
        """Initialize cash to initial capital."""
        self.cash = self.initial_capital

    @property
    def equity(self) -> float:
        """Return total portfolio equity (cash + positions market value)."""
        position_value = sum(p.market_value for p in self.positions.values())
        pair_value = sum(pp.market_value for pp in self.pair_positions.values())
        return self.cash + position_value + pair_value

    @property
    def gross_exposure(self) -> float:
        """Return gross exposure (sum of absolute position values)."""
        position_exposure = sum(abs(p.market_value) for p in self.positions.values())
        pair_exposure = sum(
            abs(pp.long_position.market_value) + abs(pp.short_position.market_value)
            for pp in self.pair_positions.values()
        )
        return position_exposure + pair_exposure

    @property
    def net_exposure(self) -> float:
        """Return net exposure (sum of position values, signed)."""
        position_exposure = sum(p.market_value for p in self.positions.values())
        pair_exposure = sum(pp.market_value for pp in self.pair_positions.values())
        return position_exposure + pair_exposure

    @property
    def realized_pnl(self) -> float:
        """Return total realized P&L from all positions."""
        position_pnl = sum(p.realized_pnl for p in self.positions.values())
        pair_pnl = sum(pp.realized_pnl for pp in self.pair_positions.values())
        return position_pnl + pair_pnl

    @property
    def unrealized_pnl(self) -> float:
        """Return total unrealized P&L from all positions."""
        position_pnl = sum(p.unrealized_pnl for p in self.positions.values())
        pair_pnl = sum(pp.unrealized_pnl for pp in self.pair_positions.values())
        return position_pnl + pair_pnl

    @property
    def total_pnl(self) -> float:
        """Return total P&L (realized + unrealized)."""
        return self.realized_pnl + self.unrealized_pnl

    @property
    def total_commission(self) -> float:
        """Return total commission paid."""
        return self._cumulative_commission

    @property
    def num_positions(self) -> int:
        """Return number of non-zero positions."""
        return sum(1 for p in self.positions.values() if not p.is_flat)

    @property
    def num_pair_positions(self) -> int:
        """Return number of open pair positions."""
        return sum(1 for pp in self.pair_positions.values() if not pp.is_closed)

    def update_prices(self, prices: dict[str, float]) -> None:
        """Update current prices for all positions.

        Args:
            prices: Dict mapping symbol to current price
        """
        for symbol, position in self.positions.items():
            if symbol in prices:
                position.update_price(prices[symbol])

        for pair_position in self.pair_positions.values():
            long_symbol = pair_position.long_position.symbol
            short_symbol = pair_position.short_position.symbol
            if long_symbol in prices and short_symbol in prices:
                pair_position.update_prices(prices[long_symbol], prices[short_symbol])

    def record_equity(self, current_date: date) -> None:
        """Record current equity to the equity curve.

        Args:
            current_date: Current simulation date
        """
        self.equity_curve.append((current_date, self.equity))

    def execute_trade(self, trade: Trade) -> float:
        """Execute a trade, updating positions and cash.

        Args:
            trade: The trade to execute

        Returns:
            Realized P&L from the trade (0 if opening position)

        Raises:
            InsufficientCapitalError: If not enough cash for the trade
        """
        # Check cash for long trades
        if trade.side == Side.LONG:
            required = trade.total_cost
            if required > self.cash:
                raise InsufficientCapitalError(required, self.cash, trade.symbol)

        # Get or create position
        if trade.symbol not in self.positions:
            self.positions[trade.symbol] = Position(
                symbol=trade.symbol,
                shares=0,
                avg_entry_price=0.0,
                current_price=trade.price,
            )

        position = self.positions[trade.symbol]
        realized_pnl = position.add_shares(trade.signed_shares, trade.price)

        # Update cash
        if trade.side == Side.LONG:
            self.cash -= trade.total_cost
        else:
            # Short sale or selling long: receive cash
            self.cash += trade.notional - trade.commission

        self._cumulative_commission += trade.commission

        # Clean up flat positions
        if position.is_flat:
            del self.positions[trade.symbol]

        return realized_pnl

    def open_pair(
        self,
        pair_id: str,
        long_trade: Trade,
        short_trade: Trade,
        hedge_ratio: float,
        entry_date: date,
    ) -> None:
        """Open a new pair position.

        Args:
            pair_id: Unique identifier for the pair
            long_trade: Trade for the long leg
            short_trade: Trade for the short leg
            hedge_ratio: Ratio of short to long notional
            entry_date: Date the pair is opened

        Raises:
            InsufficientCapitalError: If not enough cash
        """
        # Check capital for long leg
        required = long_trade.total_cost
        if required > self.cash:
            raise InsufficientCapitalError(required, self.cash, long_trade.symbol)

        # Create positions
        long_position = Position(
            symbol=long_trade.symbol,
            shares=long_trade.shares,
            avg_entry_price=long_trade.price,
            current_price=long_trade.price,
        )

        short_position = Position(
            symbol=short_trade.symbol,
            shares=-short_trade.shares,  # Negative for short
            avg_entry_price=short_trade.price,
            current_price=short_trade.price,
        )

        # Create pair position
        pair_position = PairPosition(
            pair_id=pair_id,
            long_position=long_position,
            short_position=short_position,
            hedge_ratio=hedge_ratio,
            entry_date=entry_date,
        )

        self.pair_positions[pair_id] = pair_position

        # Update cash: pay for long, receive for short
        self.cash -= long_trade.total_cost
        self.cash += short_trade.notional - short_trade.commission

        self._cumulative_commission += long_trade.commission + short_trade.commission

    def close_pair(self, pair_id: str, long_trade: Trade, short_trade: Trade) -> float:
        """Close an existing pair position.

        Args:
            pair_id: ID of the pair to close
            long_trade: Trade to close long leg (sell)
            short_trade: Trade to close short leg (buy to cover)

        Returns:
            Total realized P&L from closing the pair

        Raises:
            KeyError: If pair_id not found
        """
        if pair_id not in self.pair_positions:
            raise KeyError(f"Pair position not found: {pair_id}")

        pair_position = self.pair_positions[pair_id]

        # Calculate P&L
        long_pnl = pair_position.long_position.add_shares(-long_trade.shares, long_trade.price)
        short_pnl = pair_position.short_position.add_shares(short_trade.shares, short_trade.price)
        total_pnl = long_pnl + short_pnl

        # Update cash: receive from selling long, pay to cover short
        self.cash += long_trade.notional - long_trade.commission
        self.cash -= short_trade.total_cost

        self._cumulative_commission += long_trade.commission + short_trade.commission

        # Remove closed pair
        del self.pair_positions[pair_id]

        return total_pnl

    def get_position(self, symbol: str) -> Position | None:
        """Get position for a symbol, or None if not held."""
        return self.positions.get(symbol)

    def get_pair_position(self, pair_id: str) -> PairPosition | None:
        """Get pair position by ID, or None if not found."""
        return self.pair_positions.get(pair_id)

    def has_pair(self, pair_id: str) -> bool:
        """Check if a pair position exists."""
        return pair_id in self.pair_positions

    def iter_positions(self) -> Iterator[Position]:
        """Iterate over all individual positions."""
        return iter(self.positions.values())

    def iter_pair_positions(self) -> Iterator[PairPosition]:
        """Iterate over all pair positions."""
        return iter(self.pair_positions.values())

    def get_all_symbols(self) -> set[str]:
        """Get set of all symbols with positions."""
        symbols = set(self.positions.keys())
        for pp in self.pair_positions.values():
            symbols.add(pp.long_position.symbol)
            symbols.add(pp.short_position.symbol)
        return symbols

    def reset(self) -> None:
        """Reset portfolio to initial state."""
        self.cash = self.initial_capital
        self.positions.clear()
        self.pair_positions.clear()
        self.equity_curve.clear()
        self._cumulative_commission = 0.0
