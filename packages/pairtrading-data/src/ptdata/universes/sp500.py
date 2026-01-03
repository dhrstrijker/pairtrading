"""S&P 500 stock universe.

Note: This is a simplified implementation that returns the current
S&P 500 constituents. For proper survivorship-bias-free backtesting,
you would need historical constituent data.

Future enhancement: Track historical additions/removals.
"""

from datetime import date

from ptdata.core.exceptions import PTDataError


class SP500Universe:
    """S&P 500 stock universe.

    Provides the current S&P 500 constituents. For proper backtesting,
    you should use historical constituent data to avoid survivorship bias.

    Data source: Wikipedia's list of S&P 500 companies.

    Example:
        universe = SP500Universe()
        symbols = universe.get_symbols()  # ~500 symbols

    Warning:
        This implementation returns current constituents only.
        Historical point-in-time lookups are not supported.
        For survivorship-bias-free backtesting, consider using
        a data provider with historical index membership data.

    Attributes:
        name: Universe identifier ("sp500")
    """

    # Fallback list of major S&P 500 components
    # (used if fetching from Wikipedia fails)
    _FALLBACK_SYMBOLS: list[str] = [
        "AAPL", "MSFT", "AMZN", "NVDA", "GOOGL", "GOOG", "META", "BRK.B",
        "UNH", "XOM", "LLY", "JPM", "JNJ", "V", "PG", "MA", "AVGO", "HD",
        "CVX", "MRK", "ABBV", "COST", "PEP", "ADBE", "KO", "WMT", "MCD",
        "CSCO", "CRM", "BAC", "PFE", "TMO", "ACN", "ABT", "NFLX", "LIN",
        "DHR", "AMD", "ORCL", "DIS", "WFC", "TXN", "PM", "VZ", "INTC",
        "INTU", "NEE", "UPS", "QCOM", "RTX", "SPGI", "CAT", "BA", "HON",
        "IBM", "AMGN", "LOW", "GE", "SBUX", "GS", "AMAT", "DE", "MS",
        "BLK", "ELV", "PLD", "MDLZ", "ADP", "T", "SYK", "GILD", "ISRG",
        "ADI", "LMT", "BKNG", "VRTX", "MMC", "TJX", "CB", "AXP", "REGN",
        "SCHW", "NOW", "MO", "CVS", "CI", "ZTS", "LRCX", "C", "BDX",
        "PANW", "SLB", "TMUS", "CME", "EOG", "SO", "DUK", "MU", "BSX",
    ]

    def __init__(self, fetch_online: bool = True) -> None:
        """Initialize S&P 500 universe.

        Args:
            fetch_online: If True, fetch current constituents from Wikipedia.
                         If False, use fallback list of major components.
        """
        self._fetch_online = fetch_online
        self._symbols: list[str] | None = None

    @property
    def name(self) -> str:
        """Universe identifier."""
        return "sp500"

    def get_symbols(self, as_of_date: date | None = None) -> list[str]:
        """Get S&P 500 symbols.

        Warning:
            The as_of_date parameter is currently ignored.
            This implementation returns current constituents only.

        Args:
            as_of_date: Ignored (historical lookups not supported)

        Returns:
            List of S&P 500 ticker symbols
        """
        if self._symbols is None:
            self._symbols = self._load_symbols()
        return self._symbols.copy()

    def _load_symbols(self) -> list[str]:
        """Load S&P 500 symbols.

        Tries to fetch from Wikipedia first, falls back to static list.
        """
        if self._fetch_online:
            try:
                return self._fetch_from_wikipedia()
            except Exception:
                # Fall back to static list
                pass

        return sorted(self._FALLBACK_SYMBOLS)

    def _fetch_from_wikipedia(self) -> list[str]:
        """Fetch S&P 500 constituents from Wikipedia.

        Parses the table from:
        https://en.wikipedia.org/wiki/List_of_S%26P_500_companies

        Returns:
            List of ticker symbols
        """
        try:
            import pandas as pd
        except ImportError as e:
            msg = "pandas is required to fetch S&P 500 list from Wikipedia"
            raise PTDataError(msg) from e

        url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"

        try:
            tables = pd.read_html(url)
            if not tables:
                raise PTDataError("No tables found on Wikipedia page")

            # First table contains current constituents
            df = tables[0]

            # Symbol column might be named "Symbol" or "Ticker"
            symbol_col = None
            for col in ["Symbol", "Ticker", "symbol", "ticker"]:
                if col in df.columns:
                    symbol_col = col
                    break

            if symbol_col is None:
                raise PTDataError("Symbol column not found in Wikipedia table")

            symbols = df[symbol_col].dropna().unique().tolist()

            # Clean up symbols (some have dots that need to be handled)
            cleaned = []
            for sym in symbols:
                sym = str(sym).strip()
                if sym:
                    # Some tickers use dots (BRK.B) which is fine
                    cleaned.append(sym)

            return sorted(cleaned)

        except Exception as e:
            raise PTDataError(f"Failed to fetch S&P 500 list: {e}") from e

    def __len__(self) -> int:
        """Number of symbols in the universe."""
        return len(self.get_symbols())

    def __contains__(self, symbol: str) -> bool:
        """Check if a symbol is in the S&P 500."""
        return symbol.upper() in self.get_symbols()

    def __repr__(self) -> str:
        """String representation."""
        return f"SP500Universe(count={len(self)})"

    def refresh(self) -> None:
        """Refresh the symbol list from source."""
        self._symbols = None
        self.get_symbols()
