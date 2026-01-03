"""Main strategy analyzer class.

This module provides the StrategyAnalyzer class which integrates all
analysis capabilities into a single, easy-to-use interface.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd

from ptengine.results.report import BacktestResult

from ptengine.analysis.trade_analysis import (
    RoundTrip,
    TradeStatistics,
    match_round_trips,
    calculate_trade_statistics,
)
from ptengine.analysis.pair_analysis import (
    PairMetrics,
    analyze_pairs,
    pair_cumulative_returns,
    pair_performance_summary,
)
from ptengine.analysis.risk_analysis import (
    RiskProfile,
    calculate_risk_profile,
    rolling_metrics,
)


@dataclass
class StrategyAnalyzer:
    """Comprehensive analyzer for backtest results.

    Provides a unified interface for analyzing strategy performance across
    multiple dimensions: trades, pairs, and risk.

    Attributes:
        result: The BacktestResult to analyze.

    Example:
        ```python
        result = runner.run(pit_data)
        analyzer = StrategyAnalyzer(result)

        # Get pair performance
        print(analyzer.pair_summary())

        # Get risk profile
        risk = analyzer.risk_profile()
        print(f"Max Drawdown: {risk.max_drawdown:.2%}")

        # Generate tear sheet
        analyzer.create_tear_sheet(Path("./analysis.pdf"))
        ```
    """

    result: BacktestResult

    # Cached computed properties
    _round_trips: list[RoundTrip] | None = field(default=None, repr=False)
    _pair_metrics: dict[str, PairMetrics] | None = field(default=None, repr=False)
    _risk_profile: RiskProfile | None = field(default=None, repr=False)
    _trade_statistics: TradeStatistics | None = field(default=None, repr=False)

    @classmethod
    def from_result(cls, result: BacktestResult) -> "StrategyAnalyzer":
        """Create analyzer from a backtest result.

        Args:
            result: BacktestResult from a backtest run.

        Returns:
            StrategyAnalyzer instance.
        """
        return cls(result=result)

    @property
    def round_trips(self) -> list[RoundTrip]:
        """Get matched round-trip trades (cached).

        Returns:
            List of RoundTrip objects representing complete trades.
        """
        if self._round_trips is None:
            # Get final prices for marking open positions
            equity_curve = self.result.equity_curve()
            end_date = self.result.end_date

            # Try to get final prices from portfolio
            final_prices = {}
            if hasattr(self.result, "portfolio") and self.result.portfolio:
                for symbol in self.result.portfolio.get_all_symbols():
                    pos = self.result.portfolio.get_position(symbol)
                    if pos:
                        final_prices[symbol] = pos.current_price

            self._round_trips = match_round_trips(
                self.result.trade_log,
                final_prices=final_prices if final_prices else None,
                include_open=True,
                end_date=end_date,
            )
        return self._round_trips

    @property
    def pair_metrics(self) -> dict[str, PairMetrics]:
        """Get per-pair performance metrics (cached).

        Returns:
            Dictionary mapping pair_id to PairMetrics.
        """
        if self._pair_metrics is None:
            self._pair_metrics = analyze_pairs(self.round_trips)
        return self._pair_metrics

    def trade_statistics(self) -> TradeStatistics:
        """Get aggregate trade statistics.

        Returns:
            TradeStatistics with win rate, profit factor, etc.
        """
        if self._trade_statistics is None:
            self._trade_statistics = calculate_trade_statistics(self.round_trips)
        return self._trade_statistics

    def risk_profile(self) -> RiskProfile:
        """Get comprehensive risk metrics.

        Returns:
            RiskProfile with VaR, drawdowns, volatility, etc.
        """
        if self._risk_profile is None:
            equity_curve = self.result.equity_curve()
            daily_returns = self.result.daily_returns()

            self._risk_profile = calculate_risk_profile(
                equity_curve=equity_curve,
                daily_returns=daily_returns,
                annualized_return=self.result.metrics.annualized_return,
            )
        return self._risk_profile

    def pair_cumulative_returns(self) -> pd.DataFrame:
        """Get cumulative returns by pair over time.

        Returns:
            DataFrame with date, pair_id, cumulative_pnl, cumulative_return.
        """
        return pair_cumulative_returns(
            self.round_trips,
            initial_capital=self.result.initial_capital,
        )

    def pair_summary(self) -> pd.DataFrame:
        """Get summary DataFrame of pair performance.

        Returns:
            DataFrame with one row per pair, sorted by total P&L.
        """
        return pair_performance_summary(self.pair_metrics)

    def rolling_metrics(self, window: int = 60) -> pd.DataFrame:
        """Get rolling performance metrics.

        Args:
            window: Rolling window size in days.

        Returns:
            DataFrame with rolling_sharpe, rolling_volatility,
            rolling_return, rolling_max_dd.
        """
        daily_returns = self.result.daily_returns()
        return rolling_metrics(daily_returns, window=window)

    def summary_dict(self) -> dict[str, Any]:
        """Get complete analysis summary as a dictionary.

        Returns:
            Dictionary with all key metrics and statistics.
        """
        trade_stats = self.trade_statistics()
        risk = self.risk_profile()
        metrics = self.result.metrics

        return {
            # Performance
            "total_return": metrics.total_return,
            "annualized_return": metrics.annualized_return,
            "sharpe_ratio": metrics.sharpe_ratio,
            "sortino_ratio": risk.sortino_ratio,
            "calmar_ratio": risk.calmar_ratio,
            # Risk
            "max_drawdown": risk.max_drawdown,
            "max_drawdown_duration": risk.max_drawdown_duration,
            "volatility": risk.annualized_volatility,
            "var_95": risk.var_95,
            "cvar_95": risk.cvar_95,
            # Trades
            "total_trades": trade_stats.total_round_trips,
            "win_rate": trade_stats.win_rate,
            "profit_factor": trade_stats.profit_factor,
            "avg_holding_days": trade_stats.avg_holding_days,
            "avg_return_pct": trade_stats.avg_return_pct,
            # Pairs
            "num_pairs": len(self.pair_metrics),
            "best_pair": max(self.pair_metrics.values(), key=lambda x: x.total_pnl).pair_id
            if self.pair_metrics else None,
            "worst_pair": min(self.pair_metrics.values(), key=lambda x: x.total_pnl).pair_id
            if self.pair_metrics else None,
        }

    def full_report(self) -> str:
        """Generate comprehensive text report.

        Returns:
            Formatted string with complete analysis.
        """
        trade_stats = self.trade_statistics()
        risk = self.risk_profile()
        metrics = self.result.metrics

        lines = [
            "=" * 60,
            f"Strategy Analysis: {self.result.strategy_name}",
            "=" * 60,
            "",
            "PERFORMANCE",
            "-" * 40,
            f"  Total Return:      {metrics.total_return:>10.2%}",
            f"  Annualized Return: {metrics.annualized_return:>10.2%}",
            f"  Sharpe Ratio:      {metrics.sharpe_ratio:>10.2f}",
            f"  Sortino Ratio:     {risk.sortino_ratio:>10.2f}",
            f"  Calmar Ratio:      {risk.calmar_ratio:>10.2f}",
            "",
            "RISK",
            "-" * 40,
            f"  Max Drawdown:      {risk.max_drawdown:>10.2%}",
            f"  Max DD Duration:   {risk.max_drawdown_duration:>10} days",
            f"  Volatility (Ann.): {risk.annualized_volatility:>10.2%}",
            f"  VaR 95%:           {risk.var_95:>10.2%}",
            f"  CVaR 95%:          {risk.cvar_95:>10.2%}",
            f"  Skewness:          {risk.skewness:>10.3f}",
            f"  Kurtosis:          {risk.kurtosis:>10.3f}",
            "",
            "TRADES",
            "-" * 40,
            f"  Total Round-Trips: {trade_stats.total_round_trips:>10}",
            f"  Win Rate:          {trade_stats.win_rate:>10.1%}",
            f"  Profit Factor:     {trade_stats.profit_factor:>10.2f}",
            f"  Avg P&L:           ${trade_stats.total_pnl / max(trade_stats.total_round_trips, 1):>9.2f}",
            f"  Avg Holding:       {trade_stats.avg_holding_days:>10.1f} days",
            f"  Best Trade:        {trade_stats.best_trade_pct:>10.2%}",
            f"  Worst Trade:       {trade_stats.worst_trade_pct:>10.2%}",
            "",
            "PAIRS",
            "-" * 40,
        ]

        pair_df = self.pair_summary()
        if not pair_df.empty:
            for _, row in pair_df.head(10).iterrows():
                lines.append(
                    f"  {row['pair']:<15} {row['trades']:>4} trades  "
                    f"WR: {row['win_rate']:>5.1%}  P&L: ${row['total_pnl']:>8.2f}"
                )
        else:
            lines.append("  No pair data available")

        lines.extend(["", "=" * 60])

        return "\n".join(lines)

    def save_charts(self, output_dir: Path) -> list[Path]:
        """Save all analysis charts to a directory.

        Args:
            output_dir: Directory to save charts.

        Returns:
            List of paths to saved chart files.
        """
        from ptengine.analysis.visualizations import (
            create_equity_chart,
            create_pair_returns_chart,
            create_trade_distribution_chart,
            create_rolling_metrics_chart,
            create_risk_chart,
        )

        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        saved_files: list[Path] = []

        # Equity chart
        equity_path = output_dir / "equity_curve.png"
        create_equity_chart(
            self.result.equity_curve(),
            drawdown_periods=self.risk_profile().drawdown_periods,
            title=f"Equity Curve: {self.result.strategy_name}",
            output_mode="save",
            save_path=equity_path,
        )
        saved_files.append(equity_path)

        # Pair returns
        pair_returns_path = output_dir / "pair_returns.png"
        create_pair_returns_chart(
            self.pair_cumulative_returns(),
            title="Per-Pair Cumulative Returns",
            output_mode="save",
            save_path=pair_returns_path,
        )
        saved_files.append(pair_returns_path)

        # Trade distribution
        trade_dist_path = output_dir / "trade_distribution.png"
        create_trade_distribution_chart(
            self.round_trips,
            title="Trade Analysis",
            output_mode="save",
            save_path=trade_dist_path,
        )
        saved_files.append(trade_dist_path)

        # Rolling metrics
        rolling_path = output_dir / "rolling_metrics.png"
        create_rolling_metrics_chart(
            self.rolling_metrics(),
            title="Rolling Metrics (60-day)",
            output_mode="save",
            save_path=rolling_path,
        )
        saved_files.append(rolling_path)

        # Risk chart
        risk_path = output_dir / "risk_analysis.png"
        create_risk_chart(
            self.result.daily_returns(),
            self.risk_profile(),
            title="Risk Analysis",
            output_mode="save",
            save_path=risk_path,
        )
        saved_files.append(risk_path)

        return saved_files

    def create_tear_sheet(self, save_path: Path) -> Path:
        """Generate comprehensive tear sheet.

        Creates a single PDF or PNG file with all analysis charts
        in a grid layout.

        Args:
            save_path: Path to save the tear sheet.

        Returns:
            Path to the saved file.
        """
        from ptengine.analysis.visualizations import create_tear_sheet

        return create_tear_sheet(self, save_path)
