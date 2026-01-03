"""Core types and exceptions for pairtrading-data."""

from ptdata.core.types import PriceBar, CorporateAction, CorporateActionType
from ptdata.core.exceptions import (
    PTDataError,
    LookAheadBiasError,
    SurvivorshipBiasError,
    InsufficientDataError,
    DataQualityError,
)
from ptdata.core.constants import (
    DEFAULT_CACHE_EXPIRY_DAYS,
    DEFAULT_MAX_CONSECUTIVE_MISSING,
    DEFAULT_EXTREME_MOVE_THRESHOLD,
)

__all__ = [
    # Types
    "PriceBar",
    "CorporateAction",
    "CorporateActionType",
    # Exceptions
    "PTDataError",
    "LookAheadBiasError",
    "SurvivorshipBiasError",
    "InsufficientDataError",
    "DataQualityError",
    # Constants
    "DEFAULT_CACHE_EXPIRY_DAYS",
    "DEFAULT_MAX_CONSECUTIVE_MISSING",
    "DEFAULT_EXTREME_MOVE_THRESHOLD",
]
