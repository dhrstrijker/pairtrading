"""Trade analysis with round-trip matching.

This module provides tools for analyzing trades by matching entry and exit
transactions into round-trips, enabling accurate win rate and profit factor
calculations.
"""

from dataclasses import dataclass
from datetime import date
from statistics import mean
from typing import Any

from ptengine.core.types import Side, Trade
from ptengine.results.trades import TradeLog


@dataclass(frozen=True)
class RoundTrip:
    """A matched entry-to-exit pair trade.

    Represents a complete round-trip trade from opening to closing a pair
    position, or an open position marked to market.

    Attributes:
        pair_id: Unique identifier for the pair
        entry_date: Date the position was opened
        exit_date: Date the position was closed (None if still open)
        long_symbol: Symbol of the long leg
        short_symbol: Symbol of the short leg
        long_entry_price: Entry price for long leg
        short_entry_price: Entry price for short leg
        long_exit_price: Exit price for long leg (or mark price if open)
        short_exit_price: Exit price for short leg (or mark price if open)
        long_shares: Number of shares in long leg
        short_shares: Number of shares in short leg
        pnl: Realized (or unrealized if open) P&L
        holding_days: Number of calendar days held
        return_pct: Percentage return on notional
        commission: Total commission paid
        is_open: True if position was marked to market at backtest end
    """

    pair_id: str
    entry_date: date
    exit_date: date | None
    long_symbol: str
    short_symbol: str
    long_entry_price: float
    short_entry_price: float
    long_exit_price: float
    short_exit_price: float
    long_shares: float
    short_shares: float
    pnl: float
    holding_days: int
    return_pct: float
    commission: float
    is_open: bool = False

    @property
    def entry_notional(self) -> float:
        """Total notional at entry (long + short legs)."""
        return (self.long_shares * self.long_entry_price +
                self.short_shares * self.short_entry_price)

    @property
    def is_winner(self) -> bool:
        """True if the round-trip was profitable."""
        return self.pnl > 0


@dataclass
class TradeStatistics:
    """Aggregated statistics from round-trip trades."""

    total_round_trips: int
    closed_round_trips: int
    open_round_trips: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    avg_win: float
    avg_loss: float
    profit_factor: float
    avg_holding_days: float
    max_holding_days: int
    min_holding_days: int
    avg_return_pct: float
    best_trade_pct: float
    worst_trade_pct: float
    total_pnl: float
    total_commission: float


def match_round_trips(
    trade_log: TradeLog,
    final_prices: dict[str, float] | None = None,
    include_open: bool = True,
    end_date: date | None = None,
) -> list[RoundTrip]:
    """Match opening and closing trades into round-trips.

    Groups trades by pair_id and matches entry trades (when a pair is opened)
    with exit trades (when the pair is closed) to calculate P&L for each
    complete round-trip.

    Args:
        trade_log: Log of all trades from backtest
        final_prices: End-of-backtest prices for marking open positions.
                     Required if include_open=True and there are open positions.
        include_open: If True, include open positions marked to market.
                     If False, only include closed round-trips.
        end_date: End date for calculating holding days of open positions.

    Returns:
        List of RoundTrip objects representing matched trades.

    Note:
        For pair trades, each round-trip consists of:
        - Entry: LONG trade on one symbol + SHORT trade on another
        - Exit: SHORT trade on long symbol + LONG trade on short symbol
    """
    if trade_log.num_trades == 0:
        return []

    # Group trades by pair_id
    pair_trades: dict[str, list[Trade]] = {}
    for trade in trade_log:
        if trade.pair_id is None:
            continue
        if trade.pair_id not in pair_trades:
            pair_trades[trade.pair_id] = []
        pair_trades[trade.pair_id].append(trade)

    round_trips: list[RoundTrip] = []

    for pair_id, trades in pair_trades.items():
        # Sort trades by date
        trades = sorted(trades, key=lambda t: t.date)

        # Track position state for each symbol in the pair
        positions: dict[str, dict[str, Any]] = {}  # symbol -> {shares, avg_price, side}

        for trade in trades:
            symbol = trade.symbol

            if symbol not in positions:
                positions[symbol] = {"shares": 0.0, "avg_price": 0.0, "side": None}

            pos = positions[symbol]

            if pos["shares"] == 0:
                # Opening new position
                pos["shares"] = trade.shares
                pos["avg_price"] = trade.price
                pos["side"] = trade.side
                pos["entry_date"] = trade.date
                pos["commission"] = trade.commission
            elif pos["side"] == trade.side:
                # Adding to position (average in)
                total_cost = pos["shares"] * pos["avg_price"] + trade.shares * trade.price
                pos["shares"] += trade.shares
                pos["avg_price"] = total_cost / pos["shares"]
                pos["commission"] = pos.get("commission", 0) + trade.commission
            else:
                # Closing position (opposite side)
                closing_shares = min(trade.shares, pos["shares"])

                if closing_shares == pos["shares"]:
                    # Fully closing
                    pos["exit_price"] = trade.price
                    pos["exit_date"] = trade.date
                    pos["exit_commission"] = trade.commission
                    pos["closed"] = True

                pos["shares"] -= closing_shares

                if pos["shares"] == 0:
                    pos["shares"] = 0
                    # Position fully closed

        # Build round-trip from positions
        symbols = list(positions.keys())
        if len(symbols) == 2:
            # Determine long and short legs
            sym1, sym2 = symbols
            pos1, pos2 = positions[sym1], positions[sym2]

            if pos1.get("side") == Side.LONG:
                long_sym, short_sym = sym1, sym2
                long_pos, short_pos = pos1, pos2
            else:
                long_sym, short_sym = sym2, sym1
                long_pos, short_pos = pos2, pos1

            # Check if we have entry info
            if "entry_date" not in long_pos or "entry_date" not in short_pos:
                continue

            entry_date = max(long_pos["entry_date"], short_pos["entry_date"])

            # Check if closed or open
            is_closed = long_pos.get("closed", False) and short_pos.get("closed", False)

            if is_closed:
                exit_date = max(long_pos.get("exit_date", entry_date),
                               short_pos.get("exit_date", entry_date))
                long_exit = long_pos["exit_price"]
                short_exit = short_pos["exit_price"]
                is_open = False
            elif include_open and final_prices:
                exit_date = end_date
                long_exit = final_prices.get(long_sym, long_pos["avg_price"])
                short_exit = final_prices.get(short_sym, short_pos["avg_price"])
                is_open = True
            else:
                continue  # Skip open positions if not including them

            # Calculate P&L
            # Long leg: profit when exit > entry
            # Short leg: profit when entry > exit
            long_shares = long_pos.get("shares", 0) or (
                long_pos["avg_price"] and long_exit and
                abs(long_pos.get("commission", 0) / 0.005 / long_pos["avg_price"])
                if long_pos.get("commission") else 100
            )
            short_shares = short_pos.get("shares", 0) or (
                short_pos["avg_price"] and short_exit and
                abs(short_pos.get("commission", 0) / 0.005 / short_pos["avg_price"])
                if short_pos.get("commission") else 100
            )

            # Reconstruct shares from trades
            long_entry_trades = [
                t for t in trades if t.symbol == long_sym and t.side == Side.LONG
            ]
            short_entry_trades = [
                t for t in trades if t.symbol == short_sym and t.side == Side.SHORT
            ]

            if long_entry_trades and short_entry_trades:
                long_shares = sum(t.shares for t in long_entry_trades)
                short_shares = sum(t.shares for t in short_entry_trades)

            long_pnl = long_shares * (long_exit - long_pos["avg_price"])
            short_pnl = short_shares * (short_pos["avg_price"] - short_exit)
            total_pnl = long_pnl + short_pnl

            # Commission
            total_commission = (
                long_pos.get("commission", 0) +
                short_pos.get("commission", 0) +
                long_pos.get("exit_commission", 0) +
                short_pos.get("exit_commission", 0)
            )
            total_pnl -= total_commission

            # Entry notional for return calculation
            entry_notional = (long_shares * long_pos["avg_price"] +
                            short_shares * short_pos["avg_price"])

            return_pct = total_pnl / entry_notional if entry_notional > 0 else 0.0

            # Holding days
            holding_days = (exit_date - entry_date).days if exit_date else 0

            round_trips.append(RoundTrip(
                pair_id=pair_id,
                entry_date=entry_date,
                exit_date=exit_date,
                long_symbol=long_sym,
                short_symbol=short_sym,
                long_entry_price=long_pos["avg_price"],
                short_entry_price=short_pos["avg_price"],
                long_exit_price=long_exit,
                short_exit_price=short_exit,
                long_shares=long_shares,
                short_shares=short_shares,
                pnl=total_pnl,
                holding_days=holding_days,
                return_pct=return_pct,
                commission=total_commission,
                is_open=is_open,
            ))

    return round_trips


def calculate_trade_statistics(round_trips: list[RoundTrip]) -> TradeStatistics:
    """Calculate aggregate statistics from round-trip trades.

    Args:
        round_trips: List of matched round-trip trades.

    Returns:
        TradeStatistics with aggregated metrics.
    """
    if not round_trips:
        return TradeStatistics(
            total_round_trips=0,
            closed_round_trips=0,
            open_round_trips=0,
            winning_trades=0,
            losing_trades=0,
            win_rate=0.0,
            avg_win=0.0,
            avg_loss=0.0,
            profit_factor=0.0,
            avg_holding_days=0.0,
            max_holding_days=0,
            min_holding_days=0,
            avg_return_pct=0.0,
            best_trade_pct=0.0,
            worst_trade_pct=0.0,
            total_pnl=0.0,
            total_commission=0.0,
        )

    winners = [rt for rt in round_trips if rt.pnl > 0]
    losers = [rt for rt in round_trips if rt.pnl < 0]
    closed = [rt for rt in round_trips if not rt.is_open]
    open_rts = [rt for rt in round_trips if rt.is_open]

    total = len(round_trips)
    win_rate = len(winners) / total if total > 0 else 0.0

    gross_profit = sum(rt.pnl for rt in winners)
    gross_loss = abs(sum(rt.pnl for rt in losers))
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf")

    avg_win = mean(rt.pnl for rt in winners) if winners else 0.0
    avg_loss = mean(rt.pnl for rt in losers) if losers else 0.0

    holding_days = [rt.holding_days for rt in round_trips]
    returns = [rt.return_pct for rt in round_trips]

    return TradeStatistics(
        total_round_trips=total,
        closed_round_trips=len(closed),
        open_round_trips=len(open_rts),
        winning_trades=len(winners),
        losing_trades=len(losers),
        win_rate=win_rate,
        avg_win=avg_win,
        avg_loss=avg_loss,
        profit_factor=profit_factor,
        avg_holding_days=mean(holding_days) if holding_days else 0.0,
        max_holding_days=max(holding_days) if holding_days else 0,
        min_holding_days=min(holding_days) if holding_days else 0,
        avg_return_pct=mean(returns) if returns else 0.0,
        best_trade_pct=max(returns) if returns else 0.0,
        worst_trade_pct=min(returns) if returns else 0.0,
        total_pnl=sum(rt.pnl for rt in round_trips),
        total_commission=sum(rt.commission for rt in round_trips),
    )
