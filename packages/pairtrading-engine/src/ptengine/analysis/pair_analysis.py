"""Pair-level performance analysis.

This module provides tools for analyzing the performance of individual
trading pairs, enabling attribution of returns to specific pairs.
"""

from dataclasses import dataclass
from statistics import mean

import pandas as pd

from ptengine.analysis.trade_analysis import RoundTrip


@dataclass
class PairMetrics:
    """Performance metrics for a single trading pair.

    Attributes:
        pair_id: Unique identifier for the pair
        long_symbol: Symbol of the long leg
        short_symbol: Symbol of the short leg
        num_trades: Total number of round-trip trades
        num_winners: Number of winning trades
        num_losers: Number of losing trades
        win_rate: Fraction of trades that were profitable
        total_pnl: Total profit/loss from this pair
        avg_pnl: Average P&L per trade
        max_pnl: Best single trade P&L
        min_pnl: Worst single trade P&L
        avg_holding_days: Average holding period in days
        avg_return_pct: Average percentage return per trade
        total_commission: Total commission paid
    """

    pair_id: str
    long_symbol: str
    short_symbol: str
    num_trades: int
    num_winners: int
    num_losers: int
    win_rate: float
    total_pnl: float
    avg_pnl: float
    max_pnl: float
    min_pnl: float
    avg_holding_days: float
    avg_return_pct: float
    total_commission: float

    @property
    def symbols(self) -> tuple[str, str]:
        """Return (long_symbol, short_symbol) tuple."""
        return (self.long_symbol, self.short_symbol)

    @property
    def display_name(self) -> str:
        """Human-readable pair name."""
        return f"{self.long_symbol}/{self.short_symbol}"


def analyze_pairs(round_trips: list[RoundTrip]) -> dict[str, PairMetrics]:
    """Calculate performance metrics for each trading pair.

    Groups round-trip trades by pair_id and calculates aggregate
    statistics for each pair.

    Args:
        round_trips: List of matched round-trip trades.

    Returns:
        Dictionary mapping pair_id to PairMetrics.
    """
    if not round_trips:
        return {}

    # Group by pair_id
    pair_rts: dict[str, list[RoundTrip]] = {}
    for rt in round_trips:
        if rt.pair_id not in pair_rts:
            pair_rts[rt.pair_id] = []
        pair_rts[rt.pair_id].append(rt)

    metrics: dict[str, PairMetrics] = {}

    for pair_id, rts in pair_rts.items():
        if not rts:
            continue

        # Get symbols from first trade
        long_sym = rts[0].long_symbol
        short_sym = rts[0].short_symbol

        # Calculate metrics
        pnls = [rt.pnl for rt in rts]
        winners = [rt for rt in rts if rt.pnl > 0]
        losers = [rt for rt in rts if rt.pnl < 0]

        metrics[pair_id] = PairMetrics(
            pair_id=pair_id,
            long_symbol=long_sym,
            short_symbol=short_sym,
            num_trades=len(rts),
            num_winners=len(winners),
            num_losers=len(losers),
            win_rate=len(winners) / len(rts) if rts else 0.0,
            total_pnl=sum(pnls),
            avg_pnl=mean(pnls) if pnls else 0.0,
            max_pnl=max(pnls) if pnls else 0.0,
            min_pnl=min(pnls) if pnls else 0.0,
            avg_holding_days=mean(rt.holding_days for rt in rts) if rts else 0.0,
            avg_return_pct=mean(rt.return_pct for rt in rts) if rts else 0.0,
            total_commission=sum(rt.commission for rt in rts),
        )

    return metrics


def pair_cumulative_returns(
    round_trips: list[RoundTrip],
    initial_capital: float = 100000.0,
) -> pd.DataFrame:
    """Calculate cumulative returns by pair over time.

    Creates a time series of cumulative P&L for each pair, useful for
    visualizing how each pair contributed to overall performance.

    Args:
        round_trips: List of matched round-trip trades.
        initial_capital: Starting capital for return calculation.

    Returns:
        DataFrame with columns: date, pair_id, cumulative_pnl, cumulative_return
        Sorted by date.
    """
    if not round_trips:
        return pd.DataFrame(columns=["date", "pair_id", "cumulative_pnl", "cumulative_return"])

    # Build records for each trade exit
    records = []
    for rt in round_trips:
        if rt.exit_date is not None:
            records.append({
                "date": rt.exit_date,
                "pair_id": rt.pair_id,
                "pnl": rt.pnl,
            })

    if not records:
        return pd.DataFrame(columns=["date", "pair_id", "cumulative_pnl", "cumulative_return"])

    df = pd.DataFrame(records)
    df = df.sort_values("date")

    # Calculate cumulative P&L per pair
    result_records = []
    pair_cumulative: dict[str, float] = {}

    for _, row in df.iterrows():
        pair_id = row["pair_id"]
        if pair_id not in pair_cumulative:
            pair_cumulative[pair_id] = 0.0

        pair_cumulative[pair_id] += row["pnl"]

        result_records.append({
            "date": row["date"],
            "pair_id": pair_id,
            "cumulative_pnl": pair_cumulative[pair_id],
            "cumulative_return": pair_cumulative[pair_id] / initial_capital,
        })

    return pd.DataFrame(result_records)


def pair_performance_summary(
    pair_metrics: dict[str, PairMetrics],
) -> pd.DataFrame:
    """Create a summary DataFrame of pair performance.

    Args:
        pair_metrics: Dictionary of pair metrics from analyze_pairs().

    Returns:
        DataFrame with one row per pair, sorted by total P&L descending.
    """
    if not pair_metrics:
        return pd.DataFrame()

    records = []
    for pm in pair_metrics.values():
        records.append({
            "pair": pm.display_name,
            "pair_id": pm.pair_id,
            "trades": pm.num_trades,
            "win_rate": pm.win_rate,
            "total_pnl": pm.total_pnl,
            "avg_pnl": pm.avg_pnl,
            "best_trade": pm.max_pnl,
            "worst_trade": pm.min_pnl,
            "avg_days": pm.avg_holding_days,
            "avg_return": pm.avg_return_pct,
            "commission": pm.total_commission,
        })

    df = pd.DataFrame(records)
    return df.sort_values("total_pnl", ascending=False).reset_index(drop=True)
