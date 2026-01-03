"""Base protocol for stock universes.

This module defines the interface that all universe implementations must follow.
Using a Protocol allows for flexibility in how universes are defined.
"""

from datetime import date
from typing import Protocol, runtime_checkable


@runtime_checkable
class Universe(Protocol):
    """Protocol for stock universes.

    A universe defines a set of symbols that can be used for analysis.
    Implementations should support point-in-time constituent lookups
    to prevent survivorship bias.

    Example:
        class MyUniverse:
            @property
            def name(self) -> str:
                return "my_universe"

            def get_symbols(self, as_of_date: date | None = None) -> list[str]:
                return ["AAPL", "MSFT", "GOOGL"]

        # MyUniverse is now a valid Universe
        universe: Universe = MyUniverse()
    """

    @property
    def name(self) -> str:
        """Universe identifier.

        Returns:
            Unique string identifying this universe (e.g., "sp500", "shipping")
        """
        ...

    def get_symbols(self, as_of_date: date | None = None) -> list[str]:
        """Get the symbols in this universe.

        Args:
            as_of_date: If provided, return the symbols that were in the
                       universe on this date (for survivorship bias prevention).
                       If None, return current symbols.

        Returns:
            List of ticker symbols

        Note:
            For point-in-time accuracy, implementations should track
            historical constituent changes. If historical data is not
            available, the implementation should document this limitation.
        """
        ...
