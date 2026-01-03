"""Custom user-defined stock universes."""

from datetime import date
from pathlib import Path


class CustomUniverse:
    """User-defined list of symbols.

    Create a universe from a list of symbols, a file, or any iterable.
    Useful for testing, custom portfolios, or specific stock groups.

    Example:
        # From list
        universe = CustomUniverse(["AAPL", "MSFT", "GOOGL"])

        # From file (one symbol per line)
        universe = CustomUniverse.from_file("symbols.txt")

        # Get symbols
        symbols = universe.get_symbols()  # ["AAPL", "GOOGL", "MSFT"]

    Attributes:
        name: Universe identifier
    """

    def __init__(
        self,
        symbols: list[str],
        name: str = "custom",
    ) -> None:
        """Initialize custom universe.

        Args:
            symbols: List of ticker symbols
            name: Name identifier for this universe
        """
        # Normalize to uppercase and remove duplicates
        self._symbols = sorted(set(s.upper().strip() for s in symbols if s.strip()))
        self._name = name

    @property
    def name(self) -> str:
        """Universe identifier."""
        return self._name

    def get_symbols(self, as_of_date: date | None = None) -> list[str]:
        """Get the symbols in this universe.

        Note:
            Custom universes don't support point-in-time lookups.
            The as_of_date parameter is ignored.

        Args:
            as_of_date: Ignored (custom universes are static)

        Returns:
            List of ticker symbols
        """
        return self._symbols.copy()

    def __len__(self) -> int:
        """Number of symbols in the universe."""
        return len(self._symbols)

    def __contains__(self, symbol: str) -> bool:
        """Check if a symbol is in the universe."""
        return symbol.upper() in self._symbols

    def __repr__(self) -> str:
        """String representation."""
        return f"CustomUniverse(name={self._name!r}, count={len(self)})"

    @classmethod
    def from_file(
        cls,
        file_path: str | Path,
        name: str | None = None,
    ) -> "CustomUniverse":
        """Create universe from a text file.

        File format: one symbol per line, empty lines and comments (#) ignored.

        Example file:
            # Tech stocks
            AAPL
            MSFT
            GOOGL

        Args:
            file_path: Path to text file with symbols
            name: Universe name (defaults to filename without extension)

        Returns:
            CustomUniverse instance
        """
        path = Path(file_path)

        if name is None:
            name = path.stem

        symbols = []
        with open(path) as f:
            for line in f:
                line = line.strip()
                # Skip empty lines and comments
                if line and not line.startswith("#"):
                    symbols.append(line)

        return cls(symbols, name=name)

    @classmethod
    def from_csv(
        cls,
        file_path: str | Path,
        symbol_column: str = "symbol",
        name: str | None = None,
    ) -> "CustomUniverse":
        """Create universe from a CSV file.

        Args:
            file_path: Path to CSV file
            symbol_column: Name of the column containing symbols
            name: Universe name (defaults to filename without extension)

        Returns:
            CustomUniverse instance
        """
        import pandas as pd

        path = Path(file_path)

        if name is None:
            name = path.stem

        df = pd.read_csv(path)
        symbols = df[symbol_column].dropna().unique().tolist()

        return cls(symbols, name=name)

    def add(self, symbol: str) -> None:
        """Add a symbol to the universe.

        Args:
            symbol: Ticker symbol to add
        """
        symbol = symbol.upper().strip()
        if symbol and symbol not in self._symbols:
            self._symbols.append(symbol)
            self._symbols.sort()

    def remove(self, symbol: str) -> None:
        """Remove a symbol from the universe.

        Args:
            symbol: Ticker symbol to remove
        """
        symbol = symbol.upper().strip()
        if symbol in self._symbols:
            self._symbols.remove(symbol)

    def union(self, other: "CustomUniverse") -> "CustomUniverse":
        """Create a new universe with symbols from both universes.

        Args:
            other: Another CustomUniverse

        Returns:
            New CustomUniverse with combined symbols
        """
        combined = set(self._symbols) | set(other._symbols)
        return CustomUniverse(list(combined), name=f"{self._name}+{other._name}")

    def intersection(self, other: "CustomUniverse") -> "CustomUniverse":
        """Create a new universe with symbols in both universes.

        Args:
            other: Another CustomUniverse

        Returns:
            New CustomUniverse with common symbols
        """
        common = set(self._symbols) & set(other._symbols)
        return CustomUniverse(list(common), name=f"{self._name}&{other._name}")
