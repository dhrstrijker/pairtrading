"""Integration tests for BacktestRunner."""

from datetime import date

import pytest
from ptdata.validation import PointInTimeDataFrame

from ptengine.backtest.config import BacktestConfig
from ptengine.backtest.runner import BacktestRunner
from ptengine.core.types import PairSignal, Signal, SignalType, WeightSignal
from ptengine.strategy.base import BaseStrategy


class DoNothingStrategy(BaseStrategy):
    """Strategy that never trades."""

    @property
    def name(self) -> str:
        return "do_nothing"

    def on_bar(self, current_date: date, pit_data: PointInTimeDataFrame) -> Signal:
        return None


class SimplePairStrategy(BaseStrategy):
    """Strategy that opens one pair and closes it later."""

    def __init__(self, symbol_a: str, symbol_b: str):
        super().__init__()
        self.symbol_a = symbol_a
        self.symbol_b = symbol_b
        self._opened = False
        self._closed = False

    @property
    def name(self) -> str:
        return f"simple_pair_{self.symbol_a}_{self.symbol_b}"

    def on_bar(self, current_date: date, pit_data: PointInTimeDataFrame) -> Signal:
        # Open on first day
        if not self._opened:
            self._opened = True
            return PairSignal(
                signal_type=SignalType.OPEN_PAIR,
                long_symbol=self.symbol_a,
                short_symbol=self.symbol_b,
            )

        # Close after 30 days
        if self._opened and not self._closed and len(pit_data.get_data()) > 30:
            self._closed = True
            return PairSignal(
                signal_type=SignalType.CLOSE_PAIR,
                long_symbol=self.symbol_a,
                short_symbol=self.symbol_b,
            )

        return None


class SimpleWeightStrategy(BaseStrategy):
    """Strategy that uses weight signals."""

    def __init__(self, symbols: list[str]):
        super().__init__()
        self.symbols = symbols
        self._first_bar = True

    @property
    def name(self) -> str:
        return "simple_weight"

    def on_bar(self, current_date: date, pit_data: PointInTimeDataFrame) -> Signal:
        if self._first_bar:
            self._first_bar = False
            # Equal weight long
            weight = 0.5 / len(self.symbols)
            weights = {s: weight for s in self.symbols}
            return WeightSignal(weights=weights)
        return None


class TestBacktestRunner:
    """Integration tests for BacktestRunner."""

    def test_do_nothing_strategy(
        self, pit_data: PointInTimeDataFrame, backtest_config: BacktestConfig
    ):
        strategy = DoNothingStrategy()
        runner = BacktestRunner(strategy, backtest_config)
        result = runner.run(pit_data)

        assert result.strategy_name == "do_nothing"
        assert result.metrics.num_trades == 0
        assert result.portfolio.equity == backtest_config.initial_capital
        assert len(result.portfolio.equity_curve) > 0

    def test_simple_pair_strategy(
        self, pit_data: PointInTimeDataFrame, backtest_config: BacktestConfig
    ):
        strategy = SimplePairStrategy("AAPL", "MSFT")
        runner = BacktestRunner(strategy, backtest_config)
        result = runner.run(pit_data)

        assert result.strategy_name == "simple_pair_AAPL_MSFT"
        assert result.metrics.num_trades == 4  # 2 open + 2 close
        assert len(result.portfolio.equity_curve) > 0

    def test_result_summary(self, pit_data: PointInTimeDataFrame, backtest_config: BacktestConfig):
        strategy = DoNothingStrategy()
        runner = BacktestRunner(strategy, backtest_config)
        result = runner.run(pit_data)

        summary = result.summary()
        assert "Backtest Results" in summary
        assert "do_nothing" in summary
        assert "Total Return" in summary

    def test_equity_curve_dataframe(
        self, pit_data: PointInTimeDataFrame, backtest_config: BacktestConfig
    ):
        strategy = DoNothingStrategy()
        runner = BacktestRunner(strategy, backtest_config)
        result = runner.run(pit_data)

        ec = result.equity_curve()
        assert "date" in ec.columns
        assert "equity" in ec.columns
        assert len(ec) > 0

    def test_trades_dataframe(
        self, pit_data: PointInTimeDataFrame, backtest_config: BacktestConfig
    ):
        strategy = SimplePairStrategy("AAPL", "MSFT")
        runner = BacktestRunner(strategy, backtest_config)
        result = runner.run(pit_data)

        trades_df = result.trades_df()
        assert len(trades_df) == 4
        assert "symbol" in trades_df.columns
        assert "price" in trades_df.columns


class TestBacktestConfig:
    """Tests for BacktestConfig validation."""

    def test_valid_config(self):
        config = BacktestConfig(
            start_date=date(2020, 1, 1),
            end_date=date(2020, 12, 31),
        )
        assert config.duration_days == 365

    def test_invalid_dates_raises(self):
        with pytest.raises(ValueError):
            BacktestConfig(
                start_date=date(2020, 12, 31),
                end_date=date(2020, 1, 1),
            )

    def test_invalid_capital_raises(self):
        with pytest.raises(ValueError):
            BacktestConfig(
                start_date=date(2020, 1, 1),
                end_date=date(2020, 12, 31),
                initial_capital=-100,
            )
