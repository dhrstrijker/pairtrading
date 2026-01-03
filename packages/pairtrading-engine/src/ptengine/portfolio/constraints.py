"""Portfolio constraints for signal validation.

Constraints validate and optionally adjust signals before execution.
They can enforce risk limits, neutrality requirements, and position limits.
"""

from dataclasses import dataclass
from typing import Protocol

from ptengine.core.types import PairSignal, WeightSignal, Signal
from ptengine.core.constants import (
    DEFAULT_MAX_POSITION_PCT,
    DEFAULT_MAX_GROSS_EXPOSURE,
    DEFAULT_NEUTRALITY_TOLERANCE,
)
from ptengine.core.exceptions import ConstraintViolationError
from ptengine.portfolio.portfolio import Portfolio


class Constraint(Protocol):
    """Protocol for portfolio constraints.

    Constraints can validate signals and optionally adjust them
    to meet requirements.
    """

    @property
    def name(self) -> str:
        """Return constraint name."""
        ...

    def validate(self, signal: Signal, portfolio: Portfolio) -> bool:
        """Check if signal satisfies the constraint.

        Args:
            signal: Signal to validate
            portfolio: Current portfolio state

        Returns:
            True if valid, False otherwise
        """
        ...

    def adjust(self, signal: Signal, portfolio: Portfolio) -> Signal:
        """Adjust signal to meet constraint (if possible).

        Args:
            signal: Signal to adjust
            portfolio: Current portfolio state

        Returns:
            Adjusted signal (may be same as input if no adjustment needed)

        Raises:
            ConstraintViolationError: If signal cannot be adjusted
        """
        ...


@dataclass
class DollarNeutralConstraint:
    """Enforce dollar neutrality for weight signals.

    Weight signals should have net exposure close to zero.

    Attributes:
        tolerance: Maximum allowed absolute net exposure
        auto_adjust: If True, automatically normalize weights
    """

    tolerance: float = DEFAULT_NEUTRALITY_TOLERANCE
    auto_adjust: bool = True

    @property
    def name(self) -> str:
        return "dollar_neutral"

    def validate(self, signal: Signal, portfolio: Portfolio) -> bool:
        """Check if signal is dollar neutral within tolerance."""
        if signal is None:
            return True

        if isinstance(signal, PairSignal):
            # Pair signals are inherently dollar neutral by design
            return True

        if isinstance(signal, WeightSignal):
            return abs(signal.net_exposure) <= self.tolerance

        return True

    def adjust(self, signal: Signal, portfolio: Portfolio) -> Signal:
        """Adjust weight signal to be dollar neutral."""
        if signal is None:
            return None

        if isinstance(signal, PairSignal):
            return signal  # Already neutral

        if isinstance(signal, WeightSignal):
            if self.validate(signal, portfolio):
                return signal

            if not self.auto_adjust:
                raise ConstraintViolationError(
                    self.name,
                    signal=signal,
                    details={"net_exposure": signal.net_exposure},
                )

            # Normalize weights to be dollar neutral
            adjusted_weights = self._normalize_weights(signal.weights)
            return WeightSignal(
                weights=adjusted_weights,
                rebalance=signal.rebalance,
                metadata=signal.metadata,
            )

        return signal

    def _normalize_weights(self, weights: dict[str, float]) -> dict[str, float]:
        """Normalize weights to sum to zero.

        Adjusts all weights proportionally to achieve neutrality.
        """
        if not weights:
            return weights

        net = sum(weights.values())
        if abs(net) <= self.tolerance:
            return weights

        # Split into long and short
        longs = {k: v for k, v in weights.items() if v > 0}
        shorts = {k: v for k, v in weights.items() if v < 0}

        long_sum = sum(longs.values())
        short_sum = abs(sum(shorts.values()))

        if long_sum == 0 or short_sum == 0:
            # All same direction - can't neutralize
            return weights

        # Scale to match
        target = (long_sum + short_sum) / 2
        long_scale = target / long_sum
        short_scale = target / short_sum

        adjusted = {}
        for k, v in longs.items():
            adjusted[k] = v * long_scale
        for k, v in shorts.items():
            adjusted[k] = v * short_scale

        return adjusted


@dataclass
class PositionLimitConstraint:
    """Enforce maximum position sizes.

    Limits individual position size and total gross exposure.

    Attributes:
        max_position_pct: Maximum weight for any single position
        max_gross_exposure: Maximum total gross exposure
    """

    max_position_pct: float = DEFAULT_MAX_POSITION_PCT
    max_gross_exposure: float = DEFAULT_MAX_GROSS_EXPOSURE

    @property
    def name(self) -> str:
        return "position_limit"

    def validate(self, signal: Signal, portfolio: Portfolio) -> bool:
        """Check if signal respects position limits."""
        if signal is None:
            return True

        if isinstance(signal, PairSignal):
            # For pairs, check if we'd exceed limits
            # This is a simplified check
            return True

        if isinstance(signal, WeightSignal):
            # Check individual position limits
            for weight in signal.weights.values():
                if abs(weight) > self.max_position_pct:
                    return False

            # Check gross exposure
            if signal.gross_exposure > self.max_gross_exposure:
                return False

            return True

        return True

    def adjust(self, signal: Signal, portfolio: Portfolio) -> Signal:
        """Adjust signal to respect position limits."""
        if signal is None:
            return None

        if isinstance(signal, PairSignal):
            if not self.validate(signal, portfolio):
                raise ConstraintViolationError(
                    self.name,
                    signal=signal,
                    details={"reason": "pair_exceeds_limits"},
                )
            return signal

        if isinstance(signal, WeightSignal):
            if self.validate(signal, portfolio):
                return signal

            # Clip individual positions
            adjusted_weights = {}
            for symbol, weight in signal.weights.items():
                if weight > self.max_position_pct:
                    adjusted_weights[symbol] = self.max_position_pct
                elif weight < -self.max_position_pct:
                    adjusted_weights[symbol] = -self.max_position_pct
                else:
                    adjusted_weights[symbol] = weight

            # Scale down if gross exposure still too high
            gross = sum(abs(w) for w in adjusted_weights.values())
            if gross > self.max_gross_exposure:
                scale = self.max_gross_exposure / gross
                adjusted_weights = {k: v * scale for k, v in adjusted_weights.items()}

            return WeightSignal(
                weights=adjusted_weights,
                rebalance=signal.rebalance,
                metadata=signal.metadata,
            )

        return signal


@dataclass
class MaxPairsConstraint:
    """Limit the number of simultaneous pair positions.

    Attributes:
        max_pairs: Maximum number of open pairs allowed
    """

    max_pairs: int = 10

    @property
    def name(self) -> str:
        return "max_pairs"

    def validate(self, signal: Signal, portfolio: Portfolio) -> bool:
        """Check if opening a new pair would exceed limit."""
        if signal is None:
            return True

        if isinstance(signal, PairSignal):
            from ptengine.core.types import SignalType
            if signal.signal_type == SignalType.OPEN_PAIR:
                return portfolio.num_pair_positions < self.max_pairs
            return True  # Closing is always allowed

        return True  # Weight signals don't affect pair count

    def adjust(self, signal: Signal, portfolio: Portfolio) -> Signal:
        """Reject signal if it would exceed max pairs."""
        if not self.validate(signal, portfolio):
            raise ConstraintViolationError(
                self.name,
                signal=signal,
                details={
                    "current_pairs": portfolio.num_pair_positions,
                    "max_pairs": self.max_pairs,
                },
            )
        return signal
