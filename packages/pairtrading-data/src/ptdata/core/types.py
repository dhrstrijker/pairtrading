"""Core type definitions for pairtrading-data.

Important: Decimal vs Float
- Storage/API layer: Uses Decimal for exact representation (no floating point drift)
- Computation layer: When passing to numpy/scipy/statsmodels, convert to float64
- The conversion boundary is documented - engine/strategy projects handle the cast
"""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import Enum, auto
from typing import Any


class CorporateActionType(Enum):
    """Types of corporate actions that affect price data."""

    SPLIT = auto()
    DIVIDEND = auto()
    DELISTING = auto()
    MERGER = auto()


@dataclass(frozen=True)
class PriceBar:
    """
    Immutable price bar - single day of OHLCV data.

    Uses Decimal for exact representation. Convert to float64
    when passing to numpy/scipy for computation.

    Attributes:
        symbol: Ticker symbol
        date: Trading date
        open: Opening price
        high: Highest price
        low: Lowest price
        close: Closing price
        adj_close: Split and dividend adjusted closing price
        volume: Trading volume
    """

    symbol: str
    date: date
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    adj_close: Decimal
    volume: int

    def __post_init__(self) -> None:
        """Validate price bar data."""
        if self.high < self.low:
            raise ValueError(f"High ({self.high}) cannot be less than Low ({self.low})")
        if self.open < Decimal(0) or self.close < Decimal(0):
            raise ValueError("Prices cannot be negative")
        if self.volume < 0:
            raise ValueError("Volume cannot be negative")

    def to_float_dict(self) -> dict[str, Any]:
        """Convert to float dict for DataFrame construction.

        Use this when you need to work with pandas/numpy which require floats.
        """
        return {
            "symbol": self.symbol,
            "date": self.date,
            "open": float(self.open),
            "high": float(self.high),
            "low": float(self.low),
            "close": float(self.close),
            "adj_close": float(self.adj_close),
            "volume": self.volume,
        }

    @classmethod
    def from_float_dict(cls, data: dict[str, Any]) -> "PriceBar":
        """Create PriceBar from a dict with float values.

        Converts floats to Decimal for internal storage.
        """
        d = data["date"] if isinstance(data["date"], date) else data["date"].date()
        return cls(
            symbol=data["symbol"],
            date=d,
            open=Decimal(str(data["open"])),
            high=Decimal(str(data["high"])),
            low=Decimal(str(data["low"])),
            close=Decimal(str(data["close"])),
            adj_close=Decimal(str(data["adj_close"])),
            volume=int(data["volume"]),
        )


@dataclass(frozen=True)
class CorporateAction:
    """Record of a corporate action that affects price data.

    Attributes:
        symbol: Ticker symbol
        date: Date of the corporate action
        action_type: Type of action (split, dividend, etc.)
        value: Action-specific value:
            - SPLIT: Split ratio (e.g., 2.0 for 2-for-1)
            - DIVIDEND: Dividend amount per share
            - DELISTING: Final trading price
            - MERGER: Exchange ratio
        description: Optional description of the action
    """

    symbol: str
    date: date
    action_type: CorporateActionType
    value: Decimal
    description: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "symbol": self.symbol,
            "date": self.date.isoformat(),
            "action_type": self.action_type.name,
            "value": str(self.value),
            "description": self.description,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CorporateAction":
        """Create CorporateAction from a dictionary."""
        d = (
            date.fromisoformat(data["date"])
            if isinstance(data["date"], str)
            else data["date"]
        )
        return cls(
            symbol=data["symbol"],
            date=d,
            action_type=CorporateActionType[data["action_type"]],
            value=Decimal(data["value"]),
            description=data.get("description", ""),
        )
