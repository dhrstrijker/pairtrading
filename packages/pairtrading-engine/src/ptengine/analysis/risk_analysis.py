"""Risk analysis and metrics.

This module provides tools for analyzing risk characteristics including
drawdowns, Value at Risk (VaR), and volatility metrics.
"""

from dataclasses import dataclass
from datetime import date

import numpy as np
import pandas as pd
from scipy import stats


@dataclass
class DrawdownPeriod:
    """Represents a single drawdown period.

    A drawdown period starts when equity drops below a previous peak and
    ends when equity recovers to a new peak.

    Attributes:
        start_date: Date the drawdown began
        trough_date: Date of maximum drawdown
        recovery_date: Date equity recovered (None if not yet recovered)
        peak_equity: Equity value at the start of drawdown
        trough_equity: Lowest equity value during drawdown
        drawdown_pct: Maximum drawdown as a percentage (negative value)
        duration_days: Total days from start to recovery (or current if open)
        recovery_days: Days from trough to recovery (None if not recovered)
    """

    start_date: date
    trough_date: date
    recovery_date: date | None
    peak_equity: float
    trough_equity: float
    drawdown_pct: float
    duration_days: int
    recovery_days: int | None

    @property
    def is_recovered(self) -> bool:
        """True if the drawdown has recovered."""
        return self.recovery_date is not None


@dataclass
class RiskProfile:
    """Comprehensive risk metrics for a backtest.

    Attributes:
        max_drawdown: Maximum drawdown (negative percentage)
        max_drawdown_duration: Longest drawdown duration in days
        avg_drawdown: Average drawdown depth
        num_drawdowns: Number of distinct drawdown periods
        drawdown_periods: List of individual drawdown periods
        var_95: 95% Value at Risk (daily)
        var_99: 99% Value at Risk (daily)
        cvar_95: 95% Conditional VaR (Expected Shortfall)
        cvar_99: 99% Conditional VaR
        daily_volatility: Standard deviation of daily returns
        annualized_volatility: Annualized volatility (daily * sqrt(252))
        downside_volatility: Volatility of negative returns only
        skewness: Skewness of return distribution
        kurtosis: Excess kurtosis of return distribution
        max_daily_loss: Worst single day return
        max_daily_gain: Best single day return
        sortino_ratio: Return / downside volatility
        calmar_ratio: Annualized return / max drawdown
    """

    max_drawdown: float
    max_drawdown_duration: int
    avg_drawdown: float
    num_drawdowns: int
    drawdown_periods: list[DrawdownPeriod]
    var_95: float
    var_99: float
    cvar_95: float
    cvar_99: float
    daily_volatility: float
    annualized_volatility: float
    downside_volatility: float
    skewness: float
    kurtosis: float
    max_daily_loss: float
    max_daily_gain: float
    sortino_ratio: float
    calmar_ratio: float


def analyze_drawdowns(equity_curve: pd.DataFrame) -> list[DrawdownPeriod]:
    """Identify all drawdown periods from an equity curve.

    Args:
        equity_curve: DataFrame with 'date' and 'equity' columns.

    Returns:
        List of DrawdownPeriod objects, sorted by start date.
    """
    if equity_curve.empty or len(equity_curve) < 2:
        return []

    df = equity_curve.copy()
    if "date" in df.columns:
        df = df.set_index("date")

    equity = df["equity"]
    running_max = equity.expanding().max()
    drawdown = (equity - running_max) / running_max

    periods: list[DrawdownPeriod] = []
    in_drawdown = False
    start_idx = None
    peak_value = None
    trough_idx = None
    trough_value = None

    for i, (idx, dd) in enumerate(drawdown.items()):
        if not in_drawdown and dd < 0:
            # Starting new drawdown
            in_drawdown = True
            start_idx = idx
            peak_value = running_max.iloc[i]
            trough_idx = idx
            trough_value = equity.iloc[i]
        elif in_drawdown:
            if dd < (equity.iloc[i] - peak_value) / peak_value:
                # New trough
                trough_idx = idx
                trough_value = equity.iloc[i]

            if dd >= 0:
                # Recovered - these are guaranteed to be set when in_drawdown is True
                assert trough_value is not None and peak_value is not None
                assert start_idx is not None and trough_idx is not None
                trough_dd = (trough_value - peak_value) / peak_value
                start_d = start_idx if isinstance(start_idx, date) else start_idx.date()
                trough_d = trough_idx if isinstance(trough_idx, date) else trough_idx.date()
                rec_d = idx if isinstance(idx, date) else idx.date()
                dur = (idx - start_idx).days if hasattr(idx - start_idx, "days") else 0
                rec = (idx - trough_idx).days if hasattr(idx - trough_idx, "days") else 0
                periods.append(DrawdownPeriod(
                    start_date=start_d,
                    trough_date=trough_d,
                    recovery_date=rec_d,
                    peak_equity=float(peak_value),
                    trough_equity=float(trough_value),
                    drawdown_pct=trough_dd,
                    duration_days=dur,
                    recovery_days=rec,
                ))
                in_drawdown = False

    # Handle ongoing drawdown at end
    if in_drawdown and start_idx is not None:
        assert trough_value is not None and peak_value is not None
        assert trough_idx is not None
        last_idx = drawdown.index[-1]
        trough_dd = (trough_value - peak_value) / peak_value
        start_d = start_idx if isinstance(start_idx, date) else start_idx.date()
        trough_d = trough_idx if isinstance(trough_idx, date) else trough_idx.date()
        dur = (last_idx - start_idx).days if hasattr(last_idx - start_idx, "days") else 0
        periods.append(DrawdownPeriod(
            start_date=start_d,
            trough_date=trough_d,
            recovery_date=None,
            peak_equity=float(peak_value),
            trough_equity=float(trough_value),
            drawdown_pct=trough_dd,
            duration_days=dur,
            recovery_days=None,
        ))

    return periods


def calculate_var(
    returns: pd.Series,
    confidence: float = 0.95,
    method: str = "historical",
) -> float:
    """Calculate Value at Risk.

    VaR represents the maximum expected loss at a given confidence level.

    Args:
        returns: Series of returns (daily, typically).
        confidence: Confidence level (e.g., 0.95 for 95% VaR).
        method: "historical" for percentile-based, "parametric" for normal assumption.

    Returns:
        VaR as a negative percentage (e.g., -0.02 means 2% loss).
    """
    if returns.empty or len(returns) < 5:
        return 0.0

    returns = returns.dropna()

    if method == "historical":
        return float(np.percentile(returns, (1 - confidence) * 100))
    elif method == "parametric":
        mu = returns.mean()
        sigma = returns.std()
        return float(mu + sigma * stats.norm.ppf(1 - confidence))
    else:
        raise ValueError(f"Unknown VaR method: {method}")


def calculate_cvar(
    returns: pd.Series,
    confidence: float = 0.95,
) -> float:
    """Calculate Conditional Value at Risk (Expected Shortfall).

    CVaR is the expected loss given that loss exceeds VaR.

    Args:
        returns: Series of returns.
        confidence: Confidence level.

    Returns:
        CVaR as a negative percentage.
    """
    if returns.empty or len(returns) < 5:
        return 0.0

    returns = returns.dropna()
    var = calculate_var(returns, confidence)
    tail_returns = returns[returns <= var]

    if tail_returns.empty:
        return var

    return float(tail_returns.mean())


def calculate_risk_profile(
    equity_curve: pd.DataFrame,
    daily_returns: pd.Series | None = None,
    annualized_return: float = 0.0,
    risk_free_rate: float = 0.0,
) -> RiskProfile:
    """Calculate comprehensive risk profile.

    Args:
        equity_curve: DataFrame with 'date' and 'equity' columns.
        daily_returns: Pre-calculated daily returns (optional).
        annualized_return: Annualized return for ratio calculations.
        risk_free_rate: Risk-free rate for Sharpe-like calculations.

    Returns:
        RiskProfile with all risk metrics.
    """
    # Calculate returns if not provided
    if daily_returns is None:
        if "equity" in equity_curve.columns:
            equity = equity_curve["equity"]
        else:
            equity = equity_curve.iloc[:, 0]
        daily_returns = equity.pct_change().dropna()

    returns = daily_returns.dropna()

    # Drawdown analysis
    drawdown_periods = analyze_drawdowns(equity_curve)

    if drawdown_periods:
        max_dd = min(dp.drawdown_pct for dp in drawdown_periods)
        max_dd_duration = max(dp.duration_days for dp in drawdown_periods)
        avg_dd = float(np.mean([dp.drawdown_pct for dp in drawdown_periods]))
    else:
        max_dd = 0.0
        max_dd_duration = 0
        avg_dd = 0.0

    # VaR calculations
    var_95 = calculate_var(returns, 0.95)
    var_99 = calculate_var(returns, 0.99)
    cvar_95 = calculate_cvar(returns, 0.95)
    cvar_99 = calculate_cvar(returns, 0.99)

    # Volatility
    daily_vol = float(returns.std()) if len(returns) > 1 else 0.0
    ann_vol = daily_vol * np.sqrt(252)

    # Downside volatility (semi-deviation)
    negative_returns = returns[returns < 0]
    downside_vol = float(negative_returns.std()) if len(negative_returns) > 1 else 0.0

    # Distribution moments
    if len(returns) > 3:
        skew = float(stats.skew(returns))
        kurt = float(stats.kurtosis(returns))  # Excess kurtosis
    else:
        skew = 0.0
        kurt = 0.0

    # Extreme returns
    max_loss = float(returns.min()) if len(returns) > 0 else 0.0
    max_gain = float(returns.max()) if len(returns) > 0 else 0.0

    # Risk-adjusted ratios
    downside_ann = downside_vol * np.sqrt(252)
    sortino = (annualized_return - risk_free_rate) / downside_ann if downside_ann > 0 else 0.0
    calmar = annualized_return / abs(max_dd) if max_dd != 0 else 0.0

    return RiskProfile(
        max_drawdown=max_dd,
        max_drawdown_duration=max_dd_duration,
        avg_drawdown=avg_dd,
        num_drawdowns=len(drawdown_periods),
        drawdown_periods=drawdown_periods,
        var_95=var_95,
        var_99=var_99,
        cvar_95=cvar_95,
        cvar_99=cvar_99,
        daily_volatility=daily_vol,
        annualized_volatility=ann_vol,
        downside_volatility=downside_vol,
        skewness=skew,
        kurtosis=kurt,
        max_daily_loss=max_loss,
        max_daily_gain=max_gain,
        sortino_ratio=sortino,
        calmar_ratio=calmar,
    )


def rolling_sharpe(
    returns: pd.Series,
    window: int = 60,
    risk_free_rate: float = 0.0,
) -> pd.Series:
    """Calculate rolling Sharpe ratio.

    Args:
        returns: Daily returns series.
        window: Rolling window size in days.
        risk_free_rate: Annual risk-free rate.

    Returns:
        Series of rolling Sharpe ratios.
    """
    if len(returns) < window:
        return pd.Series(dtype=float)

    daily_rf = risk_free_rate / 252
    excess_returns = returns - daily_rf

    rolling_mean = excess_returns.rolling(window).mean()
    rolling_std = excess_returns.rolling(window).std()

    # Annualize
    sharpe = (rolling_mean * 252) / (rolling_std * np.sqrt(252))

    return sharpe


def rolling_volatility(
    returns: pd.Series,
    window: int = 20,
    annualize: bool = True,
) -> pd.Series:
    """Calculate rolling volatility.

    Args:
        returns: Daily returns series.
        window: Rolling window size in days.
        annualize: If True, annualize the volatility.

    Returns:
        Series of rolling volatility values.
    """
    if len(returns) < window:
        return pd.Series(dtype=float)

    vol = returns.rolling(window).std()

    if annualize:
        vol = vol * np.sqrt(252)

    return vol


def rolling_metrics(
    returns: pd.Series,
    window: int = 60,
    risk_free_rate: float = 0.0,
) -> pd.DataFrame:
    """Calculate multiple rolling metrics.

    Args:
        returns: Daily returns series.
        window: Rolling window size in days.
        risk_free_rate: Annual risk-free rate.

    Returns:
        DataFrame with columns: date, rolling_sharpe, rolling_volatility,
        rolling_return, rolling_max_dd
    """
    if len(returns) < window:
        return pd.DataFrame()

    sharpe = rolling_sharpe(returns, window, risk_free_rate)
    vol = rolling_volatility(returns, window)
    cum_return = (1 + returns).cumprod() - 1
    rolling_ret = returns.rolling(window).mean() * 252  # Annualized

    # Rolling max drawdown
    rolling_max = cum_return.rolling(window).max()
    rolling_dd = (cum_return - rolling_max) / (1 + rolling_max)
    rolling_max_dd = rolling_dd.rolling(window).min()

    df = pd.DataFrame({
        "rolling_sharpe": sharpe,
        "rolling_volatility": vol,
        "rolling_return": rolling_ret,
        "rolling_max_dd": rolling_max_dd,
    })

    return df.dropna()
