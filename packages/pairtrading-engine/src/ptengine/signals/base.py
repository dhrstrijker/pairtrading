"""Signal type utilities and validation.

Provides helpers for working with the Signal union type.
"""

from ptengine.core.types import PairSignal, Signal, WeightSignal


def is_pair_signal(signal: Signal) -> bool:
    """Check if signal is a PairSignal."""
    return isinstance(signal, PairSignal)


def is_weight_signal(signal: Signal) -> bool:
    """Check if signal is a WeightSignal."""
    return isinstance(signal, WeightSignal)


def get_signal_symbols(signal: Signal) -> list[str]:
    """Get list of symbols involved in a signal.

    Args:
        signal: A PairSignal, WeightSignal, or None

    Returns:
        List of symbol strings (empty if None)
    """
    if signal is None:
        return []
    elif isinstance(signal, PairSignal):
        return list(signal.symbols)
    elif isinstance(signal, WeightSignal):
        return signal.symbols
    return []


def validate_signal(signal: Signal) -> bool:
    """Validate a signal is well-formed.

    Args:
        signal: Signal to validate

    Returns:
        True if valid

    Note:
        Signal dataclasses validate in __post_init__,
        so this primarily checks for None.
    """
    if signal is None:
        return True

    if isinstance(signal, PairSignal):
        # Already validated in __post_init__
        return True

    # WeightSignal is also validated in __post_init__
    return isinstance(signal, WeightSignal)
