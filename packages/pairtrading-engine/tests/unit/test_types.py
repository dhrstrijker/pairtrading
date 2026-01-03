"""Tests for core types."""

from datetime import date
import pytest

from ptengine.core.types import (
    Side,
    SignalType,
    PairSignal,
    WeightSignal,
    Position,
    PairPosition,
    Trade,
)


class TestSide:
    """Tests for Side enum."""

    def test_long_side(self):
        assert Side.LONG.name == "LONG"

    def test_short_side(self):
        assert Side.SHORT.name == "SHORT"

    def test_negate_long(self):
        assert -Side.LONG == Side.SHORT

    def test_negate_short(self):
        assert -Side.SHORT == Side.LONG


class TestPairSignal:
    """Tests for PairSignal."""

    def test_create_open_signal(self):
        signal = PairSignal(
            signal_type=SignalType.OPEN_PAIR,
            long_symbol="AAPL",
            short_symbol="MSFT",
        )
        assert signal.long_symbol == "AAPL"
        assert signal.short_symbol == "MSFT"
        assert signal.hedge_ratio == 1.0

    def test_create_with_hedge_ratio(self):
        signal = PairSignal(
            signal_type=SignalType.OPEN_PAIR,
            long_symbol="AAPL",
            short_symbol="MSFT",
            hedge_ratio=1.5,
        )
        assert signal.hedge_ratio == 1.5

    def test_same_symbol_raises(self):
        with pytest.raises(ValueError):
            PairSignal(
                signal_type=SignalType.OPEN_PAIR,
                long_symbol="AAPL",
                short_symbol="AAPL",
            )

    def test_negative_hedge_ratio_raises(self):
        with pytest.raises(ValueError):
            PairSignal(
                signal_type=SignalType.OPEN_PAIR,
                long_symbol="AAPL",
                short_symbol="MSFT",
                hedge_ratio=-0.5,
            )

    def test_symbols_property(self):
        signal = PairSignal(
            signal_type=SignalType.OPEN_PAIR,
            long_symbol="AAPL",
            short_symbol="MSFT",
        )
        assert signal.symbols == ("AAPL", "MSFT")

    def test_get_pair_id_default(self):
        signal = PairSignal(
            signal_type=SignalType.OPEN_PAIR,
            long_symbol="AAPL",
            short_symbol="MSFT",
        )
        assert signal.get_pair_id() == "AAPL_MSFT"

    def test_get_pair_id_custom(self):
        signal = PairSignal(
            signal_type=SignalType.OPEN_PAIR,
            long_symbol="AAPL",
            short_symbol="MSFT",
            pair_id="my_pair",
        )
        assert signal.get_pair_id() == "my_pair"


class TestWeightSignal:
    """Tests for WeightSignal."""

    def test_create_weight_signal(self):
        signal = WeightSignal(weights={"AAPL": 0.5, "MSFT": -0.5})
        assert signal.weights["AAPL"] == 0.5
        assert signal.weights["MSFT"] == -0.5

    def test_empty_weights_raises(self):
        with pytest.raises(ValueError):
            WeightSignal(weights={})

    def test_net_exposure(self):
        signal = WeightSignal(weights={"AAPL": 0.3, "MSFT": -0.3})
        assert signal.net_exposure == 0.0

    def test_gross_exposure(self):
        signal = WeightSignal(weights={"AAPL": 0.3, "MSFT": -0.3})
        assert signal.gross_exposure == 0.6

    def test_is_dollar_neutral_true(self):
        signal = WeightSignal(weights={"AAPL": 0.3, "MSFT": -0.3})
        assert signal.is_dollar_neutral()

    def test_is_dollar_neutral_false(self):
        signal = WeightSignal(weights={"AAPL": 0.5, "MSFT": -0.3})
        assert not signal.is_dollar_neutral()

    def test_symbols_property(self):
        signal = WeightSignal(weights={"AAPL": 0.3, "MSFT": -0.3, "GOOGL": 0.0})
        assert sorted(signal.symbols) == ["AAPL", "GOOGL", "MSFT"]


class TestPosition:
    """Tests for Position."""

    def test_create_position(self):
        pos = Position(
            symbol="AAPL",
            shares=100,
            avg_entry_price=150.0,
            current_price=155.0,
        )
        assert pos.symbol == "AAPL"
        assert pos.shares == 100
        assert pos.avg_entry_price == 150.0

    def test_long_side(self):
        pos = Position(symbol="AAPL", shares=100, avg_entry_price=150.0)
        assert pos.side == Side.LONG

    def test_short_side(self):
        pos = Position(symbol="AAPL", shares=-100, avg_entry_price=150.0)
        assert pos.side == Side.SHORT

    def test_flat_side(self):
        pos = Position(symbol="AAPL", shares=0, avg_entry_price=0.0)
        assert pos.side is None

    def test_is_flat(self):
        pos = Position(symbol="AAPL", shares=0, avg_entry_price=0.0)
        assert pos.is_flat

    def test_market_value(self):
        pos = Position(symbol="AAPL", shares=100, avg_entry_price=150.0, current_price=160.0)
        assert pos.market_value == 16000.0

    def test_unrealized_pnl(self):
        pos = Position(symbol="AAPL", shares=100, avg_entry_price=150.0, current_price=160.0)
        assert pos.unrealized_pnl == 1000.0

    def test_add_shares_opening(self):
        pos = Position(symbol="AAPL", shares=0, avg_entry_price=0.0)
        realized = pos.add_shares(100, 150.0)
        assert pos.shares == 100
        assert pos.avg_entry_price == 150.0
        assert realized == 0.0

    def test_add_shares_averaging_in(self):
        pos = Position(symbol="AAPL", shares=100, avg_entry_price=150.0)
        realized = pos.add_shares(100, 160.0)
        assert pos.shares == 200
        assert pos.avg_entry_price == 155.0  # (150*100 + 160*100) / 200
        assert realized == 0.0

    def test_add_shares_reducing_long(self):
        pos = Position(symbol="AAPL", shares=100, avg_entry_price=150.0, current_price=160.0)
        realized = pos.add_shares(-50, 160.0)
        assert pos.shares == 50
        assert realized == 500.0  # 50 * (160 - 150)


class TestTrade:
    """Tests for Trade."""

    def test_create_trade(self):
        trade = Trade(
            date=date(2020, 1, 15),
            symbol="AAPL",
            side=Side.LONG,
            shares=100,
            price=150.0,
        )
        assert trade.symbol == "AAPL"
        assert trade.shares == 100
        assert trade.price == 150.0

    def test_negative_shares_raises(self):
        with pytest.raises(ValueError):
            Trade(
                date=date(2020, 1, 15),
                symbol="AAPL",
                side=Side.LONG,
                shares=-100,
                price=150.0,
            )

    def test_negative_price_raises(self):
        with pytest.raises(ValueError):
            Trade(
                date=date(2020, 1, 15),
                symbol="AAPL",
                side=Side.LONG,
                shares=100,
                price=-150.0,
            )

    def test_notional(self):
        trade = Trade(
            date=date(2020, 1, 15),
            symbol="AAPL",
            side=Side.LONG,
            shares=100,
            price=150.0,
        )
        assert trade.notional == 15000.0

    def test_total_cost(self):
        trade = Trade(
            date=date(2020, 1, 15),
            symbol="AAPL",
            side=Side.LONG,
            shares=100,
            price=150.0,
            commission=5.0,
        )
        assert trade.total_cost == 15005.0

    def test_signed_shares_long(self):
        trade = Trade(
            date=date(2020, 1, 15),
            symbol="AAPL",
            side=Side.LONG,
            shares=100,
            price=150.0,
        )
        assert trade.signed_shares == 100

    def test_signed_shares_short(self):
        trade = Trade(
            date=date(2020, 1, 15),
            symbol="AAPL",
            side=Side.SHORT,
            shares=100,
            price=150.0,
        )
        assert trade.signed_shares == -100
