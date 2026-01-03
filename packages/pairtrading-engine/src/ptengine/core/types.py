"""Core types for the backtesting engine.

This module defines the fundamental data structures used throughout the engine:
- Signal types (PairSignal, WeightSignal) for strategy outputs
- Position types (Position, PairPosition) for portfolio tracking
- Trade type for executed transactions
"""

from dataclasses import dataclass, field
from datetime import date
from enum import Enum, auto
from typing import Any


class Side(Enum):
    """Trade side (direction)."""

    LONG = auto()
    SHORT = auto()

    def __neg__(self) -> "Side":
        """Return the opposite side."""
        return Side.SHORT if self == Side.LONG else Side.LONG


class SignalType(Enum):
    """Type of pair signal."""

    OPEN_PAIR = auto()  # Open a new pair position
    CLOSE_PAIR = auto()  # Close an existing pair position


@dataclass(frozen=True)
class PairSignal:
    """Signal for discrete pair trades (GGR, Cointegration strategies).

    Used when a strategy wants to open or close a specific pair position
    with explicit long/short legs.

    Attributes:
        signal_type: Whether to open or close the pair
        long_symbol: Symbol to go long
        short_symbol: Symbol to go short
        hedge_ratio: Ratio of short to long notional (default 1.0 = dollar neutral)
        pair_id: Optional identifier for the pair (auto-generated if not provided)
        metadata: Optional additional data (e.g., z-score, entry reason)
    """

    signal_type: SignalType
    long_symbol: str
    short_symbol: str
    hedge_ratio: float = 1.0
    pair_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate signal fields."""
        if self.long_symbol == self.short_symbol:
            raise ValueError("Long and short symbols must be different")
        if self.hedge_ratio <= 0:
            raise ValueError("Hedge ratio must be positive")

    @property
    def symbols(self) -> tuple[str, str]:
        """Return (long_symbol, short_symbol) tuple."""
        return (self.long_symbol, self.short_symbol)

    def get_pair_id(self) -> str:
        """Return the pair_id, generating one if not set."""
        if self.pair_id is not None:
            return self.pair_id
        return f"{self.long_symbol}_{self.short_symbol}"


@dataclass(frozen=True)
class WeightSignal:
    """Signal for continuous weight-based strategies (Kalman, PCA).

    Used when a strategy specifies target portfolio weights for each symbol.
    Weights can be positive (long) or negative (short).

    Attributes:
        weights: Dict mapping symbol to target weight (-1.0 to 1.0 typical)
                 Negative = short, positive = long
        rebalance: If True, rebalance to target weights; if False, adjust incrementally
        metadata: Optional additional data
    """

    weights: dict[str, float]
    rebalance: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate signal fields."""
        if not self.weights:
            raise ValueError("Weights cannot be empty")

    @property
    def symbols(self) -> list[str]:
        """Return list of symbols in the weight signal."""
        return list(self.weights.keys())

    @property
    def net_exposure(self) -> float:
        """Return net exposure (sum of weights)."""
        return sum(self.weights.values())

    @property
    def gross_exposure(self) -> float:
        """Return gross exposure (sum of absolute weights)."""
        return sum(abs(w) for w in self.weights.values())

    def is_dollar_neutral(self, tolerance: float = 0.01) -> bool:
        """Check if weights are approximately dollar neutral."""
        return abs(self.net_exposure) <= tolerance


# Type alias for signal union
Signal = PairSignal | WeightSignal | None


@dataclass
class Position:
    """Represents a position in a single symbol.

    Tracks shares held, entry price, and P&L.

    Attributes:
        symbol: The ticker symbol
        shares: Number of shares (negative = short)
        avg_entry_price: Volume-weighted average entry price
        current_price: Most recent price for marking to market
        realized_pnl: Cumulative realized P&L from closed trades
    """

    symbol: str
    shares: float
    avg_entry_price: float
    current_price: float = 0.0
    realized_pnl: float = 0.0

    @property
    def side(self) -> Side | None:
        """Return position side, or None if flat."""
        if self.shares > 0:
            return Side.LONG
        elif self.shares < 0:
            return Side.SHORT
        return None

    @property
    def is_flat(self) -> bool:
        """Check if position is flat (no shares)."""
        return self.shares == 0

    @property
    def market_value(self) -> float:
        """Return current market value of position."""
        return self.shares * self.current_price

    @property
    def cost_basis(self) -> float:
        """Return cost basis of position."""
        return self.shares * self.avg_entry_price

    @property
    def unrealized_pnl(self) -> float:
        """Return unrealized P&L."""
        return self.market_value - self.cost_basis

    @property
    def total_pnl(self) -> float:
        """Return total P&L (realized + unrealized)."""
        return self.realized_pnl + self.unrealized_pnl

    def update_price(self, price: float) -> None:
        """Update the current market price."""
        self.current_price = price

    def add_shares(self, shares: float, price: float) -> float:
        """Add shares to position, updating avg entry price.

        Args:
            shares: Number of shares to add (negative = reduce/short)
            price: Execution price

        Returns:
            Realized P&L from this transaction (0 if adding to position)
        """
        if self.shares == 0:
            # Opening new position
            self.shares = shares
            self.avg_entry_price = price
            return 0.0

        # Same direction: average in
        if (self.shares > 0 and shares > 0) or (self.shares < 0 and shares < 0):
            total_cost = self.cost_basis + (shares * price)
            self.shares += shares
            self.avg_entry_price = total_cost / self.shares if self.shares != 0 else 0
            return 0.0

        # Opposite direction: realize P&L
        closing_shares = min(abs(shares), abs(self.shares))
        if self.shares > 0:
            # Long position, selling
            realized = closing_shares * (price - self.avg_entry_price)
        else:
            # Short position, buying to cover
            realized = closing_shares * (self.avg_entry_price - price)

        self.realized_pnl += realized

        remaining_new = abs(shares) - closing_shares
        if remaining_new > 0:
            # Flipping sides
            self.shares = remaining_new if shares > 0 else -remaining_new
            self.avg_entry_price = price
        else:
            # Reducing position
            self.shares += shares
            if self.shares == 0:
                self.avg_entry_price = 0.0

        return realized


@dataclass
class PairPosition:
    """Represents a pair position with linked long and short legs.

    Tracks both legs of a pair trade together for proper P&L attribution.

    Attributes:
        pair_id: Unique identifier for this pair
        long_position: The long leg
        short_position: The short leg
        hedge_ratio: Ratio of short to long notional
        entry_date: Date the pair was opened
    """

    pair_id: str
    long_position: Position
    short_position: Position
    hedge_ratio: float
    entry_date: date

    @property
    def symbols(self) -> tuple[str, str]:
        """Return (long_symbol, short_symbol) tuple."""
        return (self.long_position.symbol, self.short_position.symbol)

    @property
    def market_value(self) -> float:
        """Return net market value of the pair."""
        return self.long_position.market_value + self.short_position.market_value

    @property
    def unrealized_pnl(self) -> float:
        """Return combined unrealized P&L."""
        return self.long_position.unrealized_pnl + self.short_position.unrealized_pnl

    @property
    def realized_pnl(self) -> float:
        """Return combined realized P&L."""
        return self.long_position.realized_pnl + self.short_position.realized_pnl

    @property
    def total_pnl(self) -> float:
        """Return total P&L for the pair."""
        return self.long_position.total_pnl + self.short_position.total_pnl

    @property
    def is_closed(self) -> bool:
        """Check if both legs are flat."""
        return self.long_position.is_flat and self.short_position.is_flat

    def update_prices(self, long_price: float, short_price: float) -> None:
        """Update prices for both legs."""
        self.long_position.update_price(long_price)
        self.short_position.update_price(short_price)


@dataclass(frozen=True)
class Trade:
    """Represents an executed trade.

    Immutable record of a single transaction.

    Attributes:
        date: Execution date
        symbol: Ticker symbol
        side: LONG (buy) or SHORT (sell/short)
        shares: Number of shares (always positive)
        price: Execution price
        commission: Commission paid
        pair_id: Optional pair identifier if part of a pair trade
    """

    date: date
    symbol: str
    side: Side
    shares: float
    price: float
    commission: float = 0.0
    pair_id: str | None = None

    def __post_init__(self) -> None:
        """Validate trade fields."""
        if self.shares <= 0:
            raise ValueError("Trade shares must be positive")
        if self.price <= 0:
            raise ValueError("Trade price must be positive")
        if self.commission < 0:
            raise ValueError("Commission cannot be negative")

    @property
    def notional(self) -> float:
        """Return trade notional value (shares * price)."""
        return self.shares * self.price

    @property
    def total_cost(self) -> float:
        """Return total cost including commission."""
        return self.notional + self.commission

    @property
    def signed_shares(self) -> float:
        """Return signed shares (negative for short/sell)."""
        return self.shares if self.side == Side.LONG else -self.shares
