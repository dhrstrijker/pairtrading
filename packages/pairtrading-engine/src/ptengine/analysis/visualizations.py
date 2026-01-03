"""Visualization functions for backtest analysis.

This module provides matplotlib-based charts for analyzing backtest results.
All charts support both display and save-to-file modes.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Literal

import numpy as np
import pandas as pd

try:
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    from matplotlib.figure import Figure

    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False
    Figure = None

try:
    import seaborn as sns

    HAS_SEABORN = True
except ImportError:
    HAS_SEABORN = False

if TYPE_CHECKING:
    from ptengine.analysis.analyzer import StrategyAnalyzer
    from ptengine.analysis.risk_analysis import DrawdownPeriod, RiskProfile
    from ptengine.analysis.trade_analysis import RoundTrip

OutputMode = Literal["display", "save", "both"]


def _check_matplotlib() -> None:
    """Raise ImportError if matplotlib is not available."""
    if not HAS_MATPLOTLIB:
        raise ImportError(
            "matplotlib is required for visualizations. "
            "Install with: pip install pairtrading-engine[analysis]"
        )


def _setup_style() -> None:
    """Set up matplotlib style."""
    if HAS_SEABORN:
        sns.set_theme(style="whitegrid", palette="muted")
    else:
        plt.style.use("seaborn-v0_8-whitegrid")


def _handle_output(
    fig: Figure,
    output_mode: OutputMode,
    save_path: Path | None,
) -> Figure:
    """Handle figure output based on mode."""
    if output_mode in ("save", "both") and save_path:
        fig.savefig(save_path, dpi=150, bbox_inches="tight", facecolor="white")

    if output_mode in ("display", "both"):
        plt.show()
    elif output_mode == "save":
        plt.close(fig)

    return fig


def create_equity_chart(
    equity_curve: pd.DataFrame,
    drawdown_periods: list[DrawdownPeriod] | None = None,
    title: str = "Equity Curve",
    output_mode: OutputMode = "display",
    save_path: Path | None = None,
) -> Figure:
    """Create equity curve chart with drawdown overlay.

    Generates a two-panel chart:
    - Top panel: Equity curve with shaded drawdown regions
    - Bottom panel: Underwater (drawdown) curve

    Args:
        equity_curve: DataFrame with 'date' and 'equity' columns.
        drawdown_periods: List of DrawdownPeriod for shading.
        title: Chart title.
        output_mode: "display", "save", or "both".
        save_path: Path for saving (required if output_mode includes save).

    Returns:
        matplotlib Figure object.
    """
    _check_matplotlib()
    _setup_style()

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8), height_ratios=[3, 1], sharex=True)

    df = equity_curve.copy()
    if "date" not in df.columns and df.index.name != "date":
        df = df.reset_index()

    dates = pd.to_datetime(df["date"])
    equity = df["equity"]

    # Top panel: Equity curve
    ax1.plot(dates, equity, linewidth=1.5, color="#2E86AB", label="Equity")
    ax1.fill_between(dates, equity.iloc[0], equity, alpha=0.1, color="#2E86AB")

    # Shade drawdown periods
    if drawdown_periods:
        for dp in drawdown_periods:
            ax1.axvspan(
                pd.to_datetime(dp.start_date),
                pd.to_datetime(dp.recovery_date or dp.trough_date),
                alpha=0.15,
                color="#E74C3C",
            )

    ax1.set_ylabel("Equity ($)", fontsize=11)
    ax1.set_title(title, fontsize=14, fontweight="bold")
    ax1.legend(loc="upper left")
    ax1.grid(True, alpha=0.3)

    # Format y-axis as currency
    ax1.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f"${x:,.0f}"))

    # Bottom panel: Underwater curve
    running_max = equity.expanding().max()
    underwater = (equity - running_max) / running_max * 100

    ax2.fill_between(dates, 0, underwater, where=(underwater < 0), color="#E74C3C", alpha=0.5)
    ax2.plot(dates, underwater, linewidth=1, color="#E74C3C")
    ax2.axhline(0, color="black", linewidth=0.5)

    ax2.set_ylabel("Drawdown (%)", fontsize=11)
    ax2.set_xlabel("Date", fontsize=11)
    ax2.grid(True, alpha=0.3)

    # Format x-axis dates
    ax2.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
    ax2.xaxis.set_major_locator(mdates.MonthLocator(interval=3))
    plt.xticks(rotation=45)

    plt.tight_layout()
    return _handle_output(fig, output_mode, save_path)


def create_pair_returns_chart(
    pair_returns: pd.DataFrame,
    title: str = "Per-Pair Cumulative Returns",
    output_mode: OutputMode = "display",
    save_path: Path | None = None,
) -> Figure:
    """Create per-pair cumulative returns chart.

    Args:
        pair_returns: DataFrame with 'date', 'pair_id', 'cumulative_return'.
        title: Chart title.
        output_mode: "display", "save", or "both".
        save_path: Path for saving.

    Returns:
        matplotlib Figure object.
    """
    _check_matplotlib()
    _setup_style()

    fig, ax = plt.subplots(figsize=(12, 6))

    if pair_returns.empty:
        ax.text(0.5, 0.5, "No pair data available", ha="center", va="center", fontsize=14)
        ax.set_title(title)
        return _handle_output(fig, output_mode, save_path)

    # Get unique pairs and assign colors
    pairs = pair_returns["pair_id"].unique()
    colors = plt.cm.tab10(np.linspace(0, 1, len(pairs)))

    for pair_id, color in zip(pairs, colors):
        pair_data = pair_returns[pair_returns["pair_id"] == pair_id]
        dates = pd.to_datetime(pair_data["date"])
        returns = pair_data["cumulative_return"] * 100

        ax.plot(dates, returns, linewidth=1.5, label=pair_id, color=color)

    ax.axhline(0, color="black", linewidth=0.5, linestyle="--")
    ax.set_ylabel("Cumulative Return (%)", fontsize=11)
    ax.set_xlabel("Date", fontsize=11)
    ax.set_title(title, fontsize=14, fontweight="bold")
    ax.legend(loc="upper left", fontsize=9)
    ax.grid(True, alpha=0.3)

    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
    ax.xaxis.set_major_locator(mdates.MonthLocator(interval=3))
    plt.xticks(rotation=45)

    plt.tight_layout()
    return _handle_output(fig, output_mode, save_path)


def create_trade_distribution_chart(
    round_trips: list[RoundTrip],
    title: str = "Trade Analysis",
    output_mode: OutputMode = "display",
    save_path: Path | None = None,
) -> Figure:
    """Create trade distribution multi-panel chart.

    Four subplots:
    - P&L histogram
    - Holding period histogram
    - Return distribution
    - Trade count by month

    Args:
        round_trips: List of RoundTrip objects.
        title: Chart title.
        output_mode: "display", "save", or "both".
        save_path: Path for saving.

    Returns:
        matplotlib Figure object.
    """
    _check_matplotlib()
    _setup_style()

    fig, axes = plt.subplots(2, 2, figsize=(12, 10))
    fig.suptitle(title, fontsize=14, fontweight="bold")

    if not round_trips:
        for ax in axes.flat:
            ax.text(0.5, 0.5, "No trade data", ha="center", va="center")
        return _handle_output(fig, output_mode, save_path)

    pnls = [rt.pnl for rt in round_trips]
    holding_days = [rt.holding_days for rt in round_trips]
    returns = [rt.return_pct * 100 for rt in round_trips]
    entry_dates = [rt.entry_date for rt in round_trips]

    # P&L histogram
    ax1 = axes[0, 0]
    winners = [p for p in pnls if p > 0]
    losers = [p for p in pnls if p <= 0]

    if winners:
        ax1.hist(winners, bins=20, alpha=0.7, color="#27AE60", label=f"Winners ({len(winners)})")
    if losers:
        ax1.hist(losers, bins=20, alpha=0.7, color="#E74C3C", label=f"Losers ({len(losers)})")

    ax1.axvline(0, color="black", linewidth=1, linestyle="--")
    ax1.set_xlabel("P&L ($)")
    ax1.set_ylabel("Count")
    ax1.set_title("P&L Distribution")
    ax1.legend()
    ax1.grid(True, alpha=0.3)

    # Holding period histogram
    ax2 = axes[0, 1]
    ax2.hist(holding_days, bins=min(20, max(holding_days) if holding_days else 1),
             alpha=0.7, color="#3498DB", edgecolor="white")
    ax2.axvline(np.mean(holding_days), color="#E74C3C", linewidth=2,
                linestyle="--", label=f"Mean: {np.mean(holding_days):.1f} days")
    ax2.set_xlabel("Holding Period (days)")
    ax2.set_ylabel("Count")
    ax2.set_title("Holding Period Distribution")
    ax2.legend()
    ax2.grid(True, alpha=0.3)

    # Return distribution
    ax3 = axes[1, 0]
    ax3.hist(returns, bins=30, alpha=0.7, color="#9B59B6", edgecolor="white")
    ax3.axvline(0, color="black", linewidth=1, linestyle="--")
    ax3.axvline(np.mean(returns), color="#E74C3C", linewidth=2,
                linestyle="--", label=f"Mean: {np.mean(returns):.2f}%")
    ax3.set_xlabel("Return (%)")
    ax3.set_ylabel("Count")
    ax3.set_title("Return Distribution")
    ax3.legend()
    ax3.grid(True, alpha=0.3)

    # Trades by month
    ax4 = axes[1, 1]
    months = pd.to_datetime(entry_dates).to_period("M")
    month_counts = pd.Series(months).value_counts().sort_index()
    ax4.bar(range(len(month_counts)), month_counts.values, alpha=0.7, color="#1ABC9C")
    ax4.set_xlabel("Month")
    ax4.set_ylabel("Number of Trades")
    ax4.set_title("Trades by Month")

    # Set x-tick labels
    if len(month_counts) <= 12:
        ax4.set_xticks(range(len(month_counts)))
        ax4.set_xticklabels([str(m) for m in month_counts.index], rotation=45, ha="right")
    else:
        # Show every nth label
        step = max(1, len(month_counts) // 12)
        ax4.set_xticks(range(0, len(month_counts), step))
        ax4.set_xticklabels([str(month_counts.index[i]) for i in range(0, len(month_counts), step)],
                           rotation=45, ha="right")
    ax4.grid(True, alpha=0.3)

    plt.tight_layout()
    return _handle_output(fig, output_mode, save_path)


def create_rolling_metrics_chart(
    rolling_df: pd.DataFrame,
    title: str = "Rolling Metrics",
    output_mode: OutputMode = "display",
    save_path: Path | None = None,
) -> Figure:
    """Create rolling metrics chart.

    Four subplots showing rolling Sharpe, volatility, returns, and drawdown.

    Args:
        rolling_df: DataFrame from rolling_metrics() function.
        title: Chart title.
        output_mode: "display", "save", or "both".
        save_path: Path for saving.

    Returns:
        matplotlib Figure object.
    """
    _check_matplotlib()
    _setup_style()

    fig, axes = plt.subplots(2, 2, figsize=(12, 10), sharex=True)
    fig.suptitle(title, fontsize=14, fontweight="bold")

    if rolling_df.empty:
        for ax in axes.flat:
            ax.text(0.5, 0.5, "Insufficient data", ha="center", va="center")
        return _handle_output(fig, output_mode, save_path)

    dates = rolling_df.index

    # Rolling Sharpe
    ax1 = axes[0, 0]
    sharpe = rolling_df["rolling_sharpe"]
    ax1.plot(dates, sharpe, linewidth=1.5, color="#2E86AB")
    ax1.axhline(0, color="black", linewidth=0.5, linestyle="--")
    ax1.axhline(1, color="#27AE60", linewidth=0.5, linestyle="--", alpha=0.7)
    ax1.axhline(-1, color="#E74C3C", linewidth=0.5, linestyle="--", alpha=0.7)
    ax1.fill_between(dates, 0, sharpe, where=(sharpe > 0), alpha=0.2, color="#27AE60")
    ax1.fill_between(dates, 0, sharpe, where=(sharpe < 0), alpha=0.2, color="#E74C3C")
    ax1.set_ylabel("Sharpe Ratio")
    ax1.set_title("Rolling Sharpe Ratio")
    ax1.grid(True, alpha=0.3)

    # Rolling Volatility
    ax2 = axes[0, 1]
    vol = rolling_df["rolling_volatility"] * 100
    ax2.plot(dates, vol, linewidth=1.5, color="#9B59B6")
    ax2.fill_between(dates, 0, vol, alpha=0.2, color="#9B59B6")
    ax2.set_ylabel("Volatility (%)")
    ax2.set_title("Rolling Volatility (Annualized)")
    ax2.grid(True, alpha=0.3)

    # Rolling Return
    ax3 = axes[1, 0]
    ret = rolling_df["rolling_return"] * 100
    ax3.plot(dates, ret, linewidth=1.5, color="#E67E22")
    ax3.axhline(0, color="black", linewidth=0.5, linestyle="--")
    ax3.fill_between(dates, 0, ret, where=(ret > 0), alpha=0.2, color="#27AE60")
    ax3.fill_between(dates, 0, ret, where=(ret < 0), alpha=0.2, color="#E74C3C")
    ax3.set_ylabel("Return (%)")
    ax3.set_title("Rolling Return (Annualized)")
    ax3.grid(True, alpha=0.3)

    # Rolling Max Drawdown
    ax4 = axes[1, 1]
    mdd = rolling_df["rolling_max_dd"] * 100
    ax4.fill_between(dates, 0, mdd, color="#E74C3C", alpha=0.5)
    ax4.plot(dates, mdd, linewidth=1, color="#E74C3C")
    ax4.set_ylabel("Drawdown (%)")
    ax4.set_title("Rolling Max Drawdown")
    ax4.grid(True, alpha=0.3)

    for ax in axes[1, :]:
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
        ax.xaxis.set_major_locator(mdates.MonthLocator(interval=3))

    plt.xticks(rotation=45)
    plt.tight_layout()
    return _handle_output(fig, output_mode, save_path)


def create_risk_chart(
    returns: pd.Series,
    risk_profile: RiskProfile,
    title: str = "Risk Analysis",
    output_mode: OutputMode = "display",
    save_path: Path | None = None,
) -> Figure:
    """Create risk analysis chart.

    Three subplots:
    - Return distribution with VaR markers
    - Rolling volatility with mean
    - Drawdown histogram

    Args:
        returns: Daily returns series.
        risk_profile: RiskProfile from calculate_risk_profile().
        title: Chart title.
        output_mode: "display", "save", or "both".
        save_path: Path for saving.

    Returns:
        matplotlib Figure object.
    """
    _check_matplotlib()
    _setup_style()

    fig, axes = plt.subplots(1, 3, figsize=(15, 5))
    fig.suptitle(title, fontsize=14, fontweight="bold")

    # Return distribution with VaR
    ax1 = axes[0]
    returns_pct = returns * 100
    ax1.hist(returns_pct, bins=50, alpha=0.7, color="#3498DB", edgecolor="white", density=True)

    # VaR lines
    var_95 = risk_profile.var_95 * 100
    var_99 = risk_profile.var_99 * 100
    ax1.axvline(var_95, color="#E67E22", linewidth=2, linestyle="--",
                label=f"VaR 95%: {var_95:.2f}%")
    ax1.axvline(var_99, color="#E74C3C", linewidth=2, linestyle="--",
                label=f"VaR 99%: {var_99:.2f}%")
    ax1.axvline(0, color="black", linewidth=1)

    ax1.set_xlabel("Daily Return (%)")
    ax1.set_ylabel("Density")
    ax1.set_title("Return Distribution")
    ax1.legend(fontsize=9)
    ax1.grid(True, alpha=0.3)

    # Risk metrics summary
    ax2 = axes[1]
    ax2.axis("off")

    metrics_text = f"""
    Risk Metrics Summary
    {"=" * 30}

    Volatility (Ann.): {risk_profile.annualized_volatility * 100:.2f}%
    Downside Vol: {risk_profile.downside_volatility * 100:.2f}%

    Max Drawdown: {risk_profile.max_drawdown * 100:.2f}%
    Max DD Duration: {risk_profile.max_drawdown_duration} days

    VaR 95%: {risk_profile.var_95 * 100:.2f}%
    CVaR 95%: {risk_profile.cvar_95 * 100:.2f}%

    Skewness: {risk_profile.skewness:.3f}
    Kurtosis: {risk_profile.kurtosis:.3f}

    Sortino Ratio: {risk_profile.sortino_ratio:.2f}
    Calmar Ratio: {risk_profile.calmar_ratio:.2f}

    Worst Day: {risk_profile.max_daily_loss * 100:.2f}%
    Best Day: {risk_profile.max_daily_gain * 100:.2f}%
    """
    ax2.text(0.1, 0.9, metrics_text, transform=ax2.transAxes, fontsize=11,
             verticalalignment="top", fontfamily="monospace",
             bbox=dict(boxstyle="round", facecolor="wheat", alpha=0.5))

    # Drawdown depth histogram
    ax3 = axes[2]
    if risk_profile.drawdown_periods:
        dd_depths = [abs(dp.drawdown_pct) * 100 for dp in risk_profile.drawdown_periods]
        ax3.hist(dd_depths, bins=min(20, len(dd_depths)), alpha=0.7, color="#E74C3C",
                 edgecolor="white")
        ax3.axvline(abs(risk_profile.max_drawdown) * 100, color="#8E44AD", linewidth=2,
                    linestyle="--", label=f"Max: {abs(risk_profile.max_drawdown) * 100:.1f}%")
        ax3.legend()
    else:
        ax3.text(0.5, 0.5, "No drawdowns", ha="center", va="center")

    ax3.set_xlabel("Drawdown Depth (%)")
    ax3.set_ylabel("Count")
    ax3.set_title("Drawdown Distribution")
    ax3.grid(True, alpha=0.3)

    plt.tight_layout()
    return _handle_output(fig, output_mode, save_path)


def create_tear_sheet(
    analyzer: "StrategyAnalyzer",
    save_path: Path,
    title: str | None = None,
) -> Path:
    """Generate a comprehensive tear sheet with all analysis charts.

    Creates a single PDF or PNG file containing:
    - Equity curve with drawdowns
    - Per-pair cumulative returns
    - Trade distribution analysis
    - Rolling metrics

    This follows the standard quant "tear sheet" concept (like pyfolio).

    Args:
        analyzer: StrategyAnalyzer with computed analysis.
        save_path: Path to save the tear sheet (PDF or PNG).
        title: Optional title override.

    Returns:
        Path to the saved file.
    """
    _check_matplotlib()
    _setup_style()

    fig = plt.figure(figsize=(16, 20))
    gs = fig.add_gridspec(4, 2, hspace=0.3, wspace=0.25)

    strategy_name = analyzer.result.strategy_name
    title = title or f"Strategy Tear Sheet: {strategy_name}"
    fig.suptitle(title, fontsize=16, fontweight="bold", y=0.98)

    # Get data
    equity_curve = analyzer.result.equity_curve()
    round_trips = analyzer.round_trips
    pair_returns = analyzer.pair_cumulative_returns()
    risk_profile = analyzer.risk_profile()
    daily_returns = analyzer.result.daily_returns()
    rolling_df = analyzer.rolling_metrics()

    # 1. Equity curve (top, full width)
    ax1 = fig.add_subplot(gs[0, :])
    dates = pd.to_datetime(equity_curve["date"])
    equity = equity_curve["equity"]

    ax1.plot(dates, equity, linewidth=1.5, color="#2E86AB")
    ax1.fill_between(dates, equity.iloc[0], equity, alpha=0.1, color="#2E86AB")

    # Shade drawdown periods
    for dp in risk_profile.drawdown_periods:
        ax1.axvspan(
            pd.to_datetime(dp.start_date),
            pd.to_datetime(dp.recovery_date or dp.trough_date),
            alpha=0.15, color="#E74C3C"
        )

    ax1.set_ylabel("Equity ($)")
    ax1.set_title("Equity Curve", fontsize=12)
    ax1.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f"${x:,.0f}"))
    ax1.grid(True, alpha=0.3)

    # 2. Pair returns
    ax2 = fig.add_subplot(gs[1, 0])
    if not pair_returns.empty:
        pairs = pair_returns["pair_id"].unique()
        colors = plt.cm.tab10(np.linspace(0, 1, len(pairs)))
        for pair_id, color in zip(pairs, colors):
            pdata = pair_returns[pair_returns["pair_id"] == pair_id]
            ax2.plot(pd.to_datetime(pdata["date"]), pdata["cumulative_return"] * 100,
                    linewidth=1.5, label=pair_id, color=color)
        ax2.axhline(0, color="black", linewidth=0.5, linestyle="--")
        ax2.legend(fontsize=8, loc="upper left")
    ax2.set_ylabel("Cumulative Return (%)")
    ax2.set_title("Per-Pair Returns", fontsize=12)
    ax2.grid(True, alpha=0.3)

    # 3. P&L distribution
    ax3 = fig.add_subplot(gs[1, 1])
    if round_trips:
        pnls = [rt.pnl for rt in round_trips]
        winners = [p for p in pnls if p > 0]
        losers = [p for p in pnls if p <= 0]
        if winners:
            ax3.hist(winners, bins=15, alpha=0.7, color="#27AE60", label="Winners")
        if losers:
            ax3.hist(losers, bins=15, alpha=0.7, color="#E74C3C", label="Losers")
        ax3.axvline(0, color="black", linewidth=1, linestyle="--")
        ax3.legend()
    ax3.set_xlabel("P&L ($)")
    ax3.set_ylabel("Count")
    ax3.set_title("P&L Distribution", fontsize=12)
    ax3.grid(True, alpha=0.3)

    # 4. Rolling Sharpe
    ax4 = fig.add_subplot(gs[2, 0])
    if not rolling_df.empty:
        sharpe = rolling_df["rolling_sharpe"]
        ax4.plot(rolling_df.index, sharpe, linewidth=1.5, color="#2E86AB")
        ax4.axhline(0, color="black", linewidth=0.5, linestyle="--")
        ax4.fill_between(rolling_df.index, 0, sharpe, where=(sharpe > 0), alpha=0.2, color="#27AE60")
        ax4.fill_between(rolling_df.index, 0, sharpe, where=(sharpe < 0), alpha=0.2, color="#E74C3C")
    ax4.set_ylabel("Sharpe Ratio")
    ax4.set_title("Rolling Sharpe (60d)", fontsize=12)
    ax4.grid(True, alpha=0.3)

    # 5. Rolling Volatility
    ax5 = fig.add_subplot(gs[2, 1])
    if not rolling_df.empty:
        vol = rolling_df["rolling_volatility"] * 100
        ax5.plot(rolling_df.index, vol, linewidth=1.5, color="#9B59B6")
        ax5.fill_between(rolling_df.index, 0, vol, alpha=0.2, color="#9B59B6")
    ax5.set_ylabel("Volatility (%)")
    ax5.set_title("Rolling Volatility (60d, Ann.)", fontsize=12)
    ax5.grid(True, alpha=0.3)

    # 6. Metrics summary
    ax6 = fig.add_subplot(gs[3, 0])
    ax6.axis("off")

    metrics = analyzer.result.metrics
    trade_stats = analyzer.trade_statistics()

    summary = f"""
    Performance Summary
    {"=" * 35}

    Total Return: {metrics.total_return * 100:.2f}%
    Annualized Return: {metrics.annualized_return * 100:.2f}%
    Sharpe Ratio: {metrics.sharpe_ratio:.2f}
    Sortino Ratio: {risk_profile.sortino_ratio:.2f}

    Max Drawdown: {risk_profile.max_drawdown * 100:.2f}%
    Volatility (Ann.): {risk_profile.annualized_volatility * 100:.2f}%

    Total Trades: {trade_stats.total_round_trips}
    Win Rate: {trade_stats.win_rate * 100:.1f}%
    Profit Factor: {trade_stats.profit_factor:.2f}
    Avg Holding: {trade_stats.avg_holding_days:.1f} days
    """
    ax6.text(0.05, 0.95, summary, transform=ax6.transAxes, fontsize=11,
             verticalalignment="top", fontfamily="monospace",
             bbox=dict(boxstyle="round", facecolor="lightblue", alpha=0.3))

    # 7. Risk metrics
    ax7 = fig.add_subplot(gs[3, 1])
    ax7.axis("off")

    risk_text = f"""
    Risk Metrics
    {"=" * 35}

    VaR 95%: {risk_profile.var_95 * 100:.2f}%
    CVaR 95%: {risk_profile.cvar_95 * 100:.2f}%

    Skewness: {risk_profile.skewness:.3f}
    Kurtosis: {risk_profile.kurtosis:.3f}

    Worst Day: {risk_profile.max_daily_loss * 100:.2f}%
    Best Day: {risk_profile.max_daily_gain * 100:.2f}%

    # Drawdowns: {risk_profile.num_drawdowns}
    Max DD Duration: {risk_profile.max_drawdown_duration} days

    Calmar Ratio: {risk_profile.calmar_ratio:.2f}
    """
    ax7.text(0.05, 0.95, risk_text, transform=ax7.transAxes, fontsize=11,
             verticalalignment="top", fontfamily="monospace",
             bbox=dict(boxstyle="round", facecolor="lightyellow", alpha=0.3))

    # Save
    save_path = Path(save_path)
    fig.savefig(save_path, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)

    return save_path
