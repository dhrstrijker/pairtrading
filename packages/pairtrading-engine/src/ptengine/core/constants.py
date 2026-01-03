"""Constants used throughout the backtesting engine."""

# Default configuration values
DEFAULT_INITIAL_CAPITAL: float = 100_000.0
DEFAULT_CAPITAL_PER_PAIR: float = 10_000.0
DEFAULT_PRICE_COLUMN: str = "adj_close"

# Trading calendar
TRADING_DAYS_PER_YEAR: int = 252

# Position and exposure limits
DEFAULT_MAX_POSITION_PCT: float = 0.10  # 10% max per position
DEFAULT_MAX_GROSS_EXPOSURE: float = 2.0  # 200% max gross exposure

# Dollar neutrality tolerance
DEFAULT_NEUTRALITY_TOLERANCE: float = 0.01  # 1% tolerance for dollar neutral

# Risk-free rate for Sharpe calculation (annualized)
DEFAULT_RISK_FREE_RATE: float = 0.0

# Minimum data requirements
MIN_TRADING_DAYS_FOR_METRICS: int = 20
