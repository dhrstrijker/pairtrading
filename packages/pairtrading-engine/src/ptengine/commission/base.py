"""Base commission model protocol."""

from typing import Protocol


class CommissionModel(Protocol):
    """Protocol for commission calculation models.

    Commission models calculate the cost of executing a trade.
    Different brokers have different fee structures.
    """

    def calculate(self, shares: float, price: float) -> float:
        """Calculate commission for a trade.

        Args:
            shares: Number of shares traded
            price: Price per share

        Returns:
            Commission amount
        """
        ...
