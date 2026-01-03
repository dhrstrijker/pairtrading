"""Constants and default values for pairtrading-data."""

from decimal import Decimal

# Cache settings
DEFAULT_CACHE_EXPIRY_DAYS: int = 1
DEFAULT_CACHE_DIR: str = "./data/cache"

# Data quality settings
DEFAULT_MAX_CONSECUTIVE_MISSING: int = 5
DEFAULT_EXTREME_MOVE_THRESHOLD: float = 0.50  # 50% single-day move is suspicious

# API settings
DEFAULT_API_TIMEOUT: float = 30.0
DEFAULT_API_RETRY_COUNT: int = 3
DEFAULT_API_RETRY_DELAY: float = 1.0

# Data validation
MIN_PRICE: Decimal = Decimal("0.001")  # Minimum valid price (avoid division by zero)
MAX_PRICE: Decimal = Decimal("1000000")  # Maximum reasonable price

# Date formats
DATE_FORMAT: str = "%Y-%m-%d"
DATETIME_FORMAT: str = "%Y-%m-%d %H:%M:%S"

# Column names (standardized across the library)
COLUMN_SYMBOL: str = "symbol"
COLUMN_DATE: str = "date"
COLUMN_OPEN: str = "open"
COLUMN_HIGH: str = "high"
COLUMN_LOW: str = "low"
COLUMN_CLOSE: str = "close"
COLUMN_ADJ_CLOSE: str = "adj_close"
COLUMN_VOLUME: str = "volume"

PRICE_COLUMNS: list[str] = [
    COLUMN_SYMBOL,
    COLUMN_DATE,
    COLUMN_OPEN,
    COLUMN_HIGH,
    COLUMN_LOW,
    COLUMN_CLOSE,
    COLUMN_ADJ_CLOSE,
    COLUMN_VOLUME,
]
