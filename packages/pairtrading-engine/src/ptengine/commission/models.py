"""Commission model implementations.

Provides various commission structures for realistic backtesting.
"""

from dataclasses import dataclass


@dataclass
class ZeroCommission:
    """No commission (for testing or commission-free brokers)."""

    def calculate(self, shares: float, price: float) -> float:
        """Return zero commission."""
        return 0.0


@dataclass
class PerShareCommission:
    """Per-share commission model.

    Common for institutional trading and some retail brokers.

    Attributes:
        rate: Commission per share
        minimum: Minimum commission per trade
        maximum: Maximum commission per trade (None = no max)
    """

    rate: float = 0.005  # $0.005 per share
    minimum: float = 1.0  # $1 minimum
    maximum: float | None = None  # No maximum by default

    def calculate(self, shares: float, price: float) -> float:
        """Calculate per-share commission."""
        commission = abs(shares) * self.rate
        commission = max(commission, self.minimum)
        if self.maximum is not None:
            commission = min(commission, self.maximum)
        return commission


@dataclass
class PercentageCommission:
    """Percentage-based commission model.

    Commission is a percentage of trade value.

    Attributes:
        rate: Commission rate (0.001 = 0.1%)
        minimum: Minimum commission per trade
    """

    rate: float = 0.001  # 0.1% (10 basis points)
    minimum: float = 1.0  # $1 minimum

    def calculate(self, shares: float, price: float) -> float:
        """Calculate percentage commission."""
        notional = abs(shares) * price
        commission = notional * self.rate
        return max(commission, self.minimum)


@dataclass
class IBKRTieredCommission:
    """Interactive Brokers tiered commission structure.

    Simplified model based on IBKR's tiered pricing for US stocks.
    Actual IBKR pricing has volume tiers; this uses a representative rate.

    Attributes:
        rate_per_share: Base rate per share
        minimum: Minimum commission
        maximum_pct: Maximum as percentage of trade value
        exchange_fee: Additional per-share exchange/regulatory fee
    """

    rate_per_share: float = 0.0035  # $0.0035 per share
    minimum: float = 0.35  # $0.35 minimum
    maximum_pct: float = 0.01  # 1% max of trade value
    exchange_fee: float = 0.0003  # $0.0003 per share regulatory fees

    def calculate(self, shares: float, price: float) -> float:
        """Calculate IBKR-style tiered commission."""
        abs_shares = abs(shares)
        notional = abs_shares * price

        # Base commission
        commission = abs_shares * self.rate_per_share

        # Add exchange/regulatory fees
        commission += abs_shares * self.exchange_fee

        # Apply minimum
        commission = max(commission, self.minimum)

        # Apply maximum (percentage of trade value)
        max_commission = notional * self.maximum_pct
        commission = min(commission, max_commission)

        return commission
