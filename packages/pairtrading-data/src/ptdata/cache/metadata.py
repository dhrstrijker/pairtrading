"""Cache metadata management.

Tracks what data is cached and when it was downloaded.
Used to determine if cache is valid for a given request.
"""

import json
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any


@dataclass
class SymbolCacheInfo:
    """Cache information for a single symbol.

    Attributes:
        symbol: Ticker symbol
        start_date: Start of cached date range
        end_date: End of cached date range
        download_date: When the data was downloaded
        row_count: Number of rows in cached data
    """

    symbol: str
    start_date: date
    end_date: date
    download_date: datetime
    row_count: int

    def covers(self, start: date, end: date) -> bool:
        """Check if this cache covers the requested date range.

        Args:
            start: Requested start date
            end: Requested end date

        Returns:
            True if cache fully covers the requested range
        """
        return self.start_date <= start and self.end_date >= end

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "symbol": self.symbol,
            "start_date": self.start_date.isoformat(),
            "end_date": self.end_date.isoformat(),
            "download_date": self.download_date.isoformat(),
            "row_count": self.row_count,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SymbolCacheInfo":
        """Create from dictionary."""
        return cls(
            symbol=data["symbol"],
            start_date=date.fromisoformat(data["start_date"]),
            end_date=date.fromisoformat(data["end_date"]),
            download_date=datetime.fromisoformat(data["download_date"]),
            row_count=data["row_count"],
        )


@dataclass
class CacheMetadata:
    """Metadata for the entire cache.

    Tracks what data is cached for each symbol and when.
    Stored as _metadata.json in the cache directory.

    Attributes:
        cache_dir: Path to cache directory
        symbols: Mapping of symbol to cache info
    """

    cache_dir: Path
    symbols: dict[str, SymbolCacheInfo] = field(default_factory=dict)

    METADATA_FILE = "_metadata.json"

    def __post_init__(self) -> None:
        """Ensure cache_dir is a Path."""
        self.cache_dir = Path(self.cache_dir)

    @property
    def metadata_path(self) -> Path:
        """Path to the metadata file."""
        return self.cache_dir / self.METADATA_FILE

    def get(self, symbol: str) -> SymbolCacheInfo | None:
        """Get cache info for a symbol.

        Args:
            symbol: Ticker symbol

        Returns:
            SymbolCacheInfo if cached, None otherwise
        """
        return self.symbols.get(symbol.upper())

    def set(
        self,
        symbol: str,
        start_date: date,
        end_date: date,
        row_count: int,
    ) -> None:
        """Update cache info for a symbol.

        Args:
            symbol: Ticker symbol
            start_date: Start of cached date range
            end_date: End of cached date range
            row_count: Number of rows in cached data
        """
        self.symbols[symbol.upper()] = SymbolCacheInfo(
            symbol=symbol.upper(),
            start_date=start_date,
            end_date=end_date,
            download_date=datetime.now(),
            row_count=row_count,
        )

    def remove(self, symbol: str) -> None:
        """Remove cache info for a symbol.

        Args:
            symbol: Ticker symbol
        """
        self.symbols.pop(symbol.upper(), None)

    def is_valid(
        self,
        symbol: str,
        start_date: date,
        end_date: date,
        max_age_days: int = 1,
    ) -> bool:
        """Check if cache is valid for the requested range.

        Cache is valid if:
        1. Symbol is cached
        2. Cached range covers the requested range
        3. Cache is not expired (based on max_age_days)

        Args:
            symbol: Ticker symbol
            start_date: Requested start date
            end_date: Requested end date
            max_age_days: Maximum age of cache in days (0 = never expires)

        Returns:
            True if cache is valid
        """
        info = self.get(symbol)
        if info is None:
            return False

        # Check if range is covered
        if not info.covers(start_date, end_date):
            return False

        # Check if cache is expired
        if max_age_days > 0:
            age = datetime.now() - info.download_date
            if age.days >= max_age_days:
                return False

        return True

    def save(self) -> None:
        """Save metadata to disk."""
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        data = {
            "version": 1,
            "symbols": {sym: info.to_dict() for sym, info in self.symbols.items()},
        }

        with open(self.metadata_path, "w") as f:
            json.dump(data, f, indent=2)

    @classmethod
    def load(cls, cache_dir: str | Path) -> "CacheMetadata":
        """Load metadata from disk.

        Args:
            cache_dir: Path to cache directory

        Returns:
            CacheMetadata instance (empty if file doesn't exist)
        """
        cache_dir = Path(cache_dir)
        metadata_path = cache_dir / cls.METADATA_FILE

        if not metadata_path.exists():
            return cls(cache_dir=cache_dir)

        try:
            with open(metadata_path) as f:
                data = json.load(f)

            symbols = {
                sym: SymbolCacheInfo.from_dict(info)
                for sym, info in data.get("symbols", {}).items()
            }

            return cls(cache_dir=cache_dir, symbols=symbols)

        except (json.JSONDecodeError, KeyError, ValueError):
            # Corrupted metadata file - start fresh
            return cls(cache_dir=cache_dir)

    def clear(self) -> None:
        """Clear all metadata."""
        self.symbols.clear()
        if self.metadata_path.exists():
            self.metadata_path.unlink()
