"""Simple close-price execution model.

V1 implementation: All orders fill at the closing price with no slippage.
"""

from datetime import date

from ptengine.core.types import PairSignal, WeightSignal, Trade, Side, SignalType
from ptengine.core.exceptions import ExecutionError
from ptengine.portfolio.portfolio import Portfolio
from ptengine.commission.base import CommissionModel
from ptengine.commission.models import ZeroCommission


class ClosePriceExecution:
    """Simple execution model that fills all orders at closing price.

    Features:
    - Instant fill at close price
    - No slippage
    - Full fill (no partial fills)
    - Commission via pluggable CommissionModel

    Attributes:
        commission_model: Model for calculating trade commissions
    """

    def __init__(self, commission_model: CommissionModel | None = None):
        """Initialize execution model.

        Args:
            commission_model: Model for calculating commissions (default: ZeroCommission)
        """
        self.commission_model = commission_model or ZeroCommission()

    def execute_pair_signal(
        self,
        signal: PairSignal,
        current_date: date,
        prices: dict[str, float],
        portfolio: Portfolio,
        capital_per_pair: float,
    ) -> list[Trade]:
        """Execute a pair signal at close prices.

        For OPEN_PAIR: Creates long and short trades sized to capital_per_pair.
        For CLOSE_PAIR: Closes existing pair position.

        Args:
            signal: The pair signal to execute
            current_date: Current simulation date
            prices: Current prices for all symbols
            portfolio: Current portfolio state
            capital_per_pair: Capital to allocate per pair

        Returns:
            List of trades (2 trades for open/close)

        Raises:
            ExecutionError: If prices missing or pair not found for close
        """
        long_symbol = signal.long_symbol
        short_symbol = signal.short_symbol
        pair_id = signal.get_pair_id()

        # Validate prices
        if long_symbol not in prices:
            raise ExecutionError(f"Missing price for {long_symbol}", symbol=long_symbol)
        if short_symbol not in prices:
            raise ExecutionError(f"Missing price for {short_symbol}", symbol=short_symbol)

        long_price = prices[long_symbol]
        short_price = prices[short_symbol]

        trades: list[Trade] = []

        if signal.signal_type == SignalType.OPEN_PAIR:
            # Calculate shares for long leg
            long_notional = capital_per_pair / (1 + signal.hedge_ratio)
            long_shares = long_notional / long_price

            # Calculate shares for short leg (hedged)
            short_notional = long_notional * signal.hedge_ratio
            short_shares = short_notional / short_price

            # Create trades
            long_trade = Trade(
                date=current_date,
                symbol=long_symbol,
                side=Side.LONG,
                shares=long_shares,
                price=long_price,
                commission=self.commission_model.calculate(long_shares, long_price),
                pair_id=pair_id,
            )

            short_trade = Trade(
                date=current_date,
                symbol=short_symbol,
                side=Side.SHORT,
                shares=short_shares,
                price=short_price,
                commission=self.commission_model.calculate(short_shares, short_price),
                pair_id=pair_id,
            )

            # Execute in portfolio
            portfolio.open_pair(
                pair_id=pair_id,
                long_trade=long_trade,
                short_trade=short_trade,
                hedge_ratio=signal.hedge_ratio,
                entry_date=current_date,
            )

            trades = [long_trade, short_trade]

        elif signal.signal_type == SignalType.CLOSE_PAIR:
            # Get existing pair position
            pair_position = portfolio.get_pair_position(pair_id)
            if pair_position is None:
                raise ExecutionError(f"Pair position not found: {pair_id}", reason="not_found")

            # Create closing trades
            long_shares = abs(pair_position.long_position.shares)
            short_shares = abs(pair_position.short_position.shares)

            # Sell long position
            long_trade = Trade(
                date=current_date,
                symbol=long_symbol,
                side=Side.SHORT,  # Selling
                shares=long_shares,
                price=long_price,
                commission=self.commission_model.calculate(long_shares, long_price),
                pair_id=pair_id,
            )

            # Buy to cover short position
            short_trade = Trade(
                date=current_date,
                symbol=short_symbol,
                side=Side.LONG,  # Buying to cover
                shares=short_shares,
                price=short_price,
                commission=self.commission_model.calculate(short_shares, short_price),
                pair_id=pair_id,
            )

            # Execute in portfolio
            portfolio.close_pair(pair_id, long_trade, short_trade)

            trades = [long_trade, short_trade]

        return trades

    def execute_weight_signal(
        self,
        signal: WeightSignal,
        current_date: date,
        prices: dict[str, float],
        portfolio: Portfolio,
    ) -> list[Trade]:
        """Execute a weight signal by rebalancing to target weights.

        Args:
            signal: The weight signal to execute
            current_date: Current simulation date
            prices: Current prices for all symbols
            portfolio: Current portfolio state

        Returns:
            List of trades to achieve target weights

        Raises:
            ExecutionError: If prices missing for any symbol
        """
        trades: list[Trade] = []

        # Validate all prices exist
        for symbol in signal.weights:
            if symbol not in prices:
                raise ExecutionError(f"Missing price for {symbol}", symbol=symbol)

        target_equity = portfolio.equity

        for symbol, target_weight in signal.weights.items():
            price = prices[symbol]
            target_value = target_equity * target_weight
            target_shares = target_value / price

            # Get current position
            current_position = portfolio.get_position(symbol)
            current_shares = current_position.shares if current_position else 0.0

            # Calculate trade
            shares_diff = target_shares - current_shares

            if abs(shares_diff) < 0.01:  # Skip tiny trades
                continue

            if shares_diff > 0:
                # Buy
                trade = Trade(
                    date=current_date,
                    symbol=symbol,
                    side=Side.LONG,
                    shares=abs(shares_diff),
                    price=price,
                    commission=self.commission_model.calculate(abs(shares_diff), price),
                )
            else:
                # Sell/short
                trade = Trade(
                    date=current_date,
                    symbol=symbol,
                    side=Side.SHORT,
                    shares=abs(shares_diff),
                    price=price,
                    commission=self.commission_model.calculate(abs(shares_diff), price),
                )

            # Execute trade
            portfolio.execute_trade(trade)
            trades.append(trade)

        return trades
