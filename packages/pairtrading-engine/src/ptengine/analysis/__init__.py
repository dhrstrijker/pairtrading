"""Strategy analysis and visualization module.

This module provides comprehensive analysis tools for backtesting results:

- **StrategyAnalyzer**: Main entry point for analysis
- **Trade Analysis**: Round-trip matching and trade statistics
- **Pair Analysis**: Per-pair performance attribution
- **Risk Analysis**: VaR, CVaR, drawdowns, and volatility metrics
- **Visualizations**: Matplotlib charts and tear sheets

Example:
    ```python
    from ptengine.analysis import StrategyAnalyzer

    # Run backtest
    result = runner.run(pit_data)

    # Analyze
    analyzer = StrategyAnalyzer(result)
    print(analyzer.full_report())

    # Generate charts
    analyzer.save_charts(Path("./analysis"))

    # Or create a single tear sheet
    analyzer.create_tear_sheet(Path("./tearsheet.pdf"))
    ```
"""

from ptengine.analysis.analyzer import StrategyAnalyzer
from ptengine.analysis.pair_analysis import (
    PairMetrics,
    analyze_pairs,
    pair_cumulative_returns,
    pair_performance_summary,
)
from ptengine.analysis.risk_analysis import (
    DrawdownPeriod,
    RiskProfile,
    analyze_drawdowns,
    calculate_cvar,
    calculate_risk_profile,
    calculate_var,
    rolling_metrics,
    rolling_sharpe,
    rolling_volatility,
)
from ptengine.analysis.trade_analysis import (
    RoundTrip,
    TradeStatistics,
    calculate_trade_statistics,
    match_round_trips,
)

__all__ = [
    # Main analyzer
    "StrategyAnalyzer",
    # Trade analysis
    "RoundTrip",
    "TradeStatistics",
    "match_round_trips",
    "calculate_trade_statistics",
    # Pair analysis
    "PairMetrics",
    "analyze_pairs",
    "pair_cumulative_returns",
    "pair_performance_summary",
    # Risk analysis
    "DrawdownPeriod",
    "RiskProfile",
    "analyze_drawdowns",
    "calculate_var",
    "calculate_cvar",
    "calculate_risk_profile",
    "rolling_sharpe",
    "rolling_volatility",
    "rolling_metrics",
]

# Visualization imports are optional (require matplotlib)
try:
    from ptengine.analysis.visualizations import (  # noqa: F401
        create_equity_chart,
        create_pair_returns_chart,
        create_risk_chart,
        create_rolling_metrics_chart,
        create_tear_sheet,
        create_trade_distribution_chart,
    )

    __all__.extend([
        "create_equity_chart",
        "create_pair_returns_chart",
        "create_trade_distribution_chart",
        "create_rolling_metrics_chart",
        "create_risk_chart",
        "create_tear_sheet",
    ])
except ImportError:
    pass  # matplotlib not installed
