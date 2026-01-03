"""Backtest configuration."""

from dataclasses import dataclass, field
from datetime import date
from typing import TYPE_CHECKING

from ptengine.core.constants import (
    DEFAULT_INITIAL_CAPITAL,
    DEFAULT_CAPITAL_PER_PAIR,
    DEFAULT_PRICE_COLUMN,
)

if TYPE_CHECKING:
    from ptengine.commission.base import CommissionModel


@dataclass
class BacktestConfig:
    """Configuration for a backtest run.

    Attributes:
        start_date: First trading day of the simulation
        end_date: Last trading day of the simulation
        initial_capital: Starting cash balance
        capital_per_pair: Capital allocated to each pair trade
        price_column: Column name for execution prices (default: 'adj_close')
        commission_model: Model for calculating trade commissions
    """

    start_date: date
    end_date: date
    initial_capital: float = DEFAULT_INITIAL_CAPITAL
    capital_per_pair: float = DEFAULT_CAPITAL_PER_PAIR
    price_column: str = DEFAULT_PRICE_COLUMN
    commission_model: "CommissionModel | None" = None

    def __post_init__(self) -> None:
        """Validate configuration."""
        if self.start_date >= self.end_date:
            raise ValueError("start_date must be before end_date")
        if self.initial_capital <= 0:
            raise ValueError("initial_capital must be positive")
        if self.capital_per_pair <= 0:
            raise ValueError("capital_per_pair must be positive")
        if self.capital_per_pair > self.initial_capital:
            raise ValueError("capital_per_pair cannot exceed initial_capital")

    @property
    def duration_days(self) -> int:
        """Return calendar days in backtest period."""
        return (self.end_date - self.start_date).days
