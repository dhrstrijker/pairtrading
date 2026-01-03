"""Tests for portfolio management."""

from datetime import date
import pytest

from ptengine.core.types import Trade, Side
from ptengine.core.exceptions import InsufficientCapitalError
from ptengine.portfolio.portfolio import Portfolio


class TestPortfolio:
    """Tests for Portfolio class."""

    def test_initial_state(self, empty_portfolio: Portfolio):
        assert empty_portfolio.cash == 100_000.0
        assert empty_portfolio.equity == 100_000.0
        assert empty_portfolio.num_positions == 0

    def test_execute_long_trade(self, empty_portfolio: Portfolio):
        trade = Trade(
            date=date(2020, 1, 15),
            symbol="AAPL",
            side=Side.LONG,
            shares=100,
            price=100.0,
            commission=1.0,
        )
        empty_portfolio.execute_trade(trade)

        assert empty_portfolio.cash == 100_000.0 - 10_001.0
        assert "AAPL" in empty_portfolio.positions
        assert empty_portfolio.positions["AAPL"].shares == 100

    def test_execute_short_trade(self, empty_portfolio: Portfolio):
        trade = Trade(
            date=date(2020, 1, 15),
            symbol="AAPL",
            side=Side.SHORT,
            shares=100,
            price=100.0,
            commission=1.0,
        )
        empty_portfolio.execute_trade(trade)

        # Short sale: receive cash minus commission
        assert empty_portfolio.cash == 100_000.0 + 10_000.0 - 1.0

    def test_insufficient_capital_raises(self, empty_portfolio: Portfolio):
        trade = Trade(
            date=date(2020, 1, 15),
            symbol="AAPL",
            side=Side.LONG,
            shares=10000,
            price=100.0,
        )
        with pytest.raises(InsufficientCapitalError):
            empty_portfolio.execute_trade(trade)

    def test_update_prices(self, portfolio_with_position: Portfolio):
        portfolio_with_position.update_prices({"AAPL": 110.0})
        assert portfolio_with_position.positions["AAPL"].current_price == 110.0
        assert portfolio_with_position.positions["AAPL"].unrealized_pnl == 1000.0

    def test_record_equity(self, empty_portfolio: Portfolio):
        empty_portfolio.record_equity(date(2020, 1, 15))
        assert len(empty_portfolio.equity_curve) == 1
        assert empty_portfolio.equity_curve[0] == (date(2020, 1, 15), 100_000.0)

    def test_gross_exposure(self, portfolio_with_position: Portfolio):
        portfolio_with_position.update_prices({"AAPL": 100.0})
        assert portfolio_with_position.gross_exposure == 10_000.0

    def test_net_exposure(self, portfolio_with_position: Portfolio):
        portfolio_with_position.update_prices({"AAPL": 100.0})
        assert portfolio_with_position.net_exposure == 10_000.0

    def test_reset(self, portfolio_with_position: Portfolio):
        portfolio_with_position.record_equity(date(2020, 1, 15))
        portfolio_with_position.reset()

        assert portfolio_with_position.cash == 100_000.0
        assert portfolio_with_position.num_positions == 0
        assert len(portfolio_with_position.equity_curve) == 0


class TestPortfolioPairs:
    """Tests for pair position management."""

    def test_open_pair(self, empty_portfolio: Portfolio):
        long_trade = Trade(
            date=date(2020, 1, 15),
            symbol="AAPL",
            side=Side.LONG,
            shares=100,
            price=100.0,
            commission=1.0,
            pair_id="AAPL_MSFT",
        )
        short_trade = Trade(
            date=date(2020, 1, 15),
            symbol="MSFT",
            side=Side.SHORT,
            shares=50,
            price=200.0,
            commission=1.0,
            pair_id="AAPL_MSFT",
        )

        empty_portfolio.open_pair(
            pair_id="AAPL_MSFT",
            long_trade=long_trade,
            short_trade=short_trade,
            hedge_ratio=1.0,
            entry_date=date(2020, 1, 15),
        )

        assert "AAPL_MSFT" in empty_portfolio.pair_positions
        assert empty_portfolio.num_pair_positions == 1
        pair = empty_portfolio.pair_positions["AAPL_MSFT"]
        assert pair.long_position.shares == 100
        assert pair.short_position.shares == -50

    def test_close_pair(self, empty_portfolio: Portfolio):
        # First open a pair
        long_trade = Trade(
            date=date(2020, 1, 15),
            symbol="AAPL",
            side=Side.LONG,
            shares=100,
            price=100.0,
            pair_id="AAPL_MSFT",
        )
        short_trade = Trade(
            date=date(2020, 1, 15),
            symbol="MSFT",
            side=Side.SHORT,
            shares=50,
            price=200.0,
            pair_id="AAPL_MSFT",
        )
        empty_portfolio.open_pair(
            pair_id="AAPL_MSFT",
            long_trade=long_trade,
            short_trade=short_trade,
            hedge_ratio=1.0,
            entry_date=date(2020, 1, 15),
        )

        # Now close it
        close_long = Trade(
            date=date(2020, 2, 15),
            symbol="AAPL",
            side=Side.SHORT,
            shares=100,
            price=110.0,  # Profit on long
            pair_id="AAPL_MSFT",
        )
        close_short = Trade(
            date=date(2020, 2, 15),
            symbol="MSFT",
            side=Side.LONG,
            shares=50,
            price=190.0,  # Profit on short
            pair_id="AAPL_MSFT",
        )

        pnl = empty_portfolio.close_pair("AAPL_MSFT", close_long, close_short)

        assert empty_portfolio.num_pair_positions == 0
        assert pnl == 1000.0 + 500.0  # Long profit + short profit

    def test_has_pair(self, empty_portfolio: Portfolio):
        assert not empty_portfolio.has_pair("AAPL_MSFT")

        long_trade = Trade(
            date=date(2020, 1, 15),
            symbol="AAPL",
            side=Side.LONG,
            shares=100,
            price=100.0,
            pair_id="AAPL_MSFT",
        )
        short_trade = Trade(
            date=date(2020, 1, 15),
            symbol="MSFT",
            side=Side.SHORT,
            shares=50,
            price=200.0,
            pair_id="AAPL_MSFT",
        )
        empty_portfolio.open_pair(
            pair_id="AAPL_MSFT",
            long_trade=long_trade,
            short_trade=short_trade,
            hedge_ratio=1.0,
            entry_date=date(2020, 1, 15),
        )

        assert empty_portfolio.has_pair("AAPL_MSFT")
