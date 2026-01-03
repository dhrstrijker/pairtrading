"""GGR Distance-based Pairs Trading Strategy.

Implementation of the Gatev, Goetzmann, and Rouwenhorst (2006) distance method
for pairs trading. The strategy:

1. Formation Period: Identifies pairs with minimum Sum of Squared Deviations (SSD)
   in their normalized price series (cumulative returns).

2. Trading Period: Opens positions when spread diverges beyond entry threshold,
   closes when spread reverts to mean or time limit is reached.

Reference:
    Gatev, E., Goetzmann, W. N., & Rouwenhorst, K. G. (2006).
    Pairs trading: Performance of a relative-value arbitrage rule.
    The Review of Financial Studies, 19(3), 797-827.
"""

from dataclasses import dataclass
from datetime import date

import numpy as np
import pandas as pd
from ptdata.validation import PointInTimeDataFrame

from ptengine.core.types import PairSignal, Signal, SignalType, Trade
from ptengine.strategy.base import BaseStrategy


@dataclass
class PairState:
    """Tracks state for an active pair position."""

    pair_id: str
    long_symbol: str
    short_symbol: str
    entry_date: date
    entry_zscore: float
    days_held: int = 0


@dataclass
class PairCandidate:
    """A potential pair identified during formation."""

    symbol_a: str
    symbol_b: str
    ssd: float  # Sum of Squared Deviations
    correlation: float


class GGRDistanceStrategy(BaseStrategy):
    """GGR Distance-based pairs trading strategy.

    This strategy scans a universe of symbols to find pairs with minimum
    distance (SSD) in their normalized price series, then trades mean
    reversion of the spread.

    Attributes:
        symbols: List of symbols to scan for pairs
        formation_period: Days to use for pair formation (default: 120)
        lookback: Days for calculating spread statistics (default: 120)
        entry_threshold: Z-score threshold for entry (default: 2.0)
        exit_threshold: Z-score threshold for exit (default: 0.5)
        max_holding_days: Maximum days to hold a position (default: 20)
        top_n_pairs: Number of top pairs to trade (default: 5)
        min_correlation: Minimum correlation for pair consideration (default: 0.8)

    Example:
        strategy = GGRDistanceStrategy(
            symbols=["AAPL", "MSFT", "GOOGL", "META", "AMZN"],
            formation_period=120,
            entry_threshold=2.0,
            top_n_pairs=3,
        )
    """

    def __init__(
        self,
        symbols: list[str],
        formation_period: int = 120,
        lookback: int = 120,
        entry_threshold: float = 2.0,
        exit_threshold: float = 0.5,
        max_holding_days: int = 20,
        top_n_pairs: int = 5,
        min_correlation: float = 0.8,
    ):
        super().__init__()
        self.symbols = sorted(set(symbols))
        self.formation_period = formation_period
        self.lookback = lookback
        self.entry_threshold = entry_threshold
        self.exit_threshold = exit_threshold
        self.max_holding_days = max_holding_days
        self.top_n_pairs = top_n_pairs
        self.min_correlation = min_correlation

        # State
        self._pairs: list[PairCandidate] = []
        self._active_positions: dict[str, PairState] = {}
        self._formation_complete: bool = False
        self._last_formation_date: date | None = None

    @property
    def name(self) -> str:
        return f"ggr_distance_{len(self.symbols)}symbols"

    def on_start(self, start_date: date, end_date: date) -> None:
        """Reset state at start of backtest."""
        self._pairs = []
        self._active_positions = {}
        self._formation_complete = False
        self._last_formation_date = None

    def on_bar(self, current_date: date, pit_data: PointInTimeDataFrame) -> Signal:
        """Process a trading day.

        1. Check if we have enough data for formation
        2. If formation not complete, run pair formation
        3. Check for exit signals on active positions
        4. Check for entry signals on identified pairs
        """
        data = pit_data.get_data()

        # Need enough data for formation + lookback
        min_required = self.formation_period
        available_days = self._count_trading_days(data)

        if available_days < min_required:
            return None

        # Run formation if not done
        if not self._formation_complete:
            self._run_formation(data, current_date)

        if not self._pairs:
            return None

        # Update days held for active positions
        for state in self._active_positions.values():
            state.days_held += 1

        # Check exits first
        exit_signal = self._check_exits(data, current_date)
        if exit_signal is not None:
            return exit_signal

        # Check entries
        entry_signal = self._check_entries(data, current_date)
        return entry_signal

    def on_fill(self, trade: Trade) -> None:
        """Track fills to update position state."""
        super().on_fill(trade)

        if trade.pair_id is None:
            return

        # If this is a closing trade, remove from active positions
        if trade.pair_id in self._active_positions:
            # Check if this is a close signal (opposite direction)
            state = self._active_positions[trade.pair_id]
            # Closing trades come in pairs, so we check both directions
            # For simplicity, we'll remove on any trade with the pair_id
            # that happens after entry
            if state.days_held > 0:
                del self._active_positions[trade.pair_id]

    def _count_trading_days(self, data: pd.DataFrame) -> int:
        """Count unique trading days in data."""
        if "date" not in data.columns:
            return 0
        return int(data["date"].nunique())

    def _run_formation(self, data: pd.DataFrame, current_date: date) -> None:
        """Run pair formation to identify best pairs.

        Uses Sum of Squared Deviations (SSD) of normalized prices
        to rank pairs. Lower SSD = more similar price movements.
        """
        # Get normalized prices for each symbol
        normalized = self._get_normalized_prices(data)

        if normalized is None or len(normalized.columns) < 2:
            return

        # Calculate SSD for all pairs
        candidates: list[PairCandidate] = []
        symbols = list(normalized.columns)

        for i in range(len(symbols)):
            for j in range(i + 1, len(symbols)):
                sym_a, sym_b = symbols[i], symbols[j]

                # Get aligned series
                series_a = normalized[sym_a].dropna()
                series_b = normalized[sym_b].dropna()

                # Align on common dates
                common_idx = series_a.index.intersection(series_b.index)
                if len(common_idx) < self.formation_period * 0.8:
                    continue

                series_a = series_a.loc[common_idx]
                series_b = series_b.loc[common_idx]

                # Calculate correlation
                corr = series_a.corr(series_b)
                if corr < self.min_correlation:
                    continue

                # Calculate SSD
                ssd = ((series_a - series_b) ** 2).sum()

                candidates.append(PairCandidate(
                    symbol_a=sym_a,
                    symbol_b=sym_b,
                    ssd=ssd,
                    correlation=corr,
                ))

        # Sort by SSD (lower is better) and take top N
        candidates.sort(key=lambda x: x.ssd)
        self._pairs = candidates[:self.top_n_pairs]
        self._formation_complete = True
        self._last_formation_date = current_date

    def _get_normalized_prices(self, data: pd.DataFrame) -> pd.DataFrame | None:
        """Convert prices to normalized cumulative returns.

        Normalization: (P_t / P_0) - 1 = cumulative return from start
        """
        if "symbol" not in data.columns or "adj_close" not in data.columns:
            return None

        # Pivot to get prices by symbol
        price_col = "adj_close"
        try:
            prices = data.pivot_table(
                index="date",
                columns="symbol",
                values=price_col,
                aggfunc="last"
            )
        except Exception:
            return None

        # Filter to our symbols
        available = [s for s in self.symbols if s in prices.columns]
        if len(available) < 2:
            return None

        prices = prices[available]

        # Use formation period of data
        if len(prices) > self.formation_period:
            prices = prices.iloc[-self.formation_period:]

        # Calculate cumulative returns (normalized prices)
        first_prices = prices.iloc[0]
        normalized = prices / first_prices - 1

        return normalized

    def _check_exits(self, data: pd.DataFrame, current_date: date) -> Signal:
        """Check if any active position should be closed."""
        for _pair_id, state in list(self._active_positions.items()):
            # Time-based exit
            if state.days_held >= self.max_holding_days:
                return self._create_close_signal(state)

            # Mean reversion exit
            zscore = self._calculate_zscore(
                data, state.long_symbol, state.short_symbol
            )
            if zscore is None:
                continue

            # Check if spread has reverted to mean
            if abs(zscore) <= self.exit_threshold:
                return self._create_close_signal(state)

            # Check if spread has crossed zero (strong mean reversion)
            if state.entry_zscore > 0 and zscore <= 0:
                return self._create_close_signal(state)
            if state.entry_zscore < 0 and zscore >= 0:
                return self._create_close_signal(state)

        return None

    def _check_entries(self, data: pd.DataFrame, current_date: date) -> Signal:
        """Check if any pair should be entered."""
        for pair in self._pairs:
            pair_id = f"{pair.symbol_a}_{pair.symbol_b}"

            # Skip if already in position
            if pair_id in self._active_positions:
                continue

            zscore = self._calculate_zscore(data, pair.symbol_a, pair.symbol_b)
            if zscore is None:
                continue

            # Entry signal: spread diverged beyond threshold
            if zscore > self.entry_threshold:
                # Spread too high: short A, long B (expect A to fall relative to B)
                state = PairState(
                    pair_id=pair_id,
                    long_symbol=pair.symbol_b,
                    short_symbol=pair.symbol_a,
                    entry_date=current_date,
                    entry_zscore=zscore,
                )
                self._active_positions[pair_id] = state

                return PairSignal(
                    signal_type=SignalType.OPEN_PAIR,
                    long_symbol=pair.symbol_b,
                    short_symbol=pair.symbol_a,
                    pair_id=pair_id,
                    metadata={"zscore": zscore, "ssd": pair.ssd},
                )

            elif zscore < -self.entry_threshold:
                # Spread too low: long A, short B (expect A to rise relative to B)
                state = PairState(
                    pair_id=pair_id,
                    long_symbol=pair.symbol_a,
                    short_symbol=pair.symbol_b,
                    entry_date=current_date,
                    entry_zscore=zscore,
                )
                self._active_positions[pair_id] = state

                return PairSignal(
                    signal_type=SignalType.OPEN_PAIR,
                    long_symbol=pair.symbol_a,
                    short_symbol=pair.symbol_b,
                    pair_id=pair_id,
                    metadata={"zscore": zscore, "ssd": pair.ssd},
                )

        return None

    def _calculate_zscore(
        self, data: pd.DataFrame, symbol_a: str, symbol_b: str
    ) -> float | None:
        """Calculate z-score of the spread between two symbols.

        Spread = normalized_price_A - normalized_price_B
        Z-score = (spread - mean) / std
        """
        # Get prices for both symbols
        price_col = "adj_close"

        try:
            prices_a = data[data["symbol"] == symbol_a][["date", price_col]].copy()
            prices_b = data[data["symbol"] == symbol_b][["date", price_col]].copy()
        except Exception:
            return None

        if prices_a.empty or prices_b.empty:
            return None

        # Merge on date
        prices_a = prices_a.set_index("date")
        prices_b = prices_b.set_index("date")

        merged = pd.concat([prices_a, prices_b], axis=1, keys=["a", "b"])
        merged = merged.dropna()

        if len(merged) < self.lookback * 0.5:
            return None

        # Use lookback period
        if len(merged) > self.lookback:
            merged = merged.iloc[-self.lookback:]

        # Calculate normalized prices
        first_a = merged[("a", price_col)].iloc[0]
        first_b = merged[("b", price_col)].iloc[0]

        norm_a = merged[("a", price_col)] / first_a - 1
        norm_b = merged[("b", price_col)] / first_b - 1

        # Calculate spread
        spread = norm_a - norm_b

        # Z-score
        mean = spread.mean()
        std = spread.std()

        if std == 0 or np.isnan(std):
            return None

        current_spread = spread.iloc[-1]
        zscore = (current_spread - mean) / std

        return float(zscore)

    def _create_close_signal(self, state: PairState) -> PairSignal:
        """Create a close signal for an active position."""
        return PairSignal(
            signal_type=SignalType.CLOSE_PAIR,
            long_symbol=state.long_symbol,
            short_symbol=state.short_symbol,
            pair_id=state.pair_id,
            metadata={"days_held": state.days_held},
        )

    def get_active_pairs(self) -> list[str]:
        """Return list of currently active pair IDs."""
        return list(self._active_positions.keys())

    def get_identified_pairs(self) -> list[tuple[str, str, float]]:
        """Return list of identified pairs with their SSD values."""
        return [(p.symbol_a, p.symbol_b, p.ssd) for p in self._pairs]

    def reset(self) -> None:
        """Reset strategy state."""
        super().reset()
        self._pairs = []
        self._active_positions = {}
        self._formation_complete = False
        self._last_formation_date = None
