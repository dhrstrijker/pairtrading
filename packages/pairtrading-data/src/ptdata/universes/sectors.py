"""Sector-based stock universes.

Pre-defined universes for specific sectors like shipping, mining, and metals.
These are useful for pair trading within a sector where stocks are more
likely to be correlated.
"""

from datetime import date


# Shipping stocks (dry bulk, container, tanker)
SHIPPING_STOCKS: list[str] = [
    # Dry bulk carriers
    "GOGL",   # Golden Ocean Group
    "SBLK",   # Star Bulk Carriers
    "GNK",    # Genco Shipping
    "EGLE",   # Eagle Bulk Shipping
    "DSX",    # Diana Shipping
    "NMM",    # Navios Maritime Partners
    # Container shipping
    "ZIM",    # ZIM Integrated Shipping
    "DAC",    # Danaos Corporation
    "GSL",    # Global Ship Lease
    "CMRE",   # Costamare Inc
    # Tankers
    "STNG",   # Scorpio Tankers
    "TNK",    # Teekay Tankers
    "INSW",   # International Seaways
    "DHT",    # DHT Holdings
    "FRO",    # Frontline Ltd
    "NAT",    # Nordic American Tankers
    "TRMD",   # TORM plc
]

# Mining stocks (metals, minerals)
MINING_STOCKS: list[str] = [
    # Diversified
    "BHP",    # BHP Group
    "RIO",    # Rio Tinto
    "VALE",   # Vale S.A.
    # Copper
    "FCX",    # Freeport-McMoRan
    "SCCO",   # Southern Copper
    # Gold
    "NEM",    # Newmont
    "GOLD",   # Barrick Gold
    "AEM",    # Agnico Eagle Mines
    "KGC",    # Kinross Gold
    "AU",     # AngloGold Ashanti
    # Silver
    "HL",     # Hecla Mining
    "PAAS",   # Pan American Silver
    # Steel/Iron
    "CLF",    # Cleveland-Cliffs
    "X",      # United States Steel
    "NUE",    # Nucor Corporation
]

# Metal ETFs and related
METALS_ETFS: list[str] = [
    # Precious metals
    "GLD",    # SPDR Gold Shares
    "SLV",    # iShares Silver Trust
    "PPLT",   # Aberdeen Platinum ETF
    "PALL",   # Aberdeen Palladium ETF
    "IAU",    # iShares Gold Trust
    # Base metals
    "COPX",   # Global X Copper Miners ETF
    "CPER",   # United States Copper Index Fund
    # Steel
    "SLX",    # VanEck Steel ETF
    # Mining ETFs
    "GDX",    # VanEck Gold Miners ETF
    "GDXJ",   # VanEck Junior Gold Miners ETF
    "SIL",    # Global X Silver Miners ETF
]

# Energy stocks
ENERGY_STOCKS: list[str] = [
    # Integrated
    "XOM",    # Exxon Mobil
    "CVX",    # Chevron
    "SHEL",   # Shell
    "BP",     # BP
    "TTE",    # TotalEnergies
    # E&P
    "COP",    # ConocoPhillips
    "EOG",    # EOG Resources
    "PXD",    # Pioneer Natural Resources (now part of XOM)
    "DVN",    # Devon Energy
    "OXY",    # Occidental Petroleum
    # Refining
    "VLO",    # Valero Energy
    "MPC",    # Marathon Petroleum
    "PSX",    # Phillips 66
]


class SectorUniverse:
    """Sector-based stock universe.

    Pre-defined universes for specific industry sectors.
    Useful for pair trading within sectors where stocks
    tend to be more correlated.

    Available sectors:
    - shipping: Dry bulk, container, and tanker shipping companies
    - mining: Metal and mineral mining companies
    - metals: Metal ETFs (gold, silver, platinum, copper)
    - energy: Oil and gas companies

    Example:
        universe = SectorUniverse("shipping")
        symbols = universe.get_symbols()  # ["DAC", "FRO", "GOGL", ...]

    Attributes:
        name: Universe identifier (same as sector name)
    """

    SECTORS: dict[str, list[str]] = {
        "shipping": SHIPPING_STOCKS,
        "mining": MINING_STOCKS,
        "metals": METALS_ETFS,
        "energy": ENERGY_STOCKS,
    }

    def __init__(self, sector: str) -> None:
        """Initialize sector universe.

        Args:
            sector: Name of the sector (shipping, mining, metals, energy)

        Raises:
            ValueError: If sector is not recognized
        """
        sector_lower = sector.lower()
        if sector_lower not in self.SECTORS:
            available = ", ".join(sorted(self.SECTORS.keys()))
            raise ValueError(f"Unknown sector: {sector}. Available: {available}")

        self._sector = sector_lower
        self._symbols = sorted(self.SECTORS[sector_lower])

    @property
    def name(self) -> str:
        """Universe identifier (same as sector name)."""
        return self._sector

    def get_symbols(self, as_of_date: date | None = None) -> list[str]:
        """Get the symbols in this sector.

        Note:
            Sector universes don't currently support point-in-time lookups.
            The as_of_date parameter is ignored.

        Args:
            as_of_date: Ignored (sector universes are static)

        Returns:
            List of ticker symbols in the sector
        """
        return self._symbols.copy()

    def __len__(self) -> int:
        """Number of symbols in the sector."""
        return len(self._symbols)

    def __contains__(self, symbol: str) -> bool:
        """Check if a symbol is in the sector."""
        return symbol.upper() in self._symbols

    def __repr__(self) -> str:
        """String representation."""
        return f"SectorUniverse(sector={self._sector!r}, count={len(self)})"

    @classmethod
    def available_sectors(cls) -> list[str]:
        """Get list of available sectors.

        Returns:
            List of sector names
        """
        return sorted(cls.SECTORS.keys())

    @classmethod
    def all_symbols(cls) -> list[str]:
        """Get all symbols across all sectors.

        Returns:
            List of all unique symbols
        """
        all_syms: set[str] = set()
        for symbols in cls.SECTORS.values():
            all_syms.update(symbols)
        return sorted(all_syms)
